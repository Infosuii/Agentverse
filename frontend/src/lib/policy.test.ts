import { describe, expect, it } from 'vitest';
import type { Analysis } from '../api/hooks';
import { policyArea, policyChangeText, policyTypeLabel } from './policy';
import { withheldReasons } from './reasons';

describe('policy wording (#93)', () => {
  it('labels corporation tax, measures and research-only policies', () => {
    expect(policyTypeLabel({ policy_type: 'corporation_tax_main_rate' })).toBe(
      'Corporation tax · main rate',
    );
    expect(policyTypeLabel({ policy_type: 'tax_measure', measure_id: 'vat_standard_rate' })).toBe(
      'VAT standard rate',
    );
    expect(policyTypeLabel({ policy_type: 'fiscal_other' })).toBe('Fiscal policy · research only');
    expect(policyArea({ policy_type: 'tax_measure', measure_id: 'fuel_duty' })).toBe('fuel duty');
    expect(policyArea({ policy_type: 'corporation_tax_main_rate' })).toBe('UK corporation tax');
  });

  it('describes rate, value and research-only changes', () => {
    expect(
      policyChangeText({
        policy_type: 'tax_measure',
        measure_id: 'vat_standard_rate',
        baseline_rate_pct: 20,
        proposed_rate_pct: 21,
      }),
    ).toBe('20% → 21% (+1pp)');
    expect(
      policyChangeText({
        policy_type: 'tax_measure',
        measure_id: 'income_tax_personal_allowance',
        baseline_value: 12570,
        proposed_value: 13570,
        value_unit: '£',
      }),
    ).toBe('£12,570 → £13,570 (+£1,000)');
    expect(
      policyChangeText({
        policy_type: 'tax_measure',
        measure_id: 'child_benefit',
        baseline_value: 27.05,
        proposed_value: 32.05,
        value_unit: '£/week',
      }),
    ).toBe('£27.05 a week → £32.05 a week (+£5)');
    expect(policyChangeText({ policy_type: 'fiscal_other' })).toBe('Not modelled (research only)');
  });
});

describe('withheldReasons', () => {
  it('lists each scope reason once when SCOPE-001 restates them all', () => {
    const reasons = [
      'This request is not a UK fiscal policy.',
      'The current and proposed rate could not be determined, so there is nothing to model.',
    ];
    const analysis = {
      scope: { forecast_allowed: false, reasons },
      verification: {
        decline_reasons: [reasons.join(' '), 'Calculation (CALC-001): something else'],
      },
    } as unknown as Analysis;
    expect(withheldReasons(analysis)).toEqual([...reasons, 'Calculation (CALC-001): something else']);
  });

  it('keeps verification reasons when the scope allowed the forecast', () => {
    const analysis = {
      scope: { forecast_allowed: true, reasons: [] },
      verification: { decline_reasons: ['Report (REPORT-001): unsupported number'] },
    } as unknown as Analysis;
    expect(withheldReasons(analysis)).toEqual(['Report (REPORT-001): unsupported number']);
  });
});
