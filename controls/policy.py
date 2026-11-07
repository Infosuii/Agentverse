"""Policy engine: hard limits enforced in code. The agent only recommends. Owner: agent-4."""
import re

from contracts.schemas import Alert, PolicyDecision, Recommendation, RiskScore, Transaction
from controls import limits
from controls.validator import validate

_INJECTION = [re.compile(p, re.IGNORECASE) for p in limits.INJECTION_PATTERNS]


def memo_injection(txns: list[Transaction]) -> list[str]:
    return [t.txn_id for t in txns if any(p.search(t.memo or "") for p in _INJECTION)]


def decide(rec: Recommendation, score: RiskScore, alert: Alert, txns: list[Transaction]) -> PolicyDecision:
    alert_txns = [t for t in txns if t.txn_id in set(alert.txn_ids)]
    max_amount = max((t.amount_gbp for t in alert_txns), default=0.0)
    blocked: list[str] = []
    final = rec.action

    errors = validate(rec, score, alert, txns)
    if errors:
        blocked.extend(f"validation: {e}" for e in errors)
        final = "human_review"

    flagged = memo_injection(alert_txns)
    if flagged:
        blocked.append(f"memo_injection_flagged: {', '.join(flagged)}")
        final = "human_review"

    if rec.action == "close" and final == "close":
        if score.probability > limits.CLOSE_MAX_PROBABILITY:
            blocked.append(f"close_blocked: probability {score.probability} > {limits.CLOSE_MAX_PROBABILITY}")
        if score.uncertain:
            blocked.append("close_blocked: model is uncertain")
        if max_amount >= limits.HUMAN_REVIEW_AMOUNT_GBP:
            blocked.append(f"close_blocked: payment of GBP {max_amount} >= {limits.HUMAN_REVIEW_AMOUNT_GBP}")
        if any(b.startswith("close_blocked") for b in blocked):
            final = "human_review"

    requires_human = final in ("escalate", "human_review") or max_amount >= limits.HUMAN_REVIEW_AMOUNT_GBP
    return PolicyDecision(alert_id=alert.alert_id, final_action=final, blocked=blocked, requires_human=requires_human)
