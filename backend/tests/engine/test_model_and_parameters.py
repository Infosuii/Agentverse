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
    assert steps["rev.static.2027-28"].source_ids[0] == "D-obr-efo"  # baseline first, then parameter sources
    assert "D-lit-test2014" not in steps["rev.static.2027-28"].source_ids
    assert "D-lit-test2014" in steps["rev.behavioural.2027-28"].source_ids
    assert "D-obr-efo" in steps["rev.behavioural.2027-28"].source_ids
    assert "D-lit-hmrc2026" in steps["rev.base.2027-28"].source_ids  # main_rate_profit_share


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
    assert d.kind == "normal" and d.params == {"mean": 0.0, "sd": 10.0}
    for name in ("share_plant_machinery", "depreciation_structures", "trend_real_growth"):
        assert params[name].distribution.kind == "fixed" and not params[name].adjustable
    for p in params.values():
        assert p.low <= p.value <= p.high
        if p.distribution.kind == "triangular":
            assert p.distribution.params == {"low": p.low, "mode": p.value, "high": p.high}


def _registered_source_ids() -> set[str]:
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "data" / "curated" / "literature_sources.csv"
    with path.open(encoding="utf-8") as f:
        return {row["source_id"] for row in csv.DictReader(f)}


def test_every_parameter_is_sourced_or_declared_judgement(monkeypatch):
    from jane_avenue.engine import parameters as reg

    monkeypatch.setattr(reg, "_investment_shares", lambda: None)  # shares are tested separately
    registered = _registered_source_ids() | {"D-ons-investment"}
    for p in default_parameters().values():
        assert set(p.source_ids) <= registered, p.name
        if p.name.startswith("share_"):
            assert p.is_placeholder and p.basis == "team_judgement"  # 9.5 prior until the ONS dataset is present
            continue
        assert not p.is_placeholder, p.name
        assert p.rationale and "awaiting" not in p.rationale, p.name
        if p.basis != "team_judgement":
            assert p.source_ids, p.name
        else:
            assert "judgement" in p.rationale.lower(), p.name


def test_investment_shares_come_from_ons_dataset(monkeypatch):
    from jane_avenue.contracts import TimeSeries, TimeSeriesPoint
    from jane_avenue.data import registry

    points = [TimeSeriesPoint(period="plant_machinery", value=0.267), TimeSeriesPoint(period="structures", value=0.288),
              TimeSeriesPoint(period="intangibles", value=0.445)]
    series = TimeSeries(series_id="business_investment_by_asset", title="Investment shares 2025", unit="fraction",
                        frequency="annual", dataset_id="business_investment_by_asset", points=points)
    monkeypatch.setattr(registry, "load_series", lambda sid: series if sid == "business_investment_by_asset" else None)
    params = default_parameters()
    for name, v in (("share_plant_machinery", 0.267), ("share_structures", 0.288), ("share_intangibles", 0.445)):
        p = params[name]
        assert (p.value, p.low, p.high) == (v, v, v)
        assert p.basis == "official" and p.source_ids == ["D-ons-investment"] and not p.is_placeholder
        assert "2025" in p.rationale


def test_statutory_and_effective_tax_rate_steps(demo_spec, baseline):
    res = run_engine(demo_spec, default_parameters(), baseline)
    steps = {s.step_id: s for s in res.calc_trace}
    assert {"D-lit-hmrc2023", "D-lit-hmrc2026hs252"} <= set(steps["inv.allowance_pv.plant_machinery"].source_ids)
    assert "D-lit-hmrc2020" in steps["inv.allowance_pv.structures"].source_ids
    for tag in ("baseline", "proposed"):
        for kind in ("emtr", "eatr"):
            s = steps[f"etr.{kind}.{tag}"]
            assert s.unit == "%" and "D-lit-hanappi2018" in s.source_ids
    assert steps["etr.eatr.proposed"].output > steps["etr.eatr.baseline"].output > 0
    assert steps["etr.emtr.proposed"].output > steps["etr.emtr.baseline"].output
    assert not any(m.metric.startswith("etr") for m in res.metrics)  # explainability only; metrics are frozen


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
    assert p.distribution.params == {"mean": 3.0, "sd": 10.0}
    assert (p.low, p.high) == (-7.0, 13.0)


def test_apply_overrides_rejects_unknown_and_non_finite():
    with pytest.raises(ValueError, match="Unknown parameter"):
        apply_overrides(default_parameters(), {"not_a_parameter": 1.0})
    with pytest.raises(ValueError):
        apply_overrides(default_parameters(), {"capital_share": float("nan")})


def test_apply_overrides_rejects_fixed_parameters():
    with pytest.raises(ValueError, match="fixed"):
        apply_overrides(default_parameters(), {"share_structures": 0.5})


def test_sample_fixture_is_current(demo_spec, baseline):
    """tests/engine/fixtures/sample_engine_result.json is the hand-off sample for agent-8's calc inspector."""
    import json
    from pathlib import Path

    sample = EngineResult.model_validate(json.loads((Path(__file__).parent / "fixtures" /
                                                     "sample_engine_result.json").read_text(encoding="utf-8")))
    fresh = run_engine(sample.policy, default_parameters(), baseline)
    assert [s.step_id for s in fresh.calc_trace] == [s.step_id for s in sample.calc_trace]
    assert [s.output for s in fresh.calc_trace] == pytest.approx([s.output for s in sample.calc_trace])
