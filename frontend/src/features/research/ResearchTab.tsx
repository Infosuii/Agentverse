import React, { useMemo, useState } from 'react';
import { useOutletContext, useParams } from 'react-router';
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
} from '../../components/ui';

export interface ResearchTabProps {
  analysis?: Analysis;
  liveSteps?: ResearchStep[];
}

const STEP_ICONS: Record<ResearchStepKind, { icon: string; label: string; color: string }> = {
  plan: { icon: '📋', label: 'Plan', color: 'bg-blue-50 text-blue-800 border-blue-200' },
  search: { icon: '🔍', label: 'Search', color: 'bg-indigo-50 text-indigo-800 border-indigo-200' },
  fetch: { icon: '📄', label: 'Fetch URL', color: 'bg-cyan-50 text-cyan-800 border-cyan-200' },
  extract: { icon: '❝', label: 'Extract Quote', color: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  dataset_lookup: { icon: '📊', label: 'Dataset', color: 'bg-violet-50 text-violet-800 border-violet-200' },
  reason: { icon: '🧠', label: 'Reason', color: 'bg-slate-100 text-slate-800 border-slate-300' },
  synthesis: { icon: '✦', label: 'Synthesise', color: 'bg-blue-50 text-blue-800 border-blue-300' },
  warning: { icon: '⚠', label: 'Warning', color: 'bg-amber-50 text-amber-900 border-amber-300' },
  error: { icon: '✕', label: 'Error', color: 'bg-red-50 text-red-900 border-red-300' },
};

function scrollToEvidence(evidenceId: string) {
  const el = document.getElementById(`evidence-${evidenceId}`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
          className="mx-0.5 inline-flex items-center rounded border border-blue-300 bg-blue-50 px-1.5 py-0 font-mono text-xs font-semibold text-blue-800 hover:bg-blue-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
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

  const filteredEvidence = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return evidenceList.filter((ev) => {
      if (topicFilter !== 'all' && ev.topic !== topicFilter) return false;
      if (statusFilter !== 'all' && ev.verification_status !== statusFilter) return false;
      if (kindFilter !== 'all' && ev.kind !== kindFilter) return false;
      if (q) {
        const hay = `${ev.evidence_id} ${ev.claim} ${ev.quote ?? ''} ${ev.topic} ${ev.source_id}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [evidenceList, topicFilter, statusFilter, kindFilter, searchQuery]);

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
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-700">
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
          <ol className="space-y-2.5">
            {timelineSteps.map((step) => {
              const meta = STEP_ICONS[step.kind] ?? STEP_ICONS.reason;
              return (
                <li
                  key={step.step_id}
                  className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={clsx(
                          'inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-semibold',
                          meta.color,
                        )}
                      >
                        <span aria-hidden="true">{meta.icon}</span>
                        <span>{meta.label}</span>
                      </span>
                      <span className="font-semibold text-slate-900">{step.title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {typeof step.duration_ms === 'number' && (
                        <span className="font-mono text-[11px] text-slate-500">
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
                    <div className="mt-1.5 font-mono text-[11px] text-slate-600">
                      Query: <code className="rounded bg-slate-200/70 px-1">{step.query}</code>
                    </div>
                  )}

                  {step.detail && (
                    <details className="mt-1.5">
                      <summary className="cursor-pointer text-[11px] font-medium text-blue-700 hover:underline">
                        Step detail
                      </summary>
                      <p className="mt-1 whitespace-pre-wrap rounded bg-white p-2 text-xs text-slate-700 border border-slate-200">
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
                <ol className="list-decimal space-y-1.5 pl-4 text-xs text-slate-700">
                  {research.research_questions.map((q, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {q}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-xs text-slate-500">No research questions listed.</p>
              )}
            </Card>

            <Card
              title="Research Synthesis Summary"
              subtitle="Click any [E#] chip to jump to the underlying verbatim quote"
              className="lg:col-span-2"
            >
              <div className="text-xs leading-relaxed text-slate-800 whitespace-pre-line">
                {renderTextWithEvidenceRefs(research.summary)}
              </div>
            </Card>
          </div>

          {/* 3. Evidence Browser & Filterable List */}
          <Card
            title={`Extracted Evidence (${filteredEvidence.length} of ${evidenceList.length})`}
            subtitle="Every quantitative claim requires a verbatim quote verified against the fetched document"
          >
            <div className="space-y-4">
              {/* Filters & Search */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label
                    htmlFor="evidence-search"
                    className="block text-[11px] font-semibold text-slate-600"
                  >
                    Search claims or quotes
                  </label>
                  <input
                    id="evidence-search"
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter by keyword, E1, S1…"
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
                  />
                </div>

                <div>
                  <label
                    htmlFor="filter-topic"
                    className="block text-[11px] font-semibold text-slate-600"
                  >
                    Topic
                  </label>
                  <select
                    id="filter-topic"
                    value={topicFilter}
                    onChange={(e) => setTopicFilter(e.target.value as Topic | 'all')}
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
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
                    className="block text-[11px] font-semibold text-slate-600"
                  >
                    Verification Status
                  </label>
                  <select
                    id="filter-verification"
                    value={statusFilter}
                    onChange={(e) =>
                      setStatusFilter(e.target.value as VerificationStatus | 'all')
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
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
                    className="block text-[11px] font-semibold text-slate-600"
                  >
                    Evidence Kind
                  </label>
                  <select
                    id="filter-kind"
                    value={kindFilter}
                    onChange={(e) =>
                      setKindFilter(e.target.value as EvidenceKind | 'all')
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
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
                        className="rounded-lg border border-slate-200 bg-white p-4 shadow-2xs transition-shadow focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded bg-slate-900 px-2 py-0.5 font-mono text-xs font-bold text-white">
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
                              className="rounded border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                            >
                              {copiedId === ev.evidence_id ? '✓ Copied' : 'Copy citation'}
                            </button>
                          </div>
                        </div>

                        <p className="mt-2.5 text-sm font-medium text-slate-900">
                          {ev.claim}
                        </p>

                        {ev.quote && (
                          <blockquote className="mt-2 border-l-3 border-blue-500 bg-slate-50 px-3 py-2 text-xs italic text-slate-700">
                            &ldquo;{ev.quote}&rdquo;
                          </blockquote>
                        )}

                        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                          {ev.value != null && (
                            <span className="font-semibold text-slate-800 tabular-nums">
                              Value: {ev.value}
                              {ev.unit ? ` ${ev.unit}` : ''}
                            </span>
                          )}
                          {ev.period && <span>Period: {ev.period}</span>}
                          {ev.location && <span>Location: {ev.location}</span>}
                          {ev.verification_note && (
                            <span className="text-slate-500">
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
                    className="rounded-lg border-2 border-rose-300 bg-rose-50/40 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs font-bold text-rose-900">
                        {interp.interpretation_id}
                      </span>
                      <EvidenceBadge evidenceClass="ai_interpretation" />
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-slate-900">
                      {interp.statement}
                    </p>
                    {interp.supporting_evidence_ids.length > 0 && (
                      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-600">
                        <span className="font-medium">Relies on evidence:</span>
                        {interp.supporting_evidence_ids.map((evId) => (
                          <button
                            key={evId}
                            type="button"
                            onClick={() => scrollToEvidence(evId)}
                            className="rounded border border-rose-300 bg-white px-1.5 py-0.5 font-mono text-xs font-semibold text-rose-800 hover:bg-rose-100"
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
              <p className="text-xs text-slate-500">No interpretations recorded.</p>
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
                      className="rounded-md border border-slate-200 bg-slate-50/60 p-3 text-xs"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold text-slate-900">
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
                          {conf.likely_direction.replace('_', ' ')}
                        </Badge>
                      </div>
                      <p className="mt-1 text-slate-700">{conf.description}</p>
                      {conf.evidence_ids && conf.evidence_ids.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-center gap-1">
                          {conf.evidence_ids.map((evId) => (
                            <button
                              key={evId}
                              type="button"
                              onClick={() => scrollToEvidence(evId)}
                              className="rounded border border-slate-300 bg-white px-1.5 py-0.5 font-mono text-[11px] text-blue-700 hover:bg-blue-50"
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
                <p className="text-xs text-slate-500">No confounders recorded.</p>
              )}
            </Card>

            <Card
              title="Open Questions & Evidence Gaps"
              subtitle="Remaining uncertainties identified by the research agent"
            >
              {research.open_questions && research.open_questions.length > 0 ? (
                <ul className="list-disc space-y-1.5 pl-4 text-xs text-slate-700">
                  {research.open_questions.map((oq, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {oq}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-500">No open questions listed.</p>
              )}
            </Card>
          </div>

          {/* 6. Sources Panel Grouped by Publisher Type */}
          <Card
            title={`Sources Panel (${allSources.length})`}
            subtitle="Grouped by publisher type with reliability tier badges. Click any source to inspect all extracted evidence."
          >
            {sourcesByPublisherType.length === 0 ? (
              <p className="text-xs text-slate-500">No sources registered.</p>
            ) : (
              <div className="space-y-4">
                {sourcesByPublisherType.map(([pubType, sources]) => (
                  <div key={pubType} className="space-y-2">
                    <h4 className="text-xs font-bold tracking-wide text-slate-600 uppercase">
                      {pubType.replace('_', ' ')} ({sources.length})
                    </h4>
                    <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
                      {sources.map((src) => (
                        <div
                          key={src.source_id}
                          className="flex flex-col justify-between rounded-md border border-slate-200 bg-slate-50/50 p-3 text-xs"
                        >
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center justify-between gap-1.5">
                              <div className="flex items-center gap-1.5">
                                <span className="font-mono font-bold text-slate-900">
                                  [{src.source_id}]
                                </span>
                                <span className="font-semibold text-slate-700">
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
                                {src.is_placeholder && <PlaceholderBadge label="Placeholder" />}
                              </div>
                            </div>
                            <a
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block font-medium text-blue-700 hover:underline"
                            >
                              {src.title} ↗
                            </a>
                          </div>

                          <div className="mt-2 flex items-center justify-between border-t border-slate-200/70 pt-2 text-[11px] text-slate-500">
                            <span>
                              {src.url_verified ? '✓ URL verified' : '• Unverified URL'} ·{' '}
                              {src.access_method}
                            </span>
                            <button
                              type="button"
                              onClick={() => setSelectedSource(src)}
                              className="font-semibold text-blue-700 hover:underline focus:outline-none"
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
          className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs"
          onClick={() => setSelectedSource(null)}
        >
          <div
            className="flex h-full w-full max-w-lg flex-col bg-white p-6 shadow-2xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-slate-200 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-slate-900 px-2 py-0.5 font-mono text-xs font-bold text-white">
                    {selectedSource.source_id}
                  </span>
                  <Badge variant="blue">Tier {selectedSource.reliability_tier}</Badge>
                  {selectedSource.is_placeholder && <PlaceholderBadge />}
                </div>
                <h3 className="mt-2 text-base font-bold text-slate-900">
                  {selectedSource.title}
                </h3>
                <p className="mt-0.5 text-xs text-slate-600">
                  Publisher: {selectedSource.publisher} ({selectedSource.publisher_type})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSource(null)}
                aria-label="Close source drawer"
                className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                Close ✕
              </button>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-50 p-3">
                <a
                  href={selectedSource.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate font-mono text-blue-700 hover:underline max-w-xs"
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
                  className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  {copiedId === `src-${selectedSource.source_id}`
                    ? '✓ Copied'
                    : 'Copy source citation'}
                </button>
              </div>

              <h4 className="font-semibold text-slate-900">
                Evidence extracted from [{selectedSource.source_id}]
              </h4>
              {evidenceList.filter((e) => e.source_id === selectedSource.source_id)
                .length === 0 ? (
                <p className="text-slate-500">
                  No direct evidence items linked to this source ID in this analysis.
                </p>
              ) : (
                <div className="space-y-3">
                  {evidenceList
                    .filter((e) => e.source_id === selectedSource.source_id)
                    .map((ev) => (
                      <div
                        key={ev.evidence_id}
                        className="rounded-md border border-slate-200 p-3 space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-slate-900">
                            {ev.evidence_id}
                          </span>
                          <EvidenceVerificationBadge status={ev.verification_status} />
                        </div>
                        <p className="font-medium text-slate-900">{ev.claim}</p>
                        {ev.quote && (
                          <blockquote className="border-l-2 border-blue-500 pl-2 italic text-slate-600">
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
