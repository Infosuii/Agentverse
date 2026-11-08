"""Owner: agent-4. `simulate`: scenarios, Monte Carlo and the tornado in one bundle (MASTER_PROMPT section 9.6).

- Named scenarios (central / optimistic / pessimistic) use the registry defaults for any parameter the analyst
  overrode. When overrides exist, a `custom` scenario carries them, so the UI can overlay custom on central.
- The Monte Carlo and the tornado use the parameters as given, so overrides recentre them.
- The Monte Carlo bands are assumption-driven ranges. A separately labelled empirical interval for behavioural revenue
  is added only when the backtest justifies it (see `empirical.py`).
- Parameters are validated first (`validation.py`); a bad parameter raises ValueError.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

from ..contracts import Assumption, BaselineProjection, PolicySpec, ScenarioDefinition, ScenarioResult, SimulationBundle
from ..engine.model import run_engine
from ..engine.parameters import central_values, default_parameters
from .empirical import empirical_interval
from .endpoints import evaluate_endpoints
from .montecarlo import monte_carlo
from .scenarios import build_scenarios
from .tornado import sensitivity
from .validation import validate_parameters

MIN_RELIABLE_DRAWS = 500
CUSTOM_DESCRIPTION = ("Every assumption at its central value, with the analyst's overrides applied. Compare it with "
                      "the central scenario, which uses the registry defaults. Not a forecast.")


def _registry_base(spec: PolicySpec, params: Mapping[str, Assumption]) -> Mapping[str, Assumption]:
    """`params` with every user-overridden entry put back to its registry default."""
    overridden = [name for name, p in params.items() if p.is_user_override]
    if not overridden:
        return params
    defaults = default_parameters(spec)
    return {name: (defaults[name] if name in overridden and name in defaults else p) for name, p in params.items()}


def simulate(spec: PolicySpec, params: Mapping[str, Assumption], baseline: BaselineProjection, *, draws: int = 2000,
             seed: int = 42, include_sensitivity: bool = True,
             empirical_residuals: Callable[[], list[float] | None] | None = None) -> SimulationBundle:
    if seed < 0:  # numpy's own message ("expected non-negative integer") does not say which input is wrong
        raise ValueError(f"The Monte Carlo seed must be a non-negative integer, not {seed}.")
    validate_parameters(params)
    warnings: list[str] = []
    base = _registry_base(spec, params)
    if base is not params:
        validate_parameters(base)
    base_endpoints = evaluate_endpoints(spec, base, baseline)
    scenarios = build_scenarios(spec, base, baseline, endpoints=base_endpoints)
    if base is not params:
        values = central_values(params)
        definition = ScenarioDefinition(name="custom", label="Custom", description=CUSTOM_DESCRIPTION,
                                        parameter_values=values)
        scenarios.append(ScenarioResult(scenario=definition, result=run_engine(spec, params, baseline, "custom")))

    mc = monte_carlo(spec, params, baseline, draws=draws, seed=seed) if draws > 0 else None
    sens = []
    if include_sensitivity:
        endpoints = base_endpoints if base is params else evaluate_endpoints(spec, params, baseline)
        sens = sensitivity(spec, params, baseline, endpoints=endpoints)
    if mc is not None:
        if draws < MIN_RELIABLE_DRAWS:
            warnings.append(f"Only {draws} Monte Carlo draws: the percentile bands are noisy. Use at least "
                            f"{MIN_RELIABLE_DRAWS} draws before relying on them.")
        # The empirical interval is calibrated on the corporation-tax backtest, so it applies to CT policies only.
        ct = spec.policy_type in ("corporation_tax_main_rate", "corporation_tax_small_profits_rate")
        residuals = empirical_residuals() if empirical_residuals is not None and ct else None
        # the scenario whose values match the MC parameters: custom when overrides exist, otherwise central
        current = scenarios[-1].result if base is not params else scenarios[0].result
        if ct:
            empirical = empirical_interval(current, residuals)
            if empirical.bands is not None:
                mc = mc.model_copy(update={"empirical_interval": empirical.bands,
                                           "empirical_calibration_note": empirical.note})
            warnings.extend(empirical.warnings)
    return SimulationBundle(policy=spec, baseline_vintage=baseline.vintage, scenarios=scenarios, monte_carlo=mc,
                            sensitivity=sens, assumptions=list(params.values()), warnings=warnings)
