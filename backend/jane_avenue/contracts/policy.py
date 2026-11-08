from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from .common import Contract, TaxName

# tax_measure: a tax or benefit change costed from the HMRC ready reckoner (`measure_id` names the measure in
# data/curated/tax_measures.csv). fiscal_other: any other fiscal policy (a tax or spending change with no validated
# model): researched and reported, but no quantitative forecast. unsupported: not a UK fiscal policy at all.
# vat_standard_rate is kept for compatibility; parsers now produce tax_measure with measure_id="vat_standard_rate".
PolicyType = Literal["corporation_tax_main_rate", "corporation_tax_small_profits_rate", "vat_standard_rate",
                     "tax_measure", "fiscal_other", "unsupported"]


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
    # contract-change #93 (additive, optional): measures that are not rates in percent. For tax_measure policies,
    # `measure_id` names the measure; percentage-rate measures use baseline_rate_pct / proposed_rate_pct, and every
    # other measure (an allowance in £, a duty in p/litre or as an index, a benefit in £/week) uses
    # baseline_value / proposed_value in `value_unit`.
    measure_id: str | None = None
    baseline_value: float | None = None
    proposed_value: float | None = None
    value_unit: str | None = None

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
