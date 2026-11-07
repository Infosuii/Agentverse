import React, { useMemo } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame, formatChartValue, formatXAxisTick, type ChartUnit } from './ChartFrame';
import { EVIDENCE_CLASS_COLORS, type EvidenceClassKey } from '../../lib/theme';

export interface TimelinePoint {
  x: string | number;
  y: number;
  label?: string;
}

export interface TimelineEventMarker {
  x: string | number;
  y?: number;
  label: string;
  detail?: string;
  color?: string;
}

export interface TimelineChartProps {
  points: TimelinePoint[];
  events?: TimelineEventMarker[];
  unit?: ChartUnit;
  color?: string;
  seriesLabel?: string;
  title?: React.ReactNode;
  caption?: React.ReactNode;
  evidenceClass?: EvidenceClassKey;
  xLabel?: string;
  yLabel?: string;
  height?: number;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  formatValue?: (val: number) => string;
}

export function TimelineChart({
  points,
  events = [],
  unit = '%',
  color = EVIDENCE_CLASS_COLORS.observed_outcome,
  seriesLabel = 'Statutory rate',
  title,
  caption = 'Historical step-line trajectory with policy change events.',
  evidenceClass = 'observed_outcome',
  xLabel = 'Fiscal year',
  yLabel,
  height = 290,
  actions,
  footer,
  className,
  formatValue,
}: TimelineChartProps) {
  const isEmpty = useMemo(
    () => !Array.isArray(points) || points.length === 0,
    [points],
  );

  const eventMap = useMemo(() => {
    const m = new Map<string | number, TimelineEventMarker>();
    for (const ev of events) {
      m.set(ev.x, ev);
    }
    return m;
  }, [events]);

  const valFormatter = (v: number) =>
    formatValue ? formatValue(v) : formatChartValue(v, unit, 1);

  return (
    <ChartFrame
      title={title}
      caption={caption}
      evidenceClass={evidenceClass}
      unitLabel={unit}
      height={height}
      empty={isEmpty}
      emptyMessage="No historical timeline points available."
      actions={actions}
      footer={footer}
      className={className}
    >
      <ResponsiveContainer width="100%" height="100%">
        <RechartsLineChart
          data={points}
          margin={{ top: 18, right: 24, left: 12, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="x"
            tickFormatter={(x) => formatXAxisTick(x as string | number)}
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
            width={64}
            label={{
              value: yLabel ?? unit,
              angle: -90,
              position: 'insideLeft',
              style: { textAnchor: 'middle', fontSize: 11, fill: '#64748b' },
            }}
          />
          {events.map((ev, idx) => (
            <ReferenceLine
              key={`line-${ev.x}-${idx}`}
              x={ev.x}
              stroke={ev.color ?? '#94a3b8'}
              strokeDasharray="3 3"
              label={{
                value: ev.label,
                position: 'top',
                fontSize: 10,
                fill: '#334155',
              }}
            />
          ))}
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null;
              const pt = payload[0]?.payload as TimelinePoint | undefined;
              const ev = eventMap.get(label as string | number);
              if (!pt) return null;
              return (
                <div className="rounded-md border border-slate-300 bg-white p-2.5 text-xs shadow-md">
                  <div className="font-semibold text-slate-900">
                    {formatXAxisTick(pt.x)}
                  </div>
                  <div className="mt-0.5 text-slate-700 tabular-nums">
                    {seriesLabel}: <strong>{valFormatter(pt.y)}</strong>
                  </div>
                  {ev && (
                    <div className="mt-1 border-t border-slate-100 pt-1 text-[11px] text-blue-800">
                      <span className="font-semibold">{ev.label}</span>
                      {ev.detail && <span className="block text-slate-600">{ev.detail}</span>}
                    </div>
                  )}
                </div>
              );
            }}
          />
          <Line
            type="stepAfter"
            dataKey="y"
            name={seriesLabel}
            stroke={color}
            strokeWidth={2.5}
            dot={{ r: 2.5, fill: color }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
          {events.map((ev, idx) => {
            if (ev.y === undefined) return null;
            return (
              <ReferenceDot
                key={`dot-${ev.x}-${idx}`}
                x={ev.x}
                y={ev.y}
                r={4.5}
                fill={ev.color ?? '#2563eb'}
                stroke="#ffffff"
                strokeWidth={1.5}
              />
            );
          })}
        </RechartsLineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export default TimelineChart;
