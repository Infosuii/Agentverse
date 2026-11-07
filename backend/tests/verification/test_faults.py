"""Every fault is caught by its target check; faults never touch their input. Owner: agent-5."""
from __future__ import annotations

import pytest

from jane_avenue.contracts import Analysis
from jane_avenue.verification import FAULT_TARGETS, FAULTS, verify
from jane_avenue.verification.checks import ALL_CHECKS, meta_of

BRIEF_M1_FAULTS = {"unverified_quote", "orphan_evidence", "tampered_metric", "unsourced_assumption",
                   "out_of_scope_policy", "placeholder_data"}


def test_every_fault_has_a_target_and_every_check_has_a_fault() -> None:
    assert set(FAULTS) == set(FAULT_TARGETS)
    assert BRIEF_M1_FAULTS <= set(FAULTS)
    assert {meta_of(fn).check_id for fn in ALL_CHECKS} <= set(FAULT_TARGETS.values())


@pytest.mark.parametrize("name", sorted(FAULTS))
def test_fault_is_caught_by_its_target_check(name: str, clean_analysis: Analysis) -> None:
    target = FAULT_TARGETS[name]
    before = {c.check_id: c.status for c in verify(clean_analysis).checks}
    assert before[target] == "pass"

    faulty = FAULTS[name](clean_analysis)
    result = next(c for c in verify(faulty).checks if c.check_id == target)
    assert result.status == ("warn" if result.severity in ("warning", "info") else "fail"), result.detail
    assert result.detail


@pytest.mark.parametrize("name", sorted(FAULTS))
def test_fault_deep_copies_its_input(name: str, clean_analysis: Analysis) -> None:
    before = clean_analysis.model_dump()
    faulty = FAULTS[name](clean_analysis)
    assert faulty is not clean_analysis
    assert clean_analysis.model_dump() == before
    assert faulty.model_dump() != before


@pytest.mark.parametrize("name", ["out_of_scope_policy", "tampered_metric"])
def test_blocking_faults_withhold_the_forecast(name: str, clean_analysis: Analysis) -> None:
    report = verify(FAULTS[name](clean_analysis))
    assert report.overall == "forecast_withheld" and report.decline_reasons


def test_faults_explain_what_they_need(golden_analysis: Analysis) -> None:
    golden_analysis.research = None
    with pytest.raises(ValueError, match="research"):
        FAULTS["unverified_quote"](golden_analysis)
