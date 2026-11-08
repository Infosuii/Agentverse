import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Link, useParams } from 'react-router';
import clsx from 'clsx';
import {
  useAnalysis,
  type Analysis,
  type KeyFigure,
  type ReportSection,
  type Source,
} from '../../api/hooks';
import { ProvenanceNumber } from '../../components/charts';
import {
  Badge,
  DownloadIcon,
  EmptyState,
  EvidenceBadge,
  ExternalLinkIcon,
  PlaceholderBadge,
  PrinterIcon,
  Skeleton,
  VerificationBadge,
  WithheldBanner,
  buttonClasses,
} from '../../components/ui';
import { ReportMarkdown } from '../../components/report/ReportMarkdown';
import { TableOfContents, type TocEntry } from '../../components/report/TableOfContents';
import { useShellSidebar } from '../analysis/LiveAnalysis';
import { fmtDate, fmtFiscalYear, fmtGbpBn, fmtPct } from '../../lib/format';

export interface ReportTabProps {
  analysis?: Analysis;
}

interface FigureProvenanceProps {
  figure: KeyFigure;
  analysisId: string | undefined;
  sources: Source[];
}

const TIER_LABELS: Record<number, string> = {
  1: 'Tier 1 · Official',
  2: 'Tier 2 · Peer-reviewed / IFS',
  3: 'Tier 3 · Secondary',
};

/** Removes a leading "1." / "2.3" numbering; the report adds its own section numbers. */
export function stripHeadingNumber(heading: string): string {
  return heading.replace(/^\s*\d+(?:\.\d+)*\.?\s+/, '').trim() || heading;
}

function FigureProvenance({ figure, analysisId, sources }: FigureProvenanceProps) {
  return (
    <ProvenanceNumber
      value={figure.value}
      display={figure.display}
      calcStepIds={figure.calc_step_ids ?? []}
      sources={figure.source_ids ?? []}
      allSources={sources}
      evidenceClass={figure.evidence_class}
      analysisId={figure.evidence_class === 'model_scenario' ? analysisId : undefined}
      metric={figure.metric ?? undefined}
      year={figure.fiscal_year ?? undefined}
      className="font-mono text-2xl font-medium tracking-tight text-foreground"
    />
  );
}

function SectionHeading({ number, children }: { number: string; children: ReactNode }) {
  return (
    <h2 className="mb-4 flex min-w-0 items-baseline gap-3 font-display text-xl font-semibold text-foreground">
      <span className="font-mono text-sm text-primary">{number}</span>
      <span className="min-w-0">{children}</span>
    </h2>
  );
}

function ReportSectionBlock({
  id,
  number,
  title,
  first = false,
  className,
  children,
  ...rest
}: {
  id: string;
  number: string;
  title: ReactNode;
  first?: boolean;
  className?: string;
  children: ReactNode;
  'aria-label'?: string;
}) {
  return (
    <section
      id={id}
      className={clsx('scroll-mt-24', !first && 'border-t border-border pt-7', className)}
      {...rest}
    >
      <SectionHeading number={number}>{title}</SectionHeading>
      {children}
    </section>
  );
}

export function ReportTab({ analysis: propAnalysis }: ReportTabProps) {
  const { id } = useParams<{ id: string }>();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(propAnalysis ? undefined : id);
  const analysis = propAnalysis ?? fetchedAnalysis;
  const sidebarSlot = useShellSidebar();

  const report = analysis?.report;
  const sources = useMemo(() => analysis?.sources ?? [], [analysis?.sources]);
  const sourceIds = useMemo(() => new Set(sources.map((s) => s.source_id)), [sources]);

  if (!analysis && isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28" />
        <Skeleton lines={8} />
      </div>
    );
  }

  if (!analysis || !report) {
    return (
      <EmptyState
        title="Policy assessment report not ready"
        description="The policy assessment report is generated in the final pipeline stage after verification completes."
      />
    );
  }

  const analysisId = analysis.analysis_id ?? id;
  const hasPlaceholder = Boolean(
    sources.some((s) => s.is_placeholder) ||
      analysis.simulation?.assumptions?.some((a) => a.is_placeholder),
  );

  const declineReasons = [
    ...(analysis.verification?.decline_reasons ?? []),
    ...(analysis.scope?.forecast_allowed === false ? (analysis.scope.reasons ?? []) : []),
  ];
  const uniqueReasons = Array.from(new Set(declineReasons));

  const scenarios = analysis.simulation?.scenarios ?? [];
  const fiscalYears = scenarios[0]?.result.fiscal_years ?? [];
  const y1 = fiscalYears[0];
  const finalYear = fiscalYears[fiscalYears.length - 1];
  const keyFigures = report.key_figures ?? [];
  const showScenarioTable = !report.forecast_withheld && scenarios.length > 0 && Boolean(y1 && finalYear);

  // Executive summary is always section 01; the remaining generated sections follow in order.
  const summarySection = report.sections.find((s) => s.section_id === 'executive_summary');
  const bodySections: ReportSection[] = report.sections.filter(
    (s) => s.section_id !== 'executive_summary',
  );
  const hasModelledSection = bodySections.some((s) => s.section_id === 'modelled_impacts');
  const fallbackToMarkdown = report.sections.length === 0;

  const toc: TocEntry[] = [{ id: 'report-summary', title: 'Executive summary', number: '01', depth: 0 }];
  let n = 1;
  if (fallbackToMarkdown) {
    n += 1;
    toc.push({ id: 'report-document', title: 'Full assessment', number: String(n).padStart(2, '0'), depth: 0 });
  }
  for (const sec of bodySections) {
    n += 1;
    toc.push({
      id: `report-${sec.section_id}`,
      title: stripHeadingNumber(sec.heading),
      number: String(n).padStart(2, '0'),
      depth: 0,
    });
    if (sec.section_id === 'modelled_impacts' && showScenarioTable) {
      toc.push({
        id: 'report-scenario-comparison',
        title: 'Scenario comparison',
        number: `${String(n).padStart(2, '0')}.1`,
        depth: 1,
      });
    }
  }
  if (showScenarioTable && !hasModelledSection) {
    n += 1;
    toc.push({ id: 'report-scenario-comparison', title: 'Scenario comparison', number: String(n).padStart(2, '0'), depth: 0 });
  }
  if (sources.length > 0) {
    n += 1;
    toc.push({ id: 'report-sources', title: 'Sources & data provenance', number: String(n).padStart(2, '0'), depth: 0 });
  }
  const numberOf = (anchor: string) => toc.find((e) => e.id === anchor)?.number ?? '';

  const scenarioTable = showScenarioTable && y1 && finalYear && (
    <figure id="report-scenario-comparison" className="scroll-mt-24 border-y border-border">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border py-3">
        <span className="text-sm font-medium text-foreground">Scenario Comparison Summary</span>
        <span className="text-xs text-muted-foreground">
          Central, Optimistic, and Pessimistic paths ({fmtFiscalYear(y1)} to {fmtFiscalYear(finalYear)})
        </span>
      </figcaption>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-2 py-2.5 font-medium">Scenario</th>
              <th className="px-2 py-2.5 font-medium">Evidence class</th>
              <th className="px-2 py-2.5 text-right font-medium">Behavioural Rev ({fmtFiscalYear(y1)})</th>
              <th className="px-2 py-2.5 text-right font-medium">Behavioural Rev ({fmtFiscalYear(finalYear)})</th>
              <th className="px-2 py-2.5 text-right font-medium">Static Rev ({fmtFiscalYear(finalYear)})</th>
              <th className="px-2 py-2.5 text-right font-medium">Investment ({fmtFiscalYear(finalYear)})</th>
              <th className="px-2 py-2.5 text-right font-medium">GDP Level ({fmtFiscalYear(finalYear)})</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((scen) => {
              const mMap = new Map(scen.result.metrics.map((m) => [m.metric, m]));
              const bValues = mMap.get('revenue_behavioural_gbp_bn')?.values ?? [];
              const sValues = mMap.get('revenue_static_gbp_bn')?.values ?? [];
              const iValues = mMap.get('business_investment_pct')?.values ?? [];
              const gValues = mMap.get('gdp_level_pct')?.values ?? [];

              return (
                <tr key={scen.scenario.name} className="border-b border-border last:border-0 hover:bg-muted/30">
                  <td className="px-2 py-2.5 font-medium text-foreground">{scen.scenario.label}</td>
                  <td className="px-2 py-2.5">
                    <EvidenceBadge evidenceClass="model_scenario" short />
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono tabular-nums">
                    {fmtGbpBn(bValues[0]?.value)}
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono tabular-nums">
                    {fmtGbpBn(bValues[bValues.length - 1]?.value)}
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono text-muted-foreground tabular-nums">
                    {fmtGbpBn(sValues[sValues.length - 1]?.value)}
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono text-muted-foreground tabular-nums">
                    {fmtPct(iValues[iValues.length - 1]?.value)}
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono text-muted-foreground tabular-nums">
                    {fmtPct(gValues[gValues.length - 1]?.value)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-border py-2 font-mono text-[11px] text-muted-foreground">
        Model scenarios under explicit assumptions · £bn Exchequer impact (+ = revenue raised)
      </p>
    </figure>
  );

  return (
    <article aria-label="Policy assessment report" className="max-w-[1000px] space-y-7">
      {sidebarSlot && createPortal(<TableOfContents entries={toc} />, sidebarSlot)}

      {/* Publication header */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="slate">Policy Report</Badge>
          <Badge
            variant={report.generated_by === 'gemini' ? 'green' : 'blue'}
            aria-label={`Generated by: ${report.generated_by}`}
          >
            Generated by: {report.generated_by === 'gemini' ? 'Gemini Narrative' : 'Template'}
            {report.model ? ` (${report.model})` : ''}
          </Badge>
          <VerificationBadge overall={report.verification_overall} />
          {hasPlaceholder && <PlaceholderBadge />}
        </div>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="max-w-3xl font-display text-xl leading-snug font-semibold text-foreground sm:text-2xl">
            {report.title}
          </h2>
          <div data-print-hide="true" className="no-print flex flex-wrap items-center gap-2">
            {analysisId && (
              <a
                href={`/api/analyses/${encodeURIComponent(analysisId)}/report.md`}
                download={`jane-avenue-${analysisId}-report.md`}
                className={buttonClasses('outline', 'sm')}
              >
                <DownloadIcon className="h-3.5 w-3.5" />
                <span>Download .md</span>
              </a>
            )}
            <button
              type="button"
              onClick={() => window.print()}
              className={buttonClasses('primary', 'sm')}
            >
              <PrinterIcon className="h-3.5 w-3.5" />
              <span>Print / Save as PDF</span>
            </button>
          </div>
        </div>

        <p className="font-mono text-xs text-muted-foreground">
          Generated {fmtDate(report.generated_at)} · {toc.filter((e) => e.depth === 0).length} sections ·{' '}
          {keyFigures.length} traceable figures · {sources.length} sources · numbers inserted by code
        </p>
      </header>

      {report.forecast_withheld && <WithheldBanner reasons={uniqueReasons} />}

      {/* 01 Executive summary + key figures */}
      <ReportSectionBlock
        id="report-summary"
        number="01"
        title="Executive summary"
        first
        aria-label="Executive summary"
        className="border-t border-border pt-7"
      >
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <Badge variant="blue">Evidence-backed synthesis</Badge>
        </div>
        <ReportMarkdown
          markdown={summarySection?.body_markdown || report.executive_summary}
          sourceIds={sourceIds}
          analysisId={analysisId}
          lead
          className="mt-3"
        />

        {keyFigures.length > 0 && (
          <section aria-label="Report key figures" className="mt-6">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[11px] tracking-[0.14em] text-primary uppercase">
                Key figures
              </p>
              <span className="text-xs text-muted-foreground">
                {keyFigures.length} traceable figures · hover or click any number for its calculation steps &amp; provenance
              </span>
            </div>
            <div className="grid grid-cols-1 gap-x-6 gap-y-5 border-t border-border pt-5 sm:grid-cols-2 xl:grid-cols-4">
              {keyFigures.map((fig) => {
                const inspectorParams = new URLSearchParams();
                if (fig.metric) inspectorParams.set('metric', fig.metric);
                if (fig.fiscal_year) inspectorParams.set('year', fig.fiscal_year);
                const qs = inspectorParams.toString();
                const inspectorHref =
                  analysisId && fig.evidence_class === 'model_scenario'
                    ? `/analyses/${analysisId}/assumptions${qs ? `?${qs}` : ''}`
                    : null;

                return (
                  <div key={fig.figure_id} className="flex min-w-0 flex-col">
                    <span className="min-h-[2.6em] text-xs leading-snug text-muted-foreground">
                      {fig.label}
                    </span>
                    <div className="mt-1.5">
                      <FigureProvenance figure={fig} analysisId={analysisId} sources={sources} />
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                      <EvidenceBadge evidenceClass={fig.evidence_class} short />
                      <span className="font-mono">{fig.figure_id}</span>
                      {inspectorHref && (
                        <Link
                          to={inspectorHref}
                          data-print-hide="true"
                          className="no-print font-medium text-primary hover:underline"
                        >
                          Inspect formula →
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </ReportSectionBlock>

      {fallbackToMarkdown && (
        <ReportSectionBlock id="report-document" number={numberOf('report-document')} title="Full assessment">
          <ReportMarkdown markdown={report.markdown} sourceIds={sourceIds} analysisId={analysisId} />
        </ReportSectionBlock>
      )}

      {bodySections.map((sec) => (
        <ReportSectionBlock
          key={sec.section_id}
          id={`report-${sec.section_id}`}
          number={numberOf(`report-${sec.section_id}`)}
          title={stripHeadingNumber(sec.heading)}
        >
          <ReportMarkdown markdown={sec.body_markdown} sourceIds={sourceIds} analysisId={analysisId} />
          {sec.section_id === 'modelled_impacts' && scenarioTable && (
            <div className="mt-6">
              <h3 className="mb-3 flex items-baseline gap-2.5 font-display text-lg font-semibold">
                <span className="font-mono text-xs text-primary/80">
                  {numberOf('report-scenario-comparison')}
                </span>
                Scenario comparison
              </h3>
              {scenarioTable}
            </div>
          )}
        </ReportSectionBlock>
      ))}

      {showScenarioTable && !hasModelledSection && (
        <ReportSectionBlock
          id="report-scenario-comparison-section"
          number={numberOf('report-scenario-comparison')}
          title="Scenario comparison"
        >
          {scenarioTable}
        </ReportSectionBlock>
      )}

      {/* Numbered source directory with access dates and provenance */}
      {sources.length > 0 && (
        <ReportSectionBlock
          id="report-sources"
          number={numberOf('report-sources')}
          title="Sources & data provenance"
          className="print-page-break"
        >
          <div className="border-y border-border">
            <p className="border-b border-border py-3 text-sm font-medium text-foreground">
              Cited Sources &amp; Provenance Directory
              <span className="ml-2 font-normal text-muted-foreground">
                {sources.length} sources registered in this analysis
              </span>
            </p>
            <ol className="divide-y divide-border">
              {sources.map((src, i) => (
                <li
                  key={src.source_id}
                  id={`src-${src.source_id}`}
                  className="grid scroll-mt-24 grid-cols-[auto_1fr] gap-3 py-3 text-sm"
                >
                  <span className="font-mono text-xs text-primary">[{i + 1}]</span>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2">
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-foreground hover:text-primary hover:underline"
                      >
                        {src.title} <ExternalLinkIcon className="inline h-3 w-3" />
                      </a>
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <span className="font-mono text-foreground/80">[{src.source_id}]</span>
                      <span>{src.publisher}</span>
                      {src.retrieved_at && <span>· Accessed {fmtDate(src.retrieved_at)}</span>}
                      <span className="rounded-sm border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-secondary-foreground uppercase">
                        {TIER_LABELS[src.reliability_tier] ?? `Tier ${src.reliability_tier}`}
                      </span>
                      <span>{src.url_verified ? '✓ URL verified' : '• Unverified URL'}</span>
                      {src.is_placeholder && <PlaceholderBadge />}
                    </div>
                    <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
                      {src.url}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </ReportSectionBlock>
      )}
    </article>
  );
}

export default ReportTab;
