import { useEffect, useMemo, useRef, useState } from 'react';
import React from 'react';
import { useOutletContext, useParams, useSearchParams } from 'react-router';
import clsx from 'clsx';
import {
  useAnalysis,
  type Analysis,
  type Evidence,
  type EvidenceKind,
  type PublisherType,
  type ResearchStep,
  type ResearchStepKind,
  type Source,
  type Topic,
  type VerificationStatus,
} from '../../api/hooks';
import type { AnalysisOutletContext } from '../analysis/AnalysisShell';
import {
  Badge,
  Card,
  EmptyState,
  EvidenceBadge,
  PlaceholderBadge,
  Skeleton,
  SourceChip,
  Spinner,
  Table,
} from '../../components/ui';

export interface ResearchTabProps {
  analysis?: Analysis;
  liveSteps?: ResearchStep[];
}

const STEP_ICONS: Record<ResearchStepKind, { label: string; color: string }> = {
  plan: { label: 'Plan', color: 'bg-primary/10 text-primary border-primary/25' },
  search: { label: 'Search', color: 'bg-indigo-500/10 text-indigo-300 border-indigo-400/25' },
  fetch: { label: 'Fetch URL', color: 'bg-cyan-500/10 text-cyan-300 border-cyan-400/25' },
  extract: {
    label: 'Extract Quote',
    color: 'bg-emerald-500/10 text-emerald-300 border-emerald-400/25',
  },
  dataset_lookup: {
    label: 'Dataset',
    color: 'bg-violet-500/10 text-violet-300 border-violet-400/25',
  },
  reason: { label: 'Reason', color: 'bg-secondary text-foreground border-input' },
  synthesis: { label: 'Synthesise', color: 'bg-primary/10 text-primary border-primary/35' },
  warning: { label: 'Warning', color: 'bg-amber-500/10 text-amber-200 border-amber-400/35' },
  error: { label: 'Error', color: 'bg-red-500/10 text-red-200 border-red-400/35' },
};

function scrollToEvidence(evidenceId: string) {
  const el = document.getElementById(`evidence-${evidenceId}`);
  if (el) {
    el.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    el.focus({ preventScroll: true });
  }
}

function renderTextWithEvidenceRefs(text: string): React.ReactNode {
  const parts = text.split(/(\[(?:E\d+|S\d+|D-[a-zA-Z0-9_-]+)\])/g);
  return parts.map((part, idx) => {
    const evMatch = /^\[(E\d+)\]$/.exec(part);
    if (evMatch) {
      const evId = evMatch[1];
      return (
        <button
          key={`${evId}-${idx}`}
          type="button"
          onClick={() => scrollToEvidence(evId)}
          aria-label={`Jump to evidence ${evId}`}
          className="mx-0.5 inline-flex items-center rounded border border-primary/35 bg-primary/10 px-1.5 py-0 font-mono text-xs font-semibold text-primary hover:bg-primary/20 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          [{evId}]
        </button>
      );
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

function EvidenceVerificationBadge({ status }: { status: VerificationStatus }) {
  if (status === 'verified') {
    return (
      <Badge variant="green" dotColor="#16a34a" aria-label="Quote verification: Verified">
        ✓ Quote verified
      </Badge>
    );
  }
  if (status === 'failed') {
    return (
      <Badge variant="red" dotColor="#dc2626" aria-label="Quote verification: Failed">
        ✕ Quote verification failed
      </Badge>
    );
  }
  return (
    <Badge variant="amber" dotColor="#d97706" aria-label="Quote verification: Unverified">
      • Unverified quote
    </Badge>
  );
}

function formatCitation(ev: Evidence, source?: Source): string {
  const srcPart = source
    ? `${source.publisher} — "${source.title}" (${source.url})`
    : `Source [${ev.source_id}]`;
  const quotePart = ev.quote ? ` "${ev.quote}"` : '';
  return `[${ev.evidence_id}] ${ev.claim}.${quotePart} — ${srcPart}`;
}

export function ResearchTab({ analysis: propAnalysis, liveSteps }: ResearchTabProps) {
  const { id } = useParams<{ id: string }>();
  const outletCtx = useOutletContext<AnalysisOutletContext | undefined>();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(
    propAnalysis || outletCtx?.analysis ? undefined : id,
  );

  const analysis = propAnalysis ?? outletCtx?.analysis ?? fetchedAnalysis;

  const [topicFilter, setTopicFilter] = useState<Topic | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<VerificationStatus | 'all'>('all');
  const [kindFilter, setKindFilter] = useState<EvidenceKind | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [highlightedEvidence, setHighlightedEvidence] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const evidenceParam = searchParams.get('evidence');
  const handledEvidenceRef = useRef<string | null>(null);
  const drawerCloseRef = useRef<HTMLButtonElement | null>(null);
  const drawerReturnFocusRef = useRef<HTMLElement | null>(null);

  const selectedSourceId = selectedSource?.source_id ?? null;
  useEffect(() => {
    if (!selectedSourceId) return;
    // Move focus into the drawer and give it back to the opener when it closes.
    drawerReturnFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    drawerCloseRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedSource(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      drawerReturnFocusRef.current?.focus?.();
    };
  }, [selectedSourceId]);

  const allSources = useMemo<Source[]>(() => {
    const map = new Map<string, Source>();
    for (const s of analysis?.sources ?? []) {
      map.set(s.source_id, s);
    }
    for (const s of analysis?.research?.sources ?? []) {
      map.set(s.source_id, s);
    }
    return Array.from(map.values());
  }, [analysis?.sources, analysis?.research?.sources]);

  const timelineSteps = useMemo<ResearchStep[]>(() => {
    const sseSteps = liveSteps ?? outletCtx?.eventsState?.researchSteps ?? [];
    const byId = new Map<number, ResearchStep>();
    for (const step of analysis?.research?.trace ?? []) {
      byId.set(step.step_id, step);
    }
    for (const step of sseSteps) {
      byId.set(step.step_id, step);
    }
    return Array.from(byId.values()).sort((a, b) => a.step_id - b.step_id);
  }, [analysis?.research?.trace, liveSteps, outletCtx?.eventsState?.researchSteps]);

  const research = analysis?.research;
  const evidenceList = useMemo<Evidence[]>(
    () => research?.evidence ?? [],
    [research?.evidence],
  );

  // Deep link: /analyses/:id/research?evidence=E3 clears filters, scrolls to and highlights E3.
  useEffect(() => {
    if (!evidenceParam || handledEvidenceRef.current === evidenceParam) return;
    if (!evidenceList.some((ev) => ev.evidence_id === evidenceParam)) return;
    handledEvidenceRef.current = evidenceParam;
    setTopicFilter('all');
    setStatusFilter('all');
    setKindFilter('all');
    setSearchQuery('');
    setHighlightedEvidence(evidenceParam);
  }, [evidenceParam, evidenceList]);

  useEffect(() => {
    if (!highlightedEvidence) return;
    const scrollTimer = setTimeout(() => scrollToEvidence(highlightedEvidence), 0);
    const clearTimer = setTimeout(() => setHighlightedEvidence(null), 2600);
    return () => {
      clearTimeout(scrollTimer);
      clearTimeout(clearTimer);
    };
  }, [highlightedEvidence]);

  const filteredEvidence = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return evidenceList.filter((ev) => {
      if (topicFilter !== 'all' && ev.topic !== topicFilter) return false;
      if (statusFilter !== 'all' && ev.verification_status !== statusFilter) return false;
      if (kindFilter !== 'all' && ev.kind !== kindFilter) return false;
      if (q) {
        const hay =
          `${ev.evidence_id} ${ev.claim} ${ev.quote ?? ''} ${ev.topic} ${ev.source_id}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [evidenceList, topicFilter, statusFilter, kindFilter, searchQuery]);

  const statusCounts = useMemo(() => {
    const counts = { verified: 0, unverified: 0, failed: 0 };
    for (const ev of evidenceList) {
      counts[ev.verification_status] = (counts[ev.verification_status] ?? 0) + 1;
    }
    return counts;
  }, [evidenceList]);

  const sourcesByPublisherType = useMemo(() => {
    const groups = new Map<PublisherType, Source[]>();
    for (const src of allSources) {
      const pubType = src.publisher_type ?? 'other';
      const existing = groups.get(pubType) ?? [];
      existing.push(src);
      groups.set(pubType, existing);
    }
    return Array.from(groups.entries());
  }, [allSources]);

  const handleCopyCitation = (idKey: string, text: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      void navigator.clipboard.writeText(text);
    }
    setCopiedId(idKey);
    setTimeout(() => {
      setCopiedId((prev) => (prev === idKey ? null : prev));
    }, 1800);
  };

  const hasActiveFilters =
    topicFilter !== 'all' ||
    statusFilter !== 'all' ||
    kindFilter !== 'all' ||
    searchQuery.trim() !== '';

  if (!analysis && isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton lines={4} />
        <Skeleton lines={6} />
      </div>
    );
  }

  const isRunningResearch =
    analysis?.status === 'queued' ||
    analysis?.status === 'parsing' ||
    analysis?.status === 'researching';

  return (
    <div className="space-y-6">
      {/* 1. Live Research Timeline */}
      <Card
        title="Live Research Agent Timeline"
        subtitle="Autonomous Google Search grounding, document fetches, and verbatim quote extraction"
        actions={
          isRunningResearch ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
              <Spinner size="xs" />
              <span>Streaming research steps…</span>
            </span>
          ) : research?.mode ? (
            <Badge variant="slate">Research mode: {research.mode}</Badge>
          ) : undefined
        }
      >
        {timelineSteps.length === 0 ? (
          isRunningResearch ? (
            <Skeleton lines={3} />
          ) : (
            <EmptyState
              title="No research trace steps recorded"
              description="Research steps stream here in real time when the research agent runs."
            />
          )
        ) : (
          <ol className="space-y-2.5" aria-label="Research agent execution trace">
            {timelineSteps.map((step) => {
              const meta = STEP_ICONS[step.kind] ?? STEP_ICONS.reason;
              return (
                <li
                  key={step.step_id}
                  className="rounded-lg border border-border bg-muted/30 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={clsx(
                          'inline-flex items-center rounded-sm border px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-wide uppercase',
                          meta.color,
                        )}
                      >
                        {meta.label}
                      </span>
                      <span className="font-semibold text-foreground">{step.title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {typeof step.duration_ms === 'number' && (
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {step.duration_ms}ms
                        </span>
                      )}
                      {step.source_ids &&
                        step.source_ids.map((sid) => (
                          <SourceChip
                            key={sid}
                            sourceId={sid}
                            sources={allSources}
                            onInspectSource={setSelectedSource}
                          />
                        ))}
                    </div>
                  </div>

                  {step.query && (
                    <div className="mt-1.5 font-mono text-[11px] text-muted-foreground">
                      Query:{' '}
                      <code className="rounded bg-muted px-1">{step.query}</code>
                    </div>
                  )}

                  {step.detail && (
                    <details className="mt-1.5">
                      <summary className="cursor-pointer text-[11px] font-medium text-primary hover:underline">
                        Step detail
                      </summary>
                      <p className="mt-1 rounded border border-border bg-card p-2 text-xs whitespace-pre-wrap text-foreground/85">
                        {step.detail}
                      </p>
                    </details>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </Card>

      {research && (
        <>
          {/* 2. Research Questions & Summary */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card title="Research Questions" className="lg:col-span-1">
              {research.research_questions && research.research_questions.length > 0 ? (
                <ol className="list-decimal space-y-1.5 pl-4 text-xs text-foreground/85">
                  {research.research_questions.map((q, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {q}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-xs text-muted-foreground">No research questions listed.</p>
              )}
            </Card>

            <Card
              title="Research Synthesis Summary"
              subtitle="Click any [E#] chip to jump to the underlying verbatim quote"
              className="lg:col-span-2"
            >
              <div className="text-xs leading-relaxed whitespace-pre-line text-foreground">
                {renderTextWithEvidenceRefs(research.summary)}
              </div>
            </Card>
          </div>

          {/* 3. Evidence Browser & Filterable List */}
          <Card
            title={`Evidence Browser (${filteredEvidence.length} of ${evidenceList.length})`}
            subtitle="Every quantitative claim requires a verbatim quote verified against the fetched document"
            actions={
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <Badge variant="green">✓ {statusCounts.verified} verified</Badge>
                {statusCounts.unverified > 0 && (
                  <Badge variant="amber">• {statusCounts.unverified} unverified</Badge>
                )}
                {statusCounts.failed > 0 && (
                  <Badge variant="red">✕ {statusCounts.failed} failed</Badge>
                )}
                {hasActiveFilters && (
                  <button
                    type="button"
                    onClick={() => {
                      setTopicFilter('all');
                      setStatusFilter('all');
                      setKindFilter('all');
                      setSearchQuery('');
                    }}
                    className="ml-1 rounded border border-input bg-card px-2 py-0.5 text-xs font-medium text-foreground/85 hover:bg-accent"
                  >
                    Clear filters
                  </button>
                )}
              </div>
            }
          >
            <div className="space-y-4">
              {/* Filters & Search */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label
                    htmlFor="evidence-search"
                    className="block text-[11px] font-semibold text-muted-foreground"
                  >
                    Search claims or quotes
                  </label>
                  <input
                    id="evidence-search"
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter by keyword, E1, S1…"
                    className="mt-1 w-full rounded-md border border-input bg-card px-2.5 py-1.5 text-xs text-foreground focus:border-primary focus:ring-2 focus:ring-ring/30 focus:outline-none"
                  />
                </div>

                <div>
                  <label
                    htmlFor="filter-topic"
                    className="block text-[11px] font-semibold text-muted-foreground"
                  >
                    Topic
                  </label>
                  <select
                    id="filter-topic"
                    value={topicFilter}
                    onChange={(e) => setTopicFilter(e.target.value as Topic | 'all')}
                    className="mt-1 w-full rounded-md border border-input bg-card px-2.5 py-1.5 text-xs text-foreground focus:border-primary focus:ring-2 focus:ring-ring/30 focus:outline-none"
                  >
                    <option value="all">All topics</option>
                    <option value="revenue">Revenue</option>
                    <option value="elasticity">Elasticity</option>
                    <option value="investment">Investment</option>
                    <option value="gdp">GDP</option>
                    <option value="profit_shifting">Profit shifting</option>
                    <option value="macro_context">Macro context</option>
                    <option value="policy_history">Policy history</option>
                    <option value="distribution">Distribution</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="filter-verification"
                    className="block text-[11px] font-semibold text-muted-foreground"
                  >
                    Verification Status
                  </label>
                  <select
                    id="filter-verification"
                    value={statusFilter}
                    onChange={(e) =>
                      setStatusFilter(e.target.value as VerificationStatus | 'all')
                    }
                    className="mt-1 w-full rounded-md border border-input bg-card px-2.5 py-1.5 text-xs text-foreground focus:border-primary focus:ring-2 focus:ring-ring/30 focus:outline-none"
                  >
                    <option value="all">All statuses</option>
                    <option value="verified">Verified</option>
                    <option value="unverified">Unverified</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="filter-kind"
                    className="block text-[11px] font-semibold text-muted-foreground"
                  >
                    Evidence Kind
                  </label>
                  <select
                    id="filter-kind"
                    value={kindFilter}
                    onChange={(e) =>
                      setKindFilter(e.target.value as EvidenceKind | 'all')
                    }
                    className="mt-1 w-full rounded-md border border-input bg-card px-2.5 py-1.5 text-xs text-foreground focus:border-primary focus:ring-2 focus:ring-ring/30 focus:outline-none"
                  >
                    <option value="all">All kinds</option>
                    <option value="quantitative">Quantitative</option>
                    <option value="qualitative">Qualitative</option>
                    <option value="historical_event">Historical event</option>
                    <option value="counter_evidence">Counter-evidence</option>
                  </select>
                </div>
              </div>

              {filteredEvidence.length === 0 ? (
                <EmptyState
                  title="No matching evidence items"
                  description="Clear or adjust the filters above to see extracted evidence."
                />
              ) : (
                <div className="space-y-3">
                  {filteredEvidence.map((ev) => {
                    const source = allSources.find((s) => s.source_id === ev.source_id);
                    return (
                      <article
                        key={ev.evidence_id}
                        id={`evidence-${ev.evidence_id}`}
                        tabIndex={-1}
                        className={clsx(
                          'rounded-lg border bg-card p-4 transition-colors focus:ring-1 focus:ring-ring focus:outline-none',
                          highlightedEvidence === ev.evidence_id
                            ? 'border-primary ring-1 ring-primary'
                            : 'border-border',
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-sm bg-primary/15 px-2 py-0.5 font-mono text-xs font-semibold text-primary">
                              {ev.evidence_id}
                            </span>
                            <Badge variant="slate">{ev.topic}</Badge>
                            <Badge
                              variant={
                                ev.kind === 'counter_evidence' ? 'amber' : 'blue'
                              }
                            >
                              {ev.kind}
                            </Badge>
                            <EvidenceVerificationBadge status={ev.verification_status} />
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <SourceChip
                              sourceId={ev.source_id}
                              sources={allSources}
                              onInspectSource={setSelectedSource}
                            />
                            <button
                              type="button"
                              onClick={() =>
                                handleCopyCitation(
                                  ev.evidence_id,
                                  formatCitation(ev, source),
                                )
                              }
                              className="rounded border border-input bg-muted/40 px-2 py-0.5 text-[11px] font-medium text-foreground/85 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                            >
                              {copiedId === ev.evidence_id ? '✓ Copied' : 'Copy citation'}
                            </button>
                          </div>
                        </div>

                        <p className="mt-2.5 text-sm font-medium text-foreground">
                          {ev.claim}
                        </p>

                        {ev.quote && (
                          <blockquote className="mt-2 border-l-3 border-primary bg-muted/40 px-3 py-2 text-xs italic text-foreground/85">
                            &ldquo;{ev.quote}&rdquo;
                          </blockquote>
                        )}

                        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                          {ev.value != null && (
                            <span className="font-semibold text-foreground tabular-nums">
                              Value: {ev.value}
                              {ev.unit ? ` ${ev.unit}` : ''}
                            </span>
                          )}
                          {ev.period && <span>Period: {ev.period}</span>}
                          {ev.location && <span>Location: {ev.location}</span>}
                          {ev.verification_note && (
                            <span className="text-muted-foreground">
                              Note: {ev.verification_note}
                            </span>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>

          {/* Parameter Evidence Cross-Reference */}
          {research.parameter_evidence && research.parameter_evidence.length > 0 && (
            <Card
              title="Parameter Evidence Found in Literature"
              subtitle="Empirical parameter ranges extracted from cited documents for comparison with model assumptions"
            >
              <Table>
                <thead className="bg-muted/40 text-xs font-semibold text-muted-foreground uppercase">
                  <tr>
                    <th className="px-4 py-2.5">Parameter</th>
                    <th className="px-4 py-2.5">Central / Point</th>
                    <th className="px-4 py-2.5">Range [Low, High]</th>
                    <th className="px-4 py-2.5">Evidence IDs</th>
                    <th className="px-4 py-2.5">Note</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-xs">
                  {research.parameter_evidence.map((pe, idx) => (
                    <tr key={`${pe.parameter}-${idx}`}>
                      <td className="px-4 py-2.5 font-mono font-semibold text-foreground">
                        {pe.parameter}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums">
                        {pe.value != null ? pe.value : '—'}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums">
                        {pe.low != null || pe.high != null
                          ? `[${pe.low ?? '—'}, ${pe.high ?? '—'}]`
                          : '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {pe.evidence_ids.map((evId) => (
                            <button
                              key={evId}
                              type="button"
                              onClick={() => scrollToEvidence(evId)}
                              className="rounded border border-primary/35 bg-primary/10 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-primary hover:bg-primary/20"
                            >
                              [{evId}]
                            </button>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{pe.note || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          )}

          {/* 4. AI Interpretations (Rose-bordered cards) */}
          <Card
            title="AI Interpretations"
            subtitle="Analytical synthesis statements explicitly separated from observed data and official costings"
          >
            {research.interpretations && research.interpretations.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {research.interpretations.map((interp) => (
                  <div
                    key={interp.interpretation_id}
                    className="rounded-lg border-2 border-rose-400/35 bg-rose-500/5 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs font-bold text-rose-200">
                        {interp.interpretation_id}
                      </span>
                      <EvidenceBadge evidenceClass="ai_interpretation" />
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-foreground">
                      {interp.statement}
                    </p>
                    {interp.supporting_evidence_ids.length > 0 && (
                      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                        <span className="font-medium">Relies on evidence:</span>
                        {interp.supporting_evidence_ids.map((evId) => (
                          <button
                            key={evId}
                            type="button"
                            onClick={() => scrollToEvidence(evId)}
                            className="rounded border border-rose-400/35 bg-card px-1.5 py-0.5 font-mono text-xs font-semibold text-rose-300 hover:bg-rose-500/15"
                          >
                            [{evId}]
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No interpretations recorded.</p>
            )}
          </Card>

          {/* 5. Confounders & Open Questions */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card
              title="Confounders & Simultaneous Measures"
              subtitle="Factors that complicate isolating the pure rate effect"
            >
              {research.confounders && research.confounders.length > 0 ? (
                <div className="space-y-3">
                  {research.confounders.map((conf, idx) => (
                    <div
                      key={idx}
                      className="rounded-md border border-border bg-muted/30 p-3 text-xs"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold text-foreground">
                          {conf.name}
                        </span>
                        <Badge
                          variant={
                            conf.likely_direction === 'raises_revenue'
                              ? 'green'
                              : conf.likely_direction === 'lowers_revenue'
                                ? 'red'
                                : 'amber'
                          }
                        >
                          {conf.likely_direction.replace(/_/g, ' ')}
                        </Badge>
                      </div>
                      <p className="mt-1 text-foreground/85">{conf.description}</p>
                      {conf.evidence_ids && conf.evidence_ids.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-center gap-1">
                          {conf.evidence_ids.map((evId) => (
                            <button
                              key={evId}
                              type="button"
                              onClick={() => scrollToEvidence(evId)}
                              className="rounded border border-input bg-card px-1.5 py-0.5 font-mono text-[11px] text-primary hover:bg-primary/10"
                            >
                              [{evId}]
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No confounders recorded.</p>
              )}
            </Card>

            <Card
              title="Open Questions & Evidence Gaps"
              subtitle="Remaining uncertainties identified by the research agent"
            >
              {research.open_questions && research.open_questions.length > 0 ? (
                <ul className="list-disc space-y-1.5 pl-4 text-xs text-foreground/85">
                  {research.open_questions.map((oq, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {oq}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">No open questions listed.</p>
              )}
            </Card>
          </div>

          {/* 6. Sources Panel Grouped by Publisher Type */}
          <Card
            title={`Sources Panel (${allSources.length})`}
            subtitle="Grouped by publisher type with reliability tier badges. Click any source to inspect all extracted evidence."
          >
            {sourcesByPublisherType.length === 0 ? (
              <p className="text-xs text-muted-foreground">No sources registered.</p>
            ) : (
              <div className="space-y-4">
                {sourcesByPublisherType.map(([pubType, sources]) => (
                  <div key={pubType} className="space-y-2">
                    <h4 className="text-xs font-bold tracking-wide text-muted-foreground uppercase">
                      {pubType.replace(/_/g, ' ')} ({sources.length})
                    </h4>
                    <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
                      {sources.map((src) => (
                        <div
                          key={src.source_id}
                          className="flex flex-col justify-between rounded-md border border-border bg-muted/30 p-3 text-xs"
                        >
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center justify-between gap-1.5">
                              <div className="flex items-center gap-1.5">
                                <span className="font-mono font-bold text-foreground">
                                  [{src.source_id}]
                                </span>
                                <span className="font-semibold text-foreground/85">
                                  {src.publisher}
                                </span>
                              </div>
                              <div className="flex flex-wrap items-center gap-1">
                                <Badge
                                  variant={
                                    src.reliability_tier === 1
                                      ? 'blue'
                                      : src.reliability_tier === 2
                                        ? 'violet'
                                        : 'slate'
                                  }
                                >
                                  Tier {src.reliability_tier}
                                </Badge>
                                {src.is_placeholder && (
                                  <PlaceholderBadge label="Placeholder" />
                                )}
                              </div>
                            </div>
                            <a
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block font-medium text-primary hover:underline"
                            >
                              {src.title} ↗
                            </a>
                          </div>

                          <div className="mt-2 flex items-center justify-between border-t border-border/70 pt-2 text-[11px] text-muted-foreground">
                            <span>
                              {src.url_verified ? '✓ URL verified' : '• Unverified URL'} ·{' '}
                              {src.access_method}
                            </span>
                            <button
                              type="button"
                              onClick={() => setSelectedSource(src)}
                              className="font-semibold text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none rounded"
                            >
                              View evidence →
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}

      {/* M2 Source Detail Drawer */}
      {selectedSource && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Source details for ${selectedSource.source_id}`}
          className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs"
          onClick={() => setSelectedSource(null)}
        >
          <div
            className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-card p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-border pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded-sm bg-primary/15 px-2 py-0.5 font-mono text-xs font-semibold text-primary">
                    {selectedSource.source_id}
                  </span>
                  <Badge variant="blue">Tier {selectedSource.reliability_tier}</Badge>
                  {selectedSource.is_placeholder && <PlaceholderBadge />}
                </div>
                <h3 className="mt-2 text-base font-bold text-foreground">
                  {selectedSource.title}
                </h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Publisher: {selectedSource.publisher} ({selectedSource.publisher_type})
                </p>
              </div>
              <button
                type="button"
                ref={drawerCloseRef}
                onClick={() => setSelectedSource(null)}
                aria-label="Close source drawer"
                className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-accent"
              >
                Close ✕
              </button>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/40 p-3">
                <a
                  href={selectedSource.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="max-w-xs truncate font-mono text-primary hover:underline"
                >
                  {selectedSource.url} ↗
                </a>
                <button
                  type="button"
                  onClick={() =>
                    handleCopyCitation(
                      `src-${selectedSource.source_id}`,
                      `[${selectedSource.source_id}] ${selectedSource.publisher}, "${selectedSource.title}", ${selectedSource.url}`,
                    )
                  }
                  className="rounded border border-input bg-card px-2.5 py-1 text-xs font-medium text-foreground/85 hover:bg-accent"
                >
                  {copiedId === `src-${selectedSource.source_id}`
                    ? '✓ Copied'
                    : 'Copy source citation'}
                </button>
              </div>

              <h4 className="font-semibold text-foreground">
                Evidence extracted from [{selectedSource.source_id}]
              </h4>
              {evidenceList.filter((e) => e.source_id === selectedSource.source_id)
                .length === 0 ? (
                <p className="text-muted-foreground">
                  No direct evidence items linked to this source ID in this analysis.
                </p>
              ) : (
                <div className="space-y-3">
                  {evidenceList
                    .filter((e) => e.source_id === selectedSource.source_id)
                    .map((ev) => (
                      <div
                        key={ev.evidence_id}
                        className="space-y-1.5 rounded-md border border-border p-3"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-foreground">
                            {ev.evidence_id}
                          </span>
                          <EvidenceVerificationBadge status={ev.verification_status} />
                        </div>
                        <p className="font-medium text-foreground">{ev.claim}</p>
                        {ev.quote && (
                          <blockquote className="border-l-2 border-primary pl-2 italic text-muted-foreground">
                            &ldquo;{ev.quote}&rdquo;
                          </blockquote>
                        )}
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ResearchTab;
