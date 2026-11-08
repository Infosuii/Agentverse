/**
 * Design tokens for Jane Avenue (MASTER_PROMPT §9.10), tuned for the
 * Forecast Confidence Studio palette defined in `src/index.css`.
 *
 * - Scenario colours keep the exact contract hex values (charts and tests rely on them).
 * - Evidence-class and verification colours keep the contract hue families
 *   (slate / violet / blue / amber / rose; green / amber / red / grey) but use lighter
 *   shades so dots, lines and badges stay legible on the dark surfaces.
 * - Chart chrome reads CSS variables so the print stylesheet can switch to light ink.
 */

export type ScenarioColorKey = 'central' | 'optimistic' | 'pessimistic' | 'custom';

export type EvidenceClassKey =
  | 'observed_outcome'
  | 'official_costing'
  | 'model_scenario'
  | 'assumption'
  | 'ai_interpretation';

export type VerificationStatusKey = 'pass' | 'warn' | 'fail' | 'skipped';

export type VerificationOverallKey =
  | 'approved'
  | 'approved_with_warnings'
  | 'forecast_withheld';

export const SCENARIO_COLORS: Record<ScenarioColorKey, string> = {
  central: '#2563eb',
  optimistic: '#16a34a',
  pessimistic: '#dc2626',
  custom: '#7c3aed',
} as const;

export const SCENARIO_LABELS: Record<ScenarioColorKey, string> = {
  central: 'Central',
  optimistic: 'Optimistic',
  pessimistic: 'Pessimistic',
  custom: 'Custom',
} as const;

export const MC_BAND_STYLE = {
  color: 'var(--ev-model)',
  p5_p95_opacity: 0.16,
  p25_p75_opacity: 0.3,
  // Aliases for convenience across chart wrappers
  outerOpacity: 0.16,
  innerOpacity: 0.3,
} as const;

/** Shared Recharts chrome (grid, axes, tooltips) driven by the CSS design tokens. */
export const CHART_THEME = {
  grid: 'var(--border)',
  tick: 'var(--muted-foreground)',
  axisLabel: 'var(--muted-foreground)',
  reference: 'var(--muted-foreground)',
  cursor: 'var(--muted)',
  neutral: 'var(--chart-neutral)',
  neutralMuted: 'var(--chart-neutral-muted)',
  tooltip: {
    backgroundColor: 'var(--popover)',
    color: 'var(--popover-foreground)',
    border: '1px solid var(--border)',
    borderRadius: 2,
    fontSize: 12,
  },
  tooltipLabel: {
    color: 'var(--popover-foreground)',
    fontWeight: 500,
  },
  legend: {
    fontSize: 12,
    color: 'var(--muted-foreground)',
  },
} as const;

export const EVIDENCE_CLASS_TOKENS: Record<
  EvidenceClassKey,
  {
    color: string;
    label: string;
    shortLabel: string;
    bgClass: string;
    textClass: string;
    borderClass: string;
  }
> = {
  observed_outcome: {
    color: 'var(--ev-observed)',
    label: 'Observed outcome',
    shortLabel: 'Observed',
    bgClass: 'bg-slate-400/10',
    textClass: 'text-slate-200',
    borderClass: 'border-slate-400/35',
  },
  official_costing: {
    color: 'var(--ev-costing)',
    label: 'Official costing',
    shortLabel: 'Official costing',
    bgClass: 'bg-violet-500/10',
    textClass: 'text-violet-300',
    borderClass: 'border-violet-400/35',
  },
  model_scenario: {
    color: 'var(--ev-model)',
    label: 'Model scenario',
    shortLabel: 'Model scenario',
    bgClass: 'bg-blue-500/10',
    textClass: 'text-blue-300',
    borderClass: 'border-blue-400/35',
  },
  assumption: {
    color: 'var(--ev-assumption)',
    label: 'Assumption',
    shortLabel: 'Assumption',
    bgClass: 'bg-amber-500/10',
    textClass: 'text-amber-300',
    borderClass: 'border-amber-400/35',
  },
  ai_interpretation: {
    color: 'var(--ev-ai)',
    label: 'AI interpretation',
    shortLabel: 'AI interpretation',
    bgClass: 'bg-rose-500/10',
    textClass: 'text-rose-300',
    borderClass: 'border-rose-400/35',
  },
} as const;

export const EVIDENCE_CLASS_COLORS: Record<EvidenceClassKey, string> = {
  observed_outcome: EVIDENCE_CLASS_TOKENS.observed_outcome.color,
  official_costing: EVIDENCE_CLASS_TOKENS.official_costing.color,
  model_scenario: EVIDENCE_CLASS_TOKENS.model_scenario.color,
  assumption: EVIDENCE_CLASS_TOKENS.assumption.color,
  ai_interpretation: EVIDENCE_CLASS_TOKENS.ai_interpretation.color,
} as const;

export const EVIDENCE_CLASS_LABELS: Record<EvidenceClassKey, string> = {
  observed_outcome: 'Observed outcome',
  official_costing: 'Official costing',
  model_scenario: 'Model scenario',
  assumption: 'Assumption',
  ai_interpretation: 'AI interpretation',
} as const;

export const VERIFICATION_STATUS_TOKENS: Record<
  VerificationStatusKey,
  {
    color: string;
    label: string;
    symbol: string;
    bgClass: string;
    textClass: string;
    borderClass: string;
  }
> = {
  pass: {
    color: 'var(--st-pass)',
    label: 'Pass',
    symbol: '✓',
    bgClass: 'bg-emerald-500/10',
    textClass: 'text-emerald-300',
    borderClass: 'border-emerald-400/35',
  },
  warn: {
    color: 'var(--ev-assumption)',
    label: 'Warning',
    symbol: '!',
    bgClass: 'bg-amber-500/10',
    textClass: 'text-amber-300',
    borderClass: 'border-amber-400/35',
  },
  fail: {
    color: 'var(--st-fail)',
    label: 'Failed',
    symbol: '✕',
    bgClass: 'bg-red-500/10',
    textClass: 'text-red-300',
    borderClass: 'border-red-400/35',
  },
  skipped: {
    color: 'var(--chart-neutral)',
    label: 'Skipped',
    symbol: '–',
    bgClass: 'bg-slate-400/10',
    textClass: 'text-slate-300',
    borderClass: 'border-slate-400/30',
  },
} as const;

export const VERIFICATION_STATUS_COLORS: Record<VerificationStatusKey, string> = {
  pass: VERIFICATION_STATUS_TOKENS.pass.color,
  warn: VERIFICATION_STATUS_TOKENS.warn.color,
  fail: VERIFICATION_STATUS_TOKENS.fail.color,
  skipped: VERIFICATION_STATUS_TOKENS.skipped.color,
} as const;

export const VERIFICATION_OVERALL_TOKENS: Record<
  VerificationOverallKey,
  {
    color: string;
    label: string;
    bgClass: string;
    textClass: string;
    borderClass: string;
  }
> = {
  approved: {
    color: 'var(--st-pass)',
    label: 'Approved',
    bgClass: 'bg-emerald-500/10',
    textClass: 'text-emerald-300',
    borderClass: 'border-emerald-400/35',
  },
  approved_with_warnings: {
    color: 'var(--ev-assumption)',
    label: 'Approved with warnings',
    bgClass: 'bg-amber-500/10',
    textClass: 'text-amber-300',
    borderClass: 'border-amber-400/35',
  },
  forecast_withheld: {
    color: 'var(--st-fail)',
    label: 'Quantitative forecast withheld',
    bgClass: 'bg-red-500/10',
    textClass: 'text-red-300',
    borderClass: 'border-red-400/35',
  },
} as const;

export const WITHHELD_HATCH_CLASS = 'withheld-hatch';

export const THEME = {
  scenarios: SCENARIO_COLORS,
  scenarioLabels: SCENARIO_LABELS,
  mcBands: MC_BAND_STYLE,
  chart: CHART_THEME,
  evidenceClass: EVIDENCE_CLASS_TOKENS,
  evidenceColors: EVIDENCE_CLASS_COLORS,
  evidenceLabels: EVIDENCE_CLASS_LABELS,
  verification: VERIFICATION_STATUS_TOKENS,
  verificationColors: VERIFICATION_STATUS_COLORS,
  verificationOverall: VERIFICATION_OVERALL_TOKENS,
  withheldHatchClass: WITHHELD_HATCH_CLASS,
} as const;
