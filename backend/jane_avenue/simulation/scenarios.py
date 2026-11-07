"""Owner: agent-4. Central, optimistic and pessimistic scenarios (MASTER_PROMPT section 9.6)."""
from __future__ import annotations

from collections.abc import Mapping

from ..contracts import Assumption, BaselineProjection, PolicySpec, ScenarioDefinition, ScenarioResult
from ..engine.model import run_engine
from ..engine.parameters import central_values
from .endpoints import Endpoints, evaluate_endpoints

SELECTION_METRIC = "revenue_dynamic_gbp_bn"
MACRO_RULE_PARAMETER = "profit_base_deviation_pct"

_RULE = ("Each uncertain assumption (any non-fixed distribution) is tested one at a time at the low and the high end "
         "of its range, with every other assumption at its central value, and the end giving the {better} cumulative "
         "dynamic revenue (revenue_dynamic_gbp_bn summed over the horizon) is used. This works the same way for "
         "rises and cuts. The profit base deviation is a macro assumption and is set by rule to its {end} value. "
         "Assumptions that do not change cumulative dynamic revenue, and fixed assumptions, stay at central. This is "
         "a combination of {adj} assumptions under the model, not a forecast.")

DESCRIPTIONS: dict[str, str] = {
    "central": ("Every assumption at its central value. This is the model's central scenario under these "
                "assumptions, not a forecast."),
    "optimistic": "Optimistic: " + _RULE.format(better="higher", end="high", adj="favourable"),
    "pessimistic": "Pessimistic: " + _RULE.format(better="lower", end="low", adj="unfavourable"),
}
LABELS = {"central": "Central", "optimistic": "Optimistic", "pessimistic": "Pessimistic"}


def scenario_values(params: Mapping[str, Assumption], endpoints: Endpoints) -> dict[str, dict[str, float]]:
    """Parameter values for central, optimistic and pessimistic, chosen from the endpoint evaluations."""
    central = central_values(params)
    optimistic, pessimistic = dict(central), dict(central)
    cum_low = endpoints.low[SELECTION_METRIC].sum(axis=1)
    cum_high = endpoints.high[SELECTION_METRIC].sum(axis=1)
    for i, name in enumerate(endpoints.parameters):
        p = params[name]
        if name == MACRO_RULE_PARAMETER:
            optimistic[name], pessimistic[name] = p.high, p.low
            continue
        lo, hi = float(cum_low[i]), float(cum_high[i])
        if abs(hi - lo) <= 1e-12 * max(1.0, abs(lo), abs(hi)):
            continue  # no effect on cumulative dynamic revenue: stay at central
        optimistic[name], pessimistic[name] = (p.high, p.low) if hi > lo else (p.low, p.high)
    return {"central": central, "optimistic": optimistic, "pessimistic": pessimistic}


def with_values(params: Mapping[str, Assumption], values: Mapping[str, float]) -> dict[str, Assumption]:
    """`params` with each `value` replaced, keeping the Assumption (and its source_ids for the calc trace)."""
    return {name: (p.model_copy(update={"value": values[name]}) if name in values else p) for name, p in params.items()}


def build_scenarios(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *,
                    endpoints: Endpoints | None = None) -> list[ScenarioResult]:
    """Return the central, optimistic and pessimistic scenarios, in that order."""
    ep = endpoints if endpoints is not None else evaluate_endpoints(spec, params, baseline)
    out = []
    for name, values in scenario_values(params, ep).items():
        definition = ScenarioDefinition(name=name, label=LABELS[name], description=DESCRIPTIONS[name],  # type: ignore[arg-type]
                                        parameter_values=values)
        out.append(ScenarioResult(scenario=definition, result=run_engine(spec, with_values(params, values),
                                                                             baseline, name)))
    return out
