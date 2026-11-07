import hashlib
from pathlib import Path

import pandas as pd
import pytest
from jane_avenue.contracts import DatasetMeta, fiscal_year_range
from jane_avenue.data import registry

CURATED = Path(__file__).resolve().parents[3] / 'data' / 'curated'


def test_metadata_files_and_source_references():
    sources = {s.source_id for s in registry.list_sources()}
    for path in CURATED.glob('*.meta.json'):
        meta = DatasetMeta.model_validate_json(path.read_text())
        assert meta.source_id in sources
        assert (CURATED.parent / meta.file).exists()
        frame = pd.read_csv(CURATED / f'{meta.dataset_id}.csv', keep_default_na=False)
        for column in ('source_id', 'source_ids'):
            if column in frame:
                for cell in frame[column]:
                    assert set(registry._split(cell)) <= sources


def test_all_implemented_changes_match_contiguous_rate_history():
    frame = pd.read_csv(CURATED / 'ct_main_rate_history.csv').set_index('financial_year')
    assert list(frame.index) == list(range(1982, 2027))
    assert list(frame.fiscal_year) == fiscal_year_range('1982-83', 45)
    changes = registry.load_policy_changes()
    assert len(changes) == 16
    for c in changes:
        year = c.effective_date.year
        assert frame.loc[year - 1, 'main_rate_pct'] == c.old_rate_pct
        assert frame.loc[year, 'main_rate_pct'] == c.new_rate_pct
        assert not c.is_placeholder
    assert frame.loc[2017, 'main_rate_pct'] == 19  # reject stale Table A.6 forward row


def test_baseline_extrapolation_and_missing_nominal_flag():
    baseline = registry.load_baseline()
    official = pd.read_csv(CURATED / 'obr_baseline.csv')
    assert len(official) >= 6
    assert baseline.extrapolated_from == official.fiscal_year.iloc[-1]
    assert baseline.current_main_rate_pct == 25
    assert baseline.current_small_profits_rate_pct == 19
    assert baseline.is_placeholder  # real investment MUST NOT masquerade as nominal
    assert 'NOT NOMINAL' in baseline.notes
    last, extended = baseline.years[len(official) - 1:len(official) + 1]
    ratio = official.ct_receipts_gbp_bn.iloc[-1] / official.ct_receipts_gbp_bn.iloc[-2]
    assert extended.ct_receipts_gbp_bn == pytest.approx(last.ct_receipts_gbp_bn * ratio)
    with pytest.raises(ValueError, match='vintage'):
        registry.load_baseline('invented vintage')


def test_dataset_hash_and_defensive_loading():
    expected = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(CURATED.glob('*.csv')))).hexdigest()[:12]
    assert registry.DATASET_VERSION == expected
    first = registry.load_policy_changes()
    first[0].new_rate_pct = 99
    assert registry.load_policy_changes()[0].new_rate_pct != 99
    assert registry.get_source('made-up') is None
    assert registry.load_series('made-up') is None
    assert registry.load_policy_changes('vat') == []


def test_receipts_are_observations_and_have_outcomes():
    series = registry.load_series('ct_receipts')
    assert series and series.frequency == 'fiscal_year' and series.unit == '£bn'
    assert max(p.period for p in series.points) <= '2025-26'
    assert registry.load_policy_changes()[-1].observed_outcomes
