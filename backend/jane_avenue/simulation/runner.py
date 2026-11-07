"""Owner: agent-4. STUB: scenarios + Monte Carlo (agent-1 M0). Agent-4 replaces it.

STUB behaviour: optimistic and pessimistic equal the central scenario; Monte Carlo samples every non-fixed parameter;
sensitivity is empty. Bands are assumption-driven ranges, not prediction intervals.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

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
    ScenarioDefinition,
    ScenarioResult,
    SimulationBundle,
)
from ..engine.core import compute
from ..engine.model import _METRIC_META, run_engine
from ..engine.parameters import central_values

INTERVAL_NOTE = ("assumption-driven ranges, not statistical prediction intervals; "
                 "exclude model and data uncertainty")


def _sample(p: Assumption, n: int, rng: np.random.Generator) -> np.ndarray:
    d = p.distribution
    if d.kind == "triangular":
        lo, mode, hi = d.params["low"], d.params["mode"], d.params["high"]
        x = rng.triangular(lo, mode, hi, n) if hi > lo else np.full(n, mode)
    elif d.kind in ("normal", "truncated_normal"):
        x = rng.normal(d.params["mean"], d.params["sd"], n)
    elif d.kind == "uniform":
        x = rng.uniform(d.params["low"], d.params["high"], n)
    elif d.kind == "lognormal":
        x = rng.lognormal(d.params["mu"], d.params["sigma"], n)
    else:
        x = np.full(n, p.value)
    lo_b = p.slider_min if p.slider_min is not None else -np.inf
    hi_b = p.slider_max if p.slider_max is not None else np.inf
    return np.clip(x, lo_b, hi_b)


def _monte_carlo(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection,
                 n: int, seed: int) -> MonteCarloResult:
    rng = np.random.default_rng(seed)
    sampled = [name for name, p in params.items() if p.distribution.kind != "fixed"]
    values: dict[str, float | np.ndarray] = dict(central_values(params))
    for name in sampled:
        values[name] = _sample(params[name], n, rng)
    out = compute(spec, values, baseline)
    dists: list[MetricDistribution] = []
    hists: list[Histogram] = []
    for metric in METRIC_NAMES:
        arr = np.broadcast_to(out.metrics[metric], (n, len(out.fiscal_years)))
        q = np.percentile(arr, [5, 10, 25, 50, 75, 90, 95], axis=0)
        bands = [PercentileBand(fiscal_year=fy, p5=q[0, i], p10=q[1, i], p25=q[2, i], p50=q[3, i], p75=q[4, i],
                                p90=q[5, i], p95=q[6, i], mean=float(arr[:, i].mean()))
                 for i, fy in enumerate(out.fiscal_years)]
        dists.append(MetricDistribution(metric=metric, unit=_METRIC_META[metric][1], bands=bands))  # type: ignore[arg-type]
        counts, edges = np.histogram(arr[:, -1], bins=30)
        hists.append(Histogram(metric=metric, fiscal_year=out.fiscal_years[-1],  # type: ignore[arg-type]
                               bin_edges=edges.tolist(), counts=counts.tolist()))
    return MonteCarloResult(n_draws=n, seed=seed, sampled_parameters=sampled, distributions=dists, histograms=hists,
                            interval_kind="assumption_range", interval_note=INTERVAL_NOTE)


def simulate(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *, draws: int = 2000,
             seed: int = 42, include_sensitivity: bool = True,
             empirical_residuals: Callable[[], list[float] | None] | None = None) -> SimulationBundle:
    central = central_values(params)
    scenarios = []
    for name, label in (("central", "Central"), ("optimistic", "Optimistic"), ("pessimistic", "Pessimistic")):
        definition = ScenarioDefinition(name=name, label=label, parameter_values=central,  # type: ignore[arg-type]
                                        description="STUB: all parameters at central values.")
        scenarios.append(ScenarioResult(scenario=definition, result=run_engine(spec, params, baseline, name)))
    if any(p.is_user_override for p in params.values()):
        definition = ScenarioDefinition(name="custom", label="Custom", parameter_values=central,
                                        description="Central values with the analyst's overrides applied.")
        scenarios.append(ScenarioResult(scenario=definition, result=run_engine(spec, params, baseline, "custom")))
    mc = _monte_carlo(spec, params, baseline, draws, seed) if draws > 0 else None
    return SimulationBundle(policy=spec, baseline_vintage=baseline.vintage, scenarios=scenarios, monte_carlo=mc,
                            sensitivity=[], assumptions=list(params.values()),
                            warnings=["STUB simulation: optimistic/pessimistic equal central; no sensitivity."])
