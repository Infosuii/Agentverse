"""Monte Carlo and `simulate` tests. Owner: agent-4."""
import os
import time

import pytest

from jane_avenue.contracts import METRIC_NAMES, Distribution
from jane_avenue.engine import core as engine_core
from jane_avenue.engine.model import run_engine
from jane_avenue.engine.parameters import apply_overrides, central_values
from jane_avenue.simulation import INTERVAL_NOTE, monte_carlo, sensitivity, simulate

PERF_SLACK = 3.0 if os.environ.get("CI") else 1.0  # slow shared CI runners get 3x the budget

VERBATIM_NOTE = ("Shaded bands show the spread of outcomes when uncertain assumptions are varied together (Monte Carlo "
                 "over parameter distributions). They are assumption-driven ranges, not statistical prediction "
                 "intervals, and exclude model and data uncertainty.")


def _band(mc, metric, i=-1):
    return next(d for d in mc.distributions if d.metric == metric).bands[i]


def test_same_seed_identical_different_seed_differs(full_engine, demo_policy, params, baseline):
    a = monte_carlo(demo_policy, params, baseline, draws=500, seed=11)
    b = monte_carlo(demo_policy, params, baseline, draws=500, seed=11)
    c = monte_carlo(demo_policy, params, baseline, draws=500, seed=12)
    assert a.model_dump() == b.model_dump()
    assert _band(a, "revenue_dynamic_gbp_bn").p50 != _band(c, "revenue_dynamic_gbp_bn").p50


def test_percentiles_are_ordered_and_histograms_complete(full_engine, demo_policy, params, baseline):
    mc = monte_carlo(demo_policy, params, baseline, draws=2000)
    assert [d.metric for d in mc.distributions] == list(METRIC_NAMES)
    for d in mc.distributions:
        assert d.unit == ("£bn" if d.metric.endswith("_gbp_bn") else "%")
        assert len(d.bands) == demo_policy.horizon_years
        for b in d.bands:
            assert b.p5 <= b.p10 <= b.p25 <= b.p50 <= b.p75 <= b.p90 <= b.p95
            assert b.p5 <= b.mean <= b.p95
    final_year = mc.distributions[0].bands[-1].fiscal_year
    for h in mc.histograms:
        assert h.fiscal_year == final_year and len(h.counts) == 30 and len(h.bin_edges) == 31
        assert sum(h.counts) == 2000
    assert _band(mc, "revenue_dynamic_gbp_bn").p5 < _band(mc, "revenue_dynamic_gbp_bn").p95


def test_interval_semantics(full_engine, demo_policy, params, baseline):
    mc = monte_carlo(demo_policy, params, baseline, draws=100)
    assert mc.interval_kind == "assumption_range"
    assert INTERVAL_NOTE == VERBATIM_NOTE and mc.interval_note.startswith(VERBATIM_NOTE + " (MC s.e. of")
    assert mc.empirical_interval is None
    assert mc.sampled_parameters == [n for n, p in params.items() if p.distribution.kind != "fixed"]


def test_all_fixed_collapses_to_central(full_engine, demo_policy, params, baseline):
    fixed = {n: p.model_copy(update={"distribution": Distribution(kind="fixed")}) for n, p in params.items()}
    mc = monte_carlo(demo_policy, fixed, baseline, draws=300)
    assert mc.sampled_parameters == []
    central = run_engine(demo_policy, central_values(params), baseline)
    for m in central.metrics:
        for i, yv in enumerate(m.values):
            b = _band(mc, m.metric, i)
            assert b.p5 == b.p50 == b.p95 == pytest.approx(yv.value)


def test_overrides_recentre_the_distribution(full_engine, demo_policy, params, baseline):
    base = monte_carlo(demo_policy, params, baseline, draws=2000)
    moved = monte_carlo(demo_policy, apply_overrides(params, {"user_cost_elasticity": 1.2}), baseline, draws=2000)
    # a rise with a stronger investment response: investment falls further
    assert _band(moved, "business_investment_pct").p50 < _band(base, "business_investment_pct").p50
    high_base = apply_overrides(params, {"profit_base_deviation_pct": 10.0})
    shifted = monte_carlo(demo_policy, high_base, baseline, draws=2000)
    assert _band(shifted, "revenue_static_gbp_bn").p50 > _band(base, "revenue_static_gbp_bn").p50


def test_monte_carlo_uses_one_compute_call(monkeypatch, demo_policy, params, baseline):
    calls = []
    real = engine_core.compute
    monkeypatch.setattr(engine_core, "compute", lambda *a: calls.append(1) or real(*a))
    monte_carlo(demo_policy, params, baseline, draws=2000)
    assert len(calls) == 1
    calls.clear()
    simulate(demo_policy, params, baseline, draws=2000)  # endpoints (shared by scenarios + tornado) and MC
    assert len(calls) == 2


def test_simulate_without_overrides(full_engine, demo_policy, params, baseline):
    bundle = simulate(demo_policy, params, baseline, draws=200, empirical_residuals=lambda: [0.1, -0.05, 0.02])
    assert [s.scenario.name for s in bundle.scenarios] == ["central", "optimistic", "pessimistic"]
    assert bundle.monte_carlo and bundle.monte_carlo.n_draws == 200
    assert [r.metric for r in bundle.sensitivity] == ["revenue_behavioural_gbp_bn", "business_investment_pct",
                                                      "gdp_level_pct"]
    assert any("3 out-of-sample residuals" in w and "assumption-driven" in w for w in bundle.warnings)
    assert not any("STUB" in w for w in bundle.warnings)


def test_simulate_with_overrides_adds_custom(full_engine, demo_policy, params, baseline):
    overridden = apply_overrides(params, {"taxable_profit_elasticity": 0.45})
    bundle = simulate(demo_policy, overridden, baseline, draws=200)
    names = [s.scenario.name for s in bundle.scenarios]
    assert names == ["central", "optimistic", "pessimistic", "custom"]
    central, custom = bundle.scenarios[0], bundle.scenarios[3]
    assert central.scenario.parameter_values["taxable_profit_elasticity"] == params["taxable_profit_elasticity"].value
    assert custom.scenario.parameter_values["taxable_profit_elasticity"] == 0.45
    assert custom.result.scenario == "custom"
    tornado = sensitivity(demo_policy, overridden, baseline)
    assert [r.model_dump() for r in bundle.sensitivity] == [r.model_dump() for r in tornado]


def test_simulate_options(full_engine, demo_policy, params, baseline):
    bundle = simulate(demo_policy, params, baseline, draws=0, include_sensitivity=False)
    assert bundle.monte_carlo is None and bundle.sensitivity == [] and bundle.warnings == []
    assert len(bundle.scenarios) == 3


def _median_s(fn, n=7):
    fn()  # warm-up
    times = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    return sorted(times)[n // 2]


@pytest.mark.perf
@pytest.mark.parametrize("engine", ["registry", "full"])
def test_performance_budget(request, engine, demo_policy, params, baseline):
    if engine == "full":
        request.getfixturevalue("full_engine")

    def mc_and_tornado():
        monte_carlo(demo_policy, params, baseline, draws=2000)
        sensitivity(demo_policy, params, baseline)

    assert _median_s(mc_and_tornado) < 0.300 * PERF_SLACK
    assert _median_s(lambda: simulate(demo_policy, params, baseline, draws=2000), n=3) < 1.0 * PERF_SLACK


def test_sample_bundle_fixture_matches_the_contract():
    """`fixtures/sample_bundle.json` is the shape reference for agent-8's charts (25% -> 28%, 2,000 draws, seed 42,
    generated with the section 9.5 test engine and the placeholder baseline; not real figures)."""
    import json
    import pathlib

    from jane_avenue.contracts import SimulationBundle

    raw = json.loads((pathlib.Path(__file__).parent / "fixtures" / "sample_bundle.json").read_text(encoding="utf-8"))
    bundle = SimulationBundle.model_validate(raw)
    assert [s.scenario.name for s in bundle.scenarios] == ["central", "optimistic", "pessimistic"]
    assert bundle.monte_carlo and bundle.monte_carlo.interval_note.startswith(VERBATIM_NOTE)
    assert len(bundle.sensitivity) == 3
