"""Load transactions and labels with a frozen, time-based split.

STUB owned by agent-1: reads the synthetic sample. Replace the reader with the real
dataset, but keep these function signatures and the time-ordered split.
"""
import csv
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from contracts.schemas import Transaction

SAMPLE_DIR = Path(__file__).parent / "sample"
Split = Literal["train", "val", "test"]
# Fractions of the time-ordered data. FROZEN: do not tune on "test".
SPLITS: dict[str, tuple[float, float]] = {"train": (0.0, 0.6), "val": (0.6, 0.8), "test": (0.8, 1.0)}


@lru_cache(maxsize=1)
def _read_all() -> tuple[Transaction, ...]:
    with open(SAMPLE_DIR / "transactions.csv", newline="", encoding="utf-8") as f:
        txns = [
            Transaction(
                txn_id=r["txn_id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                account_from=r["account_from"],
                account_to=r["account_to"],
                amount_gbp=float(r["amount_gbp"]),
                txn_type=r["txn_type"],
                memo=r["memo"],
                is_synthetic=r["is_synthetic"] == "True",
            )
            for r in csv.DictReader(f)
        ]
    return tuple(sorted(txns, key=lambda t: (t.timestamp, t.txn_id)))


def load_transactions(split: Split) -> list[Transaction]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    txns = _read_all()
    lo, hi = SPLITS[split]
    n = len(txns)
    return list(txns[int(lo * n) : int(hi * n)])


@lru_cache(maxsize=1)
def _txn_labels() -> dict[str, int]:
    with open(SAMPLE_DIR / "labels.csv", newline="", encoding="utf-8") as f:
        return {r["txn_id"]: int(r["is_illicit"]) for r in csv.DictReader(f)}


def load_alert_labels(split: Split) -> dict[str, int]:
    """alert_id -> 1 if any transaction in the alert is illicit, else 0.

    Only risk/ (training) and evaluation/ may call this. Never agent/ or app/.
    """
    from data.alerts import make_alerts

    labels = _txn_labels()
    alerts = make_alerts(load_transactions(split))
    return {a.alert_id: max(labels[t] for t in a.txn_ids) for a in alerts}
