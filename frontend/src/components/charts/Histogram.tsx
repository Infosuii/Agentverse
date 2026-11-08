import React, { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame, formatChartValue, type ChartUnit } from './ChartFrame';
import { CHART_THEME, SCENARIO_COLORS, type EvidenceClassKey } from '../../lib/theme';

export interface HistogramMarkers {
  central?: number;
  p5?: number;
  p50?: number;
  p95?: number;
  custom?: number;
}

export interface HistogramProps {
  binEdges: number[];
  counts: number[];
  markers?: HistogramMarkers;
  unit?: ChartUnit;
  title?: React.ReactNode;
  caption?: React.ReactNode;
  evidenceClass?: EvidenceClassKey;
  height?: number;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  formatValue?: (val: number) => string;
}

interface InternalBinRow {
  midpoint: number;
  low: number;
  high: number;
  count: number;
}

export function Histogram({
  binEdges,
  counts,
  markers,
  unit = '£bn',
  title,
  caption = 'Final-year Monte Carlo draw frequency across assumption samples.',
  evidenceClass = 'model_scenario',
  height = 280,
  actions,
  footer,
  className,
  formatValue,
}: HistogramProps) {
  const { rows, isEmpty } = useMemo(() => {
    if (
      !Array.isArray(counts) ||
      counts.length === 0 ||
      !Array.isArray(binEdges) ||
      binEdges.length < counts.length + 1
    ) {
      return { rows: [] as InternalBinRow[], isEmpty: true };
    }

    const built: InternalBinRow[] = counts.map((count, i) => {
      const low = binEdges[i] ?? 0;
      const high = binEdges[i + 1] ?? low;
      return {
        midpoint: (low + high) / 2,
        low,
        high,
        count,
      };
    });

    return { rows: built, isEmpty: built.length === 0 };
  }, [binEdges, counts]);

  const valFormatter = (v: number) =>
    formatValue ? formatValue(v) : formatChartValue(v, unit);

  return (
    <ChartFrame
      title={title}
      caption={caption}
      evidenceClass={evidenceClass}
      unitLabel={unit}
      height={height}
      empty={isEmpty}
      emptyMessage="No final-year Monte Carlo histogram bins available."
      actions={actions}
      footer={footer}
      className={className}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          margin={{ top: 12, right: 20, left: 10, bottom: 20 }}
          barCategoryGap={1}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
          <XAxis
            dataKey="midpoint"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => valFormatter(Number(v))}
            tick={{ fontSize: 11, fill: CHART_THEME.tick }}
            label={{
              value: `Final-year value (${unit})`,
              position: 'insideBottom',
              offset: -10,
              fontSize: 11,
              fill: CHART_THEME.axisLabel,
            }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: CHART_THEME.tick }}
            width={48}
            label={{
              value: 'Draws',
              angle: -90,
              position: 'insideLeft',
              style: { textAnchor: 'middle', fontSize: 11, fill: CHART_THEME.axisLabel },
            }}
          />
          {markers?.p5 !== undefined && (
            <ReferenceLine
              x={markers.p5}
              stroke={CHART_THEME.neutral}
              strokeDasharray="4 3"
              label={{ value: 'p5', position: 'top', fontSize: 10, fill: CHART_THEME.tick }}
            />
          )}
          {markers?.p95 !== undefined && (
            <ReferenceLine
              x={markers.p95}
              stroke={CHART_THEME.neutral}
              strokeDasharray="4 3"
              label={{ value: 'p95', position: 'top', fontSize: 10, fill: CHART_THEME.tick }}
            />
          )}
          {markers?.central !== undefined && (
            <ReferenceLine
              x={markers.central}
              stroke={SCENARIO_COLORS.central}
              strokeWidth={2}
              label={{
                value: 'Central',
                position: 'top',
                fontSize: 10,
                fill: SCENARIO_COLORS.central,
              }}
            />
          )}
          {markers?.custom !== undefined && (
            <ReferenceLine
              x={markers.custom}
              stroke={SCENARIO_COLORS.custom}
              strokeWidth={2}
              strokeDasharray="4 2"
              label={{
                value: 'Custom',
                position: 'top',
                fontSize: 10,
                fill: SCENARIO_COLORS.custom,
              }}
            />
          )}
          <RechartsTooltip
            cursor={{ fill: CHART_THEME.cursor }}
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null;
              const bin = payload[0]?.payload as InternalBinRow | undefined;
              if (!bin) return null;
              return (
                <div className="rounded-sm border border-border bg-popover p-2.5 text-xs text-popover-foreground shadow-lg shadow-black/40">
                  <div className="font-semibold text-foreground">
                    Bin: {valFormatter(bin.low)} to {valFormatter(bin.high)}
                  </div>
                  <div className="mt-0.5 text-muted-foreground tabular-nums">
                    Frequency: <strong className="text-foreground">{bin.count}</strong> draws
                  </div>
                </div>
              );
            }}
          />
          <Bar
            dataKey="count"
            name="Simulation draws"
            fill={SCENARIO_COLORS.central}
            fillOpacity={0.68}
            radius={[2, 2, 0, 0]}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export default Histogram;
