"""FastAPI service (MASTER_PROMPT 9.9). Owner: agent-1.

Run: `uvicorn jane_avenue.api.app:app --reload --port 8000`. Every route lives under `/api`, has a `response_model`
from the contracts, and an `operation_id` equal to its function name (used by the generated frontend client).
Errors are JSON `{"message": str, "reasons": [str]}`, never a traceback.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .. import __version__, data, engine, evaluation, policy, precedents, simulation
from ..config import get_settings
from ..contracts import (
    CONTRACT_VERSION,
    TERMINAL_STATUSES,
    Analysis,
    AnalysisCreated,
    AnalysisRequest,
    AnalysisSummary,
    Assumption,
    DatasetMeta,
    EvaluationReport,
    HealthResponse,
    ParseRequest,
    ParseResponse,
    PolicyAssessment,
    PolicyChange,
    PolicySpec,
    PrecedentAnalysis,
    SimulateRequest,
    SimulationBundle,
    Source,
)
from ..orchestrator import pipeline
from ..store import AnalysisStore

log = logging.getLogger(__name__)

SSE_POLL_SECONDS = 0.25
SSE_PING_SECONDS = 15.0


class ErrorBody(BaseModel):
    message: str
    reasons: list[str] = Field(default_factory=list)


class ApiError(Exception):
    def __init__(self, status_code: int, message: str, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.reasons = reasons or []


_ERRORS = {404: {"model": ErrorBody}, 409: {"model": ErrorBody}, 422: {"model": ErrorBody}}


def _operation_id(route: APIRoute) -> str:
    return route.name


def _sse_frame(event_json: str, seq: int, type_: str) -> str:
    return f"id: {seq}\nevent: {type_}\ndata: {event_json}\n\n"


def create_app(store: AnalysisStore | None = None, *, use_executor: bool | None = None) -> FastAPI:
    """Build the app. With an explicit `store` (tests), analyses run inline as a background task, which the
    TestClient completes before returning; otherwise they run on a 2-worker thread pool so two can run at once."""
    settings = get_settings()
    if use_executor is None:
        use_executor = store is None
    app = FastAPI(title="Jane Avenue API", version=__version__,
                  description="AI-powered UK fiscal policy simulator. Prototype. Not official government analysis.",
                  generate_unique_id_function=_operation_id)
    app.state.store = store or AnalysisStore(settings.db_path)
    app.state.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis") if use_executor else None
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])

    def get_store() -> AnalysisStore:
        return app.state.store

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content=ErrorBody(message=exc.message, reasons=exc.reasons).model_dump())

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled API error")
        return JSONResponse(status_code=500, content=ErrorBody(
            message="Internal error", reasons=[f"{type(exc).__name__}: {exc}"]).model_dump())

    def _require(analysis_id: str) -> Analysis:
        analysis = get_store().get(analysis_id)
        if analysis is None:
            raise ApiError(404, f"Analysis {analysis_id} not found")
        return analysis

    # ---- health and policy ------------------------------------------------------------------------------------
    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        s = get_settings()
        return HealthResponse(status="ok", version=__version__, contract_version=CONTRACT_VERSION, mode=s.mode,
                              gemini_configured=s.gemini_configured, model_fast=s.model_fast, model_deep=s.model_deep)

    @app.post("/api/policy/parse", response_model=ParseResponse)
    def parse_policy(body: ParseRequest) -> ParseResponse:
        spec = policy.parse_policy(body.query)
        return ParseResponse(policy=spec, scope=policy.check_scope(spec))

    @app.post("/api/policy/scope", response_model=ParseResponse)
    def check_scope(spec: PolicySpec) -> ParseResponse:
        return ParseResponse(policy=spec, scope=policy.check_scope(spec))

    # ---- analyses ---------------------------------------------------------------------------------------------
    def _run(analysis_id: str) -> None:
        if app.state.executor is not None:
            app.state.executor.submit(pipeline.run_analysis, get_store(), analysis_id)
        else:
            pipeline.run_analysis(get_store(), analysis_id)

    @app.post("/api/analyses", response_model=AnalysisCreated, status_code=202, responses=_ERRORS)
    def create_analysis(body: AnalysisRequest, background: BackgroundTasks) -> AnalysisCreated:
        if body.reuse_research_from and get_store().get(body.reuse_research_from) is None:
            raise ApiError(404, f"Analysis {body.reuse_research_from} (reuse_research_from) not found")
        analysis = pipeline.create_analysis(get_store(), body)
        background.add_task(_run, analysis.analysis_id)
        return AnalysisCreated(analysis_id=analysis.analysis_id, status=analysis.status)

    @app.get("/api/analyses", response_model=list[AnalysisSummary])
    def list_analyses(limit: Annotated[int, Query(ge=1, le=500)] = 50) -> list[AnalysisSummary]:
        return get_store().list(limit)

    @app.get("/api/analyses/{analysis_id}", response_model=Analysis, responses=_ERRORS)
    def get_analysis(analysis_id: str) -> Analysis:
        return _require(analysis_id)

    @app.get("/api/analyses/{analysis_id}/events", response_class=StreamingResponse, responses={
        200: {"description": "Server-sent events: `id: <seq>`, `event: <type>`, `data: <AnalysisEvent JSON>`.",
              "content": {"text/event-stream": {}}}, **_ERRORS})
    async def stream_events(analysis_id: str, after_seq: Annotated[int, Query(ge=0)] = 0,
                            last_event_id: Annotated[str | None, Header()] = None) -> StreamingResponse:
        st = get_store()
        if await run_in_threadpool(st.status, analysis_id) is None:
            raise ApiError(404, f"Analysis {analysis_id} not found")
        start = after_seq
        if last_event_id and last_event_id.strip().isdigit():
            start = max(start, int(last_event_id.strip()))

        async def gen():
            cursor = start
            loop = asyncio.get_running_loop()
            last_sent = loop.time()
            while True:
                events = await run_in_threadpool(st.events_after, analysis_id, cursor)
                for ev in events:
                    cursor = ev.seq
                    last_sent = loop.time()
                    yield _sse_frame(ev.model_dump_json(), ev.seq, ev.type)
                    if ev.type in TERMINAL_STATUSES:
                        return
                if not events:
                    status = await run_in_threadpool(st.status, analysis_id)
                    if status in TERMINAL_STATUSES:
                        # terminal and nothing new after one more read: done
                        if not await run_in_threadpool(st.events_after, analysis_id, cursor):
                            return
                        continue
                    if loop.time() - last_sent >= SSE_PING_SECONDS:
                        last_sent = loop.time()
                        yield ": ping\n\n"
                await asyncio.sleep(SSE_POLL_SECONDS)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/analyses/{analysis_id}/report", response_model=PolicyAssessment, responses=_ERRORS)
    def get_report(analysis_id: str) -> PolicyAssessment:
        analysis = _require(analysis_id)
        if analysis.report is None:
            raise ApiError(409, "Report is not ready", [f"Analysis status is {analysis.status}"])
        return analysis.report

    @app.get("/api/analyses/{analysis_id}/report.md", response_class=Response, responses={
        200: {"content": {"text/markdown": {}}}, **_ERRORS})
    def get_report_markdown(analysis_id: str) -> Response:
        analysis = _require(analysis_id)
        if analysis.report is None:
            raise ApiError(409, "Report is not ready", [f"Analysis status is {analysis.status}"])
        return Response(content=analysis.report.markdown, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="jane-avenue-{analysis_id}.md"'})

    # ---- fast re-simulation -----------------------------------------------------------------------------------
    @app.post("/api/simulate", response_model=SimulationBundle, responses=_ERRORS)
    def simulate(body: SimulateRequest) -> SimulationBundle:
        scope = policy.check_scope(body.policy)
        if not scope.forecast_allowed:
            raise ApiError(422, "Policy is out of scope; no forecast is produced", scope.reasons)
        try:
            params = engine.apply_overrides(engine.default_parameters(body.policy), body.parameter_overrides)
        except ValueError as exc:
            raise ApiError(422, "Invalid parameter override", [str(exc)]) from exc
        return simulation.simulate(body.policy, params, data.registry.load_baseline(), draws=body.monte_carlo_draws,
                                   seed=body.seed, include_sensitivity=body.include_sensitivity,
                                   empirical_residuals=evaluation.revenue_relative_residuals)

    # ---- reference data ---------------------------------------------------------------------------------------
    @app.get("/api/parameters", response_model=list[Assumption])
    def list_parameters() -> list[Assumption]:
        return list(engine.default_parameters().values())

    @app.get("/api/precedents", response_model=list[PolicyChange])
    def list_precedents(tax: str = "corporation_tax") -> list[PolicyChange]:
        return data.registry.load_policy_changes(tax)

    @app.post("/api/precedents/match", response_model=PrecedentAnalysis)
    def match_precedents(spec: PolicySpec, k: Annotated[int, Query(ge=1, le=50)] = 5) -> PrecedentAnalysis:
        return precedents.find_precedents(spec, k=k)

    @app.get("/api/sources", response_model=list[Source])
    def list_sources() -> list[Source]:
        return data.registry.list_sources()

    @app.get("/api/sources/{source_id}", response_model=Source, responses=_ERRORS)
    def get_source(source_id: str) -> Source:
        src = data.registry.get_source(source_id)
        if src is None:
            raise ApiError(404, f"Source {source_id} not found")
        return src

    @app.get("/api/datasets", response_model=list[DatasetMeta])
    def list_datasets() -> list[DatasetMeta]:
        return data.registry.list_datasets()

    @app.get("/api/evaluation", response_model=EvaluationReport)
    def get_evaluation() -> EvaluationReport:
        return evaluation.load_results()

    return app


app = create_app()
