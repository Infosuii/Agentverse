/**
 * Design tokens for Jane Avenue (MASTER_PROMPT §9.10).
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
  color: '#2563eb',
  p5_p95_opacity: 0.12,
  p25_p75_opacity: 0.25,
  // Aliases for convenience across chart wrappers
  outerOpacity: 0.12,
  innerOpacity: 0.25,
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
    color: '#334155',
    label: 'Observed outcome',
    shortLabel: 'Observed',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-800',
    borderClass: 'border-slate-300',
  },
  official_costing: {
    color: '#6d28d9',
    label: 'Official costing',
    shortLabel: 'Official costing',
    bgClass: 'bg-violet-50',
    textClass: 'text-violet-800',
    borderClass: 'border-violet-300',
  },
  model_scenario: {
    color: '#1d4ed8',
    label: 'Model scenario',
    shortLabel: 'Model scenario',
    bgClass: 'bg-blue-50',
    textClass: 'text-blue-800',
    borderClass: 'border-blue-300',
  },
  assumption: {
    color: '#b45309',
    label: 'Assumption',
    shortLabel: 'Assumption',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-300',
  },
  ai_interpretation: {
    color: '#be123c',
    label: 'AI interpretation',
    shortLabel: 'AI interpretation',
    bgClass: 'bg-rose-50',
    textClass: 'text-rose-800',
    borderClass: 'border-rose-300',
  },
} as const;

export const EVIDENCE_CLASS_COLORS: Record<EvidenceClassKey, string> = {
  observed_outcome: '#334155',
  official_costing: '#6d28d9',
  model_scenario: '#1d4ed8',
  assumption: '#b45309',
  ai_interpretation: '#be123c',
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
    color: '#16a34a',
    label: 'Pass',
    symbol: '✓',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-800',
    borderClass: 'border-emerald-300',
  },
  warn: {
    color: '#d97706',
    label: 'Warning',
    symbol: '!',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-300',
  },
  fail: {
    color: '#dc2626',
    label: 'Failed',
    symbol: '✕',
    bgClass: 'bg-red-50',
    textClass: 'text-red-800',
    borderClass: 'border-red-300',
  },
  skipped: {
    color: '#64748b',
    label: 'Skipped',
    symbol: '–',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-600',
    borderClass: 'border-slate-300',
  },
} as const;

export const VERIFICATION_STATUS_COLORS: Record<VerificationStatusKey, string> = {
  pass: '#16a34a',
  warn: '#d97706',
  fail: '#dc2626',
  skipped: '#64748b',
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
    color: '#16a34a',
    label: 'Approved',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-800',
    borderClass: 'border-emerald-300',
  },
  approved_with_warnings: {
    color: '#d97706',
    label: 'Approved with warnings',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-300',
  },
  forecast_withheld: {
    color: '#dc2626',
    label: 'Quantitative forecast withheld',
    bgClass: 'bg-red-50',
    textClass: 'text-red-800',
    borderClass: 'border-red-300',
  },
} as const;

export const WITHHELD_HATCH_CLASS = 'withheld-hatch';

export const THEME = {
  scenarios: SCENARIO_COLORS,
  scenarioLabels: SCENARIO_LABELS,
  mcBands: MC_BAND_STYLE,
  evidenceClass: EVIDENCE_CLASS_TOKENS,
  evidenceColors: EVIDENCE_CLASS_COLORS,
  evidenceLabels: EVIDENCE_CLASS_LABELS,
  verification: VERIFICATION_STATUS_TOKENS,
  verificationColors: VERIFICATION_STATUS_COLORS,
  verificationOverall: VERIFICATION_OVERALL_TOKENS,
  withheldHatchClass: WITHHELD_HATCH_CLASS,
} as const;
