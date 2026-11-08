import { Link } from 'react-router';
import { useAnalysesList } from '../../api/hooks';
import {
  Badge,
  Card,
  EmptyState,
  InlineError,
  SearchIcon,
  Skeleton,
  VerificationBadge,
  buttonClasses,
} from '../../components/ui';
import { fmtDate } from '../../lib/format';

function HistoryHeader({ count }: { count?: number }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-5">
      <div>
        <Badge variant="slate">Policy Analyses</Badge>
        <h1 className="mt-3 font-display text-2xl font-semibold text-foreground sm:text-3xl">
          Analysis History
        </h1>
        <p className="mt-1 font-mono text-xs text-muted-foreground">
          {count === undefined
            ? 'Past policy simulations stored in SQLite'
            : `Recent policy simulations (${count})`}
        </p>
      </div>
      <Link to="/" className={buttonClasses('primary', 'sm')}>
        <SearchIcon className="h-3.5 w-3.5" />
        <span>+ New analysis</span>
      </Link>
    </header>
  );
}

export function HistoryPage() {
  const { data: analyses, isLoading, isError, error, refetch } = useAnalysesList(50);

  if (isLoading && !analyses) {
    return (
      <div className="space-y-6">
        <HistoryHeader />
        <Card>
          <Skeleton lines={5} />
        </Card>
      </div>
    );
  }

  if (isError) {
    return (
      <InlineError
        title="Could not load analysis history"
        message={error instanceof Error ? error.message : 'Failed to load history'}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!analyses || analyses.length === 0) {
    return (
      <div className="space-y-6">
        <HistoryHeader count={0} />
        <EmptyState
          title="No analyses run yet"
          description="Start a new UK fiscal policy simulation to see it recorded here."
          action={
            <Link to="/" className={buttonClasses('primary', 'sm')}>
              New analysis
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <HistoryHeader count={analyses.length} />

      <div className="overflow-x-auto border-y border-border">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted-foreground">
              <th className="px-3 py-3 font-medium">Created</th>
              <th className="px-3 py-3 font-medium">Policy / Query</th>
              <th className="px-3 py-3 font-medium">Status</th>
              <th className="px-3 py-3 font-medium">Verification</th>
              <th className="px-3 py-3 text-right font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {analyses.map((item, i) => (
              <tr key={item.analysis_id} className="transition-colors hover:bg-muted/30">
                <td className="px-3 py-3.5 align-top whitespace-nowrap">
                  {/* decorative row number: hidden from screen readers so the date is not read as "018 Nov" */}
                  <span aria-hidden="true" className="mr-2 font-mono text-[11px] text-primary/80">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {fmtDate(item.created_at)}
                  </span>
                </td>
                <td className="px-3 py-3.5 align-top">
                  <Link
                    to={`/analyses/${item.analysis_id}/overview`}
                    className="font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {item.policy_description || item.query}
                  </Link>
                  {item.policy_description && item.policy_description !== item.query && (
                    <div className="mt-0.5 max-w-xl truncate text-xs text-muted-foreground">
                      Query: &ldquo;{item.query}&rdquo;
                    </div>
                  )}
                </td>
                <td className="px-3 py-3.5 align-top whitespace-nowrap">
                  <Badge
                    variant={
                      item.status === 'completed'
                        ? 'green'
                        : item.status === 'failed'
                          ? 'red'
                          : 'blue'
                    }
                  >
                    {item.status}
                  </Badge>
                </td>
                <td className="px-3 py-3.5 align-top whitespace-nowrap">
                  {item.verification_overall ? (
                    <VerificationBadge overall={item.verification_overall} />
                  ) : (
                    <span className="text-muted-foreground/70">—</span>
                  )}
                </td>
                <td className="px-3 py-3.5 text-right align-top whitespace-nowrap">
                  <Link
                    to={`/analyses/${item.analysis_id}/overview`}
                    className="text-sm font-medium text-primary hover:underline"
                  >
                    Open →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default HistoryPage;
