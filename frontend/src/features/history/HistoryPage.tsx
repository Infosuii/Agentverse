import { Link } from 'react-router';
import { useAnalysesList } from '../../api/hooks';
import {
  Badge,
  Card,
  EmptyState,
  InlineError,
  Skeleton,
  Table,
  VerificationBadge,
} from '../../components/ui';
import { fmtDate } from '../../lib/format';

export function HistoryPage() {
  const { data: analyses, isLoading, isError, error, refetch } = useAnalysesList(50);

  if (isLoading && !analyses) {
    return (
      <Card title="Analysis History" subtitle="Past policy simulations stored in SQLite">
        <Skeleton lines={5} />
      </Card>
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
      <Card title="Analysis History" subtitle="Past policy simulations">
        <EmptyState
          title="No analyses run yet"
          description="Start a new UK fiscal policy simulation to see it recorded here."
          action={
            <Link
              to="/"
              className="inline-flex items-center rounded-md bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-blue-700"
            >
              New analysis
            </Link>
          }
        />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Analysis History</h1>
          <p className="text-xs text-slate-600">
            Recent policy simulations ({analyses.length})
          </p>
        </div>
        <Link
          to="/"
          className="inline-flex items-center rounded-md bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-blue-700"
        >
          + New analysis
        </Link>
      </div>

      <Table>
        <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
          <tr>
            <th className="px-4 py-3">Created</th>
            <th className="px-4 py-3">Policy / Query</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Verification</th>
            <th className="px-4 py-3 text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 text-xs">
          {analyses.map((item) => (
            <tr key={item.analysis_id} className="hover:bg-slate-50">
              <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                {fmtDate(item.created_at)}
              </td>
              <td className="px-4 py-3">
                <Link
                  to={`/analyses/${item.analysis_id}/overview`}
                  className="font-semibold text-slate-900 hover:text-blue-700 hover:underline"
                >
                  {item.policy_description || item.query}
                </Link>
                {item.policy_description && item.policy_description !== item.query && (
                  <div className="mt-0.5 truncate max-w-xl text-slate-500">
                    Query: &ldquo;{item.query}&rdquo;
                  </div>
                )}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
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
              <td className="px-4 py-3 whitespace-nowrap">
                {item.verification_overall ? (
                  <VerificationBadge overall={item.verification_overall} />
                ) : (
                  <span className="text-slate-400">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-right whitespace-nowrap">
                <Link
                  to={`/analyses/${item.analysis_id}/overview`}
                  className="font-medium text-blue-700 hover:underline"
                >
                  Open →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}

export default HistoryPage;
