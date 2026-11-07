import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { PrecedentsTab } from './PrecedentsTab';
import { apiClient } from '../../api/client';
import type { Analysis, PolicyChange } from '../../api/hooks';

beforeAll(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

vi.mock('../../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
    POST: vi.fn(),
  },
}));

const mockPrecedentsList: PolicyChange[] = [
  {
    change_id: 'CT-MAIN-2020-REVERSED',
    tax: 'corporation_tax',
    policy_type: 'corporation_tax_main_rate',
    announced_date: '2016-03-16',
    effective_date: '2020-04-01',
    fiscal_event: 'Budget 2020',
    old_rate_pct: 19,
    new_rate_pct: 17,
    other_measures: ['Finance Act 2016 planned cut cancelled in March 2020 Budget'],
    official_costings: [],
    observed_outcomes: [],
    macro_context: { period: '2020-21', real_gdp_growth_pct: -10.3 },
    notes: 'Reversed: legislated cut to 17% was cancelled before taking effect.',
    source_ids: ['S1'],
    is_placeholder: false,
  },
  {
    change_id: 'CT-MAIN-2023',
    tax: 'corporation_tax',
    policy_type: 'corporation_tax_main_rate',
    announced_date: '2021-03-03',
    effective_date: '2023-04-01',
    fiscal_event: 'Spring Budget 2021',
    old_rate_pct: 19,
    new_rate_pct: 25,
    other_measures: ['130% super-deduction (2021-23)', 'Full expensing from April 2023'],
    official_costings: [
      {
        fiscal_year: '2023-24',
        value_gbp_bn: 11.9,
        costing_body: 'HMT',
        fiscal_event: 'Spring Budget 2021 Table 2.1',
        includes_behavioural: true,
        source_id: 'S1',
      },
    ],
    observed_outcomes: [
      {
        metric: 'ct_receipts_gbp_bn',
        fiscal_year: '2022-23',
        value: 83.2,
        source_id: 'S1',
      },
      {
        metric: 'ct_receipts_gbp_bn',
        fiscal_year: '2023-24',
        value: 96.4,
        source_id: 'S1',
      },
      {
        metric: 'ct_receipts_pct_gdp',
        fiscal_year: '2023-24',
        value: 3.5,
        source_id: 'S1',
      },
    ],
    macro_context: {
      period: '2023-24',
      real_gdp_growth_pct: 0.4,
      cpi_inflation_pct: 7.3,
      bank_rate_pct: 5.0,
      unemployment_rate_pct: 4.1,
    },
    notes: 'Accompanied by full expensing capital allowances.',
    source_ids: ['S1'],
    is_placeholder: false,
  },
];

function buildMockAnalysis(): Analysis {
  return {
    analysis_id: 'A-PREC-01',
    created_at: '2026-11-07T12:00:00Z',
    updated_at: '2026-11-07T12:01:00Z',
    status: 'completed',
    mode: 'mock',
    request: { query: 'Raise CT from 25% to 28%' },
    policy: {
      policy_type: 'corporation_tax_main_rate',
      tax: 'corporation_tax',
      baseline_rate_pct: 25,
      proposed_rate_pct: 28,
      effective_date: '2027-04-01',
      horizon_years: 5,
      jurisdiction: 'UK',
      description: 'Raise the CT main rate from 25% to 28% from 1 April 2027',
      raw_query: 'Raise CT from 25% to 28%',
      parse_method: 'rules',
      parse_confidence: 1,
      ambiguities: [],
    },
    precedents: {
      dataset_version: 'v1',
      method: 'weighted_similarity',
      summary: 'April 2023 is the closest directional precedent (+6pp hike).',
      matches: [
        {
          change: mockPrecedentsList[1],
          similarity: 0.86,
          similarity_breakdown: {
            direction: 0.35,
            magnitude: 0.2,
            starting_rate: 0.16,
            recency: 0.15,
          },
          comparability_notes: [
            'Bundled with full expensing capital allowances.',
            'High inflation raised nominal profits independent of rate change.',
          ],
        },
      ],
    },
    sources: [
      {
        source_id: 'S1',
        title: 'Spring Budget 2021 Red Book',
        publisher: 'HM Treasury',
        publisher_type: 'hmt',
        reliability_tier: 1,
        url: 'https://www.gov.uk/budget-2021',
        access_method: 'curated_dataset',
        url_verified: true,
        is_placeholder: false,
      },
    ],
  };
}

describe('PrecedentsTab', () => {
  it('renders CT rate timeline excluding reversed proposals from implemented steps and shows matched cards', async () => {
    const mockedGet = vi.mocked(apiClient.GET);
    mockedGet.mockResolvedValue({
      data: mockPrecedentsList,
      error: undefined,
    } as never);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const analysis = buildMockAnalysis();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PrecedentsTab analysis={analysis} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Excluded from implemented timeline:.*CT-MAIN-2020-REVERSED/i),
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Spring Budget 2021/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('86%')).toBeInTheDocument();
    expect(
      screen.getByText('Bundled with full expensing capital allowances.'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Spring Budget 2021 Table 2.1/i)).toBeInTheDocument();
  });
});
