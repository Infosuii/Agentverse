"""Report check REPORT-001 (MASTER_PROMPT 9.7 and 9.8; agent-5 brief M2.5). Owner: agent-5.

Gemini writes report prose, but every number in it must come from code. Each digit sequence in the executive
summary, the section bodies and the caveats must be one of:

1. a `KeyFigure.display` (substituted from `{{fig:<id>}}`);
2. a cited evidence value, or a number in that evidence's verified quote, with the citation ([E1], or [S1] for any
   evidence from that source) in the same sentence;
3. a policy number: the current and proposed rates, the change in points, the horizon, the effective date, or a
   fiscal-year label of the modelled years;
4. a precedent fact from the curated dataset (old and new rates, the change, the year it took effect, official
   costings);
5. code-written verification text: the counts, the decline reasons, and the scope gate's reasons, warnings and
   validated bounds;
6. a scenario value (exact, or to 1-2 decimals) or the Monte Carlo draw count;
7. labels that are not quantities: section numbering, citation markers ([S3], [E1], footnotes), check IDs (CALC-001),
   precedent IDs (CT-MAIN-2023), percentiles (p5-p95), "Year 3", "t+1", "Tier 1", "FTSE 100" and URLs.

The references section is not checked (it holds URLs and access dates). The whitelist was agreed with agent-9 (#17).

Anything else fails, and the failure lists the offending snippets. Unsubstituted `{{fig:...}}` placeholders fail too.
"""
from __future__ import annotations

import re

from ...contracts import Analysis, PolicyAssessment, fiscal_year_of, fiscal_year_range
from ...policy.rules import normalise as _words_to_digits
from ._base import Outcome, check, plural

_FY = re.compile(r"\b((?:19|20)\d\d)\s*[-–/]\s*(\d\d)\b")
_PLACEHOLDER = re.compile(r"\{\{\s*fig:([^}]*)\}\}")
_CITATION = re.compile(r"\[\^?\d+\]|\[(?:[ESI]\d+|D-[\w-]+)(?:\s*[,;]\s*(?:[ESI]\d+|D-[\w-]+))*\]")
_CHECK_ID = re.compile(r"\b[A-Z]{3,8}-\d{3}\b")
_PRECEDENT_ID = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]+)*-\d{4}\b")
_PERCENTILE = re.compile(r"\bp\d{1,2}\b", re.I)
_LABELS = re.compile(r"\b(?:year|yr)\s+\d{1,2}\b|\bt\s*[+-]\s*\d{1,2}\b|\btier\s+[123]\b|\bftse\s+100\b", re.I)
_URL = re.compile(r"https?://\S+|www\.\S+")
UNCHECKED_SECTIONS = ("references", "sources", "bibliography")
_NUMBERING = re.compile(r"^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?\d+(?:\.\d+)*[.)]\s", re.M)
_NUMBER = re.compile(r"(?<![A-Za-z_\d.,])\d+(?:,\d{3})*(?:\.\d+)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z£(\[*_\"'])|\n+")
_EVIDENCE_REF = re.compile(r"\b([ES])(\d+)\b")
# Small counts are not quantities: "3 studies", "two fiscal events" (digits are written after number-word conversion).
SMALL_COUNT_MAX = 10
_COUNT = re.compile(
    r"(?<![\d.,])(\d{1,2})\s+"
    # An optional adjective ("4 major studies"), but never a unit: "8 percent cuts" is a quantity, not a count.
    r"(?:(?!(?:per|percent|percentage|pp|points?|bn|billion|m|million|k|thousand)\b)[a-z-]+\s+)?"
    r"(?:studies|study|sources?|papers?|reports?|documents?|estimates?|"
    r"events?|budgets?|years?|months?|quarters?|countries|firms|companies|precedents?|changes|rises|cuts|"
    r"scenarios?|parameters?|checks?|questions?|items?|steps?|channels?|reasons?|factors?)\b", re.I)
_HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)


def without_small_counts(text: str) -> str:
    """Remove small counts ("3 studies", "4 major studies"): an integer up to SMALL_COUNT_MAX followed by a count noun,
    with at most one non-unit word between. Quantities ("8 percent cuts", "3%") stay. Public so that research
    post-processing (agent-2) applies exactly the same rule as REPORT-001."""
    return _COUNT.sub(lambda m: " " if int(m.group(1)) <= SMALL_COUNT_MAX else m.group(0), text)


def _to_float(token: str) -> float:
    return float(token.replace(",", ""))


def _numbers(text: str) -> set[float]:
    text = _FY.sub(" ", text or "")
    return {_to_float(t) for t in _NUMBER.findall(text)}


def _matches(value: float, allowed: set[float]) -> bool:
    return any(abs(value - a) <= 1e-9 * max(1.0, abs(a)) for a in allowed)


def _close_to_evidence(value: float, evidence_value: float) -> bool:
    """A prose number may round an evidence value: 12.4 written as 12 or 12.4."""
    return abs(value - evidence_value) <= 1e-9 or abs(round(evidence_value) - value) <= 1e-9 \
        or abs(round(evidence_value, 1) - value) <= 1e-9 or abs(round(evidence_value, 2) - value) <= 1e-9


def _close_to_model(token: str, model_value: float) -> bool:
    """A scenario value may appear rounded to the decimals actually written, 1 or 2 (£11.9bn, £11.93bn), but never
    as a whole number: with dozens of modelled values, integer rounding would let almost any small number through."""
    value = _to_float(token)
    if abs(value - model_value) <= 1e-9:
        return True
    decimals = len(token.split(".", 1)[1]) if "." in token else 0
    return decimals in (1, 2) and abs(round(model_value, decimals) - value) <= 1e-9


def allowed_fiscal_years(analysis: Analysis, report: PolicyAssessment) -> set[str]:
    years: set[str] = {f.fiscal_year for f in report.key_figures if f.fiscal_year}
    if analysis.simulation:
        for s in analysis.simulation.scenarios:
            years.update(s.result.fiscal_years)
    policy = analysis.policy
    if policy and policy.effective_date:
        years.update(fiscal_year_range(fiscal_year_of(policy.effective_date), policy.horizon_years))
    if analysis.precedents:
        for m in analysis.precedents.matches:
            years.add(fiscal_year_of(m.change.effective_date))
            years.update(c.fiscal_year for c in m.change.official_costings)
            years.update(o.fiscal_year for o in m.change.observed_outcomes)
    return years


def allowed_numbers(analysis: Analysis, report: PolicyAssessment) -> set[float]:
    """Numbers allowed anywhere in the prose (whitelist items 1, 3, 4 and 5)."""
    allowed: set[float] = set()
    for f in report.key_figures:
        allowed |= _numbers(f.display)
    policy = analysis.policy
    if policy:
        for x in (policy.baseline_rate_pct, policy.proposed_rate_pct, policy.change_pp(), policy.horizon_years,
                  policy.baseline_value, policy.proposed_value):
            if x is not None:
                allowed |= {float(x), abs(float(x))}
        if policy.policy_type == "tax_measure":  # contract-change #93: the measure's own change and current rate
            from ...engine import reckoner

            if (m := reckoner.get_measure(policy.measure_id)) is not None:
                if (change := reckoner.change_units(policy, m)) is not None:
                    allowed |= {float(change), abs(float(change)), round(abs(float(change)), 2)}
                if m.current_value is not None:
                    allowed.add(float(m.current_value))
            if policy.baseline_value is not None and policy.proposed_value is not None:
                allowed.add(round(abs(policy.proposed_value - policy.baseline_value), 2))
        if policy.effective_date:
            allowed |= {float(policy.effective_date.day), float(policy.effective_date.year)}
        # The user's own words, which the report repeats in its title, the policy description and the parser notes
        # (e.g. "Read 'by 10%' as 10 percentage points" when no rate could be parsed).
        allowed |= _numbers(policy.raw_query)
    allowed |= _numbers(analysis.request.query)
    if analysis.precedents:
        if analysis.precedents.policy_key:  # the summary is fixed text from the matcher (contract 1.2.0)
            allowed |= _numbers(analysis.precedents.summary)
        for m in analysis.precedents.matches:
            c = m.change
            allowed.add(float(c.effective_date.year))
            if c.old_rate_pct is not None and c.new_rate_pct is not None:
                allowed |= {c.old_rate_pct, c.new_rate_pct, round(abs(c.new_rate_pct - c.old_rate_pct), 6),
                            round(abs(c.new_rate_pct - c.old_rate_pct), 2)}
            elif c.new_rate_pct is not None:
                allowed.add(c.new_rate_pct)
            if c.policy_key:  # the OBR's own wording and event names, quoted in the precedents section (contract 1.2.0)
                for text in (c.title, c.fiscal_event, *m.comparability_notes):
                    allowed |= _numbers(text or "")
            allowed |= {abs(x.value_gbp_bn) for x in c.official_costings}
            if c.announced_date:
                allowed.add(float(c.announced_date.year))
    if analysis.simulation and analysis.simulation.monte_carlo:
        allowed.add(float(analysis.simulation.monte_carlo.n_draws))
    if analysis.verification:
        allowed |= {float(v) for v in analysis.verification.counts.values()}
        allowed.add(float(len(analysis.verification.checks)))
        for reason in analysis.verification.decline_reasons:
            allowed |= _numbers(reason)
    if analysis.scope:
        for text in (*analysis.scope.reasons, *analysis.scope.warnings):
            allowed |= _numbers(text)
        allowed |= {x for x in (analysis.scope.validated_min_rate_pct, analysis.scope.validated_max_rate_pct,
                                analysis.scope.validated_max_change_pp) if x is not None}
    return allowed


def scenario_values(analysis: Analysis) -> list[float]:
    if analysis.simulation is None:
        return []
    return [abs(yv.value) for s in analysis.simulation.scenarios for m in s.result.metrics for yv in m.values]


def prose(report: PolicyAssessment) -> list[tuple[str, str]]:
    blocks = [("executive_summary", report.executive_summary)]
    blocks += [(f"section.{s.section_id}", s.body_markdown) for s in report.sections
               if s.section_id.lower() not in UNCHECKED_SECTIONS]
    blocks += [(f"caveat.{i}", c) for i, c in enumerate(report.caveats)]
    return [(loc, text) for loc, text in blocks if text]


def markdown_blocks(report: PolicyAssessment) -> list[tuple[str, str]]:
    """The downloadable `markdown`, split at headings, without the references section. Headings are kept (their
    numbering is ignored by the check) because the download shows them too."""
    text = report.markdown or ""
    starts = [m.start() for m in _HEADING.finditer(text)]
    if not starts or starts[0] != 0:
        starts = [0, *starts]
    blocks: list[tuple[str, str]] = []
    for i, start in enumerate(starts):
        chunk = text[start:starts[i + 1] if i + 1 < len(starts) else len(text)]
        heading = _HEADING.match(chunk)
        title = heading.group(1).strip() if heading else ""
        if any(word in title.lower() for word in UNCHECKED_SECTIONS):
            continue
        blocks.append((f"markdown:{title[:40] or 'top'}", chunk.replace("#", " ")))
    return [(loc, chunk) for loc, chunk in blocks if chunk.strip()]


def offending_numbers(analysis: Analysis, report: PolicyAssessment) -> list[tuple[str, str]]:
    """(location, snippet) for every number in the prose that code did not put there."""
    allowed = allowed_numbers(analysis, report)
    years = allowed_fiscal_years(analysis, report)
    evidence = analysis.research.evidence if analysis.research else []
    by_id = {e.evidence_id: e for e in evidence}
    modelled = scenario_values(analysis)
    found: list[tuple[str, str]] = []
    for location, text in [*prose(report), *markdown_blocks(report)]:
        for raw in _SENTENCE.split(text):
            sentence = raw.strip()
            if not sentence:
                continue
            cited = []
            for kind, num in _EVIDENCE_REF.findall(sentence):
                ref = f"{kind}{num}"
                cited += [by_id[ref]] if kind == "E" and ref in by_id else [e for e in evidence if e.source_id == ref]
            cited_values = {e.value for e in cited if e.value is not None}
            # Quotes may spell numbers out ("around ten per cent"): read them as digits too.
            quoted = set().union(*(_numbers(e.quote or "") | _numbers(_words_to_digits(e.quote or ""))
                                   for e in cited)) if cited else set()

            for m in _PLACEHOLDER.finditer(sentence):
                found.append((location, f"unsubstituted {m.group(0)}"))
            body = _PLACEHOLDER.sub(" ", sentence)
            body = _CITATION.sub(" ", body)
            body = _URL.sub(" ", body)
            body = _CHECK_ID.sub(" ", body)
            body = _PRECEDENT_ID.sub(" ", body)
            body = _PERCENTILE.sub(" ", body)
            body = _LABELS.sub(" ", body)
            body = _NUMBERING.sub(" ", body)
            body = without_small_counts(body)
            for m in _FY.finditer(body):
                label = f"{m.group(1)}-{m.group(2)}"
                if label not in years:
                    found.append((location, f"\"{label}\" in \"{sentence[:120]}\""))
            body = _FY.sub(" ", body)
            for token in _NUMBER.findall(body):
                value = _to_float(token)
                if _matches(value, allowed) or _matches(value, quoted) \
                        or any(_close_to_evidence(value, v) for v in cited_values) \
                        or any(_close_to_model(token, v) for v in modelled):
                    continue
                found.append((location, f"\"{token}\" in \"{sentence[:120]}\""))
    # The markdown repeats the sections: report a number found there only if the structured prose did not.
    structured = {snippet for loc, snippet in found if not loc.startswith("markdown:")}
    return [(loc, snippet) for loc, snippet in found
            if not (loc.startswith("markdown:") and snippet in structured)]


@check("REPORT-001", "report", "blocking", "rule", "Every number in the report comes from code")
def report_001(analysis: Analysis) -> Outcome:
    report = analysis.report
    if report is None:
        return Outcome("skipped", "No report has been generated yet.")
    found = offending_numbers(analysis, report)
    if found:
        shown = "; ".join(f"{loc}: {snippet}" for loc, snippet in found[:6])
        more = f" (and {len(found) - 6} more)" if len(found) > 6 else ""
        return Outcome("issue", f"{plural(len(found), 'number')} in the report prose did not come from a key figure, "
                                f"cited evidence or the policy: {shown}{more}.",
                       list(dict.fromkeys(loc for loc, _ in found)))
    return Outcome("pass", "Every number in the report prose comes from a key figure, cited evidence, the policy, a "
                           "precedent or the verification and scope results.")
