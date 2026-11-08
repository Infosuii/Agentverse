"""Deterministic rules parser: plain English -> `PolicySpec` (MASTER_PROMPT 9.1). Owner: agent-5.

The query is untrusted user text. It is only pattern-matched here, never executed or forwarded as instructions.

Every default the parser fills in, and every interpretation it makes, is recorded in `ambiguities`, and
`parse_confidence` falls with each one, so the analyst can see and correct what was assumed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ..contracts import BaselineProjection, PolicySpec, PolicyType, TaxName

DEFAULT_HORIZON_YEARS = 5
MIN_HORIZON_YEARS, MAX_HORIZON_YEARS = 1, 10

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")
_UNITS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}

_NUM = r"(\d+(?:\.\d+)?)"
_ARROW = r"(?:to|->|→|=>)"

# Tax detection.
_CT = re.compile(r"\bcorporation[\s-]*tax\b|\bcorporate\s+(?:income\s+|profits?\s+)?tax(?:es)?\b|\bcompany\s+tax"
                 r"(?:es)?\b|\bbusiness\s+profits?\s+tax\b|\bct\b")
_VAT = re.compile(r"\bvat\b|\bvalue[\s-]+added[\s-]+tax\b|\bsales\s+tax\b")
_SMALL_PROFITS = re.compile(r"\bsmall[\s-]+profits?\b|\bsmall\s+companies(?:'|’)?\s+rate\b")
_OTHER_TAX = re.compile(r"\b(income tax|national insurance|capital gains tax|inheritance tax|stamp duty|fuel duty|"
                        r"council tax|business rates|alcohol duty|tobacco duty|wealth tax|carbon tax|"
                        r"digital services tax|bank levy|windfall tax|energy profits levy)\b")

# Jurisdiction. The model is the UK's. A change to another country's corporation tax ("US corporate tax",
# "corporation tax in France") is refused; any other mention of another country ("as in Ireland", "match Ireland's
# corporation tax") is only noted; naming the UK anywhere overrides both. Matched on the normalised (lower-case)
# text, except "US", which is matched case-sensitively on the raw query so that the pronoun "us" never counts.
_UK = re.compile(r"\b(uk|u\.k\.|united kingdom|great britain|britain|british|england|scotland|wales|"
                 r"northern ireland|hmrc|obr|hm treasury)\b")
# Every word that names another country, mapped to how the country is named in a note.
_PLACES = {
    "france": "France", "germany": "Germany", "ireland": "Ireland", "the netherlands": "the Netherlands",
    "netherlands": "the Netherlands", "spain": "Spain", "italy": "Italy", "portugal": "Portugal",
    "belgium": "Belgium", "luxembourg": "Luxembourg", "austria": "Austria", "switzerland": "Switzerland",
    "sweden": "Sweden", "norway": "Norway", "denmark": "Denmark", "finland": "Finland", "poland": "Poland",
    "japan": "Japan", "china": "China", "india": "India", "singapore": "Singapore", "hong kong": "Hong Kong",
    "south korea": "South Korea", "canada": "Canada", "mexico": "Mexico", "brazil": "Brazil",
    "australia": "Australia", "new zealand": "New Zealand", "america": "the US", "the united states": "the US",
    "united states": "the US", "the usa": "the US", "usa": "the US", "the eu": "the EU", "european union": "the EU",
}
_DEMONYMS = {  # no "polish": it is also an ordinary verb
    "french": "France", "german": "Germany", "irish": "Ireland", "dutch": "the Netherlands", "spanish": "Spain",
    "italian": "Italy", "portuguese": "Portugal", "belgian": "Belgium", "austrian": "Austria",
    "swiss": "Switzerland", "swedish": "Sweden", "norwegian": "Norway", "danish": "Denmark", "finnish": "Finland",
    "japanese": "Japan", "chinese": "China", "indian": "India", "singaporean": "Singapore", "korean": "South Korea",
    "canadian": "Canada", "mexican": "Mexico", "brazilian": "Brazil", "australian": "Australia",
    "american": "the US", "eu": "the EU", "european": "the EU",
}
_COUNTRY_NAME = {**_PLACES, **_DEMONYMS}
_PLACE_RE = "|".join(sorted(map(re.escape, _PLACES), key=len, reverse=True))
_COUNTRY_RE = "|".join(sorted(map(re.escape, _COUNTRY_NAME), key=len, reverse=True))
_TAX_WORDS = r"(?:corporation|corporate|company)\s+(?:income\s+|profits?\s+)?tax"
# "French corporation tax", "Ireland's corporate tax", "corporation tax (rate) in France".
_FOREIGN_TAX = re.compile(rf"\b(?P<a>{_COUNTRY_RE})(?:'s)?\s+(?:main\s+)?{_TAX_WORDS}"
                          rf"|\b{_TAX_WORDS}\s+(?:main\s+)?(?:rate\s+)?(?:in|of)\s+(?P<b>{_PLACE_RE})\b")
_US_TAX = re.compile(rf"\bU\.?S\.?A?(?:'s)?\s+(?i:(?:main\s+)?{_TAX_WORDS})"
                     rf"|(?i:{_TAX_WORDS}\s+(?:rate\s+)?(?:in|of)\s+the\s+)U\.?S\.?A?\b")
_FOREIGN_MENTION = re.compile(rf"\b({_COUNTRY_RE})\b")
_US_MENTION = re.compile(r"\bU\.?S\.?A?\b")
# "Match Ireland's corporation tax", "as low as Ireland's corporate tax": a comparison, not a foreign policy.
_COMPARISON = re.compile(r"\b(match\w*|like|as|than|with|versus|vs|compared|similar|equal\w*|level\s+of|"
                         r"in\s+line\s+with)\W*\w*\W*$")


def _foreign_jurisdiction(raw: str, t: str) -> tuple[str | None, bool]:
    """(the other country, as named in a note; whether the request changes that country's corporation tax).
    (None, False) when the UK is named or no other country is."""
    if _UK.search(t):
        return None, False
    for pattern, text in ((_FOREIGN_TAX, t), (_US_TAX, raw)):
        for m in pattern.finditer(text):
            if not _COMPARISON.search(text[max(0, m.start() - 30):m.start()].lower()):
                word = m.groupdict().get("a") or m.groupdict().get("b")
                return (_COUNTRY_NAME[word] if word else "the US"), True
    if m := _FOREIGN_MENTION.search(t):
        return _COUNTRY_NAME[m.group(1)], False
    if _US_MENTION.search(raw):
        return "the US", False
    return None, False


_LEVELS_AFTER = re.compile(r"(?:'s)?\s+(?:levels?|style|model)\b")
_DEVOLVED = re.compile(r"\b(scotland|scottish|wales|welsh|holyrood|senedd)\b")
DEVOLVED_INCOME_TAX_NOTE = (
    "Income tax rates for Scotland and Wales are set by the Scottish and Welsh governments, and HMRC's ready "
    "reckoner does not include changes to those devolved elements, so this request is researched without a forecast.")


def _foreign_subject(raw: str, t: str) -> tuple[str | None, bool]:
    """Any fiscal policy (#93): (the other country, whether it is the subject of the request). Another country is the
    subject unless it only appears as a comparison ("like France", "as low as Ireland's", "to French levels")."""
    if _UK.search(t):
        return None, False
    hits = [(m.start(), m.end(), _COUNTRY_NAME[m.group(1)], t) for m in _FOREIGN_MENTION.finditer(t)]
    hits += [(m.start(), m.end(), "the US", raw) for m in _US_MENTION.finditer(raw)]
    for start, end, name, text in hits:
        before = text[max(0, start - 30):start].lower()
        if not (_COMPARISON.search(before) or _LEVELS_AFTER.match(text[end:end + 12].lower())):
            return name, True
    return (hits[0][2], False) if hits else (None, False)


_UK_PART = re.compile(r"\b(northern ireland|scotland|scottish|wales|welsh|england|english)\b")
_UK_PART_NAME = {"scottish": "Scotland", "welsh": "Wales", "english": "England"}


def _jurisdiction_gate(spec: PolicySpec, raw: str, t: str, today: date) -> PolicySpec:
    """Measures and other fiscal policies get the jurisdiction rules the corporation tax path has: another country's
    policy is refused, a comparison adds a "results are for the UK" note, and devolved income tax is research-only.

    When a measure is turned into `unsupported` or `fiscal_other`, its rate notes ("assumed the current rate of 20%")
    no longer apply and would put unexplained numbers in the report (REPORT-001), so only the date and horizon notes
    are kept, re-derived from the text (#95 review)."""
    country, subject = _foreign_subject(raw, t)
    cleared = {"measure_id": None, "baseline_value": None, "proposed_value": None, "value_unit": None,
               "baseline_rate_pct": None, "proposed_rate_pct": None}

    def timing_notes() -> list[str]:
        st = _State()
        _effective_date(t, today, st)
        _horizon(t, st)
        return st.ambiguities

    if country is not None and subject:
        note = f"The request is about {country}: only UK fiscal policy is analysed."
        return spec.model_copy(update={**cleared, "policy_type": "unsupported", "tax": None,
                                       "description": describe("unsupported", None, None, None, raw),
                                       "parse_confidence": min(spec.parse_confidence, 0.3),
                                       "ambiguities": [*timing_notes(), note]})
    notes = list(spec.ambiguities)
    if country is not None:
        notes.append(f"The request mentions {country}; only UK fiscal policy is analysed, so the results are for the "
                     "UK.")
        spec = spec.model_copy(update={"parse_confidence": round(max(0.05, spec.parse_confidence - 0.1), 2)})
    if spec.policy_type == "tax_measure" and (spec.measure_id or "").startswith("income_tax_") and _DEVOLVED.search(t):
        short = raw if len(raw) <= 120 else raw[:117] + "..."
        return spec.model_copy(update={**cleared, "policy_type": "fiscal_other",
                                       "description": f"Fiscal policy (research only): \"{short}\"",
                                       "ambiguities": [*timing_notes(), DEVOLVED_INCOME_TAX_NOTE]})
    if spec.policy_type == "tax_measure" and (part := _UK_PART.search(t)):
        name = _UK_PART_NAME.get(part.group(1), part.group(1).title())
        notes.append(f"This tax is set for the whole UK and cannot be changed for {name} alone, so the costing is "
                     "UK-wide.")
    return spec.model_copy(update={"ambiguities": notes})


# Rates. Text is normalised first: "per cent" -> "%", "percentage points" / "points" -> "pp", number words -> digits.
_FROM_TO = (
    re.compile(rf"\bfrom\s+{_NUM}\s*%?\s*{_ARROW}\s*{_NUM}\s*%"),        # from 25(%) to 28%
    re.compile(rf"\bfrom\s+{_NUM}\s*%\s*{_ARROW}\s*{_NUM}(?![\d.]|\s*pp)"),  # from 25% to 28
    re.compile(rf"(?<![\w.]){_NUM}\s*%\s*{_ARROW}\s*{_NUM}\s*%"),         # 25% to 28%
    re.compile(rf"(?<![\w.]){_NUM}\s*%?\s*(?:->|→|=>)\s*{_NUM}\s*%?(?![\d.]|\s*pp)"),  # 25 -> 24.5 (symbolic arrow)
)
# A "strong" target names the new rate ("to 28%"); a "weak" one may name the current rate ("the rate is 25%").
_TO_STRONG = re.compile(rf"\b(?:to|reach(?:es|ing)?|becomes?|set\s+at|fixed\s+at)\s+(?:a\s+rate\s+of\s+)?{_NUM}\s*%")
_TO_WEAK = re.compile(rf"\b(?:at|of|be|were|was|is|stood\s+at)\s+(?:a\s+rate\s+of\s+)?{_NUM}\s*%")
# Group 1 is a minus sign ("by -2%"), read as a cut.
_BY = re.compile(rf"\bby\s+(?:an?\s+)?(?:extra\s+|additional\s+|further\s+|another\s+)?(-\s*|minus\s+)?{_NUM}\s*(pp|%)")
_DELTA_PP = re.compile(rf"(?<![\w.-]){_NUM}\s*-?\s*pp\b")
_ANY_PCT = re.compile(rf"(?<![\w.-]){_NUM}\s*%")
_NEG_RATE = re.compile(rf"(?:-\s*|\bminus\s+){_NUM}\s*%")
# "from April 2027, then to 30% in 2029": a second change, which is not modelled.
_SEQUENCE = re.compile(r"\b(then|later|thereafter|subsequently|followed\s+by|after\s+that|and\s+again)\b")

_UP = re.compile(r"\b(rais\w*|increas\w*|hik\w*|lift\w*|up|ris(?:e|es|ing)|rose|higher|boost\w*|put\s+up)\b")
_DOWN = re.compile(r"\b(cut\w*|reduc\w*|lower\w*|decreas\w*|slash\w*|drop\w*|fall\w*|fell|trim\w*)\b")

# Dates.
_ISO_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_FISCAL_YEAR = re.compile(r"\b(20\d\d)\s*[-/–]\s*(\d\d)\b")
_DAY_MONTH_YEAR = re.compile(rf"\b(?:(\d{{1,2}})(?:st|nd|rd|th)?\s+)?({'|'.join(_MONTHS)})\s+(?:of\s+)?(20\d\d)\b")
_YEAR = re.compile(r"\b(?:from|in|by|during|for|starting(?:\s+in)?|start\s+of|beginning(?:\s+of)?)\s+(20\d\d)\b")
_NEXT_YEAR = re.compile(r"\bnext\s+(?:financial\s+|tax\s+|fiscal\s+)?year\b")

# Horizon.
_HORIZON = (
    re.compile(r"\bover\s+(?:the\s+)?(?:next\s+|following\s+|first\s+)?(\d{1,3})\s+years?\b"),
    re.compile(r"\bfor\s+(?:the\s+)?(?:next\s+|following\s+|first\s+)?(\d{1,3})\s+years?\b"),
    re.compile(r"\b(\d{1,3})\s*-?\s*years?\s+(?:horizon|period|window|forecast|outlook)\b"),
    re.compile(r"\bhorizon\s+of\s+(\d{1,3})\s+years?\b"),
)


@dataclass
class _State:
    ambiguities: list[str] = field(default_factory=list)
    penalty: float = 0.0

    def note(self, text: str, penalty: float) -> None:
        if text not in self.ambiguities:
            self.ambiguities.append(text)
        self.penalty += penalty


def normalise(query: str) -> str:
    """Lower-case the query and rewrite units and number words into one canonical form for matching."""
    t = query.lower()
    t = t.replace("–", "-").replace("—", "-").replace("’", "'").replace("％", "%")
    t = re.sub(r"\bpercentage[\s-]+points?\b|\bppts?\b|\bpp\b|\bpoints?\b|\bpts?\b", " pp", t)
    t = re.sub(r"\bper[\s-]*cent\b|\bpercent\b|\bpc\b", "%", t)
    t = re.sub(r"\bhalf\s+an?\s+pp\b|\bhalf\s+a\s+%", "0.5 pp", t)
    t = re.sub(r"\ban?\s+(?=pp\b)", "1 ", t)  # "a point" -> "1 pp"
    # "twenty-eight" -> 28 before single words, so it never becomes "20-8".
    t = re.sub(rf"\b({'|'.join(_TENS)})[\s-]+({'|'.join(_UNITS)})\b",
               lambda m: str(_TENS[m.group(1)] + _UNITS.index(m.group(2)) + 1), t)
    t = re.sub(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", lambda m: str(_NUMBER_WORDS[m.group(1)]), t)
    t = re.sub(r"\b(\d+)\s+and\s+an?\s+half\b", lambda m: f"{m.group(1)}.5", t)  # "two and a half" -> 2.5
    return re.sub(r"\s+", " ", t).strip()


def _num(text: str) -> float:
    return float(text)


def _is_rate(x: float) -> bool:
    return 0 <= x <= 100


def _policy_type(t: str, st: _State) -> PolicyType:
    # The small profits rate exists only in corporation tax, so naming it is enough.
    has_ct, has_vat = bool(_CT.search(t) or _SMALL_PROFITS.search(t)), bool(_VAT.search(t))
    if has_ct:
        if has_vat:
            st.note("The request also mentions VAT, which is ignored: only corporation tax is modelled.", 0.1)
        if other := _OTHER_TAX.search(t):
            st.note(f"The request also mentions {other.group(1)}, which is ignored: only corporation tax is modelled.",
                    0.1)
        return "corporation_tax_small_profits_rate" if _SMALL_PROFITS.search(t) else "corporation_tax_main_rate"
    if has_vat:
        return "vat_standard_rate"
    if other := _OTHER_TAX.search(t):
        st.note(f"{other.group(1).capitalize()} is not supported: only UK corporation tax is modelled.", 0.0)
    else:
        st.note("Could not identify a UK fiscal policy (a tax or public spending change).", 0.0)
    return "unsupported"


def _direction(t: str) -> int:
    """+1 for raise wording, -1 for cut wording, 0 if neither or both."""
    up, down = bool(_UP.search(t)), bool(_DOWN.search(t))
    return 1 if up and not down else -1 if down and not up else 0


def _rates(t: str, current: float | None, st: _State) -> tuple[float | None, float | None]:
    """Return (baseline, proposed) in percent, noting every interpretation."""
    m = next((found for pattern in _FROM_TO if (found := pattern.search(t))), None)
    if m:
        baseline, proposed = _num(m.group(1)), _num(m.group(2))
        if _is_rate(baseline) and _is_rate(proposed):
            words = _direction(t)
            implied = (proposed > baseline) - (proposed < baseline)
            if words and implied and words != implied:
                st.note(f"The wording suggests a {'rise' if words > 0 else 'cut'}, but the stated rates "
                        f"({baseline:g}% to {proposed:g}%) imply a {'rise' if implied > 0 else 'cut'}; "
                        "used the stated rates.", 0.15)
            if current is not None and baseline != current:
                st.note(f"The stated starting rate of {baseline:g}% differs from the current rate of {current:g}%; "
                        "used the stated rate.", 0.05)
            return baseline, proposed

    strong = _TO_STRONG.search(t)
    weak = None if strong else _TO_WEAK.search(t)
    by = _BY.search(t)
    if by is None and (neg := _NEG_RATE.search(t)):
        st.note(f"A negative tax rate (-{neg.group(1)}%) is not valid.", 0.5)
        return current, None
    delta_text, delta_unit = (by.group(2), by.group(3)) if by else (None, None)
    negative = bool(by and by.group(1))  # "by -2%": a cut of 2, whatever the verb says
    if delta_text is None and (d := _DELTA_PP.search(t)):
        delta_text, delta_unit = d.group(1), "pp"
    delta = _num(delta_text) if delta_text is not None else None
    if delta_unit == "%":
        st.note(f"Read 'by {delta_text}%' as {delta_text} percentage points, not a {delta_text}% proportional "
                "change.", 0.1)
    if negative:
        unit = "percentage point" if delta == 1 else "percentage points"
        st.note(f"Read the negative change (-{delta_text}) as a cut of {delta_text} {unit}.", 0.2)

    # "The rate is 25%; raise it by 3 points": with a change stated, a weak target is the starting rate.
    start = _num(weak.group(1)) if weak and delta is not None and _is_rate(_num(weak.group(1))) else None
    target = strong or (weak if delta is None else None)

    def assume_current() -> float | None:
        if current is None:
            st.note("Baseline rate not stated and no current rate is known for this tax.", 0.2)
        else:
            st.note(f"Baseline rate not stated; assumed the current rate of {current:g}%.", 0.1)
        return current

    if target is not None and _is_rate(_num(target.group(1))):
        proposed = _num(target.group(1))
        if delta is not None:  # "raise by 3pp to 28%": the starting rate is implied by the two numbers.
            sign = -1 if negative else _direction(t) or (1 if current is None or proposed >= current else -1)
            implied_start = round(proposed - sign * delta, 6)
            if _is_rate(implied_start):
                if current is not None and implied_start != current:
                    st.note(f"The implied starting rate of {implied_start:g}% differs from the current rate of "
                            f"{current:g}%; used the implied rate.", 0.05)
                return implied_start, proposed
        baseline = assume_current()
        words = _direction(t)
        implied = 0 if baseline is None else (proposed > baseline) - (proposed < baseline)
        if words and implied and words != implied:
            st.note(f"The wording suggests a {'rise' if words > 0 else 'cut'}, but {proposed:g}% is "
                    f"{'above' if implied > 0 else 'below'} the current rate of {baseline:g}%; used {proposed:g}%.",
                    0.15)
        return baseline, proposed

    if delta is not None:
        baseline = start if start is not None else assume_current()
        if baseline is None:
            st.note("A change was stated but the starting rate is unknown, so the new rate is unknown.", 0.1)
            return None, None
        sign = -1 if negative else _direction(t)
        if sign == 0:
            sign = 1
            st.note("Direction of the change not stated; assumed an increase.", 0.25)
        proposed = round(baseline + sign * delta, 6)
        if not _is_rate(proposed):
            st.note(f"A {delta:g}pp change from {baseline:g}% gives an impossible rate of {proposed:g}%.", 0.3)
            return baseline, None
        return baseline, proposed

    pcts = [_num(x) for x in _ANY_PCT.findall(t) if _is_rate(_num(x))]
    if len(pcts) == 1:
        st.note(f"Read {pcts[0]:g}% as the proposed rate.", 0.15)
        return assume_current(), pcts[0]
    if len(pcts) >= 2:
        st.note(f"Read {pcts[0]:g}% as the current rate and {pcts[1]:g}% as the proposed rate.", 0.2)
        return pcts[0], pcts[1]

    st.note("No proposed rate found in the request.", 0.5)
    return None, None


def _effective_date(t: str, today: date, st: _State) -> date:
    if (m := _ISO_DATE.search(t)) and 1 <= int(m.group(2)) <= 12:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    if (m := _FISCAL_YEAR.search(t)) and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        year = int(m.group(1))
        st.note(f"Read the {year}-{m.group(2)} financial year as starting on 1 April {year}.", 0.0)
        return date(year, 4, 1)
    if m := _DAY_MONTH_YEAR.search(t):
        month = _MONTHS.index(m.group(2)) + 1
        day = int(m.group(1)) if m.group(1) else 1
        try:
            return date(int(m.group(3)), month, day)
        except ValueError:
            st.note(f"Invalid day {day} in {m.group(2).capitalize()}; used the 1st of the month.", 0.05)
            return date(int(m.group(3)), month, 1)
    if m := _YEAR.search(t):
        year = int(m.group(1))
        st.note(f"Month not stated; assumed 1 April {year} (start of the CT financial year).", 0.05)
        return date(year, 4, 1)
    if _NEXT_YEAR.search(t):
        st.note(f"Read 'next year' as 1 April {today.year + 1} (start of the CT financial year).", 0.05)
        return date(today.year + 1, 4, 1)
    st.note(f"Effective date not stated; assumed 1 April {today.year + 1}.", 0.1)
    return date(today.year + 1, 4, 1)


def _horizon(t: str, st: _State) -> int:
    for pattern in _HORIZON:
        if m := pattern.search(t):
            years = int(m.group(1))
            clamped = max(MIN_HORIZON_YEARS, min(MAX_HORIZON_YEARS, years))
            if clamped != years:
                st.note(f"A {years}-year horizon is outside the supported 1-10 years; used {clamped} years.", 0.05)
            return clamped
    st.note(f"Horizon not stated; assumed {DEFAULT_HORIZON_YEARS} years.", 0.05)
    return DEFAULT_HORIZON_YEARS


_TAX_LABEL: dict[PolicyType, str] = {
    "corporation_tax_main_rate": "CT main rate",
    "corporation_tax_small_profits_rate": "CT small profits rate",
    "vat_standard_rate": "VAT standard rate",
}


def describe(policy_type: PolicyType, baseline: float | None, proposed: float | None, effective: date | None,
             raw_query: str) -> str:
    """One readable sentence, e.g. "Raise the CT main rate from 25% to 28% from 1 April 2027"."""
    label = _TAX_LABEL.get(policy_type)
    if label is None:
        short = raw_query if len(raw_query) <= 80 else raw_query[:77] + "..."
        return f"Unsupported request: \"{short}\""
    when = f" from {effective.day} {effective.strftime('%B %Y')}" if effective else ""
    if proposed is None:
        return f"Change the {label}{when} (new rate not stated)"
    if baseline is None:
        return f"Set the {label} to {proposed:g}%{when}"
    verb = "Raise" if proposed > baseline else "Cut" if proposed < baseline else "Keep"
    if verb == "Keep":
        return f"Keep the {label} at {proposed:g}%{when}"
    return f"{verb} the {label} from {baseline:g}% to {proposed:g}%{when}"


def parse_rules(query: str, *, baseline: BaselineProjection | None = None, today: date | None = None) -> PolicySpec:
    """Parse `query` with rules only. `baseline` supplies the current CT rates; `today` anchors relative dates."""
    raw = query.strip()
    t = normalise(raw)
    today = today or date.today()
    st = _State()

    # Every other UK fiscal policy (contract-change #93): ready-reckoner measures and research-only policies.
    if not (_CT.search(t) or _SMALL_PROFITS.search(t)):
        from .measures import parse_measure

        if (measure := parse_measure(raw, t, today)) is not None:
            return _jurisdiction_gate(measure, raw, t, today)

    policy_type = _policy_type(t, st)
    if policy_type in ("corporation_tax_main_rate", "corporation_tax_small_profits_rate"):
        country, refused = _foreign_jurisdiction(raw, t)
        if country is not None and refused:
            st.note(f"The request is about corporation tax in {country}: only UK corporation tax is modelled.", 0.0)
            policy_type = "unsupported"
        elif country is not None:
            st.note(f"The request mentions {country}; only UK corporation tax is modelled, so the results are for "
                    "the UK.", 0.1)
    tax: TaxName | None = {"vat_standard_rate": "vat", "unsupported": None}.get(policy_type, "corporation_tax")  # type: ignore[assignment]

    # Only corporation tax has a known current rate (from the baseline); never borrow it for another tax.
    current: float | None = None
    if tax == "corporation_tax" and baseline is not None:
        current = (baseline.current_small_profits_rate_pct if policy_type == "corporation_tax_small_profits_rate"
                   else baseline.current_main_rate_pct)

    rate_from, rate_to = _rates(t, current, st)
    targets = list(dict.fromkeys(_num(m.group(1)) for m in _TO_STRONG.finditer(t)))
    if _SEQUENCE.search(t) and len(targets) > 1:
        st.note(f"The request describes more than one rate change ({', '.join(f'{x:g}%' for x in targets)}); only "
                "the first is modelled.", 0.15)
    effective = _effective_date(t, today, st)
    horizon = _horizon(t, st)

    confidence = 1.0 - st.penalty
    if policy_type == "unsupported":
        confidence = min(confidence, 0.3)
    if rate_to is None:
        confidence = min(confidence, 0.3)
    confidence = round(max(0.05, min(1.0, confidence)), 2)

    return PolicySpec(
        policy_type=policy_type,
        tax=tax,
        baseline_rate_pct=rate_from,
        proposed_rate_pct=rate_to,
        effective_date=effective,
        horizon_years=horizon,
        description=describe(policy_type, rate_from, rate_to, effective, raw),
        raw_query=raw,
        parse_method="rules",
        parse_confidence=confidence,
        ambiguities=st.ambiguities,
    )
