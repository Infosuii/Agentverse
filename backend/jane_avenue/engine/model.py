"""Owner: agent-3. STUB: scalar engine wrapper with a partial calc trace (agent-1 M0). Agent-3 replaces it."""
from __future__ import annotations

from collections.abc import Mapping

from ..contracts import Assumption, BaselineProjection, CalcStep, EngineResult, MetricProjection, PolicySpec, YearValue
from .core import compute

MODEL_VERSION = "stub-0"

_METRIC_META: dict[str, tuple[str, str, str]] = {
    "revenue_static_gbp_bn": ("Static revenue change", "£bn", "high"),
    "revenue_behavioural_gbp_bn": ("Behavioural revenue change", "£bn", "medium"),
    "revenue_dynamic_gbp_bn": ("Dynamic revenue change", "£bn", "low"),
    "business_investment_pct": ("Business investment change", "%", "medium"),
    "business_investment_gbp_bn": ("Business investment change", "£bn", "medium"),
    "gdp_level_pct": ("GDP level change", "%", "low"),
    "cost_of_capital_pct": ("Cost of capital change", "%", "medium"),
}


def run_engine(spec: PolicySpec, params: Mapping[str, Assumption | float], baseline: BaselineProjection,
               scenario: str = "central") -> EngineResult:
    values = {k: (v.value if isinstance(v, Assumption) else float(v)) for k, v in params.items()}
    out = compute(spec, values, baseline)
    metrics = [
        MetricProjection(metric=name, label=label, unit=unit, confidence=conf,  # type: ignore[arg-type]
                         values=[YearValue(fiscal_year=fy, value=float(out.metrics[name][0, i]))
                                 for i, fy in enumerate(out.fiscal_years)],
                         note="" if name == "revenue_static_gbp_bn" else "STUB: not modelled yet (zeros).")
        for name, (label, unit, conf) in _METRIC_META.items()
    ]
    t0, t1 = spec.baseline_rate_pct / 100, spec.proposed_rate_pct / 100  # type: ignore[operator]
    trace: list[CalcStep] = []
    for i, fy in enumerate(out.fiscal_years):
        b0 = float(out.intermediates["B0"][0, i])
        timing = float(out.intermediates["timing"][0, i])
        trace.append(CalcStep(step_id=f"rev.base.{fy}", label=f"Implied main-rate profit base {fy}",
                              formula="B0 = main_rate_profit_share × R × (1 + profit_base_deviation_pct/100) / t0",
                              inputs={"t0": t0}, output=b0, unit="£bn", fiscal_year=fy,
                              parameter_names=["main_rate_profit_share", "profit_base_deviation_pct"],
                              source_ids=list(baseline.source_ids)))
        trace.append(CalcStep(step_id=f"rev.static.{fy}", label=f"Static revenue change {fy}",
                              formula="ΔR_static = (t1 − t0) × B0 × timing",
                              inputs={"t0": t0, "t1": t1, "B0": b0, "timing": timing},
                              output=float(out.metrics["revenue_static_gbp_bn"][0, i]), unit="£bn", fiscal_year=fy,
                              parameter_names=["receipts_first_year_share"], source_ids=list(baseline.source_ids)))
    return EngineResult(model_version=MODEL_VERSION, policy=spec, scenario=scenario, baseline_vintage=baseline.vintage,
                        fiscal_years=out.fiscal_years, metrics=metrics, calc_trace=trace, parameters_used=values,
                        warnings=out.warnings)
