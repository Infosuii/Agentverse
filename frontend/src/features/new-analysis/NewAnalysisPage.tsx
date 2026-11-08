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
  Eyebrow,
  InlineError,
  LoaderIcon,
  Skeleton,
  Spinner,
  Wordmark,
  buttonClasses,
} from '../../components/ui';
import { SearchBar } from '../../components/search/SearchBar';
import { ExamplePrompts } from '../../components/search/ExamplePrompts';
import { fmtPp } from '../../lib/format';
import { isResearchOnly, policyChangeText, policyTypeLabel } from '../../lib/policy';
import backdrop from '../../assets/landing-data-backdrop.jpg';

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
  {
    label: 'VAT 20% → 21%',
    query: 'Raise VAT from 20% to 21% from April 2027',
  },
  {
    label: 'Personal allowance +£1,000',
    query: 'Raise the personal allowance to £13,570',
  },
  {
    label: 'NHS spending (research only)',
    query: 'Increase NHS spending by £10bn a year',
  },
] as const;

/** Short, single-line prompts cycled by the search bar's typing indicator. */
export const SEARCH_BAR_SUGGESTIONS = [
  'What if the UK raised corporation tax from 25% to 28%?',
  'Cut corporation tax from 25% to 23% from April 2027',
  'Raise the corporation tax main rate to 27% from April 2028',
  'What would a 26% main rate raise over five years?',
  'Raise VAT from 20% to 21% from April 2027',
  'Cut fuel duty by 5p a litre',
  'Increase child benefit by £1 a week',
  'Raise the minimum wage to £15 an hour',
] as const;

const POLICY_TYPE_OPTIONS: { value: PolicyType; label: string }[] = [
  { value: 'corporation_tax_main_rate', label: 'UK Corporation Tax — Main Rate' },
  {
    value: 'corporation_tax_small_profits_rate',
    label: 'UK Corporation Tax — Small Profits Rate',
  },
  { value: 'tax_measure', label: 'UK tax or benefit measure (HMRC ready reckoner)' },
  { value: 'fiscal_other', label: 'Other fiscal policy (research only)' },
  { value: 'unsupported', label: 'Unsupported / Not a fiscal policy' },
];

const MC_DRAW_OPTIONS = [500, 2000, 5000] as const;
const MIN_QUERY_LENGTH = 3;

const FIELD_CLASS =
  'mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground tabular-nums focus:border-primary focus:ring-1 focus:ring-ring focus:outline-none';
const LABEL_CLASS = 'block text-xs font-medium text-muted-foreground';

function ScopeStatusBadge({ scope }: { scope: ScopeDecision }) {
  if (scope.status === 'supported') {
    return (
      <Badge variant="green" dotColor="var(--st-pass)" aria-label="Scope status: Supported">
        ✓ Supported scope
      </Badge>
    );
  }
  if (scope.status === 'partially_supported') {
    return (
      <Badge
        variant="amber"
        dotColor="var(--ev-assumption)"
        aria-label="Scope status: Partially supported"
      >
        ! Partially supported
      </Badge>
    );
  }
  return (
    <Badge variant="red" dotColor="var(--st-fail)" aria-label="Scope status: Unsupported">
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

  /** Query text of the most recent parse request (dedupes and drops stale responses). */
  const lastParsedQueryRef = useRef<string>('');
  /** Query text that produced the current `policySpec`. */
  const specQueryRef = useRef<string>('');
  /** Monotonic id so only the latest scope re-check updates the badge. */
  const scopeRequestRef = useRef<number>(0);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerParse = (rawQuery: string) => {
    const trimmed = rawQuery.trim();
    if (trimmed.length < MIN_QUERY_LENGTH || trimmed === lastParsedQueryRef.current) {
      return;
    }
    lastParsedQueryRef.current = trimmed;
    parseMutation.mutate(
      { query: trimmed },
      {
        onSuccess: (res) => {
          // Ignore responses for a query the analyst has already replaced.
          if (lastParsedQueryRef.current !== trimmed) return;
          specQueryRef.current = trimmed;
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
    if (trimmed.length < MIN_QUERY_LENGTH) {
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
    const requestId = scopeRequestRef.current + 1;
    scopeRequestRef.current = requestId;
    scopeMutation.mutate(nextSpec, {
      onSuccess: (res) => {
        if (scopeRequestRef.current !== requestId) return;
        setScopeDecision(res.scope);
      },
    });
  };

  const trimmedQuery = query.trim();
  const canRun = trimmedQuery.length >= MIN_QUERY_LENGTH && !createMutation.isPending;

  const handleRunAnalysis = () => {
    if (trimmedQuery.length < MIN_QUERY_LENGTH || createMutation.isPending) return;
    // Only send the reviewed spec when it belongs to the query being submitted; otherwise
    // the backend parses the new text itself (never run a stale specification).
    const policyOverride =
      policySpec && specQueryRef.current === trimmedQuery ? policySpec : null;
    createMutation.mutate(
      {
        query: trimmedQuery,
        policy_override: policyOverride,
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

  const isValueMeasure =
    policySpec?.policy_type === 'tax_measure' &&
    (policySpec.baseline_value != null || policySpec.proposed_value != null);

  const showReview =
    trimmedQuery.length >= MIN_QUERY_LENGTH ||
    Boolean(policySpec) ||
    parseMutation.isPending ||
    parseMutation.isError;

  return (
    <div className="relative">
      {/* Restrained photographic data texture behind the prompt; no decorative lighting. */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <img
          src={backdrop}
          alt=""
          width={1920}
          height={1088}
          className="h-full w-full object-cover opacity-20 grayscale"
        />
        <div className="absolute inset-0 bg-background/70" />
      </div>

      <section
        aria-labelledby="landing-title"
        className="mx-auto w-full max-w-2xl px-4 pt-[12vh] pb-10 sm:px-6"
      >
        <h1
          id="landing-title"
          className="text-center text-3xl sm:text-4xl"
        >
          <Wordmark />
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-center text-base text-muted-foreground">
          An AI-powered UK fiscal policy simulator. Propose a tax, benefit or spending change
          to explore its researched evidence, modelled impact and independent verification.
        </p>

        <div className="mt-8">
          <SearchBar
            id="policy-query-input"
            label="Proposed tax policy query"
            value={query}
            onChange={setQuery}
            onBlur={() => triggerParse(query)}
            onSubmit={handleRunAnalysis}
            suggestions={SEARCH_BAR_SUGGESTIONS}
            placeholder="e.g., What would happen if the UK increased corporation tax from 25% to 28%?"
            busy={createMutation.isPending}
            minLength={MIN_QUERY_LENGTH}
          />
          <p className="mt-2 flex min-h-5 items-center gap-1.5 text-xs text-muted-foreground">
            {parseMutation.isPending ? (
              <>
                <LoaderIcon className="h-3.5 w-3.5 text-primary" />
                <span>Reading the proposal and checking the scope gate…</span>
              </>
            ) : (
              <span>
                Enter runs the analysis · Shift + Enter adds a line · the parsed policy appears
                below for review
              </span>
            )}
          </p>
        </div>

        <Eyebrow className="mt-10 mb-1">New Policy Analysis</Eyebrow>
        <ExamplePrompts
          examples={EXAMPLE_QUERIES}
          onPick={handleChipClick}
          selectedQuery={query}
        />
        <p className="mt-8 text-center font-mono text-[11px] text-muted-foreground">
          Grounded research · historical precedents · transparent econometric engine · independent verification
        </p>
      </section>

      {showReview && (
        <section
          aria-label="Review and run"
          className="mx-auto w-full max-w-4xl space-y-5 px-4 pb-24 sm:px-6"
        >
          {parseMutation.isPending && !policySpec && (
            <Card title="Parsed Policy Specification">
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
              title="Parsed Policy Specification & Scope Gate"
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
                    <label htmlFor="spec-policy-type" className={LABEL_CLASS}>
                      Policy Type
                    </label>
                    <select
                      id="spec-policy-type"
                      value={policySpec.policy_type}
                      onChange={(e) =>
                        updatePolicyField('policy_type', e.target.value as PolicyType)
                      }
                      className={FIELD_CLASS}
                    >
                      {POLICY_TYPE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    {policySpec.policy_type === 'tax_measure' && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Measure: <span className="font-medium text-foreground">{policyTypeLabel(policySpec)}</span>
                      </p>
                    )}
                  </div>

                  {isResearchOnly(policySpec) ? (
                    <div className="sm:col-span-2 lg:col-span-3">
                      <span className={LABEL_CLASS}>Model</span>
                      <p className="mt-1 rounded-md border border-border bg-muted/40 px-2.5 py-1.5 text-sm text-foreground">
                        No validated model for this policy yet: it is researched and reported, and the forecast is
                        withheld.
                      </p>
                    </div>
                  ) : isValueMeasure ? (
                    <>
                      <div>
                        <label htmlFor="spec-baseline-value" className={LABEL_CLASS}>
                          Current Value ({policySpec.value_unit ?? 'value'})
                        </label>
                        <input
                          id="spec-baseline-value"
                          type="number"
                          step="any"
                          value={policySpec.baseline_value ?? ''}
                          onChange={(e) =>
                            updatePolicyField(
                              'baseline_value',
                              e.target.value === '' ? null : Number(e.target.value),
                            )
                          }
                          className={clsx(FIELD_CLASS, 'font-mono')}
                        />
                      </div>
                      <div>
                        <label htmlFor="spec-proposed-value" className={LABEL_CLASS}>
                          Proposed Value ({policySpec.value_unit ?? 'value'})
                        </label>
                        <input
                          id="spec-proposed-value"
                          type="number"
                          step="any"
                          value={policySpec.proposed_value ?? ''}
                          onChange={(e) =>
                            updatePolicyField(
                              'proposed_value',
                              e.target.value === '' ? null : Number(e.target.value),
                            )
                          }
                          className={clsx(FIELD_CLASS, 'font-mono')}
                        />
                      </div>
                      <div>
                        <span className={LABEL_CLASS}>Change</span>
                        <div
                          aria-live="polite"
                          className="mt-1 flex min-h-[34px] items-center rounded-md border border-border bg-muted/40 px-2.5 font-mono text-xs font-medium text-primary tabular-nums"
                        >
                          {policyChangeText(policySpec)}
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                    <div>
                      <label htmlFor="spec-baseline-rate" className={LABEL_CLASS}>
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
                        className={clsx(FIELD_CLASS, 'font-mono')}
                      />
                    </div>

                    <div>
                      <label htmlFor="spec-proposed-rate" className={LABEL_CLASS}>
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
                        className={clsx(FIELD_CLASS, 'font-mono')}
                      />
                    </div>

                    <div>
                      <label htmlFor="spec-change-pp" className={LABEL_CLASS}>
                        Rate Change
                      </label>
                      <div
                        id="spec-change-pp"
                        aria-live="polite"
                        className="mt-1 flex h-[34px] items-center rounded-md border border-border bg-muted/40 px-2.5 font-mono text-sm font-medium text-primary tabular-nums"
                      >
                        {fmtPp(changePp)}
                      </div>
                    </div>
                    </>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="spec-effective-date" className={LABEL_CLASS}>
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
                      className={FIELD_CLASS}
                    />
                  </div>

                  <div>
                    <label htmlFor="spec-horizon-years" className={LABEL_CLASS}>
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
                      className={clsx(FIELD_CLASS, 'font-mono')}
                    />
                  </div>
                </div>

                {policySpec.ambiguities && policySpec.ambiguities.length > 0 && (
                  <div
                    role="note"
                    aria-label="Parser assumptions and ambiguities"
                    className="rounded-md border border-amber-400/35 bg-amber-500/10 p-3 text-xs text-amber-200"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">Parser assumptions & ambiguities:</span>
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
                    className={clsx(
                      'rounded-md border p-3 text-xs',
                      scopeDecision.status === 'unsupported'
                        ? 'border-red-400/40 bg-red-500/10 text-red-200'
                        : scopeDecision.status === 'partially_supported'
                          ? 'border-amber-400/35 bg-amber-500/10 text-amber-200'
                          : 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200',
                    )}
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
                          <span className="font-mono font-normal text-muted-foreground">
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
                      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-amber-200">
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

          <Card title="Simulation & Research Options">
            <div className="space-y-4">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div className="flex flex-wrap items-end gap-6">
                  <div>
                    <label htmlFor="opt-mc-draws" className={LABEL_CLASS}>
                      Monte Carlo Draws
                    </label>
                    <select
                      id="opt-mc-draws"
                      value={monteCarloDraws}
                      onChange={(e) => setMonteCarloDraws(Number(e.target.value))}
                      className={clsx(FIELD_CLASS, 'w-auto')}
                    >
                      {MC_DRAW_OPTIONS.map((n) => (
                        <option key={n} value={n}>
                          {n.toLocaleString('en-GB')} draws
                        </option>
                      ))}
                    </select>
                  </div>

                  <label className="inline-flex cursor-pointer items-center gap-2 pb-2 text-xs font-medium text-foreground">
                    <input
                      type="checkbox"
                      checked={runResearch}
                      onChange={(e) => setRunResearch(e.target.checked)}
                      className="h-4 w-4 rounded-sm accent-primary"
                    />
                    <span>Run research agent</span>
                  </label>

                  <label
                    className={clsx(
                      'inline-flex cursor-pointer items-center gap-2 pb-2 text-xs font-medium',
                      runResearch ? 'text-foreground' : 'text-muted-foreground',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={useResearchCache}
                      disabled={!runResearch}
                      onChange={(e) => setUseResearchCache(e.target.checked)}
                      className="h-4 w-4 rounded-sm accent-primary disabled:opacity-50"
                    />
                    <span>Use cached research if available</span>
                  </label>
                </div>

                <button
                  type="button"
                  disabled={!canRun}
                  onClick={handleRunAnalysis}
                  className={buttonClasses('primary', 'lg')}
                >
                  {createMutation.isPending && <LoaderIcon className="h-4 w-4" />}
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
        </section>
      )}
    </div>
  );
}

export default NewAnalysisPage;
