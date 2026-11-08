"""Monte Carlo trajectory chart, rendered with matplotlib from the REAL draws (issue #98).

Every element is computed from `simulation.montecarlo.simulate_draws`, the same draw matrix that produces the stored
percentile bands:

- grey lines: a random subset of actual draws (each one a full simulated path across the horizon);
- shaded bands: the 5-95% and 25-75% ranges of ALL draws, year by year;
- green and red dashed lines: the 95th and 5th percentiles of all draws;
- black line: the mean of all draws.

Nothing is interpolated or invented: points sit only on modelled fiscal years. The pre-policy year is drawn at 0
because every metric is a change against the baseline, which is zero before the policy takes effect.

The bands are assumption-driven ranges, not prediction intervals (MASTER_PROMPT rule 6).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

import matplotlib

matplotlib.use("Agg")  # headless; must precede any figure creation

import numpy as np  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from ..contracts import PercentileBand  # noqa: E402
from ..simulation.montecarlo import Draws  # noqa: E402

Theme = Literal["light", "dark"]
DEFAULT_PATHS = 60
MAX_PATHS = 300

METRIC_LABELS: dict[str, str] = {
    "revenue_static_gbp_bn": "Static revenue change",
    "revenue_behavioural_gbp_bn": "Behavioural revenue change",
    "revenue_dynamic_gbp_bn": "Dynamic revenue change",
    "business_investment_pct": "Business investment change",
    "business_investment_gbp_bn": "Business investment change",
    "gdp_level_pct": "GDP level change",
    "cost_of_capital_pct": "Cost of capital change",
}


@dataclass(frozen=True)
class _Palette:
    background: str
    text: str
    muted: str
    grid: str
    path: str
    path_alpha: float
    band_outer: str
    band_inner: str
    upper: str
    lower: str
    mean: str
    empirical: str


PALETTES: dict[str, _Palette] = {
    "light": _Palette(background="#ffffff", text="#111827", muted="#4b5563", grid="#e5e7eb", path="#6b7280",
                      path_alpha=0.28, band_outer="#22c55e", band_inner="#16a34a", upper="#15803d",
                      lower="#dc2626", mean="#000000", empirical="#0e7490"),
    "dark": _Palette(background="#141a17", text="#e8ede9", muted="#9aa59f", grid="#26302b", path="#9ca3af",
                     path_alpha=0.22, band_outer="#22c55e", band_inner="#4ade80", upper="#4ade80",
                     lower="#f87171", mean="#ffffff", empirical="#5eead4"),
}


def _unit(metric: str) -> str:
    return "£bn" if metric.endswith("_gbp_bn") else "%"


def _fmt(value: float, unit: str) -> str:
    sign = "−" if value < 0 else "+" if value > 0 else ""
    if unit == "£bn":
        return f"{sign}£{abs(value):.1f}bn"
    return f"{sign}{abs(value):.2f}%"


def _previous_fiscal_year(fy: str) -> str:
    start = int(fy[:4]) - 1
    return f"{start}-{str(start + 1)[-2:]}"


def path_indices(n_draws: int, n_paths: int, seed: int) -> np.ndarray:
    """Which draws to plot: a reproducible random subset (no cherry-picking of extremes)."""
    n = max(0, min(n_paths, n_draws))
    return np.sort(np.random.default_rng(seed + 1).choice(n_draws, size=n, replace=False))


def summarise(arr: np.ndarray) -> dict[str, np.ndarray]:
    """Year-by-year statistics of ALL draws (same percentile method as the stored bands)."""
    p5, p25, p50, p75, p95 = np.percentile(arr, [5, 25, 50, 75, 95], axis=0)
    return {"p5": p5, "p25": p25, "p50": p50, "p75": p75, "p95": p95, "mean": arr.mean(axis=0)}


def build_monte_carlo_figure(draws: Draws, metric: str, *, n_paths: int = DEFAULT_PATHS, theme: Theme = "light",
                             title: str | None = None, empirical: Sequence[PercentileBand] | None = None,
                             note: str | None = None, dpi: int = 200) -> Figure:
    """The chart as a matplotlib Figure. Grey path lines carry gid="mc-draw-<index>" (the row in the draw matrix)."""
    if metric not in draws.metrics:
        raise KeyError(f"metric {metric!r} was not modelled for this policy")
    arr = np.asarray(draws.metrics[metric], dtype=float)
    years = list(draws.fiscal_years)
    unit = _unit(metric)
    pal = PALETTES[theme]
    stats = summarise(arr)
    label = METRIC_LABELS.get(metric, metric.replace("_", " "))

    # x positions: 0 = the year before the policy (change = 0 by construction), 1..H = modelled fiscal years.
    xs = np.arange(len(years) + 1)
    xlabels = [_previous_fiscal_year(years[0]), *years]

    def with_origin(values: np.ndarray) -> np.ndarray:
        return np.concatenate([[0.0], values])

    fig = Figure(figsize=(10, 5.8), dpi=dpi, facecolor=pal.background)
    ax = fig.add_axes((0.085, 0.27, 0.775, 0.58), facecolor=pal.background)

    idx = path_indices(arr.shape[0], min(n_paths, MAX_PATHS), draws.seed)
    for i in idx:
        ax.plot(xs, with_origin(arr[i]), color=pal.path, alpha=pal.path_alpha, linewidth=0.8, zorder=2,
                solid_capstyle="round", gid=f"mc-draw-{int(i)}")

    ax.fill_between(xs, with_origin(stats["p5"]), with_origin(stats["p95"]), color=pal.band_outer, alpha=0.16,
                    linewidth=0, zorder=1, label="5–95% of all draws")
    ax.fill_between(xs, with_origin(stats["p25"]), with_origin(stats["p75"]), color=pal.band_inner, alpha=0.26,
                    linewidth=0, zorder=1, label="25–75% of all draws")
    ax.plot(xs, with_origin(stats["p95"]), color=pal.upper, linewidth=2, linestyle=(0, (6, 3)), zorder=4,
            label="95th percentile")
    ax.plot(xs, with_origin(stats["p5"]), color=pal.lower, linewidth=2, linestyle=(0, (6, 3)), zorder=4,
            label="5th percentile")
    if empirical:
        by_year = {b.fiscal_year: b for b in empirical}
        lo = [by_year[y].p5 if y in by_year else np.nan for y in years]
        hi = [by_year[y].p95 if y in by_year else np.nan for y in years]
        ax.plot(xs[1:], hi, color=pal.empirical, linewidth=1.6, linestyle=":", zorder=4,
                label="Backtest-calibrated 5–95%")
        ax.plot(xs[1:], lo, color=pal.empirical, linewidth=1.6, linestyle=":", zorder=4)
    ax.plot(xs, with_origin(stats["mean"]), color=pal.mean, linewidth=3, zorder=5, marker="o", markersize=5,
            label="Mean of all draws")
    ax.plot([0], [0], marker="o", markersize=7, color=pal.mean, zorder=6)

    # Final-year values, labelled at the right edge.
    last = xs[-1]
    for key, colour in (("p95", pal.upper), ("mean", pal.mean), ("p5", pal.lower)):
        value = float(stats[key][-1])
        ax.annotate(f"{'Mean' if key == 'mean' else key} {_fmt(value, unit)}", xy=(last, value),
                    xytext=(8, 0), textcoords="offset points", va="center", fontsize=9, color=colour,
                    fontweight="bold" if key == "mean" else "normal", annotation_clip=False)

    ax.axhline(0, color=pal.muted, linewidth=0.8, alpha=0.6, zorder=1)
    ax.set_xticks(xs, xlabels)
    ax.set_xlim(-0.15, last + 0.15)
    ax.set_ylabel(f"Change vs baseline ({unit})", color=pal.text, fontsize=10)
    ax.grid(axis="y", color=pal.grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(pal.grid)
    ax.tick_params(colors=pal.muted, labelsize=9)

    fig.text(0.085, 0.93, title or label, color=pal.text, fontsize=13, fontweight="bold")
    fig.text(0.085, 0.885, f"{draws.draws:,} Monte Carlo draws · {len(idx)} individual draws shown in grey",
             color=pal.muted, fontsize=9.5)
    handles, labels = ax.get_legend_handles_labels()
    if len(idx):
        from matplotlib.lines import Line2D

        handles = [Line2D([0], [0], color=pal.path, alpha=0.7, linewidth=1), *handles]
        labels = ["Individual draws (sample)", *labels]
    legend = fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.075, 0.175), ncol=4, frameon=False,
                        fontsize=8.5, labelcolor=pal.text, columnspacing=1.6, handlelength=2.4)
    legend.set_zorder(10)
    footer = ("Each grey line is one complete simulated path. Bands and percentile lines use all draws. "
              "Assumption-driven ranges, not statistical prediction intervals.")
    fig.text(0.085, 0.045, footer, color=pal.muted, fontsize=8.5)
    if note:
        fig.text(0.085, 0.015, note, color=pal.lower, fontsize=8.5)

    return fig


def render_monte_carlo(draws: Draws, metric: str, *, n_paths: int = DEFAULT_PATHS, theme: Theme = "light",
                       title: str | None = None, empirical: Sequence[PercentileBand] | None = None,
                       note: str | None = None, fmt: Literal["png", "svg"] = "png", dpi: int = 200) -> bytes:
    fig = build_monte_carlo_figure(draws, metric, n_paths=n_paths, theme=theme, title=title, empirical=empirical,
                                   note=note, dpi=dpi)
    buf = BytesIO()
    fig.savefig(buf, format=fmt, facecolor=PALETTES[theme].background)
    return buf.getvalue()
