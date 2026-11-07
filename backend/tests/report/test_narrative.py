"""Unit tests for Gemini narrative report generation with MockLLM (agent-09 brief section 5.1). Owner: agent-9."""
from __future__ import annotations

import json
import re

from jane_avenue import contracts as c
from jane_avenue.llm import MockLLM
from jane_avenue.orchestrator import create_analysis, run_analysis
from jane_avenue.report import (
    NARRATIVE_HEADER,
    NarrativeDraft,
    build_narrative_input,
    generate_report,
    key_figures,
)
from jane_avenue.store import AnalysisStore
from jane_avenue.verification import check_report


def _build_completed_analysis() -> c.Analysis:
    store = AnalysisStore(":memory:")
    try:
        req = c.AnalysisRequest(
            query="What would happen if the UK increased corporation tax from 25% to 28%?",
            options=c.AnalysisOptions(monte_carlo_draws=200),
        )
        created = create_analysis(store, req)
        return run_analysis(store, created.analysis_id)
    finally:
        store.close()


def _valid_draft(source_id: str) -> NarrativeDraft:
    return NarrativeDraft(
        executive_summary=(
            f"Under these assumptions, raising the corporation tax main rate is estimated to yield "
            f"{{{{fig:rev_behav_central_y1}}}} in the first modelled year and {{{{fig:rev_behav_central_final}}}} "
            f"by the end of the horizon [{source_id}]."
        ),
        policy=(
            "The proposal increases the UK corporation tax main rate under the central policy specification."
        ),
        research=(
            f"Empirical literature [{source_id}] indicates that higher statutory rates are associated with "
            f"taxable profit shifting and user-cost investment adjustments. [AI interpretation] Behavioural "
            f"erosion moderates the mechanical static yield."
        ),
        precedents=(
            "Historical UK corporation tax reforms such as CT-MAIN-2023 were bundled with capital-allowance "
            "changes that confound simple outturn comparisons."
        ),
        modelled_impacts=(
            "Under the central scenario, static revenue is estimated at {{fig:rev_static_central_final}}, "
            "while behavioural revenue is estimated at {{fig:rev_behav_central_final}}. Business investment "
            "is estimated to change by {{fig:inv_pct_central_final}} and GDP level by {{fig:gdp_pct_central_final}}."
        ),
        uncertainty=(
            "Across the Monte Carlo parameter draws, final-year behavioural revenue spans {{fig:rev_behav_p5_final}} "
            "at p5 to {{fig:rev_behav_p95_final}} at p95 under these assumptions."
        ),
        verification=(
            "Independent verification checks passed with non-blocking warnings on placeholder baseline inputs."
        ),
        limitations=(
            "Model scenarios are conditional projections and do not constitute unconditional forecasts."
        ),
        caveats=[
            "Prototype assessment; not official HM Treasury or OBR analysis.",
            "Estimates are conditional on baseline assumptions.",
        ],
    )


def test_narrative_input_contains_no_raw_model_numbers():
    analysis = _build_completed_analysis()
    figs = key_figures(analysis)
    payload = build_narrative_input(analysis, figs)
    serialized = json.dumps(payload)

    for fig in figs:
        assert fig.display not in serialized
        assert str(round(fig.value, 2)) not in serialized

    fig_entries = payload["figures"]
    assert len(fig_entries) == len(figs)
    for entry in fig_entries:
        assert set(entry.keys()) == {"figure_id", "label", "direction", "magnitude_class", "evidence_class"}
        assert entry["direction"] in ("increase", "decrease", "none")
        assert entry["magnitude_class"] in ("small", "moderate", "large")
        assert not re.search(r"(?:^|\s)\d+", entry["label"]), f"Digit found in figure label: {entry['label']}"


def test_placeholder_substitution_and_citations_resolved():
    analysis = _build_completed_analysis()
    first_source = analysis.sources[0].source_id
    figs = {f.figure_id: f for f in key_figures(analysis)}

    mock_llm = MockLLM()
    mock_llm.register_structured(NARRATIVE_HEADER, lambda: _valid_draft(first_source))

    report = generate_report(analysis, llm_client=mock_llm)
    assert report.generated_by == "gemini"
    assert report.model is not None
    assert len(mock_llm.calls) == 1

    # Verify every {{fig:...}} placeholder was substituted with exact KeyFigure.display
    assert "{{fig:" not in report.executive_summary
    assert "{{fig:" not in report.markdown
    assert figs["rev_behav_central_y1"].display in report.executive_summary
    assert figs["rev_behav_central_final"].display in report.executive_summary

    # Verify [S#] / [D-...] was resolved into a numbered footnote reference [^1] and listed in References
    assert f"[{first_source}][^1]" in report.executive_summary
    ref_sec = next(s for s in report.sections if s.section_id == "references")
    assert f"1. **[^1] [{first_source}]**" in ref_sec.body_markdown

    # Verify check_report passes both REPORT-001 and CAUSAL-001
    vr = check_report(report, analysis)
    r001 = next(chk for chk in vr.checks if chk.check_id == "REPORT-001")
    c001 = next(chk for chk in vr.checks if chk.check_id == "CAUSAL-001")
    assert r001.status == "pass", r001.detail
    assert c001.status == "pass", c001.detail


def test_unknown_placeholder_rejected_and_falls_back_to_template():
    analysis = _build_completed_analysis()
    first_source = analysis.sources[0].source_id

    bad_draft = _valid_draft(first_source).model_copy(
        update={
            "executive_summary": (
                "Under these assumptions, revenue is estimated at {{fig:nonexistent_metric_xyz}}."
            )
        }
    )

    mock_llm = MockLLM()
    mock_llm.register_structured(NARRATIVE_HEADER, lambda: bad_draft)

    report = generate_report(analysis, llm_client=mock_llm)
    # Should have retried once (2 calls total) with offending placeholder quoted, then fallen back to template
    assert len(mock_llm.calls) == 2
    assert "nonexistent_metric_xyz" in mock_llm.calls[1][1]
    assert report.generated_by == "template"
    assert report.model is None
    assert "nonexistent_metric_xyz" not in report.markdown


def test_raw_digits_rejected_and_falls_back_to_template():
    analysis = _build_completed_analysis()
    first_source = analysis.sources[0].source_id

    bad_draft = _valid_draft(first_source).model_copy(
        update={
            "modelled_impacts": (
                "Under the central scenario, behavioural revenue is estimated at £42.7bn in the first year."
            )
        }
    )

    mock_llm = MockLLM()
    mock_llm.register_structured(NARRATIVE_HEADER, lambda: bad_draft)

    report = generate_report(analysis, llm_client=mock_llm)
    # Should have retried once (2 calls total) quoting the raw number "42.7", then fallen back to template
    assert len(mock_llm.calls) == 2
    assert "42.7" in mock_llm.calls[1][1]
    assert report.generated_by == "template"
    assert report.model is None
    assert "42.7" not in report.markdown


def test_retry_succeeds_when_second_attempt_fixes_violation():
    analysis = _build_completed_analysis()
    first_source = analysis.sources[0].source_id

    bad_draft = _valid_draft(first_source).model_copy(
        update={"executive_summary": "Revenue is estimated at £99.9bn without a placeholder."}
    )
    good_draft = _valid_draft(first_source)
    attempts = [bad_draft, good_draft]

    mock_llm = MockLLM()
    mock_llm.register_structured(NARRATIVE_HEADER, lambda: attempts.pop(0))

    report = generate_report(analysis, llm_client=mock_llm)
    assert len(mock_llm.calls) == 2
    assert "99.9" in mock_llm.calls[1][1]
    assert report.generated_by == "gemini"
    assert report.model is not None


def test_causal_language_rejected_by_check_report_and_falls_back_to_template():
    analysis = _build_completed_analysis()
    first_source = analysis.sources[0].source_id

    causal_draft = _valid_draft(first_source).model_copy(
        update={
            "executive_summary": (
                "Raising the corporation tax rate will cause a sharp reduction in business investment."
            )
        }
    )

    mock_llm = MockLLM()
    mock_llm.register_structured(NARRATIVE_HEADER, lambda: causal_draft)

    report = generate_report(analysis, llm_client=mock_llm)
    assert len(mock_llm.calls) == 2
    assert "CAUSAL-001" in mock_llm.calls[1][1]
    assert report.generated_by == "template"
    assert report.model is None

