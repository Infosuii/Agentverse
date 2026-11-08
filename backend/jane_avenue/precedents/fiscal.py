"""Precedents for every fiscal policy other than corporation tax (contract 1.2.0). Corporation tax stays in match.py.

Similarity uses the same five components and weights as corporation tax. A component that cannot be judged counts as neutral
(50%), so a sparse record cannot score highly: free-text policies have no size, and the OBR database often states no rates.
Changes with known rates rank ahead of announced measures without them, because they can be compared on the proposal's size.
Only changes that have already taken effect are matched.
Comparisons are descriptive and are not causal estimates.
"""
from __future__ import annotations

import math
import re
from datetime import date
from statistics import pstdev

from ..contracts import PolicyChange, PolicySpec, PrecedentAnalysis, PrecedentMatch
from ..data import registry
from .match import MACRO_FIELDS, WEIGHTS

_NO_EXCHEQUER_SIGN = {"overall_fiscal", "minimum_wage"}  # a rise here has no fixed effect on the public finances


def topic_key(spec: PolicySpec) -> str | None:
    """The fiscal topic a request belongs to: the measure itself, or the first topic whose pattern matches the words."""
    if spec.policy_type == "tax_measure":
        return spec.measure_id
    text = " ".join(spec.raw_query.lower().split())
    return next((t["policy_key"] for t in registry.load_fiscal_topics()
                 if t["query_pattern"] and re.search(t["query_pattern"], text)), None)


def _proposal(spec: PolicySpec, topic: dict) -> tuple[float | None, float | None, float | None, int]:
    """(change in points, change in percent of the old value, new value in points, Exchequer sign expected; 0 if unknown)."""
    from ..engine import reckoner
    from ..policy.measures import _direction

    if spec.policy_type == "tax_measure":
        measure = reckoner.get_measure(spec.measure_id)
        change = reckoner.change_units(spec, measure) if measure else None
        if measure is None or change is None:
            return None, None, None, 0
        sign = reckoner.expected_revenue_sign(spec)
        if measure.unit == "pp":
            return change, None, spec.proposed_rate_pct, sign
        if measure.unit == "pct_of_rate":
            return None, change, None, sign
        return None, 100.0 * change / spec.baseline_value if spec.baseline_value else None, None, sign  # type: ignore[arg-type]
    if topic["policy_key"] in _NO_EXCHEQUER_SIGN:
        return None, None, None, 0
    return None, None, None, _direction(" ".join(spec.raw_query.lower().split())) * int(topic["value_sign"])


def _value_sign(change: PolicyChange) -> int:
    if change.old_rate_pct is None or change.new_rate_pct is None:
        return 0
    return (change.new_rate_pct > change.old_rate_pct) - (change.new_rate_pct < change.old_rate_pct)


def _costing_sign(change: PolicyChange) -> int:
    first = next((c.value_gbp_bn for c in sorted(change.official_costings, key=lambda c: c.fiscal_year) if c.value_gbp_bn), 0.0)
    return (first > 0) - (first < 0)


def _macro_scales() -> dict[str, float]:
    ids = {"real_gdp_growth_pct": "real_gdp_growth", "cpi_inflation_pct": "cpi", "bank_rate_pct": "bank_rate"}
    scales = {}
    for field in MACRO_FIELDS:
        series = registry.load_series(ids[field])
        history = [p.value for p in series.points] if series else []
        scales[field] = pstdev(history) if len(history) > 1 else 0
    return scales


def _score(change: PolicyChange, spec: PolicySpec, topic: dict, latest, scales: dict[str, float]) -> PrecedentMatch:
    points, percent, level, sign = _proposal(spec, topic)
    scores: dict[str, float] = {
        "recency": math.exp(-max(0, (date.today() - change.effective_date).days / 365.25) / 25)}
    has_values = change.old_rate_pct is not None and change.new_rate_pct is not None
    same_kind = has_values and change.value_unit == "%" and points is not None
    threshold_only = change.value_unit == "£" and points is not None  # e.g. the IHT threshold against a change in the rate
    if sign and not threshold_only and (has_values or change.official_costings):
        actual = _value_sign(change) * int(topic["value_sign"]) if has_values else _costing_sign(change)
        if actual:
            scores["direction"] = float(actual == sign)
    if same_kind:
        scores["magnitude"] = math.exp(-abs(abs(change.new_rate_pct - change.old_rate_pct) - abs(points)) / 3)  # type: ignore[operator, arg-type]
        scores["rate_level"] = math.exp(-abs(change.new_rate_pct - level) / 5)  # type: ignore[operator, arg-type]
    elif has_values and percent is not None and change.old_rate_pct:
        historical = 100.0 * (change.new_rate_pct - change.old_rate_pct) / change.old_rate_pct  # type: ignore[operator]
        scores["magnitude"] = math.exp(-abs(abs(historical) - abs(percent)) / 3)
    notes: list[str] = []
    if latest and change.macro_context and all(scales[f] > 0 and getattr(latest, f) is not None
                                               and getattr(change.macro_context, f) is not None for f in MACRO_FIELDS):
        distance = math.sqrt(sum(((getattr(change.macro_context, f) - getattr(latest, f)) / scales[f]) ** 2 for f in MACRO_FIELDS))
        scores["macro_context"] = math.exp(-distance / 2)
    else:
        notes.append("Macro context unavailable or insufficient history; it counts as neutral.")
    if change.other_measures:
        notes.append("Simultaneous measures: " + "; ".join(change.other_measures) + ".")
    if change.notes.startswith("Reversed:"):
        notes.append("Announced policy did not take effect; no outcome can be attributed to it.")
    if threshold_only:
        notes.append("This was a change in a threshold, not in the tax rate; size and rate level are not compared.")
    if change.macro_context and change.macro_context.real_gdp_growth_pct is not None and change.macro_context.real_gdp_growth_pct < 0:
        notes.append("Pre-change fiscal year was a recession year.")
    if not change.official_costings and change.kind == "rate_series":
        notes.append("No single official costing could be identified for this change.")
    similarity = sum(weight * scores.get(name, 0.5) for name, weight in WEIGHTS.items())
    return PrecedentMatch(change=change, similarity=similarity, similarity_breakdown=scores, comparability_notes=notes)


def find_fiscal_precedents(spec: PolicySpec, *, k: int = 5) -> PrecedentAnalysis:
    key = topic_key(spec)
    topic = next((t for t in registry.load_fiscal_topics() if t["policy_key"] == key), None)
    changes = [c for c in registry.load_fiscal_changes(key) if c.effective_date <= date.today()] if key else []
    latest = registry.load_macro_context("latest")
    scales = _macro_scales()
    label = topic["label"] if topic else None
    matches = [_score(c, spec, topic, latest, scales) for c in changes] if topic else []
    # Announced measures that did not take effect cannot be compared with an actual change, so they sort last.
    matches.sort(key=lambda m: (m.change.notes.startswith("Reversed:"),
                                m.change.old_rate_pct is None and m.change.kind != "fiscal_event", -m.similarity, m.change.change_id))
    matches = matches[:k]
    ids = {sid for m in matches for sid in m.change.source_ids}
    for m in matches:
        ids.update(x.source_id for x in m.change.official_costings)
        ids.update(x.source_id for x in m.change.observed_outcomes)
        if m.change.macro_context:
            ids.update(m.change.macro_context.source_ids)
    if latest:
        ids.update(latest.source_ids)
    sources = [s for sid in sorted(ids) if (s := registry.get_source(sid)) is not None]
    if matches:
        summary = (f"{len(matches)} of {len(changes)} historical changes to {label} ranked by direction, magnitude, rate level, "
                   "macro context and recency, as far as each can be judged. Official costings and observed outcomes are "
                   "distinct evidence; similarity does not establish causation.")
    else:
        summary = (f"No UK measure for {label or 'this policy'} appears in the official sources used here, including the OBR "
                   "database of every tax measure since 1970 and every spending measure since 2010. No causal conclusion is drawn.")
    return PrecedentAnalysis(method="weighted-five-component-v1-fiscal", dataset_version=registry.DATASET_VERSION, matches=matches,
                             summary=summary, sources=sources, policy_key=key, policy_label=label)
