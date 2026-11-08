import React, { useEffect, useState } from 'react';
import clsx from 'clsx';
import { EvidenceBadge } from '../ui';
import { useThemeMode, type ThemeMode } from '../../lib/themeMode';
import type { components } from '../../api/schema';

type SimulateRequest = components['schemas']['SimulateRequest'];
export type MonteCarloMetric = components['schemas']['MetricProjection']['metric'];

/**
 * Where the draws come from:
 * - `analysis`: a finished analysis; the server re-runs its exact draws (same parameters and seed).
 * - `simulate`: the slider view; the server runs the same draws `/api/simulate` summarises.
 */
export type MonteCarloSource =
  | { kind: 'analysis'; analysisId: string }
  | { kind: 'simulate'; request: SimulateRequest };

export interface MonteCarloChartProps {
  source: MonteCarloSource;
  metric?: MonteCarloMetric;
  /** Overlay the backtest-calibrated interval (behavioural revenue only). */
  empirical?: boolean;
  paths?: number;
  title?: React.ReactNode;
  caption?: React.ReactNode;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

export function monteCarloChartUrl(
  source: MonteCarloSource,
  metric: MonteCarloMetric,
  empirical: boolean,
  paths: number,
  theme?: ThemeMode,
): string {
  const query = new URLSearchParams({
    metric,
    paths: String(paths),
    empirical: String(empirical),
  });
  if (theme) query.set('theme', theme);
  return source.kind === 'analysis'
    ? `/api/analyses/${encodeURIComponent(source.analysisId)}/charts/montecarlo.png?${query}`
    : `/api/simulate/montecarlo.png?${query}`;
}

/**
 * Monte Carlo trajectories rendered server-side with matplotlib from the REAL draws: every grey line is one
 * simulated path, and the shaded bands, percentile lines and mean are computed from all draws (issue #98).
 */
export function MonteCarloChart({
  source,
  metric = 'revenue_behavioural_gbp_bn',
  empirical = false,
  paths = 60,
  title = 'Monte Carlo trajectories',
  caption = 'Each grey line is one simulated path; bands and percentile lines use every draw. Assumption-driven ranges, not prediction intervals.',
  actions,
  footer,
  className,
}: MonteCarloChartProps) {
  const theme = useThemeMode();
  const url = monteCarloChartUrl(source, metric, empirical, paths, theme);
  const requestKey = source.kind === 'simulate' ? JSON.stringify(source.request) : '';
  const [src, setSrc] = useState<string | null>(source.kind === 'analysis' ? url : null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setError(null);
    setLoading(true);
    if (source.kind === 'analysis') {
      setSrc(url);
      return;
    }
    const controller = new AbortController();
    let objectUrl: string | null = null;
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: requestKey,
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const body = (await res.json().catch(() => null)) as { error?: string } | null;
          throw new Error(body?.error ?? `Chart request failed (${res.status})`);
        }
        return res.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : 'Chart request failed');
        setLoading(false);
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // `requestKey` captures the request body; `url` captures metric, paths and the overlay.
  }, [url, requestKey, source.kind]);

  return (
    <div className={clsx('flex flex-col rounded-lg border border-border bg-card p-4', className)}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-0.5">
          {title && (
            <h4 className="font-display text-sm font-semibold tracking-tight text-foreground">
              {title}
            </h4>
          )}
          {caption && <p className="text-xs text-muted-foreground">{caption}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          <EvidenceBadge evidenceClass="model_scenario" short />
        </div>
      </div>

      <div
        className="relative w-full overflow-hidden rounded-md bg-card"
        style={{ aspectRatio: '10 / 5.8' }}
      >
        {error ? (
          <div className="flex h-full items-center justify-center px-4 text-center text-xs text-muted-foreground">
            {error}
          </div>
        ) : (
          src && (
            <img
              src={src}
              alt="Monte Carlo trajectories: a sample of real simulated paths with the 5–95% and 25–75% ranges, 5th and 95th percentiles and the mean of all draws."
              className={clsx('h-full w-full object-contain transition-opacity', loading && 'opacity-40')}
              onLoad={() => setLoading(false)}
              onError={() => {
                setError('The chart could not be rendered.');
                setLoading(false);
              }}
            />
          )
        )}
        {loading && !error && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
            Rendering chart…
          </div>
        )}
      </div>

      {footer && (
        <div className="mt-3 border-t border-border/60 pt-2.5 text-xs text-muted-foreground">
          {footer}
        </div>
      )}
    </div>
  );
}
