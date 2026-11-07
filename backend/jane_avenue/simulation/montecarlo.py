"""Owner: agent-4. Monte Carlo over the parameter distributions (MASTER_PROMPT section 9.6).

Parameters are sampled independently (v1). All draws go through ONE vectorised `compute` call. The bands are
assumption-driven ranges, never prediction intervals.
"""
from __future__ import annotations

from collections.abc import Mapping

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


def _unit(metric: str) -> str:
    return "£bn" if metric.endswith("_gbp_bn") else "%"


def monte_carlo(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *,
                draws: int = 2000, seed: int = 42) -> MonteCarloResult:
    if draws < 1:
        raise ValueError("monte_carlo needs draws >= 1")
    rng = np.random.default_rng(seed)
    sampled = uncertain_parameters(params)
    values: dict[str, float | np.ndarray] = {name: p.value for name, p in params.items()}
    for name in sampled:
        values[name] = sample(params[name], draws, rng)
    out = engine_core.compute(spec, values, baseline)
    years = list(out.fiscal_years)
    distributions, histograms = [], []
    for metric in METRIC_NAMES:
        arr = np.broadcast_to(np.asarray(out.metrics[metric], dtype=float), (draws, len(years)))
        q = np.percentile(arr, PERCENTILES, axis=0).tolist()
        mean = arr.mean(axis=0).tolist()
        bands = [PercentileBand(fiscal_year=fy, p5=q[0][i], p10=q[1][i], p25=q[2][i], p50=q[3][i], p75=q[4][i],
                                p90=q[5][i], p95=q[6][i], mean=mean[i]) for i, fy in enumerate(years)]
        distributions.append(MetricDistribution(metric=metric, unit=_unit(metric), bands=bands))  # type: ignore[arg-type]
        counts, edges = np.histogram(arr[:, -1], bins=HISTOGRAM_BINS)
        histograms.append(Histogram(metric=metric, fiscal_year=years[-1], bin_edges=edges.tolist(),  # type: ignore[arg-type]
                                    counts=counts.tolist()))
    return MonteCarloResult(n_draws=draws, seed=seed, sampled_parameters=sampled, distributions=distributions,
                            histograms=histograms, interval_kind="assumption_range", interval_note=INTERVAL_NOTE)
