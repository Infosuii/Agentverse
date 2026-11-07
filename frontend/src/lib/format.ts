/**
 * Formatting utilities for Jane Avenue (MASTER_PROMPT §9.10).
 * Uses Unicode minus '−' (\u2212) for negative numbers.
 */

const MINUS = '−';

/**
 * Format £ billions: fmtGbpBn(3.1) -> "£3.1bn", fmtGbpBn(-0.4) -> "−£0.4bn"
 */
export function fmtGbpBn(value: number | null | undefined, dp = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  const rounded = Number(value.toFixed(dp));
  const absStr = Math.abs(rounded).toFixed(dp);
  if (rounded < 0) {
    return `${MINUS}£${absStr}bn`;
  }
  return `£${absStr}bn`;
}

/**
 * Format percentage: fmtPct(-0.05, 2) -> "−0.05%", fmtPct(25, 1) -> "25.0%"
 */
export function fmtPct(value: number | null | undefined, dp = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  const rounded = Number(value.toFixed(dp));
  const absStr = Math.abs(rounded).toFixed(dp);
  if (rounded < 0) {
    return `${MINUS}${absStr}%`;
  }
  return `${absStr}%`;
}

/**
 * Format percentage-point change: fmtPp(3) -> "+3pp", fmtPp(-2) -> "−2pp"
 */
export function fmtPp(value: number | null | undefined, dp?: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  const effectiveDp = dp !== undefined ? dp : Number.isInteger(value) ? 0 : 2;
  const rounded = Number(value.toFixed(effectiveDp));
  const absStr =
    dp !== undefined
      ? Math.abs(rounded).toFixed(dp)
      : Number(Math.abs(rounded).toFixed(effectiveDp)).toString();
  if (rounded > 0) {
    return `+${absStr}pp`;
  }
  if (rounded < 0) {
    return `${MINUS}${absStr}pp`;
  }
  return `${absStr}pp`;
}

/**
 * Format or normalise a UK fiscal year string ("2027-28").
 * Accepts "2027-28", "FY2027-28", "2027-2028", "2027", or ISO date "2027-04-01".
 */
export function fmtFiscalYear(input: string | null | undefined): string {
  if (!input) {
    return '—';
  }
  const trimmed = input.trim();
  if (!trimmed) {
    return '—';
  }
  const fyShort = /^(\d{4})-(\d{2})$/.exec(trimmed);
  if (fyShort) {
    return `${fyShort[1]}-${fyShort[2]}`;
  }
  const fyPrefix = /^FY\s*(\d{4})-(\d{2})$/i.exec(trimmed);
  if (fyPrefix) {
    return `${fyPrefix[1]}-${fyPrefix[2]}`;
  }
  const fyLong = /^(\d{4})-(\d{4})$/.exec(trimmed);
  if (fyLong) {
    return `${fyLong[1]}-${fyLong[2].slice(-2)}`;
  }
  const isoDate = /^(\d{4})-(\d{2})-(\d{2})/.exec(trimmed);
  if (isoDate) {
    const year = Number(isoDate[1]);
    const month = Number(isoDate[2]);
    const day = Number(isoDate[3]);
    const startYear = month > 4 || (month === 4 && day >= 1) ? year : year - 1;
    return `${startYear}-${String(startYear + 1).slice(-2)}`;
  }
  const singleYear = /^(\d{4})$/.exec(trimmed);
  if (singleYear) {
    const startYear = Number(singleYear[1]);
    return `${startYear}-${String(startYear + 1).slice(-2)}`;
  }
  return trimmed;
}

/**
 * Format an ISO date or Date into UK short readable format ("1 Apr 2027").
 */
export function fmtDate(input: string | Date | null | undefined): string {
  if (!input) {
    return '—';
  }
  const dateObj =
    input instanceof Date
      ? input
      : /^\d{4}-\d{2}-\d{2}$/.test(input.trim())
        ? new Date(`${input.trim()}T00:00:00Z`)
        : new Date(input);

  if (Number.isNaN(dateObj.getTime())) {
    return typeof input === 'string' ? input : '—';
  }
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(dateObj);
}
