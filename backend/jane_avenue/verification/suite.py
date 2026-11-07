"""Verifier evaluation hand-off for agent-10 (agent-5 brief M2.6). Owner: agent-5.

`run_fault_suite(analysis)` verifies the analysis as given (the clean case), then applies every fault in `FAULTS` and
verifies each faulty copy. A fault counts as detected when its target check flags (`warn` or `fail`) on the faulty
copy and that is new: the check passed or was skipped on the clean case, or it already flagged but now reports
something different. A fault is reported as not applicable (and left out of the counts) when it cannot be injected
into this analysis, or when its target already flags the clean case and the fault changes nothing it reports.

For a meaningful false-positive count, pass a genuinely clean analysis (no placeholders, verified evidence). On the
mock golden path the stub data correctly triggers DATA-001 and EVID-004, and those flags are counted.
"""
from __future__ import annotations

from ..contracts import Analysis, VerificationCheck, VerificationEval, VerificationReport
from .faults import FAULT_TARGETS, FAULTS
from .verify import check_report, verify

_FLAGGED = ("warn", "fail")


def full_verify(analysis: Analysis) -> VerificationReport:
    """`verify`, plus `check_report` when the analysis has a report. Ignores any stored verification."""
    fresh = verify(analysis)
    if analysis.report is None:
        return fresh
    return check_report(analysis.report, analysis.model_copy(update={"verification": fresh}))


def _detected(before: VerificationCheck | None, after: VerificationCheck | None) -> bool:
    if after is None or after.status not in _FLAGGED:
        return False
    if before is None or before.status not in _FLAGGED:
        return True
    return (after.status, after.detail, after.affected_ids) != (before.status, before.detail, before.affected_ids)


def run_fault_suite(analysis: Analysis) -> VerificationEval:
    clean = full_verify(analysis)
    clean_by_id = {c.check_id: c for c in clean.checks}
    flagged_clean = [c.check_id for c in clean.checks if c.status in _FLAGGED]

    by_fault: dict[str, bool] = {}
    not_applicable: list[str] = []
    for name, fault in FAULTS.items():
        try:
            faulty = fault(analysis)
        except ValueError as exc:
            not_applicable.append(f"{name} ({exc})")
            continue
        target = FAULT_TARGETS[name]
        before = clean_by_id.get(target)
        after = next((c for c in full_verify(faulty).checks if c.check_id == target), None)
        if before is not None and after is not None and before.status in _FLAGGED and \
                (after.status, after.detail, after.affected_ids) == (before.status, before.detail, before.affected_ids):
            not_applicable.append(f"{name} ({target} already flags the clean case)")
            continue
        by_fault[name] = _detected(before, after)

    missed = [name for name, ok in by_fault.items() if not ok]
    notes = [f"Clean case: {clean.overall}; flagged checks: {', '.join(flagged_clean) or 'none'}."]
    if missed:
        notes.append(f"Missed: {', '.join(missed)}.")
    if not_applicable:
        notes.append(f"Not applicable to this analysis: {'; '.join(not_applicable)}.")
    return VerificationEval(n_fault_cases=len(by_fault), detected=sum(by_fault.values()), n_clean_cases=1,
                            false_positives=len(flagged_clean), by_fault=by_fault, notes=" ".join(notes))
