import { SCENARIO_COLORS, EVIDENCE_CLASS_COLORS } from '../../lib/theme';
import { Card } from '../ui';
import { LineChart } from './LineChart';
import { FanChart } from './FanChart';
import { Tornado } from './Tornado';
import { Histogram } from './Histogram';
import { BarCompare } from './BarCompare';
import { TimelineChart } from './TimelineChart';
import { ProvenanceNumber } from './ProvenanceNumber';

const SAMPLE_YEARS = ['2027-28', '2028-29', '2029-30', '2030-31', '2031-32'];

export function ChartsGallery() {
  return (
    <Card
      title="7. Shared Chart Library & Provenance Number (`src/components/charts/`)"
      subtitle="Typed Recharts wrappers owned by agent-8 for Scenarios, Precedents, and Evaluation views."
    >
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/40 p-3 text-xs text-foreground/85">
          <span>Interactive number provenance popover example:</span>
          <ProvenanceNumber
            value={3.14}
            unit="£bn"
            calcStepIds={['rev.base.2027-28', 'rev.behav.2027-28']}
            sources={['S1', 'D-obr-baseline']}
            evidenceClass="model_scenario"
            metric="revenue_behavioural_gbp_bn"
            year="2027-28"
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <LineChart
            title="Scenario Trajectories (LineChart)"
            caption="Central, optimistic, pessimistic and custom scenario paths."
            unit="£bn"
            series={[
              {
                id: 'central',
                label: 'Central',
                color: SCENARIO_COLORS.central,
                points: SAMPLE_YEARS.map((y, i) => ({ x: y, y: 2.1 + i * 0.35 })),
              },
              {
                id: 'optimistic',
                label: 'Optimistic',
                color: SCENARIO_COLORS.optimistic,
                points: SAMPLE_YEARS.map((y, i) => ({ x: y, y: 2.8 + i * 0.45 })),
              },
              {
                id: 'pessimistic',
                label: 'Pessimistic',
                color: SCENARIO_COLORS.pessimistic,
                points: SAMPLE_YEARS.map((y, i) => ({ x: y, y: 1.3 + i * 0.2 })),
              },
              {
                id: 'custom',
                label: 'Custom',
                color: SCENARIO_COLORS.custom,
                dashed: true,
                points: SAMPLE_YEARS.map((y, i) => ({ x: y, y: 2.4 + i * 0.38 })),
              },
            ]}
          />

          <FanChart
            title="Monte Carlo Uncertainty (FanChart)"
            caption="Nested p5–p95 and p25–p75 assumption-driven bands with median line."
            unit="£bn"
            intervalNote="assumption-driven ranges, not statistical prediction intervals; exclude model and data uncertainty"
            bands={SAMPLE_YEARS.map((y, i) => ({
              x: y,
              p5: 1.2 + i * 0.18,
              p25: 1.7 + i * 0.26,
              p50: 2.1 + i * 0.35,
              p75: 2.5 + i * 0.42,
              p95: 3.1 + i * 0.52,
            }))}
          />

          <Tornado
            title="Parameter Sensitivity (Tornado)"
            caption="Final-year behavioural revenue sensitivity around central estimate."
            unit="£bn"
            base={3.5}
            items={[
              {
                label: 'Taxable profit elasticity',
                low: 4.1,
                high: 2.6,
                lowInput: 0.05,
                highInput: 0.5,
              },
              {
                label: 'Main-rate profit share',
                low: 3.1,
                high: 3.9,
                lowInput: 0.78,
                highInput: 0.92,
              },
              {
                label: 'Profit base deviation (%)',
                low: 3.25,
                high: 3.75,
                lowInput: -5,
                highInput: 5,
              },
            ]}
          />

          <Histogram
            title="Final-Year Distribution (Histogram)"
            caption="2,000 Monte Carlo draws in 2031-32 with central, p5 and p95 markers."
            unit="£bn"
            binEdges={[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]}
            counts={[45, 190, 480, 640, 410, 185, 50]}
            markers={{ p5: 1.95, central: 3.5, p95: 4.45 }}
          />

          <BarCompare
            title="Category Comparison (BarCompare)"
            caption="Observed outcome vs official costing vs model scenario."
            unit="£bn"
            series={[
              {
                id: 'observed',
                label: 'Observed outcome',
                color: EVIDENCE_CLASS_COLORS.observed_outcome,
              },
              {
                id: 'costing',
                label: 'Official costing',
                color: EVIDENCE_CLASS_COLORS.official_costing,
              },
              {
                id: 'model',
                label: 'Model scenario',
                color: EVIDENCE_CLASS_COLORS.model_scenario,
              },
            ]}
            data={[
              { category: '2023-24', observed: 11.8, costing: 11.2, model: 11.5 },
              { category: '2024-25', observed: 15.4, costing: 14.9, model: 15.1 },
            ]}
          />

          <TimelineChart
            title="UK CT Main Rate History (TimelineChart)"
            caption="Historical statutory corporation tax main rate step line."
            unit="%"
            points={[
              { x: '2008-09', y: 28 },
              { x: '2011-12', y: 26 },
              { x: '2012-13', y: 24 },
              { x: '2015-16', y: 20 },
              { x: '2017-18', y: 19 },
              { x: '2023-24', y: 25 },
            ]}
            events={[
              { x: '2015-16', y: 20, label: 'Cut to 20%' },
              { x: '2023-24', y: 25, label: 'Rise to 25% + Full Expensing' },
            ]}
          />
        </div>
      </div>
    </Card>
  );
}

export default ChartsGallery;
