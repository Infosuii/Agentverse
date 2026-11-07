"""Sampler tests. Owner: agent-4."""
import numpy as np
import pytest

from jane_avenue.contracts import Assumption, Distribution
from jane_avenue.simulation import sample

N = 40_000


def _a(kind: str, params: dict[str, float], value: float = 0.0, low: float = -1.0, high: float = 1.0,
       slider: tuple[float | None, float | None] = (None, None)) -> Assumption:
    return Assumption(name="x", label="x", description="x", category="structural", unit="fraction", value=value,
                      low=low, high=high, distribution=Distribution(kind=kind, params=params), basis="team_judgement",
                      slider_min=slider[0], slider_max=slider[1])


def _rng(seed: int = 1) -> np.random.Generator:
    return np.random.default_rng(seed)


@pytest.mark.parametrize(("kind", "params", "mean"), [
    ("normal", {"mean": 2.0, "sd": 0.5}, 2.0),
    ("triangular", {"low": 0.05, "mode": 0.2, "high": 0.5}, 0.25),
    ("uniform", {"low": 1.0, "high": 3.0}, 2.0),
    ("lognormal", {"mu": 0.0, "sigma": 0.25}, float(np.exp(0.25**2 / 2))),
])
def test_means(kind, params, mean):
    x = sample(_a(kind, params), N, _rng())
    assert x.shape == (N,)
    assert x.mean() == pytest.approx(mean, rel=0.02, abs=0.01)


def test_normal_spread():
    x = sample(_a("normal", {"mean": 0.0, "sd": 5.0}), N, _rng())
    assert x.std() == pytest.approx(5.0, rel=0.03)


def test_truncated_normal_respects_its_bounds_and_is_symmetric():
    x = sample(_a("truncated_normal", {"mean": 0.0, "sd": 1.0, "low": -0.5, "high": 1.5}), N, _rng())
    assert x.min() >= -0.5 and x.max() <= 1.5
    assert x.mean() > 0  # more mass is kept above the mean than below
    y = sample(_a("truncated_normal", {"mean": 0.0, "sd": 1.0, "low": -1.0, "high": 1.0}), N, _rng())
    assert y.mean() == pytest.approx(0.0, abs=0.02)


def test_truncated_normal_far_tail_falls_back_to_clipping():
    x = sample(_a("truncated_normal", {"mean": 0.0, "sd": 0.01, "low": 50.0, "high": 51.0}), 100, _rng())
    assert x.min() >= 50.0 and x.max() <= 51.0


def test_triangular_stays_within_its_range():
    x = sample(_a("triangular", {"low": 0.3, "mode": 0.6, "high": 1.0}), N, _rng())
    assert x.min() >= 0.3 and x.max() <= 1.0


def test_samples_are_truncated_to_slider_bounds_without_edge_spikes():
    # profit_base_deviation_pct in agent-3's M2: normal(0, 10) on a ±20 slider (about 4.6% of mass outside)
    x = sample(_a("normal", {"mean": 0.0, "sd": 10.0}, slider=(-20.0, 20.0)), N, _rng())
    assert x.min() >= -20.0 and x.max() <= 20.0
    assert np.mean(np.abs(x) == 20.0) == 0.0  # truncation, not clipping: no mass piled on the bounds
    # symmetric truncation at ±2 sd: sd = 10 × sqrt(1 − 2·2·φ(2) / (2Φ(2) − 1)) ≈ 8.80
    assert x.mean() == pytest.approx(0.0, abs=0.2)  # s.e. of the mean is about 0.044 at this n
    assert x.std() == pytest.approx(8.80, rel=0.03)
    y = sample(_a("uniform", {"low": 0.0, "high": 2.0}, slider=(None, 1.0)), N, _rng())
    assert y.min() >= 0.0 and y.max() < 1.0
    assert y.mean() == pytest.approx(0.5, abs=0.01)  # uniform on [0, 1], not half the mass at 1.0


def test_truncation_falls_back_to_clipping_when_no_mass_is_inside():
    x = sample(_a("normal", {"mean": 0.7, "sd": 0.0}, slider=(0.0, 0.5)), 100, _rng())
    assert np.all(x == 0.5)
    y = sample(_a("normal", {"mean": 100.0, "sd": 1.0}, slider=(0.0, 1.0)), 100, _rng())
    assert np.all(y == 1.0)


def test_truncated_draws_are_deterministic_per_seed():
    a = _a("normal", {"mean": 15.0, "sd": 10.0}, slider=(-20.0, 20.0))
    assert np.array_equal(sample(a, 500, _rng(5)), sample(a, 500, _rng(5)))


@pytest.mark.parametrize(("kind", "params", "expected"), [
    ("fixed", {}, 0.7),
    ("normal", {"mean": 0.3, "sd": 0.0}, 0.3),
    ("truncated_normal", {"mean": 0.3, "sd": 0.0, "low": 0.0, "high": 1.0}, 0.3),
    ("triangular", {"low": 0.4, "mode": 0.4, "high": 0.4}, 0.4),
    ("uniform", {"low": 0.2, "high": 0.2}, 0.2),
    ("lognormal", {"mu": 0.0, "sigma": 0.0}, 1.0),
])
def test_degenerate_distributions_return_a_constant(kind, params, expected):
    x = sample(_a(kind, params, value=0.7), 50, _rng())
    assert np.all(x == pytest.approx(expected))


def test_missing_distribution_params_fall_back_to_the_assumption_range():
    x = sample(_a("triangular", {}, value=0.2, low=0.1, high=0.5), N, _rng())
    assert x.min() >= 0.1 and x.max() <= 0.5
    assert x.mean() == pytest.approx((0.1 + 0.2 + 0.5) / 3, rel=0.02)


def test_same_seed_same_draws_and_zero_n():
    a = _a("normal", {"mean": 0.0, "sd": 1.0})
    assert np.array_equal(sample(a, 100, _rng(7)), sample(a, 100, _rng(7)))
    assert not np.array_equal(sample(a, 100, _rng(7)), sample(a, 100, _rng(8)))
    assert sample(a, 0, _rng()).shape == (0,)
