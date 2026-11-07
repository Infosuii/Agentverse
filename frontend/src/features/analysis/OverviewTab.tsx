import { Link, useParams } from 'react-router';
import {
  useAnalysis,
  type Analysis,
  type MetricName,
  type MetricProjection,
  type PercentileBand,
} from '../../api/hooks';
import {
  Badge,
  Card,
  EmptyState,
  EvidenceBadge,
  PlaceholderBadge,
  Skeleton,
  SourceChip,
  Stat,
  WithheldBanner,
} from '../../components/ui';
import { fmtDate, fmtFiscalYear, fmtGbpBn, fmtPct, fmtPp } from '../../lib/format';

export interface OverviewTabProps {
  analysis?: Analysis;
}

function findMetric(
  metrics: MetricProjection[] | undefined,
  name: MetricName,
): MetricProjection | undefined {
  return metrics?.find((m) => m.metric === name);
}

function findBand(
  bands: PercentileBand[] | undefined,
  fiscalYear: string | undefined,
): PercentileBand | undefined {
  if (!bands || !fiscalYear) return undefined;
  return bands.find((b) => b.fiscal_year === fiscalYear);
}

export function OverviewTab({ analysis: propAnalysis }: OverviewTabProps) {
  const { id } = useParams<{ id: string }>();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(propAnalysis ? undefined : id);
  const analysis = propAnalysis ?? fetchedAnalysis;

  if (!analysis && isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton lines={4} />
      </div>
    );
  }

  if (!analysis) {
    return (
      <EmptyState
        title="Analysis not available"
        description="Select or create an analysis to view its overview."
      />
    );
  }

  const forecastAllowed =
    analysis.verification?.forecast_allowed !== false &&
    analysis.scope?.forecast_allowed !== false;

  const declineReasons = [
    ...(analysis.verification?.decline_reasons ?? []),
    ...(analysis.scope?.forecast_allowed === false ? (analysis.scope.reasons ?? []) : []),
  ];
  const uniqueReasons = Array.from(new Set(declineReasons));

  const centralScenario =
    analysis.simulation?.scenarios?.find((s) => s.scenario.name === 'central') ??
    analysis.simulation?.scenarios?.[0];
  const centralResult = centralScenario?.result;
  const fiscalYears = centralResult?.fiscal_years ?? [];
  const year1 = fiscalYears[0];
  const finalYear = fiscalYears[fiscalYears.length - 1];

  const revBehav = findMetric(centralResult?.metrics, 'revenue_behavioural_gbp_bn');
  const invPct = findMetric(centralResult?.metrics, 'business_investment_pct');
  const gdpPct = findMetric(centralResult?.metrics, 'gdp_level_pct');

  const revBehavY1 = revBehav?.values?.[0]?.value;
  const revBehavFinal = revBehav?.values?.[revBehav.values.length - 1]?.value;
  const invFinal = invPct?.values?.[invPct.values.length - 1]?.value;
  const gdpFinal = gdpPct?.values?.[gdpPct.values.length - 1]?.value;

  const mcRevDist = analysis.simulation?.monte_carlo?.distributions?.find(
    (d) => d.metric === 'revenue_behavioural_gbp_bn',
  );
  const mcBandY1 = findBand(mcRevDist?.bands, year1);
  const mcBandFinal = findBand(mcRevDist?.bands, finalYear);

  const hasPlaceholderAssumptions = Boolean(
    analysis.simulation?.assumptions?.some((a) => a.is_placeholder),
  );

  const withheldReasonText =
    uniqueReasons[0] ?? 'Policy outside validated scope or failed blocking check';

  const quickLinks = [
    {
      tab: 'research',
      title: 'Live Research & Evidence',
      description: `${analysis.research?.evidence?.length ?? 0} extracted evidence items across ${analysis.research?.sources?.length ?? 0} sources`,
    },
    {
      tab: 'precedents',
      title: 'Historical Precedents',
      description: `${analysis.precedents?.matches?.length ?? 0} matched UK corporation tax rate changes`,
    },
    {
      tab: 'scenarios',
      title: 'Scenarios, Monte Carlo & Sliders',
      description: 'Explore central, optimistic, pessimistic paths, fan charts, and interactive sliders',
    },
    {
      tab: 'assumptions',
      title: 'Assumptions & Calculation Inspector',
      description: `${analysis.simulation?.assumptions?.length ?? 0} explicit parameters and step-by-step formulas`,
    },
    {
      tab: 'verification',
      title: 'Verification Audit',
      description: `${analysis.verification?.checks?.length ?? 0} independent audit checks (${analysis.verification?.overall ?? 'pending'})`,
    },
    {
      tab: 'report',
      title: 'Policy Assessment Report',
      description: 'Evidence-backed narrative report with downloadable Markdown & print/PDF view',
    },
  ];

  const changePp =
    analysis.policy?.baseline_rate_pct != null &&
    analysis.policy?.proposed_rate_pct != null
      ? Number(
          (
            analysis.policy.proposed_rate_pct - analysis.policy.baseline_rate_pct
          ).toFixed(2),
        )
      : null;

  return (
    <div className="space-y-6">
      {!forecastAllowed && <WithheldBanner reasons={uniqueReasons} />}

      {/* Headline Stat Tiles */}
      <section aria-label="Headline model projections">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-800">
            Headline Projections (Central Scenario)
          </h2>
          <div className="flex items-center gap-2">
            <EvidenceBadge evidenceClass="model_scenario" />
            {hasPlaceholderAssumptions && <PlaceholderBadge />}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label={`Behavioural Revenue (${fmtFiscalYear(year1 || 'Year 1')})`}
            value={fmtGbpBn(revBehavY1)}
            range={
              mcBandY1
                ? `${fmtGbpBn(mcBandY1.p5)} to ${fmtGbpBn(mcBandY1.p95)}`
                : null
            }
            sublabel="Year 1 Exchequer revenue change"
            evidenceClass="model_scenario"
            confidence={revBehav?.confidence ?? 'medium'}
            withheld={!forecastAllowed}
            withheldReason={withheldReasonText}
            isPlaceholder={hasPlaceholderAssumptions}
            provenance={
              year1
                ? `CalcStep: rev.behav.${year1} · Baseline: ${centralResult?.baseline_vintage ?? 'OBR'}`
                : undefined
            }
          />

          <Stat
            label={`Behavioural Revenue (${fmtFiscalYear(finalYear || 'Year 5')})`}
            value={fmtGbpBn(revBehavFinal)}
            range={
              mcBandFinal
                ? `${fmtGbpBn(mcBandFinal.p5)} to ${fmtGbpBn(mcBandFinal.p95)}`
                : null
            }
            sublabel={`Year ${fiscalYears.length || 5} Exchequer revenue change`}
            evidenceClass="model_scenario"
            confidence={revBehav?.confidence ?? 'medium'}
            withheld={!forecastAllowed}
            withheldReason={withheldReasonText}
            isPlaceholder={hasPlaceholderAssumptions}
            provenance={
              finalYear
                ? `CalcStep: rev.behav.${finalYear} · Assumption-driven MC p5–p95`
                : undefined
            }
          />

          <Stat
            label={`Business Investment (${fmtFiscalYear(finalYear || 'Year 5')})`}
            value={fmtPct(invFinal)}
            sublabel="User cost of capital channel"
            evidenceClass="model_scenario"
            confidence={invPct?.confidence ?? 'medium'}
            withheld={!forecastAllowed}
            withheldReason={withheldReasonText}
            isPlaceholder={hasPlaceholderAssumptions}
            provenance={
              finalYear
                ? `CalcStep: inv.pct.${finalYear} · Hall–Jorgenson user cost`
                : undefined
            }
          />

          <Stat
            label={`GDP Level (${fmtFiscalYear(finalYear || 'Year 5')})`}
            value={fmtPct(gdpFinal)}
            sublabel="Partial equilibrium capital stock effect"
            evidenceClass="model_scenario"
            confidence={gdpPct?.confidence ?? 'low'}
            withheld={!forecastAllowed}
            withheldReason={withheldReasonText}
            isPlaceholder={hasPlaceholderAssumptions}
            provenance={
              finalYear
                ? `CalcStep: gdp.pct.${finalYear} · Low confidence (partial equilibrium)`
                : undefined
            }
          />
        </div>
      </section>

      {/* Policy & Research Summary */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Policy Specification" className="lg:col-span-1">
          {analysis.policy ? (
            <dl className="space-y-2 text-xs">
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Policy type:</dt>
                <dd className="font-medium text-slate-900">
                  {analysis.policy.policy_type}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Rate change:</dt>
                <dd className="font-semibold text-slate-900 tabular-nums">
                  {analysis.policy.baseline_rate_pct ?? '—'}% →{' '}
                  {analysis.policy.proposed_rate_pct ?? '—'}% ({fmtPp(changePp)})
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Effective date:</dt>
                <dd className="font-medium text-slate-900">
                  {fmtDate(analysis.policy.effective_date)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Horizon:</dt>
                <dd className="font-medium text-slate-900">
                  {analysis.policy.horizon_years} years
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Scope status:</dt>
                <dd>
                  <Badge
                    variant={
                      analysis.scope?.status === 'supported'
                        ? 'green'
                        : analysis.scope?.status === 'partially_supported'
                          ? 'amber'
                          : 'red'
                    }
                  >
                    {analysis.scope?.status ?? 'pending'}
                  </Badge>
                </dd>
              </div>
            </dl>
          ) : (
            <Skeleton lines={4} />
          )}
        </Card>

        <Card
          title="Research & Precedent Highlights"
          className="lg:col-span-2"
          actions={
            analysis.sources && analysis.sources.length > 0 ? (
              <span className="text-xs text-slate-500">
                {analysis.sources.length} cited sources
              </span>
            ) : undefined
          }
        >
          <div className="space-y-3 text-xs leading-relaxed text-slate-700">
            {analysis.research?.summary ? (
              <p>{analysis.research.summary}</p>
            ) : (
              <p className="text-slate-500">
                Research summary will appear here once the research stage completes.
              </p>
            )}
            {analysis.precedents?.summary && (
              <p className="border-t border-slate-100 pt-2 text-slate-600">
                <strong className="text-slate-800">Historical precedents: </strong>
                {analysis.precedents.summary}
              </p>
            )}
            {analysis.sources && analysis.sources.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[11px] font-medium text-slate-500">
                  Key sources:
                </span>
                {analysis.sources.slice(0, 6).map((src) => (
                  <SourceChip
                    key={src.source_id}
                    sourceId={src.source_id}
                    sources={analysis.sources}
                  />
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Quick Links to All Analysis Tabs */}
      <Card title="Explore Analysis Workstreams">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {quickLinks.map((item) => (
            <Link
              key={item.tab}
              to={`/analyses/${analysis.analysis_id}/${item.tab}`}
              className="group flex flex-col justify-between rounded-lg border border-slate-200 bg-slate-50/60 p-3.5 transition-colors hover:border-blue-400 hover:bg-blue-50/40 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <div>
                <div className="flex items-center justify-between text-xs font-semibold text-slate-900 group-hover:text-blue-700">
                  <span>{item.title}</span>
                  <span aria-hidden="true">→</span>
                </div>
                <p className="mt-1 text-xs text-slate-600">{item.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default OverviewTab;
