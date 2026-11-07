"""`parse_policy(query) -> PolicySpec` (MASTER_PROMPT 9.1). Owner: agent-5.

M1: the deterministic rules parser (`rules.py`) handles every query. M2 adds the Gemini path for live mode, with the
rules parser as the cross-check and the fallback.

The query is untrusted user text: it is only pattern-matched, never executed or forwarded as instructions.
"""
from __future__ import annotations

import logging
from datetime import date

from ..contracts import BaselineProjection, PolicySpec
from ..data import registry
from .rules import parse_rules

log = logging.getLogger(__name__)


def _baseline() -> BaselineProjection | None:
    try:
        return registry.load_baseline()
    except Exception:  # a broken registry must not stop parsing; the spec then says the rate is unknown
        log.exception("could not load the baseline; parsing without current rates")
        return None


def parse_policy(query: str, *, today: date | None = None) -> PolicySpec:
    return parse_rules(query, baseline=_baseline(), today=today)
