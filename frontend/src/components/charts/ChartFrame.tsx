import React from 'react';
import clsx from 'clsx';
import { EvidenceBadge } from '../ui';
import { fmtFiscalYear, fmtGbpBn, fmtPct, fmtPp } from '../../lib/format';
import type { EvidenceClassKey } from '../../lib/theme';

export type ChartUnit = '£bn' | '%' | 'pp' | 'elasticity' | 'fraction' | 'years' | string;

export function formatChartValue(
  value: number | null | undefined,
  unit: ChartUnit = '£bn',
  dp?: number,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  const normalized = unit.trim();
  if (normalized === '£bn' || normalized === 'gbp_bn') {
    return fmtGbpBn(value, dp ?? 2);
  }
  if (normalized === '%' || normalized === 'pct') {
    return fmtPct(value, dp ?? 2);
  }
  if (normalized === 'pp') {
    return fmtPp(value, dp);
  }
  if (normalized === 'fraction' || normalized === 'elasticity') {
    return Number(value.toFixed(dp ?? 2)).toString();
  }
  const formatted = dp !== undefined ? value.toFixed(dp) : Number(value.toFixed(2)).toString();
  return normalized ? `${formatted} ${normalized}` : formatted;
}

export function formatXAxisTick(value: string | number): string {
  if (typeof value === 'number') {
    return String(value);
  }
  return fmtFiscalYear(value);
}

export interface ChartFrameProps {
  title?: React.ReactNode;
  caption?: React.ReactNode;
  evidenceClass?: EvidenceClassKey;
  unitLabel?: string;
  height?: number;
  empty?: boolean;
  emptyMessage?: string;
  footer?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function ChartFrame({
  title,
  caption = 'Model scenario projection under explicit assumptions.',
  evidenceClass = 'model_scenario',
  unitLabel,
  height = 280,
  empty = false,
  emptyMessage = 'No data available for this chart.',
  footer,
  actions,
  className,
  children,
}: ChartFrameProps) {
  return (
    <div
      className={clsx(
        'flex flex-col rounded-lg border border-border bg-card p-4',
        className,
      )}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-0.5">
          {title && (
            <h4 className="font-display text-sm font-semibold tracking-tight text-foreground">
              {title}
            </h4>
          )}
          {caption && (
            <p className="text-xs text-muted-foreground">
              {caption}
              {unitLabel ? ` (Unit: ${unitLabel})` : ''}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          <EvidenceBadge evidenceClass={evidenceClass} short />
        </div>
      </div>

      {empty ? (
        <div
          style={{ minHeight: Math.min(height, 220) }}
          className="flex flex-col items-center justify-center rounded-md border border-dashed border-border bg-muted/30 px-4 py-8 text-center"
        >
          <p className="text-xs font-medium text-muted-foreground">{emptyMessage}</p>
        </div>
      ) : (
        <div style={{ width: '100%', height }} className="min-w-0">
          {children}
        </div>
      )}

      {footer && (
        <div className="mt-3 border-t border-border/60 pt-2.5 text-xs text-muted-foreground">
          {footer}
        </div>
      )}
    </div>
  );
}
