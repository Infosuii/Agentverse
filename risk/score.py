"""Risk scoring: all the maths lives here. No LLM in risk/.

STUB owned by agent-2: a fixed heuristic logistic score. Replace with a trained,
calibrated model (fit on train, calibrate on val), but keep score()'s signature.
"""
import math

from contracts.schemas import Alert, Factor, RiskScore, Transaction
from data.alerts import NEAR_THRESHOLD

MODEL_VERSION = "stub-heuristic-0"
INTERCEPT = -3.0
WEIGHTS = {
    "near_threshold_count": 0.9,
    "n_txns": 0.25,
    "max_amount_k": 0.08,  # max amount in thousands of GBP
}
UNCERTAIN_WIDTH = 0.25


def features(alert: Alert, by_id: dict[str, Transaction]) -> dict[str, float]:
    ts = [by_id[i] for i in alert.txn_ids if i in by_id]
    amounts = [t.amount_gbp for t in ts] or [0.0]
    return {
        "near_threshold_count": float(sum(NEAR_THRESHOLD[0] <= a < NEAR_THRESHOLD[1] for a in amounts)),
        "n_txns": float(len(ts)),
        "max_amount_k": round(max(amounts) / 1000.0, 3),
    }


def score(alerts: list[Alert], txns: list[Transaction]) -> list[RiskScore]:
    by_id = {t.txn_id: t for t in txns}
    out: list[RiskScore] = []
    for a in alerts:
        f = features(a, by_id)
        contribs = {k: WEIGHTS[k] * v for k, v in f.items()}
        p = 1.0 / (1.0 + math.exp(-(INTERCEPT + sum(contribs.values()))))
        # Stub uncertainty: a single very large payment is an "unfamiliar pattern".
        width = 0.3 if (f["n_txns"] == 1 and f["max_amount_k"] >= 15) else 0.1
        low, high = max(0.0, p - width / 2), min(1.0, p + width / 2)
        top = sorted(contribs, key=lambda k: abs(contribs[k]), reverse=True)[:3]
        out.append(
            RiskScore(
                alert_id=a.alert_id,
                probability=round(p, 4),
                interval_low=round(low, 4),
                interval_high=round(high, 4),
                uncertain=(high - low) > UNCERTAIN_WIDTH,
                top_factors=[Factor(name=k, value=f[k], contribution=round(contribs[k], 4)) for k in top],
                model_version=MODEL_VERSION,
            )
        )
    return out
