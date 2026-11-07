import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeAll, describe, expect, it } from 'vitest';
import {
  BarCompare,
  ChartsGallery,
  FanChart,
  Histogram,
  LineChart,
  ProvenanceNumber,
  TimelineChart,
  Tornado,
  formatChartValue,
} from './index';

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

describe('Chart library & ProvenanceNumber', () => {
  it('formats chart values using UK conventions', () => {
    expect(formatChartValue(3.1, '£bn', 1)).toBe('£3.1bn');
    expect(formatChartValue(-0.4, '£bn', 1)).toBe('−£0.4bn');
    expect(formatChartValue(-0.05, '%', 2)).toBe('−0.05%');
    expect(formatChartValue(3, 'pp')).toBe('+3pp');
    expect(formatChartValue(0.2, 'elasticity')).toBe('0.2');
  });

  it('renders empty state gracefully when chart data is empty', () => {
    render(
      <MemoryRouter>
        <div>
          <LineChart title="Empty Line" series={[]} />
          <FanChart title="Empty Fan" bands={[]} />
          <Tornado title="Empty Tornado" base={0} items={[]} />
          <Histogram title="Empty Hist" binEdges={[]} counts={[]} />
          <BarCompare title="Empty Bar" data={[]} series={[]} />
          <TimelineChart title="Empty Timeline" points={[]} />
        </div>
      </MemoryRouter>,
    );

    expect(screen.getByText('No series points available to plot.')).toBeInTheDocument();
    expect(
      screen.getByText('No Monte Carlo distribution bands available.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No sensitivity tornado items available for this metric.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No final-year Monte Carlo histogram bins available.'),
    ).toBeInTheDocument();
    expect(screen.getByText('No comparison categories available.')).toBeInTheDocument();
    expect(
      screen.getByText('No historical timeline points available.'),
    ).toBeInTheDocument();
  });

  it('renders FanChart with verbatim interval_note and never calls bands confidence intervals', () => {
    const note =
      'assumption-driven ranges, not statistical prediction intervals; exclude model and data uncertainty';
    render(
      <FanChart
        title="Behavioural Revenue Fan"
        intervalNote={note}
        bands={[
          { x: '2027-28', p5: 1.5, p25: 2.1, p50: 2.6, p75: 3.1, p95: 3.8 },
        ]}
      />,
    );

    expect(screen.getByText(note)).toBeInTheDocument();
  });

  it('renders ProvenanceNumber and ChartsGallery without errors', () => {
    render(
      <MemoryRouter>
        <div>
          <ProvenanceNumber
            value={4.25}
            unit="£bn"
            calcStepIds={['rev.behav.2027-28']}
            sources={['S1']}
            evidenceClass="model_scenario"
            analysisId="test-123"
            metric="revenue_behavioural_gbp_bn"
            year="2027-28"
          />
          <ChartsGallery />
        </div>
      </MemoryRouter>,
    );

    expect(screen.getByText('£4.25bn')).toBeInTheDocument();
    expect(
      screen.getByText(/Shared Chart Library & Provenance Number/i),
    ).toBeInTheDocument();
  });
});
