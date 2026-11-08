import { useEffect, useState } from 'react';
import {
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
} from 'react-router';
import {
  ApiClientError,
  useAnalysis,
  useAnalysisEvents,
  type Analysis,
  type UseAnalysisEventsResult,
} from '../../api/hooks';
import {
  Badge,
  ErrorBoundary,
  Eyebrow,
  InlineError,
  ModeBadge,
  PlaceholderBadge,
  PrinterIcon,
  Skeleton,
  Tabs,
  VerificationBadge,
  buttonClasses,
  type TabItem,
} from '../../components/ui';
import { fmtDate } from '../../lib/format';
import {
  GenerationStatusMark,
  LiveStatusLine,
  ReadyNotice,
  ShellSidebarContext,
  StageProgress,
} from './LiveAnalysis';
import {
  isTerminal as isTerminalAnalysis,
  resolveActiveStage,
  tabStatus,
  type AnalysisTabId,
} from './liveStatus';

export interface AnalysisOutletContext {
  analysis: Analysis | undefined;
  eventsState: UseAnalysisEventsResult;
}

export function useAnalysisContext(): AnalysisOutletContext {
  return useOutletContext<AnalysisOutletContext>();
}

const TAB_DEFS: { id: AnalysisTabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'research', label: 'Research' },
  { id: 'precedents', label: 'Precedents' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'assumptions', label: 'Assumptions' },
  { id: 'verification', label: 'Verification' },
  { id: 'report', label: 'Report' },
];

const POLICY_TYPE_LABELS: Record<string, string> = {
  corporation_tax_main_rate: 'Corporation tax · main rate',
  corporation_tax_small_profits_rate: 'Corporation tax · small profits rate',
  vat_standard_rate: 'VAT · standard rate',
  unsupported: 'Outside validated scope',
};

export function AnalysisShell() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const {
    data: analysis,
    isLoading,
    isError,
    error,
    refetch,
  } = useAnalysis(id);
  const eventsState = useAnalysisEvents(id);

  // Element in the sidebar where a tab may portal secondary navigation (report contents).
  const [sidebarSlot, setSidebarSlot] = useState<HTMLElement | null>(null);

  // Show the studio "ready" notice only when the run finishes while the analyst watches.
  const [sawRunning, setSawRunning] = useState(false);
  const [readyDismissed, setReadyDismissed] = useState(false);
  const status = analysis?.status;
  const running = Boolean(status) && status !== 'completed' && status !== 'failed';
  useEffect(() => {
    setSawRunning(false);
    setReadyDismissed(false);
  }, [id]);
  useEffect(() => {
    if (running) setSawRunning(true);
  }, [running]);

  if (isLoading && !analysis) {
    return (
      <div className="grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
        <div className="hidden space-y-2 lg:block">
          <Skeleton lines={7} />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-9 w-3/4" />
          <Skeleton lines={6} />
        </div>
      </div>
    );
  }

  if (isError && !analysis) {
    return (
      <InlineError
        title="Could not load analysis"
        message={error instanceof Error ? error.message : 'Analysis not found'}
        reasons={error instanceof ApiClientError ? error.reasons : undefined}
        onRetry={() => void refetch()}
      />
    );
  }

  const isTerminal = isTerminalAnalysis(analysis);
  const activeStage = resolveActiveStage(analysis, eventsState.stage);

  const pathSegments = location.pathname.split('/').filter(Boolean);
  const currentTab = pathSegments[2] ?? 'overview';

  const hasPlaceholder = Boolean(
    analysis?.sources?.some((s) => s.is_placeholder) ||
      analysis?.simulation?.assumptions?.some((a) => a.is_placeholder) ||
      analysis?.precedents?.matches?.some((m) => m.change.is_placeholder),
  );

  const disabledFor: Record<AnalysisTabId, boolean> = {
    overview: false,
    research: false,
    precedents: !analysis?.precedents && !isTerminal,
    scenarios: !analysis?.simulation && !isTerminal,
    assumptions: !analysis?.simulation && !isTerminal,
    verification: !analysis?.verification && !isTerminal,
    report: !analysis?.report && !isTerminal,
  };

  const tabItems: TabItem[] = TAB_DEFS.map((tab, i) => ({
    id: tab.id,
    label: tab.label,
    number: String(i + 1).padStart(2, '0'),
    disabled: disabledFor[tab.id],
    status:
      analysis && analysis.status !== 'completed' ? (
        <GenerationStatusMark
          compact
          status={tabStatus(tab.id, analysis, eventsState.stagesDone, activeStage)}
        />
      ) : undefined,
  }));

  const handleTabChange = (tabId: string) => {
    if (!id) return;
    void navigate(`/analyses/${id}/${tabId}`);
  };

  const title =
    analysis?.policy?.description || analysis?.request?.query || `Analysis ${id}`;
  const showQuery =
    Boolean(analysis?.request?.query) &&
    Boolean(analysis?.policy?.description) &&
    analysis?.policy?.description !== analysis?.request?.query;
  const policyTypeLabel = analysis?.policy?.policy_type
    ? POLICY_TYPE_LABELS[analysis.policy.policy_type] ?? analysis.policy.policy_type
    : undefined;
  const sourceCount = analysis?.sources?.length ?? 0;
  const showReady =
    analysis?.status === 'completed' && sawRunning && !readyDismissed;

  return (
    <ShellSidebarContext.Provider value={sidebarSlot}>
      <div className="grid gap-x-10 gap-y-5 lg:grid-cols-[220px_minmax(0,1fr)] print:block">
        {/* Report-style header (studio publication header). */}
        <header className="min-w-0 border-b border-border pb-5 lg:col-start-2 lg:row-start-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="slate">Policy Analysis</Badge>
            {policyTypeLabel && <Badge variant="outline">{policyTypeLabel}</Badge>}
            <Badge variant="outline">United Kingdom</Badge>
            <ModeBadge mode={analysis?.mode} />
            {analysis?.verification && (
              <VerificationBadge overall={analysis.verification.overall} />
            )}
            {hasPlaceholder && <PlaceholderBadge />}
          </div>

          <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
            <h1 className="max-w-4xl font-display text-2xl leading-snug font-semibold text-foreground sm:text-3xl">
              {title}
            </h1>
            <button
              type="button"
              onClick={() => window.print()}
              data-print-hide="true"
              title="Print analysis view"
              className={buttonClasses('outline', 'xs', 'no-print mt-1')}
            >
              <PrinterIcon className="h-3.5 w-3.5" />
              <span>Print view</span>
            </button>
          </div>

          {showQuery && (
            <p className="mt-2 text-sm text-muted-foreground">
              Query: &ldquo;{analysis?.request?.query}&rdquo;
            </p>
          )}

          <p className="mt-2 font-mono text-xs text-muted-foreground">
            {isTerminal ? `Analysis ${analysis?.analysis_id ?? id}` : 'Live Analysis'}
            {analysis?.created_at ? ` · created ${fmtDate(analysis.created_at)}` : ''}
            {` · ${sourceCount} source${sourceCount === 1 ? '' : 's'}`}
            {' · figures in GBP · fiscal year April–March'}
            {analysis?.status ? ` · ${analysis.status}` : ''}
          </p>
        </header>

        {/* Studio contents rail: numbered views with live generation feedback. */}
        <aside
          data-print-hide="true"
          className="no-print min-w-0 lg:sticky lg:top-20 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:max-h-[calc(100vh-6rem)] lg:self-start lg:overflow-y-auto lg:pr-1"
        >
          <Eyebrow className="mb-3 hidden lg:block">
            {isTerminal ? 'Policy analysis' : 'Live analysis'}
          </Eyebrow>
          <Tabs
            items={tabItems}
            activeId={currentTab}
            onChange={handleTabChange}
            ariaLabel="Analysis views"
            orientation="responsive"
          />

          <div className="mt-5 lg:mt-7">
            <Eyebrow className="mb-3">Pipeline</Eyebrow>
            <StageProgress
              analysis={analysis}
              stagesDone={eventsState.stagesDone}
              activeStage={activeStage}
              compact={isTerminal}
            />
          </div>

          <div ref={setSidebarSlot} className="hidden lg:block" />
        </aside>

        <div className="min-w-0 space-y-5 lg:col-start-2">
          <LiveStatusLine
            analysis={analysis}
            activeStage={activeStage}
            events={eventsState.events}
          />

          {(analysis?.status === 'failed' || analysis?.error || eventsState.error) && (
            <InlineError
              title="Analysis pipeline error"
              message={
                analysis?.error ||
                eventsState.error ||
                'An error occurred during analysis execution.'
              }
              onRetry={() => void refetch()}
            />
          )}

          <ErrorBoundary key={currentTab}>
            <Outlet context={{ analysis, eventsState } satisfies AnalysisOutletContext} />
          </ErrorBoundary>
        </div>
      </div>

      {showReady && analysis && (
        <ReadyNotice analysis={analysis} onDismiss={() => setReadyDismissed(true)} />
      )}
    </ShellSidebarContext.Provider>
  );
}

export default AnalysisShell;
