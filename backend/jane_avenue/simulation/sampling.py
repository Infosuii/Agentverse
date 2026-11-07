"""Owner: agent-4. Draw samples from an `Assumption`'s distribution (MASTER_PROMPT section 9.6).

Every `DistributionKind` is supported. Missing distribution parameters fall back to the assumption's own
`low` / `value` / `high`, and degenerate distributions (zero spread) return a constant. All samples are clipped to
`[slider_min, slider_max]` when those bounds are set.
"""
from __future__ import annotations

import numpy as np

from ..contracts import Assumption

_MAX_REJECTION_ROUNDS = 50


def _truncated_normal(mean: float, sd: float, low: float, high: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Rejection sampling; any draws still missing after the round limit are clipped draws (fallback)."""
    out = np.empty(n)
    filled = 0
    for _ in range(_MAX_REJECTION_ROUNDS):
        if filled == n:
            return out
        x = rng.normal(mean, sd, 2 * (n - filled))
        x = x[(x >= low) & (x <= high)][: n - filled]
        out[filled:filled + x.size] = x
        filled += x.size
    if filled < n:
        out[filled:] = np.clip(rng.normal(mean, sd, n - filled), low, high)
    return out


def _draw(a: Assumption, n: int, rng: np.random.Generator) -> np.ndarray:
    d = a.distribution
    p = d.params
    if d.kind == "normal":
        mean, sd = p.get("mean", a.value), p.get("sd", 0.0)
        return rng.normal(mean, sd, n) if sd > 0 else np.full(n, mean)
    if d.kind == "truncated_normal":
        mean, sd = p.get("mean", a.value), p.get("sd", 0.0)
        low, high = p.get("low", a.low), p.get("high", a.high)
        if sd <= 0 or high <= low:
            return np.full(n, float(np.clip(mean, low, high)))
        return _truncated_normal(mean, sd, low, high, n, rng)
    if d.kind == "triangular":
        low, mode, high = p.get("low", a.low), p.get("mode", a.value), p.get("high", a.high)
        if high <= low:
            return np.full(n, mode)
        return rng.triangular(low, min(max(mode, low), high), high, n)
    if d.kind == "uniform":
        low, high = p.get("low", a.low), p.get("high", a.high)
        return rng.uniform(low, high, n) if high > low else np.full(n, low)
    if d.kind == "lognormal":
        mu, sigma = p.get("mu", float(np.log(a.value)) if a.value > 0 else 0.0), p.get("sigma", 0.0)
        return rng.lognormal(mu, sigma, n) if sigma > 0 else np.full(n, float(np.exp(mu)))
    return np.full(n, a.value)  # "fixed"


def sample(a: Assumption, n: int, rng: np.random.Generator) -> np.ndarray:
    """Return `n` draws of assumption `a` as a float array of shape (n,), clipped to the slider bounds."""
    if n <= 0:
        return np.empty(0)
    x = np.asarray(_draw(a, n, rng), dtype=float)
    if a.slider_min is not None or a.slider_max is not None:
        x = np.clip(x, a.slider_min if a.slider_min is not None else -np.inf,
                    a.slider_max if a.slider_max is not None else np.inf)
    return x
