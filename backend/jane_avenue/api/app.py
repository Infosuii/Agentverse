"""FastAPI service (MASTER_PROMPT 9.9). Owner: agent-1.

Run: `uvicorn jane_avenue.api.app:app --reload --port 8000`. Every route lives under `/api`, has a `response_model`
from the contracts, and an `operation_id` equal to its function name (used by the generated frontend client).
Errors are JSON `{"message": str, "reasons": [str]}`, never a traceback.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Literal

from fastapi import BackgroundTasks, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import __version__, charts, data, engine, evaluation, policy, precedents, simulation
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
    MetricName,
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
from ..orchestrator.logcontext import configure_logging
from ..simulation.montecarlo import simulate_draws
from ..store import AnalysisStore
from .ratelimit import TokenBucket

log = logging.getLogger(__name__)

SSE_POLL_SECONDS = 0.25
SSE_PING_SECONDS = 15.0


class ErrorBody(BaseModel):
    message: str
    reasons: list[str] = Field(default_factory=list)


class ApiError(Exception):
    def __init__(self, status_code: int, message: str, reasons: list[str] | None = None,
                 headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.reasons = reasons or []
        self.headers = headers


_ERRORS = {404: {"model": ErrorBody}, 409: {"model": ErrorBody}, 422: {"model": ErrorBody}}
_PNG = {200: {"content": {"image/png": {}}, "description": "PNG chart rendered with matplotlib"}}
_CREATE_ERRORS = {**_ERRORS, 429: {"model": ErrorBody, "description": "Too many analyses (live mode: 6 a minute)"}}


def _operation_id(route: APIRoute) -> str:
    return route.name


def _sse_frame(event_json: str, seq: int, type_: str) -> str:
    return f"id: {seq}\nevent: {type_}\ndata: {event_json}\n\n"


def placeholder_data_in_use() -> list[str]:
    """Dataset IDs still marked `is_placeholder`, plus "baseline" if the baseline projection is a placeholder."""
    found = [d.dataset_id for d in data.registry.list_datasets() if d.is_placeholder]
    if data.registry.load_baseline().is_placeholder:
        found.append("baseline")
    return found


def create_app(store: AnalysisStore | None = None, *, use_executor: bool | None = None,
               rate_limiter: TokenBucket | None = None) -> FastAPI:
    """Build the app. With an explicit `store` (tests), analyses run inline as a background task, which the
    TestClient completes before returning; otherwise they run on a 2-worker thread pool so two can run at once.

    `POST /api/analyses` is rate-limited to 6 a minute per client in live mode; pass `rate_limiter` to override."""
    configure_logging()
    settings = get_settings()
    if use_executor is None:
        use_executor = store is None
    if rate_limiter is None and settings.mode == "live":
        rate_limiter = TokenBucket(per_minute=6)
    try:
        placeholders = placeholder_data_in_use()
        if placeholders:
            log.warning("placeholder data in use (not real figures): %s", ", ".join(placeholders))
    except Exception:  # a broken registry must not stop the API from starting; /api/health and tests surface it
        log.exception("could not check the data registry for placeholders")
    app = FastAPI(title="Jane Avenue API", version=__version__,
                  description="AI-powered UK fiscal policy simulator. Prototype. Not official government analysis.",
                  generate_unique_id_function=_operation_id,
                  responses={422: {"model": ErrorBody, "description": "Invalid request or out-of-scope policy"}})
    app.state.store = store or AnalysisStore(settings.db_path)
    app.state.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis") if use_executor else None
    app.state.rate_limiter = rate_limiter
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])

    def get_store() -> AnalysisStore:
        return app.state.store

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                            content=ErrorBody(message=exc.message, reasons=exc.reasons).model_dump())

    @app.exception_handler(RequestValidationError)
    async def _invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        reasons = [f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg', 'invalid')}" for err in exc.errors()]
        return JSONResponse(status_code=422, content=ErrorBody(message="Invalid request", reasons=reasons).model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, headers=getattr(exc, "headers", None),
                            content=ErrorBody(message=str(exc.detail)).model_dump())

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
        try:
            placeholders = placeholder_data_in_use()
        except Exception:  # health must answer even if the registry is broken; the log has the traceback
            log.exception("health: could not read the data registry")
            placeholders = ["registry-unavailable"]
        return HealthResponse(status="ok", version=__version__, contract_version=CONTRACT_VERSION, mode=s.mode,
                              gemini_configured=s.gemini_configured, model_fast=s.model_fast, model_deep=s.model_deep,
                              data_dir_exists=s.data_dir.is_dir(), research_cache_dir_exists=s.research_cache_dir.is_dir(),
                              placeholder_datasets=placeholders)

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

    @app.post("/api/analyses", response_model=AnalysisCreated, status_code=202, responses=_CREATE_ERRORS)
    def create_analysis(body: AnalysisRequest, background: BackgroundTasks, request: Request) -> AnalysisCreated:
        limiter: TokenBucket | None = app.state.rate_limiter
        if limiter is not None:
            allowed, retry_after = limiter.take(request.client.host if request.client else "unknown")
            if not allowed:
                raise ApiError(429, "Too many analyses; please wait before starting another",
                               [f"Live mode allows {round(limiter.rate * 60)} analyses a minute. "
                                f"Try again in {retry_after} s."], headers={"Retry-After": str(retry_after)})
        if body.reuse_research_from and get_store().get(body.reuse_research_from) is None:
            raise ApiError(404, f"Analysis {body.reuse_research_from} (reuse_research_from) not found")
        if body.parameter_overrides:
            # Same 422 as /api/simulate, instead of accepting the run and failing it at the modelling stage.
            try:
                engine.apply_overrides(engine.default_parameters(body.policy_override), body.parameter_overrides)
            except ValueError as exc:
                raise ApiError(422, "Invalid parameter override", [str(exc)]) from exc
        if body.options.seed < 0:  # would otherwise fail the run at the modelling stage
            raise ApiError(422, "Invalid request", [f"options.seed: must be a non-negative integer, not "
                                                    f"{body.options.seed}"])
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
        try:
            return simulation.simulate(body.policy, params, data.registry.load_baseline(),
                                       draws=body.monte_carlo_draws, seed=body.seed,
                                       include_sensitivity=body.include_sensitivity,
                                       empirical_residuals=evaluation.revenue_relative_residuals)
        except ValueError as exc:  # simulate/compute validate parameters (agent-4, agent-3), e.g. investment shares
            raise ApiError(422, "Invalid simulation parameters", [str(exc)]) from exc

    # ---- Monte Carlo trajectory chart (matplotlib, real draws; issue #98) --------------------------------------
    def _monte_carlo_png(spec: PolicySpec, params: dict, *, draws: int, seed: int, metric: str, theme: str,
                         paths: int, empirical: list | None = None, expected: list | None = None) -> Response:
        """Re-run the draws (deterministic for a seed) and plot them. `expected` (stored bands) is compared with the
        re-run so a chart can never silently disagree with the numbers shown elsewhere."""
        try:
            d = simulate_draws(spec, params, data.registry.load_baseline(), draws=draws, seed=seed)
        except ValueError as exc:
            raise ApiError(422, "Invalid simulation parameters", [str(exc)]) from exc
        if metric not in d.metrics:
            raise ApiError(422, f"{metric} is not modelled for this policy", [f"Modelled: {', '.join(d.metrics)}"])
        note = None
        if expected:
            p50 = charts.summarise(d.metrics[metric])["p50"]
            stored = {b.fiscal_year: b.p50 for b in expected}
            if any(abs(stored.get(fy, float("nan")) - float(v)) > 1e-6 for fy, v in zip(d.fiscal_years, p50,
                                                                                      strict=True)):
                note = ("The model or data changed since this analysis ran: this chart re-runs the draws with the "
                        "current model, so it may differ from the stored figures.")
        png = charts.render_monte_carlo(d, metric, n_paths=paths, theme=theme, empirical=empirical,  # type: ignore[arg-type]
                                        note=note)
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})

    @app.get("/api/analyses/{analysis_id}/charts/montecarlo.png", response_class=Response,
             responses={**_PNG, **_ERRORS})
    def analysis_monte_carlo_png(analysis_id: str, metric: MetricName = "revenue_behavioural_gbp_bn",
                                 theme: Literal["light", "dark"] = "light",
                                 paths: Annotated[int, Query(ge=0, le=charts.MAX_PATHS)] = charts.DEFAULT_PATHS,
                                 empirical: bool = False) -> Response:
        """Monte Carlo trajectories of this analysis: a sample of its real draws, with bands from all draws."""
        analysis = _require(analysis_id)
        mc = analysis.simulation.monte_carlo if analysis.simulation else None
        if analysis.policy is None or mc is None:
            raise ApiError(409, "This analysis has no Monte Carlo results", [f"Analysis status is {analysis.status}"])
        if analysis.verification is not None and not analysis.verification.forecast_allowed:
            raise ApiError(409, "The quantitative forecast was withheld", analysis.verification.decline_reasons)
        params = engine.apply_overrides(engine.default_parameters(analysis.policy),
                                        analysis.request.parameter_overrides)
        expected = next((dist.bands for dist in mc.distributions if dist.metric == metric), None)
        band = mc.empirical_interval if empirical and metric == "revenue_behavioural_gbp_bn" else None
        return _monte_carlo_png(analysis.policy, params, draws=mc.n_draws, seed=mc.seed, metric=metric,
                                theme=theme, paths=paths, empirical=band, expected=expected)

    @app.post("/api/simulate/montecarlo.png", response_class=Response, responses={**_PNG, **_ERRORS})
    def simulate_monte_carlo_png(body: SimulateRequest, metric: MetricName = "revenue_behavioural_gbp_bn",
                                 theme: Literal["light", "dark"] = "light",
                                 paths: Annotated[int, Query(ge=0, le=charts.MAX_PATHS)] = charts.DEFAULT_PATHS,
                                 empirical: bool = False) -> Response:
        """Monte Carlo trajectories for the slider view: the same draws `/api/simulate` summarises."""
        if body.monte_carlo_draws < 1:
            raise ApiError(422, "A Monte Carlo chart needs at least one draw", ["monte_carlo_draws must be >= 1"])
        scope = policy.check_scope(body.policy)
        if not scope.forecast_allowed:
            raise ApiError(422, "Policy is out of scope; no forecast is produced", scope.reasons)
        try:
            params = engine.apply_overrides(engine.default_parameters(body.policy), body.parameter_overrides)
        except ValueError as exc:
            raise ApiError(422, "Invalid parameter override", [str(exc)]) from exc
        band = None
        if empirical and metric == "revenue_behavioural_gbp_bn":
            try:
                bundle = simulation.simulate(body.policy, params, data.registry.load_baseline(),
                                             draws=body.monte_carlo_draws, seed=body.seed, include_sensitivity=False,
                                             empirical_residuals=evaluation.revenue_relative_residuals)
            except ValueError as exc:
                raise ApiError(422, "Invalid simulation parameters", [str(exc)]) from exc
            band = bundle.monte_carlo.empirical_interval if bundle.monte_carlo else None
        return _monte_carlo_png(body.policy, params, draws=body.monte_carlo_draws, seed=body.seed, metric=metric,
                                theme=theme, paths=paths, empirical=band)

    # ---- reference data ---------------------------------------------------------------------------------------
    @app.get("/api/parameters", response_model=list[Assumption])
    def list_parameters() -> list[Assumption]:
        return list(engine.default_parameters().values())

    @app.get("/api/precedents", response_model=list[PolicyChange])
    def list_precedents(tax: str = "corporation_tax", policy_key: str | None = None) -> list[PolicyChange]:
        return data.registry.load_fiscal_changes(policy_key) if policy_key else data.registry.load_policy_changes(tax)

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
