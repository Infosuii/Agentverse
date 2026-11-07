"""Owner: agent-5. STUB: verification with SCOPE-001 and CALC-001 only (agent-1 M0). Agent-5 adds the catalogue."""
from __future__ import annotations

from collections import Counter

from ..contracts import Analysis, VerificationCheck, VerificationReport, utcnow
from ..data import registry
from ..engine.core import compute


def _scope_001(analysis: Analysis) -> VerificationCheck:
    ok = analysis.scope is not None and analysis.scope.forecast_allowed
    detail = "Policy is within the validated scope." if ok else "; ".join(
        analysis.scope.reasons if analysis.scope else ["Scope was not checked."])
    return VerificationCheck(check_id="SCOPE-001", category="scope", severity="blocking",
                             status="pass" if ok else "fail", title="Policy within validated scope",
                             detail=detail, method="rule")


def _calc_001(analysis: Analysis) -> VerificationCheck:
    base = dict(check_id="CALC-001", category="calculation", severity="blocking", method="recompute",
                title="Engine recompute matches the central scenario")
    sim = analysis.simulation
    if sim is None or not sim.scenarios or analysis.policy is None:
        return VerificationCheck(**base, status="skipped", detail="No simulation to recompute.")
    central = sim.scenarios[0].result
    out = compute(analysis.policy, central.parameters_used, registry.load_baseline())
    bad = []
    for m in central.metrics:
        for i, yv in enumerate(m.values):
            if abs(float(out.metrics[m.metric][0, i]) - yv.value) > 1e-9:
                bad.append(f"{m.metric}.{yv.fiscal_year}")
    if bad:
        return VerificationCheck(**base, status="fail", detail=f"{len(bad)} values differ on recompute.",
                                 affected_ids=bad)
    return VerificationCheck(**base, status="pass", detail="All central-scenario values reproduce to within 1e-9.")


def verify(analysis: Analysis) -> VerificationReport:
    checks = [_scope_001(analysis), _calc_001(analysis)]
    blocking_fail = [c for c in checks if c.severity == "blocking" and c.status == "fail"]
    if blocking_fail:
        overall = "forecast_withheld"
    elif any(c.status in ("warn", "fail") for c in checks):
        overall = "approved_with_warnings"
    else:
        overall = "approved"
    counts = dict(Counter(c.status for c in checks))
    return VerificationReport(
        overall=overall, forecast_allowed=not blocking_fail, checks=checks,  # type: ignore[arg-type]
        decline_reasons=[c.detail for c in blocking_fail],
        summary=f"{len(checks)} checks run (STUB catalogue): " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())),
        counts=counts, verified_at=utcnow(),
    )
