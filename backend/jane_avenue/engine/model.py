"""Owner: agent-3. Scalar engine wrapper: metric projections plus the full calculation trace (MASTER_PROMPT 9.5).

`run_engine` evaluates `compute` for one parameter set and turns every intermediate into a `CalcStep`, so that every
number the UI shows can be opened to its formula, inputs, parameters and sources. Trace values use the same units as
the metrics they feed: revenue in £bn, investment, capital-stock and GDP changes in percent.
"""
from __future__ import annotations

from collections.abc import Mapping

from ..contracts import Assumption, BaselineProjection, CalcStep, EngineResult, MetricProjection, PolicySpec, YearValue
from .core import (
    ASSETS,
    DG_PRE_TAX_RETURN,
    DG_SOURCE_ID,
    MAIN_POOL_WDA,
    SBA_RATE,
    STATUTORY_SOURCE_IDS,
    compute,
    devereux_griffith,
)

MODEL_VERSION = "engine-1.0.0"

# metric -> (label, unit, confidence). Agent-4's simulation imports this table; keep the name and shape.
_METRIC_META: dict[str, tuple[str, str, str]] = {
    "revenue_static_gbp_bn": ("Static revenue change", "£bn", "high"),
    "revenue_behavioural_gbp_bn": ("Behavioural revenue change", "£bn", "medium"),
    "revenue_dynamic_gbp_bn": ("Dynamic revenue change (indicative)", "£bn", "low"),
    "business_investment_pct": ("Business investment change", "%", "medium"),
    "business_investment_gbp_bn": ("Business investment change", "£bn", "medium"),
    "gdp_level_pct": ("GDP level change (indicative)", "%", "low"),
    "cost_of_capital_pct": ("Cost of capital change", "%", "medium"),
}

_ASSET_LABEL = {"plant_machinery": "plant & machinery", "structures": "structures", "intangibles": "intangibles"}

_INVESTMENT_PARAMS = ["user_cost_elasticity", "real_required_return", "full_expensing_coverage",
                      "allowance_pv_intangibles", "share_plant_machinery", "share_structures", "share_intangibles",
                      "depreciation_plant_machinery", "depreciation_structures", "depreciation_intangibles"]


def _notes(small_profits: bool, coverage: float) -> dict[str, str]:
    indicative = ("Indicative: partial equilibrium with labour held fixed; driven by the investment channel and "
                  "assumption-heavy.")
    notes = {
        "revenue_static_gbp_bn": "Mechanical change: rate change × implied taxable profit base, before behaviour.",
        "revenue_behavioural_gbp_bn": "Conventional costing: the taxable profit base responds to the net-of-tax "
                                      "rate through the taxable profit elasticity.",
        "revenue_dynamic_gbp_bn": "Behavioural revenue plus the receipts effect of the GDP change. " + indicative,
        "business_investment_pct": (
            f"Under full expensing (covering {coverage:.0%} of plant & machinery here) the allowance is worth the "
            "whole cost, so the covered plant & machinery user cost does not depend on the CT rate. A rate change "
            "therefore bites through structures, intangibles and uncovered plant & machinery."),
        "business_investment_gbp_bn": "Percentage change in business investment applied to the baseline level.",
        "gdp_level_pct": "Capital-stock gap × capital share. " + indicative,
        "cost_of_capital_pct": "Investment-weighted change in the user cost of capital across asset types.",
    }
    if small_profits:
        no_channel = "Not modelled for the small profits rate (no investment channel; partial support)."
        for m in ("business_investment_pct", "business_investment_gbp_bn", "gdp_level_pct", "cost_of_capital_pct"):
            notes[m] = no_channel
        notes["revenue_dynamic_gbp_bn"] = "Equals behavioural revenue: no investment or GDP channel for this policy."
    return notes


def run_engine(spec: PolicySpec, params: Mapping[str, Assumption | float], baseline: BaselineProjection,
               scenario: str = "central") -> EngineResult:
    if spec.policy_type == "tax_measure":  # HMRC ready-reckoner measures (engine/reckoner.py, contract-change #93)
        from .reckoner import run_engine as reckoner_run_engine

        return reckoner_run_engine(spec, params, baseline, scenario)
    values = {k: (v.value if isinstance(v, Assumption) else float(v)) for k, v in params.items()}
    param_sources = {k: list(v.source_ids) for k, v in params.items() if isinstance(v, Assumption)}
    out = compute(spec, values, baseline)
    small_profits = spec.policy_type == "corporation_tax_small_profits_rate"
    notes = _notes(small_profits, values.get("full_expensing_coverage", 0.0))

    metrics = [
        MetricProjection(metric=name, label=label, unit=unit, confidence=conf,  # type: ignore[arg-type]
                         values=[YearValue(fiscal_year=fy, value=float(out.metrics[name][0, i]))
                                 for i, fy in enumerate(out.fiscal_years)],
                         note=notes[name])
        for name, (label, unit, conf) in _METRIC_META.items()
    ]

    base_sources = list(baseline.source_ids)

    def sources(names: list[str], *, with_baseline: bool) -> list[str]:
        ids = list(base_sources) if with_baseline else []
        for n in names:
            for s in param_sources.get(n, []):
                if s not in ids:
                    ids.append(s)
        return ids

    trace: list[CalcStep] = []

    def step(step_id: str, label: str, formula: str, inputs: dict[str, float], output: float, unit: str,
             names: list[str], *, fy: str | None = None, with_baseline: bool = False,
             extra_sources: tuple[str, ...] = ()) -> None:
        names = list(dict.fromkeys(names))
        ids = sources(names, with_baseline=with_baseline)
        ids += [s for s in extra_sources if s not in ids]
        trace.append(CalcStep(step_id=step_id, label=label, formula=formula,
                              inputs={k: float(v) for k, v in inputs.items()}, output=float(output), unit=unit,
                              fiscal_year=fy, parameter_names=names, source_ids=ids))

    im = out.intermediates
    t0, t1 = spec.baseline_rate_pct / 100, spec.proposed_rate_pct / 100  # type: ignore[operator]
    r = values["real_required_return"]

    # ---- Year-independent investment steps ---------------------------------------------------------------------------
    statutory = {"plant_machinery": (STATUTORY_SOURCE_IDS["full_expensing"], STATUTORY_SOURCE_IDS["main_pool_wda"]),
                 "structures": (STATUTORY_SOURCE_IDS["sba_rate"],), "intangibles": ()}
    if not small_profits:
        cov = values["full_expensing_coverage"]
        step("inv.allowance_pv.plant_machinery", "PV of capital allowances: plant & machinery",
             f"z_pm = f × 1 + (1 − f) × φ(1 + r)/(φ + r),  φ = {MAIN_POOL_WDA:g} main-pool WDA",
             {"f": cov, "φ": MAIN_POOL_WDA, "r": r}, im["z_plant_machinery"][0, 0], "fraction",
             ["full_expensing_coverage", "real_required_return"], extra_sources=statutory["plant_machinery"])
        step("inv.allowance_pv.structures", "PV of capital allowances: structures (SBA)",
             f"z_st = s × (1 − v^(1/s))/(1 − v),  v = 1/(1 + r),  s = {SBA_RATE:g} SBA straight line",
             {"s": SBA_RATE, "r": r, "v": 1 / (1 + r)}, im["z_structures"][0, 0], "fraction",
             ["real_required_return"], extra_sources=statutory["structures"])
        step("inv.allowance_pv.intangibles", "PV of capital allowances: intangibles",
             "z_in = allowance_pv_intangibles", {"z_in": values["allowance_pv_intangibles"]},
             im["z_intangibles"][0, 0], "fraction", ["allowance_pv_intangibles"])
        for a in ASSETS:
            dep = f"depreciation_{a}"
            z_names = {"plant_machinery": ["full_expensing_coverage", "real_required_return"],
                       "structures": ["real_required_return"], "intangibles": ["allowance_pv_intangibles"]}[a]
            names = sorted({*z_names, "real_required_return", dep})
            base_inputs = {"r": r, "δ": values[dep], "z": im[f"z_{a}"][0, 0]}
            step(f"inv.user_cost.baseline.{a}", f"User cost of capital at {t0:.0%}: {_ASSET_LABEL[a]}",
                 "c(t0) = (r + δ)(1 − t0·z)/(1 − t0)", {**base_inputs, "t0": t0}, im[f"c0_{a}"][0, 0],
                 "fraction per year", names, extra_sources=statutory[a])
            step(f"inv.user_cost.proposed.{a}", f"User cost of capital at {t1:.0%}: {_ASSET_LABEL[a]}",
                 "c(t1) = (r + δ)(1 − t1·z)/(1 − t1)", {**base_inputs, "t1": t1}, im[f"c1_{a}"][0, 0],
                 "fraction per year", names, extra_sources=statutory[a])
            step(f"inv.user_cost.{a}", f"Change in user cost: {_ASSET_LABEL[a]}",
                 "Δc_a = (c(t1)/c(t0) − 1) × 100",
                 {"c(t0)": im[f"c0_{a}"][0, 0], "c(t1)": im[f"c1_{a}"][0, 0]},
                 im[f"dc_{a}"][0, 0] * 100, "%", names)
        step("inv.user_cost.weighted", "Change in the cost of capital (investment-weighted)",
             "Δc = Σ_a w_a·Δc_a / Σ_a w_a",
             {**{f"w_{a}": im[f"w_{a}"][0, 0] for a in ASSETS},
              **{f"Δc_{a}": im[f"dc_{a}"][0, 0] * 100 for a in ASSETS}},
             im["dc"][0, 0] * 100, "%", _INVESTMENT_PARAMS[1:])
        step("inv.long_run", "Long-run change in business investment",
             "ΔI_LR = −σ × Δc", {"σ": values["user_cost_elasticity"], "Δc": im["dc"][0, 0] * 100},
             im["dI_LR"][0, 0] * 100, "%", _INVESTMENT_PARAMS)
        step("gdp.capital_turnover", "Capital-stock adjustment rate",
             "d = Σ_a w_a·δ_a + g",
             {**{f"w_{a}": im[f"w_{a}"][0, 0] for a in ASSETS},
              **{f"δ_{a}": values[f"depreciation_{a}"] for a in ASSETS}, "g": values["trend_real_growth"]},
             im["d"][0, 0], "fraction per year",
             ["share_plant_machinery", "share_structures", "share_intangibles", "depreciation_plant_machinery",
              "depreciation_structures", "depreciation_intangibles", "trend_real_growth"])

        # Explainability extras (not metrics): Devereux-Griffith effective tax rates for the representative
        # investment, i.e. the three assets weighted by their investment shares.
        dg_params = ["real_required_return", "full_expensing_coverage", "allowance_pv_intangibles",
                     "share_plant_machinery", "share_structures", "share_intangibles", "depreciation_plant_machinery",
                     "depreciation_structures", "depreciation_intangibles"]
        dg_sources = (DG_SOURCE_ID, *statutory["plant_machinery"], *statutory["structures"])
        weights = {a: float(im[f"w_{a}"][0, 0]) for a in ASSETS}
        for tag, t, word in (("baseline", t0, "t0"), ("proposed", t1, "t1")):
            per = {a: devereux_griffith(t, float(im[f"z_{a}"][0, 0]), r, values[f"depreciation_{a}"]) for a in ASSETS}
            p_bar = sum(weights[a] * per[a][0] for a in ASSETS)
            step(f"etr.emtr.{tag}", f"Effective marginal tax rate at {t:.0%} (representative investment)",
                 f"EMTR = (p̃ − r)/p̃,  p̃ = Σ_a w_a·[(1 − {word}·z_a)(r + δ_a)/(1 − {word}) − δ_a]",
                 {"r": r, word: t, **{f"w_{a}": weights[a] for a in ASSETS},
                  **{f"p̃_{a}": per[a][0] for a in ASSETS}, "p̃": p_bar},
                 (p_bar - r) / p_bar * 100, "%", dg_params, extra_sources=dg_sources)
            step(f"etr.eatr.{tag}", f"Effective average tax rate at {t:.0%} (representative investment)",
                 f"EATR = Σ_a w_a·[(p − r) − (p + δ_a)(1 − {word}) + (1 − {word}·z_a)(r + δ_a)]/p,  p = "
                 f"{DG_PRE_TAX_RETURN:g} pre-tax real return",
                 {"p": DG_PRE_TAX_RETURN, "r": r, word: t, **{f"w_{a}": weights[a] for a in ASSETS},
                  **{f"EATR_{a}": per[a][2] * 100 for a in ASSETS}},
                 sum(weights[a] * per[a][2] for a in ASSETS) * 100, "%", dg_params, extra_sources=dg_sources)

    # ---- Per-year steps ----------------------------------------------------------------------------------------------
    share_label = "(1 − main_rate_profit_share)" if small_profits else "main_rate_profit_share"
    rev_base_params = ["main_rate_profit_share", "profit_base_deviation_pct"]
    x_prev = 0.0
    for i, fy in enumerate(out.fiscal_years):
        y = i + 1
        R, inv_base = float(im["R"][0, i]), float(im["I"][0, i])
        b0, b1 = float(im["B0"][0, i]), float(im["B1"][0, i])
        timing, eps = float(im["timing"][0, i]), float(im["eps"][0, i])
        timing_params = ["receipts_first_year_share"] if y == 1 else []
        eps_params = ["taxable_profit_elasticity"] + (["behavioural_first_year_share"] if y == 1 else [])
        static = float(out.metrics["revenue_static_gbp_bn"][0, i])
        behav = float(out.metrics["revenue_behavioural_gbp_bn"][0, i])
        dynamic = float(out.metrics["revenue_dynamic_gbp_bn"][0, i])

        step(f"rev.base.{fy}", f"Implied taxable profit base {fy}",
             f"B0 = {share_label} × R × (1 + profit_base_deviation_pct/100) / t0",
             {"R": R, "main_rate_profit_share": values["main_rate_profit_share"],
              "profit_base_deviation_pct": values["profit_base_deviation_pct"], "t0": t0},
             b0, "£bn", rev_base_params, fy=fy, with_baseline=True)
        step(f"rev.static.{fy}", f"Static revenue change {fy}", "ΔR_static = (t1 − t0) × B0 × timing",
             {"t0": t0, "t1": t1, "B0": b0, "timing": timing}, static, "£bn",
             rev_base_params + timing_params, fy=fy, with_baseline=True)
        step(f"rev.base_response.{fy}", f"Taxable profit base after behavioural response {fy}",
             "B1 = B0 × ((1 − t1)/(1 − t0))^ε" + ("  (ε = ε_LR × first-year share)" if y == 1 else ""),
             {"B0": b0, "t0": t0, "t1": t1, "ε": eps}, b1, "£bn", rev_base_params + eps_params, fy=fy,
             with_baseline=True)
        step(f"rev.behavioural.{fy}", f"Behavioural revenue change {fy}", "ΔR_behav = (t1 × B1 − t0 × B0) × timing",
             {"t0": t0, "t1": t1, "B0": b0, "B1": b1, "timing": timing}, behav, "£bn",
             rev_base_params + eps_params + timing_params, fy=fy, with_baseline=True)

        if small_profits:
            step(f"rev.dynamic.{fy}", f"Dynamic revenue change {fy} (indicative)",
                 "ΔR_dynamic = ΔR_behav  (no investment channel for the small profits rate)",
                 {"ΔR_behav": behav}, dynamic, "£bn", rev_base_params + eps_params + timing_params, fy=fy,
                 with_baseline=True)
            continue

        di = float(im["dI"][0, i]) * 100
        x = float(im["x"][0, i]) * 100
        dy = float(im["dY"][0, i]) * 100
        step(f"inv.change.{fy}", f"Business investment change {fy}", "ΔI_y = ΔI_LR × (1 − (1 − λ)^y)",
             {"ΔI_LR": float(im["dI_LR"][0, 0]) * 100, "λ": values["investment_adjustment_speed"], "y": y}, di, "%",
             _INVESTMENT_PARAMS + ["investment_adjustment_speed"], fy=fy)
        step(f"inv.change_gbp.{fy}", f"Business investment change {fy} (£bn)", "ΔI_£ = ΔI_y/100 × I",
             {"ΔI_y": di, "I": inv_base}, float(out.metrics["business_investment_gbp_bn"][0, i]), "£bn",
             _INVESTMENT_PARAMS + ["investment_adjustment_speed"], fy=fy, with_baseline=True)
        step(f"gdp.capital_gap.{fy}", f"Capital stock gap vs baseline {fy}", "x_y = (1 − d) × x_{y−1} + d × ΔI_y",
             {"x_{y−1}": x_prev, "d": float(im["d"][0, 0]), "ΔI_y": di}, x, "%",
             _INVESTMENT_PARAMS + ["investment_adjustment_speed", "trend_real_growth"], fy=fy)
        step(f"gdp.level.{fy}", f"GDP level change {fy} (indicative)", "ΔY_y = capital_share × x_y",
             {"capital_share": values["capital_share"], "x_y": x}, dy, "%",
             _INVESTMENT_PARAMS + ["investment_adjustment_speed", "trend_real_growth", "capital_share"], fy=fy)
        step(f"rev.dynamic.{fy}", f"Dynamic revenue change {fy} (indicative)",
             "ΔR_dynamic = ΔR_behav + t1 × B1 × timing × ΔY_y/100 × η",
             {"ΔR_behav": behav, "t1": t1, "B1": b1, "timing": timing, "ΔY_y": dy,
              "η": values["profit_gdp_elasticity"]}, dynamic, "£bn",
             rev_base_params + eps_params + timing_params + ["profit_gdp_elasticity", "capital_share",
                                                             "investment_adjustment_speed"] + _INVESTMENT_PARAMS,
             fy=fy, with_baseline=True)
        x_prev = x

    return EngineResult(model_version=MODEL_VERSION, policy=spec, scenario=scenario, baseline_vintage=baseline.vintage,
                        fiscal_years=out.fiscal_years, metrics=metrics, calc_trace=trace, parameters_used=values,
                        warnings=out.warnings)
