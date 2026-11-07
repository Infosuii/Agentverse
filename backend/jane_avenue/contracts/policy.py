from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from .common import Contract, TaxName

PolicyType = Literal["corporation_tax_main_rate", "corporation_tax_small_profits_rate", "vat_standard_rate", "unsupported"]


class PolicySpec(Contract):
    policy_type: PolicyType
    tax: TaxName | None = None
    baseline_rate_pct: float | None = Field(default=None, ge=0, le=100)
    proposed_rate_pct: float | None = Field(default=None, ge=0, le=100)
    effective_date: date | None = None
    horizon_years: int = Field(default=5, ge=1, le=10)
    jurisdiction: Literal["UK"] = "UK"
    description: str = ""          # "Raise the CT main rate from 25% to 28% from 1 April 2027"
    raw_query: str = ""
    parse_method: Literal["gemini", "rules", "manual", "fixture"] = "manual"
    parse_confidence: float = Field(default=1.0, ge=0, le=1)
    ambiguities: list[str] = Field(default_factory=list)

    def change_pp(self) -> float | None:
        if self.baseline_rate_pct is None or self.proposed_rate_pct is None:
            return None
        return round(self.proposed_rate_pct - self.baseline_rate_pct, 6)

    def direction(self) -> Literal["increase", "decrease", "no_change"] | None:
        c = self.change_pp()
        if c is None:
            return None
        return "increase" if c > 0 else "decrease" if c < 0 else "no_change"


class ScopeDecision(Contract):
    status: Literal["supported", "partially_supported", "unsupported"]
    forecast_allowed: bool
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validated_min_rate_pct: float | None = None
    validated_max_rate_pct: float | None = None
    validated_max_change_pp: float | None = None
