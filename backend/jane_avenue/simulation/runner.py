"""Owner: agent-4. `simulate`: scenarios, Monte Carlo and the tornado in one bundle (MASTER_PROMPT section 9.6).

- Named scenarios (central / optimistic / pessimistic) use the registry defaults for any parameter the analyst
  overrode. When overrides exist, a `custom` scenario carries them, so the UI can overlay custom on central.
- The Monte Carlo and the tornado use the parameters as given, so overrides recentre them.
- Every interval is an assumption-driven range. The empirical (backtest-calibrated) interval is M2.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

from ..contracts import Assumption, BaselineProjection, PolicySpec, ScenarioDefinition, ScenarioResult, SimulationBundle
from ..engine.model import run_engine
from ..engine.parameters import central_values, default_parameters
from .endpoints import evaluate_endpoints
from .montecarlo import monte_carlo
from .scenarios import build_scenarios
from .tornado import sensitivity

MIN_EMPIRICAL_RESIDUALS = 8
CUSTOM_DESCRIPTION = ("Every assumption at its central value, with the analyst's overrides applied. Compare it with "
                      "the central scenario, which uses the registry defaults. Not a forecast.")


def _registry_base(spec: PolicySpec, params: Mapping[str, Assumption]) -> Mapping[str, Assumption]:
    """`params` with every user-overridden entry put back to its registry default."""
    overridden = [name for name, p in params.items() if p.is_user_override]
    if not overridden:
        return params
    defaults = default_parameters(spec)
    return {name: (defaults[name] if name in overridden and name in defaults else p) for name, p in params.items()}


def _empirical_warning(empirical_residuals: Callable[[], list[float] | None] | None) -> str:
    residuals = empirical_residuals() if empirical_residuals is not None else None
    n = len(residuals) if residuals else 0
    if n < MIN_EMPIRICAL_RESIDUALS:
        return (f"No empirical prediction interval is shown: the historical backtest supplied {n} out-of-sample "
                f"residuals, fewer than the {MIN_EMPIRICAL_RESIDUALS} needed to calibrate one. The bands shown are "
                "assumption-driven ranges only.")
    return ("No empirical prediction interval is shown yet: the backtest-calibrated interval is not implemented in "
            "this version. The bands shown are assumption-driven ranges only.")


def simulate(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *, draws: int = 2000,
             seed: int = 42, include_sensitivity: bool = True,
             empirical_residuals: Callable[[], list[float] | None] | None = None) -> SimulationBundle:
    warnings: list[str] = []
    base = _registry_base(spec, params)
    base_endpoints = evaluate_endpoints(spec, base, baseline)
    scenarios = build_scenarios(spec, base, baseline, endpoints=base_endpoints)
    if base is not params:
        values = central_values(params)
        definition = ScenarioDefinition(name="custom", label="Custom", description=CUSTOM_DESCRIPTION,
                                        parameter_values=values)
        scenarios.append(ScenarioResult(scenario=definition, result=run_engine(spec, values, baseline, "custom")))

    mc = monte_carlo(spec, params, baseline, draws=draws, seed=seed) if draws > 0 else None
    sens = []
    if include_sensitivity:
        endpoints = base_endpoints if base is params else evaluate_endpoints(spec, params, baseline)
        sens = sensitivity(spec, params, baseline, endpoints=endpoints)
    if mc is not None:
        warnings.append(_empirical_warning(empirical_residuals))
    return SimulationBundle(policy=spec, baseline_vintage=baseline.vintage, scenarios=scenarios, monte_carlo=mc,
                            sensitivity=sens, assumptions=list(params.values()), warnings=warnings)
