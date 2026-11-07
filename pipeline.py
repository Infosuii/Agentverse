"""End-to-end run: data -> rules alerts -> risk score -> agent -> controls -> audit log.

Owner: agent-5. Run:  python pipeline.py --split test
"""
import argparse
import json

from agent.triage import triage
from contracts.schemas import PolicyDecision
from controls import audit
from controls.policy import decide
from data.alerts import make_alerts
from data.loaders import load_transactions
from risk.score import score


def run_detailed(split: str = "test", audit_path: str | None = None) -> dict:
    txns = load_transactions(split)
    alerts = make_alerts(txns)
    audit.log("data", None, {"split": split, "n_txns": len(txns), "n_alerts": len(alerts)}, audit_path)
    scores = score(alerts, txns)
    recs, decisions = [], []
    for a, s in zip(alerts, scores):
        audit.log("model", a.alert_id, s.model_dump(mode="json"), audit_path)
        rec = triage(a, s, txns)
        audit.log("agent", a.alert_id, rec.model_dump(mode="json"), audit_path)
        d = decide(rec, s, a, txns)
        audit.log("policy", a.alert_id, d.model_dump(mode="json"), audit_path)
        recs.append(rec)
        decisions.append(d)
    return {"txns": txns, "alerts": alerts, "scores": scores, "recommendations": recs, "decisions": decisions}


def run(split: str = "test", audit_path: str | None = None) -> list[PolicyDecision]:
    return run_detailed(split, audit_path)["decisions"]


if __name__ == "__main__":
    from evaluation.run_eval import evaluate

    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val", choices=["train", "val", "test"])
    args = ap.parse_args()
    out = run_detailed(args.split)
    print(json.dumps(evaluate(out["decisions"], out["scores"], args.split), indent=2))
    print("audit chain valid:", audit.verify_chain())
