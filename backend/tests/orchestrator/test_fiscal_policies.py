"""Every fiscal policy end to end in mock mode (contract-change #93). Owner: agent-2.

Taxes and benefits in HMRC's ready reckoner get modelled revenue with uncertainty; any other fiscal policy is
researched and reported with the forecast withheld. Corporation tax keeps its own model.
"""
from __future__ import annotations

from datetime import date

import pytest

from jane_avenue import contracts as c
from jane_avenue.orchestrator import create_analysis, run_analysis
from jane_avenue.research import cache
from jane_avenue.research.agent import default_questions, policy_area
from jane_avenue.store import AnalysisStore


@pytest.fixture
def store():
    s = AnalysisStore(":memory:")
    yield s
    s.close()


def _run(store, query: str) -> c.Analysis:
    req = c.AnalysisRequest(query=query, options=c.AnalysisOptions(monte_carlo_draws=200))
    return run_analysis(store, create_analysis(store, req).analysis_id)


def _check(a: c.Analysis, check_id: str):
    return next(ck for ck in a.verification.checks if ck.check_id == check_id)


@pytest.mark.parametrize(("query", "sign"), [
    ("Raise VAT to 21%", 1),
    ("Raise the personal allowance to £13,570", -1),
    ("Increase child benefit by £1 a week", -1),
    ("Cut fuel duty by 5p", -1),
])
def test_ready_reckoner_measures_are_modelled(store, query, sign):
    a = _run(store, query)
    assert a.status == "completed", a.error
    assert a.policy.policy_type == "tax_measure" and a.scope.forecast_allowed
    assert a.research is not None and a.simulation is not None
    assert a.verification.overall in ("approved", "approved_with_warnings"), a.verification.decline_reasons
    assert not a.report.forecast_withheld
    central = a.simulation.scenarios[0].result
    beh = next(mp for mp in central.metrics if mp.metric == "revenue_behavioural_gbp_bn")
    assert all((v.value > 0) == (sign > 0) for v in beh.values)
    assert not any(mp.metric.startswith(("business_investment", "gdp")) for mp in central.metrics)
    assert a.simulation.monte_carlo is not None
    assert _check(a, "CALC-002").status == "pass"
    assert _check(a, "CALC-003").status == "skipped"
    assert _check(a, "REPORT-001").status != "fail", _check(a, "REPORT-001").detail
    assert "corporation tax" not in a.report.executive_summary.lower()


def test_vat_report_names_the_measure_and_the_method(store):
    a = _run(store, "Raise VAT to 21%")
    assert "VAT standard rate" in a.report.executive_summary
    assert "ready reckoner" in a.report.markdown.lower() or "ready-reckoner" in a.report.markdown.lower()
    assert "user-cost-of-capital" not in a.report.markdown


@pytest.mark.parametrize("query", ["Increase NHS spending by £10bn", "Raise the minimum wage to £15"])
def test_other_fiscal_policies_are_researched_with_the_forecast_withheld(store, query):
    a = _run(store, query)
    assert a.status == "completed", a.error
    assert a.policy.policy_type == "fiscal_other"
    assert a.research is not None and a.research.evidence
    assert "corporation tax" not in a.research.summary.lower()
    assert a.simulation is None and a.report.forecast_withheld
    assert a.verification.overall == "forecast_withheld"
    assert "Empirical evidence from research" in a.report.executive_summary


def test_research_area_and_questions_follow_the_policy():
    vat = c.PolicySpec(policy_type="tax_measure", measure_id="vat_standard_rate", baseline_rate_pct=20,
                       proposed_rate_pct=21, effective_date=date(2027, 4, 1))
    assert policy_area(vat) == "UK VAT standard rate"
    assert all("corporation tax" not in q.lower() for q in default_questions(vat))
    other = c.PolicySpec(policy_type="fiscal_other", raw_query="Increase NHS spending")
    assert "corporation tax" not in policy_area(other).lower()


def test_cache_keys_separate_measures_but_keep_ct_keys():
    ct = c.PolicySpec(policy_type="corporation_tax_main_rate", baseline_rate_pct=25, proposed_rate_pct=28,
                      horizon_years=5)
    # The golden CT key is the hash of the original four fields only.
    assert cache.cache_key(ct) == cache.cache_key(ct.model_copy(update={"raw_query": "anything"}))
    a = c.PolicySpec(policy_type="tax_measure", measure_id="vat_standard_rate", baseline_rate_pct=20,
                     proposed_rate_pct=21)
    b = a.model_copy(update={"measure_id": "vat_reduced_rate"})
    assert cache.cache_key(a) != cache.cache_key(b)
    n1 = c.PolicySpec(policy_type="fiscal_other", raw_query="Increase NHS spending")
    n2 = c.PolicySpec(policy_type="fiscal_other", raw_query="Cut  defence spending")
    assert cache.cache_key(n1) != cache.cache_key(n2)
    assert cache.cache_key(n1) == cache.cache_key(n1.model_copy(update={"raw_query": "increase   NHS spending"}))
