"""Owner: agent-5. STUB: scope gate (agent-1 M0), following MASTER_PROMPT section 9.1. Agent-5 owns and refines it.

The validated bounds come from `data.registry.load_policy_changes()`, not hard-coded constants.
"""
from __future__ import annotations

from ..contracts import PolicySpec, ScopeDecision
from ..data import registry

MAX_CHANGE_PP = 15.0


def _validated_bounds() -> tuple[float | None, float | None, float | None]:
    changes = [c for c in registry.load_policy_changes("corporation_tax") if c.policy_type == "corporation_tax_main_rate"]
    if not changes:
        return None, None, None
    rates = [r for c in changes for r in (c.old_rate_pct, c.new_rate_pct)]
    return min(rates), max(rates), max(abs(c.new_rate_pct - c.old_rate_pct) for c in changes)


def check_scope(spec: PolicySpec) -> ScopeDecision:
    lo, hi, max_change = _validated_bounds()
    reasons: list[str] = []
    warnings: list[str] = []
    change = spec.change_pp()

    if spec.policy_type not in ("corporation_tax_main_rate", "corporation_tax_small_profits_rate"):
        reasons.append("Only the UK corporation tax main rate is supported in this version.")
    if spec.baseline_rate_pct is None or spec.proposed_rate_pct is None:
        reasons.append("Both the current and the proposed rate are needed.")
    if spec.effective_date is None:
        reasons.append("An effective date is needed.")
    if change is not None:
        if change == 0:
            reasons.append("The proposed rate equals the current rate, so there is no change to model.")
        elif abs(change) > MAX_CHANGE_PP:
            reasons.append(f"A change of {abs(change):g} percentage points exceeds the {MAX_CHANGE_PP:g}pp limit "
                           "of the validated model.")
        else:
            if max_change is not None and abs(change) > max_change:
                warnings.append(f"The change of {abs(change):g}pp is larger than any UK precedent "
                                f"(largest {max_change:g}pp).")
            if lo is not None and hi is not None and not lo <= spec.proposed_rate_pct <= hi:  # type: ignore[operator]
                warnings.append(f"The proposed rate is outside the historical range of main rates ({lo:g}%-{hi:g}%).")
    if spec.policy_type == "corporation_tax_small_profits_rate":
        warnings.append("The small profits rate is only partially supported: results use main-rate behaviour.")

    if reasons:
        status = "unsupported"
    elif warnings:
        status = "partially_supported"
    else:
        status = "supported"
    return ScopeDecision(status=status, forecast_allowed=status != "unsupported", reasons=reasons,  # type: ignore[arg-type]
                         warnings=warnings, validated_min_rate_pct=lo, validated_max_rate_pct=hi,
                         validated_max_change_pp=max_change)
