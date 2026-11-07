"""Citation checks CITE-002 and CITE-003 (MASTER_PROMPT 9.7). CITE-001 (source fetch) arrives in M2. Owner: agent-5."""
from __future__ import annotations

from ...contracts import Analysis
from ._base import Outcome, check, listing, plural


@check("CITE-002", "citation", "error", "rule", "Quantitative evidence has verified verbatim quotes")
def cite_002(analysis: Analysis) -> Outcome:
    if analysis.research is None:
        return Outcome("skipped", "No research findings to check.")
    quantitative = [e for e in analysis.research.evidence if e.kind == "quantitative" or e.value is not None]
    if not quantitative:
        return Outcome("pass", "No quantitative evidence items to check.")
    no_quote = [e.evidence_id for e in quantitative if not (e.quote or "").strip()]
    unverified = [e.evidence_id for e in quantitative
                  if e.evidence_id not in no_quote and e.verification_status != "verified"]
    if no_quote or unverified:
        parts = []
        if no_quote:
            parts.append(f"{listing(no_quote)} {'has' if len(no_quote) == 1 else 'have'} no verbatim quote")
        if unverified:
            parts.append(f"{listing(unverified)} {'is' if len(unverified) == 1 else 'are'} not verified against "
                         "the source text")
        return Outcome("issue", "Quantitative evidence " + "; ".join(parts) + ".", no_quote + unverified)
    return Outcome("pass", f"All {plural(len(quantitative), 'quantitative evidence item')} have verified quotes.")


@check("CITE-003", "citation", "error", "rule", "Every cited source ID exists")
def cite_003(analysis: Analysis) -> Outcome:
    known = {s.source_id for s in analysis.sources}
    cited: list[tuple[str, str]] = []  # (where, source_id)
    if analysis.research:
        cited += [(e.evidence_id, e.source_id) for e in analysis.research.evidence]
    if analysis.simulation:
        cited += [(a.name, sid) for a in analysis.simulation.assumptions for sid in a.source_ids]
    if analysis.precedents:
        cited += [(f"{m.change.change_id}.costing.{c.fiscal_year}", c.source_id)
                  for m in analysis.precedents.matches for c in m.change.official_costings]
    if not cited:
        return Outcome("pass", "Nothing cites a source yet.")
    missing = [(where, sid) for where, sid in cited if sid not in known]
    if missing:
        detail = "; ".join(f"{where} cites {sid}" for where, sid in missing[:8])
        more = f" (and {len(missing) - 8} more)" if len(missing) > 8 else ""
        return Outcome("issue", f"{plural(len(missing), 'citation')} point to sources that are not in the analysis: "
                                f"{detail}{more}.", [where for where, _ in missing])
    return Outcome("pass", f"All {plural(len(cited), 'citation')} resolve to sources in the analysis.")
