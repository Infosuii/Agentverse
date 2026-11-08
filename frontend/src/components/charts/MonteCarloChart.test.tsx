import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MonteCarloChart, monteCarloChartUrl, type MonteCarloSource } from './MonteCarloChart';

describe('MonteCarloChart', () => {
  it('builds the analysis and simulate chart URLs', () => {
    expect(
      monteCarloChartUrl({ kind: 'analysis', analysisId: 'a b' }, 'gdp_level_pct', true, 60),
    ).toBe('/api/analyses/a%20b/charts/montecarlo.png?metric=gdp_level_pct&paths=60&empirical=true');
    expect(
      monteCarloChartUrl(
        { kind: 'simulate', request: {} } as unknown as MonteCarloSource,
        'revenue_behavioural_gbp_bn',
        false,
        40,
      ),
    ).toBe('/api/simulate/montecarlo.png?metric=revenue_behavioural_gbp_bn&paths=40&empirical=false');
  });

  it('asks the server for a chart in the current theme', () => {
    expect(monteCarloChartUrl({ kind: 'analysis', analysisId: 'a' }, 'gdp_level_pct', false, 60, 'light')).toContain('theme=light');
    document.documentElement.dataset.theme = 'light';
    render(<MonteCarloChart source={{ kind: 'analysis', analysisId: 'ana-2' }} />);
    expect(screen.getByRole('img').getAttribute('src')).toContain('theme=light');
    delete document.documentElement.dataset.theme;
  });

  it('shows the server-rendered chart for an analysis', () => {
    render(<MonteCarloChart source={{ kind: 'analysis', analysisId: 'ana-1' }} title="Trajectories" />);
    const img = screen.getByRole('img');
    expect(img.getAttribute('src')).toContain('/api/analyses/ana-1/charts/montecarlo.png');
    expect(screen.getByText('Trajectories')).toBeTruthy();
  });
});
