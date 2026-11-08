import React, { useEffect, useId, useRef, useState } from 'react';
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
/* Buttons (class helper shared by links and buttons)                         */
/* -------------------------------------------------------------------------- */

export type ButtonVariant = 'primary' | 'outline' | 'ghost' | 'secondary';
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg' | 'icon' | 'icon-sm';

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
  outline:
    'border border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground',
  secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  ghost: 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  xs: 'h-7 px-2.5 text-xs',
  sm: 'h-8 px-3 text-xs',
  md: 'h-9 px-4 text-sm',
  lg: 'h-10 px-5 text-sm',
  icon: 'h-9 w-9',
  'icon-sm': 'h-7 w-7',
};

/** Studio button styling, usable on <button>, <a> and router <Link>. */
export function buttonClasses(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  className?: string,
): string {
  return clsx(
    'inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors',
    'focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none',
    'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    className,
  );
}

/** Small mono uppercase label used above groups of content ("Policy Report", "Pipeline"). */
export function Eyebrow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={clsx(
        'font-mono text-[11px] tracking-[0.16em] text-muted-foreground uppercase',
        className,
      )}
    >
      {children}
    </p>
  );
}

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
        'rounded-lg border border-border bg-card text-card-foreground',
        hatched && WITHHELD_HATCH_CLASS,
        className,
      )}
      {...rest}
    >
      {(title || subtitle || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border px-4 py-3 sm:px-5">
          <div className="min-w-0">
            {title && (
              <h3 className="font-display text-[15px] leading-snug font-semibold tracking-tight text-foreground">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
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
  | 'rose'
  | 'primary'
  | 'outline';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: 'xs' | 'sm';
  dotColor?: string;
}

const BADGE_VARIANTS: Record<BadgeVariant, string> = {
  slate: 'border-border bg-secondary text-secondary-foreground',
  blue: 'border-blue-400/35 bg-blue-500/10 text-blue-300',
  green: 'border-emerald-400/35 bg-emerald-500/10 text-emerald-300',
  amber: 'border-amber-400/35 bg-amber-500/10 text-amber-300',
  red: 'border-red-400/35 bg-red-500/10 text-red-300',
  violet: 'border-violet-400/35 bg-violet-500/10 text-violet-300',
  rose: 'border-rose-400/35 bg-rose-500/10 text-rose-300',
  primary: 'border-primary/40 bg-primary/10 text-primary',
  outline: 'border-border bg-transparent text-foreground',
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
        'inline-flex items-center gap-1.5 rounded-sm border font-medium whitespace-nowrap',
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
        'inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
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
  /** `block` stretches the trigger to fill its container (e.g. a grid cell holding a tile). */
  display?: 'inline' | 'block';
}

export function Tooltip({ content, children, className, display = 'inline' }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();
  const block = display === 'block';

  return (
    <span
      className={clsx(
        'relative',
        block ? 'flex h-full w-full' : 'inline-flex items-center',
        className,
      )}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        aria-describedby={open ? tooltipId : undefined}
        className={block ? 'flex h-full w-full' : 'inline-flex'}
      >
        {children}
      </span>
      {open && content && (
        <span
          id={tooltipId}
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 w-64 -translate-x-1/2 rounded-sm border border-border bg-popover p-2.5 text-left text-xs leading-relaxed text-popover-foreground shadow-lg shadow-black/40"
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
          'inline-flex items-center rounded-sm border border-border bg-secondary px-1.5 py-0.5 font-mono text-xs font-medium text-muted-foreground',
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
      <span className="block font-semibold text-foreground">{source.title}</span>
      <span className="block text-muted-foreground">
        {source.publisher} · {tierLabel}
      </span>
      <span className="block text-[11px] text-muted-foreground">
        Status: {verifiedText}
        {source.is_placeholder ? ' · Placeholder' : ''}
      </span>
      <span className="block truncate font-mono text-[10px] text-primary">{source.url}</span>
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
            'inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 font-mono text-xs font-medium transition-colors focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none',
            source.reliability_tier === 1
              ? 'border-blue-400/35 bg-blue-500/10 text-blue-300 hover:bg-blue-500/20'
              : source.reliability_tier === 2
                ? 'border-violet-400/35 bg-violet-500/10 text-violet-300 hover:bg-violet-500/20'
                : 'border-border bg-secondary text-secondary-foreground hover:bg-accent',
            className,
          )}
        >
          <span>[{source.source_id}]</span>
          <span className="font-sans text-[11px] font-normal text-muted-foreground">
            {source.publisher}
          </span>
          <span
            aria-hidden="true"
            className={clsx(
              'text-[10px]',
              source.url_verified ? 'text-emerald-400' : 'text-amber-400',
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
            className="rounded-sm border border-border bg-card px-1 py-0.5 text-[10px] text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
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
        'flex h-full flex-col rounded-lg border p-4 transition-colors',
        withheld ? WITHHELD_HATCH_CLASS : 'border-border bg-card',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-1.5">
        <span className="text-xs leading-snug text-muted-foreground">{label}</span>
        <div className="flex flex-wrap items-center gap-1">
          <EvidenceBadge evidenceClass={evidenceClass} short />
          {isPlaceholder && <PlaceholderBadge />}
        </div>
      </div>

      <div className="my-2.5">
        {withheld ? (
          <div className="py-1">
            <span className="inline-flex items-center gap-1.5 rounded-sm bg-amber-500/20 px-2 py-1 text-xs font-semibold text-amber-200">
              <span aria-hidden="true">⊘</span>
              <span>Forecast withheld</span>
            </span>
            {withheldReason && (
              <p className="mt-1.5 text-xs leading-relaxed text-amber-200/90">{withheldReason}</p>
            )}
          </div>
        ) : (
          <div className="font-mono text-2xl font-medium tracking-tight text-foreground tabular-nums">
            {value}
          </div>
        )}
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <div>
          {!withheld && range && (
            <span className="font-medium text-foreground/80">
              Range (p5–p95): <span className="font-mono tabular-nums">{range}</span>
            </span>
          )}
          {sublabel && <div className="text-muted-foreground">{sublabel}</div>}
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
      <Tooltip content={provenance} display="block">
        <div className="h-full w-full">{tileContent}</div>
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
  /** Optional index shown before the label (e.g. "01"); not part of the accessible name. */
  number?: string;
  /** Optional status (e.g. live generation feedback); exposed as the tab's description. */
  status?: React.ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  activeId: string;
  onChange?: (id: string) => void;
  ariaLabel?: string;
  /**
   * `responsive`: a horizontal, scrollable rail below `lg` that becomes a vertical
   * contents list from `lg` up (studio table-of-contents style).
   */
  orientation?: 'horizontal' | 'vertical' | 'responsive';
  className?: string;
}

export function Tabs({
  items,
  activeId,
  onChange,
  ariaLabel = 'Section tabs',
  orientation = 'horizontal',
  className,
}: TabsProps) {
  const baseId = useId();
  const vertical = orientation === 'vertical';
  const responsive = orientation === 'responsive';
  const listRef = useRef<HTMLDivElement | null>(null);

  // When the rail scrolls horizontally (small screens), keep the active tab in view.
  useEffect(() => {
    const list = listRef.current;
    if (!list || list.scrollWidth <= list.clientWidth) return;
    const active = list.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    if (!active) return;
    list.scrollLeft = Math.max(0, active.offsetLeft - (list.clientWidth - active.offsetWidth) / 2);
  }, [activeId]);

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const enabledIndices = items
      .map((item, idx) => (!item.disabled ? idx : -1))
      .filter((idx) => idx !== -1);
    if (enabledIndices.length === 0) return;

    const currentPos = enabledIndices.indexOf(index);
    const nextKeys = vertical || responsive ? ['ArrowDown', 'ArrowRight'] : ['ArrowRight'];
    const prevKeys = vertical || responsive ? ['ArrowUp', 'ArrowLeft'] : ['ArrowLeft'];
    let nextIdx: number | undefined;

    if (nextKeys.includes(e.key)) {
      e.preventDefault();
      nextIdx = enabledIndices[(currentPos + 1) % enabledIndices.length];
    } else if (prevKeys.includes(e.key)) {
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
        const container = e.currentTarget.closest('[role="tablist"]');
        const buttons = container?.querySelectorAll<HTMLElement>('[role="tab"]');
        buttons?.[nextIdx]?.focus();
      }
    }
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={ariaLabel}
      aria-orientation={responsive ? undefined : orientation}
      className={clsx(
        vertical && 'flex flex-col border-l border-border',
        responsive &&
          'scrollbar-none flex overflow-x-auto border-b border-border lg:flex-col lg:overflow-visible lg:border-b-0 lg:border-l',
        !vertical && !responsive && 'flex flex-wrap items-center gap-x-1 border-b border-border',
        className,
      )}
    >
      {items.map((item, index) => {
        const isActive = item.id === activeId;
        const statusId = item.status ? `${baseId}-${item.id}-status` : undefined;
        return (
          <button
            key={item.id}
            role="tab"
            type="button"
            aria-selected={isActive}
            aria-disabled={item.disabled}
            aria-describedby={statusId}
            disabled={item.disabled}
            tabIndex={isActive ? 0 : -1}
            onClick={() => !item.disabled && onChange?.(item.id)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={clsx(
              'group inline-flex items-center gap-2 text-sm transition-colors focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset',
              vertical &&
                '-ml-px w-full justify-between border-l py-1.5 pr-1 pl-3 text-left leading-snug',
              responsive &&
                '-mb-px shrink-0 border-b-2 px-3 py-2.5 whitespace-nowrap lg:mb-0 lg:-ml-px lg:w-full lg:justify-between lg:border-b-0 lg:border-l lg:py-1.5 lg:pr-1 lg:pl-3 lg:text-left lg:leading-snug',
              !vertical && !responsive && '-mb-px border-b-2 px-3 py-2.5 font-medium',
              isActive
                ? 'border-primary text-foreground'
                : item.disabled
                  ? 'cursor-not-allowed border-transparent text-muted-foreground/50'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            <span className="inline-flex min-w-0 items-baseline gap-2">
              {item.number && (
                <span
                  aria-hidden="true"
                  className={clsx(
                    'font-mono text-[11px]',
                    item.disabled ? 'text-muted-foreground/50' : 'text-primary/80',
                  )}
                >
                  {item.number}
                </span>
              )}
              <span className="truncate">{item.label}</span>
            </span>
            {item.badge}
            {item.status && (
              <span id={statusId} aria-hidden="true" className="shrink-0">
                {item.status}
              </span>
            )}
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
        'overflow-x-auto rounded-lg border border-border bg-card',
        wrapperClassName,
      )}
    >
      <table
        className={clsx('min-w-full divide-y divide-border text-left text-sm', className)}
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
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 py-10 text-center',
        className,
      )}
    >
      {icon && <div className="mb-2 text-2xl text-muted-foreground">{icon}</div>}
      <h3 className="font-display text-sm font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
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
      className={clsx(WITHHELD_HATCH_CLASS, 'rounded-lg border-2 p-4 text-foreground', className)}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-400 text-xs font-bold text-background"
        >
          !
        </span>
        <div className="flex-1">
          <h3 className="font-display text-sm font-semibold text-amber-100">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-amber-200/90">
            Jane Avenue declines to display headline quantitative forecasts when a policy
            falls outside validated scope or fails a blocking verification check.
            Historical precedents and qualitative research remain available below.
          </p>
          {reasons.length > 0 && (
            <ul className="mt-2.5 list-disc space-y-1 pl-5 text-xs font-medium text-amber-100">
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
        'inline-flex items-center gap-1 rounded-sm border border-amber-400/45 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-300',
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
    dot: '#34d399',
    description: 'Live Gemini API + Google Search grounding enabled',
  },
  cached: {
    label: 'Mode: Cached Research',
    variant: 'blue',
    dot: '#60a5fa',
    description: 'Replaying verified research trace from cache with deterministic engine',
  },
  mock: {
    label: 'Mode: Mock',
    variant: 'amber',
    dot: '#fbbf24',
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
          'inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-medium',
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
    color: '#94a3b8',
    label: String(overall),
    bgClass: 'bg-secondary',
    textClass: 'text-secondary-foreground',
    borderClass: 'border-border',
  };

  return (
    <span
      role="status"
      aria-label={`Verification status: ${token.label}`}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-0.5 text-xs font-semibold',
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
        className={clsx('h-4 w-full animate-pulse rounded-sm bg-muted', className)}
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
            'h-4 animate-pulse rounded-sm bg-muted',
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
        'inline-block animate-spin rounded-full border-border border-t-primary motion-reduce:animate-none',
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
        'rounded-lg border border-red-400/40 bg-red-500/10 p-4 text-red-200',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-red-200">
            <span aria-hidden="true">✕</span>
            <span>{title}</span>
          </div>
          <p className="text-xs text-red-200/90">{message}</p>
          {reasons.length > 0 && (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-red-200/90">
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
            className="rounded-md border border-red-400/40 bg-transparent px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-500/15 focus-visible:ring-1 focus-visible:ring-red-400 focus-visible:outline-none"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
