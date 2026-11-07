"""Evidence and assumption checks EVID-001..004 (MASTER_PROMPT 9.7). Owner: agent-5."""
from __future__ import annotations

from ...contracts import Analysis
from ._base import Outcome, check, listing, plural

MIN_CORE_EVIDENCE = 2
CORE_TOPICS = ("revenue", "elasticity")


@check("EVID-001", "assumption", "warning", "rule", "Adjustable assumptions are sourced or marked as judgement")
def evid_001(analysis: Analysis) -> Outcome:
    if analysis.simulation is None:
        return Outcome("skipped", "No model assumptions (no forecast was run).")
    adjustable = [a for a in analysis.simulation.assumptions if a.adjustable]
    unsourced = [a.name for a in adjustable if not a.source_ids and a.basis != "team_judgement"]
    judgement = [a.name for a in adjustable if not a.source_ids and a.basis == "team_judgement"]
    note = f" Team judgement, not sourced: {listing(judgement)}." if judgement else ""
    if unsourced:
        return Outcome("issue", f"{listing(unsourced)} {'claims' if len(unsourced) == 1 else 'claim'} a "
                                f"literature or official basis but cite no source.{note}", unsourced)
    sourced = len(adjustable) - len(judgement)
    return Outcome("pass", f"{sourced} of {plural(len(adjustable), 'adjustable assumption')} cite a source; the rest "
                           f"are explicitly team judgement.{note}")


@check("EVID-002", "assumption", "warning", "rule", "Assumptions lie within the range of verified evidence")
def evid_002(analysis: Analysis) -> Outcome:
    if analysis.simulation is None:
        return Outcome("skipped", "No model assumptions (no forecast was run).")
    if analysis.research is None or not analysis.research.parameter_evidence:
        return Outcome("pass", "No parameter evidence from research to compare the assumptions against.")
    verified = {e.evidence_id for e in analysis.research.evidence if e.verification_status == "verified"}
    assumptions = {a.name: a for a in analysis.simulation.assumptions}
    compared: list[str] = []
    outside: list[tuple[str, str]] = []
    for pe in analysis.research.parameter_evidence:
        a = assumptions.get(pe.parameter)
        backing = [eid for eid in pe.evidence_ids if eid in verified]
        if a is None or not backing or pe.low is None or pe.high is None:
            continue
        compared.append(a.name)
        lo, hi = min(pe.low, pe.high), max(pe.low, pe.high)
        if not lo - 1e-12 <= a.value <= hi + 1e-12:
            outside.append((a.name, f"{a.name} = {a.value:g} is outside {lo:g}-{hi:g} ({listing(backing)})"))
    if outside:
        return Outcome("issue", "Central assumptions outside the range of verified evidence: "
                                + "; ".join(text for _, text in outside) + ".", [name for name, _ in outside])
    if not compared:
        return Outcome("pass", "No parameter evidence with a verified range matches a model assumption.")
    return Outcome("pass", f"{listing(compared)} {'lies' if len(compared) == 1 else 'lie'} within the range of "
                           "verified evidence.")


@check("EVID-003", "evidence", "warning", "rule", "Contradictory evidence is surfaced")
def evid_003(analysis: Analysis) -> Outcome:
    if analysis.research is None:
        return Outcome("skipped", "No research findings to check.")
    evidence = analysis.research.evidence
    supported = {e.topic for e in evidence if e.kind != "counter_evidence"}
    counter = [e for e in evidence if e.kind == "counter_evidence"]
    contradicting = [e for e in counter if e.topic in supported]
    if contradicting:
        shown = "; ".join(f"{e.evidence_id} ({e.topic}): {e.claim[:140]}" for e in contradicting[:4])
        return Outcome("issue", f"{plural(len(contradicting), 'piece')} of evidence contradict other evidence on the "
                                f"same topic, so read those findings with care: {shown}.",
                       [e.evidence_id for e in contradicting])
    if counter:
        return Outcome("pass", f"{plural(len(counter), 'counter-evidence item')} found, none on a topic that other "
                               "evidence supports.")
    return Outcome("pass", "No contradictory evidence was found.")


@check("EVID-004", "evidence", "blocking", "rule", "Minimum verified evidence on revenue or elasticity")
def evid_004(analysis: Analysis) -> Outcome:
    mode = analysis.research.mode if analysis.research else analysis.mode
    severity = "warning" if mode == "mock" else "blocking"
    if analysis.scope is not None and not analysis.scope.forecast_allowed:
        return Outcome("skipped", "No forecast is made for an out-of-scope policy, so no evidence minimum applies.",
                       severity=severity)
    tiers = {s.source_id: s.reliability_tier for s in analysis.sources}
    if analysis.research:
        tiers.update({s.source_id: s.reliability_tier for s in analysis.research.sources})
    evidence = analysis.research.evidence if analysis.research else []
    core = [e.evidence_id for e in evidence if e.verification_status == "verified" and e.topic in CORE_TOPICS
            and tiers.get(e.source_id, 3) <= 2]
    if len(core) >= MIN_CORE_EVIDENCE:
        return Outcome("pass", f"{plural(len(core), 'verified evidence item')} on revenue or elasticity from tier 1-2 "
                               f"sources ({listing(core)}).", severity=severity)
    found = f" (found {len(core)}{': ' + listing(core) if core else ''})"
    tail = " In mock mode this is a warning, not a block." if mode == "mock" else ""
    return Outcome("issue", f"At least {MIN_CORE_EVIDENCE} verified evidence items on revenue or elasticity from "
                            f"official or peer-reviewed (tier 1-2) sources are needed{found}.{tail}", core,
                   severity=severity)
