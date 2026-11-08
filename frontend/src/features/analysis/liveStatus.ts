/**
 * Pure helpers that translate the pipeline (Analysis status + SSE stage events) into the
 * Forecast Confidence Studio's live-generation vocabulary: Waiting → Generating → Complete.
 */
import { ALL_STAGES, type Analysis, type Stage } from '../../api/hooks';

export type GenerationStatus = 'waiting' | 'generating' | 'complete' | 'not_run';

export type AnalysisTabId =
  | 'overview'
  | 'research'
  | 'precedents'
  | 'scenarios'
  | 'assumptions'
  | 'verification'
  | 'report';

export const STAGE_META: Record<Stage, { title: string; description: string; active: string }> =
  {
    parsing: {
      title: 'Parse & scope',
      description: 'Structured policy and validated-scope gate',
      active: 'Parsing the policy',
    },
    researching: {
      title: 'Research',
      description: 'Grounded search, fetched documents, verified quotes',
      active: 'Researching the evidence',
    },
    precedents: {
      title: 'Precedents',
      description: 'Comparable UK corporation tax changes',
      active: 'Matching historical precedents',
    },
    modelling: {
      title: 'Model & Monte Carlo',
      description: 'Scenarios, uncertainty bands and sensitivity',
      active: 'Running the econometric model',
    },
    verifying: {
      title: 'Verify',
      description: 'Independent checks; may withhold the forecast',
      active: 'Verifying every claim',
    },
    reporting: {
      title: 'Report',
      description: 'Evidence-backed assessment with code-inserted figures',
      active: 'Writing the policy assessment',
    },
  };

/** Which pipeline stages feed each analysis view. */
export const TAB_STAGES: Record<AnalysisTabId, readonly Stage[]> = {
  overview: ALL_STAGES,
  research: ['researching'],
  precedents: ['precedents'],
  scenarios: ['modelling'],
  assumptions: ['modelling'],
  verification: ['verifying'],
  report: ['reporting'],
};

export function isTerminal(analysis: Analysis | undefined): boolean {
  return analysis?.status === 'completed' || analysis?.status === 'failed';
}

export function isStageComplete(
  stage: Stage,
  analysis: Analysis | undefined,
  stagesDone: readonly Stage[],
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

/** The stage currently running, preferring the live SSE signal over the polled status. */
export function resolveActiveStage(
  analysis: Analysis | undefined,
  liveStage: Stage | null,
): Stage | null {
  if (isTerminal(analysis)) return null;
  if (liveStage) return liveStage;
  const status = analysis?.status as Stage | undefined;
  return status && ALL_STAGES.includes(status) ? status : null;
}

export function stageStatus(
  stage: Stage,
  analysis: Analysis | undefined,
  stagesDone: readonly Stage[],
  activeStage: Stage | null,
): GenerationStatus {
  if (isStageComplete(stage, analysis, stagesDone)) return 'complete';
  if (analysis?.status === 'failed') return 'not_run';
  if (activeStage === stage) return 'generating';
  return 'waiting';
}

export function tabStatus(
  tab: AnalysisTabId,
  analysis: Analysis | undefined,
  stagesDone: readonly Stage[],
  activeStage: Stage | null,
): GenerationStatus {
  if (tab === 'overview') {
    if (analysis?.status === 'completed') return 'complete';
    if (analysis?.status === 'failed') return 'not_run';
    return 'generating';
  }
  const statuses = TAB_STAGES[tab].map((st) =>
    stageStatus(st, analysis, stagesDone, activeStage),
  );
  if (statuses.every((s) => s === 'complete')) return 'complete';
  if (statuses.includes('generating')) return 'generating';
  if (statuses.includes('not_run')) return 'not_run';
  return 'waiting';
}

export const GENERATION_LABELS: Record<GenerationStatus, string> = {
  waiting: 'Waiting',
  generating: 'Generating',
  complete: 'Complete',
  not_run: 'Not run',
};
