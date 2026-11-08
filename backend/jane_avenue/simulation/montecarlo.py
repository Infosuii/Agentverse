"""Owner: agent-4. Monte Carlo over the parameter distributions (MASTER_PROMPT section 9.6).

Parameters are sampled independently (v1). All draws go through ONE vectorised `compute` call. The bands are
assumption-driven ranges, never prediction intervals.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ..contracts import (
    METRIC_NAMES,
    Assumption,
    BaselineProjection,
    Histogram,
    MetricDistribution,
    MonteCarloResult,
    PercentileBand,
    PolicySpec,
)
from ..engine import core as engine_core
from .endpoints import uncertain_parameters
from .sampling import sample

PERCENTILES = (5, 10, 25, 50, 75, 90, 95)
HISTOGRAM_BINS = 30
INTERVAL_NOTE = ("Shaded bands show the spread of outcomes when uncertain assumptions are varied together (Monte Carlo "
                 "over parameter distributions). They are assumption-driven ranges, not statistical prediction "
                 "intervals, and exclude model and data uncertainty.")
SE_METRIC = "revenue_behavioural_gbp_bn"  # the headline metric; its final-year median s.e. goes in the interval note


def median_standard_error(x: np.ndarray) -> float:
    """Distribution-free Monte Carlo standard error of the sample median of `x`.

    The rank of the median is Binomial(n, 0.5), with s.d. sqrt(n)/2 ranks, so one s.e. spans the quantiles at
    0.5 +/- 0.5/sqrt(n): s.e. ~ (q(0.5 + 0.5/sqrt(n)) - q(0.5 - 0.5/sqrt(n))) / 2.
    """
    n = x.shape[0]
    if n < 2:
        return 0.0
    half = 50.0 / np.sqrt(n)
    lo, hi = np.percentile(x, [50.0 - half, 50.0 + half])
    return float(hi - lo) / 2.0


def _se_clause(se_gbp_bn: float, n: int) -> str:
    amount = f"±£{se_gbp_bn:.2f}bn" if se_gbp_bn >= 0.005 else "below £0.01bn"
    return f"(MC s.e. of the final-year median of behavioural revenue {amount} at n={n})"


def _unit(metric: str) -> str:
    return "£bn" if metric.endswith("_gbp_bn") else "%"


@dataclass
class Draws:
    """Every Monte Carlo draw: `metrics[name]` has shape (draws, years). The single source of the bands, the
    histograms and the trajectory chart, so a plotted path is always a real draw."""
    fiscal_years: list[str]
    metrics: dict[str, np.ndarray]
    sampled_parameters: list[str]
    draws: int
    seed: int


def simulate_draws(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *,
                   draws: int = 2000, seed: int = 42) -> Draws:
    """Sample the uncertain parameters with `default_rng(seed)` and run ONE vectorised `compute` call."""
    if draws < 1:
        raise ValueError("monte_carlo needs draws >= 1")
    rng = np.random.default_rng(seed)
    sampled = uncertain_parameters(params)
    values: dict[str, float | np.ndarray] = {name: p.value for name, p in params.items()}
    for name in sampled:
        values[name] = sample(params[name], draws, rng)
    out = engine_core.compute(spec, values, baseline)
    years = list(out.fiscal_years)
    metrics = {m: np.broadcast_to(np.asarray(out.metrics[m], dtype=float), (draws, len(years)))
               for m in METRIC_NAMES if m in out.metrics}  # ready-reckoner measures model revenue only (#93)
    return Draws(fiscal_years=years, metrics=metrics, sampled_parameters=sampled, draws=draws, seed=seed)


def monte_carlo(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *,
                draws: int = 2000, seed: int = 42) -> MonteCarloResult:
    d = simulate_draws(spec, params, baseline, draws=draws, seed=seed)
    years, sampled = d.fiscal_years, d.sampled_parameters
    distributions, histograms = [], []
    se_note = ""
    for metric in METRIC_NAMES:
        if metric not in d.metrics:
            continue
        arr = d.metrics[metric]
        q = np.percentile(arr, PERCENTILES, axis=0).tolist()
        mean = arr.mean(axis=0).tolist()
        bands = [PercentileBand(fiscal_year=fy, p5=q[0][i], p10=q[1][i], p25=q[2][i], p50=q[3][i], p75=q[4][i],
                                p90=q[5][i], p95=q[6][i], mean=mean[i]) for i, fy in enumerate(years)]
        distributions.append(MetricDistribution(metric=metric, unit=_unit(metric), bands=bands))  # type: ignore[arg-type]
        counts, edges = np.histogram(arr[:, -1], bins=HISTOGRAM_BINS)
        histograms.append(Histogram(metric=metric, fiscal_year=years[-1], bin_edges=edges.tolist(),  # type: ignore[arg-type]
                                    counts=counts.tolist()))
        if metric == SE_METRIC:
            se_note = " " + _se_clause(median_standard_error(arr[:, -1]), draws)
    return MonteCarloResult(n_draws=draws, seed=seed, sampled_parameters=sampled, distributions=distributions,
                            histograms=histograms, interval_kind="assumption_range",
                            interval_note=INTERVAL_NOTE + se_note)
