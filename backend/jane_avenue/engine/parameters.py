"""Owner: agent-3. Parameter registry (MASTER_PROMPT section 9.5).

`_TABLE` holds the section 9.5 priors (names, units, central values, ranges, distributions and slider bounds).
`_SOURCING` records agent-3's M2 sourcing on top: basis, source ids, a rationale quoting the figure and where it appears,
and any value or range the sources changed. Parameters that could not be sourced stay `team_judgement` with a widened
range and say so. The investment shares come from agent-6's ONS dataset when it is available; otherwise they keep the
9.5 prior and stay `is_placeholder=True`.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from ..contracts import Assumption, Distribution, ParameterBasis, ParameterCategory, PolicySpec

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


@dataclass(frozen=True)
class _Sourcing:
    """Agent-3's M2 sourcing for one parameter. `value`/`low`/`high` replace the 9.5 prior only where given."""
    basis: ParameterBasis
    source_ids: tuple[str, ...]
    rationale: str
    value: float | None = None
    low: float | None = None
    high: float | None = None


_JUDGEMENT = "Team judgement: no citable estimate found, so the range was widened from the 9.5 prior."

# Each rationale quotes the figure and where it appears. Sources are registered in data/curated/literature_sources.csv.
_SOURCING: dict[str, _Sourcing] = {
    "taxable_profit_elasticity": _Sourcing(
        "literature", ("D-lit-devereux2014", "D-lit-devereux2012", "D-lit-obr2021"),
        "Devereux, Liu & Loretz (UK CT returns 2001-08; abstract) estimate an elasticity of taxable income of "
        "0.14-0.18 for companies around the £300k kink and 0.54-0.57 around the £10k kink. The OBR's March 2021 "
        "costing of the 19%→25% rise (supplementary release, Table 1.1) cuts the 2025-26 static yield by 6% for "
        "profit shifting (semi-elasticity 0.65, 0.38 effective) and 10% for all behaviour, which this model "
        "reproduces with ε ≈ 0.19 and ε ≈ 0.32 respectively. Central 0.20; the range spans the small-company estimate."),
    "user_cost_elasticity": _Sourcing(
        "literature", ("D-lit-chirinko2008",),
        "Chirinko (2008, J. Macroeconomics 30(2), abstract): 'the weight of the evidence suggests a value of σ in "
        "the range of 0.40-0.60'. With a CES technology σ equals the long-run user cost elasticity of capital. "
        "Central 0.60 sits at the top of that range; the high end of 1.0 covers Cobb-Douglas."),
    "profit_gdp_elasticity": _Sourcing("team_judgement", (), _JUDGEMENT + " Unit elasticity assumes the taxable "
                                       "profit base moves in proportion to GDP.", low=0.3, high=1.7),
    "behavioural_first_year_share": _Sourcing(
        "team_judgement", ("D-lit-obr2021",),
        _JUDGEMENT + " OBR's 2021 costing note reports behaviour by year but no phasing parameter.", low=0.15,
        high=0.85),
    "receipts_first_year_share": _Sourcing(
        "official", ("D-lit-hmt2021",),
        "HM Treasury Budget 2021 policy costings (p.20, CT main rate to 25% from April 2023): +£11,900m in 2023-24 "
        "vs +£16,250m in 2024-25, a first-year ratio of 0.73. That ratio also contains a smaller first-year "
        "behavioural response, so it is an upper bound on the cash-timing share; central 0.6 kept, high 0.75 covers it."),
    "investment_adjustment_speed": _Sourcing("team_judgement", (), _JUDGEMENT, low=0.2, high=0.9),
    "main_rate_profit_share": _Sourcing(
        "official", ("D-lit-hmrc2026",),
        "HMRC Corporation Tax statistics 2026 (Figure 8, 2024-25 CT chargeable by rate): main rate £77.5bn, "
        "marginal relief £9.0bn, small profits rate £2.9bn, so the main rate is 77.5/89.4 = 0.87 of the total.",
        value=0.87),
    "real_required_return": _Sourcing(
        "literature", ("D-lit-hanappi2018",),
        "Hanappi (2018), OECD Taxation Working Paper 38, Tables 1-A/1-B (p.19): real interest rate 5.00% in "
        "scenario 1 and 2.00% in scenario 2 (pre-tax real return p = 20%). Central 5%; low widened to 2%.",
        low=0.02),
    "full_expensing_coverage": _Sourcing(
        "team_judgement", ("D-lit-hmrc2023", "D-lit-hmt2023"),
        _JUDGEMENT + " HMRC guidance limits full expensing to companies' new, unused main-rate plant and "
        "machinery (no cars, no assets bought to lease); special-rate assets get a 50% FYA. The Autumn Statement "
        "2023 costing (p.22) does not publish the qualifying share.", low=0.5),
    "allowance_pv_intangibles": _Sourcing("team_judgement", (), _JUDGEMENT + " Reflects relief at accounting "
                                          "amortisation or 4% a year plus R&D relief.", low=0.6),
    "capital_share": _Sourcing(
        "official", ("D-lit-ons2024",),
        "ONS 'Trends in the UK labour share: 1997 to 2023' (main points): labour share 59.5% of GVA at factor cost "
        "in 2023, so the capital share is 0.405. Central 0.40, range 0.35-0.45.", value=0.40, low=0.35, high=0.45),
    "depreciation_plant_machinery": _Sourcing(
        "team_judgement", ("D-lit-oecd2023",),
        "Team judgement: a standard Devereux-Griffith input that could not be verified against a primary source. "
        "The range is widened to the OECD explanatory annex (Table A.4), which uses 12.6% for industrial machinery to 37.0% for computer hardware.", low=0.12, high=0.37),
    "depreciation_structures": _Sourcing(
        "team_judgement", ("D-lit-oecd2023",),
        "Team judgement: a standard Devereux-Griffith input that could not be verified against a primary source. "
        "The range is widened to the OECD explanatory annex (Table A.4), which uses 3.29% for non-residential structures.", low=0.025, high=0.05),
    "depreciation_intangibles": _Sourcing(
        "team_judgement", ("D-lit-oecd2023",),
        "Team judgement: a standard Devereux-Griffith input that could not be verified against a primary source. "
        "The range is widened to the OECD explanatory annex (Table A.4), which uses 40.3% for acquired software.", low=0.10, high=0.40),
    "profit_base_deviation_pct": _Sourcing(
        "official", ("D-lit-obr2024",),
        "OBR Forecast evaluation report October 2024 (Table 3.1): the March 2023 forecast of 2023-24 onshore CT "
        "was £76.9bn against an outturn of £91.6bn (+19%; £10.9bn from fiscal forecasting differences). The 9.5 "
        "prior of ±5% is too narrow for such errors, so widened to normal(0, 10).", low=-10.0, high=10.0),
    "trend_real_growth": _Sourcing(
        "team_judgement", ("D-lit-obr2018",),
        "Team judgement anchored on the OBR: trend productivity growth of 1.2% a year at the end of the November "
        "2017 medium term, rising to 2.0% from 2030-31 in the July 2018 FSR (Box 3.1).", low=0.010, high=0.020),
}

_SHARE_SOURCE = "D-ons-investment"
_SHARE_NAMES = ("share_plant_machinery", "share_structures", "share_intangibles")


def _investment_shares() -> tuple[dict[str, float], str] | None:
    """Latest-year asset shares from agent-6's ONS business investment by asset dataset, or None if unavailable."""
    try:
        from ..data.registry import load_series
        series = load_series("business_investment_by_asset")
    except Exception:  # noqa: BLE001 - parameters must still load if the data layer is unavailable
        return None
    if series is None:
        return None
    shares = {f"share_{p.period}": float(p.value) for p in series.points}
    if set(shares) != set(_SHARE_NAMES) or abs(sum(shares.values()) - 1.0) > 0.01:
        return None
    return shares, series.title


def default_parameters(spec: PolicySpec | None = None) -> dict[str, Assumption]:
    if spec is not None and spec.policy_type == "tax_measure":  # ready-reckoner measures (contract-change #93)
        from .reckoner import default_parameters as reckoner_parameters

        return reckoner_parameters(spec)
    out: dict[str, Assumption] = {}
    for name, label, cat, unit, value, low, high, kind, slider, description in _TABLE:
        s = _SOURCING.get(name)
        if s is not None:
            value = s.value if s.value is not None else value
            low = s.low if s.low is not None else low
            high = s.high if s.high is not None else high
        out[name] = Assumption(
            name=name, label=label, description=description, category=cat, unit=unit,
            value=value, low=low, high=high,
            distribution=_distribution(kind, value, low, high) if kind != "fixed" else Distribution(kind="fixed"),
            basis=s.basis if s else "team_judgement", source_ids=list(s.source_ids) if s else [],
            rationale=s.rationale if s else _PLACEHOLDER_RATIONALE,
            adjustable=slider is not None,
            slider_min=slider[0] if slider else None, slider_max=slider[1] if slider else None,
            slider_step=slider[2] if slider else None, is_placeholder=s is None,
        )
    shares = _investment_shares()
    if shares is not None:
        values, title = shares
        for name in _SHARE_NAMES:
            v = values[name]
            out[name] = out[name].model_copy(update={
                "value": v, "low": v, "high": v, "basis": "official", "source_ids": [_SHARE_SOURCE],
                "rationale": f"ONS business investment by asset ({title}, agent-6 dataset business_investment_by_asset):"
                             f" {v:.1%} of the three-asset total.",
                "is_placeholder": False})
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
    same delta, clipped to the slider bounds, so `low ≤ value ≤ high` always holds. Unknown names, fixed
    (non-adjustable) parameters and non-finite values raise ValueError, which the API returns as 422.
    """
    out = dict(params)
    for name, raw in overrides.items():
        if name not in params:
            raise ValueError(f"Unknown parameter: {name!r}")
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"Override for {name!r} must be a finite number")
        p = params[name]
        if not p.adjustable:
            raise ValueError(f"Parameter {name!r} is fixed and cannot be overridden")
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
