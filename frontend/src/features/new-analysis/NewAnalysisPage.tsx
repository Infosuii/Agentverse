import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import clsx from 'clsx';
import {
  ApiClientError,
  useCheckScope,
  useCreateAnalysis,
  useParsePolicy,
  type PolicySpec,
  type PolicyType,
  type ScopeDecision,
} from '../../api/hooks';
import {
  Badge,
  Card,
  EvidenceBadge,
  InlineError,
  Skeleton,
  Spinner,
} from '../../components/ui';
import { fmtPp } from '../../lib/format';

export const EXAMPLE_QUERIES = [
  {
    label: '25% → 28% hike (Golden path)',
    query: 'What would happen if the UK increased corporation tax from 25% to 28%?',
  },
  {
    label: '25% → 23% cut (April 2027)',
    query: 'Cut corporation tax from 25% to 23% from April 2027',
  },
  {
    label: 'Raise CT to 45% (Scope gate)',
    query: 'Raise corporation tax to 45%',
  },
] as const;

const POLICY_TYPE_OPTIONS: { value: PolicyType; label: string }[] = [
  { value: 'corporation_tax_main_rate', label: 'UK Corporation Tax — Main Rate' },
  {
    value: 'corporation_tax_small_profits_rate',
    label: 'UK Corporation Tax — Small Profits Rate',
  },
  { value: 'vat_standard_rate', label: 'UK VAT — Standard Rate' },
  { value: 'unsupported', label: 'Unsupported / Other Policy' },
];

const MC_DRAW_OPTIONS = [500, 2000, 5000] as const;

function ScopeStatusBadge({ scope }: { scope: ScopeDecision }) {
  if (scope.status === 'supported') {
    return (
      <Badge variant="green" dotColor="#16a34a" aria-label="Scope status: Supported">
        ✓ Supported scope
      </Badge>
    );
  }
  if (scope.status === 'partially_supported') {
    return (
      <Badge
        variant="amber"
        dotColor="#d97706"
        aria-label="Scope status: Partially supported"
      >
        ! Partially supported
      </Badge>
    );
  }
  return (
    <Badge variant="red" dotColor="#dc2626" aria-label="Scope status: Unsupported">
      ✕ Unsupported (forecast will be withheld)
    </Badge>
  );
}

export function NewAnalysisPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [policySpec, setPolicySpec] = useState<PolicySpec | null>(null);
  const [scopeDecision, setScopeDecision] = useState<ScopeDecision | null>(null);

  const [monteCarloDraws, setMonteCarloDraws] = useState<number>(2000);
  const [runResearch, setRunResearch] = useState<boolean>(true);
  const [useResearchCache, setUseResearchCache] = useState<boolean>(true);

  const parseMutation = useParsePolicy();
  const scopeMutation = useCheckScope();
  const createMutation = useCreateAnalysis();

  const lastParsedQueryRef = useRef<string>('');
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerParse = (rawQuery: string) => {
    const trimmed = rawQuery.trim();
    if (trimmed.length < 3 || trimmed === lastParsedQueryRef.current) {
      return;
    }
    lastParsedQueryRef.current = trimmed;
    parseMutation.mutate(
      { query: trimmed },
      {
        onSuccess: (res) => {
          setPolicySpec(res.policy);
          setScopeDecision(res.scope);
        },
      },
    );
  };

  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    const trimmed = query.trim();
    if (trimmed.length < 3) {
      return;
    }
    debounceTimerRef.current = setTimeout(() => {
      triggerParse(trimmed);
    }, 600);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const handleChipClick = (exampleQuery: string) => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    setQuery(exampleQuery);
    lastParsedQueryRef.current = '';
    triggerParse(exampleQuery);
  };

  const updatePolicyField = <K extends keyof PolicySpec>(
    field: K,
    value: PolicySpec[K],
  ) => {
    if (!policySpec) return;
    const nextSpec: PolicySpec = {
      ...policySpec,
      [field]: value,
      parse_method: 'manual',
    };
    setPolicySpec(nextSpec);
    scopeMutation.mutate(nextSpec, {
      onSuccess: (res) => {
        setScopeDecision(res.scope);
      },
    });
  };

  const handleRunAnalysis = () => {
    const trimmed = query.trim();
    if (trimmed.length < 3) return;
    createMutation.mutate(
      {
        query: trimmed,
        policy_override: policySpec ?? null,
        parameter_overrides: {},
        options: {
          run_research: runResearch,
          use_research_cache: useResearchCache,
          monte_carlo_draws: monteCarloDraws,
          seed: 42,
          generate_report: true,
        },
      },
      {
        onSuccess: (created) => {
          void navigate(`/analyses/${created.analysis_id}/research`);
        },
      },
    );
  };

  const changePp =
    policySpec?.baseline_rate_pct != null && policySpec?.proposed_rate_pct != null
      ? Number((policySpec.proposed_rate_pct - policySpec.baseline_rate_pct).toFixed(2))
      : null;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          UK Fiscal Policy Simulator
        </h1>
        <p className="text-sm text-slate-600">
          Enter a proposed UK tax policy in plain English. Jane Avenue parses the policy,
          checks validated historical scope, conducts live grounded research, runs a
          transparent econometric model, and independently verifies every claim.
        </p>
      </div>

      <Card
        title="1. Policy Proposal Query"
        subtitle="Describe a proposed UK corporation tax change or choose an example below"
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="policy-query-input" className="sr-only">
              Proposed tax policy query
            </label>
            <textarea
              id="policy-query-input"
              rows={3}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onBlur={() => triggerParse(query)}
              placeholder="e.g., What would happen if the UK increased corporation tax from 25% to 28%?"
              className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-2xs placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <span className="block text-xs font-medium text-slate-600">
              Example queries:
            </span>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Example policy queries">
              {EXAMPLE_QUERIES.map((ex) => {
                const isSelected = query.trim() === ex.query;
                return (
                  <button
                    key={ex.query}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => handleChipClick(ex.query)}
                    className={clsx(
                      'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none',
                      isSelected
                        ? 'border-blue-600 bg-blue-50 text-blue-900'
                        : 'border-slate-300 bg-slate-50 text-slate-700 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-800',
                    )}
                  >
                    <span>{ex.query}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </Card>

      {parseMutation.isPending && !policySpec && (
        <Card title="2. Parsed Policy Specification">
          <Skeleton lines={4} />
        </Card>
      )}

      {parseMutation.isError && (
        <InlineError
          title="Could not parse policy query"
          message={
            parseMutation.error instanceof Error
              ? parseMutation.error.message
              : 'Failed to parse policy'
          }
          reasons={
            parseMutation.error instanceof ApiClientError
              ? parseMutation.error.reasons
              : []
          }
          onRetry={() => {
            lastParsedQueryRef.current = '';
            triggerParse(query);
          }}
        />
      )}

      {policySpec && (
        <Card
          title="2. Parsed Policy Specification & Scope Gate"
          subtitle="Review or adjust parsed fields before running the full analysis"
          actions={
            <div className="flex items-center gap-2">
              {(parseMutation.isPending || scopeMutation.isPending) && (
                <Spinner size="xs" />
              )}
              {scopeDecision && <ScopeStatusBadge scope={scopeDecision} />}
            </div>
          }
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <div className="sm:col-span-2">
                <label
                  htmlFor="spec-policy-type"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Policy Type
                </label>
                <select
                  id="spec-policy-type"
                  value={policySpec.policy_type}
                  onChange={(e) =>
                    updatePolicyField('policy_type', e.target.value as PolicyType)
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
                >
                  {POLICY_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="spec-baseline-rate"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Baseline Rate (%)
                </label>
                <input
                  id="spec-baseline-rate"
                  type="number"
                  step="0.5"
                  min={0}
                  max={100}
                  value={policySpec.baseline_rate_pct ?? ''}
                  onChange={(e) =>
                    updatePolicyField(
                      'baseline_rate_pct',
                      e.target.value === '' ? null : Number(e.target.value),
                    )
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 tabular-nums focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
                />
              </div>

              <div>
                <label
                  htmlFor="spec-proposed-rate"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Proposed Rate (%)
                </label>
                <input
                  id="spec-proposed-rate"
                  type="number"
                  step="0.5"
                  min={0}
                  max={100}
                  value={policySpec.proposed_rate_pct ?? ''}
                  onChange={(e) =>
                    updatePolicyField(
                      'proposed_rate_pct',
                      e.target.value === '' ? null : Number(e.target.value),
                    )
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 tabular-nums focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
                />
              </div>

              <div>
                <label
                  htmlFor="spec-change-pp"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Rate Change
                </label>
                <div
                  id="spec-change-pp"
                  aria-live="polite"
                  className="mt-1 flex h-[30px] items-center rounded-md border border-slate-200 bg-slate-50 px-2.5 text-xs font-semibold text-slate-800 tabular-nums"
                >
                  {fmtPp(changePp)}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="spec-effective-date"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Effective Date
                </label>
                <input
                  id="spec-effective-date"
                  type="date"
                  value={policySpec.effective_date ?? ''}
                  onChange={(e) =>
                    updatePolicyField(
                      'effective_date',
                      e.target.value === '' ? null : e.target.value,
                    )
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
                />
              </div>

              <div>
                <label
                  htmlFor="spec-horizon-years"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Horizon (Years, 1–10)
                </label>
                <input
                  id="spec-horizon-years"
                  type="number"
                  min={1}
                  max={10}
                  value={policySpec.horizon_years}
                  onChange={(e) =>
                    updatePolicyField(
                      'horizon_years',
                      Math.max(1, Math.min(10, Number(e.target.value) || 5)),
                    )
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 tabular-nums focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
                />
              </div>
            </div>

            {policySpec.ambiguities && policySpec.ambiguities.length > 0 && (
              <div
                role="note"
                aria-label="Parser assumptions and ambiguities"
                className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">
                    Parser assumptions & ambiguities:
                  </span>
                  <EvidenceBadge evidenceClass="assumption" short />
                </div>
                <ul className="mt-1.5 list-disc space-y-0.5 pl-5">
                  {policySpec.ambiguities.map((amb, idx) => (
                    <li key={idx}>{amb}</li>
                  ))}
                </ul>
              </div>
            )}

            {scopeDecision && (
              <div
                role="region"
                aria-label="Scope gate assessment"
                className={
                  scopeDecision.status === 'unsupported'
                    ? 'rounded-md border border-red-300 bg-red-50 p-3 text-xs text-red-900'
                    : scopeDecision.status === 'partially_supported'
                      ? 'rounded-md border border-amber-300 bg-amber-50/70 p-3 text-xs text-amber-900'
                      : 'rounded-md border border-emerald-200 bg-emerald-50/60 p-3 text-xs text-emerald-900'
                }
              >
                <div className="flex flex-wrap items-center justify-between gap-2 font-semibold">
                  <span>
                    Scope gate:{' '}
                    {scopeDecision.forecast_allowed
                      ? 'Quantitative forecast allowed'
                      : 'Quantitative forecast withheld'}
                  </span>
                  {scopeDecision.validated_min_rate_pct != null &&
                    scopeDecision.validated_max_rate_pct != null && (
                      <span className="font-normal text-slate-600">
                        Historical UK CT range: {scopeDecision.validated_min_rate_pct}%–
                        {scopeDecision.validated_max_rate_pct}%
                        {scopeDecision.validated_max_change_pp != null
                          ? ` (max Δ ${scopeDecision.validated_max_change_pp}pp)`
                          : ''}
                      </span>
                    )}
                </div>
                {scopeDecision.reasons && scopeDecision.reasons.length > 0 && (
                  <ul className="mt-1 list-disc space-y-0.5 pl-5">
                    {scopeDecision.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}
                {scopeDecision.warnings && scopeDecision.warnings.length > 0 && (
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-amber-900">
                    {scopeDecision.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      <Card title="3. Simulation & Research Options">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <label
                  htmlFor="opt-mc-draws"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Monte Carlo Draws
                </label>
                <select
                  id="opt-mc-draws"
                  value={monteCarloDraws}
                  onChange={(e) => setMonteCarloDraws(Number(e.target.value))}
                  className="mt-1 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
                >
                  {MC_DRAW_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      {n.toLocaleString('en-GB')} draws
                    </option>
                  ))}
                </select>
              </div>

              <label className="mt-4 inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={runResearch}
                  onChange={(e) => setRunResearch(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Run research agent</span>
              </label>

              <label className="mt-4 inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={useResearchCache}
                  disabled={!runResearch}
                  onChange={(e) => setUseResearchCache(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                />
                <span>Use cached research if available</span>
              </label>
            </div>

            <button
              type="button"
              disabled={query.trim().length < 3 || createMutation.isPending}
              onClick={handleRunAnalysis}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-blue-700 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {createMutation.isPending && <Spinner size="xs" className="border-white" />}
              <span>Run analysis</span>
            </button>
          </div>

          {createMutation.isError && (
            <InlineError
              title="Failed to start analysis"
              message={
                createMutation.error instanceof Error
                  ? createMutation.error.message
                  : 'Unexpected error creating analysis'
              }
              reasons={
                createMutation.error instanceof ApiClientError
                  ? createMutation.error.reasons
                  : []
              }
              onRetry={handleRunAnalysis}
            />
          )}
        </div>
      </Card>
    </div>
  );
}

export default NewAnalysisPage;
