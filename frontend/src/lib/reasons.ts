import type { Analysis } from '../api/hooks';

/**
 * The reasons a quantitative forecast was withheld, each listed once.
 *
 * Scope reasons come first. Verification's SCOPE-001 decline reason restates all of them as one joined string, so a
 * decline reason is skipped when it only repeats the scope reasons. Without this, every scope reason was shown twice
 * (once inside the joined SCOPE-001 bullet, then again on its own). The backend report uses the same rule.
 */
export function withheldReasons(analysis: Analysis | null | undefined): string[] {
  if (!analysis) return [];
  const scopeReasons =
    analysis.scope?.forecast_allowed === false ? (analysis.scope.reasons ?? []) : [];
  const out = Array.from(new Set(scopeReasons));
  for (const r of analysis.verification?.decline_reasons ?? []) {
    if (out.includes(r)) continue;
    if (scopeReasons.length > 0 && scopeReasons.every((s) => r.includes(s.replace(/\.$/, '')))) continue;
    out.push(r);
  }
  return out;
}
