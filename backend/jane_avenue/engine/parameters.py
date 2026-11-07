"""Owner: agent-3. STUB: parameter registry (agent-1 M0) from MASTER_PROMPT section 9.5.

Every value is a team prior (`basis="team_judgement"`, `is_placeholder=True`) until agent-3 sources it.
"""
from __future__ import annotations

from collections.abc import Mapping

from ..contracts import Assumption, Distribution, ParameterCategory, PolicySpec

# name, label, category, unit, central, low, high, distribution kind, slider (min, max, step) or None
_Row = tuple[str, str, ParameterCategory, str, float, float, float, str, tuple[float, float, float] | None]
_TABLE: tuple[_Row, ...] = (
    ("taxable_profit_elasticity", "Taxable profit elasticity", "behavioural", "elasticity", 0.20, 0.05, 0.50,
     "triangular", (0.0, 1.0, 0.01)),
    ("user_cost_elasticity", "User cost elasticity of investment", "behavioural", "elasticity", 0.60, 0.30, 1.00,
     "triangular", (0.0, 1.5, 0.01)),
    ("profit_gdp_elasticity", "Profit-GDP elasticity", "structural", "elasticity", 1.0, 0.5, 1.5,
     "triangular", (0.0, 2.0, 0.05)),
    ("behavioural_first_year_share", "Behavioural response in year 1", "timing", "fraction", 0.5, 0.25, 0.75,
     "triangular", (0.0, 1.0, 0.05)),
    ("receipts_first_year_share", "Receipts in year 1", "timing", "fraction", 0.6, 0.45, 0.75,
     "triangular", (0.0, 1.0, 0.05)),
    ("investment_adjustment_speed", "Investment adjustment speed", "timing", "fraction", 0.5, 0.3, 0.8,
     "triangular", (0.1, 1.0, 0.05)),
    ("main_rate_profit_share", "Share of receipts from main-rate profits", "structural", "fraction", 0.85, 0.78, 0.92,
     "triangular", (0.5, 1.0, 0.01)),
    ("real_required_return", "Real required return", "structural", "fraction", 0.05, 0.03, 0.07,
     "triangular", (0.01, 0.10, 0.005)),
    ("full_expensing_coverage", "Full expensing coverage of P&M", "structural", "fraction", 0.80, 0.60, 0.95,
     "triangular", (0.0, 1.0, 0.05)),
    ("allowance_pv_intangibles", "PV of allowances for intangibles", "structural", "fraction", 0.90, 0.70, 1.00,
     "triangular", (0.0, 1.0, 0.05)),
    ("capital_share", "Capital share of output", "structural", "fraction", 0.35, 0.30, 0.40,
     "triangular", (0.2, 0.5, 0.01)),
    ("share_plant_machinery", "Investment share: plant & machinery", "structural", "fraction", 0.40, 0.40, 0.40,
     "fixed", None),
    ("share_structures", "Investment share: structures", "structural", "fraction", 0.27, 0.27, 0.27, "fixed", None),
    ("share_intangibles", "Investment share: intangibles", "structural", "fraction", 0.33, 0.33, 0.33, "fixed", None),
    ("depreciation_plant_machinery", "Depreciation: plant & machinery", "structural", "fraction", 0.175, 0.175, 0.175,
     "fixed", None),
    ("depreciation_structures", "Depreciation: structures", "structural", "fraction", 0.0361, 0.0361, 0.0361,
     "fixed", None),
    ("depreciation_intangibles", "Depreciation: intangibles", "structural", "fraction", 0.1535, 0.1535, 0.1535,
     "fixed", None),
    ("profit_base_deviation_pct", "Profit base deviation from baseline", "macro", "%", 0.0, -5.0, 5.0,
     "normal", (-20.0, 20.0, 0.5)),
    ("trend_real_growth", "Trend real growth", "macro", "fraction", 0.015, 0.015, 0.015, "fixed", None),
)

PARAMETER_NAMES: tuple[str, ...] = tuple(r[0] for r in _TABLE)


def _distribution(kind: str, value: float, low: float, high: float) -> Distribution:
    if kind == "triangular":
        return Distribution(kind="triangular", params={"low": low, "mode": value, "high": high})
    if kind == "normal":
        return Distribution(kind="normal", params={"mean": value, "sd": (high - low) / 2})
    return Distribution(kind="fixed")


def default_parameters(spec: PolicySpec | None = None) -> dict[str, Assumption]:
    out: dict[str, Assumption] = {}
    for name, label, cat, unit, value, low, high, kind, slider in _TABLE:
        out[name] = Assumption(
            name=name, label=label, description=f"{label} (team prior; not yet sourced).", category=cat, unit=unit,
            value=value, low=low, high=high, distribution=_distribution(kind, value, low, high),
            basis="team_judgement", rationale="Team prior from MASTER_PROMPT 9.5; awaiting a citable source.",
            adjustable=slider is not None,
            slider_min=slider[0] if slider else None, slider_max=slider[1] if slider else None,
            slider_step=slider[2] if slider else None, is_placeholder=True,
        )
    return out


def _shift(dist: Distribution, delta: float, lo: float | None, hi: float | None) -> Distribution:
    def clip(x: float) -> float:
        if lo is not None:
            x = max(lo, x)
        if hi is not None:
            x = min(hi, x)
        return x

    keys = {"low", "mode", "high", "mean"}
    params = {k: (clip(v + delta) if k in keys else v) for k, v in dist.params.items()}
    return Distribution(kind=dist.kind, params=params)


def apply_overrides(params: Mapping[str, Assumption], overrides: Mapping[str, float]) -> dict[str, Assumption]:
    """Centre each overridden distribution on the new value, clipped to the slider bounds. Unknown names: ValueError."""
    out = dict(params)
    for name, raw in overrides.items():
        if name not in params:
            raise ValueError(f"Unknown parameter: {name!r}")
        p = params[name]
        value = float(raw)
        if p.slider_min is not None:
            value = max(p.slider_min, value)
        if p.slider_max is not None:
            value = min(p.slider_max, value)
        delta = value - p.value
        low, high = p.low + delta, p.high + delta
        if p.slider_min is not None:
            low = max(p.slider_min, low)
        if p.slider_max is not None:
            high = min(p.slider_max, high)
        out[name] = p.model_copy(update={
            "value": value, "low": low, "high": high, "is_user_override": True,
            "distribution": _shift(p.distribution, delta, p.slider_min, p.slider_max),
        }, deep=True)
    return out


def central_values(params: Mapping[str, Assumption]) -> dict[str, float]:
    return {name: p.value for name, p in params.items()}
