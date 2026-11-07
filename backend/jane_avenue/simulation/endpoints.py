"""Owner: agent-4. One-at-a-time endpoint evaluations, shared by the scenarios and the tornado.

The batch has 2k + 1 rows: row 0 has every parameter at its central `value`, and rows 2i+1 / 2i+2 move uncertain
parameter i to its `low` / `high` with every other parameter at central. The batch is evaluated with ONE vectorised
`compute` call, and `simulate` reuses it for both the scenarios and the sensitivity analysis.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ..contracts import Assumption, BaselineProjection, PolicySpec
from ..engine import core as engine_core


def uncertain_parameters(params: Mapping[str, Assumption]) -> list[str]:
    """Names of the parameters with a non-fixed distribution, in registry order."""
    return [name for name, p in params.items() if p.distribution.kind != "fixed"]


@dataclass(frozen=True)
class Endpoints:
    fiscal_years: list[str]
    parameters: tuple[str, ...]          # uncertain parameters, in batch order
    central: dict[str, np.ndarray]       # metric -> (H,)
    low: dict[str, np.ndarray]           # metric -> (k, H): parameter i at its low, others central
    high: dict[str, np.ndarray]          # metric -> (k, H): parameter i at its high, others central


def evaluate_endpoints(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection) -> Endpoints:
    names = uncertain_parameters(params)
    n = 2 * len(names) + 1
    values: dict[str, float | np.ndarray] = {name: p.value for name, p in params.items()}
    for i, name in enumerate(names):
        p = params[name]
        col = np.full(n, p.value, dtype=float)
        col[2 * i + 1] = p.low
        col[2 * i + 2] = p.high
        values[name] = col
    out = engine_core.compute(spec, values, baseline)
    horizon = len(out.fiscal_years)
    central, low, high = {}, {}, {}
    for metric, arr in out.metrics.items():
        full = np.broadcast_to(np.asarray(arr, dtype=float), (n, horizon))
        central[metric] = full[0]
        low[metric] = full[1::2]
        high[metric] = full[2::2]
    return Endpoints(fiscal_years=list(out.fiscal_years), parameters=tuple(names), central=central, low=low,
                     high=high)
