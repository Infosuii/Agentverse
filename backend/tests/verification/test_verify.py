"""Verification framework: decision rule, crash isolation, determinism, no mutation. Owner: agent-5."""
from __future__ import annotations

import pytest

from jane_avenue.contracts import Analysis, VerificationCheck
from jane_avenue.verification import build_report, full_verify, run_checks, verify
from jane_avenue.verification.checks import ALL_CHECKS, CATALOGUE, Outcome, check, meta_of

from .conftest import run_pipeline

VERIFY_IDS = ["SCOPE-001", "SCOPE-002", "SCOPE-003", "CITE-001", "CITE-002", "CITE-003", "EVID-001", "EVID-002",
              "EVID-003", "EVID-004", "CALC-001", "CALC-002", "CALC-003", "DATA-001", "DATA-002", "CAUSAL-001",
              "UNC-001"]
ALL_IDS = [*VERIFY_IDS, "REPORT-001"]


def _vc(check_id: str, severity: str, status: str) -> VerificationCheck:
    return VerificationCheck(check_id=check_id, category="scope", severity=severity, status=status,  # type: ignore[arg-type]
                             title=check_id, detail=f"{check_id} detail", method="rule")


def test_checks_run_in_catalogue_order() -> None:
    assert [meta_of(fn).check_id for fn in ALL_CHECKS] == VERIFY_IDS
    assert [meta_of(fn).check_id for fn in CATALOGUE] == ALL_IDS
    assert len(ALL_IDS) == 18


def test_golden_mock_analysis_has_no_blocking_failures(golden_analysis: Analysis) -> None:
    report = full_verify(golden_analysis)
    assert [c.check_id for c in report.checks] == ALL_IDS
    assert report.forecast_allowed and report.overall != "forecast_withheld"
    assert not [c for c in report.checks if c.severity == "blocking" and c.status == "fail"]
    # Honest about the M0 stubs: placeholders and mock evidence are surfaced as warnings.
    assert {c.check_id for c in report.checks if c.status == "warn"} >= {"DATA-001", "EVID-004"}


def test_clean_analysis_passes_every_check(clean_analysis: Analysis) -> None:
    report = full_verify(clean_analysis)
    expected = dict.fromkeys(ALL_IDS, "pass") | {"CITE-001": "skipped"}  # no re-fetch in mock mode
    assert {c.check_id: c.status for c in report.checks} == expected
    assert report.overall == "approved"
    assert report.summary == "18 checks: 17 passed, 0 warnings, 0 failed, 1 skipped. Forecast approved."


def test_out_of_scope_policy_is_withheld_end_to_end() -> None:
    a = run_pipeline("Raise corporation tax from 25% to 45%")
    assert a.verification is not None
    assert a.verification.overall == "forecast_withheld" and not a.verification.forecast_allowed
    assert a.scope is not None and a.verification.decline_reasons == [" ".join(a.scope.reasons)]
    statuses = {c.check_id: c.status for c in a.verification.checks}
    assert statuses["SCOPE-001"] == "fail"
    assert statuses["SCOPE-002"] == "skipped"  # never "within the precedent range" for a refused policy
    assert statuses["CALC-001"] == statuses["EVID-004"] == "skipped"


@pytest.mark.parametrize(("checks", "overall"), [
    ([("A", "blocking", "pass"), ("B", "error", "pass")], "approved"),
    ([("A", "blocking", "pass"), ("B", "warning", "warn")], "approved_with_warnings"),
    ([("A", "blocking", "pass"), ("B", "error", "fail")], "approved_with_warnings"),
    ([("A", "blocking", "fail"), ("B", "error", "pass")], "forecast_withheld"),
    ([("A", "blocking", "skipped"), ("B", "info", "pass")], "approved"),
])
def test_decision_rule(checks: list[tuple[str, str, str]], overall: str) -> None:
    report = build_report([_vc(*c) for c in checks])
    assert report.overall == overall
    assert report.forecast_allowed == (overall != "forecast_withheld")


def test_counts_summary_and_decline_reasons_are_deterministic() -> None:
    checks = [_vc("CALC-001", "blocking", "fail"), _vc("DATA-001", "warning", "warn"), _vc("X", "error", "skipped")]
    a, b = build_report(checks), build_report(checks)
    assert a.counts == b.counts == {"pass": 0, "warn": 1, "fail": 1, "skipped": 1}
    assert a.summary == b.summary == ("3 checks: 0 passed, 1 warnings, 1 failed, 1 skipped. Quantitative forecast "
                                      "withheld by 1 blocking failure (CALC-001).")
    assert a.decline_reasons == ["CALC-001 (CALC-001): CALC-001 detail"]


def test_a_crashing_check_is_skipped_not_raised(golden_analysis: Analysis) -> None:
    @check("TEST-001", "data", "blocking", "rule", "Always crashes")
    def boom(analysis: Analysis) -> Outcome:
        raise RuntimeError("kaboom")

    [result] = run_checks(golden_analysis, [boom])
    assert result.status == "skipped" and result.severity == "blocking"
    assert "RuntimeError: kaboom" in result.detail
    assert build_report([result]).overall == "approved"


def test_verify_never_mutates_the_analysis(golden_analysis: Analysis) -> None:
    before = golden_analysis.model_dump()
    verify(golden_analysis)
    assert golden_analysis.model_dump() == before
