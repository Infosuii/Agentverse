"""`check_scope(spec) -> ScopeDecision`: the scope gate (MASTER_PROMPT 9.1). Owner: agent-5.

The validated bounds come from `data.registry.load_policy_changes()`:
- the lowest and highest main rate among the old and new rates of every implemented UK precedent (reversed
  announcements are skipped), and
- the largest absolute single change.

The fallback constants below are used only when the registry has no main-rate precedents (or fails to load), and the
decision then says so in a warning.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..contracts import PolicySpec, ScopeDecision, fiscal_year_of
from ..data import registry

log = logging.getLogger(__name__)

# Hard limit of the validated model (MASTER_PROMPT 9.1): larger changes are refused, not just warned about.
MAX_CHANGE_PP = 15.0

# Fallback bounds, used only if the registry is empty: the UK main rate ranged 19%-52% over 1983-2023, and the
# largest single change was the 6pp rise from 19% to 25% in April 2023 (HMRC CT rate history).
FALLBACK_MIN_RATE_PCT = 19.0
FALLBACK_MAX_RATE_PCT = 52.0
FALLBACK_MAX_CHANGE_PP = 6.0


@dataclass(frozen=True)
class ValidatedBounds:
    min_rate_pct: float
    max_rate_pct: float
    max_change_pp: float
    n_precedents: int
    from_registry: bool


def validated_bounds() -> ValidatedBounds:
    """Bounds derived from the curated UK main-rate precedents, or the documented fallback if there are none."""
    try:
        # Reversed announcements (CT-MAIN-2020-REVERSED: 19% -> 17%, never implemented) are not rates the UK has had,
        # so they do not widen the validated range. Same rule as evaluation.backtest and precedents.match.
        changes = [c for c in registry.load_policy_changes("corporation_tax")
                   if c.policy_type == "corporation_tax_main_rate"
                   and "reversed" not in c.change_id.lower() and "reversed" not in c.notes.lower()]
    except Exception:  # the gate must still answer if the data layer is broken
        log.exception("could not load policy changes; using fallback scope bounds")
        changes = []
    if not changes:
        return ValidatedBounds(FALLBACK_MIN_RATE_PCT, FALLBACK_MAX_RATE_PCT, FALLBACK_MAX_CHANGE_PP, 0, False)
    rates = [r for c in changes for r in (c.old_rate_pct, c.new_rate_pct)]
    max_change = max(abs(c.new_rate_pct - c.old_rate_pct) for c in changes)
    return ValidatedBounds(min(rates), max(rates), round(max_change, 6), len(changes), True)


def _baseline_coverage_reasons(spec: PolicySpec) -> list[str]:
    """The modelled years must lie inside the baseline projection. Before its first year there is nothing to project
    from (the engine would silently reuse the first baseline year), and past its last year it would extrapolate without
    bound (a 25%->28% rise from 2099 came out at over £100bn a year). Years between the last official forecast and
    the end of the baseline are allowed and flagged by DATA-002.

    Reasons use calendar dates, not fiscal-year labels, so the report can repeat them (REPORT-001 allows the numbers
    of scope reasons but only the fiscal years the analysis models)."""
    assert spec.effective_date is not None
    try:
        years = [y.fiscal_year for y in registry.load_baseline().years]
    except Exception:  # the gate must still answer if the data layer is broken
        log.exception("could not load the baseline; skipping the baseline coverage check")
        return []
    if not years:
        return []
    first, last = min(int(y[:4]) for y in years), max(int(y[:4]) for y in years)
    window_first = int(fiscal_year_of(spec.effective_date)[:4])
    window_last = window_first + spec.horizon_years - 1
    when = f"{spec.effective_date.day} {spec.effective_date:%B %Y}"
    if window_first < first:
        return [f"The effective date of {when} is before the baseline data starts (April {first}). The model projects "
                "forward from the current baseline, so it cannot model past changes."]
    if window_last > last:
        return [f"A {spec.horizon_years}-year horizon from {when} runs past the end of the baseline data "
                f"(March {last + 1}), so there is no baseline to model against."]
    return []


def check_scope(spec: PolicySpec) -> ScopeDecision:
    bounds = validated_bounds()
    reasons: list[str] = []
    warnings: list[str] = []

    if spec.policy_type == "vat_standard_rate":
        reasons.append("VAT is not supported yet: this version models the UK corporation tax main rate only.")
    elif spec.policy_type == "unsupported":
        reasons.append("This request is not a UK corporation tax rate change, which is the only policy this version "
                       "can model.")
    elif spec.policy_type == "corporation_tax_small_profits_rate":
        warnings.append("The small profits rate is only partially supported: results apply main-rate behaviour to "
                        "small-company profits.")

    if spec.baseline_rate_pct is None or spec.proposed_rate_pct is None:
        missing = " and ".join(name for name, value in (("current", spec.baseline_rate_pct),
                                                        ("proposed", spec.proposed_rate_pct)) if value is None)
        reasons.append(f"The {missing} rate could not be determined, so there is nothing to model.")
    if spec.effective_date is None:
        reasons.append("An effective date is needed.")
    else:
        reasons.extend(_baseline_coverage_reasons(spec))

    change = spec.change_pp()
    if change is not None and spec.baseline_rate_pct is not None and spec.proposed_rate_pct is not None:
        size = abs(change)
        if change == 0:
            reasons.append(f"The proposed rate equals the current rate ({spec.proposed_rate_pct:g}%), so there is no "
                           "change to model.")
        elif size > MAX_CHANGE_PP:
            reasons.append(f"The proposed {size:g}pp change is far outside any UK precedent "
                           f"(limit {MAX_CHANGE_PP:g}pp).")
        elif not (0 < spec.baseline_rate_pct < 100 and 0 <= spec.proposed_rate_pct < 100):
            reasons.append("The model needs a current rate above 0% and rates below 100%.")
        else:
            if size > bounds.max_change_pp:
                warnings.append(f"The {size:g}pp change is larger than any UK precedent (largest "
                                f"{bounds.max_change_pp:g}pp), so the results are an extrapolation.")
            if not bounds.min_rate_pct <= spec.proposed_rate_pct <= bounds.max_rate_pct:
                warnings.append(f"The proposed rate of {spec.proposed_rate_pct:g}% is outside the historical range of "
                                f"UK main rates ({bounds.min_rate_pct:g}%-{bounds.max_rate_pct:g}%).")

    if not bounds.from_registry:
        warnings.append("No curated precedent data was available, so the validated bounds use built-in fallback "
                        "values.")

    status = "unsupported" if reasons else "partially_supported" if warnings else "supported"
    return ScopeDecision(
        status=status,
        forecast_allowed=status != "unsupported",
        reasons=reasons,
        warnings=warnings,
        validated_min_rate_pct=bounds.min_rate_pct,
        validated_max_rate_pct=bounds.max_rate_pct,
        validated_max_change_pp=bounds.max_change_pp,
    )
