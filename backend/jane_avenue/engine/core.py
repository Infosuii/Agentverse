"""Owner: agent-3. STUB: pure-numpy engine core (agent-1 M0). Implements ONLY the static revenue line (section 9.5);
every other metric is zeros with the correct (n, H) shape. Agent-3 replaces this with the full model.

No I/O and no randomness. Parameters may be scalars or arrays of shape (n,).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from ..contracts import METRIC_NAMES, BaselineProjection, PolicySpec, fiscal_year_of, fiscal_year_range

MAIN_POOL_WDA = 0.18  # main-pool writing-down allowance (gov.uk capital allowances guidance; agent-3 to verify)
SBA_RATE = 0.03  # structures and buildings allowance, straight line (gov.uk; agent-3 to verify)


@dataclass
class CoreOutputs:
    fiscal_years: list[str]
    metrics: dict[str, np.ndarray]  # metric -> (n, H)
    intermediates: dict[str, np.ndarray]
    warnings: list[str] = field(default_factory=list)


def _n_draws(params: Mapping[str, float | np.ndarray]) -> int:
    n = 1
    for v in params.values():
        arr = np.asarray(v)
        if arr.ndim == 1:
            n = max(n, arr.shape[0])
    return n


def _col(params: Mapping[str, float | np.ndarray], name: str, n: int) -> np.ndarray:
    return np.broadcast_to(np.asarray(params[name], dtype=float).reshape(-1, 1), (n, 1))


def compute(spec: PolicySpec, params: Mapping[str, float | np.ndarray], baseline: BaselineProjection) -> CoreOutputs:
    if spec.baseline_rate_pct is None or spec.proposed_rate_pct is None or spec.effective_date is None:
        raise ValueError("compute needs baseline_rate_pct, proposed_rate_pct and effective_date")
    warnings: list[str] = []
    horizon = spec.horizon_years
    years = fiscal_year_range(fiscal_year_of(spec.effective_date), horizon)
    by_year = {y.fiscal_year: y.ct_receipts_gbp_bn for y in baseline.years}
    receipts = []
    for fy in years:
        if fy in by_year:
            receipts.append(by_year[fy])
        else:
            receipts.append(baseline.years[-1].ct_receipts_gbp_bn)
            warnings.append(f"Baseline has no {fy}; held receipts flat at the last baseline year.")
    n = _n_draws(params)
    R = np.broadcast_to(np.asarray(receipts, dtype=float).reshape(1, -1), (n, horizon))

    t0 = spec.baseline_rate_pct / 100
    t1 = spec.proposed_rate_pct / 100
    share = _col(params, "main_rate_profit_share", n)
    dev = _col(params, "profit_base_deviation_pct", n)
    first = _col(params, "receipts_first_year_share", n)
    timing = np.ones((n, horizon))
    timing[:, :1] = first

    B0 = share * R * (1 + dev / 100) / t0 if t0 > 0 else np.zeros((n, horizon))
    static = (t1 - t0) * B0 * timing

    metrics = {m: np.zeros((n, horizon)) for m in METRIC_NAMES}
    metrics["revenue_static_gbp_bn"] = static
    return CoreOutputs(fiscal_years=years, metrics=metrics, intermediates={"B0": B0, "timing": timing},
                       warnings=warnings)
