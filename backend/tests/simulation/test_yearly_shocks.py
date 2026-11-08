"""Monte Carlo yearly profit-base shocks (#102): uncertainty grows with the horizon. Owner: agent-5."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from jane_avenue import engine
from jane_avenue.contracts import PolicySpec
from jane_avenue.data import registry
from jane_avenue.engine import core
from jane_avenue.simulation.montecarlo import DRIFT, deviation_paths, simulate_draws

SPEC = PolicySpec(policy_type="corporation_tax_main_rate", tax="corporation_tax", baseline_rate_pct=25,
                  proposed_rate_pct=28, effective_date=date(2027, 4, 1), horizon_years=5)
METRIC = "revenue_behavioural_gbp_bn"


def _draws(drift: float, n: int = 2000):
    params = engine.apply_overrides(engine.default_parameters(SPEC), {DRIFT: drift})
    return simulate_draws(SPEC, params, registry.load_baseline(), draws=n, seed=42).metrics[METRIC]


def test_zero_drift_reproduces_the_one_level_shift_model_exactly() -> None:
    a = _draws(0.0)
    ratio = a[:, 2:] / a[:, [1]]  # every path is one shape scaled per draw
    assert np.allclose(ratio.std(axis=0), 0.0)


def test_drift_lets_paths_cross_and_widens_the_fan() -> None:
    flat, drifting = _draws(0.0), _draws(5.0)
    width = lambda a: np.percentile(a, 95, axis=0) - np.percentile(a, 5, axis=0)  # noqa: E731
    assert width(drifting)[-1] > width(flat)[-1] * 1.2  # year 5 noticeably wider
    assert np.allclose(width(drifting)[0], width(flat)[0], rtol=0.15)  # year 1 essentially unchanged
    ratio = drifting[:, 2:] / drifting[:, [1]]
    assert (ratio.std(axis=0) > 0.01).all()  # no longer scaled copies
    assert abs(drifting.mean(axis=0)[-1] - flat.mean(axis=0)[-1]) < 0.05 * abs(flat.mean(axis=0)[-1])


def test_other_parameters_draws_are_untouched() -> None:
    # The shocks are drawn after every other parameter, so year 1 (no shock yet) is identical.
    np.testing.assert_allclose(_draws(0.0, 500)[:, 0], _draws(7.0, 500)[:, 0])


def test_deviation_paths_random_walk() -> None:
    rng = np.random.default_rng(0)
    paths = deviation_paths(np.zeros(20000), 5.0, 5, rng)
    assert paths.shape == (20000, 5) and np.all(paths[:, 0] == 0)
    np.testing.assert_allclose(paths.std(axis=0), 5.0 * np.sqrt(np.arange(5)), rtol=0.05)


def test_engine_accepts_a_path_only_for_the_deviation_and_checks_its_length() -> None:
    values = engine.central_values(engine.default_parameters(SPEC))
    flat = core.compute(SPEC, values, registry.load_baseline()).metrics[METRIC]
    path = core.compute(SPEC, {**values, "profit_base_deviation_pct": np.zeros((1, 5))},
                        registry.load_baseline()).metrics[METRIC]
    np.testing.assert_allclose(path, flat)
    with pytest.raises(ValueError, match="horizon"):
        core.compute(SPEC, {**values, "profit_base_deviation_pct": np.zeros((1, 3))}, registry.load_baseline())
    with pytest.raises(ValueError, match="1-D"):
        core.compute(SPEC, {**values, "taxable_profit_elasticity": np.zeros((1, 5))}, registry.load_baseline())
