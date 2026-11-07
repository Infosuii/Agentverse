import { useEvaluation } from '../../api/hooks';
import { Card, Skeleton } from '../../components/ui';

export function EvaluationPage() {
  const { data: evaluation, isLoading } = useEvaluation();

  if (isLoading && !evaluation) {
    return <Skeleton lines={4} />;
  }

  return (
    <Card
      title="Evaluation (agent-10)"
      subtitle="Placeholder component — owned by agent-10"
    >
      <details className="text-xs">
        <summary className="cursor-pointer font-medium text-blue-700 hover:underline">
          Inspect EvaluationReport JSON
        </summary>
        <pre className="mt-2 max-h-96 overflow-auto rounded bg-slate-900 p-3 font-mono text-[11px] text-slate-100">
          {JSON.stringify(evaluation ?? null, null, 2)}
        </pre>
      </details>
    </Card>
  );
}

export default EvaluationPage;
