"""Scenario and tornado tests. Owner: agent-4."""
import pytest

from jane_avenue.engine import core as engine_core
from jane_avenue.engine.parameters import central_values
from jane_avenue.simulation import build_scenarios, sensitivity
from jane_avenue.simulation.endpoints import uncertain_parameters
from jane_avenue.simulation.tornado import TORNADO_METRICS


def _cum_dynamic(result) -> float:
    m = next(m for m in result.metrics if m.metric == "revenue_dynamic_gbp_bn")
    return sum(v.value for v in m.values)


@pytest.mark.parametrize("policy_fixture", ["demo_policy", "cut_policy"])
def test_scenario_order_and_ranking(full_engine, request, policy_fixture, params, baseline):
    spec = request.getfixturevalue(policy_fixture)
    scenarios = build_scenarios(spec, params, baseline)
    assert [s.scenario.name for s in scenarios] == ["central", "optimistic", "pessimistic"]
    central, optimistic, pessimistic = (_cum_dynamic(s.result) for s in scenarios)
    assert pessimistic < central < optimistic


@pytest.mark.parametrize("policy_fixture", ["demo_policy", "cut_policy"])
def test_scenario_ranking_holds_with_the_registry_engine(request, policy_fixture, params, baseline):
    spec = request.getfixturevalue(policy_fixture)
    central, optimistic, pessimistic = (_cum_dynamic(s.result) for s in build_scenarios(spec, params, baseline))
    assert pessimistic <= central <= optimistic


def test_scenario_parameter_rules(full_engine, demo_policy, params, baseline):
    central, optimistic, pessimistic = (s.scenario for s in build_scenarios(demo_policy, params, baseline))
    assert central.parameter_values == central_values(params)
    assert optimistic.parameter_values["profit_base_deviation_pct"] == params["profit_base_deviation_pct"].high
    assert pessimistic.parameter_values["profit_base_deviation_pct"] == params["profit_base_deviation_pct"].low
    # a rise: lower avoidance is favourable, so the optimistic scenario takes the low elasticity
    assert optimistic.parameter_values["taxable_profit_elasticity"] == params["taxable_profit_elasticity"].low
    assert pessimistic.parameter_values["taxable_profit_elasticity"] == params["taxable_profit_elasticity"].high
    for name, p in params.items():
        if p.distribution.kind == "fixed":
            assert optimistic.parameter_values[name] == pessimistic.parameter_values[name] == p.value
        else:
            assert {optimistic.parameter_values[name], pessimistic.parameter_values[name]} <= {p.low, p.value, p.high}
    for s in (optimistic, pessimistic):
        assert "one at a time" in s.description and "cumulative dynamic revenue" in s.description
        assert "profit base deviation" in s.description and "not a forecast" in s.description
    assert "not a forecast" in central.description


def test_cut_flips_the_elasticity_choice(full_engine, cut_policy, params, baseline):
    _, optimistic, pessimistic = (s.scenario for s in build_scenarios(cut_policy, params, baseline))
    # a cut: a larger base response recovers more revenue, so the optimistic scenario takes the high elasticity
    assert optimistic.parameter_values["taxable_profit_elasticity"] == params["taxable_profit_elasticity"].high
    assert pessimistic.parameter_values["taxable_profit_elasticity"] == params["taxable_profit_elasticity"].low


def test_tornado_shape_sorting_and_values(full_engine, demo_policy, params, baseline):
    results = sensitivity(demo_policy, params, baseline)
    uncertain = uncertain_parameters(params)
    assert [r.metric for r in results] == list(TORNADO_METRICS)
    central_out = full_engine(demo_policy, central_values(params), baseline)
    for r in results:
        assert r.fiscal_year == central_out.fiscal_years[-1]
        assert r.base_output == pytest.approx(float(central_out.metrics[r.metric][0, -1]))
        assert sorted(it.parameter for it in r.items) == sorted(uncertain)
        swings = [it.swing for it in r.items]
        assert swings == sorted(swings, reverse=True)
        for it in r.items:
            assert it.swing == pytest.approx(abs(it.output_at_high - it.output_at_low))
            assert (it.low_input, it.high_input) == (params[it.parameter].low, params[it.parameter].high)
    # spot-check one endpoint against a direct compute call
    moved = dict(central_values(params), user_cost_elasticity=params["user_cost_elasticity"].high)
    direct = float(full_engine(demo_policy, moved, baseline).metrics["business_investment_pct"][0, -1])
    inv = next(r for r in results if r.metric == "business_investment_pct")
    item = next(it for it in inv.items if it.parameter == "user_cost_elasticity")
    assert item.output_at_high == pytest.approx(direct)
    assert inv.items[0].parameter == "user_cost_elasticity"
    behav = next(r for r in results if r.metric == "revenue_behavioural_gbp_bn")
    swing = {it.parameter: it.swing for it in behav.items}
    assert swing["taxable_profit_elasticity"] > 0 and swing["user_cost_elasticity"] == 0


def test_endpoints_use_one_compute_call(monkeypatch, demo_policy, params, baseline):
    calls = []
    real = engine_core.compute
    monkeypatch.setattr(engine_core, "compute", lambda *a: calls.append(1) or real(*a))
    sensitivity(demo_policy, params, baseline)
    assert len(calls) == 1


def test_scenario_calc_traces_keep_parameter_sources(demo_policy, params, baseline):
    """Scenarios pass Assumptions (not floats) to run_engine, so parameter source_ids reach every calc trace."""
    from jane_avenue.engine.parameters import apply_overrides
    from jane_avenue.simulation import simulate

    sourced = {n: p.model_copy(update={"source_ids": [f"D-test-{n}"]}) for n, p in params.items()}
    sourced = apply_overrides(sourced, {"taxable_profit_elasticity": 0.3})
    bundle = simulate(demo_policy, sourced, baseline, draws=0)
    for s in bundle.scenarios:
        ids = {sid for step in s.result.calc_trace for sid in step.source_ids}
        assert "D-test-main_rate_profit_share" in ids, s.scenario.name
        assert s.result.parameters_used == s.scenario.parameter_values
