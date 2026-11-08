import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import clsx from 'clsx';
import {
  useAnalysis,
  type Analysis,
  type CheckCategory,
  type CheckStatus,
  type Severity,
  type VerificationCheck,
} from '../../api/hooks';
import {
  Badge,
  Card,
  EmptyState,
  Skeleton,
  VerificationBadge,
  WithheldBanner,
  buttonClasses,
  type BadgeVariant,
} from '../../components/ui';
import { fmtDate } from '../../lib/format';

export interface VerificationTabProps {
  analysis?: Analysis;
}

const CATEGORY_ORDER: readonly CheckCategory[] = [
  'scope',
  'citation',
  'evidence',
  'assumption',
  'calculation',
  'data',
  'causal_claim',
  'uncertainty',
  'report',
] as const;

const CATEGORY_LABELS: Record<CheckCategory, string> = {
  scope: 'Policy Scope Gate',
  citation: 'Source & Citation Integrity',
  evidence: 'Evidence Quality & Coverage',
  assumption: 'Model Assumptions',
  calculation: 'Calculation & Recompute Audit',
  data: 'Curated Data & Baseline Provenance',
  causal_claim: 'Causal Language Audit',
  uncertainty: 'Uncertainty & Interval Semantics',
  report: 'Report Number & Citation Audit',
};

const METHOD_LABELS: Record<VerificationCheck['method'], string> = {
  rule: 'Deterministic rule',
  recompute: 'Engine recompute',
  source_fetch: 'Live URL check',
  llm_critic: 'Gemini critic',
};

const SEVERITY_VARIANTS: Record<Severity, BadgeVariant> = {
  blocking: 'red',
  error: 'red',
  warning: 'amber',
  info: 'slate',
};

const METRIC_KEYS = [
  'revenue_static_gbp_bn',
  'revenue_behavioural_gbp_bn',
  'revenue_dynamic_gbp_bn',
  'business_investment_pct',
  'business_investment_gbp_bn',
  'gdp_level_pct',
  'cost_of_capital_pct',
];

function resolveAffectedLink(
  rawId: string,
  analysisId: string | undefined,
): { href: string | null; label: string; tabLabel: string } {
  if (!analysisId || rawId === '...') {
    return { href: null, label: rawId, tabLabel: '' };
  }
  const base = `/analyses/${analysisId}`;

  const evidenceMatch = /^(?:evidence:)?(E\d+)$/i.exec(rawId);
  if (evidenceMatch) {
    return {
      href: `${base}/research?evidence=${encodeURIComponent(evidenceMatch[1].toUpperCase())}`,
      label: rawId,
      tabLabel: 'Research',
    };
  }

  if (
    rawId.startsWith('source:') ||
    /^S\d+$/i.test(rawId) ||
    rawId.startsWith('D-') ||
    /^I\d+$/i.test(rawId)
  ) {
    return {
      href: `${base}/research`,
      label: rawId,
      tabLabel: 'Research',
    };
  }

  if (rawId.startsWith('precedent:') || rawId.startsWith('CT-')) {
    return {
      href: `${base}/precedents`,
      label: rawId,
      tabLabel: 'Precedents',
    };
  }

  const fyMatch = /(\d{4}-\d{2})/.exec(rawId);
  const foundMetric = METRIC_KEYS.find((m) => rawId.includes(m));
  if (foundMetric) {
    const params = new URLSearchParams({ metric: foundMetric });
    if (fyMatch) {
      params.set('year', fyMatch[1]);
    }
    return {
      href: `${base}/scenarios?${params.toString()}`,
      label: rawId,
      tabLabel: 'Scenarios',
    };
  }

  if (
    rawId.startsWith('rev.') ||
    rawId.startsWith('inv.') ||
    rawId.startsWith('gdp.') ||
    rawId.startsWith('ucc.')
  ) {
    const params = new URLSearchParams();
    if (fyMatch) params.set('year', fyMatch[1]);
    if (rawId.startsWith('rev.static')) params.set('metric', 'revenue_static_gbp_bn');
    else if (rawId.startsWith('rev.behav')) params.set('metric', 'revenue_behavioural_gbp_bn');
    else if (rawId.startsWith('rev.dyn')) params.set('metric', 'revenue_dynamic_gbp_bn');
    else if (rawId.startsWith('inv.')) params.set('metric', 'business_investment_pct');
    else if (rawId.startsWith('gdp.')) params.set('metric', 'gdp_level_pct');
    const qs = params.toString();
    return {
      href: `${base}/assumptions${qs ? `?${qs}` : ''}`,
      label: rawId,
      tabLabel: 'Inspector',
    };
  }

  return {
    href: `${base}/assumptions`,
    label: rawId,
    tabLabel: 'Assumptions',
  };
}

export function VerificationTab({ analysis: propAnalysis }: VerificationTabProps) {
  const { id } = useParams<{ id: string }>();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(propAnalysis ? undefined : id);
  const analysis = propAnalysis ?? fetchedAnalysis;

  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<CheckCategory | 'all'>('all');

  const verification = analysis?.verification;
  const checks = useMemo(() => verification?.checks ?? [], [verification]);

  const counts = useMemo(() => {
    const c = verification?.counts ?? {};
    return {
      pass: c.pass ?? checks.filter((chk) => chk.status === 'pass').length,
      warn: c.warn ?? checks.filter((chk) => chk.status === 'warn').length,
      fail: c.fail ?? checks.filter((chk) => chk.status === 'fail').length,
      skipped: c.skipped ?? checks.filter((chk) => chk.status === 'skipped').length,
    };
  }, [verification, checks]);

  const categoriesPresent = useMemo(() => {
    const set = new Set<CheckCategory>(checks.map((c) => c.category));
    return CATEGORY_ORDER.filter((cat) => set.has(cat));
  }, [checks]);

  const filteredChecks = useMemo(() => {
    return checks.filter((chk) => {
      if (onlyFlagged && chk.status !== 'fail' && chk.status !== 'warn') {
        return false;
      }
      if (selectedCategory !== 'all' && chk.category !== selectedCategory) {
        return false;
      }
      return true;
    });
  }, [checks, onlyFlagged, selectedCategory]);

  const groupedChecks = useMemo(() => {
    const groups: { category: CheckCategory; label: string; items: VerificationCheck[] }[] = [];
    for (const cat of CATEGORY_ORDER) {
      const items = filteredChecks.filter((c) => c.category === cat);
      if (items.length > 0) {
        groups.push({
          category: cat,
          label: CATEGORY_LABELS[cat] ?? cat,
          items,
        });
      }
    }
    return groups;
  }, [filteredChecks]);

  if (!analysis && isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28" />
        <Skeleton lines={6} />
      </div>
    );
  }

  if (!verification) {
    return (
      <EmptyState
        title="Verification audit pending"
        description="The independent verifier runs after research, precedent matching, and econometric modelling complete."
      />
    );
  }

  const analysisId = analysis?.analysis_id ?? id;
  const declineReasons = [
    ...(verification.decline_reasons ?? []),
    ...(analysis?.scope?.forecast_allowed === false ? (analysis.scope.reasons ?? []) : []),
  ];
  const uniqueDeclineReasons = Array.from(new Set(declineReasons));

  const statusOrder: { key: CheckStatus; label: string; colorClass: string }[] = [
    { key: 'pass', label: 'Passed', colorClass: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-200' },
    { key: 'warn', label: 'Warnings', colorClass: 'border-amber-400/25 bg-amber-500/10 text-amber-200' },
    { key: 'fail', label: 'Failed', colorClass: 'border-red-400/25 bg-red-500/10 text-red-200' },
    { key: 'skipped', label: 'Skipped', colorClass: 'border-border bg-muted/40 text-foreground/85' },
  ];

  return (
    <div className="space-y-6">
      {/* Prominent Decline Reasons Banner */}
      {(!verification.forecast_allowed || uniqueDeclineReasons.length > 0) && (
        <WithheldBanner
          title="Quantitative forecast withheld by independent verification"
          reasons={uniqueDeclineReasons}
        />
      )}

      {/* Overall Status Card */}
      <Card
        title="Independent Verification Summary"
        subtitle={`Verified at ${fmtDate(verification.verified_at)} · ${checks.length} total audit checks`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {verification.critic_model && (
              <Badge variant="violet" aria-label={`Critic model: ${verification.critic_model}`}>
                Critic model: {verification.critic_model}
              </Badge>
            )}
            <VerificationBadge overall={verification.overall} />
          </div>
        }
      >
        <div className="space-y-4">
          <p className="text-sm font-medium text-foreground">{verification.summary}</p>

          <div
            aria-label="Verification check counts by status"
            className="grid grid-cols-2 gap-3 sm:grid-cols-4"
          >
            {statusOrder.map((st) => (
              <div
                key={st.key}
                className={clsx(
                  'flex items-center justify-between rounded-lg border px-3.5 py-2.5',
                  st.colorClass,
                )}
              >
                <div className="flex items-center gap-2">
                  <VerificationBadge status={st.key} />
                  <span className="text-xs font-medium">{st.label}</span>
                </div>
                <span className="text-lg font-bold tabular-nums">{counts[st.key]}</span>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* Filters Bar */}
      <Card padding="sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by category">
            <button
              type="button"
              onClick={() => setSelectedCategory('all')}
              className={clsx(
                'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                selectedCategory === 'all'
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:bg-accent/60',
              )}
            >
              All categories ({checks.length})
            </button>
            {categoriesPresent.map((cat) => {
              const count = checks.filter((c) => c.category === cat).length;
              const isSelected = selectedCategory === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={clsx(
                    'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors capitalize',
                    isSelected
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-card text-muted-foreground hover:bg-accent/60',
                  )}
                >
                  {cat.replace(/_/g, ' ')} ({count})
                </button>
              );
            })}
          </div>

          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-1.5 text-xs font-medium text-foreground/85 select-none hover:bg-accent">
            <input
              type="checkbox"
              checked={onlyFlagged}
              onChange={(e) => setOnlyFlagged(e.target.checked)}
              className="h-3.5 w-3.5 accent-primary"
            />
            <span>Failed or warnings only ({counts.fail + counts.warn})</span>
          </label>
        </div>
      </Card>

      {/* Grouped Checks */}
      {groupedChecks.length === 0 ? (
        <EmptyState
          title="No checks match the active filters"
          description="Clear the category or failed/warning filter to inspect all verification checks."
          action={
            <button
              type="button"
              onClick={() => {
                setOnlyFlagged(false);
                setSelectedCategory('all');
              }}
              className={buttonClasses('primary', 'xs')}
            >
              Reset filters
            </button>
          }
        />
      ) : (
        <div className="space-y-4">
          {groupedChecks.map((group) => (
            <Card
              key={group.category}
              title={group.label}
              subtitle={`Category: ${group.category} · ${group.items.length} check${group.items.length === 1 ? '' : 's'}`}
              padding="none"
            >
              <ul className="divide-y divide-border">
                {group.items.map((chk) => (
                  <li key={chk.check_id} className="p-4 sm:px-5">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <VerificationBadge status={chk.status} />
                        <span className="font-mono text-xs font-bold text-foreground">
                          {chk.check_id}
                        </span>
                        <h4 className="text-sm font-semibold text-foreground">{chk.title}</h4>
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge
                          variant={SEVERITY_VARIANTS[chk.severity] ?? 'slate'}
                          aria-label={`Severity: ${chk.severity}`}
                        >
                          Severity: {chk.severity}
                        </Badge>
                        <Badge variant="slate" aria-label={`Method: ${chk.method}`}>
                          Method: {METHOD_LABELS[chk.method] ?? chk.method}
                        </Badge>
                      </div>
                    </div>

                    <p className="mt-2 text-xs leading-relaxed text-foreground/85">{chk.detail}</p>

                    {chk.affected_ids && chk.affected_ids.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                        <span className="text-[11px] font-medium text-muted-foreground">
                          Affected items:
                        </span>
                        {chk.affected_ids.map((affId, idx) => {
                          const resolved = resolveAffectedLink(affId, analysisId);
                          if (!resolved.href) {
                            return (
                              <span
                                key={`${affId}-${idx}`}
                                className="rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground"
                              >
                                {resolved.label}
                              </span>
                            );
                          }
                          return (
                            <Link
                              key={`${affId}-${idx}`}
                              to={resolved.href}
                              className="inline-flex items-center gap-1 rounded border border-primary/25 bg-primary/10 px-2 py-0.5 font-mono text-[11px] font-medium text-primary transition-colors hover:bg-primary/20"
                            >
                              <span>{resolved.label}</span>
                              <span className="font-sans text-[10px] text-primary">
                                → {resolved.tabLabel}
                              </span>
                            </Link>
                          );
                        })}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}

      {/* Governance, Risk Controls & Execution Boundaries Card */}
      <Card
        title="Governance, Risk Controls & Execution Boundaries"
        subtitle="Explicit human-in-the-loop oversight, model execution boundaries, anti-prompt-injection isolation, and data privacy controls."
      >
        <div className="grid grid-cols-1 gap-4 text-xs leading-relaxed text-slate-700 sm:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3.5">
            <h4 className="font-semibold text-slate-900">
              1. What the Agent May Do Alone vs. Human Approval
            </h4>
            <p className="mt-1">
              <strong>Autonomous (read-only &amp; bounded):</strong> Parse plain-English queries into a
              candidate <code className="font-mono text-[11px]">PolicySpec</code>, retrieve grounded
              official sources (OBR, HMRC, ONS, IFS), verify verbatim quotes against SHA-256
              snapshots, and execute the deterministic NumPy simulation and 18-check audit.
            </p>
            <p className="mt-1.5">
              <strong>Requires Human Approval:</strong> Confirming or editing the parsed policy
              specification before running (<code className="font-mono text-[11px]">New Analysis</code>{' '}
              Stage 2), overriding structural or market-regime parameters (
              <code className="font-mono text-[11px]">Assumptions &amp; Lab</code>), and any downstream
              policy briefing use. Forecasts are automatically withheld (
              <code className="font-mono text-[11px]">forecast_withheld</code>) if any blocking check
              fails.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3.5">
            <h4 className="font-semibold text-slate-900">
              2. Where Each Model Runs &amp; What Data Leaves the Device
            </h4>
            <p className="mt-1">
              <strong>100% On-Device (Local Python / NumPy / SQLite):</strong> Deterministic rules
              parser, historical Scope Gate (<code className="font-mono text-[11px]">15pp</code> hard
              limit), Hall–Jorgenson / King–Fullerton econometric engine (
              <code className="font-mono text-[11px]">engine-1.0.0</code>), 2,000-draw Monte Carlo,
              independent recompute verifier (<code className="font-mono text-[11px]">CALC-001</code>{' '}
              to <code className="font-mono text-[11px]">1e-9</code>), and{' '}
              <code className="font-mono text-[11px]">{'{{fig:id}}'}</code> report number substitution.
            </p>
            <p className="mt-1.5">
              <strong>External Network Calls:</strong> In{' '}
              <code className="font-mono text-[11px]">cached</code> and{' '}
              <code className="font-mono text-[11px]">mock</code> modes,{' '}
              <strong>zero bytes leave the device</strong>. In{' '}
              <code className="font-mono text-[11px]">live</code> mode, only the public tax policy query
              and search queries are sent to Google Gemini (<code className="font-mono text-[11px]">store=False</code>{' '}
              enforced — zero prompt retention) and official <code className="font-mono text-[11px]">.gov.uk</code> /{' '}
              <code className="font-mono text-[11px]">.org.uk</code> URLs. Untrusted prompt text never
              executes code or injects numbers.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default VerificationTab;
