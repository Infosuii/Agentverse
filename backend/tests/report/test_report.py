"""Tests for report key figures and template generation (MASTER_PROMPT 9.8). Owner: agent-9."""
from __future__ import annotations

import re

from jane_avenue import contracts as c
from jane_avenue.orchestrator import create_analysis, run_analysis
from jane_avenue.report import fmt_gbp_bn, fmt_pct, fmt_pp, generate_report, key_figures
from jane_avenue.store import AnalysisStore
from jane_avenue.verification import check_report


def _run_analysis(query: str, draws: int = 200) -> c.Analysis:
    store = AnalysisStore(":memory:")
    try:
        req = c.AnalysisRequest(query=query, options=c.AnalysisOptions(monte_carlo_draws=draws))
        created = create_analysis(store, req)
        return run_analysis(store, created.analysis_id)
    finally:
        store.close()


def test_formatting_helpers_match_frontend_rules():
    assert fmt_gbp_bn(3.1) == "£3.1bn"
    assert fmt_gbp_bn(-0.4) == "−£0.4bn"
    assert fmt_gbp_bn(0.0) == "£0.0bn"
    assert fmt_gbp_bn(-0.02) == "−£20m" and fmt_gbp_bn(0.0491) == "£49m"  # not "£0.0bn" (#94 review)
    assert fmt_gbp_bn(0.0001) == "£0.0bn" and fmt_gbp_bn(0.05) == "£0.1bn"
    assert fmt_pct(-0.05, 2) == "−0.05%"
    assert fmt_pct(25.0, 1) == "25.0%"
    assert fmt_pp(3) == "+3pp"
    assert fmt_pp(-2) == "−2pp"
    assert fmt_pp(1.5) == "+1.5pp"


def test_every_key_figure_equals_engine_value(demo_request):
    store = AnalysisStore(":memory:")
    try:
        analysis = run_analysis(store, create_analysis(store, demo_request).analysis_id)
    finally:
        store.close()

    assert analysis.report is not None
    assert not analysis.report.forecast_withheld
    figs = key_figures(analysis)
    assert figs == analysis.report.key_figures

    fig_by_id = {f.figure_id: f for f in figs}
    expected_ids = {
        "rev_behav_central_y1",
        "rev_behav_central_final",
        "rev_static_central_final",
        "inv_pct_central_final",
        "gdp_pct_central_final",
        "rev_behav_p5_final",
        "rev_behav_p95_final",
    }
    assert expected_ids <= set(fig_by_id)

    assert analysis.simulation is not None
    central = analysis.simulation.scenarios[0].result
    metrics_by_name = {m.metric: m for m in central.metrics}

    assert fig_by_id["rev_behav_central_y1"].value == metrics_by_name["revenue_behavioural_gbp_bn"].values[0].value
    assert fig_by_id["rev_behav_central_final"].value == metrics_by_name["revenue_behavioural_gbp_bn"].values[-1].value
    assert fig_by_id["rev_static_central_final"].value == metrics_by_name["revenue_static_gbp_bn"].values[-1].value
    assert fig_by_id["inv_pct_central_final"].value == metrics_by_name["business_investment_pct"].values[-1].value
    assert fig_by_id["gdp_pct_central_final"].value == metrics_by_name["gdp_level_pct"].values[-1].value

    assert analysis.simulation.monte_carlo is not None
    mc_rev = next(
        d for d in analysis.simulation.monte_carlo.distributions if d.metric == "revenue_behavioural_gbp_bn"
    )
    assert fig_by_id["rev_behav_p5_final"].value == mc_rev.bands[-1].p5
    assert fig_by_id["rev_behav_p95_final"].value == mc_rev.bands[-1].p95

    for fig in figs:
        if fig.evidence_class == "model_scenario":
            assert fig.calc_step_ids
            assert fig.display


def test_top_precedent_official_costing_included_when_present(demo_request):
    store = AnalysisStore(":memory:")
    try:
        analysis = run_analysis(store, create_analysis(store, demo_request).analysis_id)
    finally:
        store.close()

    assert analysis.precedents and analysis.precedents.matches
    src_id = analysis.sources[0].source_id
    costing = c.Costing(
        costing_body="OBR",
        fiscal_event="Spring Budget 2021",
        fiscal_year="2023-24",
        value_gbp_bn=11.9,
        includes_behavioural=True,
        source_id=src_id,
    )
    top_match = analysis.precedents.matches[0]
    updated_change = top_match.change.model_copy(update={"official_costings": [costing]})
    updated_match = top_match.model_copy(update={"change": updated_change})
    updated_prec = analysis.precedents.model_copy(
        update={"matches": [updated_match, *analysis.precedents.matches[1:]]}
    )
    analysis_with_costing = analysis.model_copy(update={"precedents": updated_prec})

    figs = key_figures(analysis_with_costing)
    cost_fig = next((f for f in figs if f.figure_id == "top_precedent_official_costing"), None)
    assert cost_fig is not None
    assert cost_fig.evidence_class == "official_costing"
    assert cost_fig.value == 11.9
    assert cost_fig.display == "£11.9bn"
    assert cost_fig.source_ids == [src_id]


def test_withheld_path_has_no_model_figures():
    analysis = _run_analysis("Raise corporation tax from 25% to 45%", draws=100)
    assert analysis.report is not None
    report = analysis.report
    assert report.forecast_withheld is True
    assert not [f for f in report.key_figures if f.evidence_class == "model_scenario"]

    section_ids = [s.section_id for s in report.sections]
    assert "research" in section_ids
    assert "precedents" in section_ids
    assert "modelled_impacts" in section_ids
    assert "withheld" in report.executive_summary.lower()
    assert "withheld" in report.markdown.lower()


def test_every_reference_resolves_to_analysis_sources(demo_request):
    store = AnalysisStore(":memory:")
    try:
        analysis = run_analysis(store, create_analysis(store, demo_request).analysis_id)
    finally:
        store.close()

    report = generate_report(analysis)
    valid_source_ids = {s.source_id for s in analysis.sources}
    assert valid_source_ids

    for fig in report.key_figures:
        for sid in fig.source_ids:
            assert sid in valid_source_ids, f"KeyFigure {fig.figure_id} source_id {sid} not in analysis.sources"

    for sec in report.sections:
        for sid in sec.source_ids:
            assert sid in valid_source_ids, f"Section {sec.section_id} source_id {sid} not in analysis.sources"

    ref_section = next(s for s in report.sections if s.section_id == "references")
    bracketed_ids = re.findall(r"\*\*\[([^\]]+)\]\*\*", ref_section.body_markdown)
    assert bracketed_ids
    for sid in bracketed_ids:
        assert sid in valid_source_ids


def test_template_has_all_nine_sections_and_full_markdown(demo_request):
    store = AnalysisStore(":memory:")
    try:
        analysis = run_analysis(store, create_analysis(store, demo_request).analysis_id)
    finally:
        store.close()

    report = generate_report(analysis)
    assert len(report.sections) == 9
    expected_headings = [
        "Executive summary",
        "Policy assessed",
        "Evidence from research",
        "Historical precedents",
        "Modelled impacts",
        "Uncertainty and sensitivity",
        "Verification findings",
        "Limitations and caveats",
        "References",
    ]
    assert [s.heading for s in report.sections] == expected_headings
    for heading in expected_headings:
        assert f"## {heading}" in report.markdown


def test_template_report_passes_report_001_and_causal_001(demo_request):
    store = AnalysisStore(":memory:")
    try:
        analysis = run_analysis(store, create_analysis(store, demo_request).analysis_id)
    finally:
        store.close()

    assert analysis.report is not None
    vr = check_report(analysis.report, analysis)
    r001 = next(chk for chk in vr.checks if chk.check_id == "REPORT-001")
    c001 = next(chk for chk in vr.checks if chk.check_id == "CAUSAL-001")
    assert r001.status == "pass", r001.detail
    assert c001.status == "pass", c001.detail

    withheld = _run_analysis("Raise corporation tax from 25% to 45%", draws=100)
    assert withheld.report is not None
    vr_w = check_report(withheld.report, withheld)
    r001_w = next(chk for chk in vr_w.checks if chk.check_id == "REPORT-001")
    c001_w = next(chk for chk in vr_w.checks if chk.check_id == "CAUSAL-001")
    assert r001_w.status == "pass", r001_w.detail
    assert c001_w.status == "pass", c001_w.detail

