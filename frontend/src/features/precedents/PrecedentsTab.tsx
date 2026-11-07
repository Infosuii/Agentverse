import { useMemo } from 'react';
import { useParams } from 'react-router';
import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  useAnalysis,
  usePrecedents,
  type Analysis,
  type PolicyChange,
  type PrecedentMatch,
  type Source,
} from '../../api/hooks';
import {
  BarCompare,
  TimelineChart,
  type BarCompareRow,
  type BarCompareSeries,
} from '../../components/charts';
import {
  Badge,
  Card,
  EmptyState,
  EvidenceBadge,
  PlaceholderBadge,
  Skeleton,
  SourceChip,
  Table,
  Tooltip,
} from '../../components/ui';
import { fmtDate, fmtFiscalYear, fmtGbpBn, fmtPct, fmtPp } from '../../lib/format';
import { EVIDENCE_CLASS_COLORS } from '../../lib/theme';

export interface PrecedentsTabProps {
  analysis?: Analysis;
}

export function isReversedChange(change: PolicyChange): boolean {
  return (
    change.change_id.toUpperCase().includes('REVERSED') ||
    Boolean(change.notes && change.notes.trim().toLowerCase().startsWith('reversed:'))
  );
}

interface TimelinePoint {
  year: number;
  fiscalYear: string;
  ratePct: number;
  changeId?: string;
  oldRatePct?: number;
  newRatePct?: number;
  fiscalEvent?: string | null;
  isMatched?: boolean;
}

export function buildRateTimeline(
  changes: PolicyChange[],
  matchedIds: Set<string>,
): { points: TimelinePoint[]; reversed: PolicyChange[] } {
  const implemented = changes
    .filter((c) => !isReversedChange(c))
    .slice()
    .sort((a, b) => a.effective_date.localeCompare(b.effective_date));
  const reversed = changes.filter((c) => isReversedChange(c));

  if (implemented.length === 0) {
    return { points: [], reversed };
  }

  const byYear = new Map<number, PolicyChange>();
  for (const chg of implemented) {
    const yr = Number(chg.effective_date.slice(0, 4));
    if (!Number.isNaN(yr)) {
      byYear.set(yr, chg);
    }
  }

  const startYear = 1982;
  const currentYear = Math.max(2026, ...Array.from(byYear.keys()));
  let activeRate = implemented[0].old_rate_pct;

  const points: TimelinePoint[] = [];
  for (let yr = startYear; yr <= currentYear; yr += 1) {
    const chg = byYear.get(yr);
    if (chg) {
      activeRate = chg.new_rate_pct;
    }
    points.push({
      year: yr,
      fiscalYear: `${yr}-${String(yr + 1).slice(-2)}`,
      ratePct: activeRate,
      changeId: chg?.change_id,
      oldRatePct: chg?.old_rate_pct,
      newRatePct: chg?.new_rate_pct,
      fiscalEvent: chg?.fiscal_event,
      isMatched: chg ? matchedIds.has(chg.change_id) : false,
    });
  }

  return { points, reversed };
}

const BREAKDOWN_LABELS: Record<string, { label: string; weight: string }> = {
  direction: { label: 'Direction (rise vs cut)', weight: '30%' },
  magnitude: { label: 'Magnitude of rate change', weight: '25%' },
  rate_level: { label: 'Statutory rate level', weight: '15%' },
  macro_context: { label: 'Macroeconomic context (z-distance)', weight: '20%' },
  recency: { label: 'Recency', weight: '10%' },
};

function PrecedentComparisonCharts({
  match,
  modelY1Rev,
}: {
  match: PrecedentMatch;
  modelY1Rev: number | null;
}) {
  const { change } = match;
  const costings = useMemo(() => change.official_costings ?? [], [change.official_costings]);
  const outcomes = useMemo(() => change.observed_outcomes ?? [], [change.observed_outcomes]);

  const receiptsLevels = useMemo(
    () =>
      outcomes
        .filter((o) => o.metric === 'ct_receipts_gbp_bn')
        .slice()
        .sort((a, b) => a.fiscal_year.localeCompare(b.fiscal_year)),
    [outcomes],
  );

  const pctGdpOutcomes = useMemo(
    () =>
      outcomes
        .filter((o) => o.metric === 'ct_receipts_pct_gdp')
        .slice()
        .sort((a, b) => a.fiscal_year.localeCompare(b.fiscal_year)),
    [outcomes],
  );

  // Derive year-on-year observed receipts changes (explicitly labelled as derived outturn differences)
  const derivedChangesByFy = useMemo(() => {
    const map = new Map<string, number>();
    for (let i = 1; i < receiptsLevels.length; i += 1) {
      const diff = Number((receiptsLevels[i].value - receiptsLevels[i - 1].value).toFixed(2));
      map.set(receiptsLevels[i].fiscal_year, diff);
    }
    return map;
  }, [receiptsLevels]);

  const barRows = useMemo<BarCompareRow[]>(() => {
    const fys = new Set<string>();
    for (const c of costings) fys.add(c.fiscal_year);
    for (const fy of derivedChangesByFy.keys()) fys.add(fy);
    const sortedFys = Array.from(fys).sort();

    return sortedFys.map((fy, idx) => {
      const c = costings.find((item) => item.fiscal_year === fy);
      const obsDiff = derivedChangesByFy.get(fy);
      return {
        category: fmtFiscalYear(fy),
        officialCosting: c ? c.value_gbp_bn : null,
        observedChange: obsDiff !== undefined ? obsDiff : null,
        modelScenario: idx === 0 && modelY1Rev !== null ? modelY1Rev : null,
      };
    });
  }, [costings, derivedChangesByFy, modelY1Rev]);

  const barSeries = useMemo<BarCompareSeries[]>(() => {
    const list: BarCompareSeries[] = [
      {
        id: 'officialCosting',
        label: 'Official costing (ex-ante £bn)',
        evidenceClass: 'official_costing',
      },
      {
        id: 'observedChange',
        label: 'Observed receipts YoY Δ (derived £bn)',
        evidenceClass: 'observed_outcome',
      },
    ];
    if (modelY1Rev !== null) {
      list.push({
        id: 'modelScenario',
        label: 'Current proposal model Y1 (£bn)',
        evidenceClass: 'model_scenario',
      });
    }
    return list;
  }, [modelY1Rev]);

  if (barRows.length === 0 && pctGdpOutcomes.length === 0 && receiptsLevels.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
      {/* Legend explaining ex-ante costing vs observed outturn vs model scenario */}
      <div className="rounded-md border border-slate-200 bg-slate-50/80 p-3 text-xs text-slate-700">
        <div className="flex flex-wrap items-center gap-2 font-semibold text-slate-900">
          <span>Evidence comparison notes:</span>
          <EvidenceBadge evidenceClass="official_costing" short />
          <EvidenceBadge evidenceClass="observed_outcome" short />
          {modelY1Rev !== null && <EvidenceBadge evidenceClass="model_scenario" short />}
        </div>
        <p className="mt-1 leading-relaxed text-slate-600">
          <strong>Ex-ante official costings</strong> (violet) are original HMT/OBR policy-table estimates for the
          package scope. <strong>Observed outcomes</strong> (slate) are ONS outturn CT receipts levels and derived
          year-on-year changes, which include macroeconomic cycles, profit growth, and simultaneous base/allowance
          measures (confounders) — they are observations, not isolated causal policy effects.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {barRows.length > 0 && (
          <BarCompare
            data={barRows}
            series={barSeries}
            unit="£bn"
            title="Official Costing vs Derived Outturn Receipts Change (£bn)"
            caption="Ex-ante HMT/OBR policy costing (violet) vs derived ONS outturn receipts YoY Δ (slate) vs current model scenario (blue)."
            evidenceClass="official_costing"
            xLabel="Fiscal year"
            height={220}
            formatValue={(v) => fmtGbpBn(v)}
          />
        )}

        {pctGdpOutcomes.length > 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h5 className="text-xs font-semibold text-slate-900">
                Observed CT Receipts (% of GDP, t−1 to t+2)
              </h5>
              <EvidenceBadge evidenceClass="observed_outcome" short />
            </div>
            <div className="h-52 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RechartsLineChart
                  data={pctGdpOutcomes.map((o) => ({
                    fiscalYear: fmtFiscalYear(o.fiscal_year),
                    pctGdp: o.value,
                  }))}
                  margin={{ top: 8, right: 12, left: 4, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="fiscalYear" tick={{ fontSize: 11, fill: '#475569' }} />
                  <YAxis
                    tickFormatter={(v: number) => fmtPct(v, 1)}
                    tick={{ fontSize: 11, fill: '#475569' }}
                    width={54}
                  />
                  <RechartsTooltip
                    formatter={(val: unknown) => [
                      fmtPct(typeof val === 'number' ? val : Number(val), 2),
                      'Observed CT receipts (% GDP)',
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="pctGdp"
                    name="Observed CT receipts (% GDP)"
                    stroke={EVIDENCE_CLASS_COLORS.observed_outcome}
                    strokeWidth={2}
                    dot={{ r: 3.5, fill: EVIDENCE_CLASS_COLORS.observed_outcome }}
                    isAnimationActive={false}
                  />
                </RechartsLineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Explicit Tables of Official Costings and Observed Levels */}
      {(costings.length > 0 || receiptsLevels.length > 0) && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {costings.length > 0 && (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-800">
                  Official Policy Costings (Ex-ante)
                </span>
                <EvidenceBadge evidenceClass="official_costing" short />
              </div>
              <Table>
                <thead className="bg-violet-50/60 text-[11px] font-semibold text-violet-950 uppercase">
                  <tr>
                    <th className="px-2.5 py-1.5">Fiscal year</th>
                    <th className="px-2.5 py-1.5">Body / Event</th>
                    <th className="px-2.5 py-1.5">Exchequer £bn</th>
                    <th className="px-2.5 py-1.5">Behavioural?</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-xs">
                  {costings.map((c, idx) => (
                    <tr key={`${c.fiscal_year}-${idx}`}>
                      <td className="px-2.5 py-1.5 font-mono">{fmtFiscalYear(c.fiscal_year)}</td>
                      <td className="px-2.5 py-1.5">
                        {c.costing_body} · {c.fiscal_event}
                      </td>
                      <td className="px-2.5 py-1.5 font-semibold text-violet-900 tabular-nums">
                        {fmtGbpBn(c.value_gbp_bn)}
                      </td>
                      <td className="px-2.5 py-1.5 text-slate-600">
                        {c.includes_behavioural === true
                          ? 'Yes'
                          : c.includes_behavioural === false
                            ? 'Static only'
                            : 'Unspecified'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}

          {receiptsLevels.length > 0 && (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-800">
                  Observed CT Receipts Outturn (Levels)
                </span>
                <EvidenceBadge evidenceClass="observed_outcome" short />
              </div>
              <Table>
                <thead className="bg-slate-100 text-[11px] font-semibold text-slate-800 uppercase">
                  <tr>
                    <th className="px-2.5 py-1.5">Fiscal year</th>
                    <th className="px-2.5 py-1.5">Receipts level (£bn)</th>
                    <th className="px-2.5 py-1.5">Derived YoY Δ (£bn)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-xs">
                  {receiptsLevels.map((o) => {
                    const diff = derivedChangesByFy.get(o.fiscal_year);
                    return (
                      <tr key={o.fiscal_year}>
                        <td className="px-2.5 py-1.5 font-mono">{fmtFiscalYear(o.fiscal_year)}</td>
                        <td className="px-2.5 py-1.5 font-semibold text-slate-900 tabular-nums">
                          {fmtGbpBn(o.value)}
                        </td>
                        <td className="px-2.5 py-1.5 text-slate-600 tabular-nums">
                          {diff !== undefined ? fmtGbpBn(diff) : '— (base year)'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PrecedentCard({
  match,
  rank,
  sources,
  modelY1Rev,
}: {
  match: PrecedentMatch;
  rank: number;
  sources: Source[];
  modelY1Rev: number | null;
}) {
  const { change, similarity, similarity_breakdown, comparability_notes } = match;
  const deltaPp = Number((change.new_rate_pct - change.old_rate_pct).toFixed(2));
  const simPct = Math.round(similarity * 100);
  const macro = change.macro_context;

  const confounders = [
    ...(comparability_notes ?? []),
    ...(change.other_measures ?? []).map((m) => `Simultaneous measure: ${m}`),
  ];

  const breakdownTooltip = (
    <div className="space-y-1.5">
      <div className="font-semibold text-white">
        Similarity score breakdown ({simPct}%)
      </div>
      {Object.entries(similarity_breakdown).map(([key, score]) => {
        const meta = BREAKDOWN_LABELS[key] ?? { label: key, weight: '' };
        return (
          <div key={key} className="flex items-center justify-between gap-2 text-[11px]">
            <span className="text-slate-300">
              {meta.label} {meta.weight ? `(${meta.weight})` : ''}
            </span>
            <span className="font-mono font-semibold text-white tabular-nums">
              {Math.round(Number(score) * 100)}%
            </span>
          </div>
        );
      })}
    </div>
  );

  return (
    <Card
      title={
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="blue">#{rank}</Badge>
          <span className="font-mono text-xs text-slate-500">{change.change_id}</span>
          <span>
            {change.old_rate_pct}% → {change.new_rate_pct}% ({fmtPp(deltaPp)})
          </span>
          {change.fiscal_event && (
            <span className="text-xs font-normal text-slate-500">· {change.fiscal_event}</span>
          )}
        </div>
      }
      subtitle={`Effective ${fmtDate(change.effective_date)}${change.announced_date ? ` · Announced ${fmtDate(change.announced_date)}` : ''}`}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {change.is_placeholder && <PlaceholderBadge />}
          <Tooltip content={breakdownTooltip}>
            <div
              tabIndex={0}
              aria-label={`Similarity score ${simPct}%. Hover for component breakdown.`}
              className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs"
            >
              <span className="font-medium text-slate-600">Similarity:</span>
              <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-blue-600"
                  style={{ width: `${Math.max(4, Math.min(100, simPct))}%` }}
                />
              </div>
              <span className="font-bold text-slate-900 tabular-nums">{simPct}%</span>
            </div>
          </Tooltip>
        </div>
      }
    >
      <div className="space-y-4">
        {change.notes && (
          <p className="text-xs leading-relaxed text-slate-700">{change.notes}</p>
        )}

        {/* Comparability notes / Confounders as Amber Chips */}
        {confounders.length > 0 && (
          <div>
            <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-amber-900 uppercase">
              Comparability Notes &amp; Policy Confounders
            </div>
            <div className="flex flex-wrap gap-1.5">
              {confounders.map((note, idx) => (
                <Badge key={idx} variant="amber" dotColor="#b45309">
                  {note}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Macro Context Mini-Table */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-[11px] font-semibold tracking-wide text-slate-600 uppercase">
              Macroeconomic Context ({macro?.period ? fmtFiscalYear(macro.period) : 'Pre-reform fiscal year'})
            </span>
            <EvidenceBadge evidenceClass="observed_outcome" short />
          </div>
          {macro ? (
            <Table>
              <thead className="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase">
                <tr>
                  <th className="px-3 py-1.5">Period</th>
                  <th className="px-3 py-1.5">Real GDP growth</th>
                  <th className="px-3 py-1.5">CPI inflation</th>
                  <th className="px-3 py-1.5">Bank Rate</th>
                  <th className="px-3 py-1.5">Unemployment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-xs">
                <tr>
                  <td className="px-3 py-2 font-mono font-medium">
                    {fmtFiscalYear(macro.period)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {fmtPct(macro.real_gdp_growth_pct, 1)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {fmtPct(macro.cpi_inflation_pct, 1)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {fmtPct(macro.bank_rate_pct, 2)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {fmtPct(macro.unemployment_rate_pct, 1)}
                  </td>
                </tr>
              </tbody>
            </Table>
          ) : (
            <p className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Macroeconomic outturn indicators for this period are not populated in the current dataset slice.
            </p>
          )}
        </div>

        {/* Precedent Comparison Charts & Tables */}
        <PrecedentComparisonCharts match={match} modelY1Rev={modelY1Rev} />

        {/* Sources */}
        {change.source_ids && change.source_ids.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2.5">
            <span className="text-[11px] font-medium text-slate-500">Sources:</span>
            {change.source_ids.map((sid) => (
              <SourceChip key={sid} sourceId={sid} sources={sources} />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

export function PrecedentsTab({ analysis: propAnalysis }: PrecedentsTabProps) {
  const { id } = useParams<{ id: string }>();
  const { data: fetchedAnalysis, isLoading: isLoadingAnalysis } = useAnalysis(
    propAnalysis ? undefined : id,
  );
  const { data: allPrecedents, isLoading: isLoadingPrecedents } = usePrecedents('corporation_tax');
  const analysis = propAnalysis ?? fetchedAnalysis;

  const precedentsSlice = analysis?.precedents;
  const matches = useMemo(() => precedentsSlice?.matches ?? [], [precedentsSlice]);
  const matchedIds = useMemo(
    () => new Set(matches.map((m) => m.change.change_id)),
    [matches],
  );

  const historyChanges = useMemo(() => {
    if (allPrecedents && allPrecedents.length > 0) {
      return allPrecedents;
    }
    return matches.map((m) => m.change);
  }, [allPrecedents, matches]);

  const { points: timelinePoints, reversed: reversedChanges } = useMemo(
    () => buildRateTimeline(historyChanges, matchedIds),
    [historyChanges, matchedIds],
  );

  const mergedSources = useMemo(() => {
    const map = new Map<string, Source>();
    for (const s of analysis?.sources ?? []) map.set(s.source_id, s);
    for (const s of precedentsSlice?.sources ?? []) map.set(s.source_id, s);
    return Array.from(map.values());
  }, [analysis?.sources, precedentsSlice?.sources]);

  const modelY1Rev = useMemo(() => {
    if (
      analysis?.verification?.forecast_allowed === false ||
      analysis?.scope?.forecast_allowed === false
    ) {
      return null;
    }
    const central = analysis?.simulation?.scenarios?.[0]?.result;
    const revBehav = central?.metrics.find((m) => m.metric === 'revenue_behavioural_gbp_bn');
    return revBehav?.values?.[0]?.value ?? null;
  }, [analysis]);

  if (!analysis && (isLoadingAnalysis || isLoadingPrecedents)) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-64" />
        <Skeleton lines={6} />
      </div>
    );
  }

  const anyPlaceholder = Boolean(
    historyChanges.some((c) => c.is_placeholder) ||
      matches.some((m) => m.change.is_placeholder),
  );

  return (
    <div className="space-y-6">
      {/* Summary Header Card */}
      <Card
        title="Historical UK Corporation Tax Precedents"
        subtitle={
          precedentsSlice
            ? `Matcher: ${precedentsSlice.method} · Dataset version: ${precedentsSlice.dataset_version}`
            : 'Historical UK Corporation Tax main rate changes (1982–present)'
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <EvidenceBadge evidenceClass="observed_outcome" />
            <EvidenceBadge evidenceClass="official_costing" />
            {anyPlaceholder && <PlaceholderBadge />}
          </div>
        }
      >
        <p className="text-sm leading-relaxed text-slate-800">
          {precedentsSlice?.summary ||
            'Comparable historical UK corporation tax changes ranked by direction, magnitude, statutory rate level, macroeconomic context, and recency.'}
        </p>
      </Card>

      {/* Main Rate Step-Line Timeline (1982 -> today) */}
      <Card
        title="UK Corporation Tax Main Rate Timeline (1982–Present)"
        subtitle="Implemented statutory main rate step-line; blue markers highlight changes matched to this proposal"
        actions={<EvidenceBadge evidenceClass="observed_outcome" short />}
      >
        {timelinePoints.length === 0 ? (
          <EmptyState
            title="No historical rate series loaded"
            description="Curated corporation tax rate history is not available."
          />
        ) : (
          <div className="space-y-3">
            <TimelineChart
              points={timelinePoints.map((pt) => ({
                x: pt.year,
                y: pt.ratePct,
                label: pt.fiscalYear,
              }))}
              events={timelinePoints
                .filter((pt) => Boolean(pt.changeId))
                .map((pt) => ({
                  x: pt.year,
                  y: pt.ratePct,
                  label: `${pt.changeId}: ${pt.oldRatePct}% → ${pt.newRatePct}%`,
                  detail: pt.fiscalEvent ?? undefined,
                  color: pt.isMatched ? '#2563eb' : '#64748b',
                }))}
              unit="%"
              seriesLabel="Implemented CT main rate (%)"
              evidenceClass="observed_outcome"
              xLabel="Year"
              yLabel="Main rate (%)"
              height={280}
              caption="Historical UK statutory corporation tax main rate step-line (1982–present)."
            />

            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
              <div className="flex flex-wrap items-center gap-4">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded-full bg-blue-600" />
                  <span>Matched precedent ({matchedIds.size})</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-slate-500" />
                  <span>Other implemented rate change</span>
                </span>
              </div>
              {reversedChanges.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="amber">
                    Excluded from implemented timeline:{' '}
                    {reversedChanges
                      .map((r) => `${r.change_id} (${r.old_rate_pct}%→${r.new_rate_pct}%, reversed)`)
                      .join('; ')}
                  </Badge>
                </div>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* Ranked Precedent Cards */}
      <section aria-label="Ranked precedent matches" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-800">
            Ranked Precedent Matches ({matches.length})
          </h2>
          <span className="text-xs text-slate-500">
            Sorted by weighted 5-component similarity score
          </span>
        </div>

        {matches.length === 0 ? (
          <EmptyState
            title="No comparable historical precedents matched"
            description="No historical UK corporation tax changes matched the proposed policy type."
          />
        ) : (
          <div className="space-y-4">
            {matches.map((match, idx) => (
              <PrecedentCard
                key={match.change.change_id}
                match={match}
                rank={idx + 1}
                sources={mergedSources}
                modelY1Rev={modelY1Rev}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default PrecedentsTab;
