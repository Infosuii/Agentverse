"""Precedents for every fiscal policy other than corporation tax (contract 1.2.0)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from jane_avenue import contracts as c
from jane_avenue.data import registry
from jane_avenue.orchestrator import create_analysis, run_analysis
from jane_avenue.policy.rules import parse_rules
from jane_avenue.precedents import find_precedents
from jane_avenue.precedents.fiscal import topic_key
from jane_avenue.store import AnalysisStore

TODAY = date(2026, 11, 8)
CURATED = registry._directory()


@pytest.fixture
def store():
    s = AnalysisStore(":memory:")
    yield s
    s.close()


def _spec(query: str) -> c.PolicySpec:
    return parse_rules(query, today=TODAY)


@pytest.mark.parametrize(("query", "key"), [
    ("Raise VAT from 20% to 21%", "vat_standard_rate"),
    ("Raise the personal allowance by £1,000", "income_tax_personal_allowance"),
    ("raise the minimum wage by 10%", "minimum_wage"),
    ("Increase NHS funding", "nhs"),
    ("Raise council tax by 5%", "council_tax"),
    ("Cut Universal Credit", "universal_credit"),
    ("Raise income tax in Scotland by 1p", "devolved_income_tax"),
    ("Should we cut taxes?", "overall_fiscal"),
])
def test_a_request_finds_its_policy(query, key):
    assert topic_key(_spec(query)) == key


def test_every_modelled_measure_has_a_topic_and_precedents():
    from jane_avenue.engine import reckoner

    topics = {t["policy_key"] for t in registry.load_fiscal_topics()}
    for measure_id in reckoner.measures():
        assert measure_id in topics
        assert registry.load_fiscal_changes(measure_id), measure_id


def test_rate_changes_chain_and_match_official_values():
    vat = [x for x in registry.load_fiscal_changes("vat_standard_rate") if x.kind == "rate_series"]
    assert [(x.old_rate_pct, x.new_rate_pct) for x in vat] == [
        (10, 8), (8, 15), (15, 17.5), (17.5, 15), (15, 17.5), (17.5, 20)]
    basic = [(x.old_rate_pct, x.new_rate_pct) for x in registry.load_fiscal_changes("income_tax_basic_rate") if x.kind == "rate_series"]
    assert basic == [(25, 24), (24, 23), (23, 22), (22, 20)]


def test_extrapolated_years_are_not_costings():
    vat_2011 = next(x for x in registry.load_fiscal_changes("vat_standard_rate") if x.effective_date == date(2011, 1, 4))
    assert {k.fiscal_year for k in vat_2011.official_costings} == {"2010-11", "2011-12", "2012-13", "2013-14", "2014-15"}
    assert vat_2011.official_costings[0].value_gbp_bn == pytest.approx(2.85)


def test_outturns_stop_at_the_last_actual_year():
    frame = pd.read_csv(CURATED / "fiscal_outturns.csv", keep_default_na=False)
    assert frame["fiscal_year"].max() <= "2025-26"
    assert (frame["value_gbp_bn"] != 0).all()


def test_only_changes_already_in_effect_are_matched():
    for query in ("Raise council tax by 5%", "Increase NHS funding", "Raise CGT from 24% to 25%"):
        for m in find_precedents(_spec(query), k=50).matches:
            assert m.change.effective_date <= date.today()


def test_a_sparse_record_cannot_score_highly():
    for m in find_precedents(_spec("Increase NHS funding"), k=50).matches:
        assert m.similarity < 0.9


def test_an_announced_cut_that_never_happened_is_flagged_and_has_no_outcomes():
    row = next(x for x in registry.load_fiscal_changes("income_tax_basic_rate") if x.title.startswith("Income Tax: reduce basic rate from 20%"))
    assert row.notes.startswith("Reversed:")
    assert row.observed_outcomes == []


def test_income_tax_changes_have_a_full_window_of_receipts():
    for change in registry.load_fiscal_changes("income_tax_basic_rate"):
        if change.kind == "rate_series":
            years = {o.fiscal_year for o in change.observed_outcomes if o.metric == "receipts_gbp_bn"}
            assert len(years) == 4, (change.effective_date, years)


def test_change_ids_are_unique():
    ids = pd.read_csv(CURATED / "fiscal_policy_changes.csv", keep_default_na=False)["change_id"]
    assert ids.is_unique


def test_no_history_says_so():
    result = find_precedents(_spec("Introduce a wealth tax"))
    assert result.policy_key == "wealth_tax" and result.matches == []
    assert "No UK measure" in result.summary


@pytest.mark.parametrize("query", ["Raise VAT from 20% to 21%", "Raise fuel duty by 5p", "raise the minimum wage by 10%",
                                   "Increase NHS funding", "Introduce a wealth tax", "Should we cut taxes?",
                                   "Raise the personal allowance by £1,000"])
def test_report_numbers_stay_traceable(store, query):
    req = c.AnalysisRequest(query=query, options=c.AnalysisOptions(monte_carlo_draws=200))
    analysis = run_analysis(store, create_analysis(store, req).analysis_id)
    assert next(k for k in analysis.verification.checks if k.check_id == "REPORT-001").status == "pass"


def test_corporation_tax_precedents_are_unchanged():
    result = find_precedents(_spec("What would happen if the UK increased corporation tax from 25% to 28%?"))
    assert result.method == "weighted-five-component-v1" and result.policy_key is None
    assert all(m.change.change_id.startswith("CT-MAIN-") for m in result.matches)
