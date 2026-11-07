from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from .common import Contract, TaxName
from .data import MacroContext
from .policy import PolicyType
from .research import Source


class Costing(Contract):
    costing_body: Literal["OBR", "HMT", "HMRC", "IFS", "other"]
    fiscal_event: str
    fiscal_year: str
    value_gbp_bn: float                 # positive = raises revenue
    includes_behavioural: bool | None = None
    source_id: str


class ObservedOutcome(Contract):
    metric: Literal["ct_receipts_gbp_bn", "ct_receipts_pct_gdp", "business_investment_gbp_bn", "real_gdp_growth_pct"]
    fiscal_year: str
    value: float
    source_id: str


class PolicyChange(Contract):
    change_id: str                      # "CT-MAIN-2023"
    tax: TaxName
    policy_type: PolicyType
    announced_date: date | None = None
    effective_date: date
    fiscal_event: str | None = None
    old_rate_pct: float
    new_rate_pct: float
    other_measures: list[str] = Field(default_factory=list)
    macro_context: MacroContext | None = None
    official_costings: list[Costing] = Field(default_factory=list)
    observed_outcomes: list[ObservedOutcome] = Field(default_factory=list)
    notes: str = ""
    source_ids: list[str]
    is_placeholder: bool = False


class PrecedentMatch(Contract):
    change: PolicyChange
    similarity: float = Field(ge=0, le=1)
    similarity_breakdown: dict[str, float]
    comparability_notes: list[str] = Field(default_factory=list)


class PrecedentAnalysis(Contract):
    method: str
    dataset_version: str
    matches: list[PrecedentMatch]       # sorted by similarity desc
    summary: str = ""
    sources: list[Source] = Field(default_factory=list)
