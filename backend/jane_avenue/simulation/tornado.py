"""Owner: agent-4. Tornado sensitivity analysis (MASTER_PROMPT section 9.6)."""
from __future__ import annotations

from collections.abc import Mapping

from ..contracts import Assumption, BaselineProjection, PolicySpec, SensitivityResult, TornadoItem
from .endpoints import Endpoints, evaluate_endpoints

TORNADO_METRICS: tuple[str, ...] = ("revenue_behavioural_gbp_bn", "business_investment_pct", "gdp_level_pct")


def sensitivity(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *,
                endpoints: Endpoints | None = None) -> list[SensitivityResult]:
    """Final-year tornado per metric: each uncertain parameter from low to high, others central; sorted by swing."""
    ep = endpoints if endpoints is not None else evaluate_endpoints(spec, params, baseline)
    fiscal_year = ep.fiscal_years[-1]
    results = []
    for metric in TORNADO_METRICS:
        lows, highs = ep.low[metric][:, -1], ep.high[metric][:, -1]
        items = [
            TornadoItem(parameter=name, label=params[name].label, low_input=params[name].low,
                        high_input=params[name].high, output_at_low=float(lows[i]), output_at_high=float(highs[i]),
                        swing=abs(float(highs[i]) - float(lows[i])))
            for i, name in enumerate(ep.parameters)
        ]
        items.sort(key=lambda it: (-it.swing, it.parameter))
        results.append(SensitivityResult(metric=metric, fiscal_year=fiscal_year,  # type: ignore[arg-type]
                                         base_output=float(ep.central[metric][-1]), items=items))
    return results
