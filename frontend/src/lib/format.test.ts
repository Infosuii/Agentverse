import { describe, expect, it } from 'vitest';
import { fmtDate, fmtFiscalYear, fmtGbpBn, fmtPct, fmtPp } from './format';

describe('format utilities', () => {
  describe('fmtGbpBn', () => {
    it('formats positive and negative GBP billions with Unicode minus', () => {
      expect(fmtGbpBn(3.1)).toBe('£3.1bn');
      expect(fmtGbpBn(-0.4)).toBe('−£0.4bn');
      expect(fmtGbpBn(0)).toBe('£0.0bn');
      expect(fmtGbpBn(-0.001)).toBe('£0.0bn');
      expect(fmtGbpBn(12.345, 2)).toBe('£12.35bn');
    });

    it('returns em-dash for null, undefined, or NaN', () => {
      expect(fmtGbpBn(null)).toBe('—');
      expect(fmtGbpBn(undefined)).toBe('—');
      expect(fmtGbpBn(Number.NaN)).toBe('—');
    });
  });

  describe('fmtPct', () => {
    it('formats percentages with configurable decimal places', () => {
      expect(fmtPct(-0.05)).toBe('−0.05%');
      expect(fmtPct(25, 1)).toBe('25.0%');
      expect(fmtPct(0, 2)).toBe('0.00%');
      expect(fmtPct(null)).toBe('—');
    });
  });

  describe('fmtPp', () => {
    it('formats percentage point changes with explicit sign', () => {
      expect(fmtPp(3)).toBe('+3pp');
      expect(fmtPp(-2)).toBe('−2pp');
      expect(fmtPp(0)).toBe('0pp');
      expect(fmtPp(1.5)).toBe('+1.5pp');
      expect(fmtPp(-1.25, 2)).toBe('−1.25pp');
      expect(fmtPp(undefined)).toBe('—');
    });
  });

  describe('fmtFiscalYear', () => {
    it('normalises fiscal years and dates into YYYY-YY', () => {
      expect(fmtFiscalYear('2027-28')).toBe('2027-28');
      expect(fmtFiscalYear('FY2027-28')).toBe('2027-28');
      expect(fmtFiscalYear('2027-2028')).toBe('2027-28');
      expect(fmtFiscalYear('2027-04-01')).toBe('2027-28');
      expect(fmtFiscalYear('2027-03-31')).toBe('2026-27');
      expect(fmtFiscalYear('2027')).toBe('2027-28');
      expect(fmtFiscalYear(null)).toBe('—');
    });
  });

  describe('fmtDate', () => {
    it('formats ISO dates in UK format', () => {
      expect(fmtDate('2027-04-01')).toBe('1 Apr 2027');
      expect(fmtDate(new Date('2026-11-07T16:45:00Z'))).toBe('7 Nov 2026');
      expect(fmtDate(null)).toBe('—');
    });
  });
});
