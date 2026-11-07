from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .common import Contract

CheckCategory = Literal["scope", "citation", "evidence", "assumption", "calculation", "data", "causal_claim", "uncertainty", "report"]
Severity = Literal["info", "warning", "error", "blocking"]
CheckStatus = Literal["pass", "warn", "fail", "skipped"]


class VerificationCheck(Contract):
    check_id: str                       # catalogue ID, MASTER_PROMPT 9.7
    category: CheckCategory
    severity: Severity
    status: CheckStatus
    title: str
    detail: str
    method: Literal["rule", "recompute", "source_fetch", "llm_critic"]
    affected_ids: list[str] = Field(default_factory=list)


class VerificationReport(Contract):
    overall: Literal["approved", "approved_with_warnings", "forecast_withheld"]
    forecast_allowed: bool
    checks: list[VerificationCheck]
    decline_reasons: list[str] = Field(default_factory=list)
    summary: str
    counts: dict[str, int] = Field(default_factory=dict)
    critic_model: str | None = None
    verified_at: datetime
