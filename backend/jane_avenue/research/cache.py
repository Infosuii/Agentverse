"""Research cache key (MASTER_PROMPT 9.2 "Caching"). Owner: agent-2. Cache read/write and replay land in M2 (#38)."""
from __future__ import annotations

import hashlib
import json

from ..contracts import PolicySpec


def cache_key(spec: PolicySpec) -> str:
    """SHA-256 of the canonical JSON of the four fields that determine the research question."""
    payload = {"policy_type": spec.policy_type, "baseline_rate_pct": spec.baseline_rate_pct,
               "proposed_rate_pct": spec.proposed_rate_pct, "horizon_years": spec.horizon_years}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
