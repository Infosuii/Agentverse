"""Fault-injection library for testing and evaluating the verifier (agent-5 brief M1.5). Owner: agent-5.

Each fault takes an `Analysis` and returns a deep copy with exactly one realistic defect injected. The input is never
modified. `FAULT_TARGETS` names the check that must catch each fault. Agent-10's verifier evaluation applies every
fault to a clean analysis and measures detection (M2 adds `run_fault_suite`).

A fault raises `ValueError` if the analysis lacks the part it corrupts (for example, no research evidence).
"""
from __future__ import annotations

from collections.abc import Callable

from ..contracts import Analysis, EngineResult, Evidence, ScopeDecision, YearValue

Fault = Callable[[Analysis], Analysis]


def _copy(analysis: Analysis) -> Analysis:
    return analysis.model_copy(deep=True)


def _central(a: Analysis) -> EngineResult:
    if a.simulation is None or not a.simulation.scenarios:
        raise ValueError("this fault needs simulation results")
    return next((s.result for s in a.simulation.scenarios if s.scenario.name == "central"),
                a.simulation.scenarios[0].result)


def _quantitative(a: Analysis) -> Evidence:
    if a.research is None:
        raise ValueError("this fault needs research findings")
    for e in a.research.evidence:
        if e.kind == "quantitative" or e.value is not None:
            return e
    raise ValueError("this fault needs a quantitative evidence item")


def _metric_values(result: EngineResult, metric: str) -> list[YearValue]:
    for m in result.metrics:
        if m.metric == metric:
            return m.values
    raise ValueError(f"the central scenario has no {metric}")


def out_of_scope_policy(analysis: Analysis) -> Analysis:
    """The policy is a 20pp rise that the scope gate refuses, but the forecast was produced anyway."""
    a = _copy(analysis)
    if a.policy is None:
        raise ValueError("this fault needs a parsed policy")
    base = a.policy.baseline_rate_pct if a.policy.baseline_rate_pct is not None else 25.0
    a.policy.baseline_rate_pct, a.policy.proposed_rate_pct = base, min(base + 20.0, 99.0)
    a.scope = ScopeDecision(status="unsupported", forecast_allowed=False,
                            reasons=["The proposed 20pp change is far outside any UK precedent (limit 15pp)."])
    return a


def scope_warning_hidden(analysis: Analysis) -> Analysis:
    """The scope gate warned that the change exceeds every precedent."""
    a = _copy(analysis)
    if a.scope is None:
        raise ValueError("this fault needs a scope decision")
    a.scope.status = "partially_supported"
    a.scope.warnings.append("The 9pp change is larger than any UK precedent (largest 6pp), so the results are an "
                            "extrapolation.")
    return a


def long_horizon(analysis: Analysis) -> Analysis:
    """A 10-year horizon, beyond the 5 years where GDP and dynamic effects are reliable."""
    a = _copy(analysis)
    if a.policy is None:
        raise ValueError("this fault needs a parsed policy")
    a.policy.horizon_years = 10
    return a


def unverified_quote(analysis: Analysis) -> Analysis:
    """A quantitative evidence item whose quote was not found verbatim in the source."""
    a = _copy(analysis)
    e = _quantitative(a)
    e.verification_status = "unverified"
    e.verification_note = "Quote not found in the fetched document."
    return a


def orphan_evidence(analysis: Analysis) -> Analysis:
    """Evidence that cites a source the analysis does not contain."""
    a = _copy(analysis)
    if a.research is None or not a.research.evidence:
        raise ValueError("this fault needs research evidence")
    a.research.evidence[0].source_id = "S999"
    return a


def unsourced_assumption(analysis: Analysis) -> Analysis:
    """An adjustable assumption that claims a literature basis but cites nothing."""
    a = _copy(analysis)
    if a.simulation is None:
        raise ValueError("this fault needs model assumptions")
    target = next((x for x in a.simulation.assumptions if x.adjustable), None)
    if target is None:
        raise ValueError("this fault needs an adjustable assumption")
    target.basis, target.source_ids, target.evidence_ids = "literature", [], []
    return a


def thin_evidence(analysis: Analysis) -> Analysis:
    """No verified revenue or elasticity evidence: everything is about macro context."""
    a = _copy(analysis)
    if a.research is None:
        raise ValueError("this fault needs research findings")
    for e in a.research.evidence:
        e.topic = "macro_context"
    return a


def tampered_metric(analysis: Analysis) -> Analysis:
    """One stored central-scenario value no longer matches what the engine produces."""
    a = _copy(analysis)
    values = _metric_values(_central(a), "revenue_static_gbp_bn")
    values[0].value += 0.25
    return a


def sign_flip(analysis: Analysis) -> Analysis:
    """Static revenue with the wrong sign for the policy direction."""
    a = _copy(analysis)
    for yv in _metric_values(_central(a), "revenue_static_gbp_bn"):
        yv.value = -yv.value
    return a


def inflated_static(analysis: Analysis) -> Analysis:
    """A static costing three times larger than the tax base can produce."""
    a = _copy(analysis)
    for yv in _metric_values(_central(a), "revenue_static_gbp_bn"):
        yv.value *= 3.0
    return a


def placeholder_data(analysis: Analysis) -> Analysis:
    """A cited source that is only a placeholder."""
    a = _copy(analysis)
    if not a.sources:
        raise ValueError("this fault needs sources")
    a.sources[0].is_placeholder = True
    return a


def stale_baseline(analysis: Analysis) -> Analysis:
    """The forecast used a baseline vintage several years old."""
    a = _copy(analysis)
    if a.simulation is None:
        raise ValueError("this fault needs simulation results")
    a.simulation.baseline_vintage = "OBR EFO March 2019"
    return a


FAULTS: dict[str, Fault] = {
    "out_of_scope_policy": out_of_scope_policy,
    "scope_warning_hidden": scope_warning_hidden,
    "long_horizon": long_horizon,
    "unverified_quote": unverified_quote,
    "orphan_evidence": orphan_evidence,
    "unsourced_assumption": unsourced_assumption,
    "thin_evidence": thin_evidence,
    "tampered_metric": tampered_metric,
    "sign_flip": sign_flip,
    "inflated_static": inflated_static,
    "placeholder_data": placeholder_data,
    "stale_baseline": stale_baseline,
}

# fault name -> the check ID that must flag it
FAULT_TARGETS: dict[str, str] = {
    "out_of_scope_policy": "SCOPE-001",
    "scope_warning_hidden": "SCOPE-002",
    "long_horizon": "SCOPE-003",
    "unverified_quote": "CITE-002",
    "orphan_evidence": "CITE-003",
    "unsourced_assumption": "EVID-001",
    "thin_evidence": "EVID-004",
    "tampered_metric": "CALC-001",
    "sign_flip": "CALC-002",
    "inflated_static": "CALC-003",
    "placeholder_data": "DATA-001",
    "stale_baseline": "DATA-002",
}
