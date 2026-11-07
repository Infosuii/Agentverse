import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import clsx from 'clsx';
import {
  ApiClientError,
  useAnalysis,
  useCreateAnalysis,
  useSimulate,
  type Analysis,
  type MetricName,
  type SimulationBundle,
} from '../../api/hooks';
import {
  Badge,
  Card,
  EmptyState,
  EvidenceBadge,
  PlaceholderBadge,
  Skeleton,
  Spinner,
  Tooltip,
  WithheldBanner,
} from '../../components/ui';
import {
  FanChart,
  Histogram,
  LineChart,
  ProvenanceNumber,
  Tornado,
  formatChartValue,
} from '../../components/charts';
import { fmtFiscalYear, fmtPp } from '../../lib/format';
import { SCENARIO_COLORS, type ScenarioColorKey } from '../../lib/theme';
import {
  METRIC_DESCRIPTORS,
  buildFanBands,
  buildParameterOverrides,
  buildPolicyWithRateOverride,
  buildScenarioSeries,
  extractFinalYearHistogram,
  extractTornadoItems,
  getMetricDescriptor,
} from './transforms';

export interface ScenariosTabProps {
  analysis?: Analysis;
}

export function ScenariosTab({ analysis: propAnalysis }: ScenariosTabProps) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(propAnalysis ? undefined : id);
  const analysis = propAnalysis ?? fetchedAnalysis;

  const [selectedMetric, setSelectedMetric] = useState<MetricName>(
    'revenue_behavioural_gbp_bn',
  );
  const [showEmpiricalBand, setShowEmpiricalBand] = useState<boolean>(false);
  const [useCustomDistributions, setUseCustomDistributions] = useState<boolean>(false);
  const [sliderValues, setSliderValues] = useState<Record<string, number>>({});
  const [proposedRateOverride, setProposedRateOverride] = useState<number | null>(null);
  const [customBundle, setCustomBundle] = useState<SimulationBundle | null>(null);
  const [recomputedMs, setRecomputedMs] = useState<number | null>(null);
  const [scopeErrorReasons, setScopeErrorReasons] = useState<string[]>([]);

  const simulateMutation = useSimulate();
  const createAnalysisMutation = useCreateAnalysis();
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const simulation = analysis?.simulation;
  const policy = analysis?.policy ?? simulation?.policy;
  const assumptions = useMemo(
    () => simulation?.assumptions ?? [],
    [simulation?.assumptions],
  );
  const adjustableAssumptions = useMemo(
    () => assumptions.filter((a) => a.adjustable),
    [assumptions],
  );

  // Sync slider initial state when analysis changes
  useEffect(() => {
    const initial: Record<string, number> = {};
    for (const a of assumptions) {
      if (a.adjustable) {
        initial[a.name] = a.value;
      }
    }
    setSliderValues(initial);
    setProposedRateOverride(policy?.proposed_rate_pct ?? null);
    setCustomBundle(null);
    setRecomputedMs(null);
    setScopeErrorReasons([]);
    setUseCustomDistributions(false);
  }, [analysis?.analysis_id, assumptions, policy?.proposed_rate_pct]);

  const parameterOverrides = useMemo(
    () => buildParameterOverrides(assumptions, sliderValues),
    [assumptions, sliderValues],
  );

  const hasRateOverride =
    proposedRateOverride !== null &&
    policy?.proposed_rate_pct != null &&
    Math.abs(proposedRateOverride - policy.proposed_rate_pct) > 1e-6;

  const hasAnyOverride =
    Object.keys(parameterOverrides).length > 0 || hasRateOverride;

  // Debounced 300ms live re-simulation
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    if (!policy || !hasAnyOverride) {
      if (!hasAnyOverride) {
        setCustomBundle(null);
        setRecomputedMs(null);
        setScopeErrorReasons([]);
        setUseCustomDistributions(false);
      }
      return;
    }

    debounceTimerRef.current = setTimeout(() => {
      const effectivePolicy = buildPolicyWithRateOverride(policy, proposedRateOverride);
      const t0 = performance.now();

      simulateMutation.mutate(
        {
          policy: effectivePolicy,
          parameter_overrides: parameterOverrides,
          monte_carlo_draws: 2000,
          seed: 42,
          include_sensitivity: true,
        },
        {
          onSuccess: (data) => {
            const elapsed = Math.max(1, Math.round(performance.now() - t0));
            setCustomBundle(data);
            setRecomputedMs(elapsed);
            setScopeErrorReasons([]);
            setUseCustomDistributions(true);
          },
          onError: (err) => {
            if (err instanceof ApiClientError && err.reasons.length > 0) {
              setScopeErrorReasons(err.reasons);
            } else if (err instanceof Error) {
              setScopeErrorReasons([err.message]);
            } else {
              setScopeErrorReasons([
                'Policy rate or parameter override falls outside validated scope.',
              ]);
            }
          },
        },
      );
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAnyOverride, parameterOverrides, policy, proposedRateOverride]);

  const activeDistributionBundle =
    useCustomDistributions && customBundle ? customBundle : simulation;

  const centralScenario = useMemo(
    () =>
      simulation?.scenarios?.find((s) => s.scenario.name === 'central') ??
      simulation?.scenarios?.[0],
    [simulation?.scenarios],
  );

  const selectedProjection = useMemo(
    () =>
      centralScenario?.result.metrics.find((m) => m.metric === selectedMetric),
    [centralScenario, selectedMetric],
  );

  const descriptor = useMemo(
    () => getMetricDescriptor(selectedMetric, selectedProjection),
    [selectedMetric, selectedProjection],
  );

  const scenarioSeries = useMemo(
    () => buildScenarioSeries(simulation, selectedMetric, customBundle),
    [simulation, selectedMetric, customBundle],
  );

  const fanData = useMemo(
    () => buildFanBands(activeDistributionBundle, selectedMetric),
    [activeDistributionBundle, selectedMetric],
  );

  const histogramData = useMemo(
    () => extractFinalYearHistogram(activeDistributionBundle, selectedMetric),
    [activeDistributionBundle, selectedMetric],
  );

  const tornadoData = useMemo(
    () => extractTornadoItems(activeDistributionBundle, selectedMetric),
    [activeDistributionBundle, selectedMetric],
  );

  if (!analysis && isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Skeleton className="h-80 lg:col-span-2" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <EmptyState
        title="Analysis not available"
        description="Select or create an analysis to explore scenarios and uncertainty."
      />
    );
  }

  const forecastAllowed =
    analysis.verification?.forecast_allowed !== false &&
    analysis.scope?.forecast_allowed !== false;

  const declineReasons = Array.from(
    new Set([
      ...(analysis.verification?.decline_reasons ?? []),
      ...(analysis.scope?.forecast_allowed === false
        ? (analysis.scope.reasons ?? [])
        : []),
    ]),
  );

  if (!forecastAllowed) {
    return (
      <div className="space-y-4">
        <WithheldBanner reasons={declineReasons} />
      </div>
    );
  }

  if (!simulation) {
    return (
      <EmptyState
        title="Simulation results pending"
        description="Scenario trajectories, Monte Carlo fan charts, and tornado sensitivity will appear once the modelling stage completes."
      />
    );
  }

  const handleResetAllSliders = () => {
    const defaults: Record<string, number> = {};
    for (const a of assumptions) {
      if (a.adjustable) {
        defaults[a.name] = a.value;
      }
    }
    setSliderValues(defaults);
    setProposedRateOverride(policy?.proposed_rate_pct ?? null);
    setCustomBundle(null);
    setRecomputedMs(null);
    setScopeErrorReasons([]);
    setUseCustomDistributions(false);
  };

  const handleFullRerun = () => {
    if (!policy) return;
    const effectivePolicy = buildPolicyWithRateOverride(policy, proposedRateOverride);
    createAnalysisMutation.mutate(
      {
        query: analysis.request.query || effectivePolicy.description || 'Custom scenario re-run',
        policy_override: effectivePolicy,
        parameter_overrides: parameterOverrides,
        reuse_research_from: analysis.analysis_id,
      },
      {
        onSuccess: (created) => {
          void navigate(`/analyses/${created.analysis_id}/scenarios`);
        },
      },
    );
  };

  const finalYear =
    centralScenario?.result.fiscal_years[
      centralScenario.result.fiscal_years.length - 1
    ];
  const finalCentralVal =
    selectedProjection?.values[selectedProjection.values.length - 1]?.value;

  const customCentralProj = customBundle?.scenarios?.[0]?.result.metrics.find(
    (m) => m.metric === selectedMetric,
  );
  const customFinalVal =
    customCentralProj?.values[customCentralProj.values.length - 1]?.value;

  const hasEmpiricalBand = fanData.empiricalBands.length > 0;
  const hasPlaceholderAssumptions = assumptions.some((a) => a.is_placeholder);

  const scenarioDescriptionsContent = (
    <span className="block space-y-1.5">
      <span className="block font-semibold text-white">Scenario definitions</span>
      {simulation.scenarios.map((s) => (
        <span key={s.scenario.name} className="block text-[11px] text-slate-200">
          <strong className="text-white">{s.scenario.label}:</strong>{' '}
          {s.scenario.description}
        </span>
      ))}
    </span>
  );

  return (
    <div className="space-y-6">
      {/* 1. Metric Selector Bar */}
      <Card
        title="Metric Selector & Confidence"
        subtitle="Select any of the 7 modelled outputs to inspect scenario paths, Monte Carlo uncertainty, and sensitivity."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <EvidenceBadge evidenceClass="model_scenario" />
            {hasPlaceholderAssumptions && <PlaceholderBadge />}
          </div>
        }
      >
        <div className="space-y-3">
          <div
            role="radiogroup"
            aria-label="Select modelled metric"
            className="flex flex-wrap gap-2"
          >
            {METRIC_DESCRIPTORS.map((m) => {
              const proj = centralScenario?.result.metrics.find(
                (p) => p.metric === m.metric,
              );
              const meta = getMetricDescriptor(m.metric, proj);
              const isSelected = m.metric === selectedMetric;

              return (
                <button
                  key={m.metric}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => setSelectedMetric(m.metric)}
                  className={clsx(
                    'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs font-medium transition-colors focus:ring-2 focus:ring-blue-500 focus:outline-none',
                    isSelected
                      ? 'border-blue-600 bg-blue-50 text-blue-900 shadow-xs'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50',
                  )}
                >
                  <span>{meta.shortLabel}</span>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                    {meta.unit}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-900">{descriptor.label}</span>
              <span className="text-slate-500">({descriptor.unit})</span>
              <Badge
                variant={
                  descriptor.confidence === 'high'
                    ? 'green'
                    : descriptor.confidence === 'medium'
                      ? 'blue'
                      : 'amber'
                }
              >
                Confidence: {descriptor.confidence}
              </Badge>
              {descriptor.lowConfidenceNote && (
                <Badge variant="amber">{descriptor.lowConfidenceNote}</Badge>
              )}
            </div>

            {finalYear && finalCentralVal !== undefined && (
              <div className="flex items-center gap-1.5 text-slate-600">
                <span>Central ({fmtFiscalYear(finalYear)}):</span>
                <ProvenanceNumber
                  value={finalCentralVal}
                  unit={descriptor.unit}
                  evidenceClass="model_scenario"
                  analysisId={analysis.analysis_id}
                  metric={selectedMetric}
                  year={finalYear}
                  sources={analysis.sources}
                />
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Main Grid: Charts (2 cols) + Live Sliders Side Panel (1 col) */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Left/Center: 4 Charts */}
        <div className="space-y-6 xl:col-span-2">
          {/* 2. Scenario LineChart */}
          <LineChart
            title={`Scenario Paths — ${descriptor.label}`}
            caption={`Central, optimistic and pessimistic projections over fiscal years (model scenario).`}
            unit={descriptor.unit}
            series={scenarioSeries}
            actions={
              <Tooltip content={scenarioDescriptionsContent}>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  <span aria-hidden="true">ℹ</span>
                  <span>Scenario rules</span>
                </button>
              </Tooltip>
            }
            footer={
              <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                {(['central', 'optimistic', 'pessimistic', 'custom'] as ScenarioColorKey[]).map(
                  (key) => {
                    const scen = simulation.scenarios.find((s) => s.scenario.name === key);
                    if (!scen && (key !== 'custom' || !customBundle)) return null;
                    return (
                      <span key={key} className="inline-flex items-center gap-1">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: SCENARIO_COLORS[key] }}
                        />
                        <span className="font-medium capitalize text-slate-700">{key}:</span>
                        <span>
                          {scen?.scenario.description ??
                            'Live re-simulation with slider overrides.'}
                        </span>
                      </span>
                    );
                  },
                )}
              </div>
            }
          />

          {/* 3. Monte Carlo FanChart */}
          <FanChart
            title={`Monte Carlo Uncertainty — ${descriptor.label}`}
            caption={`Shaded p5–p95 and p25–p75 assumption-driven bands across ${activeDistributionBundle?.monte_carlo?.n_draws ?? 2000} draws (model scenario).`}
            unit={descriptor.unit}
            bands={fanData.bands}
            intervalNote={fanData.intervalNote}
            empiricalBands={showEmpiricalBand ? fanData.empiricalBands : undefined}
            actions={
              hasEmpiricalBand ? (
                <label className="inline-flex cursor-pointer items-center gap-1.5 rounded border border-teal-300 bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-900">
                  <input
                    type="checkbox"
                    checked={showEmpiricalBand}
                    onChange={(e) => setShowEmpiricalBand(e.target.checked)}
                    className="rounded border-teal-400 text-teal-700 focus:ring-teal-500"
                  />
                  <span>Show backtest-calibrated interval</span>
                </label>
              ) : undefined
            }
            footer={
              <div className="mt-1 space-y-1 text-[11px]">
                {hasEmpiricalBand ? (
                  showEmpiricalBand &&
                  fanData.empiricalCalibrationNote && (
                    <p className="font-medium text-teal-800">
                      Empirical calibration: {fanData.empiricalCalibrationNote}
                    </p>
                  )
                ) : (
                  <p className="text-slate-500">
                    Backtest-calibrated empirical interval unavailable for this metric
                    (requires at least 8 out-of-sample behavioural revenue backtest residuals).
                  </p>
                )}
              </div>
            }
          />

          {/* 4 & 5. Final-year Histogram + Tornado Sensitivity */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Histogram
              title={`Final-Year Distribution (${fmtFiscalYear(histogramData.histogram?.fiscal_year ?? finalYear ?? 'Year 5')})`}
              caption={`Distribution of ${activeDistributionBundle?.monte_carlo?.n_draws ?? 2000} draws in the final horizon year (model scenario).`}
              unit={descriptor.unit}
              binEdges={histogramData.histogram?.bin_edges ?? []}
              counts={histogramData.histogram?.counts ?? []}
              markers={{
                central: histogramData.centralFinal,
                p5: histogramData.p5Final,
                p95: histogramData.p95Final,
                custom: customFinalVal,
              }}
            />

            {tornadoData.items.length > 0 ? (
              <Tornado
                title={`Parameter Sensitivity Tornado (${fmtFiscalYear(tornadoData.sensitivity?.fiscal_year ?? finalYear ?? 'Year 5')})`}
                caption="One-at-a-time swing from low to high parameter bounds around central (model scenario)."
                unit={descriptor.unit}
                base={tornadoData.sensitivity?.base_output ?? finalCentralVal ?? 0}
                items={tornadoData.items}
              />
            ) : (
              <Card
                title="Parameter Sensitivity Tornado"
                subtitle="One-at-a-time parameter swing around the central scenario"
              >
                <EmptyState
                  title="No tornado sensitivity for this metric"
                  description="Tornado sensitivity is computed for behavioural revenue, business investment (%), and GDP level (%) once the full simulation runner runs."
                />
              </Card>
            )}
          </div>
        </div>

        {/* Right: 4.1 Live Sliders Side Panel */}
        <div className="space-y-4 xl:col-span-1">
          <Card
            title="Live Assumption Sliders"
            subtitle="Adjust policy rate or model parameters to re-simulate in under 1 second."
            actions={
              hasAnyOverride ? (
                <button
                  type="button"
                  onClick={handleResetAllSliders}
                  className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Reset all
                </button>
              ) : undefined
            }
          >
            <div className="space-y-4">
              {/* Status & Custom toggle bar */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
                <div className="flex items-center gap-2">
                  {simulateMutation.isPending ? (
                    <span className="inline-flex items-center gap-1.5 text-blue-700">
                      <Spinner size="xs" />
                      <span>Simulating…</span>
                    </span>
                  ) : recomputedMs !== null ? (
                    <span className="font-medium text-violet-800">
                      recomputed in {recomputedMs} ms
                    </span>
                  ) : (
                    <span className="text-slate-500">
                      Drag any slider to overlay custom scenario
                    </span>
                  )}
                </div>

                {customBundle && (
                  <label className="inline-flex cursor-pointer items-center gap-1.5 font-medium text-violet-800">
                    <input
                      type="checkbox"
                      checked={useCustomDistributions}
                      onChange={(e) => setUseCustomDistributions(e.target.checked)}
                      className="rounded border-violet-400 text-violet-700 focus:ring-violet-500"
                    />
                    <span>Custom fan &amp; tornado</span>
                  </label>
                )}
              </div>

              {/* Inline 422 Out-of-Scope Error */}
              {scopeErrorReasons.length > 0 && (
                <div
                  role="alert"
                  className="rounded-md border border-amber-400 bg-amber-50 p-3 text-xs text-amber-950"
                >
                  <div className="font-semibold">
                    Out-of-scope rate or override (keeping last valid chart):
                  </div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4">
                    {scopeErrorReasons.map((r, idx) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Proposed Rate Slider */}
              {policy && policy.proposed_rate_pct != null && (
                <div className="rounded-md border border-blue-200 bg-blue-50/40 p-3">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <label
                      htmlFor="slider-proposed-rate"
                      className="font-semibold text-slate-900"
                    >
                      Proposed CT main rate
                    </label>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-bold text-blue-800 tabular-nums">
                        {(proposedRateOverride ?? policy.proposed_rate_pct).toFixed(1)}%
                      </span>
                      {policy.baseline_rate_pct != null && (
                        <span className="text-[11px] text-slate-500">
                          (
                          {fmtPp(
                            (proposedRateOverride ?? policy.proposed_rate_pct) -
                              policy.baseline_rate_pct,
                            1,
                          )}
                          )
                        </span>
                      )}
                      {hasRateOverride && (
                        <button
                          type="button"
                          onClick={() =>
                            setProposedRateOverride(policy.proposed_rate_pct ?? null)
                          }
                          className="text-[11px] text-blue-700 hover:underline"
                        >
                          Reset
                        </button>
                      )}
                    </div>
                  </div>
                  <input
                    id="slider-proposed-rate"
                    type="range"
                    min={10}
                    max={40}
                    step={0.5}
                    value={proposedRateOverride ?? policy.proposed_rate_pct}
                    onChange={(e) => setProposedRateOverride(Number(e.target.value))}
                    className="mt-2 w-full accent-blue-600"
                  />
                  <div className="mt-1 flex justify-between text-[10px] text-slate-500">
                    <span>10%</span>
                    <span>Default: {policy.proposed_rate_pct}%</span>
                    <span>40%</span>
                  </div>
                </div>
              )}

              {/* Adjustable Assumption Sliders */}
              <div className="max-h-[540px] space-y-3 overflow-y-auto pr-1">
                {adjustableAssumptions.map((assumption) => {
                  const min = assumption.slider_min ?? assumption.low;
                  const max = assumption.slider_max ?? assumption.high;
                  const step =
                    assumption.slider_step ??
                    Number(((max - min) / 20 || 0.01).toFixed(3));
                  const currentVal = sliderValues[assumption.name] ?? assumption.value;
                  const isOverridden = Math.abs(currentVal - assumption.value) > 1e-6;
                  const defaultPct =
                    max > min
                      ? Math.min(
                          100,
                          Math.max(0, ((assumption.value - min) / (max - min)) * 100),
                        )
                      : 50;

                  return (
                    <div
                      key={assumption.name}
                      className={clsx(
                        'rounded-md border p-2.5 text-xs transition-colors',
                        isOverridden
                          ? 'border-violet-300 bg-violet-50/40'
                          : 'border-slate-200 bg-white',
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <label
                          htmlFor={`slider-${assumption.name}`}
                          className="font-medium text-slate-800"
                        >
                          {assumption.label}
                        </label>
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono font-semibold text-slate-900 tabular-nums">
                            {formatChartValue(currentVal, assumption.unit)}
                          </span>
                          {isOverridden && (
                            <button
                              type="button"
                              onClick={() =>
                                setSliderValues((prev) => ({
                                  ...prev,
                                  [assumption.name]: assumption.value,
                                }))
                              }
                              className="text-[11px] font-medium text-violet-700 hover:underline"
                            >
                              Reset
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="relative mt-2">
                        <input
                          id={`slider-${assumption.name}`}
                          type="range"
                          min={min}
                          max={max}
                          step={step}
                          value={currentVal}
                          onChange={(e) => {
                            const val = Number(e.target.value);
                            setSliderValues((prev) => ({
                              ...prev,
                              [assumption.name]: val,
                            }));
                          }}
                          className="w-full accent-violet-600"
                        />
                        {/* Default tick indicator */}
                        <span
                          aria-hidden="true"
                          title={`Default: ${assumption.value}`}
                          style={{ left: `${defaultPct}%` }}
                          className="pointer-events-none absolute -top-0.5 h-2 w-0.5 -translate-x-1/2 bg-slate-500"
                        />
                      </div>

                      <div className="mt-0.5 flex justify-between text-[10px] text-slate-500 tabular-nums">
                        <span>{min}</span>
                        <span>Default: {assumption.value}</span>
                        <span>{max}</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Full Re-run Button */}
              <div className="border-t border-slate-200 pt-3">
                <button
                  type="button"
                  disabled={!hasAnyOverride || createAnalysisMutation.isPending}
                  onClick={handleFullRerun}
                  className={clsx(
                    'flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors focus:ring-2 focus:ring-violet-500 focus:outline-none',
                    hasAnyOverride
                      ? 'bg-violet-700 text-white hover:bg-violet-800'
                      : 'cursor-not-allowed bg-slate-100 text-slate-400',
                  )}
                >
                  {createAnalysisMutation.isPending && <Spinner size="xs" />}
                  <span>Re-run full analysis with these assumptions</span>
                </button>
                <p className="mt-1 text-[11px] text-slate-500">
                  Reuses existing research findings (<code>reuse_research_from</code>) and
                  runs full verification and report generation.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default ScenariosTab;
