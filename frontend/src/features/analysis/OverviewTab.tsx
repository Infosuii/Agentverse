import type { ReactNode } from 'react';
import { Link, useOutletContext, useParams } from 'react-router';
import {
  useAnalysis,
  type Analysis,
  type MetricName,
  type MetricProjection,
  type PercentileBand,
} from '../../api/hooks';
import type { AnalysisOutletContext } from './AnalysisShell';
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
import { FanChart } from '../../components/charts';
import { fmtDate, fmtFiscalYear, fmtGbpBn, fmtPct } from '../../lib/format';
import { isResearchOnly, policyArea, policyChangeLabel, policyChangeText, policyTypeLabel } from '../../lib/policy';
import { withheldReasons } from '../../lib/reasons';

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

function OverviewHeading({ number, children }: { number: string; children: ReactNode }) {
  return (
    <h2 className="flex items-baseline gap-3 font-display text-lg font-semibold text-foreground">
      <span aria-hidden="true" className="font-mono text-sm text-primary">
        {number}
      </span>
      {children}
    </h2>
  );
}

export function OverviewTab({ analysis: propAnalysis }: OverviewTabProps) {
  const { id } = useParams<{ id: string }>();
  const outletCtx = useOutletContext<AnalysisOutletContext | undefined>();
  const activityEvents = outletCtx?.eventsState?.events ?? [];
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

  const uniqueReasons = withheldReasons(analysis);

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

  const researchOnly = isResearchOnly(analysis.policy);

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
      description: `${analysis.precedents?.matches?.length ?? 0} matched historical changes to ${policyArea(analysis.policy)}`,
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


  return (
    <div className="space-y-6">
      {!forecastAllowed && <WithheldBanner reasons={uniqueReasons} />}

      {/* Headline Stat Tiles */}
      <section aria-label="Headline model projections">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <OverviewHeading number="01">Headline Projections (Central Scenario)</OverviewHeading>
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

          {(invPct || !forecastAllowed) && !researchOnly && (
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
          )}

          {(gdpPct || !forecastAllowed) && !researchOnly && (
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
          )}
        </div>

        {forecastAllowed && mcRevDist && mcRevDist.bands.length > 0 && (
          <div className="mt-4">
            <FanChart
              title={`Monte Carlo Simulation Trajectories — ${revBehav?.label ?? 'Behavioural Revenue Change'}`}
              caption={`Simulated draws (${analysis.simulation?.monte_carlo?.n_draws ?? 2000} trajectories), pale green p5–p95 band, upper 95% bound (green), lower 5% bound (red), and average path (bold black).`}
              unit={mcRevDist.unit}
              bands={mcRevDist.bands.map((b) => ({
                x: b.fiscal_year,
                p5: b.p5,
                p10: b.p10,
                p25: b.p25,
                p50: b.p50,
                p75: b.p75,
                p90: b.p90,
                p95: b.p95,
                mean: b.mean,
              }))}
              intervalNote={
                analysis.simulation?.monte_carlo?.interval_note ??
                'assumption-driven ranges, not statistical prediction intervals; exclude model and data uncertainty'
              }
            />
          </div>
        )}
      </section>

      {/* Policy & Research Summary */}
      <div className="border-t border-border pt-6">
        <OverviewHeading number="02">Policy &amp; Evidence Summary</OverviewHeading>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Policy Specification" className="lg:col-span-1">
          {analysis.policy ? (
            <dl className="space-y-2 text-xs">
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Policy type:</dt>
                <dd className="font-medium text-foreground">
                  {policyTypeLabel(analysis.policy)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">{policyChangeLabel(analysis.policy)}:</dt>
                <dd className="font-semibold text-foreground tabular-nums">
                  {policyChangeText(analysis.policy)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Effective date:</dt>
                <dd className="font-medium text-foreground">
                  {fmtDate(analysis.policy.effective_date)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Horizon:</dt>
                <dd className="font-medium text-foreground">
                  {analysis.policy.horizon_years} years
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Scope status:</dt>
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
              <span className="text-xs text-muted-foreground">
                {analysis.sources.length} sources in total (research, precedents, data)
              </span>
            ) : undefined
          }
        >
          <div className="space-y-3 text-xs leading-relaxed text-foreground/85">
            {analysis.research?.summary ? (
              <p>{analysis.research.summary}</p>
            ) : (
              <p className="text-muted-foreground">
                Research summary will appear here once the research stage completes.
              </p>
            )}
            {analysis.precedents?.summary && (
              <p className="border-t border-border/60 pt-2 text-muted-foreground">
                <strong className="text-foreground">Historical precedents: </strong>
                {analysis.precedents.summary}
              </p>
            )}
            {analysis.sources && analysis.sources.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[11px] font-medium text-muted-foreground">
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

      {/* Quick Links to All Analysis Tabs (studio ruled rows) */}
      <section aria-label="Explore Analysis Workstreams" className="border-t border-border pt-6">
        <OverviewHeading number="03">Explore Analysis Workstreams</OverviewHeading>
        <div className="mt-3 grid grid-cols-1 gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
          {quickLinks.map((item, idx) => (
            <Link
              key={item.tab}
              to={`/analyses/${analysis.analysis_id}/${item.tab}`}
              className="group block border-t border-border py-3 transition-colors hover:border-primary focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span className="flex items-center justify-between gap-2">
                <span className="flex items-baseline gap-2 text-sm font-medium text-foreground group-hover:text-primary">
                  <span aria-hidden="true" className="font-mono text-[11px] text-primary/80">
                    {String(idx + 2).padStart(2, '0')}
                  </span>
                  <span>{item.title}</span>
                </span>
                <span aria-hidden="true" className="text-muted-foreground group-hover:text-primary">
                  →
                </span>
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">{item.description}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Studio activity log: the pipeline's own event stream, newest last */}
      {activityEvents.length > 0 && (
        <section aria-label="Analysis activity" className="rounded-lg border border-border bg-muted/40 p-4">
          <p className="mb-2 font-mono text-[11px] tracking-[0.16em] text-muted-foreground uppercase">
            Analysis activity
          </p>
          <ul className="max-h-56 space-y-1 overflow-y-auto font-mono text-xs">
            {activityEvents.map((ev) => (
              <li
                key={ev.seq}
                className={
                  ev.type === 'error' || ev.type === 'failed'
                    ? 'text-red-300'
                    : ev.type === 'warning'
                      ? 'text-amber-300'
                      : 'text-muted-foreground'
                }
              >
                <span aria-hidden="true" className="text-primary">
                  ›
                </span>{' '}
                {ev.message}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default OverviewTab;
