import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { ResearchTab } from './ResearchTab';
import type { Analysis } from '../../api/hooks';

const RESEARCH_ANALYSIS: Analysis = {
  analysis_id: 'ana-res-1',
  created_at: '2026-11-07T16:45:00Z',
  updated_at: '2026-11-07T16:46:00Z',
  status: 'completed',
  mode: 'mock',
  request: {
    query: 'What would happen if the UK increased corporation tax from 25% to 28%?',
  },
  sources: [
    {
      source_id: 'S1',
      title: 'OBR Economic and Fiscal Outlook',
      url: 'https://obr.uk/efo',
      publisher: 'OBR',
      publisher_type: 'obr',
      access_method: 'url_fetch',
      reliability_tier: 1,
      url_verified: true,
      is_placeholder: false,
    },
  ],
  research: {
    policy: {
      policy_type: 'corporation_tax_main_rate',
      horizon_years: 5,
      jurisdiction: 'UK',
      description: 'Raise CT 25% to 28%',
      raw_query: '',
      parse_method: 'rules',
      parse_confidence: 1,
    },
    mode: 'mock',
    summary: 'The 2023 increase is documented in [E1] and elasticity in [E2].',
    research_questions: ['What is the UK taxable profit elasticity?'],
    sources: [
      {
        source_id: 'S1',
        title: 'OBR Economic and Fiscal Outlook',
        url: 'https://obr.uk/efo',
        publisher: 'OBR',
        publisher_type: 'obr',
        access_method: 'url_fetch',
        reliability_tier: 1,
        url_verified: true,
        is_placeholder: false,
      },
    ],
    evidence: [
      {
        evidence_id: 'E1',
        source_id: 'S1',
        kind: 'quantitative',
        topic: 'revenue',
        claim: 'The April 2023 increase to 25% raised onshore CT receipts significantly.',
        quote: 'Onshore corporation tax receipts rose following the April 2023 main rate increase.',
        value: 12.4,
        unit: '£bn',
        verification_status: 'verified',
        confidence: 'high',
      },
      {
        evidence_id: 'E2',
        source_id: 'S1',
        kind: 'quantitative',
        topic: 'elasticity',
        claim: 'Taxable profit elasticity is estimated around 0.20.',
        quote: 'We assume a taxable profit elasticity of 0.20 for main rate changes.',
        value: 0.2,
        unit: 'elasticity',
        verification_status: 'unverified',
        confidence: 'medium',
      },
    ],
    interpretations: [
      {
        interpretation_id: 'I1',
        statement: 'Full expensing partly offsets investment sensitivity for plant & machinery.',
        supporting_evidence_ids: ['E1'],
        confidence: 'medium',
      },
    ],
    confounders: [
      {
        name: 'Full expensing (2023)',
        description: 'Introduced simultaneously with the 19% to 25% rate rise.',
        evidence_ids: ['E1'],
        likely_direction: 'lowers_revenue',
      },
    ],
    parameter_evidence: [
      {
        parameter: 'taxable_profit_elasticity',
        value: 0.2,
        low: 0.05,
        high: 0.5,
        evidence_ids: ['E2'],
        note: 'OBR central costing assumption',
      },
    ],
    open_questions: ['Magnitude of profit shifting under Pillar Two minimum tax.'],
    trace: [
      {
        step_id: 1,
        ts: '2026-11-07T16:45:01Z',
        kind: 'plan',
        title: 'Planned 4 research questions',
        detail: 'Covering revenue, elasticity, investment, and confounders.',
      },
    ],
    started_at: '2026-11-07T16:45:00Z',
    completed_at: '2026-11-07T16:45:10Z',
  },
};

describe('ResearchTab', () => {
  it('filters evidence by search box and topic, and opens/closes the source detail drawer', () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ResearchTab analysis={RESEARCH_ANALYSIS} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText(/Planned 4 research questions/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /The April 2023 increase to 25% raised onshore CT receipts significantly\./i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Taxable profit elasticity is estimated around 0\.20\./i),
    ).toBeInTheDocument();

    // Search filter
    const searchInput = screen.getByLabelText(/Search claims or quotes/i);
    fireEvent.change(searchInput, { target: { value: 'elasticity' } });

    expect(
      screen.queryByText(
        /The April 2023 increase to 25% raised onshore CT receipts significantly\./i,
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Taxable profit elasticity is estimated around 0\.20\./i),
    ).toBeInTheDocument();

    // Clear filters button
    fireEvent.click(screen.getByRole('button', { name: /Clear filters/i }));
    expect(
      screen.getByText(
        /The April 2023 increase to 25% raised onshore CT receipts significantly\./i,
      ),
    ).toBeInTheDocument();

    // Open source detail drawer
    fireEvent.click(screen.getByRole('button', { name: /View evidence →/i }));
    expect(
      screen.getByRole('dialog', { name: /Source details for S1/i }),
    ).toBeInTheDocument();

    // Escape closes drawer
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(
      screen.queryByRole('dialog', { name: /Source details for S1/i }),
    ).not.toBeInTheDocument();
  });
});
