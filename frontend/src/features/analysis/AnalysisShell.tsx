import {
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
} from 'react-router';
import clsx from 'clsx';
import {
  ALL_STAGES,
  ApiClientError,
  useAnalysis,
  useAnalysisEvents,
  type Analysis,
  type Stage,
  type UseAnalysisEventsResult,
} from '../../api/hooks';
import {
  Badge,
  Card,
  InlineError,
  ModeBadge,
  PlaceholderBadge,
  Skeleton,
  Spinner,
  Tabs,
  VerificationBadge,
} from '../../components/ui';

export interface AnalysisOutletContext {
  analysis: Analysis | undefined;
  eventsState: UseAnalysisEventsResult;
}

export function useAnalysisContext(): AnalysisOutletContext {
  return useOutletContext<AnalysisOutletContext>();
}

const STAGE_LABELS: Record<Stage, string> = {
  parsing: '1. Parse & Scope',
  researching: '2. Research',
  precedents: '3. Precedents',
  modelling: '4. Model & MC',
  verifying: '5. Verify',
  reporting: '6. Report',
};

function isStageComplete(
  stage: Stage,
  analysis: Analysis | undefined,
  stagesDone: Stage[],
): boolean {
  if (analysis?.status === 'completed') return true;
  if (stagesDone.includes(stage)) return true;
  if (analysis?.stage_timings_ms && stage in analysis.stage_timings_ms) return true;
  if (stage === 'parsing' && analysis?.policy) return true;
  if (stage === 'researching' && analysis?.research) return true;
  if (stage === 'precedents' && analysis?.precedents) return true;
  if (stage === 'modelling' && analysis?.simulation) return true;
  if (stage === 'verifying' && analysis?.verification) return true;
  if (stage === 'reporting' && analysis?.report) return true;
  return false;
}

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

  if (isLoading && !analysis) {
    return (
      <div className="space-y-4">
        <Card>
          <Skeleton lines={3} />
        </Card>
        <Card>
          <Skeleton lines={6} />
        </Card>
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

  const activeStage: Stage | null =
    analysis?.status === 'completed' || analysis?.status === 'failed'
      ? null
      : eventsState.stage ??
        (ALL_STAGES.includes(analysis?.status as Stage)
          ? (analysis?.status as Stage)
          : null);

  const pathSegments = location.pathname.split('/').filter(Boolean);
  const currentTab = pathSegments[2] ?? 'overview';

  const isTerminal =
    analysis?.status === 'completed' || analysis?.status === 'failed';

  const hasPlaceholder = Boolean(
    analysis?.sources?.some((s) => s.is_placeholder) ||
      analysis?.simulation?.assumptions?.some((a) => a.is_placeholder) ||
      analysis?.precedents?.matches?.some((m) => m.change.is_placeholder),
  );

  const tabItems = [
    {
      id: 'overview',
      label: 'Overview',
      disabled: false,
    },
    {
      id: 'research',
      label: 'Research',
      disabled: false,
    },
    {
      id: 'precedents',
      label: 'Precedents',
      disabled: !analysis?.precedents && !isTerminal,
    },
    {
      id: 'scenarios',
      label: 'Scenarios',
      disabled: !analysis?.simulation && !isTerminal,
    },
    {
      id: 'assumptions',
      label: 'Assumptions',
      disabled: !analysis?.simulation && !isTerminal,
    },
    {
      id: 'verification',
      label: 'Verification',
      disabled: !analysis?.verification && !isTerminal,
    },
    {
      id: 'report',
      label: 'Report',
      disabled: !analysis?.report && !isTerminal,
    },
  ];

  const handleTabChange = (tabId: string) => {
    if (!id) return;
    void navigate(`/analyses/${id}/${tabId}`);
  };

  return (
    <div className="space-y-4">
      <Card padding="md" data-print-hide="false">
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight text-slate-900 sm:text-xl">
                  {analysis?.policy?.description ||
                    analysis?.request?.query ||
                    `Analysis ${id}`}
                </h1>
                {!isTerminal && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                    <Spinner size="xs" />
                    <span>Running ({analysis?.status ?? 'queued'})</span>
                  </span>
                )}
              </div>
              {analysis?.request?.query &&
                analysis?.policy?.description &&
                analysis.policy.description !== analysis.request.query && (
                  <p className="text-xs text-slate-500">
                    Query: &ldquo;{analysis.request.query}&rdquo;
                  </p>
                )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <ModeBadge mode={analysis?.mode} />
              {analysis?.verification && (
                <VerificationBadge overall={analysis.verification.overall} />
              )}
              {hasPlaceholder && <PlaceholderBadge />}
              <button
                type="button"
                onClick={() => window.print()}
                data-print-hide="true"
                className="no-print inline-flex items-center gap-1 rounded border border-slate-200 bg-white px-2.5 py-0.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                title="Print analysis view"
              >
                Print view
              </button>
            </div>
          </div>

          {/* 6-Stage Progress Bar */}
          <div
            aria-label="Pipeline stage progress"
            className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6"
          >
            {ALL_STAGES.map((st) => {
              const done = isStageComplete(st, analysis, eventsState.stagesDone);
              const active = activeStage === st && !done;
              const timingMs = analysis?.stage_timings_ms?.[st];

              return (
                <div
                  key={st}
                  className={clsx(
                    'flex items-center justify-between rounded-md border px-2.5 py-1.5 text-xs transition-colors',
                    done
                      ? 'border-emerald-200 bg-emerald-50/70 text-emerald-900'
                      : active
                        ? 'border-blue-400 bg-blue-50 text-blue-900 ring-1 ring-blue-300'
                        : 'border-slate-200 bg-slate-50 text-slate-500',
                  )}
                >
                  <span className="flex items-center gap-1.5 font-medium truncate">
                    <span aria-hidden="true">
                      {done ? '✓' : active ? '●' : '○'}
                    </span>
                    <span className="truncate">{STAGE_LABELS[st]}</span>
                  </span>
                  {typeof timingMs === 'number' && (
                    <Badge variant="slate" className="ml-1 px-1.5 py-0 text-[10px]">
                      {timingMs}ms
                    </Badge>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </Card>

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

      <div data-print-hide="true" className="no-print">
        <Tabs
          items={tabItems}
          activeId={currentTab}
          onChange={handleTabChange}
          ariaLabel="Analysis views"
        />
      </div>

      <div className="pt-1">
        <Outlet context={{ analysis, eventsState } satisfies AnalysisOutletContext} />
      </div>
    </div>
  );
}

export default AnalysisShell;
