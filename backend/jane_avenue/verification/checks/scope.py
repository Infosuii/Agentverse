"""Scope checks SCOPE-001..003 (MASTER_PROMPT 9.7). Owner: agent-5."""
from __future__ import annotations

from ...contracts import Analysis
from ._base import Outcome, check, listing

RELIABLE_YEARS = 5
_LONG_RUN_METRICS = ("gdp_level_pct", "revenue_dynamic_gbp_bn")


@check("SCOPE-001", "scope", "blocking", "rule", "Policy within the validated scope")
def scope_001(analysis: Analysis) -> Outcome:
    scope = analysis.scope
    if scope is None:
        return Outcome("issue", "The policy was never checked against the validated scope.")
    if not scope.forecast_allowed:
        reasons = " ".join(scope.reasons) or "The scope gate refused this policy."
        return Outcome("issue", reasons)
    label = "fully supported" if scope.status == "supported" else "partially supported (see SCOPE-002)"
    return Outcome("pass", f"The policy is within the validated scope: {label}.")


@check("SCOPE-002", "scope", "warning", "rule", "Change and rate within the UK precedent range")
def scope_002(analysis: Analysis) -> Outcome:
    scope = analysis.scope
    if scope is None:
        return Outcome("skipped", "No scope decision to inspect.")
    if scope.warnings:
        return Outcome("issue", " ".join(scope.warnings))
    if scope.validated_min_rate_pct is not None and scope.validated_max_change_pp is not None:
        return Outcome("pass", f"The change and the proposed rate are within the UK precedent range "
                               f"({scope.validated_min_rate_pct:g}%-{scope.validated_max_rate_pct:g}%, changes up to "
                               f"{scope.validated_max_change_pp:g}pp).")
    return Outcome("pass", "The scope gate raised no range warnings.")


@check("SCOPE-003", "scope", "warning", "rule", "Horizon within the reliable 5-year window")
def scope_003(analysis: Analysis) -> Outcome:
    policy = analysis.policy
    if policy is None:
        return Outcome("skipped", "No parsed policy.")
    if policy.horizon_years <= RELIABLE_YEARS:
        return Outcome("pass", f"The {policy.horizon_years}-year horizon is within the {RELIABLE_YEARS}-year window.")
    late_years: list[str] = []
    if analysis.simulation and analysis.simulation.scenarios:
        late_years = analysis.simulation.scenarios[0].result.fiscal_years[RELIABLE_YEARS:]
    affected = [f"{m}.{fy}" for m in _LONG_RUN_METRICS for fy in late_years]
    years = f" ({listing(late_years)})" if late_years else ""
    return Outcome("issue", f"The {policy.horizon_years}-year horizon runs past year {RELIABLE_YEARS}: GDP and dynamic "
                            f"revenue results for later years{years} are unreliable.", affected)
