"""HMRC Ready Reckoner calibration, structural CT parameter training, and multi-policy stress tests. Owner: agent-11."""
from __future__ import annotations

import math
from datetime import date

import pytest
from pydantic import ValidationError

from jane_avenue.contracts import AnalysisRequest, ParseRequest, PolicySpec
from jane_avenue.data import registry
from jane_avenue.engine import apply_overrides, default_parameters, reckoner, run_engine
from jane_avenue.policy import check_scope, parse_policy
from jane_avenue.simulation import simulate

TODAY = date(2026, 11, 8)


def test_all_17_hmrc_measures_reconcile_with_published_ready_reckoner() -> None:
    """Every costed point in `tax_measures.csv` must match `official_effect_gbp_bn` within 1e-9."""
    measures = reckoner.measures()
    assert len(measures) == 17
    for mid, m in measures.items():
        for size, vals_m in m.up:
            up_vals = list(reckoner.official_effect_gbp_bn(m, float(size)))
            assert up_vals == pytest.approx([v / 1000.0 for v in vals_m], abs=1e-9), mid
        if m.down is not None:
            for size, vals_m in m.down:
                down_vals = list(reckoner.official_effect_gbp_bn(m, -float(size)))
                assert down_vals == pytest.approx([v / 1000.0 for v in vals_m], abs=1e-9), mid
        else:
            for size, vals_m in m.up:
                down_vals = list(reckoner.official_effect_gbp_bn(m, -float(size)))
                assert down_vals == pytest.approx([-v / 1000.0 for v in vals_m], abs=1e-9), mid


def test_ct_structural_engine_calibration_against_hmrc_june_2025_ready_reckoner() -> None:
    """Cross-check +1pp CT (25% -> 26%) against HMRC's June 2025 Ready Reckoner (+£3.6bn, +£3.9bn, +£4.0bn)."""
    hmrc_ct_1pp = {"2026-27": 3.60, "2027-28": 3.90, "2028-29": 4.00}
    baseline = registry.load_baseline()
    params = default_parameters()
    spec = PolicySpec(
        policy_type="corporation_tax_main_rate",
        tax="corporation_tax",
        baseline_rate_pct=25.0,
        proposed_rate_pct=26.0,
        effective_date=date(2026, 4, 1),
        horizon_years=3,
    )
    res = run_engine(spec, params, baseline, "central")
    behav = {
        v.fiscal_year: v.value
        for m in res.metrics
        if m.metric == "revenue_behavioural_gbp_bn"
        for v in m.values
    }
    # Steady-state years (2027-28 and 2028-29) agree with HMRC within £0.15bn
    assert abs(behav["2027-28"] - hmrc_ct_1pp["2027-28"]) < 0.15
    assert abs(behav["2028-29"] - hmrc_ct_1pp["2028-29"]) < 0.15

    # Calibrated parameters (eps=0.11, r1=0.90) achieve RMSE < £0.20bn across all 3 years
    cal_params = apply_overrides(
        params,
        {"taxable_profit_elasticity": 0.11, "receipts_first_year_share": 0.90},
    )
    cal_res = run_engine(spec, cal_params, baseline, "central")
    cal_behav = {
        v.fiscal_year: v.value
        for m in cal_res.metrics
        if m.metric == "revenue_behavioural_gbp_bn"
        for v in m.values
    }
    rmse = math.sqrt(sum((cal_behav[fy] - hmrc_ct_1pp[fy]) ** 2 for fy in hmrc_ct_1pp) / 3.0)
    assert rmse < 0.20


def test_simulation_invariants_across_all_17_hmrc_measures() -> None:
    """Every HMRC measure preserves finiteness, cumulative dynamic ordering, and MC quantile ordering."""
    baseline = registry.load_baseline()
    for mid, m in reckoner.measures().items():
        step = float(m.up[0][0])
        if m.unit == "pp":
            assert m.current_value is not None
            spec = PolicySpec(
                policy_type="tax_measure",
                measure_id=mid,
                baseline_rate_pct=m.current_value,
                proposed_rate_pct=m.current_value + step,
                effective_date=date(2027, 4, 1),
                horizon_years=5,
            )
        elif m.unit in ("gbp", "gbp_per_week"):
            assert m.current_value is not None
            spec = PolicySpec(
                policy_type="tax_measure",
                measure_id=mid,
                baseline_value=m.current_value,
                proposed_value=m.current_value + step,
                value_unit="£" if m.unit == "gbp" else "£/week",
                effective_date=date(2027, 4, 1),
                horizon_years=5,
            )
        elif m.current_value is not None:
            spec = PolicySpec(
                policy_type="tax_measure",
                measure_id=mid,
                baseline_value=m.current_value,
                proposed_value=round(m.current_value * (1.0 + step / 100.0), 4),
                value_unit=m.current_unit,
                effective_date=date(2027, 4, 1),
                horizon_years=5,
            )
        else:
            spec = PolicySpec(
                policy_type="tax_measure",
                measure_id=mid,
                baseline_value=100.0,
                proposed_value=100.0 + step,
                value_unit="index (current rate = 100)",
                effective_date=date(2027, 4, 1),
                horizon_years=5,
            )

        assert check_scope(spec).forecast_allowed, mid
        bundle = simulate(spec, default_parameters(spec), baseline, draws=200, seed=42, include_sensitivity=True)
        by_name = {s.scenario.name: s.result for s in bundle.scenarios}
        cum_dyn = {
            name: sum(
                v.value
                for mp in res.metrics
                if mp.metric == "revenue_dynamic_gbp_bn"
                for v in mp.values
            )
            for name, res in by_name.items()
        }
        assert cum_dyn["pessimistic"] <= cum_dyn["central"] + 1e-9, mid
        assert cum_dyn["central"] <= cum_dyn["optimistic"] + 1e-9, mid

        assert bundle.monte_carlo is not None
        for dist in bundle.monte_carlo.distributions:
            for band in dist.bands:
                qs = [band.p5, band.p10, band.p25, band.p50, band.p75, band.p90, band.p95]
                assert all(math.isfinite(q) for q in qs), mid
                assert all(qs[i] <= qs[i + 1] + 1e-9 for i in range(len(qs) - 1)), mid


@pytest.mark.parametrize(
    "query",
    [
        "Set corporation tax to -10%",
        "Raise corporation tax from 25% to -28%",
        "Set VAT standard rate to -18%",
        "Set income tax basic rate to -21%",
        "Set income tax basic rate to -20p",
        "Cut US corporate tax from 21% to 15%",
        "Raise French VAT to 22%",
        "Build 50 new hospitals across England",
    ],
)
def test_adversarial_and_invalid_queries_withhold_forecast(query: str) -> None:
    spec = parse_policy(query, today=TODAY, use_llm=False)
    decision = check_scope(spec)
    assert not decision.forecast_allowed, query


def test_blank_queries_rejected_by_contracts() -> None:
    for blank in ("   ", "\t\n ", "  a "):
        with pytest.raises(ValidationError):
            AnalysisRequest(query=blank)
        with pytest.raises(ValidationError):
            ParseRequest(query=blank)
