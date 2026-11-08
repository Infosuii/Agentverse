"""Rules parser for UK fiscal policies other than corporation tax (contract-change #93). Owner: agent-5 (written by
agent-2 on the human owner's instruction, for owner review).

`parse_measure(raw, t, today)` runs before the corporation-tax path whenever the request does not name corporation
tax. It returns:

- a `tax_measure` spec for any measure HMRC's ready reckoner costs (engine/reckoner.py): income tax rates and
  Personal Allowance, NICs, VAT, IPT, CGT, IHT, fuel, alcohol and tobacco duties, and Child Benefit, with the change
  in that measure's own unit;
- a `fiscal_other` spec for any other tax or spending policy (researched and reported, no forecast);
- None when the request is not a UK fiscal policy (the caller keeps its `unsupported` result).

As in rules.py, the query is untrusted text and is only pattern-matched. Every default is recorded in `ambiguities`.
"""
from __future__ import annotations

import re
from datetime import date

from ..contracts import PolicySpec
from ..engine import reckoner
from .rules import _DOWN, _UP, _effective_date, _horizon, _rates, _State

# Measure detection on the normalised text (lower case, "per cent" -> "%", "points" -> " pp", number words -> digits).
# Order matters: the more specific names come first.
_CGT = re.compile(r"\bcapital[\s-]+gains[\s-]+tax\b|\bcgt\b")
_NIC = re.compile(r"\bnational[\s-]+insurance\b|\bnics?\b|\bni\s+contributions?\b")
_MEASURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Not the "two-child limit/cap" (a Universal Credit rule), which is researched as another fiscal policy.
    ("child_benefit", re.compile(r"(?<!two[\s-])(?<!2[\s-])\bchild[\s-]+benefit\b(?![\s-]+(?:cap|limit))")),
    ("income_tax_personal_allowance", re.compile(r"\bpersonal[\s-]+allowance\b|\btax[\s-]+free[\s-]+allowance\b")),
    ("ipt_standard_rate", re.compile(r"\binsurance[\s-]+premium[\s-]+tax\b|\bipt\b")),
    ("inheritance_tax_rate", re.compile(r"\binheritance[\s-]+tax\b|\biht\b|\bdeath[\s-]+dut(?:y|ies)\b")),
    ("fuel_duty", re.compile(r"\bfuel[\s-]+(?:duty|duties|tax)\b|\b(?:petrol|diesel)[\s-]+(?:duty|duties|tax)\b")),
    ("alcohol_duty", re.compile(r"\b(?:alcohol|beer|cider|wine|spirits?)[\s-]+(?:duty|duties|tax)\b")),
    ("tobacco_duty", re.compile(r"\b(?:tobacco|cigarette)[\s-]+(?:duty|duties|tax)\b")),
    ("vat", re.compile(r"\bvat\b|\bvalue[\s-]+added[\s-]+tax\b|\bsales[\s-]+tax\b")),
    ("cgt", _CGT),
    ("nics", _NIC),
    ("income_tax", re.compile(r"\bincome[\s-]+tax\b|\b(?:basic|higher|additional|top)[\s-]+rate\s+of\s+tax\b"
                              r"|\b(?:basic|higher|additional)[\s-]+rate(?:\s+of)?\s+income\b")),
    # Bare band names ("raise the additional rate to 50%") are income tax; checked last, after VAT, CGT and NICs.
    ("income_tax_band", re.compile(r"\b(?:basic|higher|additional|top)[\s-]+rate\b|\b45p\s+rate\b")),
)
# Other taxes and spending: fiscal, but with no validated model. Researched and reported only.
_OTHER_FISCAL = re.compile(
    r"\b(council[\s-]+tax|business[\s-]+rates|stamp[\s-]+duty|sdlt|wealth[\s-]+tax|carbon[\s-]+tax|"
    r"digital[\s-]+services[\s-]+tax|bank[\s-]+(?:levy|surcharge)|windfall[\s-]+tax|energy[\s-]+profits[\s-]+levy|"
    r"apprenticeship[\s-]+levy|air[\s-]+passenger[\s-]+duty|vehicle[\s-]+excise[\s-]+duty|road[\s-]+tax|"
    r"landfill[\s-]+tax|sugar[\s-]+tax|soft[\s-]+drinks[\s-]+(?:industry\s+)?levy|land[\s-]+value[\s-]+tax|"
    r"dividend[\s-]+tax|plastic[\s-]+packaging[\s-]+tax|gambling[\s-]+(?:duty|tax)|tariffs?|"
    r"(?:public|government)[\s-]+spending|spending|funding|public[\s-]+investment|capital[\s-]+investment|"
    r"nhs|defen[cs]e[\s-]+(?:spending|budget)|schools?[\s-]+(?:spending|funding|budget)|education[\s-]+(?:spending|"
    r"funding|budget)|welfare|universal[\s-]+credit|state[\s-]+pension|pension[\s-]+(?:credit|triple[\s-]+lock)|"
    r"triple[\s-]+lock|housing[\s-]+benefit|winter[\s-]+fuel|benefits?[\s-]+(?:cap|freeze|uprating)|"
    r"public[\s-]+sector[\s-]+pay|borrowing|deficit|national[\s-]+debt|fiscal[\s-]+rules?|tax[\s-]+credits?|"
    r"(?:cut|raise|increase|lower|reduce)\s+(?:all\s+)?taxes|"
    # Policies with direct fiscal effects that are not themselves taxes or spending lines (contract-change #93).
    r"(?:national[\s-]+)?(?:minimum|living)[\s-]+wage|benefits?|pip|personal[\s-]+independence[\s-]+payment|"
    r"jobseeker'?s?[\s-]+allowance|carer'?s?[\s-]+allowance|disability[\s-]+(?:benefits?|payments?)|"
    r"tax(?:es|ation)?|levy|levies|dut(?:y|ies)|subsid(?:y|ies)|tax[\s-]+reliefs?|budget)\b")
# Words that name the measure must not count as direction words ("higher rate" is not "raise").
_NAME_WORDS = re.compile(r"\b(?:basic|higher|additional|top|lower|reduced|standard|main)[\s-]+rates?\b|"
                         r"\bhigher[\s-]+earners?\b|\b\d+p\s+rate\b")

_AMOUNT = r"£\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?(k\b|bn\b|billion\b|m\b|million\b)?"
_PENCE = r"(\d+(?:\.\d+)?)\s?(?:p\b|pence\b)"


def _measure_id(t: str, st: _State) -> str | None:
    found = next((mid for mid, pattern in _MEASURES if pattern.search(t)), None)
    if found == "vat":
        return "vat_reduced_rate" if re.search(r"\breduced[\s-]+rate\b", t) else "vat_standard_rate"
    if found == "cgt":
        if re.search(r"\b(lower|basic)[\s-]+rate\b", t):
            return "cgt_lower_rate"
        if not re.search(r"\b(higher|upper|top)[\s-]+rate\b", t):
            st.note("Capital Gains Tax band not stated; assumed the higher rate.", 0.1)
        return "cgt_higher_rate"
    if found == "nics":
        if re.search(r"\bemployers?'?s?\b", t):
            return "nics_employer_rate"
        if re.search(r"\bclass[\s-]+4\b|\bself[\s-]+employed\b", t):
            return "nics_class4_main_rate"
        if not re.search(r"\bemployees?'?s?\b", t):
            st.note("National Insurance class not stated; assumed the Class 1 employee main rate.", 0.1)
        return "nics_employee_main_rate"
    if found == "income_tax_band":
        st.note("The tax was not named; read the rate band as Income Tax.", 0.1)
        found = "income_tax"
    if found == "income_tax":
        if re.search(r"\b(additional|top)[\s-]+rate\b|\b45p\b", t):
            return "income_tax_additional_rate"
        if re.search(r"\bhigher[\s-]+rate\b", t):
            return "income_tax_higher_rate"
        if not re.search(r"\bbasic[\s-]+rate\b", t):
            st.note("Income Tax band not stated; assumed the basic rate.", 0.1)
        return "income_tax_basic_rate"
    return found


def _direction(t: str) -> int:
    t = _NAME_WORDS.sub(" ", t)
    up, down = bool(_UP.search(t)), bool(_DOWN.search(t))
    return 1 if up and not down else -1 if down and not up else 0


def _gbp(value: str, scale: str | None) -> float:
    x = float(value.replace(",", ""))
    return x * {"k": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}.get((scale or "").strip(), 1.0)


def _money_values(t: str, current: float | None, st: _State, *, unit_word: str) -> tuple[float | None, float | None]:
    """(current, proposed) for a £ measure: "from £X to £Y", "to £Y", "by £N", "by N%"."""
    if m := re.search(rf"\bfrom\s+{_AMOUNT}\s+(?:to|->)\s+{_AMOUNT}", t):
        return _gbp(m.group(1), m.group(2)), _gbp(m.group(3), m.group(4))
    sign = _direction(t)
    by = re.search(rf"\bby\s+(?:an?\s+(?:extra|additional|further)\s+)?{_AMOUNT}", t)
    by_pct = re.search(r"\bby\s+(\d+(?:\.\d+)?)\s*%", t)
    to = re.search(rf"\b(?:to|at)\s+{_AMOUNT}", t)
    if current is None:
        st.note(f"The current {unit_word} is not known, so the change cannot be costed.", 0.3)
        return None, None
    if to and not by:
        return current, _gbp(to.group(1), to.group(2))
    if by or by_pct:
        if sign == 0:
            sign = 1
            st.note("Direction of the change not stated; assumed an increase.", 0.25)
        delta = _gbp(by.group(1), by.group(2)) if by else current * float(by_pct.group(1)) / 100.0  # type: ignore[union-attr]
        if by_pct and not by:
            st.note(f"Read 'by {by_pct.group(1)}%' as {by_pct.group(1)}% of the current {unit_word} "  # type: ignore[union-attr]
                    f"({current:,.2f}).", 0.05)
        return current, round(current + sign * delta, 2)
    st.note(f"No new {unit_word} found in the request.", 0.5)
    return current, None


def _duty_values(t: str, m: reckoner.Measure, st: _State) -> tuple[float | None, float | None, str]:
    """(current, proposed, unit) for a duty: pence per litre where the current rate is known, else an index."""
    sign = _direction(t)
    pct = re.search(r"\bby\s+(\d+(?:\.\d+)?)\s*%", t)
    if m.current_value is not None:  # fuel duty, in p/litre
        cur = m.current_value
        if f := re.search(rf"\bfrom\s+{_PENCE}\s+(?:to|->)\s+{_PENCE}", t):
            return float(f.group(1)), float(f.group(2)), m.current_unit
        if to := re.search(rf"\bto\s+{_PENCE}", t):
            return cur, float(to.group(1)), m.current_unit
        if by := re.search(rf"\bby\s+{_PENCE}", t):
            if sign == 0:
                sign = 1
                st.note("Direction of the change not stated; assumed an increase.", 0.25)
            return cur, round(cur + sign * float(by.group(1)), 4), m.current_unit
        if pct:
            if sign == 0:
                sign = 1
                st.note("Direction of the change not stated; assumed an increase.", 0.25)
            return cur, round(cur * (1 + sign * float(pct.group(1)) / 100.0), 4), m.current_unit
    elif pct:  # alcohol and tobacco: a percentage change of every rate, on an index (current = 100)
        if sign == 0:
            sign = 1
            st.note("Direction of the change not stated; assumed an increase.", 0.25)
        st.note("Applied the percentage change to every duty rate in the group (current rates indexed to 100).", 0.05)
        return 100.0, round(100.0 * (1 + sign * float(pct.group(1)) / 100.0), 6), "index (current rate = 100)"
    st.note(f"No change to {m.label.lower()} found in the request.", 0.5)
    return m.current_value, None, m.current_unit or "index (current rate = 100)"


def describe_measure(m: reckoner.Measure, spec_values: dict, effective: date | None) -> str:
    when = f" from {effective.day} {effective.strftime('%B %Y')}" if effective else ""
    if m.unit == "pp":
        old, new = spec_values.get("baseline_rate_pct"), spec_values.get("proposed_rate_pct")
        fmt = "{:g}%"
    elif m.unit == "pct_of_rate" and spec_values.get("value_unit", "").startswith("index"):
        old, new = spec_values.get("baseline_value"), spec_values.get("proposed_value")
        if old is not None and new is not None and new != old:
            pct = abs(new / old - 1) * 100
            return f"{'Raise' if new > old else 'Cut'} {m.label[0].lower() + m.label[1:]} by {pct:g}%{when}"
        fmt = "{:g}"
    elif m.unit == "pct_of_rate":
        old, new = spec_values.get("baseline_value"), spec_values.get("proposed_value")
        fmt = "{:g}p per litre"
    else:
        old, new = spec_values.get("baseline_value"), spec_values.get("proposed_value")
        fmt = "£{:,.2f}" if m.unit == "gbp_per_week" else "£{:,.0f}"
        fmt += " a week" if m.unit == "gbp_per_week" else ""
    name = ("the " + m.label if m.label.startswith(("VAT", "Income", "Class", "Capital", "Inheritance", "Insurance"))
            else m.label if m.label.startswith("Child") else m.label[0].lower() + m.label[1:])
    if new is None:
        return f"Change {name}{when} (new value not stated)"
    if old is None:
        return f"Set {name} to {fmt.format(new)}{when}"
    verb = "Raise" if new > old else "Cut" if new < old else "Keep"
    if verb == "Keep":
        return f"Keep {name} at {fmt.format(new)}{when}"
    return f"{verb} {name} from {fmt.format(old)} to {fmt.format(new)}{when}"


def parse_measure(raw: str, t: str, today: date) -> PolicySpec | None:
    """Parse a non-corporation-tax fiscal policy, or return None if `t` names no fiscal policy."""
    st = _State()
    mid = _measure_id(t, st)
    m = reckoner.get_measure(mid) if mid else None
    if m is None:
        if not _OTHER_FISCAL.search(t):
            return None
        effective = _effective_date(t, today, st)
        horizon = _horizon(t, st)
        st.note("No validated model exists for this policy yet: it is researched and reported, but no quantitative "
                "forecast is made.", 0.0)
        short = raw if len(raw) <= 120 else raw[:117] + "..."
        return PolicySpec(policy_type="fiscal_other", effective_date=effective, horizon_years=horizon,
                          description=f"Fiscal policy (research only): \"{short}\"", raw_query=raw,
                          parse_method="rules", parse_confidence=round(max(0.05, min(0.6, 1.0 - st.penalty)), 2),
                          ambiguities=st.ambiguities)

    values: dict = {}
    if m.unit == "pp":
        text = _NAME_WORDS.sub(" ", t)  # "higher rate" is not a raise; "the 45p rate" is a name, not a number
        # Pence in the pound: a level after "to/from/at" is a rate ("to 50p" = 50%), any other is a change ("by 1p").
        text = re.sub(r"\b(to|from|at)\s+(-?\s*\d+(?:\.\d+)?)\s?p\b", r"\1 \2%", text)
        text = re.sub(r"(?<![\w.-])(\d+(?:\.\d+)?)\s?p\b", r"\1 pp", text)
        rate_from, rate_to = _rates(text, m.current_value, st)
        values = {"baseline_rate_pct": rate_from, "proposed_rate_pct": rate_to}
    elif m.unit in ("gbp", "gbp_per_week"):
        word = "Personal Allowance" if m.unit == "gbp" else "weekly rate (eldest child)"
        old, new = _money_values(t, m.current_value, st, unit_word=word)
        values = {"baseline_value": old, "proposed_value": new, "value_unit": "£" if m.unit == "gbp" else "£/week"}
        if m.unit == "gbp_per_week":
            st.note("The change in £ a week applies to both Child Benefit rates (eldest and additional children).", 0.0)
    else:
        old, new, unit = _duty_values(t, m, st)
        values = {"baseline_value": old, "proposed_value": new, "value_unit": unit}
    effective = _effective_date(t, today, st)
    horizon = _horizon(t, st)
    missing = values.get("proposed_rate_pct", values.get("proposed_value")) is None
    confidence = round(max(0.05, min(0.3 if missing else 1.0, 1.0 - st.penalty)), 2)
    return PolicySpec(policy_type="tax_measure", measure_id=m.measure_id, effective_date=effective,
                      horizon_years=horizon, description=describe_measure(m, values, effective), raw_query=raw,
                      parse_method="rules", parse_confidence=confidence, ambiguities=st.ambiguities, **values)
