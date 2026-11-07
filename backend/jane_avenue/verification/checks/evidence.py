"""Evidence and assumption checks EVID-001 and EVID-004 (MASTER_PROMPT 9.7). EVID-002/003 arrive in M2.
Owner: agent-5."""
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
