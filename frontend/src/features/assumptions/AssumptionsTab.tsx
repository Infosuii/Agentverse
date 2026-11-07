import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import clsx from 'clsx';
import {
  useAnalysis,
  type Analysis,
  type Assumption,
  type CalcStep,
  type Distribution,
  type MetricName,
  type ParameterBasis,
  type ParameterCategory,
  type ParameterEvidence,
} from '../../api/hooks';
import {
  Badge,
  Card,
  EmptyState,
  EvidenceBadge,
  PlaceholderBadge,
  Skeleton,
  SourceChip,
  Table,
  WithheldBanner,
  type BadgeVariant,
} from '../../components/ui';
import { ProvenanceNumber, formatChartValue } from '../../components/charts';
import { fmtFiscalYear } from '../../lib/format';
import { METRIC_DESCRIPTORS } from '../scenarios/transforms';

export interface AssumptionsTabProps {
  analysis?: Analysis;
}

const CATEGORY_ORDER: readonly ParameterCategory[] = [
  'behavioural',
  'structural',
  'timing',
  'macro',
] as const;

const CATEGORY_LABELS: Record<ParameterCategory, string> = {
  behavioural: 'Behavioural Elasticities',
  structural: 'Structural & Capital Allowances',
  timing: 'Timing & Phasing',
  macro: 'Macroeconomic Context',
};

const BASIS_BADGE_MAP: Record<
  ParameterBasis,
  { label: string; variant: BadgeVariant }
> = {
  official: { label: 'Official', variant: 'blue' },
  literature: { label: 'Literature', variant: 'violet' },
  calibrated: { label: 'Calibrated', variant: 'green' },
  team_judgement: { label: 'Team judgement', variant: 'amber' },
};

export function DistributionSparkline({
  distribution,
  low,
  value,
  high,
}: {
  distribution: Distribution;
  low: number;
  value: number;
  high: number;
}) {
  const width = 76;
  const height = 22;
  const pad = 3;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const span = high - low;
  const modeFrac =
    span > 1e-9 ? Math.min(1, Math.max(0, (value - low) / span)) : 0.5;
  const modeX = pad + modeFrac * w;

  if (distribution.kind === 'fixed' || span <= 1e-9) {
    return (
      <svg
        width={width}
        height={height}
        aria-label="Fixed parameter value"
        className="inline-block overflow-visible"
      >
        <line
          x1={pad}
          y1={height - pad}
          x2={width - pad}
          y2={height - pad}
          stroke="#cbd5e1"
          strokeWidth={1}
        />
        <line
          x1={width / 2}
          y1={pad}
          x2={width / 2}
          y2={height - pad}
          stroke="#475569"
          strokeWidth={2}
        />
      </svg>
    );
  }

  if (
    distribution.kind === 'normal' ||
    distribution.kind === 'truncated_normal' ||
    distribution.kind === 'lognormal'
  ) {
    const pts: string[] = [];
    for (let i = 0; i <= 20; i += 1) {
      const t = i / 20;
      const z = (t - modeFrac) / 0.24;
      const yVal = Math.exp(-0.5 * z * z);
      const x = pad + t * w;
      const y = height - pad - yVal * h;
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    const areaPts = `${pad},${height - pad} ${pts.join(' ')} ${width - pad},${height - pad}`;
    return (
      <svg
        width={width}
        height={height}
        aria-label={`${distribution.kind} distribution`}
        className="inline-block overflow-visible"
      >
        <polygon points={areaPts} fill="#d97706" fillOpacity={0.18} />
        <polyline
          points={pts.join(' ')}
          fill="none"
          stroke="#b45309"
          strokeWidth={1.5}
        />
      </svg>
    );
  }

  if (distribution.kind === 'uniform') {
    return (
      <svg
        width={width}
        height={height}
        aria-label="Uniform distribution"
        className="inline-block overflow-visible"
      >
        <rect
          x={pad}
          y={pad + 3}
          width={w}
          height={h - 3}
          fill="#2563eb"
          fillOpacity={0.18}
          stroke="#2563eb"
          strokeWidth={1.2}
        />
      </svg>
    );
  }

  // Default: triangular distribution
  const triPts = `${pad},${height - pad} ${modeX.toFixed(1)},${pad} ${width - pad},${height - pad}`;
  return (
    <svg
      width={width}
      height={height}
      aria-label="Triangular distribution"
      className="inline-block overflow-visible"
    >
      <polygon
        points={triPts}
        fill="#2563eb"
        fillOpacity={0.18}
        stroke="#2563eb"
        strokeWidth={1.5}
      />
      <line
        x1={modeX}
        y1={pad}
        x2={modeX}
        y2={height - pad}
        stroke="#1d4ed8"
        strokeWidth={1}
        strokeDasharray="2 1"
      />
    </svg>
  );
}

/**
 * Dependency rank for Calculation Inspector (MASTER_PROMPT §4.2 of agent-08 prompt):
 * 1. user-cost steps
 * 2. base
 * 3. static
 * 4. behavioural
 * 5. investment
 * 6. capital
 * 7. GDP
 * 8. dynamic
 */
export function getCalcStepDependencyRank(step: CalcStep): number {
  const id = step.step_id.toLowerCase();
  const label = step.label.toLowerCase();
  const formula = step.formula.toLowerCase();

  // 1. User-cost, allowance PV & Devereux-Griffith EMTR/EATR steps
  if (
    id.startsWith('inv.allowance_pv') ||
    id.startsWith('inv.user_cost') ||
    id.startsWith('etr.') ||
    id.includes('ucc') ||
    id.includes('user_cost') ||
    id.includes('cost_of_capital') ||
    id.includes('emtr') ||
    id.includes('eatr') ||
    id.includes('z_') ||
    id.includes('c_') ||
    label.includes('user cost') ||
    label.includes('allowance') ||
    label.includes('cost of capital') ||
    label.includes('effective marginal tax rate') ||
    label.includes('effective average tax rate')
  ) {
    return 1;
  }
  // 2. Base & base response steps (B0, B1)
  if (
    id.startsWith('rev.base') ||
    id.includes('base') ||
    id.includes('b0') ||
    id.includes('b1') ||
    label.includes('base')
  ) {
    return 2;
  }
  // 3. Static revenue steps
  if (id.startsWith('rev.static') || id.includes('static') || label.includes('static')) {
    return 3;
  }
  // 4. Behavioural revenue steps
  if (
    id.startsWith('rev.behav') ||
    id.includes('behav') ||
    label.includes('behavioural')
  ) {
    return 4;
  }
  // 5. Investment steps (inv.long_run, inv.change, inv.change_gbp)
  if (
    id.startsWith('inv.long_run') ||
    id.startsWith('inv.change') ||
    id.includes('inv') ||
    id.includes('investment') ||
    formula.includes('δi') ||
    label.includes('investment')
  ) {
    return 5;
  }
  // 6. Capital stock / turnover / gap steps (gdp.capital_turnover, gdp.capital_gap)
  if (
    id.startsWith('gdp.capital_') ||
    id.includes('cap') ||
    id.includes('x_') ||
    label.includes('capital stock') ||
    label.includes('capital gap') ||
    label.includes('capital turnover')
  ) {
    return 6;
  }
  // 7. GDP level steps (gdp.level)
  if (id.startsWith('gdp.level') || id.includes('gdp') || label.includes('gdp')) {
    return 7;
  }
  // 8. Dynamic revenue steps (rev.dynamic)
  if (id.startsWith('rev.dynamic') || id.includes('dyn') || label.includes('dynamic')) {
    return 8;
  }
  return 9;
}

const METRIC_MAX_RANK: Record<MetricName, number> = {
  cost_of_capital_pct: 1,
  revenue_static_gbp_bn: 3,
  revenue_behavioural_gbp_bn: 4,
  business_investment_pct: 5,
  business_investment_gbp_bn: 5,
  gdp_level_pct: 7,
  revenue_dynamic_gbp_bn: 8,
};

export function filterAndSortCalcSteps(
  trace: CalcStep[],
  metric: MetricName,
  year: string | undefined,
): CalcStep[] {
  if (!Array.isArray(trace) || trace.length === 0) {
    return [];
  }

  const yearSteps = trace.filter(
    (s) => !s.fiscal_year || !year || s.fiscal_year === year,
  );

  const maxRank = METRIC_MAX_RANK[metric] ?? 8;
  const relevant = yearSteps.filter((step) => {
    const rank = getCalcStepDependencyRank(step);
    const id = step.step_id.toLowerCase();
    if (metric === 'cost_of_capital_pct') {
      return rank === 1;
    }
    if (metric === 'revenue_static_gbp_bn') {
      return (rank === 2 && !id.includes('base_response')) || rank === 3;
    }
    if (metric === 'revenue_behavioural_gbp_bn') {
      return rank >= 2 && rank <= 4;
    }
    if (
      metric === 'business_investment_pct' ||
      metric === 'business_investment_gbp_bn'
    ) {
      return rank === 1 || rank === 5;
    }
    if (metric === 'gdp_level_pct') {
      return rank === 1 || rank === 5 || rank === 6 || rank === 7;
    }
    return rank <= maxRank;
  });

  const targetList = relevant.length > 0 ? relevant : yearSteps;
  return [...targetList].sort(
    (a, b) => getCalcStepDependencyRank(a) - getCalcStepDependencyRank(b),
  );
}

export function AssumptionsTab({ analysis: propAnalysis }: AssumptionsTabProps) {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(propAnalysis ? undefined : id);
  const analysis = propAnalysis ?? fetchedAnalysis;

  const queryMetric = searchParams.get('metric') as MetricName | null;
  const queryYear = searchParams.get('year');

  const simulation = analysis?.simulation;
  const assumptions = useMemo(
    () => simulation?.assumptions ?? [],
    [simulation?.assumptions],
  );
  const centralResult = useMemo(
    () =>
      simulation?.scenarios?.find((s) => s.scenario.name === 'central')?.result ??
      simulation?.scenarios?.[0]?.result,
    [simulation?.scenarios],
  );
  const fiscalYears = useMemo(
    () => centralResult?.fiscal_years ?? [],
    [centralResult?.fiscal_years],
  );

  const [selectedAssumptionName, setSelectedAssumptionName] = useState<string | null>(
    null,
  );
  const [inspectorMetric, setInspectorMetric] = useState<MetricName>(
    queryMetric && METRIC_DESCRIPTORS.some((m) => m.metric === queryMetric)
      ? queryMetric
      : 'revenue_behavioural_gbp_bn',
  );
  const [inspectorYear, setInspectorYear] = useState<string>(
    queryYear || fiscalYears[0] || '2027-28',
  );

  // Sync deep-link query params (?metric=&year=)
  useEffect(() => {
    if (queryMetric && METRIC_DESCRIPTORS.some((m) => m.metric === queryMetric)) {
      setInspectorMetric(queryMetric);
    }
    if (queryYear) {
      setInspectorYear(queryYear);
    } else if (fiscalYears.length > 0 && !fiscalYears.includes(inspectorYear)) {
      setInspectorYear(fiscalYears[0]!);
    }
  }, [queryMetric, queryYear, fiscalYears, inspectorYear]);

  const groupedAssumptions = useMemo(() => {
    const groups = new Map<ParameterCategory, Assumption[]>();
    for (const cat of CATEGORY_ORDER) {
      groups.set(cat, []);
    }
    for (const a of assumptions) {
      const list = groups.get(a.category) ?? [];
      list.push(a);
      groups.set(a.category, list);
    }
    return groups;
  }, [assumptions]);

  const parameterEvidenceMap = useMemo(() => {
    const m = new Map<string, ParameterEvidence[]>();
    for (const pe of analysis?.research?.parameter_evidence ?? []) {
      const list = m.get(pe.parameter) ?? [];
      list.push(pe);
      m.set(pe.parameter, list);
    }
    return m;
  }, [analysis?.research?.parameter_evidence]);

  const selectedAssumption = useMemo(
    () =>
      assumptions.find((a) => a.name === selectedAssumptionName) ??
      assumptions[0] ??
      null,
    [assumptions, selectedAssumptionName],
  );

  const orderedCalcSteps = useMemo(
    () =>
      filterAndSortCalcSteps(
        centralResult?.calc_trace ?? [],
        inspectorMetric,
        inspectorYear,
      ),
    [centralResult?.calc_trace, inspectorMetric, inspectorYear],
  );

  if (!analysis && isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!analysis) {
    return (
      <EmptyState
        title="Analysis not available"
        description="Select or create an analysis to view model assumptions and calculation steps."
      />
    );
  }

  const forecastAllowed =
    analysis.verification?.forecast_allowed !== false &&
    analysis.scope?.forecast_allowed !== false;

  const declineReasons = Array.from(
    new Set([
      ...(analysis.verification?.decline_reasons ?? []),
      ...(analysis.scope?.forecast_allowed === false
        ? (analysis.scope.reasons ?? [])
        : []),
    ]),
  );

  const handleMetricYearChange = (newMetric: MetricName, newYear: string) => {
    setInspectorMetric(newMetric);
    setInspectorYear(newYear);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('metric', newMetric);
        next.set('year', newYear);
        return next;
      },
      { replace: true },
    );
  };

  return (
    <div className="space-y-6">
      {!forecastAllowed && <WithheldBanner reasons={declineReasons} />}

      {/* 3.3 Assumptions Table + Detail Panel */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card
            title="Model Assumptions & Provenance Registry"
            subtitle="Every econometric parameter with its central value, uncertainty range, distribution shape, basis, and sources. Click any row to inspect rationale and research cross-checks."
            actions={<EvidenceBadge evidenceClass="assumption" />}
          >
            {assumptions.length === 0 ? (
              <EmptyState
                title="No assumptions loaded"
                description="Assumptions will populate when the modelling stage runs."
              />
            ) : (
              <div className="space-y-5">
                {CATEGORY_ORDER.map((category) => {
                  const rows = groupedAssumptions.get(category) ?? [];
                  if (rows.length === 0) return null;

                  return (
                    <div key={category} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold tracking-wide text-slate-700 uppercase">
                          {CATEGORY_LABELS[category]}
                        </h4>
                        <span className="text-[11px] text-slate-500">
                          {rows.length} parameter{rows.length === 1 ? '' : 's'}
                        </span>
                      </div>

                      <Table>
                        <thead className="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase">
                          <tr>
                            <th className="px-3 py-2">Parameter</th>
                            <th className="px-3 py-2">Central Value</th>
                            <th className="px-3 py-2">Low–High Range</th>
                            <th className="px-3 py-2">Distribution</th>
                            <th className="px-3 py-2">Basis</th>
                            <th className="px-3 py-2">Sources</th>
                            <th className="px-3 py-2">Flags</th>
                            <th className="px-3 py-2">What the research found</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 text-xs">
                          {rows.map((a) => {
                            const isSelected = selectedAssumption?.name === a.name;
                            const basisMeta =
                              BASIS_BADGE_MAP[a.basis] ?? BASIS_BADGE_MAP.team_judgement;
                            const researchMatches =
                              parameterEvidenceMap.get(a.name) ?? [];

                            return (
                              <tr
                                key={a.name}
                                id={`assumption-row-${a.name}`}
                                onClick={() => setSelectedAssumptionName(a.name)}
                                className={clsx(
                                  'cursor-pointer transition-colors',
                                  isSelected
                                    ? 'bg-amber-50/70'
                                    : 'hover:bg-slate-50',
                                )}
                              >
                                <td className="px-3 py-2.5 font-medium text-slate-900">
                                  <div>{a.label}</div>
                                  <div className="font-mono text-[10px] text-slate-500">
                                    {a.name}
                                  </div>
                                </td>
                                <td className="px-3 py-2.5 font-mono font-semibold text-slate-900 tabular-nums">
                                  {formatChartValue(a.value, a.unit)}
                                  <span className="ml-1 font-sans text-[10px] font-normal text-slate-500">
                                    ({a.unit})
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 font-mono text-slate-700 tabular-nums">
                                  {a.distribution.kind === 'fixed' ? (
                                    <span className="text-slate-400">Fixed</span>
                                  ) : (
                                    `${formatChartValue(a.low, a.unit)} – ${formatChartValue(a.high, a.unit)}`
                                  )}
                                </td>
                                <td className="px-3 py-2.5">
                                  <div className="flex items-center gap-1.5">
                                    <DistributionSparkline
                                      distribution={a.distribution}
                                      low={a.low}
                                      value={a.value}
                                      high={a.high}
                                    />
                                    <span className="text-[10px] text-slate-500">
                                      {a.distribution.kind}
                                    </span>
                                  </div>
                                </td>
                                <td className="px-3 py-2.5">
                                  <Badge variant={basisMeta.variant}>
                                    {basisMeta.label}
                                  </Badge>
                                </td>
                                <td className="px-3 py-2.5">
                                  {(a.source_ids ?? []).length > 0 ? (
                                    <div className="flex flex-wrap gap-1">
                                      {(a.source_ids ?? []).map((sid) => (
                                        <SourceChip
                                          key={sid}
                                          sourceId={sid}
                                          sources={analysis.sources}
                                        />
                                      ))}
                                    </div>
                                  ) : (
                                    <span className="text-[11px] text-slate-400">
                                      None cited
                                    </span>
                                  )}
                                </td>
                                <td className="px-3 py-2.5">
                                  <div className="flex flex-wrap gap-1">
                                    {a.is_user_override && (
                                      <Badge variant="violet">User override</Badge>
                                    )}
                                    {a.is_placeholder && (
                                      <PlaceholderBadge label="Placeholder" />
                                    )}
                                    {!a.is_user_override && !a.is_placeholder && (
                                      <span className="text-[11px] text-emerald-700">
                                        Verified
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="px-3 py-2.5">
                                  {researchMatches.length > 0 ? (
                                    <div className="space-y-1">
                                      {researchMatches.map((pe, idx) => (
                                        <div
                                          key={idx}
                                          className="rounded border border-blue-200 bg-blue-50/50 px-2 py-1 text-[11px] text-slate-700"
                                        >
                                          <div className="font-mono font-medium text-blue-900 tabular-nums">
                                            {pe.value !== null && pe.value !== undefined
                                              ? `Central: ${pe.value}`
                                              : ''}
                                            {pe.low !== null &&
                                            pe.low !== undefined &&
                                            pe.high !== null &&
                                            pe.high !== undefined
                                              ? ` [${pe.low} – ${pe.high}]`
                                              : ''}
                                          </div>
                                          {pe.note && (
                                            <div className="text-[10px] text-slate-600">
                                              {pe.note}
                                            </div>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    <span className="text-[11px] text-slate-400">
                                      No direct research match
                                    </span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </Table>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        {/* Assumption Detail Panel */}
        <div className="space-y-4 xl:col-span-1">
          <Card
            title={
              selectedAssumption
                ? `Assumption Detail: ${selectedAssumption.label}`
                : 'Assumption Detail'
            }
            subtitle="Description, economic rationale, and linked research evidence."
          >
            {selectedAssumption ? (
              <div className="space-y-3 text-xs text-slate-700">
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 p-2.5">
                  <span className="font-mono text-[11px] font-semibold text-slate-800">
                    {selectedAssumption.name}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Badge
                      variant={
                        BASIS_BADGE_MAP[selectedAssumption.basis]?.variant ?? 'amber'
                      }
                    >
                      {BASIS_BADGE_MAP[selectedAssumption.basis]?.label ??
                        selectedAssumption.basis}
                    </Badge>
                    {selectedAssumption.is_placeholder && (
                      <PlaceholderBadge label="Placeholder" />
                    )}
                  </div>
                </div>

                <div>
                  <div className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                    Description
                  </div>
                  <p className="mt-1 leading-relaxed text-slate-800">
                    {selectedAssumption.description}
                  </p>
                </div>

                {selectedAssumption.rationale && (
                  <div>
                    <div className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                      Economic Rationale
                    </div>
                    <p className="mt-1 leading-relaxed text-slate-700">
                      {selectedAssumption.rationale}
                    </p>
                  </div>
                )}

                <div className="grid grid-cols-3 gap-2 rounded-md border border-slate-100 bg-slate-50 p-2.5 text-center tabular-nums">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase">Low</div>
                    <div className="font-mono font-semibold text-slate-800">
                      {formatChartValue(
                        selectedAssumption.low,
                        selectedAssumption.unit,
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase">Central</div>
                    <div className="font-mono font-bold text-blue-800">
                      {formatChartValue(
                        selectedAssumption.value,
                        selectedAssumption.unit,
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase">High</div>
                    <div className="font-mono font-semibold text-slate-800">
                      {formatChartValue(
                        selectedAssumption.high,
                        selectedAssumption.unit,
                      )}
                    </div>
                  </div>
                </div>

                {/* Sources */}
                <div>
                  <div className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                    Cited Sources
                  </div>
                  {(selectedAssumption.source_ids ?? []).length > 0 ? (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {(selectedAssumption.source_ids ?? []).map((sid) => (
                        <SourceChip
                          key={sid}
                          sourceId={sid}
                          sources={analysis.sources}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-slate-400">
                      No curated or research sources linked yet.
                    </p>
                  )}
                </div>

                {/* Linked Evidence IDs -> Research Tab */}
                <div>
                  <div className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                    Linked Research Evidence IDs
                  </div>
                  {(selectedAssumption.evidence_ids ?? []).length > 0 ? (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {(selectedAssumption.evidence_ids ?? []).map((eid) => (
                        <Link
                          key={eid}
                          to={`/analyses/${analysis.analysis_id}/research?evidence=${encodeURIComponent(eid)}`}
                          className="inline-flex items-center gap-1 rounded border border-blue-300 bg-blue-50 px-2 py-0.5 font-mono text-xs font-medium text-blue-800 hover:bg-blue-100"
                        >
                          <span>[{eid}]</span>
                          <span aria-hidden="true">→</span>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-slate-400">
                      No specific evidence IDs attached.
                    </p>
                  )}
                </div>

                {/* What the research found cross-check */}
                <div className="border-t border-slate-100 pt-3">
                  <div className="text-[11px] font-semibold tracking-wide text-slate-600 uppercase">
                    What the research found (comparison only)
                  </div>
                  {(parameterEvidenceMap.get(selectedAssumption.name) ?? []).length >
                  0 ? (
                    <div className="mt-1.5 space-y-2">
                      {(parameterEvidenceMap.get(selectedAssumption.name) ?? []).map(
                        (pe, i) => (
                          <div
                            key={i}
                            className="rounded-md border border-blue-200 bg-blue-50/40 p-2.5"
                          >
                            <div className="font-mono text-xs font-semibold text-blue-900 tabular-nums">
                              Value: {pe.value ?? '—'} · Range: [{pe.low ?? '—'} to{' '}
                              {pe.high ?? '—'}]
                            </div>
                            {pe.note && (
                              <p className="mt-1 text-xs text-slate-700">{pe.note}</p>
                            )}
                            {pe.evidence_ids.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                {pe.evidence_ids.map((eid) => (
                                  <Link
                                    key={eid}
                                    to={`/analyses/${analysis.analysis_id}/research?evidence=${encodeURIComponent(eid)}`}
                                    className="rounded border border-blue-300 bg-white px-1.5 py-0.5 font-mono text-[11px] text-blue-700 hover:underline"
                                  >
                                    [{eid}]
                                  </Link>
                                ))}
                              </div>
                            )}
                          </div>
                        ),
                      )}
                    </div>
                  ) : (
                    <p className="mt-1 text-slate-400">
                      No parameter evidence extracted for{' '}
                      <code>{selectedAssumption.name}</code> in this research run.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Select a parameter row from the table to inspect its details.
              </p>
            )}
          </Card>
        </div>
      </div>

      {/* 4.2 Calculation Inspector ("How was this calculated?") */}
      {forecastAllowed && (
        <Card
          title="How was this calculated? (Calculation Inspector)"
          subtitle="Select a modelled metric and fiscal year to inspect the exact econometric CalcSteps in dependency order."
          actions={<EvidenceBadge evidenceClass="model_scenario" />}
        >
          <div className="space-y-4">
            {/* Metric & Fiscal Year Selectors */}
            <div className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
              <div className="flex items-center gap-2">
                <label
                  htmlFor="inspector-metric-select"
                  className="font-semibold text-slate-700"
                >
                  Metric:
                </label>
                <select
                  id="inspector-metric-select"
                  value={inspectorMetric}
                  onChange={(e) =>
                    handleMetricYearChange(
                      e.target.value as MetricName,
                      inspectorYear,
                    )
                  }
                  className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                >
                  {METRIC_DESCRIPTORS.map((m) => (
                    <option key={m.metric} value={m.metric}>
                      {m.label} ({m.unit})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <label
                  htmlFor="inspector-year-select"
                  className="font-semibold text-slate-700"
                >
                  Fiscal Year:
                </label>
                <select
                  id="inspector-year-select"
                  value={inspectorYear}
                  onChange={(e) =>
                    handleMetricYearChange(inspectorMetric, e.target.value)
                  }
                  className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                >
                  {(fiscalYears.length > 0 ? fiscalYears : ['2027-28']).map(
                    (fy) => (
                      <option key={fy} value={fy}>
                        {fmtFiscalYear(fy)}
                      </option>
                    ),
                  )}
                </select>
              </div>

              <div className="ml-auto text-slate-500">
                Showing <strong>{orderedCalcSteps.length}</strong> step
                {orderedCalcSteps.length === 1 ? '' : 's'} in dependency order
                (user-cost → base → static → behavioural → investment → capital →
                GDP → dynamic)
              </div>
            </div>

            {/* Ordered CalcStep Cards */}
            {orderedCalcSteps.length === 0 ? (
              <EmptyState
                title="No calculation trace steps available"
                description="Calculation trace steps will appear here once the econometric engine completes."
              />
            ) : (
              <div className="space-y-3">
                {orderedCalcSteps.map((step, index) => (
                  <div
                    key={step.step_id}
                    className="rounded-lg border border-slate-200 bg-white p-4 shadow-2xs"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 pb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-[11px] font-bold text-blue-800">
                          {index + 1}
                        </span>
                        <div>
                          <h5 className="text-xs font-bold text-slate-900">
                            {step.label}
                          </h5>
                          <code className="font-mono text-[11px] text-slate-500">
                            {step.step_id}
                          </code>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-slate-500">Output:</span>
                        <ProvenanceNumber
                          value={step.output}
                          unit={step.unit}
                          calcStepIds={[step.step_id]}
                          sources={step.source_ids}
                          allSources={analysis.sources}
                          evidenceClass="model_scenario"
                        />
                        <span className="font-mono text-[11px] text-slate-500">
                          ({step.unit})
                        </span>
                      </div>
                    </div>

                    {/* Monospace Formula */}
                    <div className="mt-2.5 rounded-md border border-slate-200 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100">
                      {step.formula}
                    </div>

                    {/* Inputs Table & Sources */}
                    <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-3">
                      <div className="lg:col-span-2">
                        <div className="mb-1 text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                          Step Inputs
                        </div>
                        <Table>
                          <thead className="bg-slate-50 text-[10px] font-semibold text-slate-600 uppercase">
                            <tr>
                              <th className="px-2.5 py-1.5">Symbol / Input</th>
                              <th className="px-2.5 py-1.5">Value</th>
                              <th className="px-2.5 py-1.5">Linked Parameter</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 text-xs">
                            {Object.entries(step.inputs).map(([symbol, val]) => {
                              const matchingParam =
                                assumptions.find((a) => a.name === symbol) ??
                                assumptions.find(
                                  (a) =>
                                    (step.parameter_names ?? []).includes(a.name) &&
                                    Math.abs(a.value - val) < 1e-6,
                                );

                              return (
                                <tr key={symbol}>
                                  <td className="px-2.5 py-1.5 font-mono font-medium text-slate-800">
                                    {symbol}
                                  </td>
                                  <td className="px-2.5 py-1.5 font-mono text-slate-900 tabular-nums">
                                    {Number(val.toFixed(6))}
                                  </td>
                                  <td className="px-2.5 py-1.5">
                                    {matchingParam ? (
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setSelectedAssumptionName(
                                            matchingParam.name,
                                          );
                                          const el = document.getElementById(
                                            `assumption-row-${matchingParam.name}`,
                                          );
                                          el?.scrollIntoView({
                                            behavior: 'smooth',
                                            block: 'center',
                                          });
                                        }}
                                        className="font-mono text-[11px] font-medium text-blue-700 hover:underline"
                                      >
                                        {matchingParam.name} ({matchingParam.label})
                                      </button>
                                    ) : (
                                      <span className="text-[11px] text-slate-400">
                                        —
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </Table>
                      </div>

                      <div className="space-y-2.5 text-xs">
                        {(step.parameter_names ?? []).length > 0 && (
                          <div>
                            <div className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                              Parameters Used
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {(step.parameter_names ?? []).map((pname) => (
                                <button
                                  key={pname}
                                  type="button"
                                  onClick={() => {
                                    setSelectedAssumptionName(pname);
                                    const el = document.getElementById(
                                      `assumption-row-${pname}`,
                                    );
                                    el?.scrollIntoView({
                                      behavior: 'smooth',
                                      block: 'center',
                                    });
                                  }}
                                  className="rounded border border-amber-300 bg-amber-50 px-2 py-0.5 font-mono text-[11px] font-medium text-amber-900 hover:bg-amber-100"
                                >
                                  {pname}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {(step.source_ids ?? []).length > 0 && (
                          <div>
                            <div className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                              Baseline / Step Sources
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {(step.source_ids ?? []).map((sid) => (
                                <SourceChip
                                  key={sid}
                                  sourceId={sid}
                                  sources={analysis.sources}
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

export default AssumptionsTab;
