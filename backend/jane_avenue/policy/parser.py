"""Owner: agent-5. STUB: deterministic rules parser (agent-1 M0). Agent-5 adds the Gemini parser and more phrasings.

The query is untrusted user text: it is only pattern-matched, never executed or forwarded as instructions.
"""
from __future__ import annotations

import re
from datetime import date

from ..contracts import PolicySpec, PolicyType
from ..data import registry

_PCT = r"(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)"
_FROM_TO = re.compile(rf"from\s+{_PCT}\s+to\s+{_PCT}", re.I)
_TO = re.compile(rf"\bto\s+{_PCT}", re.I)
_BY = re.compile(r"\bby\s+(\d+(?:\.\d+)?)\s*(?:percentage\s+points?|pp|points?|%)", re.I)
_CUT_WORDS = re.compile(r"\b(cut|cuts|reduc\w*|lower\w*|decreas\w*)\b", re.I)
_YEAR = re.compile(r"\b(?:from|in)\s+(?:(january|february|march|april|may|june|july|august|september|october|"
                   r"november|december)\s+)?(20\d\d)\b", re.I)
_HORIZON = re.compile(r"\bover\s+(\d{1,2})\s+years?\b", re.I)
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")


def _policy_type(q: str) -> PolicyType:
    if re.search(r"\bvat\b|value added tax", q, re.I):
        return "vat_standard_rate"
    if re.search(r"corporation\s+tax|\bct\b|corporate\s+tax", q, re.I):
        if re.search(r"small\s+profits?", q, re.I):
            return "corporation_tax_small_profits_rate"
        return "corporation_tax_main_rate"
    return "unsupported"


def parse_policy(query: str) -> PolicySpec:
    q = query.strip()
    ambiguities: list[str] = []
    policy_type = _policy_type(q)
    tax = {"vat_standard_rate": "vat", "unsupported": None}.get(policy_type, "corporation_tax")

    # Only corporation tax has a known current rate (from the baseline); never borrow it for another tax.
    current: float | None = None
    if tax == "corporation_tax":
        baseline_cfg = registry.load_baseline()
        current = (baseline_cfg.current_small_profits_rate_pct if policy_type == "corporation_tax_small_profits_rate"
                   else baseline_cfg.current_main_rate_pct)

    baseline: float | None = None
    proposed: float | None = None
    if m := _FROM_TO.search(q):
        baseline, proposed = float(m.group(1)), float(m.group(2))
    elif current is not None and (m := _BY.search(q)):
        baseline = current
        delta = float(m.group(1))
        proposed = baseline - delta if _CUT_WORDS.search(q) else baseline + delta
        ambiguities.append(f"Baseline rate not stated; assumed the current rate of {current:g}%.")
    elif m := _TO.search(q):
        baseline, proposed = current, float(m.group(1))
        if current is not None:
            ambiguities.append(f"Baseline rate not stated; assumed the current rate of {current:g}%.")
        else:
            ambiguities.append("Baseline rate not stated and no current rate is known for this tax.")

    if m := _YEAR.search(q):
        month = _MONTHS.index(m.group(1).lower()) + 1 if m.group(1) else 4
        effective = date(int(m.group(2)), month, 1)
        if not m.group(1):
            ambiguities.append("Month not stated; assumed 1 April (start of the CT financial year).")
    else:
        effective = date(date.today().year + 1, 4, 1)
        ambiguities.append(f"Effective date not stated; assumed 1 April {effective.year}.")

    if m := _HORIZON.search(q):
        horizon = max(1, min(10, int(m.group(1))))
    else:
        horizon = 5
        ambiguities.append("Horizon not stated; assumed 5 years.")

    if policy_type == "unsupported":
        ambiguities.append("Could not identify a supported tax policy (UK corporation tax main rate).")

    description = ""
    if baseline is not None and proposed is not None and tax == "corporation_tax":
        verb = "Raise" if proposed > baseline else "Cut" if proposed < baseline else "Keep"
        which = "small profits rate" if policy_type == "corporation_tax_small_profits_rate" else "main rate"
        description = (f"{verb} the CT {which} from {baseline:g}% to {proposed:g}% "
                       f"from {effective.day} {effective.strftime('%B %Y')}")

    return PolicySpec(
        policy_type=policy_type,
        tax=tax,  # type: ignore[arg-type]
        baseline_rate_pct=baseline,
        proposed_rate_pct=proposed,
        effective_date=effective,
        horizon_years=horizon,
        description=description,
        raw_query=q,
        parse_method="rules",
        parse_confidence=0.9 if baseline is not None and proposed is not None and policy_type != "unsupported" else 0.3,
        ambiguities=ambiguities,
    )
