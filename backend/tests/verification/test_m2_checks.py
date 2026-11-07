"""M2 checks: CITE-001, EVID-002/003, UNC-001, CAUSAL-001, REPORT-001, check_report, run_fault_suite.
Offline: fetches and the Gemini critic are stubbed. Owner: agent-5."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from jane_avenue.contracts import Analysis, KeyFigure, ParameterEvidence, ReportSection
from jane_avenue.llm import LLMUnavailable, MockLLM
from jane_avenue.verification import FAULTS, check_report, full_verify, run_fault_suite, verify
from jane_avenue.verification.checks import causal, citation
from jane_avenue.verification.checks.causal import causal_001
from jane_avenue.verification.checks.citation import cite_001, url_problem
from jane_avenue.verification.checks.evidence import evid_002, evid_003
from jane_avenue.verification.checks.report import report_001
from jane_avenue.verification.checks.uncertainty import claims_prediction_interval, unc_001
from jane_avenue.verification.faults import untraceable_number

from .conftest import run_pipeline

# ------------------------------------------------------------------------------------------------------ CITE-001


@pytest.mark.parametrize(("url", "ok"), [
    ("https://obr.uk/efo/", True), ("https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA", True),
    ("ftp://obr.uk/file", False), ("https://localhost/x", False), ("https://obr", False),
    ("https://docs.example.com/a", False), ("https://www.gov.uk.fake.invalid/doc", False), ("https://a b.uk", False),
    ("", False),
])
def test_url_problem(url: str, ok: bool) -> None:
    assert (url_problem(url) is None) == ok


def test_cite_001_fetches_unverified_urls_in_live_mode(clean_analysis: Analysis,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    clean_analysis.mode = "live"
    clean_analysis.sources[0].url_verified = False
    fetched: list[str] = []
    monkeypatch.setattr(citation, "FETCH", lambda url: fetched.append(url) or True)
    assert cite_001(clean_analysis).status == "pass"
    assert fetched == [clean_analysis.sources[0].url]  # verified URLs are not re-fetched

    monkeypatch.setattr(citation, "FETCH", lambda url: False)
    result = cite_001(clean_analysis)
    assert result.status == "fail" and result.affected_ids == [clean_analysis.sources[0].source_id]


def _client(routes: dict[str, httpx.Response]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(f"{request.method} {request.url}", httpx.Response(404))
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(citation, "RESOLVE", lambda host: ["10.0.0.5"] if host == "intranet.corp.uk" else ["93.184.216.34"])


def test_fetch_ok_follows_safe_redirects_and_falls_back_to_get(public_dns: None) -> None:
    client = _client({
        "HEAD https://obr.uk/a": httpx.Response(301, headers={"location": "/b"}),
        "HEAD https://obr.uk/b": httpx.Response(405),
        "GET https://obr.uk/a": httpx.Response(301, headers={"location": "/b"}),
        "GET https://obr.uk/b": httpx.Response(200),
    })
    assert citation.fetch_ok("https://obr.uk/a", client=client)


@pytest.mark.parametrize("target", ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8000/",
                                    "https://intranet.corp.uk/secret", "http://printer.local/"])
def test_fetch_ok_refuses_redirects_to_non_public_addresses(public_dns: None, target: str) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "obr.uk":
            return httpx.Response(302, headers={"location": target})
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    assert not citation.fetch_ok("https://obr.uk/report", client=client)
    assert all("obr.uk" in url for url in requested)  # the private target is never requested


def test_fetch_ok_stops_after_too_many_redirects(public_dns: None) -> None:
    client = _client({f"HEAD https://obr.uk/{i}": httpx.Response(302, headers={"location": f"/{i + 1}"})
                      for i in range(10)})
    assert not citation.fetch_ok("https://obr.uk/0", client=client)


def test_cite_001_only_requires_verification_for_cited_sources(clean_analysis: Analysis,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    clean_analysis.mode = "live"
    grounding = clean_analysis.sources[0].model_copy(update={
        "source_id": "S7", "url_verified": False, "access_method": "google_search",
        "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/XYZ"})
    clean_analysis.sources.append(grounding)
    monkeypatch.setattr(citation, "FETCH", lambda url: pytest.fail("uncited search results are not re-fetched"))
    result = cite_001(clean_analysis)
    assert result.status == "pass" and "1 uncited search result was not fetched" in result.detail

    assert clean_analysis.research is not None
    clean_analysis.research.evidence[0].source_id = "S7"  # now it is cited, so it must verify
    monkeypatch.setattr(citation, "FETCH", lambda url: False)
    assert cite_001(clean_analysis).affected_ids == ["S7"]


def test_cite_001_fetches_at_most_ten(clean_analysis: Analysis, monkeypatch: pytest.MonkeyPatch) -> None:
    clean_analysis.mode = "live"
    template = clean_analysis.sources[0]
    clean_analysis.sources = [template.model_copy(update={"source_id": f"S{i}", "url_verified": False})
                              for i in range(1, 13)]
    assert clean_analysis.research is not None
    clean_analysis.research.evidence = [clean_analysis.research.evidence[0].model_copy(
        update={"evidence_id": f"E{i}", "source_id": f"S{i}"}) for i in range(1, 13)]
    calls: list[str] = []
    monkeypatch.setattr(citation, "FETCH", lambda url: calls.append(url) or True)
    result = cite_001(clean_analysis)
    assert len(calls) == 10 and result.status == "fail" and result.affected_ids == ["S11", "S12"]


def test_cite_001_in_cached_mode_requires_recorded_verification(clean_analysis: Analysis) -> None:
    clean_analysis.mode = "cached"
    assert cite_001(clean_analysis).status == "pass"
    clean_analysis.sources[1].url_verified = False  # S2 is cited by E2
    assert cite_001(clean_analysis).status == "fail"


def test_cite_001_never_fetches_in_mock_mode(clean_analysis: Analysis, monkeypatch: pytest.MonkeyPatch) -> None:
    clean_analysis.sources[0].url_verified = False
    monkeypatch.setattr(citation, "FETCH", lambda url: pytest.fail("fetched in mock mode"))
    result = cite_001(clean_analysis)
    assert result.status == "skipped" and "mock mode" in result.detail


# ------------------------------------------------------------------------------------------------- EVID-002/003


def test_evid_002_passes_when_the_assumption_is_inside_verified_evidence(clean_analysis: Analysis) -> None:
    assert clean_analysis.research is not None
    clean_analysis.research.parameter_evidence = [ParameterEvidence(
        parameter="taxable_profit_elasticity", low=0.05, high=0.5, evidence_ids=["E2"])]
    result = evid_002(clean_analysis)
    assert result.status == "pass" and "taxable_profit_elasticity" in result.detail


def test_evid_002_ignores_unverified_evidence(clean_analysis: Analysis) -> None:
    out_of_range = FAULTS["evidence_out_of_range"](clean_analysis)
    assert out_of_range.research is not None
    for e in out_of_range.research.evidence:
        e.verification_status = "unverified"
    assert evid_002(out_of_range).status == "pass"


def test_evid_003_counter_evidence_on_an_unsupported_topic_passes(clean_analysis: Analysis) -> None:
    faulty = FAULTS["contradicting_evidence"](clean_analysis)
    assert faulty.research is not None
    faulty.research.evidence[-1].topic = "distribution"
    assert evid_003(faulty).status == "pass"


# ------------------------------------------------------------------------------------------------------ UNC-001


@pytest.mark.parametrize(("text", "claims"), [
    ("assumption-driven ranges, not statistical prediction intervals; exclude model and data uncertainty", False),
    ("These are 90% prediction intervals.", True),
    ("Shown as a prediction interval rather than a range.", True),
    ("This is an assumption range rather than a prediction interval.", False),
    ("", False),
])
def test_claims_prediction_interval(text: str, claims: bool) -> None:
    assert claims_prediction_interval(text) == claims


def test_unc_001_accepts_calibrated_empirical_intervals(clean_analysis: Analysis) -> None:
    sim = clean_analysis.simulation
    assert sim is not None and sim.monte_carlo is not None
    mc = sim.monte_carlo
    mc.interval_kind = "empirical_prediction_interval"
    mc.empirical_interval = mc.distributions[0].bands
    mc.empirical_calibration_note = "n=12 out-of-sample errors; observed 90% coverage 83%."
    assert unc_001(clean_analysis).status == "pass"


def test_unc_001_flags_prediction_interval_wording_on_assumption_ranges(clean_analysis: Analysis) -> None:
    assert clean_analysis.simulation is not None
    clean_analysis.simulation.warnings.append("Bands are 90% prediction intervals.")
    result = unc_001(clean_analysis)
    index = len(clean_analysis.simulation.warnings) - 1
    assert result.status == "fail" and result.affected_ids == [f"simulation.warning.{index}"]


# --------------------------------------------------------------------------------------------------- CAUSAL-001


def test_causal_rule_pass_accepts_referenced_and_hedged_sentences(clean_analysis: Analysis) -> None:
    assert clean_analysis.research is not None
    clean_analysis.research.summary = ("The 2023 rise led to higher receipts [E1]. Behavioural revenue is estimated "
                                       "to be lower than static revenue under these assumptions.")
    assert causal_001(clean_analysis).status == "pass"


def _critic(monkeypatch: pytest.MonkeyPatch, answer: Any) -> MockLLM:
    mock = MockLLM()
    mock.register_structured(causal.CRITIC_HEADER, answer if callable(answer) else lambda: answer)
    monkeypatch.setattr(causal, "get_llm", lambda: mock)
    return mock


def test_live_critic_flags_and_sets_critic_model(clean_analysis: Analysis, monkeypatch: pytest.MonkeyPatch) -> None:
    assert clean_analysis.research is not None
    clean_analysis.mode = "live"
    clean_analysis.research.summary = "Higher rates make firms invest less."
    _critic(monkeypatch, {"findings": [
        {"text": "Higher rates make firms invest less.", "issue": "causal, no evidence", "severity": "medium"},
        {"text": "A sentence that is not in the prose.", "issue": "hallucinated", "severity": "high"},
    ]})
    result = causal_001(clean_analysis)
    assert result.method == "llm_critic" and result.status == "warn"
    assert "invest less" in result.detail and "not in the prose" not in result.detail
    report = verify(clean_analysis)
    assert report.critic_model == causal.critic_model()


def test_live_critic_unavailable_falls_back_to_rules(clean_analysis: Analysis,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    clean_analysis.mode = "live"

    def unavailable() -> Any:
        raise LLMUnavailable("quota")

    _critic(monkeypatch, unavailable)
    result = causal_001(clean_analysis)
    assert result.method == "rule" and result.status == "pass" and "critic unavailable" in result.detail
    assert verify(clean_analysis).critic_model is None


def test_critic_never_runs_in_mock_mode(clean_analysis: Analysis, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = _critic(monkeypatch, {"findings": []})
    causal_001(clean_analysis)
    assert getattr(mock, "calls", []) == []


# --------------------------------------------------------------------------------------------------- REPORT-001


def _report_with(analysis: Analysis, body: str, figures: list[KeyFigure] | None = None) -> Analysis:
    assert analysis.report is not None
    a = analysis.model_copy(deep=True)
    a.report.sections = [ReportSection(section_id="impacts", heading="Modelled impacts", body_markdown=body)]  # type: ignore[union-attr]
    a.report.key_figures = figures or []  # type: ignore[union-attr]
    return a


FIG = KeyFigure(figure_id="rev_y1", label="Behavioural revenue, 2027-28", value=3.14, unit="£bn", display="£3.1bn",
                evidence_class="model_scenario", fiscal_year="2027-28")


@pytest.mark.parametrize(("body", "ok"), [
    ("Behavioural revenue is estimated at £3.1bn in 2027-28.", True),                 # key figure + modelled year
    ("Raising the rate from 25% to 28% from 1 April 2027 is a 3 point rise.", True),  # policy numbers
    ("The OBR costed the 2023 rise at around £12bn a year [E1].", True),              # cited evidence value
    ("The OBR costed the 2023 rise at around £12bn a year.", False),                  # same number, no citation
    ("1. Revenue rises under these assumptions (see CALC-001 and p95).", True),       # numbering, IDs, percentiles
    ("Receipts would rise by £{X}bn.", False),                                        # invented number
    ("Revenue in 2041-42 is uncertain.", False),                                      # fiscal year not modelled
    ("Revenue is {{fig:missing}} in the first year.", False),                         # unsubstituted placeholder
    ("By Year 3 (t+2) the effect fades; see CT-MAIN-1983 and Tier 1 sources at https://obr.uk/efo2026/.", True),
    ("Results use 200 Monte Carlo draws.", True),                                      # n_draws from the fixture
])
def test_report_001_whitelist(clean_analysis: Analysis, body: str, ok: bool) -> None:
    body = body.replace("{X}", untraceable_number(clean_analysis))
    result = report_001(_report_with(clean_analysis, body, [FIG]))
    assert result.status == ("pass" if ok else "fail"), result.detail


def test_report_001_accepts_rounded_scenario_values(clean_analysis: Analysis) -> None:
    assert clean_analysis.simulation is not None
    static = next(m for m in clean_analysis.simulation.scenarios[0].result.metrics
                  if m.metric == "revenue_static_gbp_bn")
    body = f"Static revenue is about £{static.values[0].value:.1f}bn in the first year."
    assert report_001(_report_with(clean_analysis, body)).status == "pass"


def test_report_001_skips_the_references_section(clean_analysis: Analysis) -> None:
    a = _report_with(clean_analysis, "No numbers here.")
    assert a.report is not None
    a.report.sections.append(ReportSection(section_id="references", heading="9. References",
                                           body_markdown="[1] OBR, accessed 7 November 2026, https://obr.uk/x"))
    assert report_001(a).status == "pass"


def test_report_001_lists_offending_snippets(clean_analysis: Analysis) -> None:
    x, y = untraceable_number(clean_analysis), untraceable_number(clean_analysis, 2)
    result = report_001(_report_with(clean_analysis, f"Receipts would rise by £{x}bn. Costs fall by {y}%."))
    assert result.affected_ids == ["section.impacts"]
    assert f"\"{x}\"" in result.detail and f"\"{y}\"" in result.detail


# --------------------------------------------------------------------------------- check_report and fault suite


def test_check_report_merges_and_recomputes_without_mutating(clean_analysis: Analysis) -> None:
    clean_analysis.verification = verify(clean_analysis)
    assert clean_analysis.report is not None
    before = clean_analysis.model_dump()
    bad = FAULTS["raw_number_in_report"](clean_analysis).report
    assert bad is not None
    merged = check_report(bad, clean_analysis)
    assert [c.check_id for c in merged.checks][-1] == "REPORT-001"
    assert len(merged.checks) == 18 and merged.overall == "forecast_withheld"
    assert any("REPORT-001" in r for r in merged.decline_reasons)
    assert clean_analysis.model_dump() == before


def test_pipeline_runs_check_report_after_the_report(golden_analysis: Analysis) -> None:
    assert golden_analysis.verification is not None
    ids = [c.check_id for c in golden_analysis.verification.checks]
    assert len(ids) == 18 and ids[-1] == "REPORT-001"
    assert golden_analysis.verification.forecast_allowed


def test_withheld_report_is_not_blocked_by_its_own_decline_reasons() -> None:
    a = run_pipeline("Raise corporation tax from 25% to 45%")
    assert a.verification is not None
    assert {c.check_id: c.status for c in a.verification.checks}["REPORT-001"] == "pass"


def test_fault_suite_detects_every_fault_on_a_clean_analysis(clean_analysis: Analysis) -> None:
    result = run_fault_suite(clean_analysis)
    assert result.n_fault_cases == 18 and result.detected == 18, result.notes
    assert result.n_clean_cases == 1 and result.false_positives == 0
    assert all(result.by_fault.values())


def test_fault_suite_on_the_mock_golden_path_reports_honestly(golden_analysis: Analysis) -> None:
    result = run_fault_suite(golden_analysis)
    assert result.false_positives >= 1 and "DATA-001" in result.notes  # stub placeholders are real flags
    assert "Not applicable" in result.notes  # the stub research has no quantitative evidence to corrupt
    assert "already flags the clean case" in result.notes  # DATA-001 flags the stub placeholders anyway
    assert result.detected == result.n_fault_cases, result.notes
    assert full_verify(golden_analysis).forecast_allowed


@pytest.mark.parametrize(("token", "ok"), [("12.01", True), ("12.0", True), ("12", False), ("12.006584", True),
                                           ("11.9", False)])
def test_scenario_values_round_only_to_written_decimals(token: str, ok: bool) -> None:
    from jane_avenue.verification.checks.report import _close_to_model

    assert _close_to_model(token, 12.006584) == ok


def test_report_001_reads_spelled_out_numbers_in_cited_quotes(clean_analysis: Analysis) -> None:
    assert clean_analysis.research is not None
    clean_analysis.research.evidence[0].quote = "Around ten per cent of the cost is recovered in receipts over time."
    ok = "Expansion recovers around 10 per cent of the cost in receipts [E1]."
    assert report_001(_report_with(clean_analysis, ok)).status == "pass"
    uncited = "Expansion recovers around 10 per cent of the cost in receipts."
    assert report_001(_report_with(clean_analysis, uncited)).status == "fail"


@pytest.mark.parametrize(("body", "ok"), [
    ("Three studies and 2 fiscal events support this.", True),
    ("Research covered 9 official sources.", True),
    ("Research covered 12 official sources.", False),   # above the small-count limit
    ("Receipts rose by 9 per cent.", False),             # a quantity, not a count
])
def test_report_001_small_counts(clean_analysis: Analysis, body: str, ok: bool) -> None:
    assert report_001(_report_with(clean_analysis, body)).status == ("pass" if ok else "fail")


def test_report_001_scans_the_downloadable_markdown(clean_analysis: Analysis) -> None:
    a = _report_with(clean_analysis, "No numbers here.")
    assert a.report is not None
    x = untraceable_number(clean_analysis)
    a.report.markdown = (f"# Assessment\n\n## Modelled impacts\n\nReceipts rise by £{x}bn.\n\n"
                         "## References\n\n[1] OBR, accessed 7 November 2026, https://obr.uk/efo\n")
    result = report_001(a)
    assert result.status == "fail" and result.affected_ids == ["markdown:Modelled impacts"]
    assert "accessed" not in result.detail  # the references section is not checked


def test_report_001_does_not_double_report_the_markdown_copy(clean_analysis: Analysis) -> None:
    x = untraceable_number(clean_analysis)
    a = _report_with(clean_analysis, f"Receipts rise by £{x}bn.")
    assert a.report is not None
    a.report.markdown = f"# Assessment\n\n## Modelled impacts\n\nReceipts rise by £{x}bn.\n"
    assert report_001(a).affected_ids == ["section.impacts"]
