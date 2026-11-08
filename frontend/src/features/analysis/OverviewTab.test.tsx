import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeAll, describe, expect, it } from 'vitest';
import { OverviewTab } from './OverviewTab';
import type { Analysis } from '../../api/hooks';

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

const SAMPLE_ANALYSIS: Analysis = {
  analysis_id: 'ana-1',
  created_at: '2026-11-07T16:45:00Z',
  updated_at: '2026-11-07T16:46:00Z',
  status: 'completed',
  mode: 'mock',
  request: {
    query: 'What would happen if the UK increased corporation tax from 25% to 28%?',
  },
  policy: {
    policy_type: 'corporation_tax_main_rate',
    tax: 'corporation_tax',
    baseline_rate_pct: 25,
    proposed_rate_pct: 28,
    effective_date: '2027-04-01',
    horizon_years: 2,
    jurisdiction: 'UK',
    description: 'Raise the CT main rate from 25% to 28% from 1 April 2027',
    raw_query: 'What would happen if the UK increased corporation tax from 25% to 28%?',
    parse_method: 'rules',
    parse_confidence: 1,
    ambiguities: [],
  },
  scope: {
    status: 'supported',
    forecast_allowed: true,
    reasons: [],
    warnings: [],
  },
  simulation: {
    policy: {
      policy_type: 'corporation_tax_main_rate',
      tax: 'corporation_tax',
      baseline_rate_pct: 25,
      proposed_rate_pct: 28,
      effective_date: '2027-04-01',
      horizon_years: 2,
      jurisdiction: 'UK',
      description: 'Raise the CT main rate from 25% to 28% from 1 April 2027',
      raw_query: '',
      parse_method: 'rules',
      parse_confidence: 1,
    },
    baseline_vintage: 'OBR EFO March 2026',
    assumptions: [],
    scenarios: [
      {
        scenario: {
          name: 'central',
          label: 'Central',
          description: 'Central parameters',
          parameter_values: {},
        },
        result: {
          model_version: '1.0.0',
          policy: {
            policy_type: 'corporation_tax_main_rate',
            horizon_years: 2,
            jurisdiction: 'UK',
            description: '',
            raw_query: '',
            parse_method: 'rules',
            parse_confidence: 1,
          },
          scenario: 'central',
          baseline_vintage: 'OBR EFO March 2026',
          fiscal_years: ['2027-28', '2028-29'],
          metrics: [
            {
              metric: 'revenue_behavioural_gbp_bn',
              label: 'Behavioural revenue',
              unit: '£bn',
              confidence: 'medium',
              note: '',
              values: [
                { fiscal_year: '2027-28', value: 3.1 },
                { fiscal_year: '2028-29', value: 5.4 },
              ],
            },
            {
              metric: 'business_investment_pct',
              label: 'Business investment',
              unit: '%',
              confidence: 'medium',
              note: '',
              values: [
                { fiscal_year: '2027-28', value: -0.2 },
                { fiscal_year: '2028-29', value: -0.45 },
              ],
            },
            {
              metric: 'gdp_level_pct',
              label: 'GDP level',
              unit: '%',
              confidence: 'low',
              note: '',
              values: [
                { fiscal_year: '2027-28', value: -0.03 },
                { fiscal_year: '2028-29', value: -0.08 },
              ],
            },
          ],
          calc_trace: [],
          parameters_used: {},
        },
      },
    ],
    monte_carlo: {
      n_draws: 2000,
      seed: 42,
      sampled_parameters: [],
      interval_kind: 'assumption_range',
      interval_note: 'assumption-driven ranges',
      histograms: [],
      distributions: [
        {
          metric: 'revenue_behavioural_gbp_bn',
          unit: '£bn',
          bands: [
            {
              fiscal_year: '2027-28',
              p5: 2.1,
              p10: 2.3,
              p25: 2.7,
              p50: 3.1,
              p75: 3.5,
              p90: 3.8,
              p95: 4.0,
              mean: 3.1,
            },
            {
              fiscal_year: '2028-29',
              p5: 3.9,
              p10: 4.2,
              p25: 4.8,
              p50: 5.4,
              p75: 6.0,
              p90: 6.4,
              p95: 6.8,
              mean: 5.4,
            },
          ],
        },
      ],
    },
  },
  verification: {
    overall: 'approved',
    forecast_allowed: true,
    checks: [],
    decline_reasons: [],
    summary: 'All checks passed',
    verified_at: '2026-11-07T16:46:00Z',
  },
};

describe('OverviewTab', () => {
  it('renders central scenario stat tiles with MC p5-p95 ranges and low-confidence labels', () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <OverviewTab analysis={SAMPLE_ANALYSIS} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText('£3.1bn')).toBeInTheDocument();
    expect(screen.getByText('£5.4bn')).toBeInTheDocument();
    expect(screen.getByText('−0.45%')).toBeInTheDocument();
    expect(screen.getByText('−0.08%')).toBeInTheDocument();
    expect(screen.getByText('Low confidence (indicative)')).toBeInTheDocument();
  });

  it('shows WithheldBanner and hides numbers when verification.forecast_allowed is false', () => {
    const withheldAnalysis: Analysis = {
      ...SAMPLE_ANALYSIS,
      verification: {
        overall: 'forecast_withheld',
        forecast_allowed: false,
        checks: [],
        decline_reasons: ['SCOPE-001: Rate change of +20pp exceeds validated bounds'],
        summary: 'Forecast withheld',
        verified_at: '2026-11-07T16:46:00Z',
      },
    };

    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <OverviewTab analysis={withheldAnalysis} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      screen.getByRole('alert', { name: /Quantitative forecast withheld/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText('£3.1bn')).not.toBeInTheDocument();
    expect(screen.queryByText('£5.4bn')).not.toBeInTheDocument();
  });
});
