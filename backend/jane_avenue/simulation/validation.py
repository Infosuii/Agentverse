"""Owner: agent-4. Parameter checks run before every simulation (agent-4 brief, M2 item 5).

Every parameter must satisfy `low <= value <= high`, and its distribution's support must contain `value`. A violation
raises a `ValueError` naming the parameter, so a bad registry entry or override fails loudly instead of producing
silently skewed scenarios or bands.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from ..contracts import Assumption

_TOL = 1e-9


def _within(x: float, lo: float, hi: float) -> bool:
    scale = max(1.0, abs(lo), abs(hi))
    return lo - _TOL * scale <= x <= hi + _TOL * scale


def _support_error(p: Assumption) -> str | None:
    d, prm, v = p.distribution, p.distribution.params, p.value
    if d.kind == "fixed":
        return None
    if d.kind in ("normal", "truncated_normal") and prm.get("sd", 0.0) < 0:
        return f"sd must be >= 0 (got {prm['sd']:g})"
    if d.kind == "lognormal":
        if prm.get("sigma", 0.0) < 0:
            return f"sigma must be >= 0 (got {prm['sigma']:g})"
        return None if v > 0 else f"a lognormal distribution needs a positive value (got {v:g})"
    if d.kind == "normal":
        return None
    lo, hi = prm.get("low", p.low), prm.get("high", p.high)
    if hi < lo:
        return f"distribution low {lo:g} is above its high {hi:g}"
    if d.kind == "triangular" and not _within(prm.get("mode", v), lo, hi):
        return f"triangular mode {prm.get('mode', v):g} is outside [{lo:g}, {hi:g}]"
    if not _within(v, lo, hi):
        return f"value {v:g} is outside the {d.kind} support [{lo:g}, {hi:g}]"
    return None


def validate_parameters(params: Mapping[str, Assumption]) -> None:
    """Raise `ValueError` listing every parameter that breaks `low <= value <= high` or its distribution's support."""
    problems: list[str] = []
    for name, p in params.items():
        if not all(math.isfinite(x) for x in (p.value, p.low, p.high)):
            problems.append(f"{name}: value, low and high must be finite numbers")
            continue
        if not _within(p.value, p.low, p.high):
            problems.append(f"{name}: needs low <= value <= high (got {p.low:g} <= {p.value:g} <= {p.high:g})")
            continue
        error = _support_error(p)
        if error:
            problems.append(f"{name}: {error}")
    if problems:
        raise ValueError("Invalid simulation parameters: " + "; ".join(problems))
