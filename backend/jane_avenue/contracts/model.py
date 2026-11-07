from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Confidence, Contract, YearValue
from .policy import PolicySpec

DistributionKind = Literal["fixed", "normal", "truncated_normal", "triangular", "uniform", "lognormal"]


class Distribution(Contract):
    """params: fixed {} | normal {mean, sd} | truncated_normal {mean, sd, low, high} |
    triangular {low, mode, high} | uniform {low, high} | lognormal {mu, sigma}"""
    kind: DistributionKind
    params: dict[str, float] = Field(default_factory=dict)


ParameterCategory = Literal["behavioural", "structural", "macro", "timing"]
ParameterBasis = Literal["literature", "official", "calibrated", "team_judgement"]


class Assumption(Contract):
    name: str
    label: str
    description: str
    category: ParameterCategory
    unit: str                           # "elasticity" | "fraction" | "%" | "years"
    value: float
    low: float
    high: float
    distribution: Distribution
    basis: ParameterBasis
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    adjustable: bool = True
    slider_min: float | None = None
    slider_max: float | None = None
    slider_step: float | None = None
    is_user_override: bool = False
    is_placeholder: bool = False


MetricName = Literal[
    "revenue_static_gbp_bn", "revenue_behavioural_gbp_bn", "revenue_dynamic_gbp_bn",
    "business_investment_pct", "business_investment_gbp_bn", "gdp_level_pct", "cost_of_capital_pct",
]
METRIC_NAMES: tuple[str, ...] = MetricName.__args__  # type: ignore[attr-defined]


class MetricProjection(Contract):
    metric: MetricName
    label: str
    unit: Literal["£bn", "%"]
    values: list[YearValue]             # change vs baseline
    confidence: Confidence
    note: str = ""


class CalcStep(Contract):
    step_id: str                        # "rev.static.2027-28"
    label: str
    formula: str
    inputs: dict[str, float]
    output: float
    unit: str
    fiscal_year: str | None = None
    parameter_names: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class EngineResult(Contract):
    model_version: str
    policy: PolicySpec
    scenario: str
    baseline_vintage: str
    fiscal_years: list[str]
    metrics: list[MetricProjection]
    calc_trace: list[CalcStep]
    parameters_used: dict[str, float]
    warnings: list[str] = Field(default_factory=list)
