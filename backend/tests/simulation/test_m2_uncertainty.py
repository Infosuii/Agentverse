"""M2 tests: parameter validation, Monte Carlo standard error, empirical interval. Owner: agent-4."""
import re

import numpy as np
import pytest

from jane_avenue.contracts import Distribution
from jane_avenue.engine.parameters import apply_overrides
from jane_avenue.evaluation import results as evaluation_results
from jane_avenue.simulation import monte_carlo, simulate, validate_parameters
from jane_avenue.simulation.montecarlo import median_standard_error

RESIDUALS = [0.12, -0.08, 0.05, -0.02, 0.03, -0.10, 0.07, 0.01, -0.04, 0.09]  # n = 10, (pred − obs)/obs
OUTCOME_ERRORS = [1 / (1 + r) - 1 for r in RESIDUALS]  # (obs − pred)/pred, what the interval is built from


def _info(**overrides):
    info = {"n": len(RESIDUALS), "test_period": "2008-09 to 2025-26", "loo_coverage_90": 0.9, "loo_covered": 9,
            "residuals": RESIDUALS}
    info.update(overrides)
    return info


@pytest.fixture
def calibrated(monkeypatch):
    """Expose agent-10's agreed `empirical_calibration_info()` helper (not on main yet)."""
    def install(info):
        monkeypatch.setattr(evaluation_results, "empirical_calibration_info", lambda: info, raising=False)
    install(_info())
    return install


# ---- validation -------------------------------------------------------------------------------------------------------

def test_registry_defaults_and_overrides_are_valid(params):
    validate_parameters(params)
    validate_parameters(apply_overrides(params, {"taxable_profit_elasticity": 0.9, "profit_base_deviation_pct": -15}))


# Each case builds its bad values from the parameter's own value and range, so the tests do not depend on the registry's
# current numbers (agent-3 sources and changes them).
@pytest.mark.parametrize(("name", "update", "message"), [
    ("taxable_profit_elasticity", lambda p: {"value": p.high + 0.1}, "low <= value <= high"),
    ("capital_share", lambda p: {"low": p.value + 0.01, "high": p.value + 0.02}, "low <= value <= high"),
    ("user_cost_elasticity", lambda p: {"distribution": Distribution(
        kind="triangular", params={"low": p.low, "mode": p.high + 0.1, "high": p.high})}, "triangular mode"),
    ("real_required_return", lambda p: {"distribution": Distribution(
        kind="uniform", params={"low": p.value + 0.01, "high": p.value + 0.02})}, "outside the uniform support"),
    ("capital_share", lambda p: {"distribution": Distribution(
        kind="truncated_normal", params={"mean": p.value, "sd": 0.02, "low": p.value - 0.2, "high": p.value - 0.1})},
     "outside the truncated_normal support"),
    ("profit_base_deviation_pct", lambda p: {"value": 0.0, "low": -1.0, "high": 1.0, "distribution": Distribution(
        kind="lognormal", params={"mu": 0.0, "sigma": 0.1})}, "positive value"),
    ("profit_base_deviation_pct", lambda p: {"distribution": Distribution(
        kind="normal", params={"mean": p.value, "sd": -1.0})}, "sd must be >= 0"),
    ("capital_share", lambda p: {"value": float("nan")}, "finite"),
])
def test_invalid_parameters_raise_a_clear_error(params, demo_policy, baseline, name, update, message):
    bad = dict(params)
    bad[name] = params[name].model_copy(update=update(params[name]))
    with pytest.raises(ValueError, match=re.escape(name)) as exc:
        validate_parameters(bad)
    assert message in str(exc.value)
    with pytest.raises(ValueError, match=re.escape(f"{name}: ")):
        simulate(demo_policy, bad, baseline, draws=10)


# ---- Monte Carlo standard error -------------------------------------------------------------------------------------------

def test_median_standard_error_matches_theory():
    x = np.random.default_rng(3).normal(0.0, 1.0, 20_000)
    assert median_standard_error(x) == pytest.approx(np.sqrt(np.pi / 2) / np.sqrt(x.size), rel=0.15)
    assert median_standard_error(np.full(100, 4.2)) == 0.0
    assert median_standard_error(np.array([1.0])) == 0.0


def test_interval_note_reports_the_median_standard_error(full_engine, demo_policy, params, baseline):
    note = monte_carlo(demo_policy, params, baseline, draws=2000).interval_note
    m = re.search(r"\(MC s\.e\. of the final-year median of behavioural revenue ±£(\d+\.\d{2})bn at n=2000\)$", note)
    assert m and 0 < float(m.group(1)) < 1
    assert "below £0.01bn" in monte_carlo(demo_policy, {n: p.model_copy(update={"distribution": Distribution(
        kind="fixed")}) for n, p in params.items()}, baseline, draws=50).interval_note


def test_low_draw_count_warns(full_engine, demo_policy, params, baseline):
    assert any("Only 200 Monte Carlo draws" in w for w in simulate(demo_policy, params, baseline, draws=200).warnings)
    assert not any("Monte Carlo draws" in w for w in simulate(demo_policy, params, baseline, draws=500).warnings)


# ---- empirical interval ---------------------------------------------------------------------------------------------------

def _behavioural(result):
    return [v.value for v in next(m for m in result.metrics if m.metric == "revenue_behavioural_gbp_bn").values]


@pytest.mark.parametrize("policy_fixture", ["demo_policy", "cut_policy"])
def test_empirical_interval_when_justified(full_engine, calibrated, request, policy_fixture, params, baseline):
    spec = request.getfixturevalue(policy_fixture)
    bundle = simulate(spec, params, baseline, draws=500, empirical_residuals=lambda: RESIDUALS)
    mc = bundle.monte_carlo
    assert mc.interval_kind == "assumption_range"  # the main bands keep their label
    central = _behavioural(bundle.scenarios[0].result)
    assert len(mc.empirical_interval) == len(central)
    q50 = float(np.percentile(OUTCOME_ERRORS, 50))
    for band, c in zip(mc.empirical_interval, central, strict=True):
        assert band.p5 <= band.p10 <= band.p25 <= band.p50 <= band.p75 <= band.p90 <= band.p95
        assert band.p50 == pytest.approx(c * (1 + q50))
        assert band.mean == pytest.approx(c * (1 + np.mean(OUTCOME_ERRORS)))
    lo, hi = np.percentile(OUTCOME_ERRORS, [5, 95])
    last = mc.empirical_interval[-1]
    assert [last.p5, last.p95] == pytest.approx(sorted([central[-1] * (1 + lo), central[-1] * (1 + hi)]))
    note = mc.empirical_calibration_note
    assert "n=10" in note and "2008-09 to 2025-26" in note and "9/10" in note and "90%" in note
    assert not any("empirical prediction interval" in w.lower() for w in bundle.warnings)


def test_empirical_interval_follows_the_custom_scenario(full_engine, calibrated, demo_policy, params, baseline):
    overridden = apply_overrides(params, {"taxable_profit_elasticity": 0.45})
    bundle = simulate(demo_policy, overridden, baseline, draws=500, empirical_residuals=lambda: RESIDUALS)
    custom = _behavioural(bundle.scenarios[-1].result)
    q50 = float(np.percentile(OUTCOME_ERRORS, 50))
    assert [b.p50 for b in bundle.monte_carlo.empirical_interval] == pytest.approx([c * (1 + q50) for c in custom])


@pytest.mark.parametrize(("residuals", "info", "reason"), [
    (None, _info(), "supplied 0 out-of-sample residuals"),
    (RESIDUALS[:7], _info(), "supplied 7 out-of-sample residuals"),
    (RESIDUALS, None, "did not report the test period and observed coverage"),
    (RESIDUALS, _info(loo_covered=None, loo_coverage_90=None), "did not report"),
    (RESIDUALS, _info(test_period=""), "did not report"),
])
def test_no_empirical_interval_explains_why(full_engine, calibrated, demo_policy, params, baseline, residuals, info,
                                            reason):
    calibrated(info)
    bundle = simulate(demo_policy, params, baseline, draws=500, empirical_residuals=lambda: residuals)
    assert bundle.monte_carlo.empirical_interval is None and bundle.monte_carlo.empirical_calibration_note is None
    assert any(w.startswith("No empirical prediction interval is shown") and reason in w for w in bundle.warnings)


def test_no_helper_on_main_means_no_interval(full_engine, demo_policy, params, baseline):
    bundle = simulate(demo_policy, params, baseline, draws=500, empirical_residuals=lambda: RESIDUALS)
    if not hasattr(evaluation_results, "empirical_calibration_info"):
        assert bundle.monte_carlo.empirical_interval is None


def test_under_coverage_is_flagged(full_engine, calibrated, demo_policy, params, baseline):
    calibrated(_info(loo_covered=None, loo_coverage_90=62.5))  # percent form is accepted too
    bundle = simulate(demo_policy, params, baseline, draws=500, empirical_residuals=lambda: RESIDUALS)
    assert bundle.monte_carlo.empirical_interval is not None
    assert "62%" in bundle.monte_carlo.empirical_calibration_note or "63%" in bundle.monte_carlo.empirical_calibration_note
    assert any("likely too narrow" in w for w in bundle.warnings)


@pytest.mark.parametrize("policy_fixture", ["demo_policy", "cut_policy"])
def test_biased_backtest_shifts_the_band_the_right_way(full_engine, calibrated, request, policy_fixture, params,
                                                        baseline):
    """A model that over-predicted by about 10% in the backtest ((pred − obs)/obs ≈ +0.10) should get a band centred
    on central / 1.1, closer to zero than central. It must not be pushed further out to central × 1.1."""
    spec = request.getfixturevalue(policy_fixture)
    over = [0.08, 0.09, 0.10, 0.10, 0.10, 0.11, 0.12, 0.10, 0.09, 0.11]
    calibrated(_info(n=len(over), residuals=over))
    bundle = simulate(spec, params, baseline, draws=200, empirical_residuals=lambda: over)
    central = _behavioural(bundle.scenarios[0].result)
    for band, c in zip(bundle.monte_carlo.empirical_interval, central, strict=True):
        assert band.p50 == pytest.approx(c / 1.10, rel=1e-9)
        assert abs(band.p95) < abs(c) and abs(band.p5) < abs(c)  # the whole band sits on the observed (smaller) side
    under = [-r / (1 + r) for r in over]  # mirror image: the model under-predicted, so outcomes ran above it
    bundle = simulate(spec, params, baseline, draws=200, empirical_residuals=lambda: under)
    for band, c in zip(bundle.monte_carlo.empirical_interval, central, strict=True):
        assert abs(band.p5) > abs(c) and band.p50 == pytest.approx(c * 1.10, rel=1e-9)


def test_unconvertible_residuals_are_dropped(full_engine, calibrated, demo_policy, params, baseline):
    bundle = simulate(demo_policy, params, baseline, draws=200,
                      empirical_residuals=lambda: [-1.0, -1.5, float("nan")] + RESIDUALS[:6])
    assert bundle.monte_carlo.empirical_interval is None
    assert any("supplied 6 out-of-sample residuals" in w for w in bundle.warnings)
