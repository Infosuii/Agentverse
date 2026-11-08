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
    metric: Literal["ct_receipts_gbp_bn", "ct_receipts_pct_gdp", "business_investment_gbp_bn", "real_gdp_growth_pct",
                    "receipts_gbp_bn", "receipts_pct_gdp", "spending_gbp_bn", "spending_pct_gdp",
                    "borrowing_gbp_bn", "borrowing_pct_gdp"]
    fiscal_year: str
    value: float
    source_id: str
    label: str | None = None            # what the series measures, e.g. "VAT receipts (net of refunds)"


class PolicyChange(Contract):
    change_id: str                      # "CT-MAIN-2023"
    tax: TaxName
    policy_type: PolicyType
    announced_date: date | None = None
    effective_date: date
    fiscal_event: str | None = None
    # In `value_unit` when that is set, otherwise percent. Null when the source does not state the value.
    old_rate_pct: float | None
    new_rate_pct: float | None
    other_measures: list[str] = Field(default_factory=list)
    macro_context: MacroContext | None = None
    official_costings: list[Costing] = Field(default_factory=list)
    observed_outcomes: list[ObservedOutcome] = Field(default_factory=list)
    notes: str = ""
    source_ids: list[str]
    is_placeholder: bool = False
    # contract 1.2.0 (additive, optional): precedents for policies other than corporation tax.
    policy_key: str | None = None       # data/curated/fiscal_topics.csv
    title: str | None = None            # the rate series ("Petrol") or the measure as the OBR names it
    value_unit: str | None = None       # "%", "£", "p/litre", "£/week"
    kind: Literal["rate_series", "announced_measure", "fiscal_event"] | None = None


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
    policy_key: str | None = None       # contract 1.2.0: which fiscal topic was matched; null for corporation tax
    policy_label: str | None = None
