import React, { useMemo } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame, formatChartValue, formatXAxisTick, type ChartUnit } from './ChartFrame';
import { MC_BAND_STYLE, type EvidenceClassKey } from '../../lib/theme';

export interface FanBandPoint {
  x: string | number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface FanOverlaySeries {
  id: string;
  label: string;
  color: string;
  points: { x: string | number; y: number | null }[];
  dashed?: boolean;
}

export interface EmpiricalBandPoint {
  x: string | number;
  p5: number;
  p95: number;
}

export interface FanChartProps {
  bands: FanBandPoint[];
  overlays?: FanOverlaySeries[];
  empiricalBands?: EmpiricalBandPoint[];
  empiricalLabel?: string;
  intervalNote?: string;
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

interface InternalFanRow {
  x: string | number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  outerRange: [number, number];
  innerRange: [number, number];
  empP5?: number;
  empP95?: number;
  [overlayKey: string]: unknown;
}

export function FanChart({
  bands,
  overlays = [],
  empiricalBands,
  empiricalLabel = 'Empirical prediction interval (backtest-calibrated)',
  intervalNote = 'assumption-driven ranges, not statistical prediction intervals; exclude model and data uncertainty',
  unit = '£bn',
  title,
  caption = 'Monte Carlo assumption-driven uncertainty distribution across fiscal years.',
  evidenceClass = 'model_scenario',
  showZeroReference = true,
  xLabel = 'Fiscal year',
  yLabel,
  height = 310,
  actions,
  footer,
  className,
  formatValue,
}: FanChartProps) {
  const { rows, isEmpty } = useMemo(() => {
    if (!Array.isArray(bands) || bands.length === 0) {
      return { rows: [] as InternalFanRow[], isEmpty: true };
    }

    const empMap = new Map<string | number, EmpiricalBandPoint>();
    for (const eb of empiricalBands ?? []) {
      empMap.set(eb.x, eb);
    }

    const overlayMaps = new Map<string, Map<string | number, number | null>>();
    for (const ov of overlays) {
      const m = new Map<string | number, number | null>();
      for (const pt of ov.points) {
        m.set(pt.x, pt.y);
      }
      overlayMaps.set(ov.id, m);
    }

    const built: InternalFanRow[] = bands.map((b) => {
      const emp = empMap.get(b.x);
      const row: InternalFanRow = {
        x: b.x,
        p5: b.p5,
        p25: b.p25,
        p50: b.p50,
        p75: b.p75,
        p95: b.p95,
        outerRange: [b.p5, b.p95],
        innerRange: [b.p25, b.p75],
      };
      if (emp) {
        row.empP5 = emp.p5;
        row.empP95 = emp.p95;
      }
      for (const ov of overlays) {
        row[`overlay_${ov.id}`] = overlayMaps.get(ov.id)?.get(b.x) ?? null;
      }
      return row;
    });

    return { rows: built, isEmpty: built.length === 0 };
  }, [bands, empiricalBands, overlays]);

  const valFormatter = (v: number) =>
    formatValue ? formatValue(v) : formatChartValue(v, unit);

  const defaultFooter = intervalNote ? (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-slate-600">
        <strong className="font-semibold text-slate-700">Interval note:</strong>{' '}
        <span>{intervalNote}</span>
      </span>
      {footer}
    </div>
  ) : (
    footer
  );

  return (
    <ChartFrame
      title={title}
      caption={caption}
      evidenceClass={evidenceClass}
      unitLabel={unit}
      height={height}
      empty={isEmpty}
      emptyMessage="No Monte Carlo distribution bands available."
      actions={actions}
      footer={defaultFooter}
      className={className}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={rows}
          margin={{ top: 10, right: 20, left: 12, bottom: 20 }}
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
            labelFormatter={(label) => `Fiscal year: ${formatXAxisTick(label as string | number)}`}
            formatter={(value: unknown, name: string) => {
              if (Array.isArray(value) && value.length === 2) {
                return [
                  `${valFormatter(Number(value[0]))} to ${valFormatter(Number(value[1]))}`,
                  name,
                ];
              }
              return [valFormatter(Number(value)), name];
            }}
            contentStyle={{
              fontSize: 12,
              borderRadius: 6,
              borderColor: '#cbd5e1',
            }}
          />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 11 }} />
          <Area
            type="monotone"
            dataKey={(d: InternalFanRow) => [d.p5, d.p95]}
            name="p5–p95 range"
            stroke="none"
            fill={MC_BAND_STYLE.color}
            fillOpacity={MC_BAND_STYLE.p5_p95_opacity}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey={(d: InternalFanRow) => [d.p25, d.p75]}
            name="p25–p75 range"
            stroke="none"
            fill={MC_BAND_STYLE.color}
            fillOpacity={MC_BAND_STYLE.p25_p75_opacity}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="p50"
            name="Median (p50)"
            stroke={MC_BAND_STYLE.color}
            strokeWidth={2.5}
            dot={{ r: 3, fill: MC_BAND_STYLE.color }}
            isAnimationActive={false}
          />
          {empiricalBands && empiricalBands.length > 0 && (
            <>
              <Line
                type="monotone"
                dataKey="empP95"
                name={`${empiricalLabel} (upper)`}
                stroke="#0f766e"
                strokeWidth={1.75}
                strokeDasharray="5 4"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="empP5"
                name={`${empiricalLabel} (lower)`}
                stroke="#0f766e"
                strokeWidth={1.75}
                strokeDasharray="5 4"
                dot={false}
                isAnimationActive={false}
              />
            </>
          )}
          {overlays.map((ov) => (
            <Line
              key={ov.id}
              type="monotone"
              dataKey={`overlay_${ov.id}`}
              name={ov.label}
              stroke={ov.color}
              strokeWidth={2}
              strokeDasharray={ov.dashed ? '6 4' : undefined}
              dot={{ r: 2.5, fill: ov.color }}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export default FanChart;
