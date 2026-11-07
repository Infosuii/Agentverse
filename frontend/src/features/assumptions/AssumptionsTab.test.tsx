import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { Analysis, CalcStep } from '../../api/hooks';
import {
  AssumptionsTab,
  filterAndSortCalcSteps,
  getCalcStepDependencyRank,
} from './AssumptionsTab';

const SAMPLE_CALC_STEPS: CalcStep[] = [
  {
    step_id: 'rev.dynamic.2027-28',
    label: 'Dynamic revenue change 2027-28',
    formula: 'ΔR_dynamic = ΔR_behav + t1 × B1 × timing × ΔY × profit_gdp_elasticity',
    inputs: { ΔR_behav: 5.2, ΔY: -0.04 },
    output: 5.05,
    unit: '£bn',
    fiscal_year: '2027-28',
    parameter_names: ['profit_gdp_elasticity'],
    source_ids: ['D-obr-baseline'],
  },
  {
    step_id: 'rev.static.2027-28',
    label: 'Static revenue change 2027-28',
    formula: 'ΔR_static = (t1 − t0) × B0 × timing',
    inputs: { t0: 0.25, t1: 0.28, B0: 320, timing: 0.6 },
    output: 5.76,
    unit: '£bn',
    fiscal_year: '2027-28',
    parameter_names: ['receipts_first_year_share'],
    source_ids: ['D-obr-baseline'],
  },
  {
    step_id: 'rev.base.2027-28',
    label: 'Implied main-rate profit base 2027-28',
    formula: 'B0 = main_rate_profit_share × R / t0',
    inputs: { t0: 0.25, R: 94.1 },
    output: 320.0,
    unit: '£bn',
    fiscal_year: '2027-28',
    parameter_names: ['main_rate_profit_share'],
    source_ids: ['D-obr-baseline'],
  },
  {
    step_id: 'ucc.delta_c.2027-28',
    label: 'Weighted user cost of capital change 2027-28',
    formula: 'Δc = Σ w_a Δc_a',
    inputs: { r: 0.05 },
    output: 1.85,
    unit: '%',
    fiscal_year: '2027-28',
    parameter_names: ['real_required_return'],
    source_ids: ['S1'],
  },
  {
    step_id: 'rev.behav.2027-28',
    label: 'Behavioural revenue change 2027-28',
    formula: 'ΔR_behav = (t1 × B1 − t0 × B0) × timing',
    inputs: { B0: 320, B1: 317.4 },
    output: 5.2,
    unit: '£bn',
    fiscal_year: '2027-28',
    parameter_names: ['taxable_profit_elasticity'],
    source_ids: ['D-obr-baseline'],
  },
];

describe('AssumptionsTab & Calculation Inspector', () => {
  it('orders CalcSteps strictly in dependency order (user-cost -> base -> static -> behavioural -> dynamic)', () => {
    expect(getCalcStepDependencyRank(SAMPLE_CALC_STEPS[3]!)).toBe(1); // ucc
    expect(getCalcStepDependencyRank(SAMPLE_CALC_STEPS[2]!)).toBe(2); // base
    expect(getCalcStepDependencyRank(SAMPLE_CALC_STEPS[1]!)).toBe(3); // static
    expect(getCalcStepDependencyRank(SAMPLE_CALC_STEPS[4]!)).toBe(4); // behav
    expect(getCalcStepDependencyRank(SAMPLE_CALC_STEPS[0]!)).toBe(8); // dynamic

    const sorted = filterAndSortCalcSteps(
      SAMPLE_CALC_STEPS,
      'revenue_dynamic_gbp_bn',
      '2027-28',
    );
    expect(sorted.map((s) => s.step_id)).toEqual([
      'ucc.delta_c.2027-28',
      'rev.base.2027-28',
      'rev.static.2027-28',
      'rev.behav.2027-28',
      'rev.dynamic.2027-28',
    ]);
  });

  it('renders assumptions table with research cross-check and calculation inspector', () => {
    const samplePolicy = {
      policy_type: 'corporation_tax_main_rate' as const,
      tax: 'corporation_tax' as const,
      baseline_rate_pct: 25,
      proposed_rate_pct: 28,
      effective_date: '2027-04-01',
      horizon_years: 2,
      jurisdiction: 'UK' as const,
      description: 'Raise CT to 28%',
      raw_query: 'Raise CT to 28%',
      parse_method: 'rules' as const,
      parse_confidence: 1,
      ambiguities: [],
    };

    const sampleAnalysis: Analysis = {
      analysis_id: 'test-assumptions',
      created_at: '2026-11-07T17:00:00Z',
      updated_at: '2026-11-07T17:00:00Z',
      status: 'completed',
      mode: 'mock',
      request: { query: 'Raise CT to 28%' },
      policy: samplePolicy,
      research: {
        policy: samplePolicy,
        mode: 'mock',
        summary: 'Test research summary',
        parameter_evidence: [
          {
            parameter: 'taxable_profit_elasticity',
            value: 0.22,
            low: 0.1,
            high: 0.45,
            evidence_ids: ['E1'],
            note: 'IFS estimate from UK corporate tax returns',
          },
        ],
        started_at: '2026-11-07T17:00:00Z',
      },
      simulation: {
        policy: samplePolicy,
        baseline_vintage: 'OBR March 2026',
        scenarios: [
          {
            scenario: {
              name: 'central',
              label: 'Central',
              description: 'Central settings',
              parameter_values: { taxable_profit_elasticity: 0.2 },
            },
            result: {
              model_version: '1.0',
              policy: samplePolicy,
              scenario: 'central',
              baseline_vintage: 'OBR March 2026',
              fiscal_years: ['2027-28'],
              metrics: [],
              calc_trace: SAMPLE_CALC_STEPS,
              parameters_used: { taxable_profit_elasticity: 0.2 },
              warnings: [],
            },
          },
        ],
        assumptions: [
          {
            name: 'taxable_profit_elasticity',
            label: 'Taxable profit elasticity',
            description: 'Elasticity of taxable corporate profits.',
            category: 'behavioural',
            unit: 'elasticity',
            value: 0.2,
            low: 0.05,
            high: 0.5,
            distribution: {
              kind: 'triangular',
              params: { low: 0.05, mode: 0.2, high: 0.5 },
            },
            basis: 'literature',
            source_ids: ['S1'],
            evidence_ids: ['E1'],
            rationale: 'Standard literature elasticity.',
            adjustable: true,
            slider_min: 0,
            slider_max: 1,
            slider_step: 0.01,
            is_user_override: false,
            is_placeholder: false,
          },
        ],
      },
      sources: [
        {
          source_id: 'S1',
          title: 'IFS Corporate Tax Note',
          url: 'https://ifs.org.uk/ct',
          publisher: 'IFS',
          publisher_type: 'ifs',
          access_method: 'url_fetch',
          reliability_tier: 2,
          url_verified: true,
          is_placeholder: false,
        },
      ],
      stage_timings_ms: {},
    };

    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[
            '/analyses/test-assumptions/assumptions?metric=revenue_behavioural_gbp_bn&year=2027-28',
          ]}
        >
          <AssumptionsTab analysis={sampleAnalysis} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      screen.getByText('Model Assumptions & Provenance Registry'),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText('IFS estimate from UK corporate tax returns').length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText('How was this calculated? (Calculation Inspector)'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Implied main-rate profit base 2027-28'),
    ).toBeInTheDocument();
  });
});
