"""Evaluation report loader and residual calibration helpers. Owner: agent-10."""
from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..contracts import BacktestCase, EvaluationReport, utcnow
from ..data import registry

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "latest.json"
MIN_RESIDUAL_CASES = 8


def load_results(path: Path | None = None) -> EvaluationReport:
    """Load the latest EvaluationReport from `results/latest.json`, or return a placeholder report."""
    target = path or RESULTS_PATH
    if target.exists():
        return EvaluationReport.model_validate_json(target.read_text(encoding="utf-8"))
    return EvaluationReport(
        generated_at=utcnow(),
        dataset_version=registry.DATASET_VERSION,
        target_description="Placeholder: the evaluation has not been run yet.",
        methods=[],
        cases=[],
        limitations=["No evaluation results yet."],
        is_placeholder=True,
    )


def _test_cases(cases: Sequence[BacktestCase] | None = None) -> list[BacktestCase]:
    source_cases = list(cases) if cases is not None else load_results().cases
    return [
        c
        for c in source_cases
        if c.split == "test"
        and c.observed > 0
        and "jane_behavioural" in c.predictions
        and math.isfinite(c.predictions["jane_behavioural"])
        and math.isfinite(c.observed)
    ]


def revenue_relative_residuals(cases: Sequence[BacktestCase] | None = None) -> list[float] | None:
    """Return test-split relative errors `(pred - obs) / obs` of `jane_behavioural`, or `None` if `n < 8`."""
    t_cases = _test_cases(cases)
    if len(t_cases) < MIN_RESIDUAL_CASES:
        return None
    return [float((c.predictions["jane_behavioural"] - c.observed) / c.observed) for c in t_cases]


def empirical_calibration_info(cases: Sequence[BacktestCase] | None = None) -> dict[str, object] | None:
    """Return leave-one-out 5-95% empirical interval calibration metadata for agent-4's simulation runner."""
    t_cases = _test_cases(cases)
    if len(t_cases) < MIN_RESIDUAL_CASES:
        return None
    residuals = [float((c.predictions["jane_behavioural"] - c.observed) / c.observed) for c in t_cases]
    arr = np.asarray(residuals, dtype=float)
    n = len(residuals)
    loo_covered = 0
    for i in range(n):
        other = np.delete(arr, i)
        q5, q95 = np.percentile(other, (5, 95))
        if float(q5) <= residuals[i] <= float(q95):
            loo_covered += 1
    test_period = f"FY{t_cases[0].fiscal_year}–FY{t_cases[-1].fiscal_year}"
    return {
        "n": n,
        "test_period": test_period,
        "loo_covered": loo_covered,
        "loo_coverage_90": round(loo_covered / n, 4),
        "residuals": residuals,
    }
