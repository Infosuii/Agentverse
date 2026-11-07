from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .common import Contract, Mode
from .policy import PolicySpec, ScopeDecision
from .precedents import PrecedentAnalysis
from .report import PolicyAssessment
from .research import ResearchFindings, Source
from .simulation import SimulationBundle
from .verification import VerificationReport

Stage = Literal["parsing", "researching", "precedents", "modelling", "verifying", "reporting"]
STAGES: tuple[str, ...] = Stage.__args__  # type: ignore[attr-defined]
AnalysisStatus = Literal["queued", "parsing", "researching", "precedents", "modelling", "verifying", "reporting", "completed", "failed"]
TERMINAL_STATUSES = ("completed", "failed")


class AnalysisOptions(Contract):
    run_research: bool = True
    use_research_cache: bool = True
    monte_carlo_draws: int = Field(default=2000, ge=0, le=20000)
    seed: int = 42
    generate_report: bool = True


class AnalysisRequest(Contract):
    query: str = Field(min_length=3, max_length=2000)
    policy_override: PolicySpec | None = None
    parameter_overrides: dict[str, float] = Field(default_factory=dict)
    reuse_research_from: str | None = None
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


EventType = Literal["stage_started", "stage_completed", "research_step", "log", "warning", "error", "completed", "failed"]


class AnalysisEvent(Contract):
    analysis_id: str
    seq: int
    ts: datetime
    type: EventType
    stage: Stage | None = None
    message: str
    data: dict[str, Any] | None = None   # ResearchStep dump for "research_step"


class Analysis(Contract):
    analysis_id: str
    created_at: datetime
    updated_at: datetime
    status: AnalysisStatus
    mode: Mode
    request: AnalysisRequest
    policy: PolicySpec | None = None
    scope: ScopeDecision | None = None
    research: ResearchFindings | None = None
    precedents: PrecedentAnalysis | None = None
    simulation: SimulationBundle | None = None
    verification: VerificationReport | None = None
    report: PolicyAssessment | None = None
    sources: list[Source] = Field(default_factory=list)
    error: str | None = None
    stage_timings_ms: dict[str, int] = Field(default_factory=dict)


class AnalysisSummary(Contract):
    analysis_id: str
    created_at: datetime
    status: AnalysisStatus
    query: str
    policy_description: str | None = None
    verification_overall: str | None = None


class AnalysisCreated(Contract):
    analysis_id: str
    status: AnalysisStatus


class ParseRequest(Contract):
    query: str = Field(min_length=3, max_length=2000)


class ParseResponse(Contract):
    policy: PolicySpec
    scope: ScopeDecision


class HealthResponse(Contract):
    status: Literal["ok"]
    version: str
    contract_version: str
    mode: Mode
    gemini_configured: bool
    model_fast: str
    model_deep: str
