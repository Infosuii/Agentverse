import { useParams } from 'react-router';
import { useAnalysis, type Analysis } from '../../api/hooks';
import { Card, Skeleton } from '../../components/ui';

export interface ReportTabProps {
  analysis?: Analysis;
}

export function ReportTab({ analysis: propAnalysis }: ReportTabProps) {
  const { id } = useParams<{ id: string }>();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(propAnalysis ? undefined : id);
  const analysis = propAnalysis ?? fetchedAnalysis;

  if (!analysis && isLoading) {
    return <Skeleton lines={4} />;
  }

  return (
    <Card title="Report (agent-9)" subtitle="Placeholder component — owned by agent-9">
      <details className="text-xs">
        <summary className="cursor-pointer font-medium text-blue-700 hover:underline">
          Inspect analysis.report JSON slice
        </summary>
        <pre className="mt-2 max-h-96 overflow-auto rounded bg-slate-900 p-3 font-mono text-[11px] text-slate-100">
          {JSON.stringify(analysis?.report ?? null, null, 2)}
        </pre>
      </details>
    </Card>
  );
}

export default ReportTab;
