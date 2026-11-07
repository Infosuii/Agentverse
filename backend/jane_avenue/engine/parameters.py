"""Owner: agent-3. Parameter registry (MASTER_PROMPT section 9.5).

Every value starts as a team prior (`basis="team_judgement"`, `is_placeholder=True`) and is replaced by a sourced
value in M2. Names, units, central values, ranges, distributions and slider bounds follow the section 9.5 table exactly.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from ..contracts import Assumption, Distribution, ParameterCategory, PolicySpec

# name, label, category, unit, central, low, high, distribution kind, slider (min, max, step) or None, description
_Row = tuple[str, str, ParameterCategory, str, float, float, float, str, tuple[float, float, float] | None, str]
_TABLE: tuple[_Row, ...] = (
    ("taxable_profit_elasticity", "Taxable profit elasticity", "behavioural", "elasticity", 0.20, 0.05, 0.50,
     "triangular", (0.0, 1.0, 0.01),
     "Elasticity of the taxable profit base with respect to the net-of-tax rate (1 − t). Captures profit shifting, "
     "timing and real responses that change declared profits."),
    ("user_cost_elasticity", "User cost elasticity of investment", "behavioural", "elasticity", 0.60, 0.30, 1.00,
     "triangular", (0.0, 1.5, 0.01),
     "Long-run percentage fall in business investment for a 1% rise in the user cost of capital (σ)."),
    ("profit_gdp_elasticity", "Profit-GDP elasticity", "structural", "elasticity", 1.0, 0.5, 1.5,
     "triangular", (0.0, 2.0, 0.05),
     "Percentage change in the taxable profit base for a 1% change in the GDP level (η); drives dynamic revenue."),
    ("behavioural_first_year_share", "Behavioural response in year 1", "timing", "fraction", 0.5, 0.25, 0.75,
     "triangular", (0.0, 1.0, 0.05),
     "Share of the long-run taxable-profit response that occurs in the first fiscal year."),
    ("receipts_first_year_share", "Receipts in year 1", "timing", "fraction", 0.6, 0.45, 0.75,
     "triangular", (0.0, 1.0, 0.05),
     "Share of the first year's change in liabilities received as cash in that fiscal year (instalment timing)."),
    ("investment_adjustment_speed", "Investment adjustment speed", "timing", "fraction", 0.5, 0.3, 0.8,
     "triangular", (0.1, 1.0, 0.05),
     "Share of the remaining gap to long-run investment closed each year (λ, partial adjustment)."),
    ("main_rate_profit_share", "Share of receipts from main-rate profits", "structural", "fraction", 0.85, 0.78, 0.92,
     "triangular", (0.5, 1.0, 0.01),
     "Share of onshore CT receipts paid on profits taxed at the main rate; the rest is small profits and marginal "
     "relief."),
    ("real_required_return", "Real required return", "structural", "fraction", 0.05, 0.03, 0.07,
     "triangular", (0.01, 0.10, 0.005),
     "Real discount rate (r) used in the user cost of capital and the present value of capital allowances."),
    ("full_expensing_coverage", "Full expensing coverage of P&M", "structural", "fraction", 0.80, 0.60, 0.95,
     "triangular", (0.0, 1.0, 0.05),
     "Share of plant & machinery investment eligible for full expensing; the rest gets the 18% main-pool WDA."),
    ("allowance_pv_intangibles", "PV of allowances for intangibles", "structural", "fraction", 0.90, 0.70, 1.00,
     "triangular", (0.0, 1.0, 0.05),
     "Present value of tax relief per £1 of intangible investment (intangibles regime and R&D relief)."),
    ("capital_share", "Capital share of output", "structural", "fraction", 0.35, 0.30, 0.40,
     "triangular", (0.2, 0.5, 0.01),
     "Output elasticity with respect to the capital stock (1 − labour share)."),
    ("share_plant_machinery", "Investment share: plant & machinery", "structural", "fraction", 0.40, 0.40, 0.40,
     "fixed", None, "Share of business investment in plant & machinery (incl. transport and ICT equipment)."),
    ("share_structures", "Investment share: structures", "structural", "fraction", 0.27, 0.27, 0.27, "fixed", None,
     "Share of business investment in non-residential buildings and structures."),
    ("share_intangibles", "Investment share: intangibles", "structural", "fraction", 0.33, 0.33, 0.33, "fixed", None,
     "Share of business investment in intellectual property products."),
    ("depreciation_plant_machinery", "Depreciation: plant & machinery", "structural", "fraction", 0.175, 0.175, 0.175,
     "fixed", None, "Annual economic depreciation rate of plant & machinery (δ_pm)."),
    ("depreciation_structures", "Depreciation: structures", "structural", "fraction", 0.0361, 0.0361, 0.0361,
     "fixed", None, "Annual economic depreciation rate of structures (δ_st)."),
    ("depreciation_intangibles", "Depreciation: intangibles", "structural", "fraction", 0.1535, 0.1535, 0.1535,
     "fixed", None, "Annual economic depreciation rate of intangibles (δ_in)."),
    ("profit_base_deviation_pct", "Profit base deviation from baseline", "macro", "%", 0.0, -5.0, 5.0,
     "normal", (-20.0, 20.0, 0.5),
     "Percentage error in the baseline profit base, representing receipts forecast uncertainty."),
    ("trend_real_growth", "Trend real growth", "macro", "fraction", 0.015, 0.015, 0.015, "fixed", None,
     "Long-run trend real growth rate (g), used in the capital-stock law of motion."),
)

PARAMETER_NAMES: tuple[str, ...] = tuple(r[0] for r in _TABLE)
_PLACEHOLDER_RATIONALE = "Team prior from MASTER_PROMPT 9.5; awaiting a citable source."


def _distribution(kind: str, value: float, low: float, high: float) -> Distribution:
    if kind == "triangular":
        return Distribution(kind="triangular", params={"low": low, "mode": value, "high": high})
    if kind == "normal":  # normal(0, 5) for profit_base_deviation_pct: sd = (high − low)/2
        return Distribution(kind="normal", params={"mean": value, "sd": (high - low) / 2})
    return Distribution(kind="fixed")


def default_parameters(spec: PolicySpec | None = None) -> dict[str, Assumption]:
    out: dict[str, Assumption] = {}
    for name, label, cat, unit, value, low, high, kind, slider, description in _TABLE:
        out[name] = Assumption(
            name=name, label=label, description=description, category=cat, unit=unit,
            value=value, low=low, high=high, distribution=_distribution(kind, value, low, high),
            basis="team_judgement", rationale=_PLACEHOLDER_RATIONALE,
            adjustable=slider is not None,
            slider_min=slider[0] if slider else None, slider_max=slider[1] if slider else None,
            slider_step=slider[2] if slider else None, is_placeholder=True,
        )
    return out


def _clip(x: float, lo: float | None, hi: float | None) -> float:
    if lo is not None:
        x = max(lo, x)
    if hi is not None:
        x = min(hi, x)
    return x


def apply_overrides(params: Mapping[str, Assumption], overrides: Mapping[str, float]) -> dict[str, Assumption]:
    """Centre each overridden parameter on its new value.

    The value is clipped to the slider bounds; `low`, `high` and the distribution's mean/mode/low/high shift by the
    same delta, clipped to the slider bounds, so `low ≤ value ≤ high` always holds. Unknown names raise ValueError.
    """
    out = dict(params)
    for name, raw in overrides.items():
        if name not in params:
            raise ValueError(f"Unknown parameter: {name!r}")
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"Override for {name!r} must be a finite number")
        p = params[name]
        lo_b, hi_b = p.slider_min, p.slider_max
        value = _clip(value, lo_b, hi_b)
        delta = value - p.value
        low = min(_clip(p.low + delta, lo_b, hi_b), value)
        high = max(_clip(p.high + delta, lo_b, hi_b), value)
        dist_params = {k: (_clip(v + delta, lo_b, hi_b) if k in ("low", "mode", "high", "mean") else v)
                       for k, v in p.distribution.params.items()}
        if "mode" in dist_params:
            dist_params["mode"] = value
        if "mean" in dist_params:
            dist_params["mean"] = value
        out[name] = p.model_copy(update={
            "value": value, "low": low, "high": high, "is_user_override": True,
            "distribution": Distribution(kind=p.distribution.kind, params=dist_params),
        }, deep=True)
    return out


def central_values(params: Mapping[str, Assumption]) -> dict[str, float]:
    return {name: p.value for name, p in params.items()}
