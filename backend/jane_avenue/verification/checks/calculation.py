"""Calculation checks CALC-001..003 (MASTER_PROMPT 9.7). Owner: agent-5.

CALC-001 re-runs the engine independently of the stored results; CALC-002 checks the accounting identities and
signs; CALC-003 checks the static costing against an upper bound that needs no model at all.
"""
from __future__ import annotations

import math

from ... import engine
from ...contracts import Analysis, EngineResult, ScenarioResult
from ...data import registry
from ._base import Outcome, check, listing, plural

RECOMPUTE_TOL = 1e-9
IDENTITY_REL_TOL = 1e-6
MC_MEDIAN_TOL = 0.15
STATIC_BOUND_SLACK = 1.05


def _central(analysis: Analysis) -> ScenarioResult | None:
    if analysis.simulation is None:
        return None
    return next((s for s in analysis.simulation.scenarios if s.scenario.name == "central"), None)


def _values(result: EngineResult, metric: str) -> dict[str, float]:
    for m in result.metrics:
        if m.metric == metric:
            return {yv.fiscal_year: yv.value for yv in m.values}
    return {}


def _no_forecast(analysis: Analysis) -> Outcome | None:
    if analysis.simulation is not None and analysis.simulation.scenarios:
        return None
    if analysis.scope is not None and not analysis.scope.forecast_allowed:
        return Outcome("skipped", "No forecast was made for an out-of-scope policy.")
    return Outcome("skipped", "No simulation results to check.")


def _close(a: float, b: float, rel: float) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=RECOMPUTE_TOL)


@check("CALC-001", "calculation", "blocking", "recompute", "Engine recompute matches the central scenario")
def calc_001(analysis: Analysis) -> Outcome:
    if (skip := _no_forecast(analysis)) is not None:
        return skip
    central = _central(analysis)
    if central is None:
        return Outcome("issue", "The simulation has no central scenario to recompute.")
    if analysis.policy is None:
        return Outcome("issue", "Model results exist without a parsed policy, so they cannot be reproduced.")
    fresh = engine.run_engine(analysis.policy, central.scenario.parameter_values, registry.load_baseline(), "central")
    stored = {m.metric: {yv.fiscal_year: yv.value for yv in m.values} for m in central.result.metrics}
    recomputed = {m.metric: {yv.fiscal_year: yv.value for yv in m.values} for m in fresh.metrics}
    bad: list[str] = []
    examples: list[str] = []
    for metric in sorted(set(stored) | set(recomputed)):
        old, new = stored.get(metric, {}), recomputed.get(metric, {})
        for fy in sorted(set(old) | set(new)):
            key = f"{metric}.{fy}"
            if fy not in old or fy not in new:
                bad.append(key)
                examples.append(f"{key} is {'missing from the stored results' if fy not in old else 'not reproduced'}")
            elif abs(old[fy] - new[fy]) > RECOMPUTE_TOL:
                bad.append(key)
                examples.append(f"{key} stored {old[fy]:.6g}, recomputed {new[fy]:.6g}")
    if bad:
        return Outcome("issue", f"{plural(len(bad), 'value')} did not reproduce on an independent engine run: "
                                + "; ".join(examples[:5]) + ("; ..." if len(examples) > 5 else "") + ".", bad)
    n = sum(len(v) for v in stored.values())
    return Outcome("pass", f"All {plural(n, 'central-scenario value')} reproduce to within {RECOMPUTE_TOL:g} "
                           f"(baseline {fresh.baseline_vintage}).")


def _identity_problems(scenario: ScenarioResult, direction: int) -> list[tuple[str, str]]:
    """Hard problems as (affected_id, sentence)."""
    result = scenario.result
    name = scenario.scenario.name
    problems: list[tuple[str, str]] = []
    static = _values(result, "revenue_static_gbp_bn")
    behavioural = _values(result, "revenue_behavioural_gbp_bn")
    dynamic = _values(result, "revenue_dynamic_gbp_bn")
    steps = {s.step_id: s for s in result.calc_trace}

    for fy, value in static.items():
        if direction and (value == 0 or math.copysign(1, value) != direction):
            problems.append((f"{name}.revenue_static_gbp_bn.{fy}",
                             f"{name} static revenue in {fy} ({value:.3g}) has the wrong sign for a "
                             f"{'rise' if direction > 0 else 'cut'}"))
    for metric, values in (("revenue_behavioural_gbp_bn", behavioural), ("revenue_dynamic_gbp_bn", dynamic)):
        for fy, value in values.items():
            if direction and value * direction < -RECOMPUTE_TOL:
                problems.append((f"{name}.{metric}.{fy}", f"{name} {metric} in {fy} ({value:.3g}) has the opposite "
                                                          "sign to the policy change"))

    for metric, prefix in (("revenue_static_gbp_bn", "rev.static"), ("revenue_behavioural_gbp_bn", "rev.behavioural"),
                           ("revenue_dynamic_gbp_bn", "rev.dynamic")):
        for fy, value in _values(result, metric).items():
            step = steps.get(f"{prefix}.{fy}")
            if step is not None and not _close(step.output, value, IDENTITY_REL_TOL):
                problems.append((f"{name}.{metric}.{fy}", f"{name} {metric} in {fy} ({value:.6g}) differs from its "
                                                          f"calculation step {step.step_id} ({step.output:.6g})"))

    for fy, behav in behavioural.items():  # behavioural = static + t1 x (B1 - B0) x timing
        step = steps.get(f"rev.behavioural.{fy}")
        if step is None or fy not in static or not {"B0", "B1", "t1", "timing"} <= set(step.inputs):
            continue
        i = step.inputs
        offset = i["t1"] * (i["B1"] - i["B0"]) * i["timing"]
        if not _close(behav, static[fy] + offset, IDENTITY_REL_TOL):
            problems.append((f"{name}.revenue_behavioural_gbp_bn.{fy}",
                             f"{name} behavioural revenue in {fy} ({behav:.6g}) is not static ({static[fy]:.6g}) "
                             f"plus the behavioural offset ({offset:.6g})"))
    return problems


@check("CALC-002", "calculation", "error", "rule", "Revenue identities, signs and Monte Carlo median")
def calc_002(analysis: Analysis) -> Outcome:
    if (skip := _no_forecast(analysis)) is not None:
        return skip
    policy = analysis.policy
    if policy is not None and policy.policy_type == "tax_measure":
        # The sign of the official costing, not of the rate change: raising an allowance or a CGT rate can lose
        # revenue. 0 (no sign check) when HMRC's own costing changes sign across years (contract-change #93).
        direction = engine.reckoner.expected_revenue_sign(policy)
    else:
        change = policy.change_pp() if policy else None
        direction = 0 if not change else (1 if change > 0 else -1)
    problems = [p for s in analysis.simulation.scenarios for p in _identity_problems(s, direction)]  # type: ignore[union-attr]
    if problems:
        shown = "; ".join(text for _, text in problems[:4]) + ("; ..." if len(problems) > 4 else "")
        return Outcome("issue", f"{plural(len(problems), 'identity or sign problem')}: {shown}.",
                       [key for key, _ in problems])

    soft: list[str] = []
    central = _central(analysis)
    mc = analysis.simulation.monte_carlo  # type: ignore[union-attr]
    if central is not None and mc is not None:
        values = _values(central.result, "revenue_behavioural_gbp_bn")
        for dist in mc.distributions:
            if dist.metric != "revenue_behavioural_gbp_bn":
                continue
            for band in dist.bands:
                c = values.get(band.fiscal_year)
                if c is not None and abs(c) > RECOMPUTE_TOL and abs(band.p50 - c) > MC_MEDIAN_TOL * abs(c):
                    soft.append(band.fiscal_year)
    if soft:
        return Outcome("warn", f"The Monte Carlo median of behavioural revenue is more than {MC_MEDIAN_TOL:.0%} away "
                               f"from the central scenario in {listing(soft)}: the central case is not typical of "
                               "the assumption ranges.",
                       [f"monte_carlo.revenue_behavioural_gbp_bn.{fy}" for fy in soft])
    return Outcome("pass", "Revenue signs match the policy direction, metrics match their calculation steps, and the "
                           "Monte Carlo median is close to the central scenario.")


@check("CALC-003", "calculation", "error", "rule", "Static costing within the mechanical upper bound")
def calc_003(analysis: Analysis) -> Outcome:
    if (skip := _no_forecast(analysis)) is not None:
        return skip
    policy = analysis.policy
    if policy is not None and policy.policy_type == "tax_measure":
        return Outcome("skipped", "The corporation-tax receipts bound does not apply: this measure is costed directly "
                                  "from HMRC's ready reckoner, which CALC-001 reproduces.")
    if policy is None or policy.baseline_rate_pct is None or policy.proposed_rate_pct is None:
        return Outcome("skipped", "The policy has no rates to bound against.")
    t0, t1 = policy.baseline_rate_pct / 100, policy.proposed_rate_pct / 100
    if t0 <= 0:
        return Outcome("skipped", "A zero current rate has no proportional bound.")
    baseline = registry.load_baseline()
    receipts = {y.fiscal_year: y.ct_receipts_gbp_bn for y in baseline.years}
    last = baseline.years[-1].ct_receipts_gbp_bn if baseline.years else None
    over: list[tuple[str, str]] = []
    for scenario in analysis.simulation.scenarios:  # type: ignore[union-attr]
        for fy, value in _values(scenario.result, "revenue_static_gbp_bn").items():
            r = receipts.get(fy, last)
            if r is None:
                continue
            bound = abs(t1 - t0) / t0 * r * STATIC_BOUND_SLACK
            if abs(value) > bound + RECOMPUTE_TOL:
                over.append((f"{scenario.scenario.name}.revenue_static_gbp_bn.{fy}",
                             f"{scenario.scenario.name} {fy}: £{abs(value):.2f}bn exceeds £{bound:.2f}bn"))
    if over:
        return Outcome("issue", "Static revenue is larger than a proportional change in all CT receipts could "
                                "produce (|Δt|/t0 × receipts × 1.05): " + "; ".join(t for _, t in over[:4])
                                + ("; ..." if len(over) > 4 else "") + ".", [k for k, _ in over])
    return Outcome("pass", "Static revenue is within |Δt|/t0 × baseline receipts × 1.05 in every scenario and year.")
