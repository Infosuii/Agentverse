import { useEffect, useState } from 'react';
import clsx from 'clsx';

export interface TocEntry {
  id: string;
  title: string;
  number: string;
  depth: number;
}

/** Tracks which section id is currently near the top of the viewport. */
export function useActiveSection(ids: readonly string[]): string | null {
  const [active, setActive] = useState<string | null>(null);
  const key = ids.join('|');

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    const els = key
      .split('|')
      .map((id) => (id ? document.getElementById(id) : null))
      .filter((e): e is HTMLElement => Boolean(e));
    if (els.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: '-80px 0px -65% 0px' },
    );
    els.forEach((e) => observer.observe(e));
    return () => observer.disconnect();
  }, [key]);

  return active;
}

/** Sticky, clickable contents list that highlights the section being read (studio TOC). */
export function TableOfContents({
  entries,
  label = 'Policy Report',
  className,
}: {
  entries: readonly TocEntry[];
  label?: string;
  className?: string;
}) {
  const active = useActiveSection(entries.map((e) => e.id));
  return (
    <nav aria-label={`${label} contents`} className={clsx('mt-7', className)}>
      <p className="mb-3 font-mono text-[11px] tracking-[0.16em] text-muted-foreground uppercase">
        {label}
      </p>
      <ul className="space-y-1 border-l border-border">
        {entries.map((e) => (
          <li key={e.id}>
            <a
              href={`#${e.id}`}
              className={clsx(
                '-ml-px block border-l py-1 text-sm leading-snug transition-colors',
                e.depth === 0 ? 'pl-3' : 'pl-6 text-[13px]',
                active === e.id
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              <span className="mr-1.5 font-mono text-[11px] text-primary/80">{e.number}</span>
              {e.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default TableOfContents;
