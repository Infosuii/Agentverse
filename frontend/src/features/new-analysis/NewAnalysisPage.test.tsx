import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { NewAnalysisPage } from './NewAnalysisPage';
import { apiClient } from '../../api/client';

vi.mock('../../api/client', () => ({
  apiClient: {
    POST: vi.fn(),
    GET: vi.fn(),
  },
}));

describe('NewAnalysisPage', () => {
  it('parses policy when clicking an example chip and rechecks scope when editing rate', async () => {
    const mockedPost = vi.mocked(apiClient.POST);
    mockedPost.mockImplementation(async (path: string) => {
      if (path === '/api/policy/parse') {
        return {
          data: {
            policy: {
              policy_type: 'corporation_tax_main_rate',
              tax: 'corporation_tax',
              baseline_rate_pct: 25,
              proposed_rate_pct: 28,
              effective_date: '2027-04-01',
              horizon_years: 5,
              jurisdiction: 'UK',
              description: 'Raise the CT main rate from 25% to 28% from 1 April 2027',
              raw_query:
                'What would happen if the UK increased corporation tax from 25% to 28%?',
              parse_method: 'rules',
              parse_confidence: 1,
              ambiguities: ['Assumed effective date of 1 April 2027'],
            },
            scope: {
              status: 'supported',
              forecast_allowed: true,
              reasons: [],
              warnings: [],
            },
          },
          error: undefined,
        } as never;
      }
      if (path === '/api/policy/scope') {
        return {
          data: {
            policy: {
              policy_type: 'corporation_tax_main_rate',
              tax: 'corporation_tax',
              baseline_rate_pct: 25,
              proposed_rate_pct: 45,
              effective_date: '2027-04-01',
              horizon_years: 5,
              jurisdiction: 'UK',
              description: 'Raise the CT main rate from 25% to 45%',
              raw_query: '',
              parse_method: 'manual',
              parse_confidence: 1,
              ambiguities: [],
            },
            scope: {
              status: 'unsupported',
              forecast_allowed: false,
              reasons: ['Rate change of +20pp exceeds maximum supported 15pp bound'],
              warnings: [],
            },
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: new Error('Unexpected path') } as never;
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <NewAnalysisPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const chip = screen.getByRole('button', {
      name: /What would happen if the UK increased corporation tax from 25% to 28%\?/i,
    });
    fireEvent.click(chip);

    await waitFor(() => {
      expect(screen.getByLabelText(/Proposed Rate \(%\)/i)).toHaveValue(28);
    });

    expect(
      screen.getByText('Assumed effective date of 1 April 2027'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Supported scope/i)).toBeInTheDocument();

    const proposedInput = screen.getByLabelText(/Proposed Rate \(%\)/i);
    fireEvent.change(proposedInput, { target: { value: '45' } });

    await waitFor(() => {
      expect(
        screen.getByText(/Rate change of \+20pp exceeds maximum supported 15pp bound/i),
      ).toBeInTheDocument();
    });
  });
});
