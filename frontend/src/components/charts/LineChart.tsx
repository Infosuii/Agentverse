import React, { useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart as RechartsLineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame, formatChartValue, formatXAxisTick, type ChartUnit } from './ChartFrame';
import type { EvidenceClassKey } from '../../lib/theme';

export interface LineChartPoint {
  x: string | number;
  y: number | null;
}

export interface LineChartSeries {
  id: string;
  label: string;
  color: string;
  points: LineChartPoint[];
  dashed?: boolean;
}

export interface LineChartProps {
  series: LineChartSeries[];
  unit?: ChartUnit;
  title?: React.ReactNode;
  caption?: React.ReactNode;
  evidenceClass?: EvidenceClassKey;
  showZeroReference?: boolean;
  xLabel?: string;
  yLabel?: string;
  height?: number;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  formatValue?: (val: number) => string;
  formatX?: (x: string | number) => string;
}

export function LineChart({
  series,
  unit = '£bn',
  title,
  caption = 'Scenario projection path over fiscal years.',
  evidenceClass = 'model_scenario',
  showZeroReference = true,
  xLabel = 'Fiscal year',
  yLabel,
  height = 300,
  actions,
  footer,
  className,
  formatValue,
  formatX,
}: LineChartProps) {
  const { rows, isEmpty } = useMemo(() => {
    const validSeries = series.filter((s) => Array.isArray(s.points) && s.points.length > 0);
    if (validSeries.length === 0) {
      return { rows: [] as Array<Record<string, string | number | null>>, isEmpty: true };
    }

    const xOrder: Array<string | number> = [];
    const byX = new Map<string | number, Record<string, string | number | null>>();

    for (const s of validSeries) {
      for (const pt of s.points) {
        if (!byX.has(pt.x)) {
          xOrder.push(pt.x);
          byX.set(pt.x, { x: pt.x });
        }
        const entry = byX.get(pt.x)!;
        entry[s.id] = pt.y;
      }
    }

    return {
      rows: xOrder.map((x) => byX.get(x)!),
      isEmpty: xOrder.length === 0,
    };
  }, [series]);

  const valFormatter = (v: number) =>
    formatValue ? formatValue(v) : formatChartValue(v, unit);
  const xFormatter = (x: string | number) =>
    formatX ? formatX(x) : formatXAxisTick(x);

  return (
    <ChartFrame
      title={title}
      caption={caption}
      evidenceClass={evidenceClass}
      unitLabel={unit}
      height={height}
      empty={isEmpty}
      emptyMessage="No series points available to plot."
      actions={actions}
      footer={footer}
      className={className}
    >
      <ResponsiveContainer width="100%" height="100%">
        <RechartsLineChart
          data={rows}
          margin={{ top: 10, right: 20, left: 12, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="x"
            tickFormatter={xFormatter}
            tick={{ fontSize: 11, fill: '#475569' }}
            label={{
              value: xLabel,
              position: 'insideBottom',
              offset: -10,
              fontSize: 11,
              fill: '#64748b',
            }}
          />
          <YAxis
            tickFormatter={(v: number) => valFormatter(Number(v))}
            tick={{ fontSize: 11, fill: '#475569' }}
            width={72}
            label={{
              value: yLabel ?? unit,
              angle: -90,
              position: 'insideLeft',
              style: { textAnchor: 'middle', fontSize: 11, fill: '#64748b' },
            }}
          />
          {showZeroReference && (
            <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="4 4" />
          )}
          <RechartsTooltip
            labelFormatter={(label) => `${xLabel}: ${xFormatter(label as string | number)}`}
            formatter={(value: unknown, name: string) => {
              const s = series.find((item) => item.id === name || item.label === name);
              const num = typeof value === 'number' ? value : Number(value);
              return [valFormatter(num), s?.label ?? name];
            }}
            contentStyle={{
              fontSize: 12,
              borderRadius: 6,
              borderColor: '#cbd5e1',
            }}
          />
          <Legend
            verticalAlign="top"
            height={28}
            wrapperStyle={{ fontSize: 12 }}
          />
          {series.map((s) => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.id}
              name={s.label}
              stroke={s.color}
              strokeWidth={2.25}
              strokeDasharray={s.dashed ? '6 4' : undefined}
              dot={{ r: 3, fill: s.color }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </RechartsLineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export default LineChart;
