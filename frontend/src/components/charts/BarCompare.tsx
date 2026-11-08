import React, { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame, formatChartValue, formatXAxisTick, type ChartUnit } from './ChartFrame';
import { CHART_THEME, EVIDENCE_CLASS_COLORS, type EvidenceClassKey } from '../../lib/theme';

export interface BarCompareSeries {
  id: string;
  label: string;
  color?: string;
  evidenceClass?: EvidenceClassKey;
}

export interface BarCompareRow {
  category: string;
  [seriesId: string]: string | number | null | undefined;
}

export interface BarCompareProps {
  data: BarCompareRow[];
  series: BarCompareSeries[];
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
}

export function BarCompare({
  data,
  series,
  unit = '£bn',
  title,
  caption = 'Grouped comparison across categories and evidence sources.',
  evidenceClass = 'model_scenario',
  showZeroReference = true,
  xLabel = 'Category',
  yLabel,
  height = 300,
  actions,
  footer,
  className,
  formatValue,
}: BarCompareProps) {
  const isEmpty = useMemo(
    () => !Array.isArray(data) || data.length === 0 || !Array.isArray(series) || series.length === 0,
    [data, series],
  );

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
      emptyMessage="No comparison categories available."
      actions={actions}
      footer={footer}
      className={className}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 10, right: 20, left: 12, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
          <XAxis
            dataKey="category"
            tickFormatter={(x) => formatXAxisTick(x as string | number)}
            tick={{ fontSize: 11, fill: CHART_THEME.tick }}
            label={{
              value: xLabel,
              position: 'insideBottom',
              offset: -10,
              fontSize: 11,
              fill: CHART_THEME.axisLabel,
            }}
          />
          <YAxis
            tickFormatter={(v: number) => valFormatter(Number(v))}
            tick={{ fontSize: 11, fill: CHART_THEME.tick }}
            width={72}
            label={{
              value: yLabel ?? unit,
              angle: -90,
              position: 'insideLeft',
              style: { textAnchor: 'middle', fontSize: 11, fill: CHART_THEME.axisLabel },
            }}
          />
          {showZeroReference && (
            <ReferenceLine y={0} stroke={CHART_THEME.reference} strokeDasharray="4 4" />
          )}
          <RechartsTooltip
            cursor={{ fill: CHART_THEME.cursor }}
            labelFormatter={(label) => `${xLabel}: ${formatXAxisTick(label as string | number)}`}
            formatter={(value: unknown, name: string) => {
              const s = series.find((item) => item.id === name || item.label === name);
              const num = typeof value === 'number' ? value : Number(value);
              return [valFormatter(num), s?.label ?? name];
            }}
            contentStyle={CHART_THEME.tooltip}
            labelStyle={CHART_THEME.tooltipLabel}
          />
          <Legend verticalAlign="top" height={28} wrapperStyle={CHART_THEME.legend} />
          {series.map((s) => {
            const fill =
              s.color ??
              (s.evidenceClass
                ? EVIDENCE_CLASS_COLORS[s.evidenceClass]
                : EVIDENCE_CLASS_COLORS.model_scenario);
            return (
              <Bar
                key={s.id}
                dataKey={s.id}
                name={s.label}
                fill={fill}
                radius={[3, 3, 0, 0]}
                isAnimationActive={false}
              />
            );
          })}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export default BarCompare;
