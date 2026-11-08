import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart as RechartsLineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useEvaluation } from '../../api/hooks';
import { BarCompare, ChartFrame } from '../../components/charts';
import {
  Badge,
  Card,
  EmptyState,
  EvidenceBadge,
  InlineError,
  ModeBadge,
  PlaceholderBadge,
  Skeleton,
  Stat,
  Table,
  Tooltip,
  VerificationBadge,
} from '../../components/ui';
import { fmtDate, fmtFiscalYear, fmtGbpBn, fmtPct } from '../../lib/format';
import { CHART_THEME, EVIDENCE_CLASS_COLORS, SCENARIO_COLORS } from '../../lib/theme';

const METHOD_COLORS: Record<string, string> = {
  observed: EVIDENCE_CLASS_COLORS.observed_outcome,
  jane_behavioural: SCENARIO_COLORS.central,
  jane_calibrated: SCENARIO_COLORS.optimistic,
  static: 'var(--chart-neutral)',
  naive_growth: 'var(--chart-neutral-muted)',
  linear_regression: 'var(--chart-warm)',
  lightgbm: SCENARIO_COLORS.custom,
};

const METHOD_SHORT_LABELS: Record<string, string> = {
  naive_growth: 'Naive growth',
  static: 'Static scaling',
  jane_behavioural: 'Jane behavioural (ε=0.20)',
  jane_calibrated: 'Jane calibrated (train ε)',
  linear_regression: 'Log-change OLS',
  lightgbm: 'LightGBM (ML)',
};

export function EvaluationPage() {
  const {
    data: evaluation,
    isLoading,
    isError,
    error,
    refetch,
  } = useEvaluation();

  const [splitFilter, setSplitFilter] = useState<'all' | 'test' | 'train'>('all');
  const [casesFilter, setCasesFilter] = useState<'changes' | 'all'>('changes');

  const testMethods = useMemo(
    () =>
      (evaluation?.methods ?? [])
        .filter((m) => m.split === 'test')
        .sort((a, b) => a.mae - b.mae),
    [evaluation?.methods],
  );

  const trainMethods = useMemo(
    () =>
      (evaluation?.methods ?? [])
        .filter((m) => m.split === 'train')
        .sort((a, b) => a.mae - b.mae),
    [evaluation?.methods],
  );

  const bestTestMethod = useMemo(
    () => (testMethods.length > 0 ? testMethods[0] : null),
    [testMethods],
  );

  const bestBaselineTest = useMemo(() => {
    const baselines = testMethods.filter((m) => m.is_baseline);
    return baselines.length > 0 ? baselines[0] : null;
  }, [testMethods]);

  const janeBehavTest = useMemo(
    () => testMethods.find((m) => m.method === 'jane_behavioural') ?? null,
    [testMethods],
  );

  const displayedMethods = useMemo(() => {
    const all = evaluation?.methods ?? [];
    const filtered =
      splitFilter === 'all' ? all : all.filter((m) => m.split === splitFilter);
    return [...filtered].sort((a, b) => {
      if (a.split !== b.split) return a.split === 'test' ? -1 : 1;
      return a.mae - b.mae;
    });
  }, [evaluation?.methods, splitFilter]);

  const highlightCases = useMemo(() => {
    const cases = evaluation?.cases ?? [];
    if (casesFilter === 'all') return cases;
    const changes = cases.filter((c) => c.case_id.startsWith('CT-MAIN-'));
    return changes.length > 0 ? changes : cases;
  }, [evaluation?.cases, casesFilter]);

  const chartData = useMemo(() => {
    const cases = evaluation?.cases ?? [];
    return cases.map((c) => ({
      fiscal_year: fmtFiscalYear(c.fiscal_year),
      split: c.split,
      case_id: c.case_id,
      observed: c.observed,
      jane_behavioural: c.predictions?.jane_behavioural ?? null,
      jane_calibrated: c.predictions?.jane_calibrated ?? null,
      static: c.predictions?.static ?? null,
      naive_growth: c.predictions?.naive_growth ?? null,
      linear_regression: c.predictions?.linear_regression ?? null,
      lightgbm: c.predictions?.lightgbm ?? null,
    }));
  }, [evaluation?.cases]);

  const firstTestYear = useMemo(() => {
    const found = chartData.find((d) => d.split === 'test');
    return found?.fiscal_year ?? null;
  }, [chartData]);

  const lastTestYear = useMemo(() => {
    const tests = chartData.filter((d) => d.split === 'test');
    return tests.length > 0 ? tests[tests.length - 1].fiscal_year : null;
  }, [chartData]);

  const maeBarData = useMemo(() => {
    const trainByMethod = new Map(trainMethods.map((m) => [m.method, m.mae]));
    return testMethods.map((m) => ({
      category: METHOD_SHORT_LABELS[m.method] ?? m.method,
      test_mae: m.mae,
      train_mae: trainByMethod.get(m.method) ?? null,
    }));
  }, [testMethods, trainMethods]);

  if (isLoading && !evaluation) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading evaluation report">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card><Skeleton lines={3} /></Card>
          <Card><Skeleton lines={3} /></Card>
          <Card><Skeleton lines={3} /></Card>
          <Card><Skeleton lines={3} /></Card>
        </div>
        <Card><Skeleton lines={6} /></Card>
        <Card><Skeleton lines={8} /></Card>
      </div>
    );
  }

  if (isError && !evaluation) {
    return (
      <InlineError
        title="Unable to load evaluation report"
        message={
          error instanceof Error
            ? error.message
            : 'Failed to fetch /api/evaluation from backend.'
        }
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  if (!evaluation || (evaluation.methods.length === 0 && evaluation.cases.length === 0)) {
    return (
      <EmptyState
        title="No evaluation results available yet"
        description="Run `python -m jane_avenue.evaluation.run` in the backend to generate historical backtest, ML experiment, research citation, and verifier fault-injection results."
      />
    );
  }

  const reval = evaluation.research_eval;
  const veval = evaluation.verification_eval;
  const ml = evaluation.ml_experiment;
  const verifierRate =
    veval && veval.n_fault_cases > 0
      ? (veval.detected / veval.n_fault_cases) * 100
      : null;

  return (
    <div className="space-y-6">
      {/* Page Header & Conditional Backtest Framing */}
      <header className="border-b border-border pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="slate">Evaluation &amp; Model Reliability</Badge>
          <Badge variant="blue">Dataset {evaluation.dataset_version}</Badge>
          <Badge variant="outline">Generated {fmtDate(evaluation.generated_at)}</Badge>
          {evaluation.is_placeholder && <PlaceholderBadge />}
        </div>
        <h1 className="mt-3 max-w-4xl font-display text-2xl leading-snug font-semibold text-foreground sm:text-3xl">
          Historical Backtesting, ML Experiment & Trust Evaluation
        </h1>
        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-muted-foreground">
          <strong className="font-semibold text-foreground">
            Conditional backtest methodology:
          </strong>{' '}
          {evaluation.target_description}
        </p>
        <p className="mt-2 font-mono text-xs text-muted-foreground">
          {evaluation.methods.length} method results · {evaluation.cases.length} backtest cases ·
          out-of-sample test split FY ≥ 2008
        </p>
      </header>

      {/* Prominent Placeholder Banner when is_placeholder is set */}
      {evaluation.is_placeholder && (
        <div
          role="alert"
          aria-label="Placeholder evaluation warning"
          className="rounded-lg border-2 border-amber-400/50 bg-amber-500/10 p-4 text-amber-200"
        >
          <div className="flex items-start gap-3">
            <span
              aria-hidden="true"
              className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-400 text-xs font-bold text-background"
            >
              ⚠
            </span>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-bold text-amber-200">
                  Placeholder Evaluation Data Active
                </h2>
                <PlaceholderBadge label="is_placeholder=true" />
              </div>
              <p className="text-xs leading-relaxed text-amber-200">
                One or more underlying series in this evaluation report come from unverified
                placeholder fixtures rather than curated official HMRC/OBR/ONS releases. Do not
                rely on these metrics as empirical validation until placeholder flags are cleared.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Headline Strip */}
      <section aria-label="Evaluation headline metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Central Engine Out-of-Sample MAE (jane_behavioural)"
          value={
            janeBehavTest
              ? fmtGbpBn(janeBehavTest.mae, 2)
              : bestTestMethod
                ? fmtGbpBn(bestTestMethod.mae, 2)
                : '—'
          }
          sublabel={
            janeBehavTest && bestBaselineTest
              ? `Jane behavioural vs best baseline (${bestBaselineTest.method}: ${fmtGbpBn(bestBaselineTest.mae, 2)})`
              : 'Out-of-sample FY ≥ 2008'
          }
          evidenceClass="model_scenario"
          isPlaceholder={evaluation.is_placeholder}
          provenance={
            <span>
              Out-of-sample test split (FY ≥ 2008, n={janeBehavTest?.n ?? bestTestMethod?.n ?? 0}).
              Central engine <code>jane_behavioural</code> MAPE:{' '}
              {janeBehavTest?.mape_pct != null ? fmtPct(janeBehavTest.mape_pct, 2) : '—'}.{' '}
              <code>jane_calibrated</code> (MAE{' '}
              {bestTestMethod ? fmtGbpBn(bestTestMethod.mae, 2) : '—'}) hits the 1.500 search bound
              on FY ≤ 2007 and is statistically indistinguishable on n=17.
            </span>
          }
        />

        <Stat
          label="ML Experiment Verdict (LightGBM)"
          value={
            ml ? (ml.adopted ? 'Adopted (Wins OOS)' : 'Rejected (Not Adopted)') : 'Not run'
          }
          sublabel={
            ml && ml.test_mae != null && ml.best_baseline_mae != null
              ? `Test MAE ${fmtGbpBn(ml.test_mae, 2)} vs baseline ${fmtGbpBn(ml.best_baseline_mae, 2)}`
              : 'Requires out-of-sample win to adopt'
          }
          evidenceClass="model_scenario"
          isPlaceholder={evaluation.is_placeholder}
          provenance={
            <span>
              {ml?.conclusion ??
                'LightGBM is adopted only if its out-of-sample test MAE beats the best simple baseline.'}
            </span>
          }
        />

        <Stat
          label="Research Citation & Quote Validity"
          value={
            reval?.citation_url_valid_rate != null
              ? fmtPct(reval.citation_url_valid_rate * 100, 1)
              : '—'
          }
          sublabel={
            reval
              ? `Fact accuracy ${reval.fact_accuracy != null ? fmtPct(reval.fact_accuracy * 100, 1) : '—'} · Quotes ${reval.quote_match_rate != null ? fmtPct(reval.quote_match_rate * 100, 1) : '—'} · ${reval.hallucinated_sources ?? 0} hallucinated`
              : 'Gold-set research evaluation'
          }
          evidenceClass="observed_outcome"
          provenance={
            <span>
              {reval?.notes ??
                'Evaluated on 15 factual UK Corporation Tax questions with verified official URLs.'}
            </span>
          }
        />

        <Stat
          label="Verifier Fault Detection Rate"
          value={
            veval && verifierRate != null
              ? `${veval.detected}/${veval.n_fault_cases} (${fmtPct(verifierRate, 1)})`
              : '—'
          }
          sublabel={
            veval
              ? `Clean-case false positives: ${veval.false_positives}/${veval.n_clean_cases}`
              : 'Fault-injection audit suite'
          }
          evidenceClass="observed_outcome"
          provenance={
            <span>
              {veval?.notes ??
                'Single-fault injection across scope, citation, evidence, calculation, data, causal, uncertainty, and report checks.'}
            </span>
          }
        />
      </section>

      {/* Predicted vs Observed Chart over Fiscal Years + Method MAE Comparison */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ChartFrame
            title="Predicted vs Observed UK Corporation Tax Receipts (R_{y+1})"
            caption="Conditional 2-year-ahead predictions (£bn nominal) across fiscal years. The shaded right-hand region marks the out-of-sample test split (FY ≥ 2008)."
            evidenceClass="observed_outcome"
            unitLabel="£bn"
            height={340}
            empty={chartData.length === 0}
            footer={
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <strong>Chronological split:</strong> Training on FY ≤ 2007 (unshaded); Out-of-sample testing on FY ≥ 2008 (shaded blue).
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <EvidenceBadge evidenceClass="observed_outcome" short />
                  <EvidenceBadge evidenceClass="model_scenario" short />
                </div>
              </div>
            }
          >
            <ResponsiveContainer width="100%" height="100%">
              <RechartsLineChart
                data={chartData}
                margin={{ top: 14, right: 20, left: 12, bottom: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
                {firstTestYear && lastTestYear && (
                  <ReferenceArea
                    x1={firstTestYear}
                    x2={lastTestYear}
                    fill="var(--ev-model)"
                    fillOpacity={0.08}
                    label={{
                      value: 'Out-of-sample test split (FY ≥ 2008)',
                      position: 'insideTopRight',
                      fontSize: 11,
                      fill: 'var(--ev-model-soft)',
                    }}
                  />
                )}
                {firstTestYear && (
                  <ReferenceLine
                    x={firstTestYear}
                    stroke="var(--ev-model)"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                  />
                )}
                <XAxis
                  dataKey="fiscal_year"
                  tick={{ fontSize: 11, fill: CHART_THEME.tick }}
                  label={{
                    value: 'Policy fiscal year (y)',
                    position: 'insideBottom',
                    offset: -10,
                    fontSize: 11,
                    fill: CHART_THEME.axisLabel,
                  }}
                />
                <YAxis
                  tickFormatter={(v: number) => fmtGbpBn(Number(v), 0)}
                  tick={{ fontSize: 11, fill: CHART_THEME.tick }}
                  width={68}
                />
                <RechartsTooltip
                  cursor={{ stroke: CHART_THEME.reference, strokeDasharray: '3 3' }}
                  formatter={(val: unknown, name: string) => [
                    fmtGbpBn(typeof val === 'number' ? val : Number(val), 2),
                    name,
                  ]}
                  labelFormatter={(label) => `Policy year: ${String(label)}`}
                  contentStyle={CHART_THEME.tooltip}
            labelStyle={CHART_THEME.tooltipLabel}
                />
                <Legend verticalAlign="top" height={28} wrapperStyle={CHART_THEME.legend} />
                <Line
                  type="monotone"
                  dataKey="observed"
                  name="Observed R_{y+1} (outturn)"
                  stroke={METHOD_COLORS.observed}
                  strokeWidth={2.75}
                  dot={{ r: 3, fill: METHOD_COLORS.observed }}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="jane_behavioural"
                  name="Jane behavioural (central ε=0.20)"
                  stroke={METHOD_COLORS.jane_behavioural}
                  strokeWidth={2.25}
                  dot={{ r: 2.5, fill: METHOD_COLORS.jane_behavioural }}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="jane_calibrated"
                  name="Jane calibrated (train ε)"
                  stroke={METHOD_COLORS.jane_calibrated}
                  strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="static"
                  name="Static baseline"
                  stroke={METHOD_COLORS.static}
                  strokeWidth={1.75}
                  strokeDasharray="3 3"
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="naive_growth"
                  name="Naive profit-growth baseline"
                  stroke={METHOD_COLORS.naive_growth}
                  strokeWidth={1.5}
                  strokeDasharray="2 2"
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="linear_regression"
                  name="Log-change OLS baseline"
                  stroke={METHOD_COLORS.linear_regression}
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={false}
                  isAnimationActive={false}
                />
                {ml && (
                  <Line
                    type="monotone"
                    dataKey="lightgbm"
                    name="LightGBM (ML experiment)"
                    stroke={METHOD_COLORS.lightgbm}
                    strokeWidth={1.75}
                    strokeDasharray="6 3"
                    dot={false}
                    isAnimationActive={false}
                  />
                )}
              </RechartsLineChart>
            </ResponsiveContainer>
          </ChartFrame>
        </div>

        <div className="lg:col-span-1">
          <BarCompare
            title="Test vs Train MAE by Method"
            caption="Mean absolute error (£bn, lower is better) on out-of-sample test years (FY ≥ 2008) vs training years (FY ≤ 2007)."
            data={maeBarData}
            series={[
              {
                id: 'test_mae',
                label: 'Out-of-sample Test MAE (£bn)',
                color: SCENARIO_COLORS.central,
              },
              {
                id: 'train_mae',
                label: 'In-sample Train MAE (£bn)',
                color: CHART_THEME.neutralMuted,
              },
            ]}
            unit="£bn"
            xLabel="Method"
            height={340}
            showZeroReference={false}
            footer="Tree & OLS models fit training noise or era-specific trends; structural elasticity generalises better out of sample."
          />
        </div>
      </div>

      {/* Methods Comparison Table */}
      <Card
        title="Backtest Methods Comparison Table"
        subtitle="Conditional prediction accuracy per chronological split. Baselines are explicitly marked; headline judgement uses the out-of-sample test split (FY ≥ 2008)."
        actions={
          <div className="flex items-center gap-1" role="group" aria-label="Filter split">
            {(['all', 'test', 'train'] as const).map((sp) => (
              <button
                key={sp}
                type="button"
                onClick={() => setSplitFilter(sp)}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                  splitFilter === sp
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-card text-muted-foreground hover:bg-accent/60'
                }`}
              >
                {sp === 'all' ? 'All splits' : sp === 'test' ? 'Test (FY ≥ 2008)' : 'Train (FY ≤ 2007)'}
              </button>
            ))}
          </div>
        }
      >
        <Table aria-label="Backtest methods table">
          <thead className="bg-muted/40 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            <tr>
              <th className="px-3 py-2.5">Split</th>
              <th className="px-3 py-2.5">Method</th>
              <th className="px-3 py-2.5">Role</th>
              <th className="px-3 py-2.5 text-right">n</th>
              <th className="px-3 py-2.5 text-right">MAE (£bn)</th>
              <th className="px-3 py-2.5 text-right">RMSE (£bn)</th>
              <th className="px-3 py-2.5 text-right">MAPE (%)</th>
              <th className="px-3 py-2.5 text-right">Policy-Effect Dir. Accuracy</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-xs">
            {displayedMethods.map((m) => {
              const isBestTest =
                m.split === 'test' && bestTestMethod?.method === m.method;
              return (
                <tr
                  key={`${m.split}-${m.method}`}
                  className={isBestTest ? 'bg-primary/5' : 'hover:bg-muted/30'}
                >
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <Badge variant={m.split === 'test' ? 'blue' : 'slate'}>
                      {m.split === 'test' ? 'Test (FY ≥ 2008)' : 'Train (FY ≤ 2007)'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="font-semibold text-foreground">
                      {m.label}{' '}
                      <code className="rounded bg-secondary px-1 py-0.5 font-mono text-[11px] text-foreground/85">
                        {m.method}
                      </code>
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">{m.description}</div>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <div className="flex flex-wrap items-center gap-1">
                      {m.is_baseline ? (
                        <Badge variant="amber">Baseline</Badge>
                      ) : (
                        <Badge variant="green">Candidate model</Badge>
                      )}
                      <EvidenceBadge evidenceClass="model_scenario" short />
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-foreground/85">
                    {m.n}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-foreground">
                    <Tooltip
                      content={`Mean absolute error across n=${m.n} ${m.split}-split fiscal years (${m.label}).`}
                    >
                      <span className="cursor-help underline decoration-muted-foreground/50 decoration-dotted underline-offset-2">
                        {fmtGbpBn(m.mae, 2)}
                      </span>
                    </Tooltip>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-foreground/85">
                    <Tooltip
                      content={`Root mean squared error across n=${m.n} ${m.split}-split fiscal years.`}
                    >
                      <span className="cursor-help underline decoration-muted-foreground/50 decoration-dotted underline-offset-2">
                        {fmtGbpBn(m.rmse, 2)}
                      </span>
                    </Tooltip>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-foreground/85">
                    {m.mape_pct != null ? fmtPct(m.mape_pct, 2) : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-foreground/85">
                    {m.directional_accuracy != null
                      ? `${fmtPct(m.directional_accuracy * 100, 1)}${m.method === 'naive_growth' ? '*' : ''}`
                      : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
          * Policy-effect directional accuracy compares the sign of each method&apos;s predicted
          rate effect (method minus <code>naive_growth</code>) against the observed excess movement
          on rate-change years. For <code>naive_growth</code>, directional accuracy is 0.0% by
          construction because it predicts zero policy rate effect (ΔR<sup>rate</sup> = 0). On{' '}
          <code>n = 17</code> test years, <code>jane_behavioural</code> (central prior ε = 0.20)
          and <code>jane_calibrated</code> (which hits the 1.500 upper search bound on FY ≤ 2007)
          are statistically indistinguishable.
        </p>
      </Card>

      {/* Highlight Cases Table for Statutory Rate-Change Years */}
      <Card
        title="Historical Rate-Change Cases: Observed Outcome vs Official Costing vs Model Predictions"
        subtitle="Each number carries its explicit evidence-class badge. Ex-ante official costings (HMT/OBR policy-measure deltas ΔR in £bn under contemporary Budget baselines) are shown as a reference column only and are never treated as total-receipts ground truth."
        actions={
          <div className="flex items-center gap-1" role="group" aria-label="Filter cases">
            <button
              type="button"
              onClick={() => setCasesFilter('changes')}
              className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                casesFilter === 'changes'
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:bg-accent/60'
              }`}
            >
              Rate-change years ({evaluation.cases.filter((c) => c.case_id.startsWith('CT-MAIN-')).length})
            </button>
            <button
              type="button"
              onClick={() => setCasesFilter('all')}
              className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                casesFilter === 'all'
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:bg-accent/60'
              }`}
            >
              All panel years ({evaluation.cases.length})
            </button>
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Column evidence classes:</span>
          <EvidenceBadge evidenceClass="observed_outcome" />
          <span>= Outturn CT receipts R_{'{y+1}'} (£bn)</span>
          <span className="text-muted-foreground">|</span>
          <EvidenceBadge evidenceClass="official_costing" />
          <span>= Ex-ante HMT/OBR Budget costing ΔR (£bn, reference only)</span>
          <span className="text-muted-foreground">|</span>
          <EvidenceBadge evidenceClass="model_scenario" />
          <span>= Conditional backtest prediction R̂_{'{y+1}'} (£bn)</span>
        </div>

        <Table aria-label="Rate-change backtest cases table">
          <thead className="bg-muted/40 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            <tr>
              <th className="px-3 py-2.5">Case / Event</th>
              <th className="px-3 py-2.5">Policy FY</th>
              <th className="px-3 py-2.5">Split</th>
              <th className="px-3 py-2.5 text-right">
                <div className="flex flex-col items-end gap-0.5">
                  <span>Observed R_{'{y+1}'}</span>
                  <EvidenceBadge evidenceClass="observed_outcome" short />
                </div>
              </th>
              <th className="px-3 py-2.5 text-right">
                <div className="flex flex-col items-end gap-0.5">
                  <span>Official Costing (ΔR ref)</span>
                  <EvidenceBadge evidenceClass="official_costing" short />
                </div>
              </th>
              <th className="px-3 py-2.5 text-right">
                <div className="flex flex-col items-end gap-0.5">
                  <span>Naive Growth</span>
                  <EvidenceBadge evidenceClass="model_scenario" short />
                </div>
              </th>
              <th className="px-3 py-2.5 text-right">
                <div className="flex flex-col items-end gap-0.5">
                  <span>Static</span>
                  <EvidenceBadge evidenceClass="model_scenario" short />
                </div>
              </th>
              <th className="px-3 py-2.5 text-right">
                <div className="flex flex-col items-end gap-0.5">
                  <span>Jane Behavioural</span>
                  <EvidenceBadge evidenceClass="model_scenario" short />
                </div>
              </th>
              <th className="px-3 py-2.5 text-right">
                <div className="flex flex-col items-end gap-0.5">
                  <span>Jane Calibrated</span>
                  <EvidenceBadge evidenceClass="model_scenario" short />
                </div>
              </th>
              <th className="px-3 py-2.5 text-right">
                <div className="flex flex-col items-end gap-0.5">
                  <span>Log OLS</span>
                  <EvidenceBadge evidenceClass="model_scenario" short />
                </div>
              </th>
              {ml && (
                <th className="px-3 py-2.5 text-right">
                  <div className="flex flex-col items-end gap-0.5">
                    <span>LightGBM</span>
                    <EvidenceBadge evidenceClass="model_scenario" short />
                  </div>
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-xs">
            {highlightCases.map((c) => {
              const p = c.predictions ?? {};
              return (
                <tr key={c.case_id} className="hover:bg-muted/30">
                  <td className="px-3 py-2.5">
                    <Tooltip content={c.notes || c.target}>
                      <span className="cursor-help font-mono font-semibold text-foreground underline decoration-muted-foreground/50 decoration-dotted underline-offset-2">
                        {c.case_id}
                      </span>
                    </Tooltip>
                    <div className="text-[11px] text-muted-foreground">{c.target}</div>
                  </td>
                  <td className="px-3 py-2.5 font-mono whitespace-nowrap text-foreground/85">
                    {fmtFiscalYear(c.fiscal_year)}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <Badge variant={c.split === 'test' ? 'blue' : 'slate'}>
                      {c.split}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-foreground">
                    <Tooltip
                      content={`Observed outturn UK CT receipts for ${c.target} (curated HMRC/OBR dataset).`}
                    >
                      <span className="cursor-help">{fmtGbpBn(c.observed, 2)}</span>
                    </Tooltip>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-violet-300">
                    {c.official_costing_gbp_bn != null ? (
                      <Tooltip content="Ex-ante HMT/OBR Budget policy costing (revenue change ΔR vs Budget baseline, not total receipts).">
                        <span className="cursor-help font-medium underline decoration-violet-400/50 decoration-dotted underline-offset-2">
                          {c.official_costing_gbp_bn > 0
                            ? `+${fmtGbpBn(c.official_costing_gbp_bn, 2)}`
                            : fmtGbpBn(c.official_costing_gbp_bn, 2)}
                        </span>
                      </Tooltip>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-muted-foreground">
                    {fmtGbpBn(p.naive_growth, 2)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-foreground/85">
                    {fmtGbpBn(p.static, 2)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-blue-300">
                    <Tooltip content={c.notes || 'Jane Avenue behavioural engine prediction'}>
                      <span className="cursor-help underline decoration-blue-400/50 decoration-dotted underline-offset-2">
                        {fmtGbpBn(p.jane_behavioural, 2)}
                      </span>
                    </Tooltip>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-emerald-300">
                    {fmtGbpBn(p.jane_calibrated, 2)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-muted-foreground">
                    {fmtGbpBn(p.linear_regression, 2)}
                  </td>
                  {ml && (
                    <td className="px-3 py-2.5 text-right font-mono tabular-nums text-purple-300">
                      {fmtGbpBn(p.lightgbm, 2)}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </Table>
      </Card>

      {/* ML Experiment, Research Eval, and Verifier Eval Cards */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ML Experiment Card */}
        <Card
          title="Out-of-Sample ML Experiment (LightGBM)"
          subtitle="Product rule: ML is adopted only if it beats the best simple baseline out of sample."
          actions={
            ml ? (
              <Badge variant={ml.adopted ? 'green' : 'amber'}>
                {ml.adopted ? 'ADOPTED' : 'NOT ADOPTED'}
              </Badge>
            ) : null
          }
        >
          {ml ? (
            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2.5 rounded-md border border-border bg-muted/40 p-3">
                <div>
                  <div className="text-[11px] text-muted-foreground">LightGBM Test MAE</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-foreground">
                    {fmtGbpBn(ml.test_mae, 2)}
                  </div>
                  <div className="text-[10px] text-muted-foreground">{ml.test_period}</div>
                </div>
                <div>
                  <div className="text-[11px] text-muted-foreground">
                    Best Baseline ({ml.best_baseline})
                  </div>
                  <div className="mt-0.5 font-mono text-base font-bold text-emerald-300">
                    {fmtGbpBn(ml.best_baseline_mae, 2)}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    In-sample Train MAE:{' '}
                    {fmtGbpBn(
                      trainMethods.find((m) => m.method === 'lightgbm')?.mae ?? null,
                      2,
                    )}
                  </div>
                </div>
              </div>

              <div>
                <span className="font-semibold text-foreground/85">Model spec: </span>
                <code className="break-all rounded bg-secondary px-1 py-0.5 font-mono text-[11px] text-foreground/85">
                  {ml.model}
                </code>
              </div>

              <div>
                <span className="font-semibold text-foreground/85">Features: </span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {ml.features.map((f) => (
                    <Badge key={f} variant="slate">
                      {f}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-amber-400/25 bg-amber-500/10 p-3 leading-relaxed text-foreground">
                <strong className="font-semibold text-amber-200">Verdict & reasoning: </strong>
                {ml.conclusion}
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">ML experiment has not been run yet.</p>
          )}
        </Card>

        {/* Research Evaluation Card */}
        <Card
          title="Research Agent Citation & Fact Accuracy"
          subtitle="Evaluated on the 15-question UK CT gold set with verified official URLs."
          actions={reval ? <ModeBadge mode={reval.mode} /> : null}
        >
          {reval ? (
            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2.5 rounded-md border border-border bg-muted/40 p-3">
                <div>
                  <div className="text-[11px] text-muted-foreground">Fact Accuracy (n={reval.n_questions})</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-foreground">
                    {reval.fact_accuracy != null ? fmtPct(reval.fact_accuracy * 100, 1) : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-muted-foreground">Citation URL Validity</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-emerald-300">
                    {reval.citation_url_valid_rate != null
                      ? fmtPct(reval.citation_url_valid_rate * 100, 1)
                      : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-muted-foreground">Quote Match Rate</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-foreground">
                    {reval.quote_match_rate != null
                      ? fmtPct(reval.quote_match_rate * 100, 1)
                      : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-muted-foreground">Hallucinated Sources</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-emerald-300">
                    {reval.hallucinated_sources ?? 0}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between rounded border border-border px-3 py-2">
                <span className="font-medium text-foreground/85">
                  Official Tier-1 Source Share (HMRC/OBR/HMT/ONS)
                </span>
                <span className="font-mono font-bold text-primary">
                  {reval.official_source_share != null
                    ? fmtPct(reval.official_source_share * 100, 1)
                    : '—'}
                </span>
              </div>

              {reval.notes && (
                <p className="leading-relaxed text-muted-foreground">{reval.notes}</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Research evaluation has not been run yet.</p>
          )}
        </Card>

        {/* Verifier Evaluation Card */}
        <Card
          title="Independent Verifier Fault-Injection Suite"
          subtitle="Single-fault injection against the golden-path analysis."
          actions={
            veval ? (
              <VerificationBadge
                status={
                  veval.detected === veval.n_fault_cases && veval.false_positives === 0
                    ? 'pass'
                    : 'warn'
                }
              />
            ) : null
          }
        >
          {veval ? (
            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2.5 rounded-md border border-border bg-muted/40 p-3">
                <div>
                  <div className="text-[11px] text-muted-foreground">Faults Detected</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-emerald-300">
                    {veval.detected}/{veval.n_fault_cases} (
                    {verifierRate != null ? fmtPct(verifierRate, 1) : '—'})
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-muted-foreground">Clean-Case False Positives</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-foreground">
                    {veval.false_positives}/{veval.n_clean_cases}
                  </div>
                </div>
              </div>

              <div className="max-h-44 overflow-y-auto rounded border border-border divide-y divide-border/60">
                {Object.entries(veval.by_fault).map(([faultName, detected]) => (
                  <div
                    key={faultName}
                    className="flex items-center justify-between px-2.5 py-1.5"
                  >
                    <code className="font-mono text-[11px] text-foreground">{faultName}</code>
                    <VerificationBadge status={detected ? 'pass' : 'fail'} />
                  </div>
                ))}
              </div>

              {veval.notes && (
                <p className="leading-relaxed text-muted-foreground">{veval.notes}</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Verifier evaluation has not been run yet.</p>
          )}
        </Card>
      </div>

      {/* Prominent Limitations & Caveats List */}
      <Card
        title="Methodological Limitations & Honest Caveats"
        subtitle="Explicit econometric, historical, and data limitations that analysts must weigh alongside model outputs."
      >
        <ul className="space-y-2.5 text-xs leading-relaxed text-foreground/85">
          {(evaluation.limitations ?? []).map((lim, idx) => (
            <li
              key={idx}
              className="flex items-start gap-2.5 rounded-md border border-border bg-muted/30 p-3"
            >
              <span
                aria-hidden="true"
                className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-[11px] font-bold text-foreground/85"
              >
                {idx + 1}
              </span>
              <span>{lim}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

export default EvaluationPage;
