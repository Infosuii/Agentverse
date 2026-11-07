"""Every fault is caught by its target check; faults never touch their input. Owner: agent-5."""
from __future__ import annotations

import pytest

from jane_avenue.contracts import Analysis
from jane_avenue.verification import FAULT_TARGETS, FAULTS, full_verify
from jane_avenue.verification.checks import CATALOGUE, meta_of

BRIEF_FAULTS = {"fake_source_url", "unverified_quote", "orphan_evidence", "tampered_metric", "unsourced_assumption",
                "out_of_scope_policy", "placeholder_data", "causal_claim", "mislabelled_interval", "raw_number_in_report"}


def test_every_fault_has_a_target_and_every_check_has_a_fault() -> None:
    assert set(FAULTS) == set(FAULT_TARGETS)
    assert BRIEF_FAULTS <= set(FAULTS)
    assert {meta_of(fn).check_id for fn in CATALOGUE} == set(FAULT_TARGETS.values())  # all 18 checks covered


@pytest.mark.parametrize("name", sorted(FAULTS))
def test_fault_is_caught_by_its_target_check(name: str, clean_analysis: Analysis) -> None:
    target = FAULT_TARGETS[name]
    before = {c.check_id: c.status for c in full_verify(clean_analysis).checks}
    assert before[target] in ("pass", "skipped")

    faulty = FAULTS[name](clean_analysis)
    result = next(c for c in full_verify(faulty).checks if c.check_id == target)
    assert result.status == ("warn" if result.severity in ("warning", "info") else "fail"), result.detail
    assert result.detail


@pytest.mark.parametrize("name", sorted(FAULTS))
def test_fault_deep_copies_its_input(name: str, clean_analysis: Analysis) -> None:
    before = clean_analysis.model_dump()
    faulty = FAULTS[name](clean_analysis)
    assert faulty is not clean_analysis
    assert clean_analysis.model_dump() == before
    assert faulty.model_dump() != before


@pytest.mark.parametrize("name", ["out_of_scope_policy", "tampered_metric", "raw_number_in_report"])
def test_blocking_faults_withhold_the_forecast(name: str, clean_analysis: Analysis) -> None:
    report = full_verify(FAULTS[name](clean_analysis))
    assert report.overall == "forecast_withheld" and report.decline_reasons


def test_faults_explain_what_they_need(golden_analysis: Analysis) -> None:
    golden_analysis.research = None
    with pytest.raises(ValueError, match="research"):
        FAULTS["unverified_quote"](golden_analysis)
