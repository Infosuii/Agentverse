import type { PolicySpec } from '../api/hooks';
import { fmtPp } from './format';

/**
 * Policy wording shared by every tab (contract-change #93). Corporation tax keeps its own econometric model; the taxes
 * and benefits in HMRC's ready reckoner (`tax_measure`) are modelled from official costings; any other fiscal policy
 * (`fiscal_other`) is researched and reported with the forecast withheld.
 */

type Policy = Pick<
  PolicySpec,
  | 'policy_type'
  | 'baseline_rate_pct'
  | 'proposed_rate_pct'
  | 'measure_id'
  | 'baseline_value'
  | 'proposed_value'
  | 'value_unit'
>;

/** The labels in data/curated/tax_measures.csv. */
export const MEASURE_LABELS: Record<string, string> = {
  income_tax_basic_rate: 'Income Tax basic rate',
  income_tax_higher_rate: 'Income Tax higher rate',
  income_tax_additional_rate: 'Income Tax additional rate',
  income_tax_personal_allowance: 'Income Tax Personal Allowance',
  nics_employee_main_rate: 'Employee National Insurance main rate',
  nics_employer_rate: 'Employer National Insurance rate',
  nics_class4_main_rate: 'Self-employed (Class 4) National Insurance rate',
  cgt_lower_rate: 'Capital Gains Tax lower rate',
  cgt_higher_rate: 'Capital Gains Tax higher rate',
  inheritance_tax_rate: 'Inheritance Tax rate',
  vat_standard_rate: 'VAT standard rate',
  vat_reduced_rate: 'VAT reduced rate',
  ipt_standard_rate: 'Insurance Premium Tax standard rate',
  fuel_duty: 'Fuel duty',
  alcohol_duty: 'Alcohol duties',
  tobacco_duty: 'Tobacco duties',
  child_benefit: 'Child Benefit',
};

const TYPE_LABELS: Record<string, string> = {
  corporation_tax_main_rate: 'Corporation tax · main rate',
  corporation_tax_small_profits_rate: 'Corporation tax · small profits rate',
  vat_standard_rate: 'VAT · standard rate',
  fiscal_other: 'Fiscal policy · research only',
  unsupported: 'Outside validated scope',
};

export function isCorporationTax(policy: Policy | null | undefined): boolean {
  return (
    policy?.policy_type === 'corporation_tax_main_rate' ||
    policy?.policy_type === 'corporation_tax_small_profits_rate'
  );
}

export function isResearchOnly(policy: Policy | null | undefined): boolean {
  return policy?.policy_type === 'fiscal_other';
}

function measureLabel(policy: Policy): string {
  const id = policy.measure_id ?? '';
  return MEASURE_LABELS[id] ?? (id ? id.replace(/_/g, ' ') : 'Tax measure');
}

/** "Corporation tax · main rate", "VAT standard rate", "Fiscal policy · research only". */
export function policyTypeLabel(policy: Policy | null | undefined): string | undefined {
  if (!policy?.policy_type) return undefined;
  if (policy.policy_type === 'tax_measure') return measureLabel(policy);
  return TYPE_LABELS[policy.policy_type] ?? policy.policy_type;
}

/** What the policy is about, for sentences: "UK corporation tax", "the VAT standard rate", "this fiscal policy". */
export function policyArea(policy: Policy | null | undefined): string {
  if (!policy || isCorporationTax(policy)) return 'UK corporation tax';
  if (policy.policy_type === 'tax_measure') {
    const label = measureLabel(policy);
    if (/_duty$/.test(policy.measure_id ?? '')) return label.toLowerCase(); // "fuel duty"
    if (policy.measure_id === 'child_benefit') return label;
    return `the ${label}`;
  }
  return 'this fiscal policy';
}

function fmtValue(v: number, unit: string): string {
  const n = v.toLocaleString('en-GB', { maximumFractionDigits: 2 });
  if (unit.startsWith('£/week')) return `£${n} a week`;
  if (unit.startsWith('£')) return `£${n}`;
  if (unit.startsWith('p/')) return `${n}p${unit.slice(1)}`;
  if (unit.startsWith('index')) return `${n} (index)`;
  return `${n} ${unit}`.trim();
}

function fmtSigned(delta: number, unit: string): string {
  const sign = delta > 0 ? '+' : delta < 0 ? '−' : '';
  const abs = Math.abs(delta).toLocaleString('en-GB', { maximumFractionDigits: 2 });
  if (unit.startsWith('£')) return `${sign}£${abs}`;
  if (unit.startsWith('p/')) return `${sign}${abs}p`;
  return `${sign}${abs}`;
}

/** The headline row label for the policy card: "Rate change", "Value change" or "Change". */
export function policyChangeLabel(policy: Policy | null | undefined): string {
  if (policy?.baseline_value != null || policy?.proposed_value != null) return 'Value change';
  if (isResearchOnly(policy)) return 'Change';
  return 'Rate change';
}

/** "25% → 28% (+3pp)", "£12,570 → £13,570 (+£1,000)", "Not modelled (research only)". */
export function policyChangeText(policy: Policy | null | undefined): string {
  if (!policy) return '—';
  if (isResearchOnly(policy)) return 'Not modelled (research only)';
  if (policy.baseline_value != null || policy.proposed_value != null) {
    const unit = policy.value_unit ?? '';
    const b = policy.baseline_value;
    const p = policy.proposed_value;
    const left = b != null ? fmtValue(b, unit) : '—';
    const right = p != null ? fmtValue(p, unit) : '—';
    if (b == null || p == null) return `${left} → ${right}`;
    if (unit.startsWith('index') && b !== 0) {
      const pct = ((p / b - 1) * 100).toLocaleString('en-GB', { maximumFractionDigits: 2 });
      return `${p > b ? '+' : p < b ? '−' : ''}${pct.replace('-', '')}% on the duty rate`;
    }
    return `${left} → ${right} (${fmtSigned(Number((p - b).toFixed(4)), unit)})`;
  }
  const b = policy.baseline_rate_pct;
  const p = policy.proposed_rate_pct;
  const change = b != null && p != null ? Number((p - b).toFixed(2)) : null;
  return `${b ?? '—'}% → ${p ?? '—'}% (${fmtPp(change)})`;
}
