"""Data checks DATA-001 and DATA-002 (MASTER_PROMPT 9.7). Owner: agent-5."""
from __future__ import annotations

import re
from datetime import date

from ...contracts import Analysis
from ...data import registry
from ._base import Outcome, check, listing, plural

MAX_VINTAGE_AGE_MONTHS = 12
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")
_VINTAGE = re.compile(rf"(?:\b({'|'.join(_MONTHS)}|{'|'.join(m[:3] for m in _MONTHS)})\w*\s+)?\b((?:19|20)\d\d)\b",
                      re.I)


@check("DATA-001", "data", "warning", "rule", "No placeholder data")
def data_001(analysis: Analysis) -> Outcome:
    found: list[str] = []
    found += [f"source:{s.source_id}" for s in analysis.sources if s.is_placeholder]
    if analysis.research:
        found += [f"source:{s.source_id}" for s in analysis.research.sources if s.is_placeholder]
    if analysis.precedents:
        found += [f"precedent:{m.change.change_id}" for m in analysis.precedents.matches if m.change.is_placeholder]
    if analysis.simulation:
        found += [f"assumption:{a.name}" for a in analysis.simulation.assumptions if a.is_placeholder]
    found += [f"dataset:{d.dataset_id}" for d in registry.list_datasets() if d.is_placeholder]
    if registry.load_baseline().is_placeholder:
        found.append("baseline")
    found = list(dict.fromkeys(found))
    if found:
        return Outcome("issue", f"{plural(len(found), 'placeholder')} not yet verified against official data: "
                                f"{listing(found)}.", found)
    return Outcome("pass", "No placeholder sources, datasets, assumptions, baseline or precedents.")


def vintage_date(vintage: str) -> date | None:
    """"OBR EFO March 2026" -> 1 March 2026; "2026" -> 1 January 2026; None if no year is named."""
    m = _VINTAGE.search(vintage or "")
    if m is None:
        return None
    month = 1
    if m.group(1):
        month = next(i for i, name in enumerate(_MONTHS, start=1) if name.startswith(m.group(1).lower()[:3]))
    return date(int(m.group(2)), month, 1)


def _months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


@check("DATA-002", "data", "warning", "rule", "Baseline is current and not extrapolated")
def data_002(analysis: Analysis) -> Outcome:
    baseline = registry.load_baseline()
    vintage = analysis.simulation.baseline_vintage if analysis.simulation else baseline.vintage
    findings: list[str] = []
    affected: list[str] = []

    when = vintage_date(vintage)
    if when is None:
        findings.append(f"The baseline vintage \"{vintage}\" does not say when it was published, so its age is "
                        "unknown.")
        affected.append("baseline.vintage")
    else:
        age = _months_between(when, analysis.created_at.date())
        if age > MAX_VINTAGE_AGE_MONTHS:
            findings.append(f"The baseline vintage \"{vintage}\" is {age} months old (limit "
                            f"{MAX_VINTAGE_AGE_MONTHS}).")
            affected.append("baseline.vintage")

    if baseline.extrapolated_from:
        findings.append(f"Baseline years after {baseline.extrapolated_from} are extrapolated, not official "
                        "forecasts.")
        affected.append("baseline.extrapolated")
    if analysis.simulation and analysis.simulation.scenarios:
        result = analysis.simulation.scenarios[0].result
        covered = {y.fiscal_year for y in baseline.years}
        beyond = [fy for fy in result.fiscal_years if fy not in covered]
        if beyond:
            findings.append(f"The baseline does not cover {listing(beyond)}; the engine held receipts flat there.")
            affected += [f"baseline.{fy}" for fy in beyond]
    if findings:
        return Outcome("issue", " ".join(findings), affected)
    return Outcome("pass", f"The baseline (\"{vintage}\") is under {MAX_VINTAGE_AGE_MONTHS} months old and covers "
                           "the horizon without extrapolation.")
