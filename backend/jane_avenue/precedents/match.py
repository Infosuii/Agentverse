"""Deterministic historical similarity; comparisons are not causal estimates."""
from __future__ import annotations

import math
from datetime import date
from statistics import pstdev

from ..contracts import PolicySpec, PrecedentAnalysis, PrecedentMatch
from ..data import registry

WEIGHTS = {'direction': .30, 'magnitude': .25, 'rate_level': .15, 'macro_context': .20, 'recency': .10}
MACRO_FIELDS = ('real_gdp_growth_pct', 'cpi_inflation_pct', 'bank_rate_pct')


def find_precedents(spec: PolicySpec, *, k: int = 5) -> PrecedentAnalysis:
    if k < 0:
        raise ValueError('k must be nonnegative')
    if spec.policy_type in ('tax_measure', 'fiscal_other'):
        from .fiscal import find_fiscal_precedents

        return find_fiscal_precedents(spec, k=k)
    changes = [c for c in registry.load_policy_changes(spec.tax or 'corporation_tax')
               if c.policy_type == spec.policy_type]
    prop = spec.change_pp()
    latest = registry.load_macro_context('latest')
    scales = {}
    for field in MACRO_FIELDS:
        series = registry.load_series({'real_gdp_growth_pct': 'real_gdp_growth',
                                       'cpi_inflation_pct': 'cpi', 'bank_rate_pct': 'bank_rate'}[field])
        history = [p.value for p in series.points] if series else []
        scales[field] = pstdev(history) if len(history) > 1 else 0
    matches = []
    if prop is not None and spec.policy_type != 'unsupported':
        for c in changes:
            hist = c.new_rate_pct - c.old_rate_pct
            scores = dict(direction=float((hist > 0) - (hist < 0) == (prop > 0) - (prop < 0)),
                          magnitude=math.exp(-abs(abs(hist) - abs(prop)) / 3),
                          rate_level=math.exp(-abs(c.new_rate_pct - spec.proposed_rate_pct) / 5),
                          recency=math.exp(-max(0, (date.today() - c.effective_date).days / 365.25) / 25))
            notes = []
            if latest and c.macro_context and all(scales[f] > 0 and getattr(latest, f) is not None
                                                and getattr(c.macro_context, f) is not None for f in MACRO_FIELDS):
                distance = math.sqrt(sum(((getattr(c.macro_context, f) - getattr(latest, f)) / scales[f]) ** 2
                                         for f in MACRO_FIELDS))
                scores['macro_context'] = math.exp(-distance / 2)
            else:
                notes.append('Macro context unavailable or insufficient history; remaining weights renormalised.')
            if c.other_measures:
                notes.append('Simultaneous measures: ' + '; '.join(c.other_measures) + '.')
            if 'phased' in c.notes.lower() or 'phased' in ' '.join(c.other_measures).lower():
                notes.append('Part of a phased package; not an isolated rate experiment.')
            if 'reversed' in c.notes.lower():
                notes.append('Announced policy was reversed; no implemented-rate outcome can be attributed to it.')
            if c.macro_context and c.macro_context.real_gdp_growth_pct is not None and c.macro_context.real_gdp_growth_pct < 0:
                notes.append('Pre-change fiscal year was a recession year.')
            if c.effective_date.year == 2023:
                notes.append('Full expensing introduced in April 2023 confounds the main-rate comparison.')
            total_weight = sum(WEIGHTS[f] for f in scores)
            similarity = sum(WEIGHTS[f] * score for f, score in scores.items()) / total_weight
            matches.append(PrecedentMatch(change=c, similarity=similarity,
                                          similarity_breakdown=scores, comparability_notes=notes))
    matches.sort(key=lambda m: (-m.similarity, m.change.change_id))
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
    summary = (f'{len(matches)} historical changes ranked by direction, magnitude, rate level, macro context and recency. '
               'Official costings and observed outcomes are distinct evidence; similarity does not establish causation.'
               if matches else 'No comparable historical changes for this tax and policy type. No causal conclusion is drawn.')
    return PrecedentAnalysis(method='weighted-five-component-v1', dataset_version=registry.DATASET_VERSION,
                             matches=matches, summary=summary, sources=sources)
