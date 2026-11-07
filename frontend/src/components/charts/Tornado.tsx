import React, { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame, formatChartValue, type ChartUnit } from './ChartFrame';
import { SCENARIO_COLORS, type EvidenceClassKey } from '../../lib/theme';

export interface TornadoInputItem {
  label: string;
  parameter?: string;
  low: number;
  high: number;
  lowInput?: number;
  highInput?: number;
  swing?: number;
}

export interface TornadoProps {
  items: TornadoInputItem[];
  base: number;
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

interface InternalTornadoRow {
  label: string;
  parameter?: string;
  low: number;
  high: number;
  lowInput?: number;
  highInput?: number;
  range: [number, number];
  swing: number;
}

export function Tornado({
  items,
  base,
  unit = '£bn',
  title,
  caption = 'One-at-a-time parameter sensitivity around the central scenario.',
  evidenceClass = 'model_scenario',
  height,
  actions,
  footer,
  className,
  formatValue,
}: TornadoProps) {
  const { rows, isEmpty } = useMemo(() => {
    if (!Array.isArray(items) || items.length === 0) {
      return { rows: [] as InternalTornadoRow[], isEmpty: true };
    }

    const built: InternalTornadoRow[] = items
      .map((item) => {
        const minOut = Math.min(item.low, item.high);
        const maxOut = Math.max(item.low, item.high);
        const swing =
          item.swing !== undefined ? Math.abs(item.swing) : Math.abs(item.high - item.low);
        return {
          label: item.label,
          parameter: item.parameter,
          low: item.low,
          high: item.high,
          lowInput: item.lowInput,
          highInput: item.highInput,
          range: [minOut, maxOut] as [number, number],
          swing,
        };
      })
      .sort((a, b) => b.swing - a.swing);

    return { rows: built, isEmpty: built.length === 0 };
  }, [items]);

  const valFormatter = (v: number) =>
    formatValue ? formatValue(v) : formatChartValue(v, unit);

  const computedHeight = height ?? Math.max(240, rows.length * 36 + 70);

  return (
    <ChartFrame
      title={title}
      caption={caption}
      evidenceClass={evidenceClass}
      unitLabel={unit}
      height={computedHeight}
      empty={isEmpty}
      emptyMessage="No sensitivity tornado items available for this metric."
      actions={actions}
      footer={
        footer ?? (
          <span>
            Central baseline: <strong className="tabular-nums">{valFormatter(base)}</strong>
          </span>
        )
      }
      className={className}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 10, right: 24, left: 16, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            type="number"
            domain={['auto', 'auto']}
            tickFormatter={(v: number) => valFormatter(Number(v))}
            tick={{ fontSize: 11, fill: '#475569' }}
            label={{
              value: `Output (${unit})`,
              position: 'insideBottom',
              offset: -10,
              fontSize: 11,
              fill: '#64748b',
            }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={175}
            tick={{ fontSize: 11, fill: '#334155' }}
          />
          <ReferenceLine
            x={base}
            stroke={SCENARIO_COLORS.central}
            strokeWidth={2}
            strokeDasharray="4 3"
          />
          <RechartsTooltip
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null;
              const row = payload[0]?.payload as InternalTornadoRow | undefined;
              if (!row) return null;
              return (
                <div className="rounded-md border border-slate-300 bg-white p-2.5 text-xs shadow-md">
                  <div className="font-semibold text-slate-900">{row.label}</div>
                  <div className="mt-1 space-y-0.5 text-slate-600 tabular-nums">
                    <div>
                      At low input
                      {row.lowInput !== undefined ? ` (${row.lowInput})` : ''}:{' '}
                      <strong className="text-slate-900">{valFormatter(row.low)}</strong>
                    </div>
                    <div>
                      At high input
                      {row.highInput !== undefined ? ` (${row.highInput})` : ''}:{' '}
                      <strong className="text-slate-900">{valFormatter(row.high)}</strong>
                    </div>
                    <div>
                      Central base: <strong>{valFormatter(base)}</strong> · Swing:{' '}
                      <strong>{valFormatter(row.swing)}</strong>
                    </div>
                  </div>
                </div>
              );
            }}
          />
          <Bar
            dataKey="range"
            name="Sensitivity range"
            radius={[3, 3, 3, 3]}
            isAnimationActive={false}
          >
            {rows.map((entry, idx) => (
              <Cell
                key={`${entry.label}-${idx}`}
                fill={SCENARIO_COLORS.central}
                fillOpacity={0.78}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export default Tornado;
