"""Parsing and scope for tax/benefit measures and other fiscal policies (contract-change #93). Owner: agent-2."""
from __future__ import annotations

from datetime import date

import pytest

from jane_avenue.contracts import PolicySpec
from jane_avenue.policy import check_scope, parse_policy

TODAY = date(2026, 11, 8)


def _parse(q: str) -> PolicySpec:
    return parse_policy(q, today=TODAY, use_llm=False)


@pytest.mark.parametrize(("query", "measure", "old", "new"), [
    ("Raise VAT to 21%", "vat_standard_rate", 20, 21),
    ("Cut the basic rate of income tax by 1p", "income_tax_basic_rate", 20, 19),
    ("Raise the higher rate of income tax to 42%", "income_tax_higher_rate", 40, 42),
    ("Raise the additional rate to 50%", "income_tax_additional_rate", 45, 50),
    ("Raise the 45p rate to 50p", "income_tax_additional_rate", 45, 50),
    ("Cut employer NICs to 13.8%", "nics_employer_rate", 15, 13.8),
    ("Raise CGT higher rate to 28%", "cgt_higher_rate", 24, 28),
    ("Raise inheritance tax to 45%", "inheritance_tax_rate", 40, 45),
])
def test_rate_measures(query, measure, old, new):
    s = _parse(query)
    assert (s.policy_type, s.measure_id) == ("tax_measure", measure)
    assert (s.baseline_rate_pct, s.proposed_rate_pct) == (old, new)
    assert s.parse_method == "rules"


@pytest.mark.parametrize(("query", "measure", "old", "new"), [
    ("Raise the personal allowance to £13,570", "income_tax_personal_allowance", 12570, 13570),
    ("Cut fuel duty by 5p", "fuel_duty", 52.95, 47.95),
    ("Increase child benefit by £5 a week", "child_benefit", 27.05, 32.05),
    ("Raise alcohol duty by 10%", "alcohol_duty", 100, 110),
])
def test_value_measures(query, measure, old, new):
    s = _parse(query)
    assert (s.policy_type, s.measure_id) == ("tax_measure", measure)
    assert s.baseline_value == pytest.approx(old) and s.proposed_value == pytest.approx(new)
    assert s.value_unit


@pytest.mark.parametrize("query", [
    "Increase NHS spending by £10bn",
    "Raise the minimum wage to £15",
    "What happens if the UK raises the national living wage by 10%?",
    "Introduce a wealth tax of 1% on assets over £10m",
    "Abolish the two-child benefit cap",
    "Cut council tax for pensioners",
])
def test_other_fiscal_policies_are_research_only(query):
    s = _parse(query)
    assert s.policy_type == "fiscal_other", s
    assert s.raw_query == query and query in s.description
    d = check_scope(s)
    assert not d.forecast_allowed and d.status == "unsupported"
    assert any("research" in r.lower() for r in d.reasons)


def test_non_fiscal_request_is_unsupported():
    s = _parse("What is the best football team in London?")
    assert s.policy_type == "unsupported"


def test_corporation_tax_is_still_the_ct_model():
    s = _parse("Raise corporation tax from 25% to 28%")
    assert s.policy_type == "corporation_tax_main_rate" and s.measure_id is None


def test_measure_in_range_is_allowed_with_horizon_warning():
    d = check_scope(_parse("Raise VAT to 21% for 5 years"))
    assert d.forecast_allowed and d.status == "partially_supported"
    assert any("first 3 years" in w for w in d.warnings)


def test_measure_beyond_costed_point_warns_in_words():
    d = check_scope(_parse("Increase child benefit by £5 a week"))
    assert d.forecast_allowed
    assert any("£5 a week" in w and "£1 a week" in w for w in d.warnings)


def test_measure_beyond_hard_limit_is_declined():
    d = check_scope(_parse("Raise VAT to 40%"))
    assert not d.forecast_allowed
    assert any("far larger" in r and "5 percentage points" in r for r in d.reasons)


def test_measure_with_no_change_is_declined():
    s = _parse("Raise VAT to 21%").model_copy(update={"proposed_rate_pct": 20.0})
    d = check_scope(s)
    assert not d.forecast_allowed and any("unchanged" in r for r in d.reasons)


def test_unknown_measure_is_declined():
    s = _parse("Raise VAT to 21%").model_copy(update={"measure_id": "nope"})
    assert not check_scope(s).forecast_allowed


def test_mirrored_decrease_warns():
    d = check_scope(_parse("Cut VAT to 19%"))
    assert d.forecast_allowed and any("mirrors" in w for w in d.warnings)


def test_negative_measure_rates_and_values_are_declined():
    for q in ("Set VAT standard rate to -18%", "Set income tax basic rate to -21%", "Set income tax basic rate to -20p"):
        s = _parse(q)
        assert s.proposed_rate_pct is None
        assert not check_scope(s).forecast_allowed
    neg_val = PolicySpec(policy_type="tax_measure", measure_id="income_tax_personal_allowance",
                         baseline_value=500.0, proposed_value=-500.0, value_unit="£")
    d = check_scope(neg_val)
    assert not d.forecast_allowed and any("cannot be negative" in r for r in d.reasons)


# --- #94 review (agent-11) -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("query", "country"), [
    ("Raise VAT in France from 20% to 25%", "France"),
    ("Cut the US income tax top rate to 35%", "the US"),
    ("Should Ireland raise income tax to 50%?", "Ireland"),
])
def test_another_countrys_tax_is_refused(query, country):
    s = _parse(query)
    assert s.policy_type == "unsupported" and s.measure_id is None
    assert any(f"about {country}" in a for a in s.ambiguities)
    assert not check_scope(s).forecast_allowed


@pytest.mark.parametrize("query", ["Raise VAT to 25% like France", "Introduce a wealth tax like France"])
def test_a_comparison_with_another_country_is_still_uk_policy(query):
    s = _parse(query)
    assert s.policy_type in ("tax_measure", "fiscal_other")
    assert any("results are for the UK" in a for a in s.ambiguities)


def test_devolved_income_tax_is_research_only():
    s = _parse("Raise income tax in Scotland by 1p")
    assert s.policy_type == "fiscal_other" and s.measure_id is None
    assert any("devolved" in a for a in s.ambiguities)


def test_uk_income_tax_costing_states_its_coverage():
    d = check_scope(_parse("Cut the basic rate of income tax by 1p"))
    assert d.forecast_allowed
    assert any("England and Northern Ireland" in w for w in d.warnings)
    assert not any("England and Northern Ireland" in w for w in check_scope(_parse("Raise VAT to 21%")).warnings)


@pytest.mark.parametrize("query", ["How do I file my tax return?", "Increase funding for my startup",
                                   "Plan a budget for my wedding"])
def test_personal_questions_are_not_fiscal_policy(query):
    assert _parse(query).policy_type == "unsupported"


@pytest.mark.parametrize("query", ["Should we cut taxes?", "Increase funding for schools by £2bn",
                                   "Introduce a tax on sugary drinks"])
def test_generic_fiscal_words_count_with_a_public_object_or_policy_verb(query):
    assert _parse(query).policy_type == "fiscal_other"
