import React, { useId, useState } from 'react';
import { Link } from 'react-router';
import clsx from 'clsx';
import { EvidenceBadge, SourceChip } from '../ui';
import { formatChartValue, type ChartUnit } from './ChartFrame';
import type { MetricName, Source } from '../../api/hooks';
import type { EvidenceClassKey } from '../../lib/theme';

export interface ProvenanceNumberProps {
  value: number | null | undefined;
  display?: React.ReactNode;
  unit?: ChartUnit;
  dp?: number;
  calcStepIds?: string[];
  sources?: (string | Source)[];
  allSources?: Source[];
  evidenceClass?: EvidenceClassKey;
  analysisId?: string;
  metric?: MetricName | string;
  year?: string;
  onInspectCalculation?: (metric?: string, year?: string, stepIds?: string[]) => void;
  className?: string;
}

export function ProvenanceNumber({
  value,
  display,
  unit = '£bn',
  dp,
  calcStepIds = [],
  sources = [],
  allSources = [],
  evidenceClass = 'model_scenario',
  analysisId,
  metric,
  year,
  onInspectCalculation,
  className,
}: ProvenanceNumberProps) {
  const [open, setOpen] = useState(false);
  const popoverId = useId();

  const formatted =
    display !== undefined ? display : formatChartValue(value, unit, dp);

  const normalizedSourceIds: string[] = sources.map((s) =>
    typeof s === 'string' ? s : s.source_id,
  );
  const mergedSources: Source[] = [
    ...allSources,
    ...sources.filter((s): s is Source => typeof s !== 'string'),
  ];

  const inspectorSearchParams = new URLSearchParams();
  if (metric) inspectorSearchParams.set('metric', metric);
  if (year) inspectorSearchParams.set('year', year);
  const queryString = inspectorSearchParams.toString();
  const inspectorHref = analysisId
    ? `/analyses/${analysisId}/assumptions${queryString ? `?${queryString}` : ''}`
    : undefined;

  return (
    <span
      className={clsx('relative inline-flex items-baseline', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        aria-describedby={open ? popoverId : undefined}
        onClick={() => {
          if (onInspectCalculation) {
            onInspectCalculation(metric, year, calcStepIds);
          } else {
            setOpen((prev) => !prev);
          }
        }}
        className="inline-flex cursor-pointer items-baseline gap-1 rounded px-0.5 font-semibold tabular-nums underline decoration-muted-foreground/50 decoration-dotted underline-offset-2 transition-colors hover:bg-primary/10 hover:text-primary hover:decoration-primary focus:ring-2 focus:ring-ring focus:outline-none"
      >
        <span>{formatted}</span>
      </button>

      {open && (
        <div
          id={popoverId}
          role="dialog"
          aria-label="Number provenance details"
          className="absolute bottom-full left-1/2 z-50 mb-1.5 w-72 -translate-x-1/2 rounded-sm border border-border bg-popover p-3 text-left text-xs text-popover-foreground shadow-lg shadow-black/40"
        >
          <div className="flex items-center justify-between gap-2 border-b border-border/60 pb-2">
            <span className="font-semibold text-foreground tabular-nums">
              {formatted}
            </span>
            <EvidenceBadge evidenceClass={evidenceClass} short />
          </div>

          <div className="mt-2 space-y-2">
            {calcStepIds.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                  Calculation Steps
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {calcStepIds.map((stepId) => (
                    <code
                      key={stepId}
                      className="rounded border border-primary/25 bg-primary/10 px-1.5 py-0.5 font-mono text-[11px] text-primary"
                    >
                      {stepId}
                    </code>
                  ))}
                </div>
              </div>
            )}

            {normalizedSourceIds.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                  Sources
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {normalizedSourceIds.map((sid) => (
                    <SourceChip
                      key={sid}
                      sourceId={sid}
                      sources={mergedSources}
                    />
                  ))}
                </div>
              </div>
            )}

            {calcStepIds.length === 0 && normalizedSourceIds.length === 0 && (
              <p className="text-[11px] text-muted-foreground">
                Traceable model output ({evidenceClass.replace(/_/g, ' ')}).
              </p>
            )}

            {(inspectorHref || onInspectCalculation) && (
              <div className="border-t border-border/60 pt-2">
                {inspectorHref ? (
                  <Link
                    to={inspectorHref}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    <span>Inspect in Calculation Inspector</span>
                    <span aria-hidden="true">→</span>
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => onInspectCalculation?.(metric, year, calcStepIds)}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    <span>Inspect in Calculation Inspector</span>
                    <span aria-hidden="true">→</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </span>
  );
}

export default ProvenanceNumber;
