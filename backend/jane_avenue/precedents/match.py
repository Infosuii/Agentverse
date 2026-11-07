"""Owner: agent-6. STUB: simple precedent matcher (agent-1 M0). Agent-6 replaces it with the full 5-component score.

STUB similarity = 0.5 x direction + 0.5 x magnitude, with magnitude = exp(-|abs(d_hist) - abs(d_prop)| / 3pp).
"""
from __future__ import annotations

import math

from ..contracts import PolicySpec, PrecedentAnalysis, PrecedentMatch
from ..data import registry


def find_precedents(spec: PolicySpec, *, k: int = 5) -> PrecedentAnalysis:
    changes = [c for c in registry.load_policy_changes(spec.tax or "corporation_tax")
               if c.policy_type == spec.policy_type]
    prop = spec.change_pp()
    matches: list[PrecedentMatch] = []
    if prop is not None and spec.policy_type != "unsupported":
        for c in changes:
            hist = c.new_rate_pct - c.old_rate_pct
            direction = 1.0 if (hist > 0) == (prop > 0) and hist != 0 and prop != 0 else 0.0
            magnitude = math.exp(-abs(abs(hist) - abs(prop)) / 3.0)
            sim = 0.5 * direction + 0.5 * magnitude
            matches.append(PrecedentMatch(change=c, similarity=round(sim, 6),
                                          similarity_breakdown={"direction": direction, "magnitude": magnitude},
                                          comparability_notes=["Placeholder data: not yet verified."]))
        matches.sort(key=lambda m: m.similarity, reverse=True)
        matches = matches[:k]

    source_ids = {sid for m in matches for sid in m.change.source_ids}
    sources = [s for sid in sorted(source_ids) if (s := registry.get_source(sid)) is not None]
    summary = (f"{len(matches)} placeholder precedents ranked by direction and size of change."
               if matches else "No comparable precedents for this policy.")
    return PrecedentAnalysis(method="stub-direction-magnitude", dataset_version=registry.DATASET_VERSION,
                             matches=matches, summary=summary, sources=sources)
