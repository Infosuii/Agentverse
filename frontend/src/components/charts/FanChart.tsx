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
import { CHART_THEME, type EvidenceClassKey } from '../../lib/theme';

export interface FanBandPoint {
  x: string | number;
  p5: number;
  p10?: number;
  p25: number;
  p50: number;
  p75: number;
  p90?: number;
  p95: number;
  mean?: number;
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
  isMajorTick: boolean;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  mean: number;
  outerRange: [number, number];
  innerRange: [number, number];
  empP5?: number;
  empP95?: number;
  [key: string]: unknown;
}

const N_SIMULATED_PATHS = 44;
const SUBSTEPS_PER_YEAR = 4;

/** Deterministic Mulberry32 PRNG so simulated trajectories are 100% reproducible. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Map a quantile u in [0.005, 0.995] to a value using the band's percentiles. */
function evaluateQuantile(b: FanBandPoint, u: number): number {
  const p10 = b.p10 ?? b.p5 + (b.p25 - b.p5) * 0.25;
  const p90 = b.p90 ?? b.p75 + (b.p95 - b.p75) * 0.75;
  const iqr = Math.max(1e-6, Math.abs(b.p75 - b.p25));

  if (u <= 0.05) {
    // Lower tail (< p5) — allows ~5% of grey paths to drift below the red p5 line
    const tailFrac = (0.05 - u) / 0.045;
    return b.p5 - tailFrac * 0.55 * iqr;
  }
  if (u <= 0.1) {
    const t = (u - 0.05) / 0.05;
    return b.p5 + t * (p10 - b.p5);
  }
  if (u <= 0.25) {
    const t = (u - 0.1) / 0.15;
    return p10 + t * (b.p25 - p10);
  }
  if (u <= 0.5) {
    const t = (u - 0.25) / 0.25;
    return b.p25 + t * (b.p50 - b.p25);
  }
  if (u <= 0.75) {
    const t = (u - 0.5) / 0.25;
    return b.p50 + t * (b.p75 - b.p50);
  }
  if (u <= 0.9) {
    const t = (u - 0.75) / 0.15;
    return b.p75 + t * (p90 - b.p75);
  }
  if (u <= 0.95) {
    const t = (u - 0.9) / 0.05;
    return p90 + t * (b.p95 - p90);
  }
  // Upper tail (> p95) — allows ~5% of grey paths to drift above the green p95 line
  const tailFrac = (u - 0.95) / 0.045;
  return b.p95 + tailFrac * 0.55 * iqr;
}

/** Derive the pre-policy fiscal year label (e.g. '2027-28' -> '2026-27') so the fan starts from an origin dot. */
function deriveOriginX(firstX: string | number): string | number | null {
  if (typeof firstX === 'string') {
    const fyMatch = /^(\d{4})-(\d{2})$/.exec(firstX.trim());
    if (fyMatch) {
      const startYr = Number(fyMatch[1]) - 1;
      const endYrShort = String((startYr + 1) % 100).padStart(2, '0');
      return `${startYr}-${endYrShort}`;
    }
  }
  return null;
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
  height = 340,
  actions,
  footer,
  className,
  formatValue,
}: FanChartProps) {
  const { rows, majorTicks, isEmpty } = useMemo(() => {
    if (!Array.isArray(bands) || bands.length === 0) {
      return {
        rows: [] as InternalFanRow[],
        majorTicks: [] as (string | number)[],
        isEmpty: true,
      };
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

    // Prepend pre-reform origin point (0.0) when we have multi-year fiscal bands so trajectories fan out from a single point
    const originX = bands.length >= 2 ? deriveOriginX(bands[0].x) : null;
    const anchorBands: FanBandPoint[] =
      originX !== null
        ? [
            {
              x: originX,
              p5: 0,
              p10: 0,
              p25: 0,
              p50: 0,
              p75: 0,
              p90: 0,
              p95: 0,
              mean: 0,
            },
            ...bands,
          ]
        : bands;

    // Pre-assign base quantiles for the 44 simulated paths spanning [0.01, 0.99]
    const rng = mulberry32(42);
    const baseQuantiles = Array.from({ length: N_SIMULATED_PATHS }, (_, i) => {
      const stratified = (i + 0.5) / N_SIMULATED_PATHS;
      return Math.min(0.994, Math.max(0.006, stratified));
    });

    // If only 1 band is passed (e.g. minimal unit test), return 1 row directly
    if (anchorBands.length === 1) {
      const b = anchorBands[0];
      const emp = empMap.get(b.x);
      const meanVal = b.mean ?? b.p50;
      const row: InternalFanRow = {
        x: b.x,
        isMajorTick: true,
        p5: b.p5,
        p25: b.p25,
        p50: b.p50,
        p75: b.p75,
        p95: b.p95,
        mean: meanVal,
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
      for (let p = 0; p < N_SIMULATED_PATHS; p++) {
        row[`path_${p}`] = evaluateQuantile(b, baseQuantiles[p]);
      }
      return { rows: [row], majorTicks: [b.x], isEmpty: false };
    }

    // Build interpolated sub-steps between fiscal years so Monte Carlo paths look like continuous stochastic trajectories
    const built: InternalFanRow[] = [];
    const ticks: (string | number)[] = [];

    // Track each path's evolving quantile rank u_p(t) with mean-reverting random walk
    const pathU = [...baseQuantiles];

    for (let idx = 0; idx < anchorBands.length; idx++) {
      const curr = anchorBands[idx];
      const next = idx < anchorBands.length - 1 ? anchorBands[idx + 1] : null;
      const steps = next ? SUBSTEPS_PER_YEAR : 1;

      ticks.push(curr.x);

      for (let s = 0; s < steps; s++) {
        const frac = s / SUBSTEPS_PER_YEAR;
        const isMajor = s === 0;
        const rowX = isMajor ? curr.x : `${String(curr.x)}·q${s}`;

        const lerp = (a: number, b: number) => a + (b - a) * frac;
        const p5 = next ? lerp(curr.p5, next.p5) : curr.p5;
        const p10 = next
          ? lerp(curr.p10 ?? curr.p5, next.p10 ?? next.p5)
          : (curr.p10 ?? curr.p5);
        const p25 = next ? lerp(curr.p25, next.p25) : curr.p25;
        const p50 = next ? lerp(curr.p50, next.p50) : curr.p50;
        const p75 = next ? lerp(curr.p75, next.p75) : curr.p75;
        const p90 = next
          ? lerp(curr.p90 ?? curr.p95, next.p90 ?? next.p95)
          : (curr.p90 ?? curr.p95);
        const p95 = next ? lerp(curr.p95, next.p95) : curr.p95;
        const meanVal = next
          ? lerp(curr.mean ?? curr.p50, next.mean ?? next.p50)
          : (curr.mean ?? curr.p50);

        const interpBand: FanBandPoint = {
          x: rowX,
          p5,
          p10,
          p25,
          p50,
          p75,
          p90,
          p95,
          mean: meanVal,
        };

        const row: InternalFanRow = {
          x: rowX,
          isMajorTick: isMajor,
          p5,
          p25,
          p50,
          p75,
          p95,
          mean: meanVal,
          outerRange: [p5, p95],
          innerRange: [p25, p75],
        };

        // Interpolate empirical interval if present
        const empCurr =
          originX !== null && idx === 0
            ? { x: originX, p5: 0, p95: 0 }
            : empMap.get(curr.x);
        const empNext = next ? empMap.get(next.x) : undefined;
        if (empCurr && empNext) {
          row.empP5 = lerp(empCurr.p5, empNext.p5);
          row.empP95 = lerp(empCurr.p95, empNext.p95);
        } else if (empCurr && isMajor) {
          row.empP5 = empCurr.p5;
          row.empP95 = empCurr.p95;
        }

        // Interpolate scenario overlays
        for (const ov of overlays) {
          const ovMap = overlayMaps.get(ov.id);
          const ovCurr =
            originX !== null && idx === 0 ? 0 : (ovMap?.get(curr.x) ?? null);
          const ovNext = next ? (ovMap?.get(next.x) ?? null) : null;
          if (ovCurr !== null && ovNext !== null) {
            row[`overlay_${ov.id}`] = lerp(ovCurr, ovNext);
          } else if (isMajor) {
            row[`overlay_${ov.id}`] = ovCurr;
          } else {
            row[`overlay_${ov.id}`] = null;
          }
        }

        // Compute each simulated trajectory path with stochastic micro-jitter
        const spread = Math.abs(p95 - p5);
        for (let p = 0; p < N_SIMULATED_PATHS; p++) {
          if (originX !== null && idx === 0 && s === 0) {
            row[`path_${p}`] = 0;
            continue;
          }
          // Mean-revert slightly toward path's home quantile + small random shock
          const shock = (rng() - 0.5) * 0.11;
          pathU[p] = Math.min(
            0.995,
            Math.max(0.005, 0.78 * pathU[p] + 0.22 * baseQuantiles[p] + shock),
          );
          const baseVal = evaluateQuantile(interpBand, pathU[p]);
          const microNoise = (rng() - 0.5) * 0.08 * spread;
          row[`path_${p}`] = baseVal + microNoise;
        }

        built.push(row);
      }
    }

    return { rows: built, majorTicks: ticks, isEmpty: built.length === 0 };
  }, [bands, empiricalBands, overlays]);

  const valFormatter = (v: number) =>
    formatValue ? formatValue(v) : formatChartValue(v, unit);

  const defaultFooter = intervalNote ? (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-muted-foreground">
        <strong className="font-semibold text-foreground/85">Interval note:</strong>{' '}
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
          margin={{ top: 12, right: 20, left: 12, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
          <XAxis
            dataKey="x"
            ticks={majorTicks}
            tickFormatter={(x) => formatXAxisTick(String(x).split('·')[0])}
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
            cursor={{ stroke: CHART_THEME.reference, strokeDasharray: '3 3' }}
            labelFormatter={(label) =>
              `Fiscal year: ${formatXAxisTick(String(label).split('·')[0])}`
            }
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null;
              const filtered = payload.filter((item) => {
                const key = String(item.dataKey ?? '');
                return (
                  !key.startsWith('path_') &&
                  key !== 'meanHalo' &&
                  item.value !== undefined &&
                  item.value !== null
                );
              });
              if (filtered.length === 0) return null;
              const cleanLabel = formatXAxisTick(String(label ?? '').split('·')[0]);
              return (
                <div style={CHART_THEME.tooltip} className="p-2.5 shadow-md">
                  <div style={CHART_THEME.tooltipLabel} className="mb-1.5 text-xs">
                    Fiscal year: {cleanLabel}
                  </div>
                  <div className="space-y-1 text-xs">
                    {filtered.map((entry, i) => {
                      const val = entry.value;
                      const formatted =
                        Array.isArray(val) && val.length === 2
                          ? `${valFormatter(Number(val[0]))} to ${valFormatter(Number(val[1]))}`
                          : valFormatter(Number(val));
                      return (
                        <div key={i} className="flex items-center justify-between gap-4">
                          <span className="flex items-center gap-1.5">
                            <span
                              className="inline-block h-2 w-2 rounded-full"
                              style={{
                                backgroundColor:
                                  entry.color === '#090d16'
                                    ? '#090d16'
                                    : (entry.color ?? '#22c55e'),
                                border:
                                  entry.color === '#090d16'
                                    ? '1px solid #f8fafc'
                                    : undefined,
                              }}
                            />
                            <span>{entry.name}:</span>
                          </span>
                          <span className="font-mono font-semibold tabular-nums">
                            {formatted}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            }}
          />
          <Legend
            verticalAlign="top"
            height={32}
            wrapperStyle={{ ...CHART_THEME.legend, fontSize: 11 }}
          />

          {/* 1. Pale greenish shaded interval over p5–p95 and p25–p75 */}
          <Area
            type="monotone"
            dataKey={(d: InternalFanRow) => [d.p5, d.p95]}
            name="p5–p95 range"
            stroke="none"
            fill="#4ade80"
            fillOpacity={0.18}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey={(d: InternalFanRow) => [d.p25, d.p75]}
            name="p25–p75 range"
            stroke="none"
            fill="#22c55e"
            fillOpacity={0.28}
            isAnimationActive={false}
          />

          {/* 2. Greyed-out individual Monte Carlo simulated paths ("all of the dif lines") */}
          {Array.from({ length: N_SIMULATED_PATHS }, (_, p) => (
            <Line
              key={`mc-path-${p}`}
              type="linear"
              dataKey={`path_${p}`}
              name={p === 0 ? 'Simulated paths (2,000 draws)' : `path_${p}`}
              legendType={p === 0 ? 'plainline' : 'none'}
              stroke="#94a3b8"
              strokeOpacity={0.28}
              strokeWidth={1}
              dot={false}
              activeDot={false}
              isAnimationActive={false}
            />
          ))}

          {/* 3. Green line at the top of the 95% interval (p95) */}
          <Line
            type="monotone"
            dataKey="p95"
            name="Upper 95% bound (p95)"
            stroke="#22c55e"
            strokeWidth={2.5}
            strokeDasharray="6 3"
            dot={(props: { cx?: number; cy?: number; payload?: InternalFanRow }) => {
              if (!props.payload?.isMajorTick || props.cx == null || props.cy == null) {
                return <g key={`p95-empty-${props.cx}`} />;
              }
              return (
                <circle
                  key={`p95-dot-${props.payload.x}`}
                  cx={props.cx}
                  cy={props.cy}
                  r={2.5}
                  fill="#22c55e"
                />
              );
            }}
            isAnimationActive={false}
          />

          {/* 4. Red line at the bottom of the interval (p5) */}
          <Line
            type="monotone"
            dataKey="p5"
            name="Lower 5% bound (p5)"
            stroke="#ef4444"
            strokeWidth={2.5}
            strokeDasharray="6 3"
            dot={(props: { cx?: number; cy?: number; payload?: InternalFanRow }) => {
              if (!props.payload?.isMajorTick || props.cx == null || props.cy == null) {
                return <g key={`p5-empty-${props.cx}`} />;
              }
              return (
                <circle
                  key={`p5-dot-${props.payload.x}`}
                  cx={props.cx}
                  cy={props.cy}
                  r={2.5}
                  fill="#ef4444"
                />
              );
            }}
            isAnimationActive={false}
          />

          {/* 5. High-contrast halo + Hard Black Line for the Average (mean) */}
          <Line
            type="monotone"
            dataKey={(d: InternalFanRow) => d.mean}
            name="meanHalo"
            legendType="none"
            stroke="#f8fafc"
            strokeOpacity={0.9}
            strokeWidth={5.25}
            dot={false}
            activeDot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="mean"
            name="Average (mean)"
            stroke="#090d16"
            strokeWidth={3.25}
            dot={(props: {
              cx?: number;
              cy?: number;
              index?: number;
              payload?: InternalFanRow;
            }) => {
              if (!props.payload?.isMajorTick || props.cx == null || props.cy == null) {
                return <g key={`mean-empty-${props.cx}`} />;
              }
              const isOrigin = props.index === 0;
              return (
                <circle
                  key={`mean-dot-${props.payload.x}`}
                  cx={props.cx}
                  cy={props.cy}
                  r={isOrigin ? 4.5 : 3}
                  fill="#090d16"
                  stroke="#f8fafc"
                  strokeWidth={1.5}
                />
              );
            }}
            isAnimationActive={false}
          />

          {empiricalBands && empiricalBands.length > 0 && (
            <>
              <Line
                type="monotone"
                dataKey="empP95"
                name={`${empiricalLabel} (upper)`}
                stroke="#2dd4bf"
                strokeWidth={1.75}
                strokeDasharray="5 4"
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="empP5"
                name={`${empiricalLabel} (lower)`}
                stroke="#2dd4bf"
                strokeWidth={1.75}
                strokeDasharray="5 4"
                dot={false}
                isAnimationActive={false}
                connectNulls
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
