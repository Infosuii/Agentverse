"""`verify(analysis) -> VerificationReport` (MASTER_PROMPT 9.7). Owner: agent-5.

Runs every registered check, isolates crashes (a crashing check is reported as `skipped`, never raised), then applies
the decision rule:

- any `blocking` check with status `fail` -> `forecast_withheld`;
- otherwise any `warn` or `fail` -> `approved_with_warnings`;
- otherwise `approved`.

`counts` and `summary` are deterministic functions of the checks. Verification never changes the analysis.

`check_report` adds REPORT-001 (and re-runs CAUSAL-001) once the report exists. The orchestrator calls it after report
generation, and agent-9 calls it before accepting a Gemini draft.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from ..contracts import Analysis, PolicyAssessment, VerificationCheck, VerificationReport, utcnow
from .checks import ALL_CHECKS, REPORT_CHECKS, CheckFn, meta_of
from .checks.causal import critic_model

log = logging.getLogger(__name__)

STATUSES = ("pass", "warn", "fail", "skipped")


def run_check(fn: CheckFn, analysis: Analysis) -> VerificationCheck:
    meta = meta_of(fn)
    try:
        return fn(analysis)
    except Exception as exc:  # one broken check must never break verification or the pipeline
        log.exception("verification check %s crashed", meta.check_id)
        return VerificationCheck(check_id=meta.check_id, category=meta.category, severity=meta.severity,
                                 status="skipped", title=meta.title, method=meta.method,
                                 detail=f"The check could not run: {type(exc).__name__}: {exc}"[:500])


def run_checks(analysis: Analysis, checks: Iterable[CheckFn] = ALL_CHECKS) -> list[VerificationCheck]:
    return [run_check(fn, analysis) for fn in checks]


def _decline_reason(c: VerificationCheck) -> str:
    return c.detail if c.check_id == "SCOPE-001" else f"{c.title} ({c.check_id}): {c.detail}"


def build_report(checks: list[VerificationCheck], *, critic_model: str | None = None) -> VerificationReport:
    blocking = [c for c in checks if c.severity == "blocking" and c.status == "fail"]
    if blocking:
        overall = "forecast_withheld"
    elif any(c.status in ("warn", "fail") for c in checks):
        overall = "approved_with_warnings"
    else:
        overall = "approved"
    counts = {s: sum(1 for c in checks if c.status == s) for s in STATUSES}
    summary = (f"{len(checks)} checks: {counts['pass']} passed, {counts['warn']} warnings, {counts['fail']} failed, "
               f"{counts['skipped']} skipped.")
    if blocking:
        summary += (f" Quantitative forecast withheld by {len(blocking)} blocking "
                    f"{'failure' if len(blocking) == 1 else 'failures'} ({', '.join(c.check_id for c in blocking)}).")
    elif overall == "approved_with_warnings":
        flagged = [c.check_id for c in checks if c.status in ("warn", "fail")]
        summary += f" Forecast shown with warnings ({', '.join(flagged)})."
    else:
        summary += " Forecast approved."
    return VerificationReport(overall=overall, forecast_allowed=not blocking, checks=checks,
                              decline_reasons=[_decline_reason(c) for c in blocking], summary=summary, counts=counts,
                              critic_model=critic_model, verified_at=utcnow())


def _critic(checks: list[VerificationCheck]) -> str | None:
    return critic_model() if any(c.method == "llm_critic" for c in checks) else None


def verify(analysis: Analysis) -> VerificationReport:
    checks = run_checks(analysis)
    return build_report(checks, critic_model=_critic(checks))


def check_report(report: PolicyAssessment, analysis: Analysis) -> VerificationReport:
    """Run REPORT-001 against a finished report and return the merged VerificationReport (overall recomputed).

    CAUSAL-001 is re-run as well, because the report prose did not exist when `verify` ran. The other checks are taken
    from `analysis.verification` (or run now if the analysis was never verified). Neither argument is modified.
    """
    with_report = analysis.model_copy(update={"report": report})
    previous = analysis.verification.checks if analysis.verification else run_checks(with_report)
    fresh = {c.check_id: c for c in run_checks(with_report, REPORT_CHECKS)}
    merged = [fresh.pop(c.check_id, c) for c in previous]
    merged += list(fresh.values())
    return build_report(merged, critic_model=_critic(merged))
