/**
 * Live-analysis feedback ported from the Forecast Confidence Studio report stream:
 * heading-level generation status, the pipeline stage list, a polite status line
 * (announces stage changes, never every event) and the dismissible "ready" notice.
 */
import { createContext, useContext } from 'react';
import { Link } from 'react-router';
import clsx from 'clsx';
import { ALL_STAGES, type Analysis, type AnalysisEvent, type Stage } from '../../api/hooks';
import { CheckIcon, LoaderIcon, XIcon, buttonClasses } from '../../components/ui';
import { VERIFICATION_OVERALL_TOKENS, type VerificationOverallKey } from '../../lib/theme';
import {
  GENERATION_LABELS,
  STAGE_META,
  stageStatus,
  type GenerationStatus,
} from './liveStatus';

/* -------------------------------------------------------------------------- */
/* Sidebar slot: lets a tab (the report) place its contents list in the shell  */
/* -------------------------------------------------------------------------- */

export const ShellSidebarContext = createContext<HTMLElement | null>(null);

export function useShellSidebar(): HTMLElement | null {
  return useContext(ShellSidebarContext);
}

/* -------------------------------------------------------------------------- */
/* Generation status (Waiting / Generating / Complete / Not run)               */
/* -------------------------------------------------------------------------- */

export function GenerationStatusMark({
  status,
  compact = false,
  className,
}: {
  status: GenerationStatus;
  /** Icon-only below the `lg` breakpoint (the label stays for wide sidebars). */
  compact?: boolean;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        'inline-flex min-h-5 shrink-0 items-center gap-1.5 text-xs font-normal text-muted-foreground',
        className,
      )}
    >
      {status === 'generating' && <LoaderIcon className="h-3.5 w-3.5 text-primary" />}
      {status === 'complete' && <CheckIcon className="h-3.5 w-3.5 text-success" />}
      {status === 'waiting' && (
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50" />
      )}
      {status === 'not_run' && <XIcon className="h-3.5 w-3.5 text-muted-foreground" />}
      <span className={clsx(compact && 'hidden lg:inline')}>{GENERATION_LABELS[status]}</span>
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Pipeline stage list                                                         */
/* -------------------------------------------------------------------------- */

export function StageProgress({
  analysis,
  stagesDone,
  activeStage,
  compact = false,
  className,
}: {
  analysis: Analysis | undefined;
  stagesDone: readonly Stage[];
  activeStage: Stage | null;
  /** Hide stage descriptions (used once the run has finished). */
  compact?: boolean;
  className?: string;
}) {
  return (
    <ol
      aria-label="Pipeline stage progress"
      className={clsx(
        'grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 lg:grid-cols-1 lg:gap-y-0',
        className,
      )}
    >
      {ALL_STAGES.map((st, i) => {
        const status = stageStatus(st, analysis, stagesDone, activeStage);
        const timingMs = analysis?.stage_timings_ms?.[st];
        const meta = STAGE_META[st];
        return (
          <li
            key={st}
            className={clsx('relative flex gap-3 lg:last:pb-0', compact ? 'lg:pb-2.5' : 'lg:pb-4')}
          >
            {i < ALL_STAGES.length - 1 && (
              <span
                aria-hidden="true"
                className={clsx(
                  'absolute top-7 left-[11px] hidden h-[calc(100%-1.75rem)] w-px',
                  compact ? 'lg:hidden' : 'lg:block',
                  status === 'complete' ? 'bg-primary' : 'bg-border',
                )}
              />
            )}
            <span
              aria-hidden="true"
              className={clsx(
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border font-mono text-[10px]',
                status === 'complete' && 'border-primary bg-primary text-primary-foreground',
                status === 'generating' && 'border-primary text-primary',
                status === 'waiting' && 'border-border text-muted-foreground',
                status === 'not_run' && 'border-border text-muted-foreground/60',
              )}
            >
              {status === 'complete' ? (
                <CheckIcon className="h-3.5 w-3.5" strokeWidth={2.5} />
              ) : status === 'generating' ? (
                <LoaderIcon className="h-3.5 w-3.5" />
              ) : (
                i + 1
              )}
            </span>
            <div className="min-w-0 pt-0.5">
              <p
                className={clsx(
                  'text-xs leading-snug font-medium',
                  status === 'waiting' || status === 'not_run'
                    ? 'text-muted-foreground'
                    : 'text-foreground',
                )}
              >
                {meta.title}
                <span className="sr-only"> — {GENERATION_LABELS[status]}</span>
              </p>
              <p
                className={clsx(
                  'hidden text-[11px] leading-snug text-muted-foreground',
                  !compact && 'lg:block',
                )}
              >
                {meta.description}
              </p>
              {typeof timingMs === 'number' && (
                <p className="font-mono text-[10px] text-muted-foreground">{timingMs}ms</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* -------------------------------------------------------------------------- */
/* Live status line                                                            */
/* -------------------------------------------------------------------------- */

/** Announces status changes politely; never auto-scrolls. */
export function LiveStatusLine({
  analysis,
  activeStage,
  events,
}: {
  analysis: Analysis | undefined;
  activeStage: Stage | null;
  events: readonly AnalysisEvent[];
}) {
  const status = analysis?.status;
  if (status === 'completed' || status === 'failed') return null;

  const latest = [...events]
    .reverse()
    .find((e) => e.type !== 'error' && e.type !== 'failed' && Boolean(e.message));
  const title = activeStage ? STAGE_META[activeStage].active : 'Queued';

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-sm border border-border bg-muted/30 px-3 py-2 text-sm"
    >
      <span className="font-mono text-xs text-primary">Live Analysis</span>
      <span className="font-medium text-foreground">{title}</span>
      <span className="min-w-0 text-muted-foreground">
        {latest?.message ?? 'Preparing the policy analysis…'}
        <span aria-hidden="true" className="report-stream-cursor" />
      </span>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Ready notice                                                                */
/* -------------------------------------------------------------------------- */

export function ReadyNotice({
  analysis,
  onDismiss,
}: {
  analysis: Analysis;
  onDismiss: () => void;
}) {
  const overall = analysis.verification?.overall as VerificationOverallKey | undefined;
  const verdict = overall ? VERIFICATION_OVERALL_TOKENS[overall]?.label : undefined;
  const reportHref = `/analyses/${analysis.analysis_id}/report`;

  return (
    <aside
      aria-label="Policy assessment ready"
      data-print-hide="true"
      className="notice-enter fixed inset-x-4 bottom-12 z-40 mx-auto flex max-w-lg items-start gap-3 rounded-sm border border-border bg-popover p-4 text-popover-foreground shadow-lg shadow-black/40"
    >
      <CheckIcon className="mt-0.5 h-4 w-4 text-success" />
      <div role="status" className="min-w-0 flex-1">
        <p className="text-sm font-medium">Your policy assessment is ready</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Research, modelling and verification finished
          {verdict ? ` · ${verdict}` : ''}.
        </p>
        <Link to={reportHref} onClick={onDismiss} className={buttonClasses('outline', 'xs', 'mt-3')}>
          Open the policy report
        </Link>
      </div>
      <button
        type="button"
        aria-label="Dismiss completion notification"
        onClick={onDismiss}
        className={buttonClasses('ghost', 'icon-sm')}
      >
        <XIcon className="h-4 w-4" />
      </button>
    </aside>
  );
}
