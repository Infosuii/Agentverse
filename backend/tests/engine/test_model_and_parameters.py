"""run_engine trace tests and parameter registry tests (owner: agent-3)."""
from __future__ import annotations

import math

import pytest

from jane_avenue.contracts import METRIC_NAMES, EngineResult
from jane_avenue.engine import (
    MODEL_VERSION,
    PARAMETER_NAMES,
    apply_overrides,
    central_values,
    compute,
    default_parameters,
    run_engine,
)

# ---- run_engine ------------------------------------------------------------------------------------------------------


def test_run_engine_matches_compute(demo_spec, baseline):
    params = default_parameters()
    res = run_engine(demo_spec, params, baseline)
    assert isinstance(res, EngineResult)
    assert res.model_version == MODEL_VERSION
    out = compute(demo_spec, central_values(params), baseline)
    assert [m.metric for m in res.metrics] == list(METRIC_NAMES)
    for m in res.metrics:
        assert [v.value for v in m.values] == pytest.approx(out.metrics[m.metric][0].tolist())


def test_confidence_and_indicative_labels(demo_spec, baseline):
    res = run_engine(demo_spec, default_parameters(), baseline)
    conf = {m.metric: m.confidence for m in res.metrics}
    assert conf == {"revenue_static_gbp_bn": "high", "revenue_behavioural_gbp_bn": "medium",
                    "revenue_dynamic_gbp_bn": "low", "business_investment_pct": "medium",
                    "business_investment_gbp_bn": "medium", "gdp_level_pct": "low", "cost_of_capital_pct": "medium"}
    by = {m.metric: m for m in res.metrics}
    assert "indicative" in by["gdp_level_pct"].label.lower()
    assert "indicative" in by["revenue_dynamic_gbp_bn"].label.lower()
    assert "full expensing" in by["business_investment_pct"].note.lower()


def test_calc_trace_is_complete(demo_spec, baseline):
    res = run_engine(demo_spec, default_parameters(), baseline)
    ids = {s.step_id for s in res.calc_trace}
    assert len(ids) == len(res.calc_trace), "step ids must be unique"
    for a in ("plant_machinery", "structures", "intangibles"):
        for prefix in ("inv.allowance_pv", "inv.user_cost.baseline", "inv.user_cost.proposed", "inv.user_cost"):
            assert f"{prefix}.{a}" in ids
    assert {"inv.user_cost.weighted", "inv.long_run", "gdp.capital_turnover"} <= ids
    for fy in res.fiscal_years:
        for prefix in ("rev.base", "rev.static", "rev.base_response", "rev.behavioural", "inv.change",
                       "inv.change_gbp", "gdp.capital_gap", "gdp.level", "rev.dynamic"):
            assert f"{prefix}.{fy}" in ids
    for s in res.calc_trace:
        assert s.formula and s.unit and s.parameter_names
        assert set(s.parameter_names) <= set(PARAMETER_NAMES)
        assert all(math.isfinite(v) for v in s.inputs.values()) and math.isfinite(s.output)


def test_trace_outputs_equal_metric_values(demo_spec, baseline):
    res = run_engine(demo_spec, default_parameters(), baseline)
    steps = {s.step_id: s for s in res.calc_trace}
    step_for = {"revenue_static_gbp_bn": "rev.static", "revenue_behavioural_gbp_bn": "rev.behavioural",
                "revenue_dynamic_gbp_bn": "rev.dynamic", "business_investment_pct": "inv.change",
                "business_investment_gbp_bn": "inv.change_gbp", "gdp_level_pct": "gdp.level"}
    for m in res.metrics:
        for v in m.values:
            sid = "inv.user_cost.weighted" if m.metric == "cost_of_capital_pct" else f"{step_for[m.metric]}.{v.fiscal_year}"
            assert steps[sid].output == pytest.approx(v.value), sid


def test_trace_carries_baseline_and_parameter_sources(demo_spec, baseline):
    params = default_parameters()
    params["taxable_profit_elasticity"] = params["taxable_profit_elasticity"].model_copy(
        update={"source_ids": ["D-lit-test2014"]})
    res = run_engine(demo_spec, params, baseline)
    steps = {s.step_id: s for s in res.calc_trace}
    assert steps["rev.static.2027-28"].source_ids == ["D-obr-efo"]
    assert "D-lit-test2014" in steps["rev.behavioural.2027-28"].source_ids
    assert "D-obr-efo" in steps["rev.behavioural.2027-28"].source_ids


def test_run_engine_accepts_plain_floats(demo_spec, baseline):
    res = run_engine(demo_spec, central_values(default_parameters()), baseline, scenario="custom")
    assert res.scenario == "custom"


def test_small_profits_trace_has_no_investment_steps(spec_factory, baseline):
    spec = spec_factory(19, 21, policy_type="corporation_tax_small_profits_rate")
    res = run_engine(spec, default_parameters(), baseline)
    assert not any(s.step_id.startswith(("inv.", "gdp.")) for s in res.calc_trace)
    assert any("partial support" in w for w in res.warnings)


# ---- Parameter registry --------------------------------------------------------------------------------------------

def test_registry_matches_spec_table():
    params = default_parameters()
    assert tuple(params) == PARAMETER_NAMES
    assert len(PARAMETER_NAMES) == 19
    p = params["taxable_profit_elasticity"]
    assert (p.value, p.low, p.high, p.slider_min, p.slider_max) == (0.20, 0.05, 0.50, 0.0, 1.0)
    assert p.distribution.kind == "triangular"
    assert p.distribution.params == {"low": 0.05, "mode": 0.20, "high": 0.50}
    d = params["profit_base_deviation_pct"].distribution
    assert d.kind == "normal" and d.params == {"mean": 0.0, "sd": 5.0}
    for name in ("share_plant_machinery", "depreciation_structures", "trend_real_growth"):
        assert params[name].distribution.kind == "fixed" and not params[name].adjustable
    for p in params.values():
        assert p.basis == "team_judgement" and p.is_placeholder
        assert p.low <= p.value <= p.high


def test_apply_overrides_shifts_whole_distribution():
    params = default_parameters()
    out = apply_overrides(params, {"taxable_profit_elasticity": 0.30})
    p = out["taxable_profit_elasticity"]
    assert p.is_user_override
    assert (p.value, p.low, p.high) == pytest.approx((0.30, 0.15, 0.60))
    assert p.distribution.params == pytest.approx({"low": 0.15, "mode": 0.30, "high": 0.60})
    assert not params["taxable_profit_elasticity"].is_user_override  # input untouched
    assert out["user_cost_elasticity"] == params["user_cost_elasticity"]


def test_apply_overrides_clips_to_slider_bounds():
    out = apply_overrides(default_parameters(), {"taxable_profit_elasticity": 5.0})
    p = out["taxable_profit_elasticity"]
    assert p.value == 1.0 and p.high == 1.0
    assert p.low <= p.value <= p.high
    assert max(p.distribution.params.values()) <= 1.0
    low = apply_overrides(default_parameters(), {"taxable_profit_elasticity": -1})["taxable_profit_elasticity"]
    assert low.value == 0.0 and low.low == 0.0 and low.low <= low.value <= low.high


def test_apply_overrides_normal_distribution():
    p = apply_overrides(default_parameters(), {"profit_base_deviation_pct": 3.0})["profit_base_deviation_pct"]
    assert p.distribution.params == {"mean": 3.0, "sd": 5.0}
    assert (p.low, p.high) == (-2.0, 8.0)


def test_apply_overrides_rejects_unknown_and_non_finite():
    with pytest.raises(ValueError, match="Unknown parameter"):
        apply_overrides(default_parameters(), {"not_a_parameter": 1.0})
    with pytest.raises(ValueError):
        apply_overrides(default_parameters(), {"capital_share": float("nan")})


def test_sample_fixture_is_current(demo_spec, baseline):
    """tests/engine/fixtures/sample_engine_result.json is the hand-off sample for agent-8's calc inspector."""
    import json
    from pathlib import Path

    sample = EngineResult.model_validate(json.loads((Path(__file__).parent / "fixtures" /
                                                     "sample_engine_result.json").read_text(encoding="utf-8")))
    fresh = run_engine(sample.policy, default_parameters(), baseline)
    assert [s.step_id for s in fresh.calc_trace] == [s.step_id for s in sample.calc_trace]
    assert [s.output for s in fresh.calc_trace] == pytest.approx([s.output for s in sample.calc_trace])
