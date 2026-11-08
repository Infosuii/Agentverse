import type { ReactNode } from 'react';
import { Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';

/**
 * Turns bare citation markers into links:
 * - `[S3]` / `[D-obr-baseline]` → the numbered source directory entry (`#src-S3`)
 * - `[E2]` → the evidence item in the Research view
 * Markers already used as link text or reference definitions (`[S3](…)`, `[S3]: …`) are left alone.
 */
export function linkCitations(
  markdown: string,
  sourceIds: ReadonlySet<string>,
  analysisId?: string,
): string {
  const linkify = (text: string) =>
    text.replace(
      /(?<!\\)\[((?:S\d+)|(?:D-[A-Za-z0-9_.-]+)|(?:E\d+))\](?![(:])/g,
      (match, id: string) => {
        if (/^E\d+$/.test(id)) {
          if (!analysisId) return match;
          return `[\\[${id}\\]](/analyses/${encodeURIComponent(analysisId)}/research?evidence=${encodeURIComponent(id)})`;
        }
        if (!sourceIds.has(id)) return match;
        return `[\\[${id}\\]](#src-${encodeURIComponent(id)})`;
      },
    );
  // Leave fenced and inline code untouched.
  return markdown
    .split(/(```[\s\S]*?```|`[^`\n]*`)/g)
    .map((part, i) => (i % 2 === 1 ? part : linkify(part)))
    .join('');
}

function MarkdownLink({
  href,
  children,
}: {
  href?: string;
  children?: ReactNode;
}) {
  const className =
    'text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary';
  if (href && href.startsWith('/')) {
    return (
      <Link to={href} className={className}>
        {children}
      </Link>
    );
  }
  if (href && href.startsWith('#')) {
    return (
      <a href={href} className={clsx(className, 'font-mono text-[0.85em] no-underline')}>
        {children}
      </a>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
    </a>
  );
}

/** Studio "reading column" typography for generated markdown. */
export const REPORT_PROSE_CLASS = clsx(
  'min-w-0 text-foreground/95 [overflow-wrap:anywhere]',
  '[&_p]:mb-4 [&_p:last-child]:mb-0',
  '[&_h1]:mt-6 [&_h1]:mb-3 [&_h1]:font-display [&_h1]:text-xl [&_h1]:font-semibold',
  '[&_h2]:mt-6 [&_h2]:mb-2.5 [&_h2]:font-display [&_h2]:text-lg [&_h2]:font-semibold',
  '[&_h3]:mt-5 [&_h3]:mb-2 [&_h3]:font-display [&_h3]:text-base [&_h3]:font-semibold',
  '[&_h4]:mt-4 [&_h4]:mb-1.5 [&_h4]:font-mono [&_h4]:text-xs [&_h4]:tracking-[0.14em] [&_h4]:text-primary [&_h4]:uppercase',
  '[&_ul]:mb-4 [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5',
  '[&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:space-y-1.5 [&_ol]:pl-5',
  '[&_li]:marker:text-muted-foreground',
  '[&_strong]:font-semibold [&_strong]:text-foreground',
  '[&_em]:text-foreground/90',
  '[&_blockquote]:mb-4 [&_blockquote]:border-l-2 [&_blockquote]:border-primary/60 [&_blockquote]:pl-4 [&_blockquote]:text-muted-foreground',
  '[&_code]:rounded-sm [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.85em]',
  '[&_hr]:my-6 [&_hr]:border-border',
  '[&_table]:my-4 [&_table]:w-full [&_table]:border-y [&_table]:border-border [&_table]:text-sm',
  '[&_th]:border-b [&_th]:border-border [&_th]:px-2 [&_th]:py-2 [&_th]:text-left [&_th]:font-medium [&_th]:text-muted-foreground',
  '[&_td]:border-b [&_td]:border-border [&_td]:px-2 [&_td]:py-2 [&_td]:tabular-nums',
);

export function ReportMarkdown({
  markdown,
  sourceIds,
  analysisId,
  lead = false,
  className,
}: {
  markdown: string;
  sourceIds?: ReadonlySet<string>;
  analysisId?: string;
  /** Larger "lead paragraph" type, used for the executive summary. */
  lead?: boolean;
  className?: string;
}) {
  const content = sourceIds ? linkCitations(markdown, sourceIds, analysisId) : markdown;
  return (
    <div
      className={clsx(
        REPORT_PROSE_CLASS,
        lead ? 'text-[17px] leading-[1.65]' : 'text-[15px] leading-[1.7]',
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }: { href?: string; children?: ReactNode }) => (
            <MarkdownLink href={href}>{children}</MarkdownLink>
          ),
          table: ({ children }: { children?: ReactNode }) => (
            <div className="overflow-x-auto">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default ReportMarkdown;
