"""Rules engine that raises alerts. It is also the BENCHMARK the system must beat.

STUB owned by agent-1: simple threshold rules per account per day.
"""
from collections import defaultdict

from contracts.schemas import Alert, Transaction

NEAR_THRESHOLD = (9000.0, 10000.0)  # just under the GBP 10k reporting-style threshold
LARGE_AMOUNT = 10000.0
VELOCITY_COUNT = 4  # payments sent by one account in one day


def make_alerts(txns: list[Transaction]) -> list[Alert]:
    """One alert per (sending account, day) that trips any rule, in arrival order."""
    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in txns:
        groups[(t.account_from, t.timestamp.date())].append(t)

    alerts: list[Alert] = []
    for (acct, day), ts in groups.items():
        ts = sorted(ts, key=lambda t: (t.timestamp, t.txn_id))
        triggers = []
        if any(NEAR_THRESHOLD[0] <= t.amount_gbp < NEAR_THRESHOLD[1] for t in ts):
            triggers.append("near_threshold")
        if any(t.amount_gbp >= LARGE_AMOUNT for t in ts):
            triggers.append("large_amount")
        if len(ts) >= VELOCITY_COUNT:
            triggers.append("velocity")
        if triggers:
            alerts.append(
                Alert(
                    alert_id=f"AL-{acct}-{day.isoformat()}",
                    account_id=acct,
                    txn_ids=[t.txn_id for t in ts],
                    created_at=ts[-1].timestamp,
                    trigger="+".join(triggers),
                )
            )
    return sorted(alerts, key=lambda a: (a.created_at, a.alert_id))
