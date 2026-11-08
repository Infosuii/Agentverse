import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { VerificationTab } from './VerificationTab';
import type { Analysis } from '../../api/hooks';

function buildMockAnalysis(): Analysis {
  return {
    analysis_id: 'A-TEST-01',
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
    verification: {
      overall: 'approved_with_warnings',
      forecast_allowed: true,
      verified_at: '2026-11-07T12:00:30Z',
      summary: '1 check passed, 1 warning (placeholder source).',
      decline_reasons: [],
      critic_model: 'gemini-3-flash-preview',
      checks: [
        {
          check_id: 'ARITH-001',
          category: 'calculation',
          status: 'pass',
          severity: 'blocking',
          method: 'recompute',
          title: 'Scenario arithmetic verified',
          detail: 'Every ScenarioResult series independently recomputes within tolerance.',
          affected_ids: ['central.revenue_behavioural_gbp_bn.2027-28'],
        },
        {
          check_id: 'CITATION-002',
          category: 'citation',
          status: 'warn',
          severity: 'warning',
          method: 'rule',
          title: 'Placeholder source used',
          detail: 'Placeholder source S2 is used in baseline assumptions.',
          affected_ids: ['source:S2', 'precedent:CT-MAIN-2023', 'assumption:elasticity_rev'],
        },
      ],
    },
  };
}

describe('VerificationTab', () => {
  it('renders overall status, counts, critic model badge, and filters checks', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const analysis = buildMockAnalysis();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <VerificationTab analysis={analysis} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getAllByText(/Approved with Warnings/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Critic model: gemini-3-flash-preview/i)).toBeInTheDocument();
    expect(screen.getByText('ARITH-001')).toBeInTheDocument();
    expect(screen.getByText('CITATION-002')).toBeInTheDocument();
    expect(
      screen.getByText(/Governance, Risk Controls & Execution Boundaries/i),
    ).toBeInTheDocument();

    // Check deep links for affected_ids
    const sourceLink = screen.getByRole('link', { name: /source:S2/i });
    expect(sourceLink).toHaveAttribute('href', '/analyses/A-TEST-01/research');

    const precedentLink = screen.getByRole('link', { name: /precedent:CT-MAIN-2023/i });
    expect(precedentLink).toHaveAttribute('href', '/analyses/A-TEST-01/precedents');

    // Toggle failed/warnings only filter
    const toggleCheckbox = screen.getByRole('checkbox', { name: /Failed or warnings only/i });
    fireEvent.click(toggleCheckbox);

    expect(screen.queryByText('ARITH-001')).not.toBeInTheDocument();
    expect(screen.getByText('CITATION-002')).toBeInTheDocument();
  });

  it('displays decline reasons prominently when forecast is withheld', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const analysis = buildMockAnalysis();
    analysis.verification = {
      overall: 'forecast_withheld',
      forecast_allowed: false,
      verified_at: '2026-11-07T12:00:30Z',
      summary: 'Forecast withheld due to blocking scope check.',
      decline_reasons: ['Proposed rate change of +25pp exceeds supported +15pp bound.'],
      checks: [
        {
          check_id: 'SCOPE-001',
          category: 'scope',
          status: 'fail',
          severity: 'blocking',
          method: 'rule',
          title: 'Out of supported scope',
          detail: 'Policy is outside supported model scope.',
          affected_ids: [],
        },
      ],
    };

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <VerificationTab analysis={analysis} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      screen.getAllByText(/Proposed rate change of \+25pp exceeds supported \+15pp bound\./i).length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('SCOPE-001')).toBeInTheDocument();
  });
});
