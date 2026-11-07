"""Owner: agent-3. Pure-numpy econometric engine core (MASTER_PROMPT section 9.5).

`compute(spec, params, baseline)` evaluates every equation in section 9.5 for n parameter draws at once:

* every parameter may be a scalar or an array of shape (n,); each is reshaped to (n, 1) or (1, 1);
* baseline series are (1, H);
* every metric and per-year intermediate is broadcast to (n, H).

No I/O and no randomness. Units follow the contracts: the returned *_pct metrics are percent and *_gbp_bn metrics are
£bn nominal, with revenue signed from the Exchequer's point of view (positive = more tax). Internal intermediates are
fractions unless their key says otherwise.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from ..contracts import METRIC_NAMES, BaselineProjection, PolicySpec, fiscal_year_of, fiscal_year_range

# Statutory capital-allowance constants (UK, Capital Allowances Act 2001 as amended):
# - Main-pool writing-down allowance: 18% a year on a reducing balance.
#   gov.uk "Claim capital allowances: Writing down allowances" (https://www.gov.uk/work-out-capital-allowances/rates-and-pools)
MAIN_POOL_WDA = 0.18
# - Structures and buildings allowance: 3% a year straight line on qualifying cost, for contracts from 1 April 2020
#   (33 1/3 years). gov.uk "Claiming capital allowances for structures and buildings"
#   (https://www.gov.uk/guidance/claiming-capital-allowances-for-structures-and-buildings)
SBA_RATE = 0.03
# - Full expensing: 100% first-year allowance on new, unused main-pool plant and machinery bought by companies from
#   1 April 2023 (made permanent from Autumn Statement 2023). Assets outside it (used, leased-out, special rate pool at
#   50% FYA, unincorporated businesses) fall back to the WDA; `full_expensing_coverage` is the covered share.
#   gov.uk "Full expensing" (https://www.gov.uk/guidance/capital-allowances-full-expensing-and-50-first-year-allowance)

ASSETS: tuple[str, ...] = ("plant_machinery", "structures", "intangibles")
SHARE_DRIFT_TOLERANCE = 0.01  # |Σ shares − 1| below this is renormalised with a warning; above it is an error

REQUIRED_PARAMETERS: tuple[str, ...] = (
    "taxable_profit_elasticity", "user_cost_elasticity", "profit_gdp_elasticity", "behavioural_first_year_share",
    "receipts_first_year_share", "investment_adjustment_speed", "main_rate_profit_share", "real_required_return",
    "full_expensing_coverage", "allowance_pv_intangibles", "capital_share",
    "share_plant_machinery", "share_structures", "share_intangibles",
    "depreciation_plant_machinery", "depreciation_structures", "depreciation_intangibles",
    "profit_base_deviation_pct", "trend_real_growth",
)

SUPPORTED_POLICY_TYPES = ("corporation_tax_main_rate", "corporation_tax_small_profits_rate")
SMALL_PROFITS_WARNING = (
    "Small profits rate: partial support. The rate change applies to the non-main-rate share of receipts "
    "(1 − main_rate_profit_share); marginal relief interactions and any investment, GDP or dynamic effects are "
    "not modelled."
)


@dataclass
class CoreOutputs:
    fiscal_years: list[str]
    metrics: dict[str, np.ndarray]  # metric -> (n, H)
    intermediates: dict[str, np.ndarray]
    warnings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------------------------------------------------
# Building blocks shared by compute() and by evaluation (agent-10)
# ----------------------------------------------------------------------------------------------------------------------

def _revenue(t0: float, t1: float, b0, elasticity, timing):
    """Static and behavioural revenue (section 9.5). Works on scalars or broadcastable arrays."""
    static = (t1 - t0) * b0 * timing
    b1 = b0 * ((1.0 - t1) / (1.0 - t0)) ** elasticity
    behavioural = (t1 * b1 - t0 * b0) * timing
    return static, b1, behavioural


def revenue_static_behavioural(t0: float, t1: float, receipts: float, *, main_rate_profit_share: float,
                               elasticity: float, timing: float = 1.0) -> tuple[float, float]:
    """(static, behavioural) revenue change for one year. Same equations as compute(); reused by evaluation.

    `t0`/`t1` are fractions, `receipts` is baseline onshore CT receipts in £bn, `elasticity` is the year's effective
    taxable-profit elasticity ε_y and `timing` the share of the year's liability received in that fiscal year.
    """
    _check_rates(t0, t1)
    b0 = main_rate_profit_share * receipts / t0
    static, _, behavioural = _revenue(t0, t1, b0, elasticity, timing)
    return float(static), float(behavioural)


def allowance_pv_plant_machinery(full_expensing_coverage, real_required_return):
    """z_pm: full expensing on the covered share, 18% reducing-balance WDA on the rest (first claim immediate)."""
    r = real_required_return
    wda = MAIN_POOL_WDA * (1.0 + r) / (MAIN_POOL_WDA + r)
    return full_expensing_coverage * 1.0 + (1.0 - full_expensing_coverage) * wda


def allowance_pv_structures(real_required_return):
    """z_st: SBA 3% a year straight line for 1/0.03 = 33⅓ years, first claim immediate."""
    v = 1.0 / (1.0 + real_required_return)
    return SBA_RATE * (1.0 - v ** (1.0 / SBA_RATE)) / (1.0 - v)


def user_cost(t, z, r, delta):
    """Hall–Jorgenson / King–Fullerton user cost of capital: c(t) = (r + δ)(1 − t·z)/(1 − t)."""
    return (r + delta) * (1.0 - t * z) / (1.0 - t)


# ----------------------------------------------------------------------------------------------------------------------
# Validation and baseline helpers
# ----------------------------------------------------------------------------------------------------------------------

def _check_rates(t0: float, t1: float) -> None:
    if not 0 < t0 < 1:
        raise ValueError(f"Baseline rate must be strictly between 0% and 100% (got {t0 * 100:g}%)")
    if not 0 <= t1 < 1:
        raise ValueError(f"Proposed rate must be at least 0% and below 100% (got {t1 * 100:g}%)")


def _n_draws(params: Mapping[str, float | np.ndarray]) -> int:
    n = 1
    for name, v in params.items():
        arr = np.asarray(v)
        if arr.ndim > 1:
            raise ValueError(f"Parameter {name!r} must be a scalar or a 1-D array, got shape {arr.shape}")
        if arr.ndim == 1 and arr.shape[0] != 1:
            if n not in (1, arr.shape[0]):
                raise ValueError(f"Parameter {name!r} has {arr.shape[0]} draws; other parameters have {n}")
            n = arr.shape[0]
    return n


def _col(params: Mapping[str, float | np.ndarray], name: str) -> np.ndarray:
    return np.asarray(params[name], dtype=float).reshape(-1, 1)


def _baseline_series(baseline: BaselineProjection, years: list[str], attr: str,
                     warnings: list[str]) -> np.ndarray:
    """Baseline values for `years`; years outside the baseline extrapolate at the nearest observed growth rate."""
    known = {y.fiscal_year: float(getattr(y, attr)) for y in baseline.years}
    if not known:
        raise ValueError("Baseline has no years")
    ordered = sorted(known)
    first, last = ordered[0], ordered[-1]
    g_last = known[last] / known[ordered[-2]] if len(ordered) > 1 and known[ordered[-2]] else 1.0
    g_first = known[ordered[1]] / known[first] if len(ordered) > 1 and known[first] else 1.0
    out: list[float] = []
    filled: list[str] = []
    for fy in years:
        if fy in known:
            out.append(known[fy])
            continue
        start = int(fy[:4])
        if start > int(last[:4]):
            out.append(known[last] * g_last ** (start - int(last[:4])))
        else:
            out.append(known[first] / g_first ** (int(first[:4]) - start))
        filled.append(fy)
    if filled:
        warnings.append(f"Baseline {attr} has no values for {', '.join(filled)}; extrapolated at the nearest "
                        f"observed annual growth rate.")
    return np.asarray(out, dtype=float).reshape(1, -1)


def _investment_weights(params: Mapping[str, float | np.ndarray], warnings: list[str]) -> dict[str, np.ndarray]:
    raw = {a: _col(params, f"share_{a}") for a in ASSETS}
    if any(np.any(w < 0) for w in raw.values()):
        raise ValueError("Investment shares must be non-negative")
    total = raw["plant_machinery"] + raw["structures"] + raw["intangibles"]
    drift = float(np.max(np.abs(total - 1.0)))
    if drift >= SHARE_DRIFT_TOLERANCE:
        raise ValueError(f"Investment shares must sum to 1 (largest drift {drift:.4f})")
    if drift > 1e-9:
        warnings.append(f"Investment shares summed to {float(np.mean(total)):.4f}; renormalised to 1.")
    return {a: w / total for a, w in raw.items()}


# ----------------------------------------------------------------------------------------------------------------------
# compute()
# ----------------------------------------------------------------------------------------------------------------------

def compute(spec: PolicySpec, params: Mapping[str, float | np.ndarray], baseline: BaselineProjection) -> CoreOutputs:
    if spec.policy_type not in SUPPORTED_POLICY_TYPES:
        raise ValueError(f"The engine does not model policy_type={spec.policy_type!r}")
    if spec.baseline_rate_pct is None or spec.proposed_rate_pct is None:
        raise ValueError("compute needs baseline_rate_pct and proposed_rate_pct")
    if spec.effective_date is None:
        raise ValueError("compute needs effective_date")
    missing = [p for p in REQUIRED_PARAMETERS if p not in params]
    if missing:
        raise ValueError(f"Missing parameters: {', '.join(missing)}")
    t0, t1 = spec.baseline_rate_pct / 100.0, spec.proposed_rate_pct / 100.0
    _check_rates(t0, t1)

    small_profits = spec.policy_type == "corporation_tax_small_profits_rate"
    warnings: list[str] = []
    current = baseline.current_small_profits_rate_pct if small_profits else baseline.current_main_rate_pct
    if abs(spec.baseline_rate_pct - current) > 1e-9:
        warnings.append(f"Policy baseline rate {spec.baseline_rate_pct:g}% differs from the baseline projection's "
                        f"current rate {current:g}% ({baseline.vintage}).")
    if baseline.is_placeholder:
        warnings.append("Baseline projection is a placeholder; figures are for wiring only.")
    if small_profits:
        warnings.append(SMALL_PROFITS_WARNING)

    n = _n_draws(params)
    H = spec.horizon_years
    years = fiscal_year_range(fiscal_year_of(spec.effective_date), H)
    R = _baseline_series(baseline, years, "ct_receipts_gbp_bn", warnings)
    Inv = _baseline_series(baseline, years, "business_investment_gbp_bn", warnings)
    y_idx = np.arange(1, H + 1, dtype=float).reshape(1, -1)
    first_year = y_idx == 1.0

    # ---- Revenue ---------------------------------------------------------------------------------------------------
    share = _col(params, "main_rate_profit_share")
    base_share = (1.0 - share) if small_profits else share
    dev = _col(params, "profit_base_deviation_pct")
    timing = np.where(first_year, _col(params, "receipts_first_year_share"), 1.0)
    eps = _col(params, "taxable_profit_elasticity") * np.where(first_year, _col(params, "behavioural_first_year_share"),
                                                               1.0)
    B0 = base_share * R * (1.0 + dev / 100.0) / t0
    static, B1, behavioural = _revenue(t0, t1, B0, eps, timing)

    # ---- Investment via the user cost of capital ---------------------------------------------------------------------
    w = _investment_weights(params, warnings)
    r = _col(params, "real_required_return")
    deltas = {a: _col(params, f"depreciation_{a}") for a in ASSETS}
    z = {
        "plant_machinery": allowance_pv_plant_machinery(_col(params, "full_expensing_coverage"), r),
        "structures": allowance_pv_structures(r),
        "intangibles": _col(params, "allowance_pv_intangibles"),
    }
    c0 = {a: user_cost(t0, z[a], r, deltas[a]) for a in ASSETS}
    c1 = {a: user_cost(t1, z[a], r, deltas[a]) for a in ASSETS}
    dc_a = {a: c1[a] / c0[a] - 1.0 for a in ASSETS}
    dc = w["plant_machinery"] * dc_a["plant_machinery"] + w["structures"] * dc_a["structures"] \
        + w["intangibles"] * dc_a["intangibles"]                                       # weights already sum to 1
    dI_LR = -_col(params, "user_cost_elasticity") * dc
    dI = dI_LR * (1.0 - (1.0 - _col(params, "investment_adjustment_speed")) ** y_idx)  # (n, H) fraction

    # ---- GDP (partial equilibrium, labour fixed) ---------------------------------------------------------------------
    dbar = sum(w[a] * deltas[a] for a in ASSETS)
    d = dbar + _col(params, "trend_real_growth")
    rows = max(dI.shape[0], d.shape[0])
    dI_full = np.broadcast_to(dI, (rows, H))
    x = np.empty((rows, H))
    prev = np.zeros((rows, 1))
    for j in range(H):  # x_y = (1 − d)·x_{y−1} + d·ΔI_y, x_0 = 0
        prev = (1.0 - d) * prev + d * dI_full[:, j:j + 1]
        x[:, j:j + 1] = prev
    dY = _col(params, "capital_share") * x

    if small_profits:  # no investment channel
        zeros = np.zeros((1, H))
        dc, dI, x, dY = np.zeros((1, 1)), zeros, zeros, zeros
        dI_LR = np.zeros((1, 1))
    dynamic = behavioural + t1 * B1 * timing * dY * _col(params, "profit_gdp_elasticity")

    shape = (n, H)

    def full(a: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(np.broadcast_to(a, shape), dtype=float)

    metrics = {
        "revenue_static_gbp_bn": full(static),
        "revenue_behavioural_gbp_bn": full(behavioural),
        "revenue_dynamic_gbp_bn": full(dynamic),
        "business_investment_pct": full(dI * 100.0),
        "business_investment_gbp_bn": full(dI * Inv),
        "gdp_level_pct": full(dY * 100.0),
        "cost_of_capital_pct": full(dc * 100.0),
    }
    assert set(metrics) == set(METRIC_NAMES)
    intermediates: dict[str, np.ndarray] = {
        "R": R, "I": Inv, "timing": full(timing), "eps": full(eps), "B0": full(B0), "B1": full(B1),
        "dc": np.broadcast_to(dc, (n, 1)), "dI_LR": np.broadcast_to(dI_LR, (n, 1)), "dI": full(dI), "x": full(x),
        "dY": full(dY), "d": np.broadcast_to(d, (n, 1)),
    }
    for a in ASSETS:
        intermediates[f"w_{a}"] = np.broadcast_to(w[a], (n, 1))
        intermediates[f"z_{a}"] = np.broadcast_to(z[a], (n, 1))
        intermediates[f"c0_{a}"] = np.broadcast_to(c0[a], (n, 1))
        intermediates[f"c1_{a}"] = np.broadcast_to(c1[a], (n, 1))
        intermediates[f"dc_{a}"] = np.broadcast_to(dc_a[a], (n, 1))
    return CoreOutputs(fiscal_years=years, metrics=metrics, intermediates=intermediates, warnings=warnings)
