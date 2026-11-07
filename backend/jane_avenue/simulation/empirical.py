"""Owner: agent-4. Backtest-calibrated empirical interval for behavioural revenue (MASTER_PROMPT 9.6, agent-4 M2).

Agreed with agent-10 (Issue #45): `revenue_relative_residuals()` returns (predicted − observed) / observed for
`jane_behavioural` on the test split only, or None when fewer than 8 exist.

Direction matters. Those residuals measure the model's error relative to the outcome, but the interval brackets the
outcome given the model's central path. So each residual r is first converted to the outcome's error relative to the
prediction, u = observed / predicted − 1 = 1 / (1 + r) − 1. The interval is then central × (1 + quantile of u) per
year, for the 5/10/25/50/75/90/95 quantiles. A model that over-predicted in the backtest (r > 0) therefore gets a
band shifted below its central path, not above it. Residuals with r <= −1 (a non-positive prediction) cannot be
converted and are dropped.

The residuals are full-year, but the central path already applies `receipts_first_year_share` in year 1 and the
interval is proportional to it, so no extra year-1 scaling is needed.

The interval is shown only when there are at least 8 residuals AND the backtest reports its coverage
(`evaluation.results.empirical_calibration_info()`). Otherwise it is None, and a warning says why.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from ..contracts import EngineResult, PercentileBand

MIN_RESIDUALS = 8
METRIC = "revenue_behavioural_gbp_bn"
QUANTILES = (5, 10, 25, 50, 75, 90, 95)
UNDER_COVERAGE = 0.80  # warn when the nominal 90% interval covered less than this share of backtest outcomes


@dataclass(frozen=True)
class EmpiricalOutcome:
    bands: list[PercentileBand] | None
    note: str | None
    warnings: list[str]


def calibration_info() -> dict[str, object] | None:
    """Agent-10's calibration summary, or None if evaluation does not expose it (yet)."""
    from ..evaluation import results

    fn = getattr(results, "empirical_calibration_info", None)
    try:
        return fn() if callable(fn) else None
    except Exception:  # noqa: BLE001 - a broken evaluation artefact must never break simulation
        return None


def _coverage(info: dict[str, object], n: int) -> tuple[float, str] | None:
    """(coverage fraction, "covered/n") from the calibration info, or None if it is not reported."""
    covered = info.get("loo_covered")
    if isinstance(covered, int) and n > 0:
        return covered / n, f"{covered}/{n}"
    raw = info.get("loo_coverage_90")
    if isinstance(raw, int | float) and math.isfinite(raw):
        frac = float(raw) / 100 if raw > 1 else float(raw)
        return frac, f"{frac:.0%} of {n}"
    return None


def _no_interval(reason: str) -> EmpiricalOutcome:
    return EmpiricalOutcome(None, None, [f"No empirical prediction interval is shown: {reason} The bands shown are "
                                         "assumption-driven ranges only."])


def outcome_errors(residuals: Sequence[float] | None) -> list[float]:
    """Convert (predicted − observed) / observed residuals to (observed − predicted) / predicted errors."""
    return [1.0 / (1.0 + float(r)) - 1.0 for r in (residuals or []) if math.isfinite(r) and r > -1.0]


def empirical_interval(central: EngineResult, residuals: Sequence[float] | None,
                       info_fn: Callable[[], dict[str, object] | None] | None = None) -> EmpiricalOutcome:
    clean = outcome_errors(residuals)
    n = len(clean)
    if n < MIN_RESIDUALS:
        return _no_interval(f"the historical backtest supplied {n} out-of-sample residuals, fewer than the "
                            f"{MIN_RESIDUALS} needed to calibrate one.")
    info = (info_fn or calibration_info)() or {}
    coverage = _coverage(info, n)
    period = info.get("test_period")
    if coverage is None or not isinstance(period, str) or not period:
        return _no_interval(f"the backtest supplied {n} residuals but did not report the test period and observed "
                            "coverage needed to label the interval honestly.")
    q = np.percentile(np.asarray(clean), QUANTILES)
    factors = 1.0 + q
    mean_factor = 1.0 + float(np.mean(clean))
    metric = next(m for m in central.metrics if m.metric == METRIC)
    bands = []
    for yv in metric.values:
        vals = sorted(float(yv.value * f) for f in factors)  # sorting keeps p5 <= ... <= p95 when central < 0
        bands.append(PercentileBand(fiscal_year=yv.fiscal_year, p5=vals[0], p10=vals[1], p25=vals[2], p50=vals[3],
                                    p75=vals[4], p90=vals[5], p95=vals[6], mean=float(yv.value * mean_factor)))
    frac, covered = coverage
    note = (f"Empirical prediction interval for behavioural revenue: the central path × (1 + quantiles of the "
            f"observed-versus-predicted errors from n={n} out-of-sample years of the jane_behavioural backtest, test "
            f"period {period}). In the backtest "
            f"the 90% (5th–95th percentile) interval covered {covered} outcomes ({frac:.0%}, leave-one-out). The "
            "backtest is conditional on realised profits, so this interval excludes macroeconomic forecast error.")
    warnings = []
    if frac < UNDER_COVERAGE:
        warnings.append(f"The empirical 90% interval covered only {frac:.0%} of backtest outcomes, so it is likely "
                        "too narrow.")
    return EmpiricalOutcome(bands, note, warnings)
