"""Evaluation on held-out data against benchmarks, with bootstrap 95% CIs. Owner: agent-1.

Benchmark: the rules engine's arrival order (how an analyst works the queue today).
Capacity: the analyst can only review a fraction of alerts (ANALYST_CAPACITY).
"""
import math

import numpy as np
from sklearn.metrics import average_precision_score

from contracts.schemas import PolicyDecision, RiskScore
from data.loaders import load_alert_labels

ANALYST_CAPACITY = 0.25  # fraction of the queue reviewed (assumption: state it in the deck)
N_BOOT = 1000
SEED = 0


def _recall_at_capacity(y: np.ndarray, order: np.ndarray) -> float:
    k = max(1, math.ceil(ANALYST_CAPACITY * len(y)))
    total = y.sum()
    return float(y[order[:k]].sum() / total) if total else float("nan")


def evaluate(decisions: list[PolicyDecision], scores: list[RiskScore], split: str) -> dict:
    """Scores must be in alert arrival order (as produced by data.alerts.make_alerts)."""
    labels = load_alert_labels(split)
    y = np.array([labels[s.alert_id] for s in scores], dtype=float)
    p = np.array([s.probability for s in scores], dtype=float)
    n = len(y)

    def metrics(idx: np.ndarray) -> tuple[float, float]:
        yy, pp = y[idx], p[idx]
        system = _recall_at_capacity(yy, np.argsort(-pp, kind="stable"))
        baseline = _recall_at_capacity(yy, np.arange(len(yy)))
        return system, baseline

    sys_r, base_r = metrics(np.arange(n))
    rng = np.random.default_rng(SEED)
    boots = np.array([metrics(rng.integers(0, n, n)) for _ in range(N_BOOT)])
    boots = boots[~np.isnan(boots).any(axis=1)]

    def ci(col: int) -> list[float]:
        return [float(np.percentile(boots[:, col], 2.5)), float(np.percentile(boots[:, col], 97.5))]

    both = 0 < y.sum() < n
    actions: dict[str, int] = {}
    for d in decisions:
        actions[d.final_action] = actions.get(d.final_action, 0) + 1
    return {
        "split": split,
        "n_alerts": n,
        "n_positive": int(y.sum()),
        "analyst_capacity": ANALYST_CAPACITY,
        "recall_at_capacity_system": sys_r,
        "recall_at_capacity_system_ci95": ci(0),
        "recall_at_capacity_baseline_arrival_order": base_r,
        "recall_at_capacity_baseline_ci95": ci(1),
        "pr_auc_system": float(average_precision_score(y, p)) if both else float("nan"),
        "pr_auc_random": float(y.mean()) if n else float("nan"),
        "final_actions": actions,
        "n_requires_human": sum(d.requires_human for d in decisions),
        "data_is_synthetic": True,  # agent-1: set from the dataset actually used
    }
