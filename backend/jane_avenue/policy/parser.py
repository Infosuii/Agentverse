"""`parse_policy(query) -> PolicySpec` (MASTER_PROMPT 9.1). Owner: agent-5.

- Live mode: Gemini structured output (`gemini.py`), cross-checked against the rules parser
  (`parse_method="gemini"`).
- Mock mode, or whenever Gemini is unavailable or returns something invalid: the deterministic rules parser
  (`parse_method="rules"`).

The query is untrusted user text: it is only pattern-matched, or passed to Gemini as data, never executed.
"""
from __future__ import annotations

import logging
from datetime import date

from ..config import get_settings
from ..contracts import BaselineProjection, PolicySpec
from ..data import registry
from ..llm import LLMUnavailable, get_llm
from . import gemini
from .rules import parse_rules

log = logging.getLogger(__name__)


def _baseline() -> BaselineProjection | None:
    try:
        return registry.load_baseline()
    except Exception:  # a broken registry must not stop parsing; the spec then says the rate is unknown
        log.exception("could not load the baseline; parsing without current rates")
        return None


def parse_policy(query: str, *, today: date | None = None, use_llm: bool | None = None) -> PolicySpec:
    """`use_llm` defaults to live mode only."""
    baseline = _baseline()
    rules = parse_rules(query, baseline=baseline, today=today)
    if rules.policy_type in ("tax_measure", "fiscal_other"):
        # The Gemini path reads corporation-tax fields only; measure values come from the text parser alone.
        return rules
    if use_llm is None:
        use_llm = get_settings().mode == "live"
    if not use_llm:
        return rules
    try:
        parsed = get_llm().generate_structured(gemini.build_prompt(query.strip()), gemini.ParsedPolicy,
                                               system=gemini.SYSTEM_INSTRUCTION)
        return gemini.merge(query.strip(), parsed, rules, baseline)
    except LLMUnavailable as exc:
        log.info("Gemini parser unavailable, using rules: %s", exc)
    except Exception:  # an invalid or surprising answer must never break parsing
        log.exception("Gemini parser failed, using rules")
    return rules
