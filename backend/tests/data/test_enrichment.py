import pandas as pd
import pytest

from jane_avenue.data import registry


def test_macro_and_asset_series_are_available_and_sources_resolve():
    for sid in ('ct_receipts', 'nominal_gdp', 'pnfc_gos', 'bank_rate', 'real_gdp_growth',
                'cpi', 'business_investment', 'ct_main_rate'):
        series = registry.load_series(sid)
        assert series and series.frequency == 'fiscal_year'
        assert series.points == sorted(series.points, key=lambda p: p.period)
        assert all(p.period <= '2026-27' for p in series.points)
    shares = registry.load_series('business_investment_by_asset')
    assert shares and '2025' in shares.title
    assert {p.period for p in shares.points} == {'plant_machinery', 'structures', 'intangibles'}
    assert sum(p.value for p in shares.points) == pytest.approx(1)
    frame = pd.DataFrame(registry._rows('business_investment_by_asset'))
    assert frame.groupby('year')['share'].sum().to_list() == pytest.approx([1] * frame.year.nunique())
    assert frame[frame.year == 2025].value_gbp_bn.sum() == pytest.approx(323.375)  # ONS NPEK £323,375m


def test_original_costings_are_distinct_from_updated_database_effects():
    changes = {c.change_id: c for c in registry.load_policy_changes()}
    costing = next(c for c in changes['CT-MAIN-2023'].official_costings if c.fiscal_year == '2025-26')
    assert costing.value_gbp_bn == 17.2  # HMT Budget 2021 table 2.1, row 22
    assert costing.source_id == 'D-budget2021'
    assert all(c.value_gbp_bn <= 0 for c in changes['CT-MAIN-2017'].official_costings)
    assert all(c.includes_behavioural is None for c in changes['CT-MAIN-2017'].official_costings)
    assert changes['CT-MAIN-2023'].macro_context.period == '2022-23'
    assert not changes['CT-MAIN-2020-REVERSED'].observed_outcomes
    assert not any(m.is_placeholder for m in registry.list_datasets())


def test_nominal_baseline_anchor_and_price_basis():
    baseline = registry.load_baseline()
    macro = {r['fiscal_year']: r for r in registry._rows('macro_annual')}
    assert baseline.years[0].business_investment_gbp_bn == pytest.approx(
        float(macro[baseline.years[0].fiscal_year]['business_investment_gbp_bn']))
    assert 'GDP deflator proxies' in baseline.notes


def test_csv_cache_respects_data_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(registry, '_directory', lambda: tmp_path)
    assert registry.load_policy_changes() == []
    assert registry.get_source('D-hmrc-history') is None
