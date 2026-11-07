import { useParams } from 'react-router';
import { useAnalysis, type Analysis } from '../../api/hooks';
import { Card, Skeleton } from '../../components/ui';

export interface AssumptionsTabProps {
  analysis?: Analysis;
}

export function AssumptionsTab({ analysis: propAnalysis }: AssumptionsTabProps) {
  const { id } = useParams<{ id: string }>();
  const { data: fetchedAnalysis, isLoading } = useAnalysis(propAnalysis ? undefined : id);
  const analysis = propAnalysis ?? fetchedAnalysis;

  if (!analysis && isLoading) {
    return <Skeleton lines={4} />;
  }

  const slice = {
    assumptions: analysis?.simulation?.assumptions ?? [],
    calc_trace: analysis?.simulation?.scenarios?.[0]?.result?.calc_trace ?? [],
    parameter_evidence: analysis?.research?.parameter_evidence ?? [],
  };

  return (
    <Card
      title="Assumptions (agent-8)"
      subtitle="Placeholder component — owned by agent-8"
    >
      <details className="text-xs">
        <summary className="cursor-pointer font-medium text-blue-700 hover:underline">
          Inspect assumptions & calc_trace JSON slice
        </summary>
        <pre className="mt-2 max-h-96 overflow-auto rounded bg-slate-900 p-3 font-mono text-[11px] text-slate-100">
          {JSON.stringify(slice, null, 2)}
        </pre>
      </details>
    </Card>
  );
}

export default AssumptionsTab;
