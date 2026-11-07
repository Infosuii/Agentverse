"""Engine core tests (owner: agent-3): economics, shapes, validation, golden numbers, performance."""
from __future__ import annotations

import time

import numpy as np
import pytest

from jane_avenue.contracts import METRIC_NAMES
from jane_avenue.engine import compute, revenue_static_behavioural
from jane_avenue.engine.core import allowance_pv_plant_machinery, devereux_griffith, user_cost

# ---- Golden-number regression ----------------------------------------------------------------------------------------
# Demo policy: CT main rate 25% → 28% from 1 April 2027, 5 years, against the frozen baseline in conftest.py and the
# frozen parameter set below (the M2 sourced central values, with the ONS 2025 investment shares from agent-6's
# business_investment_by_asset dataset). Both are frozen so data updates do not move these numbers. If an intentional
# model or parameter change moves them, regenerate them and say why here:
#   2026-11-07 agent-3: first M1 engine (team-prior parameters, MASTER_PROMPT 9.5 equations).
#   2026-11-07 agent-3: M2 sourcing. main_rate_profit_share 0.85→0.87 (HMRC CT statistics 2026), capital_share
#     0.35→0.40 (ONS labour share), investment shares 0.40/0.27/0.33 → ONS 2025 0.267/0.288/0.445.
FROZEN_PARAMS = {
    "taxable_profit_elasticity": 0.20, "user_cost_elasticity": 0.60, "profit_gdp_elasticity": 1.0,
    "behavioural_first_year_share": 0.5, "receipts_first_year_share": 0.6, "investment_adjustment_speed": 0.5,
    "main_rate_profit_share": 0.87, "real_required_return": 0.05, "full_expensing_coverage": 0.80,
    "allowance_pv_intangibles": 0.90, "capital_share": 0.40,
    "share_plant_machinery": 0.26704290684190185, "share_structures": 0.28833088519520683,
    "share_intangibles": 0.4446262079628914,
    "depreciation_plant_machinery": 0.175, "depreciation_structures": 0.0361, "depreciation_intangibles": 0.1535,
    "profit_base_deviation_pct": 0.0, "trend_real_growth": 0.015,
}
GOLDEN: dict[str, list[float]] = {
    "revenue_static_gbp_bn": [7.278811, 12.777416, 13.298312, 13.842996, 14.409989],
    "revenue_behavioural_gbp_bn": [7.002049, 11.807727, 12.289092, 12.792439, 13.316403],
    "revenue_dynamic_gbp_bn": [6.990986, 11.762087, 12.213032, 12.685088, 13.17808],
    "business_investment_pct": [-0.291184, -0.436777, -0.509573, -0.545971, -0.56417],
    "business_investment_gbp_bn": [-0.901755, -1.369367, -1.616379, -1.753448, -1.834508],
    "gdp_level_pct": [-0.016352, -0.038584, -0.061783, -0.083769, -0.10369],
    "cost_of_capital_pct": [0.970615, 0.970615, 0.970615, 0.970615, 0.970615],
}


def test_golden_demo_policy(demo_spec, baseline):
    out = compute(demo_spec, FROZEN_PARAMS, baseline)
    assert out.fiscal_years == ["2027-28", "2028-29", "2029-30", "2030-31", "2031-32"]
    for metric, expected in GOLDEN.items():
        np.testing.assert_allclose(out.metrics[metric][0], expected, atol=1e-5, err_msg=metric)


def test_all_metrics_present_with_shape(demo_spec, central, baseline):
    out = compute(demo_spec, central, baseline)
    assert set(out.metrics) == set(METRIC_NAMES)
    assert all(v.shape == (1, 5) for v in out.metrics.values())


# ---- Signs ---------------------------------------------------------------------------------------------------------

def test_signs_for_a_rise(spec_factory, central, baseline):
    m = compute(spec_factory(25, 28), central, baseline).metrics
    assert (m["revenue_static_gbp_bn"] > 0).all()
    assert (m["revenue_behavioural_gbp_bn"] > 0).all()
    assert (m["cost_of_capital_pct"] > 0).all()
    assert (m["business_investment_pct"] < 0).all()
    assert (m["business_investment_gbp_bn"] < 0).all()
    assert (m["gdp_level_pct"] < 0).all()
    assert (m["revenue_dynamic_gbp_bn"] < m["revenue_behavioural_gbp_bn"]).all()


def test_signs_for_a_cut(spec_factory, central, baseline):
    m = compute(spec_factory(25, 22), central, baseline).metrics
    assert (m["revenue_static_gbp_bn"] < 0).all()
    assert (m["revenue_behavioural_gbp_bn"] < 0).all()
    assert (m["cost_of_capital_pct"] < 0).all()
    assert (m["business_investment_pct"] > 0).all()
    assert (m["gdp_level_pct"] > 0).all()
    assert (m["revenue_dynamic_gbp_bn"] > m["revenue_behavioural_gbp_bn"]).all()


def test_behavioural_between_zero_and_static_for_a_rise(spec_factory, central, baseline):
    m = compute(spec_factory(25, 28), central, baseline).metrics
    assert (0 < m["revenue_behavioural_gbp_bn"]).all()
    assert (m["revenue_behavioural_gbp_bn"] < m["revenue_static_gbp_bn"]).all()


def test_behavioural_loss_smaller_than_static_loss_for_a_cut(spec_factory, central, baseline):
    m = compute(spec_factory(25, 22), central, baseline).metrics
    assert (np.abs(m["revenue_behavioural_gbp_bn"]) < np.abs(m["revenue_static_gbp_bn"])).all()


def test_zero_change_is_zero_everywhere(spec_factory, central, baseline):
    out = compute(spec_factory(25, 25), central, baseline)
    for metric, values in out.metrics.items():
        assert np.all(values == 0.0), metric


def test_small_change_symmetry(spec_factory, central, baseline):
    up = compute(spec_factory(25, 25.1), central, baseline).metrics
    down = compute(spec_factory(25, 24.9), central, baseline).metrics
    for metric in METRIC_NAMES:
        np.testing.assert_allclose(up[metric], -down[metric], rtol=0.02, atol=1e-9, err_msg=metric)


# ---- Full expensing ----------------------------------------------------------------------------------------------

def test_plant_machinery_rate_neutral_at_full_expensing(spec_factory, central, baseline):
    z = allowance_pv_plant_machinery(1.0, central["real_required_return"])
    assert z == pytest.approx(1.0)
    for t in (0.19, 0.25, 0.28, 0.40):
        assert user_cost(t, z, 0.05, 0.175) == pytest.approx(0.05 + 0.175)
    params = dict(central, full_expensing_coverage=1.0)
    out = compute(spec_factory(25, 28), params, baseline)
    assert out.intermediates["dc_plant_machinery"][0, 0] == pytest.approx(0.0, abs=1e-12)
    assert out.intermediates["dc_structures"][0, 0] > 0
    assert out.intermediates["dc_intangibles"][0, 0] > 0


# ---- Monotonicity ------------------------------------------------------------------------------------------------

def test_revenue_monotonic_in_profit_elasticity(spec_factory, central, baseline):
    spec = spec_factory(25, 28)
    eps = np.linspace(0.0, 1.0, 11)
    behav = compute(spec, dict(central, taxable_profit_elasticity=eps), baseline).metrics["revenue_behavioural_gbp_bn"]
    assert np.all(np.diff(behav, axis=0) < 0)  # a larger ε shrinks the revenue gain from a rise


def test_investment_monotonic_in_user_cost_elasticity(spec_factory, central, baseline):
    spec = spec_factory(25, 28)
    sigma = np.linspace(0.0, 1.5, 11)
    inv = compute(spec, dict(central, user_cost_elasticity=sigma), baseline).metrics["business_investment_pct"]
    assert np.all(np.diff(inv, axis=0) < 0)  # a larger σ deepens the investment fall from a rise


# ---- Vectorisation -------------------------------------------------------------------------------------------------

def _draws(central: dict[str, float], n: int, seed: int = 0) -> dict[str, float | np.ndarray]:
    rng = np.random.default_rng(seed)
    params: dict[str, float | np.ndarray] = dict(central)
    params["taxable_profit_elasticity"] = rng.uniform(0.05, 0.5, n)
    params["user_cost_elasticity"] = rng.uniform(0.3, 1.0, n)
    params["real_required_return"] = rng.uniform(0.03, 0.07, n)
    params["full_expensing_coverage"] = rng.uniform(0.6, 0.95, n)
    params["investment_adjustment_speed"] = rng.uniform(0.3, 0.8, n)
    params["receipts_first_year_share"] = rng.uniform(0.45, 0.75, n)
    params["profit_base_deviation_pct"] = rng.normal(0, 5, n)
    params["capital_share"] = rng.uniform(0.3, 0.4, n)
    return params


def test_vectorised_equals_scalar(demo_spec, central, baseline):
    n = 7
    params = _draws(central, n)
    vec = compute(demo_spec, params, baseline)
    for metric in METRIC_NAMES:
        assert vec.metrics[metric].shape == (n, 5)
    for i in range(n):
        scalar = {k: (float(v[i]) if isinstance(v, np.ndarray) else v) for k, v in params.items()}
        one = compute(demo_spec, scalar, baseline)
        for metric in METRIC_NAMES:
            np.testing.assert_allclose(vec.metrics[metric][i], one.metrics[metric][0], rtol=1e-12, atol=1e-12)


def test_2000_draws_under_50ms(demo_spec, central, baseline):
    params = _draws(central, 2000)
    compute(demo_spec, params, baseline)  # warm-up
    best = min(_timed(lambda: compute(demo_spec, params, baseline)) for _ in range(5))
    assert best < 0.050, f"compute took {best * 1000:.1f} ms for 2000 draws"


def _timed(fn) -> float:
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


# ---- Evaluation helper ---------------------------------------------------------------------------------------------

def test_revenue_static_behavioural_matches_compute(demo_spec, central, baseline):
    out = compute(demo_spec, central, baseline)
    j = 1  # second year: timing = 1, full elasticity
    static, behav = revenue_static_behavioural(
        0.25, 0.28, float(out.intermediates["R"][0, j]),
        main_rate_profit_share=central["main_rate_profit_share"],
        elasticity=central["taxable_profit_elasticity"])
    assert static == pytest.approx(out.metrics["revenue_static_gbp_bn"][0, j])
    assert behav == pytest.approx(out.metrics["revenue_behavioural_gbp_bn"][0, j])


# ---- Baseline handling and validation -------------------------------------------------------------------------------

def test_extrapolates_beyond_baseline_with_warning(demo_spec, central, baseline):
    out = compute(demo_spec, central, baseline)
    R = out.intermediates["R"][0]
    assert R[-1] == pytest.approx(R[-2] * (132.59574346866282 / 127.37846588160546))
    assert any("2031-32" in w and "extrapolated" in w for w in out.warnings)


def test_warns_when_baseline_rate_differs(spec_factory, central, baseline):
    out = compute(spec_factory(26, 28), central, baseline)
    assert any("differs" in w for w in out.warnings)


def test_rejects_missing_rates(spec_factory, central, baseline):
    with pytest.raises(ValueError, match="rate"):
        compute(spec_factory(25, None), central, baseline)


def test_rejects_rate_of_100_percent(spec_factory, central, baseline):
    with pytest.raises(ValueError):
        compute(spec_factory(25, 100), central, baseline)


def test_rejects_unsupported_policy(spec_factory, central, baseline):
    with pytest.raises(ValueError):
        compute(spec_factory(20, 21, policy_type="vat_standard_rate"), central, baseline)


def test_shares_small_drift_renormalised_with_warning(demo_spec, central, baseline):
    shares = {"share_plant_machinery": 0.40, "share_structures": 0.275, "share_intangibles": 0.33}  # sums to 1.005
    out = compute(demo_spec, dict(central, **shares), baseline)
    assert any("renormalised" in w for w in out.warnings)
    w = sum(out.intermediates[f"w_{a}"][0, 0] for a in ("plant_machinery", "structures", "intangibles"))
    assert w == pytest.approx(1.0)


def test_shares_large_drift_raises(demo_spec, central, baseline):
    with pytest.raises(ValueError, match="sum to 1"):
        compute(demo_spec, dict(central, share_structures=0.40), baseline)


def test_missing_parameter_raises(demo_spec, central, baseline):
    params = dict(central)
    del params["capital_share"]
    with pytest.raises(ValueError, match="capital_share"):
        compute(demo_spec, params, baseline)


# ---- Small profits rate (partial support) ----------------------------------------------------------------------------

def test_small_profits_rate_partial(spec_factory, central, baseline):
    out = compute(spec_factory(19, 21, policy_type="corporation_tax_small_profits_rate"), central, baseline)
    m = out.metrics
    assert (m["revenue_static_gbp_bn"] > 0).all()
    np.testing.assert_allclose(m["revenue_dynamic_gbp_bn"], m["revenue_behavioural_gbp_bn"])
    for metric in ("business_investment_pct", "business_investment_gbp_bn", "gdp_level_pct", "cost_of_capital_pct"):
        assert np.all(m[metric] == 0.0)
    assert any("partial support" in w for w in out.warnings)
    b0 = out.intermediates["B0"][0, 1]
    R = out.intermediates["R"][0, 1]
    assert b0 == pytest.approx((1 - central["main_rate_profit_share"]) * R / 0.19)


# ---- Devereux-Griffith effective tax rates ------------------------------------------------------------------------------

def test_devereux_griffith_properties():
    p, r = 0.20, 0.05
    _, emtr, eatr = devereux_griffith(0.25, 1.0, r, 0.175, p)  # full expensing = cash-flow tax
    assert emtr == pytest.approx(0.0, abs=1e-12)
    assert eatr == pytest.approx(0.25 * (p - r) / p)
    _, emtr0, eatr0 = devereux_griffith(0.0, 0.5, r, 0.0361, p)
    assert emtr0 == pytest.approx(0.0, abs=1e-12) and eatr0 == pytest.approx(0.0, abs=1e-12)
    lo = devereux_griffith(0.25, 0.5, r, 0.0361, p)
    hi = devereux_griffith(0.28, 0.5, r, 0.0361, p)
    assert hi[1] > lo[1] > 0 and hi[2] > lo[2] > 0
