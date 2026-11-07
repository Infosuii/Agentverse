import math

import pytest

from jane_avenue.contracts import MacroContext, PolicySpec
from jane_avenue.data import registry
from jane_avenue.precedents.match import WEIGHTS, find_precedents


def policy(**kwargs):
    return PolicySpec(policy_type='corporation_tax_main_rate', tax='corporation_tax',
                      baseline_rate_pct=25, proposed_rate_pct=28, **kwargs)


def test_rise_prefers_rise_and_includes_resolved_sources():
    result = find_precedents(policy(), k=16)
    assert result.matches[0].change.change_id == 'CT-MAIN-2023'
    assert all(0 <= m.similarity <= 1 for m in result.matches)
    assert [m.similarity for m in result.matches] == sorted((m.similarity for m in result.matches), reverse=True)
    sources = {s.source_id for s in result.sources}
    assert all(set(m.change.source_ids) <= sources for m in result.matches)
    assert any('Full expensing' in n for n in result.matches[0].comparability_notes)


def test_missing_macro_renormalises_exact_weights(monkeypatch):
    monkeypatch.setattr(registry, 'load_macro_context', lambda period: None)
    m = find_precedents(policy(), k=1).matches[0]
    assert set(m.similarity_breakdown) == {'direction', 'magnitude', 'rate_level', 'recency'}
    assert m.similarity_breakdown['magnitude'] == pytest.approx(math.exp(-1))
    expected = sum(WEIGHTS[k] * v for k, v in m.similarity_breakdown.items()) / .8
    assert m.similarity == pytest.approx(expected)
    assert any('renormalised' in n for n in m.comparability_notes)


def test_macro_z_distance_and_recession_note(monkeypatch):
    changes = registry.load_policy_changes()[-3:]
    for i, c in enumerate(changes):
        c.macro_context = MacroContext(period='2020-21', real_gdp_growth_pct=-1 + i,
                                      cpi_inflation_pct=2 + i, bank_rate_pct=3 + i)
    monkeypatch.setattr(registry, 'load_policy_changes', lambda tax: changes)
    monkeypatch.setattr(registry, 'load_macro_context', lambda period: changes[0].macro_context)
    result = find_precedents(policy())
    first = next(m for m in result.matches if m.change.change_id == changes[0].change_id)
    assert first.similarity_breakdown['macro_context'] == 1
    assert any('recession' in n for n in first.comparability_notes)
    assert all(len(m.similarity_breakdown) == 5 for m in result.matches)


def test_invalid_policy_and_k():
    assert not find_precedents(policy(), k=0).matches
    assert not find_precedents(PolicySpec(policy_type='vat_standard_rate', tax='vat')).matches
    with pytest.raises(ValueError):
        find_precedents(policy(), k=-1)
