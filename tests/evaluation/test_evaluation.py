import math

from evaluation.run_eval import evaluate
from pipeline import run_detailed


def test_evaluate_reports_metrics_with_ci(tmp_path):
    out = run_detailed("val", tmp_path / "audit.jsonl")
    r = evaluate(out["decisions"], out["scores"], "val")
    assert r["n_alerts"] == len(out["alerts"])
    for key in ("recall_at_capacity_system", "recall_at_capacity_baseline_arrival_order"):
        assert math.isnan(r[key]) or 0 <= r[key] <= 1
    lo, hi = r["recall_at_capacity_system_ci95"]
    assert lo <= hi
