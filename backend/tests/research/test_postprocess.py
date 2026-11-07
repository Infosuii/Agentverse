"""Trust rules enforced in code (research/postprocess.py). Owner: agent-2."""
from __future__ import annotations

from datetime import UTC, date, datetime

from jane_avenue.contracts import (
    Confounder,
    Evidence,
    Interpretation,
    ParameterEvidence,
    PolicySpec,
    ResearchFindings,
    ResearchStep,
    Source,
)
from jane_avenue.engine import PARAMETER_NAMES
from jane_avenue.research.postprocess import postprocess, strip_new_numbers, value_in_quote

T = datetime(2026, 11, 7, tzinfo=UTC)
SPEC = PolicySpec(policy_type="corporation_tax_main_rate", tax="corporation_tax", baseline_rate_pct=25.0,
                  proposed_rate_pct=28.0, effective_date=date(2027, 4, 1), horizon_years=5)
GROUNDED = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA"
FETCHED = "https://www.gov.uk/ct-stats"


def _src(sid: str, url: str, access: str = "google_search") -> Source:
    return Source(source_id=sid, title=sid, url=url, publisher="p", access_method=access)  # type: ignore[arg-type]


def _ev(eid: str, sid: str, status: str = "verified", quote: str = "Receipts were GBP 82.3 billion.") -> Evidence:
    return Evidence(evidence_id=eid, source_id=sid, kind="quantitative", topic="revenue", claim="c", quote=quote,
                    verification_status=status)  # type: ignore[arg-type]


def _findings(**kw) -> ResearchFindings:
    base = dict(policy=SPEC, mode="live", summary="", started_at=T)
    base.update(kw)
    return ResearchFindings(**base)


def test_sources_must_come_from_grounding_or_a_fetch() -> None:
    f = _findings(sources=[_src("S1", GROUNDED), _src("S2", "https://invented.example/report"),
                           _src("S3", FETCHED, "url_fetch"), _src("S4", "https://obr.uk/", "fixture")],
                  evidence=[_ev("E1", "S2"), _ev("E2", "S3")])
    clean, notes = postprocess(f, allowed_urls={GROUNDED, FETCHED, "https://obr.uk/"},
                               parameter_names=PARAMETER_NAMES)
    assert [(s.source_id, s.url) for s in clean.sources] == [("S1", GROUNDED), ("S2", FETCHED)]
    # evidence on the dropped S2 is gone; evidence on S3 is renumbered with its source
    assert [(e.evidence_id, e.source_id) for e in clean.evidence] == [("E1", "S2")]
    assert any("S2" in n for n in notes) and any("Dropped evidence E1" in n for n in notes)


def test_ids_are_renumbered_densely_and_references_rewritten() -> None:
    f = _findings(
        sources=[_src("S1", "https://bad.example"), _src("S2", GROUNDED), _src("S3", FETCHED)],
        evidence=[_ev("E1", "S1"), _ev("E2", "S2"), _ev("E3", "S3")],
        summary="Receipts were GBP 82.3 billion [E2]. Unsupported [E1]. Both [E2, E3].",
        interpretations=[Interpretation(interpretation_id="I4", statement="Interpretation: see [E3].",
                                        supporting_evidence_ids=["E3", "E1"])],
        confounders=[Confounder(name="cycle", description="d", evidence_ids=["E1", "E3"])],
        trace=[ResearchStep(step_id=1, ts=T, kind="extract", title="t", detail="x" * 900,
                            source_ids=["S1", "S3"], evidence_ids=["E1", "E3"])])
    clean, _ = postprocess(f, allowed_urls={GROUNDED, FETCHED}, parameter_names=PARAMETER_NAMES)
    assert [s.source_id for s in clean.sources] == ["S1", "S2"]
    assert [(e.evidence_id, e.source_id) for e in clean.evidence] == [("E1", "S1"), ("E2", "S2")]
    assert clean.summary == "Receipts were GBP 82.3 billion [E1]. Unsupported. Both [E1, E2]."
    assert clean.interpretations[0].interpretation_id == "I1"
    assert clean.interpretations[0].supporting_evidence_ids == ["E2"]
    assert clean.interpretations[0].statement == "Interpretation: see [E2]."
    assert clean.confounders[0].evidence_ids == ["E2"]
    step = clean.trace[0]
    assert step.source_ids == ["S2"] and step.evidence_ids == ["E2"] and len(step.detail) == 500


def test_parameter_evidence_needs_a_known_name_and_non_failed_evidence() -> None:
    f = _findings(
        sources=[_src("S1", GROUNDED)],
        evidence=[_ev("E1", "S1"), _ev("E2", "S1", status="failed")],
        parameter_evidence=[
            ParameterEvidence(parameter="taxable_profit_elasticity", evidence_ids=["E1", "E2"]),
            ParameterEvidence(parameter="user_cost_elasticity", evidence_ids=["E2"]),
            ParameterEvidence(parameter="made_up_parameter", evidence_ids=["E1"]),
            ParameterEvidence(parameter="capital_share", evidence_ids=["E9"]),
        ])
    clean, notes = postprocess(f, allowed_urls={GROUNDED}, parameter_names=PARAMETER_NAMES)
    assert [(p.parameter, p.evidence_ids) for p in clean.parameter_evidence] == [("taxable_profit_elasticity", ["E1"])]
    assert len(clean.evidence) == 2  # failed evidence is kept, only excluded from parameter evidence
    assert len([n for n in notes if "parameter" in n]) == 3


def test_summary_sentences_with_new_numbers_are_removed() -> None:
    f = _findings(sources=[_src("S1", GROUNDED)], evidence=[_ev("E1", "S1")],
                  summary=("Receipts were GBP 82.3 billion [E1]. The rise from 25% to 28% over 5 years is analysed. "
                           "This will raise GBP 4.1 billion a year. Two studies agree."))
    clean, notes = postprocess(f, allowed_urls={GROUNDED}, parameter_names=PARAMETER_NAMES)
    assert clean.summary == ("Receipts were GBP 82.3 billion [E1]. The rise from 25% to 28% over 5 years is "
                             "analysed. Two studies agree.")
    assert any("summary" in n for n in notes)


def test_numbers_from_model_written_claims_or_failed_quotes_are_not_allowed() -> None:
    ev_claim = _ev("E1", "S1", quote="Receipts rose sharply.").model_copy(update={"claim": "Receipts rose 0.83%."})
    ev_failed = _ev("E2", "S1", status="failed", quote="Receipts were GBP 99.9 billion.")
    f = _findings(sources=[_src("S1", GROUNDED)], evidence=[ev_claim, ev_failed],
                  summary="Receipts rose 0.83% [E1]. They were GBP 99.9 billion [E2]. Receipts rose [E1].")
    clean, _ = postprocess(f, allowed_urls={GROUNDED}, parameter_names=PARAMETER_NAMES)
    assert clean.summary == "Receipts rose [E1]."


def test_strip_new_numbers_and_value_in_quote_helpers() -> None:
    text, removed = strip_new_numbers("A is 1,200 [E1]. B is 7.5.", {1200.0})
    assert text == "A is 1,200 [E1]." and removed == ["B is 7.5."]
    assert value_in_quote(17.2, "raised GBP 17.2bn")
    assert value_in_quote(17.2e9, "raised GBP 17.2bn")
    assert value_in_quote(0.25, "a rate of 25%")
    assert not value_in_quote(18.0, "raised GBP 17.2bn")
    assert not value_in_quote(1.0, None)


def test_interpretations_need_verified_support() -> None:
    f = _findings(sources=[_src("S1", GROUNDED)], evidence=[_ev("E1", "S1"), _ev("E2", "S1", status="failed")],
                  interpretations=[
                      Interpretation(interpretation_id="I1", statement="Interpretation: only failed support.",
                                     supporting_evidence_ids=["E2"]),
                      Interpretation(interpretation_id="I2", statement="Interpretation: mixed support.",
                                     supporting_evidence_ids=["E2", "E1"])])
    clean, notes = postprocess(f, allowed_urls={GROUNDED}, parameter_names=PARAMETER_NAMES)
    assert [(i.interpretation_id, i.supporting_evidence_ids) for i in clean.interpretations] == [("I1", ["E1"])]
    assert clean.interpretations[0].statement == "Interpretation: mixed support."
    assert any("I1" in n and "verified" in n for n in notes)
