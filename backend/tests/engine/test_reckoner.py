"""HMRC ready-reckoner engine for tax and benefit measures (contract-change #93). Owner: agent-2."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from jane_avenue.contracts import PolicySpec
from jane_avenue.engine import compute, default_parameters, reckoner, run_engine


def _pp(measure_id: str, old: float, new: float, horizon: int = 4) -> PolicySpec:
    return PolicySpec(policy_type="tax_measure", measure_id=measure_id, baseline_rate_pct=old, proposed_rate_pct=new,
                      effective_date=date(2027, 4, 1), horizon_years=horizon)


def _val(measure_id: str, old: float, new: float, horizon: int = 4) -> PolicySpec:
    return PolicySpec(policy_type="tax_measure", measure_id=measure_id, baseline_value=old, proposed_value=new,
                      effective_date=date(2027, 4, 1), horizon_years=horizon)


def test_every_measure_has_three_years_sources_and_a_costed_point():
    ms = reckoner.measures()
    assert len(ms) >= 15
    for m in ms.values():
        assert m.years == ("2026-27", "2027-28", "2028-29")
        assert m.up and m.source_ids and reckoner.RR_SOURCE_ID in m.source_ids
        assert 0 < m.largest_costed <= m.max_change


def test_interpolation_hits_costed_points_and_is_linear_between():
    pa = reckoner.get_measure("income_tax_personal_allowance")
    np.testing.assert_allclose(reckoner.official_effect_gbp_bn(pa, 100), [-0.81, -1.05, -1.0])
    np.testing.assert_allclose(reckoner.official_effect_gbp_bn(pa, 1257), [-10.0, -11.65, -11.5])
    mid = reckoner.official_effect_gbp_bn(pa, (100 + 1257) / 2)
    np.testing.assert_allclose(mid, [(-0.81 - 10.0) / 2, (-1.05 - 11.65) / 2, (-1.0 - 11.5) / 2])
    np.testing.assert_allclose(reckoner.official_effect_gbp_bn(pa, 50), [-0.405, -0.525, -0.5])  # through (0, 0)


def test_decreases_use_hmrc_rows_or_mirror_the_increase():
    vat = reckoner.get_measure("vat_standard_rate")
    np.testing.assert_allclose(reckoner.official_effect_gbp_bn(vat, -1), [-8.8, -9.2, -9.55])  # mirrored
    add = reckoner.get_measure("income_tax_additional_rate")
    np.testing.assert_allclose(reckoner.official_effect_gbp_bn(add, -1), [-0.175, -0.335, -0.3])  # HMRC cost row
    cb = reckoner.get_measure("child_benefit")
    np.testing.assert_allclose(reckoner.official_effect_gbp_bn(cb, 1), [-0.565, -0.575, -0.575])  # a cost
    np.testing.assert_allclose(reckoner.official_effect_gbp_bn(cb, -1), [0.565, 0.58, 0.565])


@pytest.mark.parametrize(("spec", "sign"), [
    (_pp("vat_standard_rate", 20, 21), 1),
    (_pp("vat_standard_rate", 20, 19), -1),
    (_val("income_tax_personal_allowance", 12570, 13570), -1),
    (_val("child_benefit", 27.05, 32.05), -1),
    (_pp("cgt_higher_rate", 24, 25), 0),  # the yield changes sign across years
    (_pp("vat_standard_rate", 20, 20), 0),
])
def test_expected_revenue_sign(spec, sign):
    assert reckoner.expected_revenue_sign(spec) == sign


def test_change_units():
    fuel = reckoner.get_measure("fuel_duty")
    assert reckoner.change_units(_val("fuel_duty", 52.95, 50.3025), fuel) == pytest.approx(-5.0)
    assert reckoner.change_units(_pp("fuel_duty", 20, 21), fuel) is None  # no values given
    vat = reckoner.get_measure("vat_standard_rate")
    assert reckoner.change_units(_pp("vat_standard_rate", 20, 22.5), vat) == pytest.approx(2.5)


def test_run_engine_uprates_with_gdp_and_repeats_the_third_year(baseline):
    spec = _pp("vat_standard_rate", 20, 21, horizon=4)
    res = run_engine(spec, default_parameters(spec), baseline)
    gdp = {y.fiscal_year: y.nominal_gdp_gbp_bn for y in baseline.years}
    beh = next(mp for mp in res.metrics if mp.metric == "revenue_behavioural_gbp_bn")
    assert [v.fiscal_year for v in beh.values] == ["2027-28", "2028-29", "2029-30", "2030-31"]
    expected = [8.8 * gdp["2027-28"] / gdp["2026-27"], 9.2 * gdp["2028-29"] / gdp["2027-28"],
                9.55 * gdp["2029-30"] / gdp["2028-29"], 9.55 * gdp["2030-31"] / gdp["2028-29"]]
    np.testing.assert_allclose([v.value for v in beh.values], expected)
    assert {mp.metric for mp in res.metrics} == set(reckoner.METRICS)  # no investment or GDP metrics
    ids = {s.step_id for s in res.calc_trace}
    assert {"rr.change", "rr.effect.2027-28", "rr.uprate.2027-28", "rev.static.2030-31",
            "rev.behavioural.2030-31", "rev.dynamic.2030-31"} <= ids
    assert res.model_version == reckoner.MODEL_VERSION


def test_costing_scale_moves_behavioural_but_not_static(baseline):
    spec = _pp("vat_standard_rate", 20, 21)
    lo = compute(spec, {reckoner.PARAMETER: 0.8}, baseline)
    hi = compute(spec, {reckoner.PARAMETER: 1.1}, baseline)
    np.testing.assert_allclose(lo.metrics["revenue_static_gbp_bn"], hi.metrics["revenue_static_gbp_bn"])
    np.testing.assert_allclose(hi.metrics["revenue_behavioural_gbp_bn"] / lo.metrics["revenue_behavioural_gbp_bn"],
                               1.1 / 0.8)


def test_default_parameters_widen_beyond_the_largest_costed_change():
    small = default_parameters(_pp("vat_standard_rate", 20, 21))[reckoner.PARAMETER]
    big = default_parameters(_pp("vat_standard_rate", 20, 23))[reckoner.PARAMETER]
    assert (small.low, small.value, small.high) == (0.8, 1.0, 1.1)
    assert big.low == 0.7 and big.high == 1.1 and "3 percentage points" in big.rationale


def test_fmt_change_puts_units_in_words():
    assert reckoner.fmt_change(5, "gbp_per_week") == "£5 a week"
    assert reckoner.fmt_change(1000, "gbp") == "£1,000"
    assert reckoner.fmt_change(2, "pp") == "2 percentage points"
    assert reckoner.fmt_change(5, "pct_of_rate") == "5% of the duty rate"


def test_unknown_measure_raises(baseline):
    with pytest.raises(ValueError, match="No ready-reckoner measure"):
        compute(_pp("not_a_measure", 1, 2), {reckoner.PARAMETER: 1.0}, baseline)
