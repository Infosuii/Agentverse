"""Ready-reckoner model for tax and benefit measures (contract-change #93). Owner: agent-3 (written by agent-2 on the
human owner's instruction, for owner review).

Every number comes from HMRC's official "Direct effects of illustrative tax changes" (June 2025), never from Gemini:

1. **Costed change.** HMRC costs small illustrative changes ("change the basic rate by 1p": +£6.9bn, +£8.25bn,
   +£8.2bn in 2026-27 to 2028-29). The change the analyst asked for is mapped onto those points by piecewise-linear
   interpolation through zero (one point: a straight line; CGT has points at 1, 5 and 10pp, and the signs show that its
   yield turns negative as the rate rises). Beyond the largest costed point the last segment is extended, and the scope
   gate warns. Decreases use HMRC's own "cost" rows where they exist, otherwise they mirror the increase.
2. **Timing.** The ready reckoner's three columns are the first, second and third years of a change made in 2026-27.
   Policy year k uses column min(k, 3), uprated to the policy's fiscal year by OBR nominal GDP (the baseline):
   effect × GDP(policy year) / GDP(ready-reckoner year). Years after the third repeat the third-year effect grown with
   nominal GDP.
3. **Uncertainty.** One assumption, `rr_costing_scale` (central 1.0), multiplies the official effect. Its range is a
   labelled team judgement: HMRC's figures are direct effects of *small* changes, and larger changes need not scale
   linearly.

Metrics: `revenue_static_gbp_bn` is the official direct effect scaled to the change; `revenue_behavioural_gbp_bn` applies
the costing scale; `revenue_dynamic_gbp_bn` equals it (no macroeconomic feedback is modelled). Investment and GDP are
not modelled, so those metrics are absent rather than zero.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from ..contracts import (
    Assumption,
    BaselineProjection,
    CalcStep,
    Distribution,
    EngineResult,
    MetricProjection,
    PolicySpec,
    YearValue,
    fiscal_year_of,
    fiscal_year_range,
)

MODEL_VERSION = "reckoner-1.0.0"
PARAMETER = "rr_costing_scale"
RR_SOURCE_ID = "D-hmrc-ready-reckoner-2025"
UNIT_LABEL = {"pp": "percentage points", "gbp": "£", "gbp_per_week": "£ a week", "pct_of_rate": "% of the duty rate"}
METRICS = ("revenue_static_gbp_bn", "revenue_behavioural_gbp_bn", "revenue_dynamic_gbp_bn")


def fmt_change(x: float, unit: str) -> str:
    """A change in a measure's unit, in words: "2 percentage points", "£1,000", "£5 a week", "5% of the duty rate"."""
    if unit == "gbp":
        return f"£{fmt(x)}"
    if unit == "gbp_per_week":
        return f"£{fmt(x)} a week"
    if unit == "pct_of_rate":
        return f"{fmt(x)}% of the duty rate"
    return f"{fmt(x)} percentage points"


def fmt(x: float) -> str:
    """9.44287 -> "9.44", 2514.0 -> "2,514"."""
    return f"{x:,.2f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class Measure:
    measure_id: str
    label: str
    tax: str
    policy_area: str                       # "tax" | "spending"
    unit: str                              # pp | gbp | gbp_per_week | pct_of_rate
    current_value: float | None
    current_unit: str
    up: tuple[tuple[float, tuple[float, ...]], ...]          # (size, £m per ready-reckoner year), sign applied
    down: tuple[tuple[float, tuple[float, ...]], ...] | None  # None: mirror the increase
    max_change: float
    years: tuple[str, ...]
    source_ids: tuple[str, ...]
    rows_up: tuple[str, ...]
    rows_down: tuple[str, ...]

    @property
    def largest_costed(self) -> float:
        return max(size for size, _ in self.up)


def _points(spec: str, sign: int, values: dict[tuple[str, str], dict[str, float]], years: tuple[str, ...]
            ) -> tuple[tuple[tuple[float, tuple[float, ...]], ...], tuple[str, ...]]:
    out, rows = [], []
    for point in filter(None, str(spec).split(";")):
        size, refs = point.split("=", 1)
        total = np.zeros(len(years))
        for ref in refs.split("+"):
            section, label = ref.split("::", 1)
            total += np.array([values[(section, label)][fy] for fy in years])
            rows.append(f"{section}: {label}")
        out.append((float(size), tuple(float(v) * sign for v in total)))
    return tuple(sorted(out)), tuple(rows)


@lru_cache(maxsize=1)
def _measures() -> dict[str, Measure]:
    from ..data import registry

    values: dict[tuple[str, str], dict[str, float]] = {}
    for r in registry.load_ready_reckoner():
        values.setdefault((r["section"], r["label"]), {})[r["fiscal_year"]] = float(r["value_gbp_m"])
    years = tuple(sorted({fy for v in values.values() for fy in v}))
    out: dict[str, Measure] = {}
    for r in registry.load_tax_measures():
        up, rows_up = _points(r["points_up"], int(r["sign_up"]), values, years)
        down, rows_down = (_points(r["points_down"], int(r["sign_down"]), values, years)
                           if str(r["points_down"]).strip() else (None, ()))
        current = str(r["current_value"]).strip()
        out[r["measure_id"]] = Measure(
            measure_id=r["measure_id"], label=r["label"], tax=r["tax"], policy_area=r["policy_area"], unit=r["unit"],
            current_value=float(current) if current else None, current_unit=str(r["current_unit"]),
            up=up, down=down, max_change=float(r["max_change"]), years=years,
            source_ids=tuple(s.strip() for s in str(r["source_ids"]).split(";") if s.strip()),
            rows_up=rows_up, rows_down=rows_down)
    return out


def measures() -> dict[str, Measure]:
    return dict(_measures())


def get_measure(measure_id: str | None) -> Measure | None:
    return _measures().get(measure_id or "")


def change_units(spec: PolicySpec, m: Measure) -> float | None:
    """The change the policy makes, in the measure's ready-reckoner unit (signed)."""
    if m.unit == "pp":
        if spec.baseline_rate_pct is None or spec.proposed_rate_pct is None:
            return None
        return round(spec.proposed_rate_pct - spec.baseline_rate_pct, 9)
    if spec.baseline_value is None or spec.proposed_value is None:
        return None
    if m.unit == "pct_of_rate":
        if spec.baseline_value <= 0:
            return None
        return round((spec.proposed_value / spec.baseline_value - 1.0) * 100.0, 9)
    return round(spec.proposed_value - spec.baseline_value, 9)


def _interpolate(points: tuple[tuple[float, tuple[float, ...]], ...], size: float) -> np.ndarray:
    """£m per year for a change of `size` (>= 0): piecewise linear through (0, 0) and the costed points; the last
    segment is extended beyond the largest point."""
    xs = [0.0] + [p[0] for p in points]
    ys = [np.zeros(len(points[0][1]))] + [np.array(p[1]) for p in points]
    for i in range(1, len(xs)):
        if size <= xs[i] or i == len(xs) - 1:
            x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
            return y0 + (y1 - y0) * (size - x0) / (x1 - x0)
    raise AssertionError("unreachable")  # pragma: no cover


def official_effect_gbp_bn(m: Measure, change: float) -> np.ndarray:
    """Exchequer revenue (£bn, + = more revenue) per ready-reckoner year for a signed change in the measure's unit."""
    if change >= 0:
        return _interpolate(m.up, change) / 1000.0
    if m.down is not None:
        return _interpolate(m.down, -change) / 1000.0
    return -_interpolate(m.up, -change) / 1000.0


def expected_revenue_sign(spec: PolicySpec) -> int:
    """+1 / -1 when the official costing has the same sign in every year, else 0 (e.g. CGT, whose yield changes sign)."""
    m = get_measure(spec.measure_id)
    change = change_units(spec, m) if m else None
    if m is None or not change:
        return 0
    signs = {int(np.sign(v)) for v in official_effect_gbp_bn(m, change) if abs(v) > 1e-12}
    return signs.pop() if len(signs) == 1 else 0


def _validate(spec: PolicySpec) -> tuple[Measure, float]:
    m = get_measure(spec.measure_id)
    if m is None:
        raise ValueError(f"No ready-reckoner measure {spec.measure_id!r}")
    change = change_units(spec, m)
    if change is None:
        raise ValueError(f"The policy does not give the current and proposed value for {m.label}")
    if spec.effective_date is None:
        raise ValueError("compute needs effective_date")
    return m, change


def default_parameters(spec: PolicySpec | None = None) -> dict[str, Assumption]:
    """The single assumption of the ready-reckoner model. Its range widens when the change goes beyond HMRC's largest
    costed illustrative change."""
    low, high = 0.8, 1.1
    rationale = ("Team judgement. HMRC's ready-reckoner figures are direct effects of small illustrative changes "
                 "(including some behavioural response, but no wider macroeconomic effects); HMRC notes larger "
                 "changes need not scale linearly. Central 1.0 takes the official costing at face value; the range "
                 "allows a 20% smaller or 10% larger effect.")
    if spec is not None and (m := get_measure(spec.measure_id)) is not None:
        change = change_units(spec, m)
        if change is not None and abs(change) > m.largest_costed + 1e-9:
            low, high = 0.7, 1.1
            rationale += (f" Widened to 0.7-1.1 because the change ({fmt_change(abs(change), m.unit)}) is larger "
                          f"than HMRC's largest costed change ({fmt_change(m.largest_costed, m.unit)}).")
    return {PARAMETER: Assumption(
        name=PARAMETER, label="Ready-reckoner costing scale",
        description="Multiplier on HMRC's official direct-effect costing, scaled to the size of the change.",
        category="behavioural", unit="multiplier", value=1.0, low=low, high=high,
        distribution=Distribution(kind="triangular", params={"low": low, "mode": 1.0, "high": high}),
        basis="team_judgement", source_ids=[RR_SOURCE_ID], rationale=rationale, adjustable=True,
        slider_min=0.5, slider_max=1.5, slider_step=0.05)}


def compute(spec: PolicySpec, params: Mapping[str, float | np.ndarray], baseline: BaselineProjection):  # noqa: ANN201
    from .core import CoreOutputs, _col, _n_draws

    m, change = _validate(spec)
    if PARAMETER not in params:
        raise ValueError(f"Missing parameters: {PARAMETER}")
    scale = _col(params, PARAMETER)
    n = _n_draws(params)
    H = spec.horizon_years
    years = fiscal_year_range(fiscal_year_of(spec.effective_date), H)  # type: ignore[arg-type]
    gdp = {y.fiscal_year: y.nominal_gdp_gbp_bn for y in baseline.years}
    missing = [fy for fy in (*years, *m.years) if fy not in gdp]
    if missing:
        raise ValueError(f"The baseline has no nominal GDP for {', '.join(sorted(set(missing)))}")
    effect = official_effect_gbp_bn(m, change)
    cols = [min(k, len(m.years) - 1) for k in range(H)]
    base = np.array([effect[c] for c in cols]).reshape(1, H)
    uprate = np.array([gdp[fy] / gdp[m.years[c]] for fy, c in zip(years, cols, strict=True)]).reshape(1, H)
    static = base * uprate
    behavioural = static * scale
    warnings: list[str] = []
    if abs(change) > m.largest_costed + 1e-9:
        warnings.append(f"The change ({fmt_change(abs(change), m.unit)}) is larger than HMRC's largest costed "
                        f"illustrative change ({fmt_change(m.largest_costed, m.unit)}); the costing is extrapolated linearly.")
    if change < 0 and m.down is None:
        warnings.append("HMRC costs this measure for an increase; the decrease mirrors that costing.")
    if H > len(m.years):
        warnings.append(f"Years after the ready reckoner's third year use its third-year effect grown with OBR "
                        f"nominal GDP ({baseline.vintage}).")
    if baseline.is_placeholder:
        warnings.append("Baseline projection is a placeholder; figures are for wiring only.")
    shape = (n, H)

    def full(a: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(np.broadcast_to(a, shape), dtype=float)

    return CoreOutputs(
        fiscal_years=years,
        metrics={"revenue_static_gbp_bn": full(static), "revenue_behavioural_gbp_bn": full(behavioural),
                 "revenue_dynamic_gbp_bn": full(behavioural)},
        intermediates={"rr_effect": base, "rr_uprate": uprate, "rr_change": np.full((1, 1), change)},
        warnings=warnings)


_LABELS = {
    "revenue_static_gbp_bn": ("Official direct effect (HMRC ready reckoner, scaled)", "medium",
                              "HMRC's direct-effect costing for this change, scaled from its illustrative change and "
                              "uprated with nominal GDP. Includes some behavioural response; no macroeconomic effects."),
    "revenue_behavioural_gbp_bn": ("Revenue change with costing uncertainty", "medium",
                                   "The official direct effect × the ready-reckoner costing scale (central 1.0)."),
    "revenue_dynamic_gbp_bn": ("Revenue change (no macroeconomic feedback)", "low",
                               "Equals the revenue change above: no investment, labour-supply or GDP channel is "
                               "modelled for this measure."),
}


def run_engine(spec: PolicySpec, params: Mapping[str, Assumption | float], baseline: BaselineProjection,
               scenario: str = "central") -> EngineResult:
    values = {k: (v.value if isinstance(v, Assumption) else float(v)) for k, v in params.items()}
    out = compute(spec, values, baseline)
    m, change = _validate(spec)
    scale = values[PARAMETER]
    rr_sources = [s for s in m.source_ids]
    base_sources = list(baseline.source_ids)
    metrics = [MetricProjection(metric=name, label=label, unit="£bn", confidence=conf,  # type: ignore[arg-type]
                                values=[YearValue(fiscal_year=fy, value=float(out.metrics[name][0, i]))
                                        for i, fy in enumerate(out.fiscal_years)], note=note)
               for name, (label, conf, note) in _LABELS.items()]
    old, new = ((spec.baseline_rate_pct, spec.proposed_rate_pct) if m.unit == "pp"
                else (spec.baseline_value, spec.proposed_value))
    rows = m.rows_up if change >= 0 or m.down is None else m.rows_down
    trace = [CalcStep(step_id="rr.change", label=f"Change in {m.label} ({UNIT_LABEL[m.unit]})",
                      formula=("proposed − current" if m.unit != "pct_of_rate" else "(proposed / current − 1) × 100"),
                      inputs={"current": float(old), "proposed": float(new)}, output=float(change),  # type: ignore[arg-type]
                      unit=UNIT_LABEL[m.unit], source_ids=rr_sources)]
    for i, fy in enumerate(out.fiscal_years):
        col = min(i, len(m.years) - 1)
        effect, uprate = float(out.intermediates["rr_effect"][0, i]), float(out.intermediates["rr_uprate"][0, i])
        static = float(out.metrics["revenue_static_gbp_bn"][0, i])
        behav = float(out.metrics["revenue_behavioural_gbp_bn"][0, i])
        trace += [
            CalcStep(step_id=f"rr.effect.{fy}",
                     label=f"HMRC ready-reckoner effect, year {col + 1} profile ({m.years[col]})",
                     formula=f"interpolate(costed points, change) from: {'; '.join(rows)}",
                     inputs={"change": float(change)}, output=effect, unit="£bn", fiscal_year=fy,
                     source_ids=[RR_SOURCE_ID]),
            CalcStep(step_id=f"rr.uprate.{fy}", label="Uprating by OBR nominal GDP",
                     formula=f"GDP({fy}) / GDP({m.years[col]})", inputs={}, output=uprate, unit="ratio",
                     fiscal_year=fy, source_ids=base_sources),
            CalcStep(step_id=f"rev.static.{fy}", label="Official direct effect, scaled", formula="effect × uprating",
                     inputs={"effect": effect, "uprating": uprate}, output=static, unit="£bn", fiscal_year=fy,
                     source_ids=[RR_SOURCE_ID, *base_sources]),
            CalcStep(step_id=f"rev.behavioural.{fy}", label="Revenue change with costing scale",
                     formula="static × rr_costing_scale", inputs={"static": static, PARAMETER: scale}, output=behav,
                     unit="£bn", fiscal_year=fy, parameter_names=[PARAMETER], source_ids=[RR_SOURCE_ID]),
            CalcStep(step_id=f"rev.dynamic.{fy}", label="Revenue change (no macroeconomic feedback)",
                     formula="behavioural", inputs={"behavioural": behav}, output=behav, unit="£bn", fiscal_year=fy,
                     parameter_names=[PARAMETER], source_ids=[RR_SOURCE_ID]),
        ]
    return EngineResult(model_version=MODEL_VERSION, policy=spec, scenario=scenario, baseline_vintage=baseline.vintage,
                        fiscal_years=list(out.fiscal_years), metrics=metrics, calc_trace=trace,
                        parameters_used={PARAMETER: float(scale)}, warnings=list(out.warnings))
