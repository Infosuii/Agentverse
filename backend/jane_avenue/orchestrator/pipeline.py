"""Analysis pipeline (MASTER_PROMPT 9.9). Owner: agent-1.

Stages run in order: parsing, researching, precedents, modelling, verifying, reporting. The `Analysis` is saved
after every stage, and every stage start/end (plus each research step) is appended to the event stream that the
SSE endpoint serves. Module functions are looked up at call time (`policy.parse_policy`, ...) so that owners'
replacements and test monkeypatches are picked up without touching this file.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from .. import data, engine, evaluation, policy, precedents, report, research, simulation, verification
from ..config import get_settings
from ..contracts import (
    Analysis,
    AnalysisEvent,
    AnalysisRequest,
    EventType,
    ResearchStep,
    Source,
    Stage,
    utcnow,
)
from ..store import AnalysisStore
from .logcontext import analysis_context, stage_context

log = logging.getLogger(__name__)


class Emitter:
    """Appends `AnalysisEvent`s with a per-analysis seq (1, 2, 3, ...), read and written under one store lock."""

    def __init__(self, store: AnalysisStore, analysis_id: str) -> None:
        self.store = store
        self.analysis_id = analysis_id

    def __call__(self, type: EventType, message: str, stage: Stage | None = None,
                 data: dict[str, Any] | None = None) -> AnalysisEvent:
        return self.store.append_next_event(self.analysis_id, lambda seq: AnalysisEvent(
            analysis_id=self.analysis_id, seq=seq, ts=utcnow(), type=type, stage=stage, message=message, data=data))


def create_analysis(store: AnalysisStore, request: AnalysisRequest) -> Analysis:
    now = utcnow()
    analysis = Analysis(analysis_id=uuid4().hex[:12], created_at=now, updated_at=now, status="queued",
                        mode=get_settings().mode, request=request)
    store.save(analysis)
    return analysis


def collect_sources(analysis: Analysis) -> list[Source]:
    """Union of research, precedent, assumption and baseline sources, de-duplicated by ID (first one wins)."""
    seen: dict[str, Source] = {}

    def add(src: Source | None) -> None:
        if src is not None and src.source_id not in seen:
            seen[src.source_id] = src

    if analysis.research:
        for s in analysis.research.sources:
            add(s)
    if analysis.precedents:
        for s in analysis.precedents.sources:
            add(s)
    if analysis.simulation:
        for a in analysis.simulation.assumptions:
            for sid in a.source_ids:
                add(data.registry.get_source(sid))
        for sid in data.registry.load_baseline().source_ids:
            add(data.registry.get_source(sid))
    return list(seen.values())


class _Run:
    """Mutable holder for one pipeline run, so stage functions can replace the analysis object."""

    def __init__(self, store: AnalysisStore, analysis: Analysis) -> None:
        self.store = store
        self.a = analysis
        self.emit = Emitter(store, analysis.analysis_id)

    def save(self, **update: Any) -> None:
        self.a = self.a.model_copy(update={**update, "updated_at": utcnow()}, deep=True)
        self.store.save(self.a)

    def stage(self, name: Stage, fn: Callable[[], dict[str, Any] | None]) -> None:
        with stage_context(name):
            self.save(status=name)
            self.emit("stage_started", f"Started {name}", stage=name)
            t0 = time.perf_counter()
            update = fn() or {}
            elapsed = int((time.perf_counter() - t0) * 1000)
            self.a = self.a.model_copy(update=update, deep=True)
            timings = {**self.a.stage_timings_ms, name: elapsed}
            self.save(stage_timings_ms=timings, sources=collect_sources(self.a))
            self.emit("stage_completed", f"Completed {name} in {elapsed} ms", stage=name,
                      data={"duration_ms": elapsed})
            log.info("stage completed in %d ms", elapsed)


def _parsing(run: _Run) -> dict[str, Any]:
    req = run.a.request
    spec = req.policy_override or policy.parse_policy(req.query)
    scope = policy.check_scope(spec)
    if not scope.forecast_allowed:
        run.emit("warning", "Policy is out of scope: " + "; ".join(scope.reasons), stage="parsing",
                 data={"reasons": scope.reasons})
    return {"policy": spec, "scope": scope}


def _researching(run: _Run) -> dict[str, Any]:
    req = run.a.request
    if req.reuse_research_from:
        prev = run.store.get(req.reuse_research_from)
        if prev is None or prev.research is None:
            run.emit("warning", f"No research to reuse from {req.reuse_research_from}; running research.",
                     stage="researching")
        else:
            run.emit("log", f"Reused research from analysis {req.reuse_research_from}", stage="researching")
            return {"research": prev.research.model_copy(deep=True)}
    if not req.options.run_research:
        run.emit("log", "Research skipped (run_research=false)", stage="researching")
        return {}
    if run.a.policy is None or run.a.policy.policy_type == "unsupported":
        # Research is about UK corporation tax: for any other policy it would only add off-topic evidence.
        run.emit("log", "Research skipped: the request is not a UK corporation tax change", stage="researching")
        return {}

    def on_step(step: ResearchStep) -> None:
        run.emit("research_step", step.title, stage="researching", data=step.model_dump(mode="json"))

    try:
        findings = research.run_research(run.a.policy, on_step=on_step, use_cache=req.options.use_research_cache)
    except Exception as exc:  # research failures must never fail the analysis (MASTER_PROMPT 9.2 failure policy)
        log.exception("research failed; continuing without research")
        run.emit("error", f"Research failed and was skipped: {type(exc).__name__}: {exc}", stage="researching")
        return {}
    return {"research": findings}


def _precedents(run: _Run) -> dict[str, Any]:
    return {"precedents": precedents.find_precedents(run.a.policy)}


def _modelling(run: _Run) -> dict[str, Any]:
    if run.a.scope is None or not run.a.scope.forecast_allowed:
        run.emit("log", "Modelling skipped: policy is out of scope", stage="modelling")
        return {}
    opts = run.a.request.options
    try:
        params = engine.apply_overrides(engine.default_parameters(run.a.policy), run.a.request.parameter_overrides)
        bundle = simulation.simulate(run.a.policy, params, data.registry.load_baseline(),
                                     draws=opts.monte_carlo_draws, seed=opts.seed,
                                     empirical_residuals=evaluation.revenue_relative_residuals)
    except ValueError as exc:
        # Invalid parameters fail the analysis with a clear reason. Skipping modelling instead could let verification
        # approve an analysis that has no numbers.
        run.emit("error", f"Invalid simulation parameters: {exc}", stage="modelling")
        raise ValueError(f"Invalid simulation parameters: {exc}") from exc
    return {"simulation": bundle}


def _verifying(run: _Run) -> dict[str, Any]:
    return {"verification": verification.verify(run.a)}


def _reporting(run: _Run) -> dict[str, Any]:
    if not run.a.request.options.generate_report:
        run.emit("log", "Report skipped (generate_report=false)", stage="reporting")
        return {}
    assessment = report.generate_report(run.a)
    update: dict[str, Any] = {"report": assessment}
    check_report = getattr(verification, "check_report", None)  # agent-5's REPORT-001 re-check
    if callable(check_report) and run.a.verification is not None:
        final = check_report(assessment, run.a)
        update["verification"] = final
        if _report_disagrees(assessment, final):
            # REPORT-001 changed the verdict after the report was written (e.g. an untraceable number withholds the
            # forecast). The verdict stands; rewrite the report once from it so the report and verification agree.
            run.emit("warning", f"Report check changed the verdict to {final.overall}; regenerating the report",
                     stage="reporting", data={"verification_overall": final.overall})
            log.warning("REPORT-001 changed the verdict to %s; regenerating the report", final.overall)
            update["report"] = report.generate_report(run.a.model_copy(update={"verification": final}, deep=True))
    return update


def _report_disagrees(assessment: Any, final: Any) -> bool:
    return (assessment.forecast_withheld != (not final.forecast_allowed)
            or assessment.verification_overall != final.overall)


_STAGES: tuple[tuple[Stage, Callable[[_Run], dict[str, Any] | None]], ...] = (
    ("parsing", _parsing),
    ("researching", _researching),
    ("precedents", _precedents),
    ("modelling", _modelling),
    ("verifying", _verifying),
    ("reporting", _reporting),
)


def run_analysis(store: AnalysisStore, analysis_id: str) -> Analysis:
    analysis = store.get(analysis_id)
    if analysis is None:
        raise KeyError(f"Unknown analysis {analysis_id}")
    run = _Run(store, analysis)
    with analysis_context(analysis_id):
        log.info("analysis started (mode=%s): %s", analysis.mode, analysis.request.query[:120])
        t0 = time.perf_counter()
        try:
            for name, fn in _STAGES:
                run.stage(name, lambda fn=fn: fn(run))
            run.save(status="completed")
            overall = run.a.verification.overall if run.a.verification else None
            run.emit("completed", "Analysis completed", data={"verification_overall": overall})
            log.info("analysis completed in %d ms (verification=%s)", (time.perf_counter() - t0) * 1000, overall)
        except Exception as exc:  # any unexpected failure ends the run cleanly; the error is shown in the UI
            log.exception("analysis failed during %s", run.a.status)
            message = f"{type(exc).__name__}: {exc}"
            run.save(status="failed", error=message)
            run.emit("failed", message)
    return run.a
