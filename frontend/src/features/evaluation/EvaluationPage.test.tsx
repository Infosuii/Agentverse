import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import type { EvaluationReport } from '../../api/hooks';
import { EvaluationPage } from './EvaluationPage';

function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

const mockUseEvaluation = vi.fn();

vi.mock('../../api/hooks', async () => {
  const actual = await vi.importActual<typeof import('../../api/hooks')>('../../api/hooks');
  return {
    ...actual,
    useEvaluation: () => mockUseEvaluation(),
  };
});

const SAMPLE_REPORT: EvaluationReport = {
  generated_at: '2026-11-07T19:00:00Z',
  dataset_version: '10bb93bda87c',
  target_description:
    'Conditional backtest of UK Corporation Tax receipts R_{y+1} (£bn nominal) predicted from information at fiscal year y-1, conditioning on realised 2-year profit growth (pnfc_gos).',
  methods: [
    {
      method: 'jane_calibrated',
      label: 'Jane Avenue behavioural engine (train-calibrated ε; bound hit)',
      description:
        'Same structural revenue equation with elasticity ε reached the search bound of 1.500 on [0.0, 1.5] (corner solution; not identified on FY ≤ 2007 training data).',
      split: 'test',
      n: 17,
      mae: 5.29,
      rmse: 6.68,
      mape_pct: 9.43,
      directional_accuracy: 0.5455,
      is_baseline: false,
    },
    {
      method: 'jane_behavioural',
      label: 'Jane Avenue behavioural engine (central prior ε)',
      description: 'Engine static + behavioural revenue equation with central ε = 0.20.',
      split: 'test',
      n: 17,
      mae: 5.48,
      rmse: 7.01,
      mape_pct: 9.29,
      directional_accuracy: 0.5455,
      is_baseline: false,
    },
    {
      method: 'static',
      label: 'Static tax-rate scaling baseline',
      description: 'Proportional scaling with zero behavioural response.',
      split: 'test',
      n: 17,
      mae: 5.65,
      rmse: 7.19,
      mape_pct: 9.46,
      directional_accuracy: 0.5455,
      is_baseline: true,
    },
    {
      method: 'lightgbm',
      label: 'LightGBM gradient-boosted trees (ML experiment)',
      description: 'Shallow regularised LightGBM regressor.',
      split: 'test',
      n: 17,
      mae: 6.33,
      rmse: 8.0,
      mape_pct: 12.28,
      directional_accuracy: 0.6364,
      is_baseline: false,
    },
    {
      method: 'naive_growth',
      label: 'Naive profit-growth baseline',
      description: 'Assumes receipts grow one-for-one with profit proxy.',
      split: 'test',
      n: 17,
      mae: 6.56,
      rmse: 8.25,
      mape_pct: 11.09,
      directional_accuracy: 0.0,
      is_baseline: true,
    },
    {
      method: 'jane_behavioural',
      label: 'Jane Avenue behavioural engine (central prior ε)',
      description: 'Engine static + behavioural revenue equation with central ε = 0.20.',
      split: 'train',
      n: 25,
      mae: 4.13,
      rmse: 4.9,
      mape_pct: 17.44,
      directional_accuracy: 0.3333,
      is_baseline: false,
    },
  ],
  cases: [
    {
      case_id: 'CT-MAIN-1984',
      fiscal_year: '1984-85',
      split: 'train',
      target: 'ct_receipts_gbp_bn (1985-86)',
      observed: 10.71,
      official_costing_gbp_bn: null,
      predictions: {
        naive_growth: 8.4,
        static: 6.97,
        jane_behavioural: 7.18,
        jane_calibrated: 8.77,
        linear_regression: 11.02,
        lightgbm: 7.96,
      },
      notes: '1984 rate cut case.',
    },
    {
      case_id: 'FY-2019-20',
      fiscal_year: '2019-20',
      split: 'test',
      target: 'ct_receipts_gbp_bn (2020-21)',
      observed: 52.1,
      official_costing_gbp_bn: null,
      predictions: {
        naive_growth: 55.0,
        static: 55.0,
        jane_behavioural: 55.0,
        jane_calibrated: 55.0,
        linear_regression: 56.2,
        lightgbm: 57.1,
      },
      notes: 'Non-rate-change fiscal year.',
    },
    {
      case_id: 'CT-MAIN-2023',
      fiscal_year: '2023-24',
      split: 'test',
      target: 'ct_receipts_gbp_bn (2024-25)',
      observed: 95.7,
      official_costing_gbp_bn: 16.25,
      predictions: {
        naive_growth: 84.83,
        static: 107.6,
        jane_behavioural: 106.15,
        jane_calibrated: 97.26,
        linear_regression: 72.86,
        lightgbm: 89.64,
      },
      notes: 'April 2023 main rate increase from 19% to 25%.',
    },
  ],
  ml_experiment: {
    model: 'LightGBMRegressor(max_depth=2, num_leaves=3, seed=42)',
    features: [
      'rate_change_pp',
      'starting_rate_pct',
      'profit_growth_pct',
      'bank_rate_pct',
      'real_gdp_growth_pct',
      'lagged_receipts_pct_gdp',
    ],
    train_period: 'FY1983-84–FY2007-08',
    test_period: 'FY2008-09–FY2024-25',
    test_mae: 6.33,
    best_baseline: 'static',
    best_baseline_mae: 5.65,
    adopted: false,
    conclusion:
      'NOT ADOPTED: LightGBM achieved an out-of-sample test MAE of £6.33bn vs static baseline £5.65bn.',
  },
  research_eval: {
    n_questions: 15,
    fact_accuracy: 1.0,
    citation_url_valid_rate: 1.0,
    quote_match_rate: 1.0,
    hallucinated_sources: 0,
    official_source_share: 1.0,
    mode: 'cached',
    notes: 'Evaluated 15 gold factual UK CT questions.',
  },
  verification_eval: {
    n_fault_cases: 18,
    detected: 18,
    n_clean_cases: 1,
    false_positives: 0,
    by_fault: {
      wrong_static_sign: true,
      unverified_quote_marked_verified: true,
    },
    notes: 'Clean case: approved; flagged checks: none.',
  },
  limitations: [
    'Conditional backtest design isolates tax-rate response from macroeconomic forecast error.',
    'Small sample of 16 statutory rate changes since FY1982.',
  ],
  is_placeholder: false,
};

describe('EvaluationPage', () => {
  it('renders headline strip, methods table, highlight cases with EvidenceBadges, ML card, research/verifier cards, and limitations', () => {
    mockUseEvaluation.mockReturnValue({
      data: SAMPLE_REPORT,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    renderWithQueryClient(<EvaluationPage />);

    // Headline metrics
    expect(
      screen.getByText('Central Engine Out-of-Sample MAE (jane_behavioural)'),
    ).toBeInTheDocument();
    expect(screen.getByText('Rejected (Not Adopted)')).toBeInTheDocument();
    expect(screen.getAllByText('18/18 (100.0%)').length).toBeGreaterThanOrEqual(1);

    // Methods table & corner-solution note
    expect(
      screen.getByText('Backtest Methods Comparison Table'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/corner solution; not identified on FY ≤ 2007 training data/i),
    ).toBeInTheDocument();

    // Cases table & filtering
    expect(screen.getByText('CT-MAIN-2023')).toBeInTheDocument();
    expect(screen.queryByText('FY-2019-20')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /All panel years/i }));
    expect(screen.getByText('FY-2019-20')).toBeInTheDocument();

    // ML card
    expect(screen.getByText('NOT ADOPTED')).toBeInTheDocument();
    expect(screen.getByText('rate_change_pp')).toBeInTheDocument();

    // Research & verifier cards
    expect(screen.getByText('Hallucinated Sources')).toBeInTheDocument();
    expect(screen.getByText('Clean-Case False Positives')).toBeInTheDocument();
    expect(screen.getByText('wrong_static_sign')).toBeInTheDocument();

    // Limitations section
    expect(
      screen.getByText('Methodological Limitations & Honest Caveats'),
    ).toBeInTheDocument();
  });

  it('displays a prominent warning banner when is_placeholder is true', () => {
    mockUseEvaluation.mockReturnValue({
      data: { ...SAMPLE_REPORT, is_placeholder: true },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    renderWithQueryClient(<EvaluationPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Placeholder Evaluation Data Active')).toBeInTheDocument();
  });
});
