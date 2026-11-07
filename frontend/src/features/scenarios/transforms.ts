import type {
  Assumption,
  Confidence,
  Histogram,
  MetricDistribution,
  MetricName,
  MetricProjection,
  PolicySpec,
  ScenarioResult,
  SensitivityResult,
  SimulationBundle,
} from '../../api/hooks';
import { SCENARIO_COLORS, SCENARIO_LABELS, type ScenarioColorKey } from '../../lib/theme';
import type { EmpiricalBandPoint, FanBandPoint, LineChartSeries, TornadoInputItem } from '../../components/charts';

export interface MetricDescriptor {
  metric: MetricName;
  label: string;
  shortLabel: string;
  unit: '£bn' | '%';
  confidence: Confidence;
  lowConfidenceNote?: string;
}

export const METRIC_DESCRIPTORS: readonly MetricDescriptor[] = [
  {
    metric: 'revenue_behavioural_gbp_bn',
    label: 'Behavioural revenue change',
    shortLabel: 'Behavioural revenue',
    unit: '£bn',
    confidence: 'medium',
  },
  {
    metric: 'revenue_static_gbp_bn',
    label: 'Static revenue change',
    shortLabel: 'Static revenue',
    unit: '£bn',
    confidence: 'high',
  },
  {
    metric: 'revenue_dynamic_gbp_bn',
    label: 'Dynamic revenue change',
    shortLabel: 'Dynamic revenue',
    unit: '£bn',
    confidence: 'low',
    lowConfidenceNote: 'low confidence: indicative',
  },
  {
    metric: 'business_investment_pct',
    label: 'Business investment change (%)',
    shortLabel: 'Business investment (%)',
    unit: '%',
    confidence: 'medium',
  },
  {
    metric: 'business_investment_gbp_bn',
    label: 'Business investment change (£bn)',
    shortLabel: 'Business investment (£bn)',
    unit: '£bn',
    confidence: 'medium',
  },
  {
    metric: 'gdp_level_pct',
    label: 'GDP level change (%)',
    shortLabel: 'GDP level (%)',
    unit: '%',
    confidence: 'low',
    lowConfidenceNote: 'low confidence: indicative',
  },
  {
    metric: 'cost_of_capital_pct',
    label: 'Cost of capital change (%)',
    shortLabel: 'Cost of capital (%)',
    unit: '%',
    confidence: 'medium',
  },
] as const;

export function getMetricDescriptor(
  metric: MetricName,
  projection?: MetricProjection,
): MetricDescriptor {
  const base =
    METRIC_DESCRIPTORS.find((m) => m.metric === metric) ?? METRIC_DESCRIPTORS[0];
  return {
    ...base,
    label: projection?.label || base.label,
    unit: (projection?.unit as '£bn' | '%') || base.unit,
    confidence: projection?.confidence || base.confidence,
    lowConfidenceNote:
      (projection?.confidence ?? base.confidence) === 'low'
        ? 'low confidence: indicative'
        : base.lowConfidenceNote,
  };
}

export function buildScenarioSeries(
  bundle: SimulationBundle | null | undefined,
  metric: MetricName,
  customBundle?: SimulationBundle | null,
): LineChartSeries[] {
  if (!bundle?.scenarios || bundle.scenarios.length === 0) {
    return [];
  }

  const order: ScenarioColorKey[] = ['central', 'optimistic', 'pessimistic', 'custom'];
  const byName = new Map<string, ScenarioResult>();
  for (const s of bundle.scenarios) {
    byName.set(s.scenario.name, s);
  }

  const series: LineChartSeries[] = [];

  for (const key of order) {
    if (key === 'custom' && customBundle) {
      // Handled below from customBundle if present
      continue;
    }
    const scen = byName.get(key);
    if (!scen) continue;
    const proj = scen.result.metrics.find((m) => m.metric === metric);
    if (!proj || proj.values.length === 0) continue;

    series.push({
      id: key,
      label: scen.scenario.label || SCENARIO_LABELS[key],
      color: SCENARIO_COLORS[key],
      dashed: key === 'custom',
      points: proj.values.map((v) => ({ x: v.fiscal_year, y: v.value })),
    });
  }

  if (customBundle?.scenarios && customBundle.scenarios.length > 0) {
    const customScen =
      customBundle.scenarios.find((s) => s.scenario.name === 'custom') ??
      customBundle.scenarios.find((s) => s.scenario.name === 'central') ??
      customBundle.scenarios[0];
    const proj = customScen?.result.metrics.find((m) => m.metric === metric);
    if (proj && proj.values.length > 0) {
      series.push({
        id: 'custom',
        label: 'Custom (slider override)',
        color: SCENARIO_COLORS.custom,
        dashed: true,
        points: proj.values.map((v) => ({ x: v.fiscal_year, y: v.value })),
      });
    }
  }

  return series;
}

export function buildFanBands(
  bundle: SimulationBundle | null | undefined,
  metric: MetricName,
): {
  bands: FanBandPoint[];
  intervalNote: string;
  empiricalBands: EmpiricalBandPoint[];
  empiricalCalibrationNote: string | null;
  distribution: MetricDistribution | undefined;
} {
  const mc = bundle?.monte_carlo;
  const dist = mc?.distributions?.find((d) => d.metric === metric);
  const bands: FanBandPoint[] = (dist?.bands ?? []).map((b) => ({
    x: b.fiscal_year,
    p5: b.p5,
    p25: b.p25,
    p50: b.p50,
    p75: b.p75,
    p95: b.p95,
  }));

  // Empirical intervals are calibrated only for revenue_behavioural_gbp_bn per MASTER_PROMPT §9.6
  const hasEmpiricalForMetric =
    metric === 'revenue_behavioural_gbp_bn' &&
    Array.isArray(mc?.empirical_interval) &&
    mc.empirical_interval.length > 0;

  const empiricalBands: EmpiricalBandPoint[] = hasEmpiricalForMetric
    ? (mc!.empirical_interval ?? []).map((b) => ({
        x: b.fiscal_year,
        p5: b.p5,
        p95: b.p95,
      }))
    : [];

  return {
    bands,
    intervalNote:
      mc?.interval_note ??
      'assumption-driven ranges, not statistical prediction intervals; exclude model and data uncertainty',
    empiricalBands,
    empiricalCalibrationNote: hasEmpiricalForMetric
      ? (mc?.empirical_calibration_note ?? null)
      : null,
    distribution: dist,
  };
}

export function extractFinalYearHistogram(
  bundle: SimulationBundle | null | undefined,
  metric: MetricName,
): {
  histogram: Histogram | undefined;
  centralFinal: number | undefined;
  p5Final: number | undefined;
  p95Final: number | undefined;
} {
  const mc = bundle?.monte_carlo;
  const histogram = mc?.histograms?.find((h) => h.metric === metric);
  const dist = mc?.distributions?.find((d) => d.metric === metric);
  const lastBand = dist?.bands?.[dist.bands.length - 1];

  const centralScen =
    bundle?.scenarios?.find((s) => s.scenario.name === 'central') ??
    bundle?.scenarios?.[0];
  const proj = centralScen?.result.metrics.find((m) => m.metric === metric);
  const centralFinal = proj?.values?.[proj.values.length - 1]?.value;

  return {
    histogram,
    centralFinal,
    p5Final: lastBand?.p5,
    p95Final: lastBand?.p95,
  };
}

export function extractTornadoItems(
  bundle: SimulationBundle | null | undefined,
  metric: MetricName,
): {
  sensitivity: SensitivityResult | undefined;
  items: TornadoInputItem[];
} {
  const sens = bundle?.sensitivity?.find((s) => s.metric === metric);
  if (!sens || !Array.isArray(sens.items)) {
    return { sensitivity: undefined, items: [] };
  }

  const items: TornadoInputItem[] = sens.items.map((item) => ({
    label: item.label || item.parameter,
    parameter: item.parameter,
    low: item.output_at_low,
    high: item.output_at_high,
    lowInput: item.low_input,
    highInput: item.high_input,
    swing: item.swing,
  }));

  return { sensitivity: sens, items };
}

export function buildParameterOverrides(
  assumptions: Assumption[],
  sliderValues: Record<string, number>,
): Record<string, number> {
  const overrides: Record<string, number> = {};
  for (const a of assumptions) {
    if (!a.adjustable) continue;
    const current = sliderValues[a.name];
    if (current === undefined) continue;
    if (Math.abs(current - a.value) > 1e-6) {
      overrides[a.name] = current;
    }
  }
  return overrides;
}

export function buildPolicyWithRateOverride(
  policy: PolicySpec,
  proposedRatePct: number | null,
): PolicySpec {
  if (
    proposedRatePct === null ||
    Number.isNaN(proposedRatePct) ||
    policy.proposed_rate_pct === proposedRatePct
  ) {
    return policy;
  }
  const baseRate = policy.baseline_rate_pct ?? 25;
  const directionWord =
    proposedRatePct > baseRate
      ? 'Raise'
      : proposedRatePct < baseRate
        ? 'Cut'
        : 'Keep';
  return {
    ...policy,
    proposed_rate_pct: proposedRatePct,
    description: `${directionWord} the CT main rate from ${baseRate}% to ${proposedRatePct}%`,
  };
}
