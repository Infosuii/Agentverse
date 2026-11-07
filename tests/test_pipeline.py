from controls import audit
from pipeline import run_detailed


def test_end_to_end_runs_and_logs(tmp_path):
    p = tmp_path / "audit.jsonl"
    out = run_detailed("test", p)
    assert len(out["decisions"]) == len(out["alerts"]) > 0
    assert audit.verify_chain(p)
    # Every escalation or review must require a human.
    for d in out["decisions"]:
        if d.final_action in ("escalate", "human_review"):
            assert d.requires_human
