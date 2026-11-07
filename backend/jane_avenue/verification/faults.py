"""Fault-injection library for testing and evaluating the verifier (agent-5 brief M1.5). Owner: agent-5.

Each fault takes an `Analysis` and returns a deep copy with exactly one realistic defect injected. The input is never
modified. `FAULT_TARGETS` names the check that must catch each fault. Agent-10's verifier evaluation applies every
fault to an analysis and measures detection with `suite.run_fault_suite`.

A fault raises `ValueError` if the analysis lacks the part it corrupts (for example, no research evidence).
"""
from __future__ import annotations

from collections.abc import Callable

from ..contracts import Analysis, EngineResult, Evidence, ParameterEvidence, ReportSection, ScopeDecision, YearValue

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


def fake_source_url(analysis: Analysis) -> Analysis:
    """A source whose URL was made up: it points at a domain that cannot exist and was never fetched."""
    a = _copy(analysis)
    target = next((s for s in a.sources if not s.is_placeholder), None)
    if target is None:
        raise ValueError("this fault needs a non-placeholder source")
    target.url = "https://www.obr-official-forecasts.invalid/efo/ct-costing-2027.pdf"
    target.url_verified = False
    return a


def evidence_out_of_range(analysis: Analysis) -> Analysis:
    """Verified evidence puts an elasticity in a range that excludes the model's central value."""
    a = _copy(analysis)
    if a.research is None or a.simulation is None:
        raise ValueError("this fault needs research findings and model assumptions")
    verified = [e.evidence_id for e in a.research.evidence if e.verification_status == "verified"]
    target = next((x for x in a.simulation.assumptions if x.adjustable), None)
    if not verified or target is None:
        raise ValueError("this fault needs verified evidence and an adjustable assumption")
    width = max(abs(target.value), 1.0)
    a.research.parameter_evidence = [ParameterEvidence(
        parameter=target.name, low=target.value + width, high=target.value + 2 * width, evidence_ids=verified[:1],
        note="Injected fault: evidence range excludes the central assumption.")]
    return a


def contradicting_evidence(analysis: Analysis) -> Analysis:
    """Counter-evidence on a topic that other evidence supports."""
    a = _copy(analysis)
    if a.research is None or not a.research.evidence:
        raise ValueError("this fault needs research evidence")
    first = a.research.evidence[0]
    a.research.evidence.append(Evidence(
        evidence_id=f"E{len(a.research.evidence) + 900}", source_id=first.source_id, kind="counter_evidence",
        topic=first.topic, claim="Receipts after the last rise fell short of the official costing.",
        verification_status="verified", confidence="medium"))
    return a


def causal_claim(analysis: Analysis) -> Analysis:
    """An unsupported causal claim with no evidence reference in the research summary."""
    a = _copy(analysis)
    if a.research is None:
        raise ValueError("this fault needs research findings")
    a.research.summary = (a.research.summary.rstrip() + " Raising the rate will cause a collapse in business "
                          "investment.").strip()
    return a


def mislabelled_interval(analysis: Analysis) -> Analysis:
    """Assumption-driven Monte Carlo bands relabelled as calibrated prediction intervals."""
    a = _copy(analysis)
    if a.simulation is None or a.simulation.monte_carlo is None:
        raise ValueError("this fault needs Monte Carlo results")
    a.simulation.monte_carlo.interval_kind = "empirical_prediction_interval"
    a.simulation.monte_carlo.empirical_interval = None
    a.simulation.monte_carlo.empirical_calibration_note = None
    return a


def raw_number_in_report(analysis: Analysis) -> Analysis:
    """Report prose containing a number that no key figure, evidence or policy field supplied."""
    a = _copy(analysis)
    if a.report is None:
        raise ValueError("this fault needs a generated report")
    a.report.sections.append(ReportSection(section_id="injected", heading="Modelled impacts",
                                           body_markdown="Receipts would rise by £7.3bn in the first full year."))
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
    "fake_source_url": fake_source_url,
    "evidence_out_of_range": evidence_out_of_range,
    "contradicting_evidence": contradicting_evidence,
    "causal_claim": causal_claim,
    "mislabelled_interval": mislabelled_interval,
    "raw_number_in_report": raw_number_in_report,
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
    "fake_source_url": "CITE-001",
    "evidence_out_of_range": "EVID-002",
    "contradicting_evidence": "EVID-003",
    "causal_claim": "CAUSAL-001",
    "mislabelled_interval": "UNC-001",
    "raw_number_in_report": "REPORT-001",
}
