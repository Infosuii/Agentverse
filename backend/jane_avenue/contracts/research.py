from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from .common import Confidence, Contract, Mode
from .policy import PolicySpec

PublisherType = Literal["obr", "ons", "hmrc", "hmt", "boe", "ifs", "parliament", "academic", "international_org", "news", "other"]
AccessMethod = Literal["google_search", "url_fetch", "url_context", "curated_dataset", "fixture"]


class Source(Contract):
    """Real, retrievable document. URL must come from grounding metadata, a fetch, or a curated dataset."""
    source_id: str                      # "S1"... (research) or "D-<slug>" (curated)
    title: str
    url: str
    publisher: str
    publisher_type: PublisherType = "other"
    published_date: date | None = None
    retrieved_at: datetime | None = None
    access_method: AccessMethod
    reliability_tier: Literal[1, 2, 3] = 3   # 1 official, 2 IFS/peer-reviewed, 3 other
    url_verified: bool = False
    content_sha256: str | None = None
    is_placeholder: bool = False


EvidenceKind = Literal["quantitative", "qualitative", "historical_event", "counter_evidence"]
Topic = Literal["revenue", "investment", "gdp", "profit_shifting", "elasticity", "macro_context", "policy_history", "distribution", "other"]
VerificationStatus = Literal["verified", "unverified", "failed"]


class Evidence(Contract):
    evidence_id: str                    # "E1"...
    source_id: str
    kind: EvidenceKind
    topic: Topic
    claim: str
    quote: str | None = None            # verbatim; required for quantitative evidence
    value: float | None = None
    unit: str | None = None
    period: str | None = None
    location: str | None = None         # page / table / section
    verification_status: VerificationStatus = "unverified"
    verification_note: str | None = None
    confidence: Confidence = "medium"


class Interpretation(Contract):
    interpretation_id: str              # "I1"...
    statement: str
    supporting_evidence_ids: list[str]
    confidence: Confidence = "medium"


class Confounder(Contract):
    name: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    likely_direction: Literal["raises_revenue", "lowers_revenue", "ambiguous"] = "ambiguous"


class ParameterEvidence(Contract):
    parameter: str                      # must be in engine.PARAMETER_NAMES
    value: float | None = None
    low: float | None = None
    high: float | None = None
    evidence_ids: list[str]
    note: str = ""


ResearchStepKind = Literal["plan", "search", "fetch", "extract", "dataset_lookup", "reason", "synthesis", "warning", "error"]


class ResearchStep(Contract):
    step_id: int
    ts: datetime
    kind: ResearchStepKind
    title: str
    detail: str = ""
    tool: str | None = None
    query: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    duration_ms: int | None = None


class ResearchFindings(Contract):
    policy: PolicySpec
    mode: Mode
    model: str | None = None
    summary: str
    research_questions: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    interpretations: list[Interpretation] = Field(default_factory=list)
    confounders: list[Confounder] = Field(default_factory=list)
    parameter_evidence: list[ParameterEvidence] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    trace: list[ResearchStep] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
    cache_key: str | None = None
