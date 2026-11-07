import React, { useId, useState } from 'react';
import clsx from 'clsx';
import type { Confidence, EvidenceClass, Mode, Source } from '../../api/hooks';
import { useHealth } from '../../api/hooks';
import {
  EVIDENCE_CLASS_TOKENS,
  VERIFICATION_OVERALL_TOKENS,
  VERIFICATION_STATUS_TOKENS,
  WITHHELD_HATCH_CLASS,
  type EvidenceClassKey,
  type VerificationOverallKey,
  type VerificationStatusKey,
} from '../../lib/theme';

/* -------------------------------------------------------------------------- */
/* Card                                                                       */
/* -------------------------------------------------------------------------- */

export interface CardProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hatched?: boolean;
}

export function Card({
  title,
  subtitle,
  actions,
  padding = 'md',
  hatched = false,
  className,
  children,
  ...rest
}: CardProps) {
  const padClass = {
    none: '',
    sm: 'p-3',
    md: 'p-4 sm:p-5',
    lg: 'p-6',
  }[padding];

  return (
    <div
      className={clsx(
        'rounded-lg border border-slate-200 bg-white shadow-xs',
        hatched && WITHHELD_HATCH_CLASS,
        className,
      )}
      {...rest}
    >
      {(title || subtitle || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 px-4 py-3 sm:px-5">
          <div>
            {title && (
              <h3 className="text-sm font-semibold tracking-tight text-slate-900">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={padClass}>{children}</div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Badge                                                                      */
/* -------------------------------------------------------------------------- */

export type BadgeVariant =
  | 'slate'
  | 'blue'
  | 'green'
  | 'amber'
  | 'red'
  | 'violet'
  | 'rose';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: 'xs' | 'sm';
  dotColor?: string;
}

const BADGE_VARIANTS: Record<BadgeVariant, string> = {
  slate: 'bg-slate-100 text-slate-800 border-slate-300',
  blue: 'bg-blue-50 text-blue-800 border-blue-300',
  green: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  amber: 'bg-amber-50 text-amber-800 border-amber-300',
  red: 'bg-red-50 text-red-800 border-red-300',
  violet: 'bg-violet-50 text-violet-800 border-violet-300',
  rose: 'bg-rose-50 text-rose-800 border-rose-300',
};

export function Badge({
  variant = 'slate',
  size = 'xs',
  dotColor,
  className,
  children,
  ...rest
}: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-md border font-medium whitespace-nowrap',
        size === 'xs' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
        BADGE_VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {dotColor && (
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ backgroundColor: dotColor }}
        />
      )}
      {children}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* EvidenceBadge                                                              */
/* -------------------------------------------------------------------------- */

export interface EvidenceBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  evidenceClass?: EvidenceClass | EvidenceClassKey;
  kind?: EvidenceClass | EvidenceClassKey;
  value?: EvidenceClass | EvidenceClassKey;
  short?: boolean;
}

export function EvidenceBadge({
  evidenceClass,
  kind,
  value,
  short = false,
  className,
  ...rest
}: EvidenceBadgeProps) {
  const key = (evidenceClass ?? kind ?? value ?? 'model_scenario') as EvidenceClassKey;
  const token = EVIDENCE_CLASS_TOKENS[key] ?? EVIDENCE_CLASS_TOKENS.model_scenario;
  const text = short ? token.shortLabel : token.label;

  return (
    <span
      role="status"
      aria-label={`Evidence class: ${token.label}`}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        token.bgClass,
        token.textClass,
        token.borderClass,
        className,
      )}
      {...rest}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: token.color }}
      />
      <span>{text}</span>
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Tooltip                                                                    */
/* -------------------------------------------------------------------------- */

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function Tooltip({ content, children, className }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();

  return (
    <span
      className={clsx('relative inline-flex items-center', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? tooltipId : undefined} className="inline-flex">
        {children}
      </span>
      {open && content && (
        <span
          id={tooltipId}
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 w-64 -translate-x-1/2 rounded-md border border-slate-700 bg-slate-900 p-2.5 text-left text-xs leading-relaxed text-slate-100 shadow-lg"
        >
          {content}
        </span>
      )}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* SourceChip                                                                 */
/* -------------------------------------------------------------------------- */

export interface SourceChipProps {
  sourceId: string;
  sources?: Source[];
  onInspectSource?: (source: Source) => void;
  className?: string;
}

const TIER_LABELS: Record<1 | 2 | 3, string> = {
  1: 'Tier 1 · Official',
  2: 'Tier 2 · Peer-reviewed / IFS',
  3: 'Tier 3 · Secondary',
};

export function SourceChip({
  sourceId,
  sources = [],
  onInspectSource,
  className,
}: SourceChipProps) {
  const source = sources.find((s) => s.source_id === sourceId);

  if (!source) {
    return (
      <span
        aria-label={`Source ${sourceId}`}
        className={clsx(
          'inline-flex items-center rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-medium text-slate-700',
          className,
        )}
      >
        [{sourceId}]
      </span>
    );
  }

  const tierLabel = TIER_LABELS[source.reliability_tier] ?? 'Tier 3';
  const verifiedText = source.url_verified ? 'URL verified' : 'Unverified URL';

  const tooltipContent = (
    <span className="block space-y-1">
      <span className="block font-semibold text-white">{source.title}</span>
      <span className="block text-slate-300">
        {source.publisher} · {tierLabel}
      </span>
      <span className="block text-[11px] text-slate-300">
        Status: {verifiedText}
        {source.is_placeholder ? ' · Placeholder' : ''}
      </span>
      <span className="block truncate font-mono text-[10px] text-blue-300">
        {source.url}
      </span>
    </span>
  );

  return (
    <Tooltip content={tooltipContent}>
      <span className="inline-flex items-center gap-0.5">
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Source ${source.source_id}: ${source.title} (${source.publisher}, ${tierLabel}, ${verifiedText})`}
          className={clsx(
            'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-xs font-medium transition-colors focus:ring-2 focus:ring-blue-500 focus:outline-none',
            source.reliability_tier === 1
              ? 'border-blue-300 bg-blue-50 text-blue-800 hover:bg-blue-100'
              : source.reliability_tier === 2
                ? 'border-violet-300 bg-violet-50 text-violet-800 hover:bg-violet-100'
                : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200',
            className,
          )}
        >
          <span>[{source.source_id}]</span>
          <span className="font-sans text-[11px] font-normal text-slate-600">
            {source.publisher}
          </span>
          <span
            aria-hidden="true"
            className={clsx(
              'text-[10px]',
              source.url_verified ? 'text-emerald-700' : 'text-amber-700',
            )}
          >
            {source.url_verified ? '✓' : '•'}
          </span>
        </a>
        {onInspectSource && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onInspectSource(source);
            }}
            aria-label={`Inspect all evidence from ${source.source_id}`}
            title="Inspect source evidence"
            className="rounded border border-slate-200 bg-white px-1 py-0.5 text-[10px] text-slate-600 hover:bg-slate-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
          >
            ⋯
          </button>
        )}
      </span>
    </Tooltip>
  );
}

/* -------------------------------------------------------------------------- */
/* Stat                                                                       */
/* -------------------------------------------------------------------------- */

export interface StatProps {
  label: string;
  value: React.ReactNode;
  sublabel?: React.ReactNode;
  evidenceClass?: EvidenceClass | EvidenceClassKey;
  range?: string | null;
  confidence?: Confidence | null;
  withheld?: boolean;
  withheldReason?: string;
  isPlaceholder?: boolean;
  provenance?: React.ReactNode;
  className?: string;
}

export function Stat({
  label,
  value,
  sublabel,
  evidenceClass = 'model_scenario',
  range,
  confidence,
  withheld = false,
  withheldReason,
  isPlaceholder = false,
  provenance,
  className,
}: StatProps) {
  const tileContent = (
    <div
      className={clsx(
        'flex h-full flex-col justify-between rounded-lg border p-4 transition-colors',
        withheld
          ? clsx(WITHHELD_HATCH_CLASS, 'border-amber-400')
          : 'border-slate-200 bg-white shadow-xs',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-1.5">
        <span className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
          {label}
        </span>
        <div className="flex flex-wrap items-center gap-1">
          <EvidenceBadge evidenceClass={evidenceClass} short />
          {isPlaceholder && <PlaceholderBadge />}
        </div>
      </div>

      <div className="my-2.5">
        {withheld ? (
          <div className="py-1">
            <span className="inline-flex items-center gap-1.5 rounded bg-amber-100/90 px-2 py-1 text-xs font-semibold text-amber-900">
              <span aria-hidden="true">⊘</span>
              <span>Forecast withheld</span>
            </span>
            {withheldReason && (
              <p className="mt-1 text-xs text-amber-900">{withheldReason}</p>
            )}
          </div>
        ) : (
          <div className="text-2xl font-bold tracking-tight text-slate-900 tabular-nums">
            {value}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <div>
          {!withheld && range && (
            <span className="font-medium text-slate-600">
              Range (p5–p95): <span className="tabular-nums">{range}</span>
            </span>
          )}
          {sublabel && <div className="text-slate-500">{sublabel}</div>}
        </div>
        {confidence && (
          <Badge
            variant={
              confidence === 'high'
                ? 'green'
                : confidence === 'medium'
                  ? 'blue'
                  : 'amber'
            }
            aria-label={`Confidence: ${confidence}`}
          >
            {confidence === 'low' ? 'Low confidence (indicative)' : `${confidence} confidence`}
          </Badge>
        )}
      </div>
    </div>
  );

  if (provenance) {
    return (
      <Tooltip content={provenance} className="block w-full">
        <div className="w-full">{tileContent}</div>
      </Tooltip>
    );
  }

  return tileContent;
}

/* -------------------------------------------------------------------------- */
/* Tabs                                                                       */
/* -------------------------------------------------------------------------- */

export interface TabItem {
  id: string;
  label: React.ReactNode;
  disabled?: boolean;
  badge?: React.ReactNode;
  href?: string;
}

export interface TabsProps {
  items: TabItem[];
  activeId: string;
  onChange?: (id: string) => void;
  ariaLabel?: string;
  className?: string;
}

export function Tabs({
  items,
  activeId,
  onChange,
  ariaLabel = 'Section tabs',
  className,
}: TabsProps) {
  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const enabledIndices = items
      .map((item, idx) => (!item.disabled ? idx : -1))
      .filter((idx) => idx !== -1);
    if (enabledIndices.length === 0) return;

    const currentPos = enabledIndices.indexOf(index);
    let nextIdx: number | undefined;

    if (e.key === 'ArrowRight') {
      e.preventDefault();
      nextIdx = enabledIndices[(currentPos + 1) % enabledIndices.length];
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      nextIdx =
        enabledIndices[(currentPos - 1 + enabledIndices.length) % enabledIndices.length];
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIdx = enabledIndices[0];
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIdx = enabledIndices[enabledIndices.length - 1];
    }

    if (nextIdx !== undefined) {
      const targetItem = items[nextIdx];
      if (targetItem && !targetItem.disabled) {
        onChange?.(targetItem.id);
        const container = e.currentTarget.parentElement;
        const buttons = container?.querySelectorAll<HTMLElement>('[role="tab"]');
        buttons?.[nextIdx]?.focus();
      }
    }
  };

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={clsx(
        'flex flex-wrap items-center gap-1 border-b border-slate-200',
        className,
      )}
    >
      {items.map((item, index) => {
        const isActive = item.id === activeId;
        return (
          <button
            key={item.id}
            role="tab"
            type="button"
            aria-selected={isActive}
            aria-disabled={item.disabled}
            disabled={item.disabled}
            tabIndex={isActive ? 0 : -1}
            onClick={() => !item.disabled && onChange?.(item.id)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={clsx(
              'inline-flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors focus:ring-2 focus:ring-blue-500 focus:outline-none focus:ring-inset',
              isActive
                ? 'border-blue-600 text-blue-700'
                : item.disabled
                  ? 'cursor-not-allowed border-transparent text-slate-400'
                  : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900',
            )}
          >
            <span>{item.label}</span>
            {item.badge}
          </button>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Table                                                                      */
/* -------------------------------------------------------------------------- */

export interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  children: React.ReactNode;
  wrapperClassName?: string;
}

export function Table({ children, className, wrapperClassName, ...rest }: TableProps) {
  return (
    <div
      className={clsx(
        'overflow-x-auto rounded-lg border border-slate-200 bg-white',
        wrapperClassName,
      )}
    >
      <table
        className={clsx('min-w-full divide-y divide-slate-200 text-left text-sm', className)}
        {...rest}
      >
        {children}
      </table>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* EmptyState                                                                 */
/* -------------------------------------------------------------------------- */

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50/70 px-6 py-10 text-center',
        className,
      )}
    >
      {icon && <div className="mb-2 text-2xl text-slate-400">{icon}</div>}
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* WithheldBanner                                                             */
/* -------------------------------------------------------------------------- */

export interface WithheldBannerProps {
  reasons?: string[];
  title?: string;
  className?: string;
}

export function WithheldBanner({
  reasons = [],
  title = 'Quantitative forecast withheld',
  className,
}: WithheldBannerProps) {
  return (
    <div
      role="alert"
      aria-label={title}
      className={clsx(
        WITHHELD_HATCH_CLASS,
        'rounded-lg border-2 border-amber-500 p-4 text-slate-900 shadow-xs',
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-600 text-xs font-bold text-white"
        >
          !
        </span>
        <div className="flex-1">
          <h3 className="text-sm font-bold text-amber-950">{title}</h3>
          <p className="mt-1 text-xs text-amber-900">
            Jane Avenue declines to display headline quantitative forecasts when a policy
            falls outside validated scope or fails a blocking verification check.
            Historical precedents and qualitative research remain available below.
          </p>
          {reasons.length > 0 && (
            <ul className="mt-2.5 list-disc space-y-1 pl-5 text-xs font-medium text-amber-950">
              {reasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* PlaceholderBadge                                                           */
/* -------------------------------------------------------------------------- */

export interface PlaceholderBadgeProps {
  label?: string;
  className?: string;
}

export function PlaceholderBadge({
  label = 'Placeholder (unverified)',
  className,
}: PlaceholderBadgeProps) {
  return (
    <span
      role="status"
      aria-label={`Data status: ${label}`}
      className={clsx(
        'inline-flex items-center gap-1 rounded border border-amber-400 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-900',
        className,
      )}
    >
      <span aria-hidden="true">⚠</span>
      <span>{label}</span>
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* ModeBadge                                                                  */
/* -------------------------------------------------------------------------- */

export interface ModeBadgeProps {
  mode?: Mode | null;
  className?: string;
}

const MODE_STYLES: Record<
  Mode,
  { label: string; variant: BadgeVariant; dot: string; description: string }
> = {
  live: {
    label: 'Mode: Live Gemini',
    variant: 'green',
    dot: '#16a34a',
    description: 'Live Gemini API + Google Search grounding enabled',
  },
  cached: {
    label: 'Mode: Cached Research',
    variant: 'blue',
    dot: '#2563eb',
    description: 'Replaying verified research trace from cache with deterministic engine',
  },
  mock: {
    label: 'Mode: Mock',
    variant: 'amber',
    dot: '#d97706',
    description: 'Deterministic offline mock fixtures (no external network calls)',
  },
};

export function ModeBadge({ mode, className }: ModeBadgeProps) {
  const { data: health } = useHealth();
  const resolvedMode: Mode = mode ?? health?.mode ?? 'mock';
  const cfg = MODE_STYLES[resolvedMode] ?? MODE_STYLES.mock;

  return (
    <Tooltip content={cfg.description}>
      <Badge
        variant={cfg.variant}
        dotColor={cfg.dot}
        aria-label={`Runtime ${cfg.label}`}
        className={className}
      >
        {cfg.label}
      </Badge>
    </Tooltip>
  );
}

/* -------------------------------------------------------------------------- */
/* VerificationBadge (helper for header, history & verification views)        */
/* -------------------------------------------------------------------------- */

export interface VerificationBadgeProps {
  overall?: VerificationOverallKey | string | null;
  status?: VerificationStatusKey | null;
  className?: string;
}

export function VerificationBadge({
  overall,
  status,
  className,
}: VerificationBadgeProps) {
  if (status) {
    const token = VERIFICATION_STATUS_TOKENS[status] ?? VERIFICATION_STATUS_TOKENS.skipped;
    return (
      <span
        role="status"
        aria-label={`Check status: ${token.label}`}
        className={clsx(
          'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
          token.bgClass,
          token.textClass,
          token.borderClass,
          className,
        )}
      >
        <span aria-hidden="true" className="font-bold">
          {token.symbol}
        </span>
        <span>{token.label}</span>
      </span>
    );
  }

  if (!overall) {
    return null;
  }

  const key = overall as VerificationOverallKey;
  const token = VERIFICATION_OVERALL_TOKENS[key] ?? {
    color: '#64748b',
    label: String(overall),
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-700',
    borderClass: 'border-slate-300',
  };

  return (
    <span
      role="status"
      aria-label={`Verification status: ${token.label}`}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-xs font-semibold',
        token.bgClass,
        token.textClass,
        token.borderClass,
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: token.color }}
      />
      <span>{token.label}</span>
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Skeleton & Spinner                                                         */
/* -------------------------------------------------------------------------- */

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  lines?: number;
}

export function Skeleton({ lines = 1, className, ...rest }: SkeletonProps) {
  if (lines <= 1) {
    return (
      <div
        role="status"
        aria-label="Loading"
        className={clsx('h-4 w-full animate-pulse rounded bg-slate-200', className)}
        {...rest}
      />
    );
  }

  return (
    <div role="status" aria-label="Loading" className="space-y-2" {...rest}>
      {Array.from({ length: lines }).map((_, idx) => (
        <div
          key={idx}
          className={clsx(
            'h-4 animate-pulse rounded bg-slate-200',
            idx === lines - 1 ? 'w-3/4' : 'w-full',
            className,
          )}
        />
      ))}
    </div>
  );
}

export function Spinner({
  size = 'sm',
  className,
}: {
  size?: 'xs' | 'sm' | 'md';
  className?: string;
}) {
  const dim = {
    xs: 'h-3 w-3 border-2',
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
  }[size];

  return (
    <span
      role="status"
      aria-label="Loading"
      className={clsx(
        'inline-block animate-spin rounded-full border-slate-300 border-t-blue-600',
        dim,
        className,
      )}
    />
  );
}

/* -------------------------------------------------------------------------- */
/* InlineError                                                                */
/* -------------------------------------------------------------------------- */

export interface InlineErrorProps {
  title?: string;
  message: string;
  reasons?: string[];
  onRetry?: () => void;
  className?: string;
}

export function InlineError({
  title = 'Error',
  message,
  reasons = [],
  onRetry,
  className,
}: InlineErrorProps) {
  return (
    <div
      role="alert"
      className={clsx(
        'rounded-lg border border-red-300 bg-red-50 p-4 text-red-900',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-red-900">
            <span aria-hidden="true">✕</span>
            <span>{title}</span>
          </div>
          <p className="text-xs text-red-800">{message}</p>
          {reasons.length > 0 && (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-red-800">
              {reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-800 shadow-2xs hover:bg-red-100 focus:ring-2 focus:ring-red-500 focus:outline-none"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
