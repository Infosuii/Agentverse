from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .common import Contract, Mode


class BacktestCase(Contract):
    case_id: str
    fiscal_year: str
    split: Literal["train", "test"]
    target: str
    observed: float
    official_costing_gbp_bn: float | None = None
    predictions: dict[str, float]
    notes: str = ""


class MethodSummary(Contract):
    method: str
    label: str
    description: str
    split: Literal["train", "test"]
    n: int
    mae: float
    rmse: float
    mape_pct: float | None = None
    directional_accuracy: float | None = None
    is_baseline: bool


class MLExperiment(Contract):
    model: str
    features: list[str]
    train_period: str
    test_period: str
    test_mae: float | None = None
    best_baseline: str
    best_baseline_mae: float | None = None
    adopted: bool
    conclusion: str


class ResearchEval(Contract):
    n_questions: int
    fact_accuracy: float | None = None
    citation_url_valid_rate: float | None = None
    quote_match_rate: float | None = None
    hallucinated_sources: int | None = None
    official_source_share: float | None = None
    mode: Mode
    notes: str = ""


class VerificationEval(Contract):
    n_fault_cases: int
    detected: int
    n_clean_cases: int
    false_positives: int
    by_fault: dict[str, bool]
    notes: str = ""


class EvaluationReport(Contract):
    generated_at: datetime
    dataset_version: str
    target_description: str
    methods: list[MethodSummary]
    cases: list[BacktestCase]
    ml_experiment: MLExperiment | None = None
    research_eval: ResearchEval | None = None
    verification_eval: VerificationEval | None = None
    limitations: list[str] = Field(default_factory=list)
    is_placeholder: bool = False
