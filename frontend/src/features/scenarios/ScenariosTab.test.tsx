import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { beforeAll, describe, expect, it } from 'vitest';
import type { Analysis, Assumption, PolicySpec, SimulationBundle } from '../../api/hooks';
import {
  buildFanBands,
  buildParameterOverrides,
  buildPolicyWithRateOverride,
  buildScenarioSeries,
  extractFinalYearHistogram,
  extractTornadoItems,
} from './transforms';
import { ScenariosTab } from './ScenariosTab';

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

const SAMPLE_POLICY: PolicySpec = {
  policy_type: 'corporation_tax_main_rate',
  tax: 'corporation_tax',
  baseline_rate_pct: 25,
  proposed_rate_pct: 28,
  effective_date: '2027-04-01',
  horizon_years: 2,
  jurisdiction: 'UK',
  description: 'Raise the CT main rate from 25% to 28%',
  raw_query: 'What if CT rises from 25% to 28%?',
  parse_method: 'rules',
  parse_confidence: 1,
  ambiguities: [],
};

const SAMPLE_ASSUMPTIONS: Assumption[] = [
  {
    name: 'taxable_profit_elasticity',
    label: 'Taxable profit elasticity',
    description: 'Elasticity of taxable profits wrt net-of-tax rate',
    category: 'behavioural',
    unit: 'elasticity',
    value: 0.2,
    low: 0.05,
    high: 0.5,
    distribution: { kind: 'triangular', params: { low: 0.05, mode: 0.2, high: 0.5 } },
    basis: 'literature',
    source_ids: ['S1'],
    evidence_ids: ['E1'],
    rationale: 'Devereux, Liu & Loretz (2014)',
    adjustable: true,
    slider_min: 0,
    slider_max: 1,
    slider_step: 0.01,
    is_user_override: false,
    is_placeholder: false,
  },
  {
    name: 'share_plant_machinery',
    label: 'Investment share: plant & machinery',
    description: 'Fixed asset share',
    category: 'structural',
    unit: 'fraction',
    value: 0.4,
    low: 0.4,
    high: 0.4,
    distribution: { kind: 'fixed', params: {} },
    basis: 'official',
    source_ids: ['D-ons'],
    evidence_ids: [],
    rationale: 'ONS asset shares',
    adjustable: false,
    slider_min: null,
    slider_max: null,
    slider_step: null,
    is_user_override: false,
    is_placeholder: false,
  },
];

const SAMPLE_BUNDLE: SimulationBundle = {
  policy: SAMPLE_POLICY,
  baseline_vintage: 'OBR March 2026',
  scenarios: [
    {
      scenario: {
        name: 'central',
        label: 'Central',
        description: 'All parameters at central settings.',
        parameter_values: { taxable_profit_elasticity: 0.2 },
      },
      result: {
        model_version: '1.0',
        policy: SAMPLE_POLICY,
        scenario: 'central',
        baseline_vintage: 'OBR March 2026',
        fiscal_years: ['2027-28', '2028-29'],
        metrics: [
          {
            metric: 'revenue_behavioural_gbp_bn',
            label: 'Behavioural revenue change',
            unit: '£bn',
            confidence: 'medium',
            note: '',
            values: [
              { fiscal_year: '2027-28', value: 5.2 },
              { fiscal_year: '2028-29', value: 8.6 },
            ],
          },
          {
            metric: 'gdp_level_pct',
            label: 'GDP level change',
            unit: '%',
            confidence: 'low',
            note: 'Partial equilibrium',
            values: [
              { fiscal_year: '2027-28', value: -0.04 },
              { fiscal_year: '2028-29', value: -0.08 },
            ],
          },
        ],
        calc_trace: [],
        parameters_used: { taxable_profit_elasticity: 0.2 },
        warnings: [],
      },
    },
    {
      scenario: {
        name: 'optimistic',
        label: 'Optimistic',
        description: 'Uncertain parameters set to higher revenue bound.',
        parameter_values: { taxable_profit_elasticity: 0.05 },
      },
      result: {
        model_version: '1.0',
        policy: SAMPLE_POLICY,
        scenario: 'optimistic',
        baseline_vintage: 'OBR March 2026',
        fiscal_years: ['2027-28', '2028-29'],
        metrics: [
          {
            metric: 'revenue_behavioural_gbp_bn',
            label: 'Behavioural revenue change',
            unit: '£bn',
            confidence: 'medium',
            note: '',
            values: [
              { fiscal_year: '2027-28', value: 6.1 },
              { fiscal_year: '2028-29', value: 10.2 },
            ],
          },
        ],
        calc_trace: [],
        parameters_used: { taxable_profit_elasticity: 0.05 },
        warnings: [],
      },
    },
    {
      scenario: {
        name: 'pessimistic',
        label: 'Pessimistic',
        description: 'Uncertain parameters set to lower revenue bound.',
        parameter_values: { taxable_profit_elasticity: 0.5 },
      },
      result: {
        model_version: '1.0',
        policy: SAMPLE_POLICY,
        scenario: 'pessimistic',
        baseline_vintage: 'OBR March 2026',
        fiscal_years: ['2027-28', '2028-29'],
        metrics: [
          {
            metric: 'revenue_behavioural_gbp_bn',
            label: 'Behavioural revenue change',
            unit: '£bn',
            confidence: 'medium',
            note: '',
            values: [
              { fiscal_year: '2027-28', value: 3.8 },
              { fiscal_year: '2028-29', value: 6.4 },
            ],
          },
        ],
        calc_trace: [],
        parameters_used: { taxable_profit_elasticity: 0.5 },
        warnings: [],
      },
    },
  ],
  monte_carlo: {
    n_draws: 2000,
    seed: 42,
    sampled_parameters: ['taxable_profit_elasticity'],
    distributions: [
      {
        metric: 'revenue_behavioural_gbp_bn',
        unit: '£bn',
        bands: [
          {
            fiscal_year: '2027-28',
            p5: 4.0,
            p10: 4.3,
            p25: 4.8,
            p50: 5.2,
            p75: 5.6,
            p90: 5.9,
            p95: 6.0,
            mean: 5.18,
          },
          {
            fiscal_year: '2028-29',
            p5: 6.6,
            p10: 7.1,
            p25: 7.9,
            p50: 8.6,
            p75: 9.2,
            p90: 9.7,
            p95: 10.0,
            mean: 8.55,
          },
        ],
      },
    ],
    histograms: [
      {
        metric: 'revenue_behavioural_gbp_bn',
        fiscal_year: '2028-29',
        bin_edges: [6.0, 7.0, 8.0, 9.0, 10.0],
        counts: [200, 600, 800, 400],
      },
    ],
    interval_kind: 'assumption_range',
    interval_note:
      'assumption-driven ranges, not statistical prediction intervals; exclude model and data uncertainty',
    empirical_interval: null,
    empirical_calibration_note: null,
  },
  sensitivity: [
    {
      metric: 'revenue_behavioural_gbp_bn',
      fiscal_year: '2028-29',
      base_output: 8.6,
      items: [
        {
          parameter: 'taxable_profit_elasticity',
          label: 'Taxable profit elasticity',
          low_input: 0.05,
          high_input: 0.5,
          output_at_low: 9.9,
          output_at_high: 6.9,
          swing: 3.0,
        },
      ],
    },
  ],
  assumptions: SAMPLE_ASSUMPTIONS,
  warnings: [],
};

describe('Scenario transforms & slider override builders', () => {
  it('transforms SimulationBundle scenarios into LineChart series with theme colors', () => {
    const series = buildScenarioSeries(SAMPLE_BUNDLE, 'revenue_behavioural_gbp_bn');
    expect(series).toHaveLength(3);
    expect(series[0]?.id).toBe('central');
    expect(series[0]?.color).toBe('#2563eb');
    expect(series[1]?.id).toBe('optimistic');
    expect(series[1]?.color).toBe('#16a34a');
    expect(series[2]?.id).toBe('pessimistic');
    expect(series[2]?.color).toBe('#dc2626');
  });

  it('adds purple custom series when customBundle is provided', () => {
    const series = buildScenarioSeries(
      SAMPLE_BUNDLE,
      'revenue_behavioural_gbp_bn',
      SAMPLE_BUNDLE,
    );
    expect(series).toHaveLength(4);
    expect(series[3]?.id).toBe('custom');
    expect(series[3]?.color).toBe('#7c3aed');
    expect(series[3]?.dashed).toBe(true);
  });

  it('extracts fan bands, final-year histogram, and tornado items accurately', () => {
    const fan = buildFanBands(SAMPLE_BUNDLE, 'revenue_behavioural_gbp_bn');
    expect(fan.bands).toHaveLength(2);
    expect(fan.bands[1]?.p50).toBe(8.6);
    expect(fan.intervalNote).toContain('assumption-driven ranges');

    const hist = extractFinalYearHistogram(
      SAMPLE_BUNDLE,
      'revenue_behavioural_gbp_bn',
    );
    expect(hist.centralFinal).toBe(8.6);
    expect(hist.p5Final).toBe(6.6);
    expect(hist.p95Final).toBe(10.0);

    const tornado = extractTornadoItems(
      SAMPLE_BUNDLE,
      'revenue_behavioural_gbp_bn',
    );
    expect(tornado.items).toHaveLength(1);
    expect(tornado.items[0]?.swing).toBe(3.0);
  });

  it('builds parameter overrides only for modified adjustable parameters', () => {
    const overrides = buildParameterOverrides(SAMPLE_ASSUMPTIONS, {
      taxable_profit_elasticity: 0.35,
      share_plant_machinery: 0.5, // non-adjustable, should be ignored
    });
    expect(overrides).toEqual({ taxable_profit_elasticity: 0.35 });

    const noOverrides = buildParameterOverrides(SAMPLE_ASSUMPTIONS, {
      taxable_profit_elasticity: 0.2,
    });
    expect(noOverrides).toEqual({});
  });

  it('updates PolicySpec when proposed rate slider changes', () => {
    const updated = buildPolicyWithRateOverride(SAMPLE_POLICY, 30);
    expect(updated.proposed_rate_pct).toBe(30);
    expect(updated.description).toContain('25% to 30%');
  });

  it('hides numbers and renders WithheldBanner when verification.forecast_allowed is false', () => {
    const withheldAnalysis: Analysis = {
      analysis_id: 'withheld-1',
      created_at: '2026-11-07T17:00:00Z',
      updated_at: '2026-11-07T17:00:00Z',
      status: 'completed',
      mode: 'mock',
      request: { query: 'Raise CT to 45%' },
      policy: SAMPLE_POLICY,
      simulation: SAMPLE_BUNDLE,
      verification: {
        overall: 'forecast_withheld',
        forecast_allowed: false,
        checks: [],
        decline_reasons: ['Rate change (+20pp) exceeds 15pp limit'],
        summary: 'Withheld',
        counts: {},
        verified_at: '2026-11-07T17:00:00Z',
      },
      sources: [],
      stage_timings_ms: {},
    };

    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ScenariosTab analysis={withheldAnalysis} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      screen.getByRole('alert', { name: /Quantitative forecast withheld/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Rate change \(\+20pp\) exceeds 15pp limit/i),
    ).toBeInTheDocument();
    expect(screen.queryByText('Live Assumption Sliders')).not.toBeInTheDocument();
  });
});
