"""Simulation test fixtures. Owner: agent-4.

`full_engine` swaps in a local, vectorised implementation of the MASTER_PROMPT section 9.5 formulas, so the scenario
and tornado logic can be tested with non-zero behavioural, investment, GDP and dynamic metrics before agent-3's full
engine lands. It honours the frozen `compute` signature from Appendix B. Tests that do not request it use the real
`engine.core.compute`.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import numpy as np
import pytest

from jane_avenue.contracts import BaselineProjection, PolicySpec, fiscal_year_of, fiscal_year_range
from jane_avenue.data.registry import load_baseline
from jane_avenue.engine import core as engine_core
from jane_avenue.engine import model as engine_model
from jane_avenue.engine.core import CoreOutputs
from jane_avenue.engine.parameters import default_parameters


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "perf: timing budget test; budgets get 3x slack when CI is set")


def full_compute(spec: PolicySpec, params: Mapping[str, float | np.ndarray], baseline: BaselineProjection) -> CoreOutputs:
    h = spec.horizon_years
    years = fiscal_year_range(fiscal_year_of(spec.effective_date), h)  # type: ignore[arg-type]
    by_year = {y.fiscal_year: y for y in baseline.years}
    rows = [by_year.get(fy, baseline.years[-1]) for fy in years]
    n = max([np.asarray(v).shape[0] for v in params.values() if np.ndim(v) == 1] or [1])

    def col(name: str) -> np.ndarray:
        return np.broadcast_to(np.asarray(params[name], dtype=float).reshape(-1, 1), (n, 1))

    R = np.array([r.ct_receipts_gbp_bn for r in rows]).reshape(1, -1)
    inv = np.array([r.business_investment_gbp_bn for r in rows]).reshape(1, -1)
    t0, t1 = spec.baseline_rate_pct / 100, spec.proposed_rate_pct / 100  # type: ignore[operator]
    first_year = np.arange(h).reshape(1, -1) == 0
    timing = np.where(first_year, col("receipts_first_year_share"), 1.0)
    eps = col("taxable_profit_elasticity") * np.where(first_year, col("behavioural_first_year_share"), 1.0)

    B0 = col("main_rate_profit_share") * R * (1 + col("profit_base_deviation_pct") / 100) / t0
    static = (t1 - t0) * B0 * timing
    B1 = B0 * ((1 - t1) / (1 - t0)) ** eps
    behav = (t1 * B1 - t0 * B0) * timing

    r = col("real_required_return")
    phi = engine_core.MAIN_POOL_WDA
    fe = col("full_expensing_coverage")
    v = 1 / (1 + r)
    z = {"plant_machinery": fe + (1 - fe) * phi * (1 + r) / (phi + r),
         "structures": engine_core.SBA_RATE * (1 - v ** (1 / engine_core.SBA_RATE)) / (1 - v),
         "intangibles": col("allowance_pv_intangibles")}
    w = {a: col(f"share_{a}") for a in z}
    dep = {a: col(f"depreciation_{a}") for a in z}

    def user_cost(t: float, a: str) -> np.ndarray:
        return (r + dep[a]) * (1 - t * z[a]) / (1 - t)

    w_sum = sum(w.values())
    dc = sum(w[a] * (user_cost(t1, a) / user_cost(t0, a) - 1) for a in z) / w_sum
    dI_lr = -col("user_cost_elasticity") * dc
    y = np.arange(1, h + 1).reshape(1, -1)
    dI = dI_lr * (1 - (1 - col("investment_adjustment_speed")) ** y)
    d = sum(w[a] * dep[a] for a in z) / w_sum + col("trend_real_growth")
    x = np.zeros((n, h))
    prev = np.zeros((n, 1))
    for i in range(h):
        prev = (1 - d) * prev + d * dI[:, i:i + 1]
        x[:, i:i + 1] = prev
    dY = col("capital_share") * x
    dynamic = behav + t1 * B1 * timing * dY * col("profit_gdp_elasticity")

    full = lambda a: np.broadcast_to(a, (n, h)).copy()  # noqa: E731
    metrics = {"revenue_static_gbp_bn": full(static), "revenue_behavioural_gbp_bn": full(behav),
               "revenue_dynamic_gbp_bn": full(dynamic), "business_investment_pct": full(dI * 100),
               "business_investment_gbp_bn": full(dI * inv), "gdp_level_pct": full(dY * 100),
               "cost_of_capital_pct": full(np.broadcast_to(dc, (n, h)) * 100)}
    return CoreOutputs(fiscal_years=years, metrics=metrics, intermediates={"B0": full(B0), "timing": full(timing)})


@pytest.fixture
def full_engine(monkeypatch: pytest.MonkeyPatch):
    """Route `engine.core.compute` (and `run_engine`'s reference to it) through `full_compute`."""
    monkeypatch.setattr(engine_core, "compute", full_compute)
    monkeypatch.setattr(engine_model, "compute", full_compute, raising=False)
    return full_compute


@pytest.fixture
def baseline() -> BaselineProjection:
    return load_baseline()


@pytest.fixture
def params():
    return default_parameters()


@pytest.fixture
def cut_policy() -> PolicySpec:
    return PolicySpec(policy_type="corporation_tax_main_rate", tax="corporation_tax", baseline_rate_pct=25.0,
                      proposed_rate_pct=23.0, effective_date=date(2027, 4, 1), horizon_years=5,
                      description="Cut the CT main rate from 25% to 23% from 1 April 2027", raw_query="25 to 23",
                      parse_method="manual")
