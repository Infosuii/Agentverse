"""Cached offline curated-data loaders. Owner: agent-6."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import get_settings
from ..contracts import (
    BaselineProjection,
    BaselineYear,
    Costing,
    DatasetMeta,
    MacroContext,
    ObservedOutcome,
    PolicyChange,
    Source,
    TimeSeries,
    TimeSeriesPoint,
    fiscal_year_range,
)


def _directory() -> Path:
    return get_settings().data_dir / 'curated'


def _version() -> str:
    h = hashlib.sha256()
    for file in sorted(_directory().glob('*.csv')):
        h.update(file.read_bytes())
    return h.hexdigest()[:12]


DATASET_VERSION = _version()


@lru_cache(maxsize=32)
def _read_csv(path: Path) -> tuple[dict, ...]:
    return tuple(pd.read_csv(path, keep_default_na=False).to_dict('records')) if path.exists() else ()


def _rows(name: str) -> tuple[dict, ...]:
    return _read_csv(_directory() / f'{name}.csv')


@lru_cache(maxsize=32)
def _read_meta(path: Path) -> DatasetMeta:
    return DatasetMeta.model_validate_json(path.read_text(encoding='utf-8'))


def _meta(name: str) -> DatasetMeta:
    return _read_meta(_directory() / f'{name}.meta.json')


def list_datasets() -> list[DatasetMeta]:
    return [_meta(p.name.removesuffix('.meta.json')).model_copy(deep=True)
            for p in sorted(_directory().glob('*.meta.json'))]


def _split(value) -> list[str]:
    return [s.strip() for s in str(value).split(';') if s.strip()]


def list_sources() -> list[Source]:
    return [Source(**dict(r, published_date=r.get('published_date') or None),
                   access_method='curated_dataset', url_verified=True)
            for name in ('sources', 'literature_sources') for r in _rows(name)]


def get_source(source_id: str) -> Source | None:
    return next((s for s in list_sources() if s.source_id == source_id), None)


def load_macro_context(period: str) -> MacroContext | None:
    rows = _rows('macro_annual')
    row = max(rows, key=lambda r: r['fiscal_year'], default=None) if period == 'latest' else next(
        (r for r in rows if r['fiscal_year'] == period), None)
    if row is None:
        return None
    return MacroContext(period=row['fiscal_year'], source_ids=_split(row.get('source_ids', '')),
                        **{k: row.get(k) if row.get(k) != '' else None for k in (
                            'real_gdp_growth_pct', 'cpi_inflation_pct', 'bank_rate_pct', 'unemployment_rate_pct')})


def load_policy_changes(tax: str = 'corporation_tax') -> list[PolicyChange]:
    if tax != 'corporation_tax':
        return []
    result = []
    for row in _rows('ct_policy_changes'):
        year = int(str(row['effective_date'])[:4])
        outcomes = []
        for dataset, metrics in [('ct_receipts', ('ct_receipts_gbp_bn', 'ct_receipts_pct_gdp')),
                                 ('macro_annual', ('business_investment_gbp_bn', 'real_gdp_growth_pct'))]:
            for r in _rows(dataset):
                if str(row['reversed']).lower() == 'true':
                    continue
                if int(str(r['fiscal_year'])[:4]) not in range(year - 1, year + 3):
                    continue
                for metric in metrics:
                    if r.get(metric, '') != '':
                        outcomes.append(ObservedOutcome(metric=metric, fiscal_year=r['fiscal_year'], value=r[metric],
                                                        source_id=r.get('source_id') or {
                                                            'business_investment_gbp_bn': 'D-ons-investment',
                                                            'real_gdp_growth_pct': 'D-ons-real-gdp'}[metric]))
        costings = [Costing(**{k: (r[k] if r[k] != '' else None) for k in Costing.model_fields})
                    for r in _rows('ct_costings') if r['change_id'] == row['change_id']]
        result.append(PolicyChange(
            change_id=row['change_id'], tax=tax, policy_type=row['policy_type'],
            announced_date=row['announced_date'] or None, fiscal_event=row['fiscal_event'] or None,
            effective_date=row['effective_date'], old_rate_pct=row['old_rate_pct'], new_rate_pct=row['new_rate_pct'],
            other_measures=_split(row['other_measures']), notes=row['notes'] +
            (' Official costing covers a joint phased package; it is not an isolated estimate for this rate step.'
             if row['change_id'] in ('CT-MAIN-2012', 'CT-MAIN-2013', 'CT-MAIN-2017') else '') +
            (' Reversed: announced change did not take effect.' if str(row['reversed']).lower() == 'true' else ''),
            macro_context=load_macro_context(fiscal_year_range(f'{year - 1}-00', 1)[0]),
            official_costings=costings, observed_outcomes=outcomes, source_ids=_split(row['source_ids']),
            is_placeholder=_meta('ct_policy_changes').is_placeholder))
    return sorted(result, key=lambda c: (c.effective_date, c.change_id))


def load_baseline(vintage: str = 'latest') -> BaselineProjection:
    meta = _meta('obr_baseline')
    if vintage not in ('latest', meta.vintage):
        raise ValueError(f'Unknown baseline vintage: {vintage}')
    fields = tuple(BaselineYear.model_fields)
    years = sorted([BaselineYear(**{k: r[k] for k in fields}) for r in _rows('obr_baseline')],
                   key=lambda y: y.fiscal_year)
    if len(years) < 2:
        raise ValueError('Baseline needs two official forecast years')
    horizon = years[-1].fiscal_year
    growth = {k: getattr(years[-1], k) / getattr(years[-2], k) for k in fields if k != 'fiscal_year'}
    for fy in fiscal_year_range(f'{int(horizon[:4]) + 1}-00', 10):
        years.append(BaselineYear(fiscal_year=fy, **{k: getattr(years[-1], k) * g for k, g in growth.items()}))
    rate = max(_rows('ct_main_rate_history'), key=lambda r: r['financial_year'])
    return BaselineProjection(vintage=meta.vintage, current_main_rate_pct=rate['main_rate_pct'],
                              current_small_profits_rate_pct=rate['small_profits_rate_pct'], years=years,
                              source_ids=sorted({r['source_id'] for r in _rows('obr_baseline')} |
                                                {'D-obr-databank', 'D-ons-investment', rate['source_id']}),
                              extrapolated_from=horizon, is_placeholder=meta.is_placeholder, notes=meta.notes +
                              ' Years after the official horizon extrapolate each series at its last annual growth rate.')


_SERIES = {
    'ct_receipts': ('ct_receipts', 'ct_receipts_gbp_bn', '£bn'),
    'ct_main_rate': ('ct_main_rate_history', 'main_rate_pct', '%'),
    'nominal_gdp': ('macro_annual', 'nominal_gdp_gbp_bn', '£bn'),
    'pnfc_gos': ('macro_annual', 'pnfc_gross_operating_surplus_gbp_bn', '£bn'),
    'bank_rate': ('macro_annual', 'bank_rate_pct', '%'),
    'real_gdp_growth': ('macro_annual', 'real_gdp_growth_pct', '%'),
    'cpi': ('macro_annual', 'cpi_inflation_pct', '%'),
    'business_investment': ('macro_annual', 'business_investment_gbp_bn', '£bn'),
}


def load_series(series_id: str) -> TimeSeries | None:
    if series_id == 'business_investment_by_asset':
        rows = _rows(series_id)
        if not rows:
            return None
        latest = max(r['year'] for r in rows)
        return TimeSeries(series_id=series_id, title=f'Investment shares {latest}', unit='fraction',
                          frequency='annual', dataset_id=series_id,
                          points=[TimeSeriesPoint(period=r['asset'], value=r['share']) for r in rows if r['year'] == latest])
    if series_id not in _SERIES:
        return None
    dataset, field, unit = _SERIES[series_id]
    points = [TimeSeriesPoint(period=r['fiscal_year'], value=r[field]) for r in _rows(dataset) if r.get(field, '') != '']
    return TimeSeries(series_id=series_id, title=series_id.replace('_', ' ').title(), unit=unit,
                      frequency='fiscal_year', dataset_id=dataset, points=points) if points else None
