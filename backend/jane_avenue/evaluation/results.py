"""Owner: agent-10. STUB: evaluation loader (agent-1 M0). Agent-10 adds `python -m jane_avenue.evaluation.run`."""
from __future__ import annotations

from pathlib import Path

from ..contracts import EvaluationReport, utcnow
from ..data import registry

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "latest.json"


def load_results() -> EvaluationReport:
    if RESULTS_PATH.exists():
        return EvaluationReport.model_validate_json(RESULTS_PATH.read_text(encoding="utf-8"))
    return EvaluationReport(
        generated_at=utcnow(), dataset_version=registry.DATASET_VERSION,
        target_description="Placeholder: the evaluation has not been run yet.",
        methods=[], cases=[], limitations=["No evaluation results yet."], is_placeholder=True,
    )


def revenue_relative_residuals() -> list[float] | None:
    return None
