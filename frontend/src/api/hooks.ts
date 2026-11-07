import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type { components } from './schema';

// Canonical contract types from generated OpenAPI schema (Appendix A)
export type Analysis = components['schemas']['Analysis'];
export type AnalysisCreated = components['schemas']['AnalysisCreated'];
export type AnalysisOptions = components['schemas']['AnalysisOptions'];
export type AnalysisRequest = components['schemas']['AnalysisRequest'];
export type AnalysisSummary = components['schemas']['AnalysisSummary'];
export type Assumption = components['schemas']['Assumption'];
export type BacktestCase = components['schemas']['BacktestCase'];
export type CalcStep = components['schemas']['CalcStep'];
export type Confounder = components['schemas']['Confounder'];
export type Costing = components['schemas']['Costing'];
export type DatasetMeta = components['schemas']['DatasetMeta'];
export type Distribution = components['schemas']['Distribution'];
export type EngineResult = components['schemas']['EngineResult'];
export type ErrorBody = components['schemas']['ErrorBody'];
export type EvaluationReport = components['schemas']['EvaluationReport'];
export type Evidence = components['schemas']['Evidence'];
export type HealthResponse = components['schemas']['HealthResponse'];
export type Histogram = components['schemas']['Histogram'];
export type Interpretation = components['schemas']['Interpretation'];
export type KeyFigure = components['schemas']['KeyFigure'];
export type MLExperiment = components['schemas']['MLExperiment'];
export type MacroContext = components['schemas']['MacroContext'];
export type MethodSummary = components['schemas']['MethodSummary'];
export type MetricDistribution = components['schemas']['MetricDistribution'];
export type MetricProjection = components['schemas']['MetricProjection'];
export type MonteCarloResult = components['schemas']['MonteCarloResult'];
export type ObservedOutcome = components['schemas']['ObservedOutcome'];
export type ParameterEvidence = components['schemas']['ParameterEvidence'];
export type ParseRequest = components['schemas']['ParseRequest'];
export type ParseResponse = components['schemas']['ParseResponse'];
export type PercentileBand = components['schemas']['PercentileBand'];
export type PolicyAssessment = components['schemas']['PolicyAssessment'];
export type PolicyChange = components['schemas']['PolicyChange'];
export type PolicySpec = components['schemas']['PolicySpec'];
export type PrecedentAnalysis = components['schemas']['PrecedentAnalysis'];
export type PrecedentMatch = components['schemas']['PrecedentMatch'];
export type ReportSection = components['schemas']['ReportSection'];
export type ResearchEval = components['schemas']['ResearchEval'];
export type ResearchFindings = components['schemas']['ResearchFindings'];
export type ResearchStep = components['schemas']['ResearchStep'];
export type ScenarioDefinition = components['schemas']['ScenarioDefinition'];
export type ScenarioResult = components['schemas']['ScenarioResult'];
export type ScopeDecision = components['schemas']['ScopeDecision'];
export type SensitivityResult = components['schemas']['SensitivityResult'];
export type SimulateRequest = components['schemas']['SimulateRequest'];
export type SimulationBundle = components['schemas']['SimulationBundle'];
export type Source = components['schemas']['Source'];
export type TornadoItem = components['schemas']['TornadoItem'];
export type VerificationCheck = components['schemas']['VerificationCheck'];
export type VerificationEval = components['schemas']['VerificationEval'];
export type VerificationReport = components['schemas']['VerificationReport'];
export type YearValue = components['schemas']['YearValue'];

// Literal and union types derived from contract schemas
export type Mode = Analysis['mode'];
export type TaxName = PolicyChange['tax'];
export type Confidence = MetricProjection['confidence'];
export type EvidenceClass = KeyFigure['evidence_class'];
export type PolicyType = PolicySpec['policy_type'];
export type PublisherType = Source['publisher_type'];
export type AccessMethod = Source['access_method'];
export type EvidenceKind = Evidence['kind'];
export type Topic = Evidence['topic'];
export type VerificationStatus = Evidence['verification_status'];
export type ResearchStepKind = ResearchStep['kind'];
export type DistributionKind = Distribution['kind'];
export type ParameterCategory = Assumption['category'];
export type ParameterBasis = Assumption['basis'];
export type MetricName = MetricProjection['metric'];
export type ScenarioName = ScenarioDefinition['name'];
export type CheckCategory = VerificationCheck['category'];
export type Severity = VerificationCheck['severity'];
export type CheckStatus = VerificationCheck['status'];
export type AnalysisStatus = Analysis['status'];

export type Stage =
  | 'parsing'
  | 'researching'
  | 'precedents'
  | 'modelling'
  | 'verifying'
  | 'reporting';

export type EventType =
  | 'stage_started'
  | 'stage_completed'
  | 'research_step'
  | 'log'
  | 'warning'
  | 'error'
  | 'completed'
  | 'failed';

export interface AnalysisEvent {
  analysis_id: string;
  seq: number;
  ts: string;
  type: EventType;
  stage?: Stage | null;
  message: string;
  data?: Record<string, unknown> | null;
}

export const ALL_STAGES: readonly Stage[] = [
  'parsing',
  'researching',
  'precedents',
  'modelling',
  'verifying',
  'reporting',
] as const;

export const TERMINAL_STATUSES: readonly AnalysisStatus[] = ['completed', 'failed'] as const;

export function isTerminalStatus(status?: AnalysisStatus | null): boolean {
  return status === 'completed' || status === 'failed';
}

export class ApiClientError extends Error {
  reasons: string[];

  constructor(message: string, reasons: string[] = []) {
    super(reasons.length > 0 ? `${message}: ${reasons.join('; ')}` : message);
    this.name = 'ApiClientError';
    this.reasons = reasons;
  }
}

function extractApiError(error: unknown, fallback: string): ApiClientError {
  if (error instanceof ApiClientError) {
    return error;
  }
  if (error instanceof Error) {
    return new ApiClientError(error.message);
  }
  if (error && typeof error === 'object') {
    const errObj = error as {
      message?: unknown;
      reasons?: unknown;
      detail?: unknown;
    };
    const reasons = Array.isArray(errObj.reasons)
      ? errObj.reasons.map((r) => String(r))
      : [];
    if (typeof errObj.message === 'string' && errObj.message) {
      return new ApiClientError(errObj.message, reasons);
    }
    if (typeof errObj.detail === 'string' && errObj.detail) {
      return new ApiClientError(errObj.detail, reasons);
    }
  }
  return new ApiClientError(fallback);
}

/**
 * GET /api/health
 */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/health');
      if (error || !data) {
        throw extractApiError(error, 'Failed to fetch health status');
      }
      return data;
    },
    staleTime: 30_000,
    retry: 1,
  });
}

/**
 * POST /api/policy/parse
 */
export function useParsePolicy() {
  return useMutation({
    mutationFn: async (input: string | ParseRequest) => {
      const body: ParseRequest = typeof input === 'string' ? { query: input } : input;
      const { data, error } = await apiClient.POST('/api/policy/parse', { body });
      if (error || !data) {
        throw extractApiError(error, 'Failed to parse policy query');
      }
      return data;
    },
  });
}

/**
 * POST /api/policy/scope
 */
export function useCheckScope() {
  return useMutation({
    mutationFn: async (policy: PolicySpec) => {
      const { data, error } = await apiClient.POST('/api/policy/scope', { body: policy });
      if (error || !data) {
        throw extractApiError(error, 'Failed to check policy scope');
      }
      return data;
    },
  });
}

/**
 * POST /api/analyses
 */
export function useCreateAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (request: AnalysisRequest) => {
      const { data, error } = await apiClient.POST('/api/analyses', { body: request });
      if (error || !data) {
        throw extractApiError(error, 'Failed to create analysis');
      }
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['analyses'] });
    },
  });
}

/**
 * GET /api/analyses/{analysis_id} — refetches every 1.5s while status is not terminal
 */
export function useAnalysis(id: string | undefined) {
  return useQuery({
    queryKey: ['analysis', id],
    enabled: Boolean(id),
    queryFn: async () => {
      if (!id) {
        throw new Error('Analysis ID is required');
      }
      const { data, error } = await apiClient.GET('/api/analyses/{analysis_id}', {
        params: { path: { analysis_id: id } },
      });
      if (error || !data) {
        throw extractApiError(error, `Failed to load analysis ${id}`);
      }
      return data;
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && isTerminalStatus(status)) {
        return false;
      }
      return 1500;
    },
  });
}

export interface UseAnalysisEventsResult {
  events: AnalysisEvent[];
  researchSteps: ResearchStep[];
  stage: Stage | null;
  stagesDone: Stage[];
  done: boolean;
  error: string | null;
}

const NAMED_SSE_EVENTS: readonly EventType[] = [
  'stage_started',
  'stage_completed',
  'research_step',
  'log',
  'warning',
  'error',
  'completed',
  'failed',
];

/**
 * SSE subscription hook for GET /api/analyses/{id}/events?after_seq=N.
 * Tracks last seq, reconnects with exponential backoff, stops on completed/failed,
 * and invalidates useAnalysis on each stage_completed event.
 */
export function useAnalysisEvents(id: string | undefined): UseAnalysisEventsResult {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [researchSteps, setResearchSteps] = useState<ResearchStep[]>([]);
  const [stage, setStage] = useState<Stage | null>(null);
  const [stagesDone, setStagesDone] = useState<Stage[]>([]);
  const [done, setDone] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const lastSeqRef = useRef<number>(0);
  const doneRef = useRef<boolean>(false);
  const retryCountRef = useRef<number>(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setEvents([]);
    setResearchSteps([]);
    setStage(null);
    setStagesDone([]);
    setDone(false);
    setError(null);
    lastSeqRef.current = 0;
    doneRef.current = false;
    retryCountRef.current = 0;

    if (!id || typeof EventSource === 'undefined') {
      return;
    }

    let unmounted = false;

    const cleanup = () => {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };

    const handleParsedEvent = (evt: AnalysisEvent) => {
      if (unmounted) return;
      if (typeof evt.seq === 'number') {
        if (evt.seq <= lastSeqRef.current) {
          return;
        }
        lastSeqRef.current = evt.seq;
      }

      retryCountRef.current = 0;
      setEvents((prev) => [...prev, evt]);

      if (evt.type === 'stage_started' && evt.stage) {
        setStage(evt.stage);
      } else if (evt.type === 'stage_completed') {
        if (evt.stage) {
          const completedStage = evt.stage;
          setStagesDone((prev) =>
            prev.includes(completedStage) ? prev : [...prev, completedStage],
          );
        }
        void queryClient.invalidateQueries({ queryKey: ['analysis', id] });
      } else if (evt.type === 'research_step' && evt.data) {
        const step = evt.data as unknown as ResearchStep;
        if (step && typeof step.title === 'string') {
          setResearchSteps((prev) => {
            if (prev.some((s) => s.step_id === step.step_id)) {
              return prev;
            }
            return [...prev, step];
          });
        }
      } else if (evt.type === 'error') {
        setError(evt.message || 'Error during analysis');
      } else if (evt.type === 'completed' || evt.type === 'failed') {
        doneRef.current = true;
        setDone(true);
        if (evt.type === 'failed') {
          setError(evt.message || 'Analysis failed');
        }
        void queryClient.invalidateQueries({ queryKey: ['analysis', id] });
        void queryClient.invalidateQueries({ queryKey: ['analyses'] });
        cleanup();
      }
    };

    const handleMessageEvent = (ev: Event) => {
      const msgEv = ev as MessageEvent;
      if (typeof msgEv.data !== 'string' || !msgEv.data) {
        return;
      }
      try {
        const parsed = JSON.parse(msgEv.data) as AnalysisEvent;
        handleParsedEvent(parsed);
      } catch {
        // Ignore malformed frame
      }
    };

    const connect = () => {
      if (unmounted || doneRef.current) return;
      cleanup();

      const url = `/api/analyses/${encodeURIComponent(id)}/events?after_seq=${lastSeqRef.current}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.onmessage = handleMessageEvent;

      for (const eventName of NAMED_SSE_EVENTS) {
        if (eventName === 'error') continue;
        es.addEventListener(eventName, handleMessageEvent);
      }

      es.onerror = (ev: Event) => {
        if (unmounted) return;
        const msgEv = ev as MessageEvent;
        if (typeof msgEv?.data === 'string' && msgEv.data.length > 0) {
          handleMessageEvent(ev);
          return;
        }
        if (doneRef.current) {
          cleanup();
          return;
        }
        es.close();
        esRef.current = null;
        const attempt = retryCountRef.current;
        retryCountRef.current += 1;
        if (attempt >= 6) {
          setError('Lost connection to analysis event stream');
          return;
        }
        const delayMs = Math.min(500 * Math.pow(2, attempt), 8000);
        retryTimerRef.current = setTimeout(() => {
          connect();
        }, delayMs);
      };
    };

    connect();

    return () => {
      unmounted = true;
      cleanup();
    };
  }, [id, queryClient]);

  return {
    events,
    researchSteps,
    stage,
    stagesDone,
    done,
    error,
  };
}

/**
 * POST /api/simulate (fast slider re-simulation)
 */
export function useSimulate() {
  return useMutation({
    mutationFn: async (request: SimulateRequest) => {
      const { data, error } = await apiClient.POST('/api/simulate', { body: request });
      if (error || !data) {
        throw extractApiError(error, 'Simulation request failed');
      }
      return data;
    },
  });
}

/**
 * GET /api/parameters
 */
export function useParameters() {
  return useQuery({
    queryKey: ['parameters'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/parameters');
      if (error || !data) {
        throw extractApiError(error, 'Failed to fetch model parameters');
      }
      return data;
    },
    staleTime: 60_000,
  });
}

/**
 * GET /api/precedents?tax=...
 */
export function usePrecedents(tax = 'corporation_tax') {
  return useQuery({
    queryKey: ['precedents', tax],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/precedents', {
        params: { query: { tax } },
      });
      if (error || !data) {
        throw extractApiError(error, 'Failed to fetch historical precedents');
      }
      return data;
    },
    staleTime: 60_000,
  });
}

/**
 * POST /api/precedents/match?k=5
 */
export function useMatchPrecedents() {
  return useMutation({
    mutationFn: async (
      input: PolicySpec | { policy: PolicySpec; k?: number },
    ) => {
      const isWrapped = 'policy' in input && typeof input.policy === 'object';
      const policy = isWrapped ? (input as { policy: PolicySpec; k?: number }).policy : (input as PolicySpec);
      const k = isWrapped ? ((input as { policy: PolicySpec; k?: number }).k ?? 5) : 5;

      const { data, error } = await apiClient.POST('/api/precedents/match', {
        params: { query: { k } },
        body: policy,
      });
      if (error || !data) {
        throw extractApiError(error, 'Failed to match precedents');
      }
      return data;
    },
  });
}

/**
 * GET /api/evaluation
 */
export function useEvaluation() {
  return useQuery({
    queryKey: ['evaluation'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/evaluation');
      if (error || !data) {
        throw extractApiError(error, 'Failed to load evaluation report');
      }
      return data;
    },
    staleTime: 30_000,
  });
}

/**
 * GET /api/analyses?limit=50
 */
export function useAnalysesList(limit = 50) {
  return useQuery({
    queryKey: ['analyses', limit],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/analyses', {
        params: { query: { limit } },
      });
      if (error || !data) {
        throw extractApiError(error, 'Failed to fetch analyses list');
      }
      return data;
    },
  });
}

/**
 * GET /api/sources
 */
export function useSources() {
  return useQuery({
    queryKey: ['sources'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/sources');
      if (error || !data) {
        throw extractApiError(error, 'Failed to fetch curated sources');
      }
      return data;
    },
    staleTime: 60_000,
  });
}

/**
 * GET /api/datasets
 */
export function useDatasets() {
  return useQuery({
    queryKey: ['datasets'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/datasets');
      if (error || !data) {
        throw extractApiError(error, 'Failed to fetch datasets metadata');
      }
      return data;
    },
    staleTime: 60_000,
  });
}
