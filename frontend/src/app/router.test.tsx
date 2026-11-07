import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from './router';

vi.mock('../api/hooks', async () => {
  const actual = await vi.importActual<typeof import('../api/hooks')>('../api/hooks');
  return {
    ...actual,
    useHealth: () => ({
      data: {
        status: 'ok',
        mode: 'mock',
        version: '0.1.0',
        gemini_configured: false,
      },
    }),
    useAnalysesList: () => ({
      data: [
        {
          analysis_id: 'an-golden-28',
          created_at: '2026-11-07T12:00:00Z',
          status: 'completed',
          query: 'Increase the UK main Corporation Tax rate from 25% to 28% in April 2027',
          policy_description: 'Increase the UK main Corporation Tax rate from 25% to 28% in April 2027',
          verification_overall: 'approved',
        },
      ],
      isLoading: false,
      isError: false,
    }),
  };
});

function renderAtRoute(route: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AppRoutes & Shell integration', () => {
  it('renders Layout shell with header, skip link, ModeBadge, and disclaimer footer on /', () => {
    renderAtRoute('/');
    expect(screen.getByText('Skip to main content')).toBeInTheDocument();
    expect(screen.getByText('Jane Avenue')).toBeInTheDocument();
    expect(screen.getByText('Mode: Mock')).toBeInTheDocument();
    expect(
      screen.getByText('Prototype. Not official government analysis.'),
    ).toBeInTheDocument();
  });

  it('renders /history with past analyses and links back to the run', () => {
    renderAtRoute('/history');
    expect(screen.getByText('Analysis History')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Increase the UK main Corporation Tax rate from 25% to 28% in April 2027',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Open →')).toBeInTheDocument();
  });

  it('renders /dev/ui primitive gallery cleanly', () => {
    renderAtRoute('/dev/ui');
    expect(
      screen.getByText(/UI Primitives & Design System Gallery/i),
    ).toBeInTheDocument();
    expect(screen.getByText('Forecast withheld')).toBeInTheDocument();
  });
});
