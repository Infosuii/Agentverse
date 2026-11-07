from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Contract
from .model import Assumption, EngineResult, MetricName
from .policy import PolicySpec

ScenarioName = Literal["central", "optimistic", "pessimistic", "custom"]


class ScenarioDefinition(Contract):
    name: ScenarioName
    label: str
    description: str
    parameter_values: dict[str, float]


class ScenarioResult(Contract):
    scenario: ScenarioDefinition
    result: EngineResult


class PercentileBand(Contract):
    fiscal_year: str
    p5: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float
    mean: float


class MetricDistribution(Contract):
    metric: MetricName
    unit: Literal["£bn", "%"]
    bands: list[PercentileBand]


class Histogram(Contract):
    metric: MetricName
    fiscal_year: str
    bin_edges: list[float]
    counts: list[int]


class MonteCarloResult(Contract):
    n_draws: int
    seed: int
    sampled_parameters: list[str]
    distributions: list[MetricDistribution]
    histograms: list[Histogram]
    interval_kind: Literal["assumption_range", "empirical_prediction_interval"] = "assumption_range"
    interval_note: str
    empirical_interval: list[PercentileBand] | None = None
    empirical_calibration_note: str | None = None


class TornadoItem(Contract):
    parameter: str
    label: str
    low_input: float
    high_input: float
    output_at_low: float
    output_at_high: float
    swing: float


class SensitivityResult(Contract):
    metric: MetricName
    fiscal_year: str
    base_output: float
    items: list[TornadoItem]


class SimulationBundle(Contract):
    policy: PolicySpec
    baseline_vintage: str
    scenarios: list[ScenarioResult]     # always includes "central" first
    monte_carlo: MonteCarloResult | None = None
    sensitivity: list[SensitivityResult] = Field(default_factory=list)
    assumptions: list[Assumption]
    warnings: list[str] = Field(default_factory=list)


class SimulateRequest(Contract):
    policy: PolicySpec
    parameter_overrides: dict[str, float] = Field(default_factory=dict)
    monte_carlo_draws: int = Field(default=2000, ge=0, le=20000)
    seed: int = 42
    include_sensitivity: bool = True
