import { describe, expect, it } from 'vitest';
import type { PolicyChange, PrecedentMatch } from '../../api/hooks';
import { buildRateTimeline, changeText, timelineSeries } from './PrecedentsTab';

function change(over: Partial<PolicyChange>): PolicyChange {
  return {
    change_id: 'X',
    tax: 'other',
    policy_type: 'tax_measure',
    effective_date: '2011-01-04',
    old_rate_pct: 17.5,
    new_rate_pct: 20,
    other_measures: [],
    official_costings: [],
    observed_outcomes: [],
    notes: '',
    source_ids: ['S'],
    is_placeholder: false,
    kind: 'rate_series',
    title: 'Standard rate',
    value_unit: '%',
    ...over,
  } as PolicyChange;
}

describe('changeText', () => {
  it('shows percentage points for rates', () => {
    expect(changeText(change({}))).toContain('17.5% → 20%');
  });
  it('uses the unit of the rate for other measures', () => {
    expect(changeText(change({ old_rate_pct: 11850, new_rate_pct: 12500, value_unit: '£' }))).toBe('£11,850 → £12,500');
    expect(changeText(change({ old_rate_pct: 57.95, new_rate_pct: 52.95, value_unit: 'p/litre' }))).toBe('57.95 → 52.95 p/litre');
  });
  it('is empty when the source states no values', () => {
    expect(changeText(change({ old_rate_pct: null, new_rate_pct: null, value_unit: null }))).toBe('');
  });
});

describe('timelines for other policies', () => {
  const beer = change({ change_id: 'B', title: 'Beer', value_unit: '£/litre of pure alcohol' });
  const spirits = change({ change_id: 'S', title: 'Spirits', value_unit: '£/litre of pure alcohol' });
  const announced = change({ change_id: 'O', kind: 'announced_measure', title: 'A measure', old_rate_pct: null, new_rate_pct: null });

  it('shows one series, chosen by the best match', () => {
    const matches = [{ change: spirits }] as PrecedentMatch[];
    expect(timelineSeries([beer, spirits, announced], matches)).toEqual([spirits]);
  });
  it('skips records with no values and starts at the first change', () => {
    const { points } = buildRateTimeline([announced, change({})], new Set(), null);
    expect(points[0].year).toBe(2011);
    expect(points[0].ratePct).toBe(20);
  });
  it('ignores measures with no rates entirely', () => {
    expect(buildRateTimeline([announced], new Set(), null).points).toEqual([]);
  });
});
