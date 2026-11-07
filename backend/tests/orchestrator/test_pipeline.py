"""End-to-end pipeline in mock mode, and the store. Owner: agent-1.

These tests check the platform (stages, events, saving, sources, failure handling), not the stub numbers, so
they keep passing as module owners replace their stubs.
"""
import threading

import pytest

from jane_avenue import contracts as c
from jane_avenue.orchestrator import Emitter, create_analysis, pipeline, run_analysis
from jane_avenue.store import AnalysisStore


@pytest.fixture
def store():
    s = AnalysisStore(":memory:")
    yield s
    s.close()


def _run(store, request):
    return run_analysis(store, create_analysis(store, request).analysis_id)


def test_golden_path_completes(store, demo_request):
    a = _run(store, demo_request)
    assert a.status == "completed", a.error
    assert a.mode == "mock"
    assert a.policy and a.policy.policy_type == "corporation_tax_main_rate"
    assert a.scope and a.scope.forecast_allowed
    assert a.research and a.precedents and a.simulation and a.verification and a.report
    assert a.simulation.scenarios[0].scenario.name == "central"
    assert a.simulation.monte_carlo and a.simulation.monte_carlo.n_draws == 500
    assert set(a.stage_timings_ms) == set(c.STAGES)
    assert store.get(a.analysis_id) == a


def test_events_are_ordered_and_complete(store, demo_request):
    a = _run(store, demo_request)
    events = store.events_after(a.analysis_id, 0)
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert [e.stage for e in events if e.type == "stage_started"] == list(c.STAGES)
    assert [e.stage for e in events if e.type == "stage_completed"] == list(c.STAGES)
    steps = [e for e in events if e.type == "research_step"]
    assert steps and all(c.ResearchStep.model_validate(e.data) for e in steps)
    assert events[-1].type == "completed"
    assert store.events_after(a.analysis_id, events[-2].seq) == [events[-1]]


def test_sources_are_union_without_duplicates(store, demo_request):
    a = _run(store, demo_request)
    ids = [s.source_id for s in a.sources]
    assert len(ids) == len(set(ids))
    expected = {s.source_id for s in a.research.sources} | {s.source_id for s in a.precedents.sources}
    assert expected <= set(ids)


def test_out_of_scope_withholds_forecast(store):
    a = _run(store, c.AnalysisRequest(query="Raise corporation tax from 25% to 45%",
                                      options=c.AnalysisOptions(monte_carlo_draws=100)))
    assert a.status == "completed"
    assert a.scope.status == "unsupported"
    assert a.simulation is None
    assert a.verification.overall == "forecast_withheld" and not a.verification.forecast_allowed
    assert a.report.forecast_withheld
    assert any(e.type == "warning" for e in store.events_after(a.analysis_id))


def test_policy_override_and_skip_research(store, demo_policy):
    req = c.AnalysisRequest(query="manual", policy_override=demo_policy,
                            options=c.AnalysisOptions(run_research=False, monte_carlo_draws=0))
    a = _run(store, req)
    assert a.status == "completed"
    assert a.policy == demo_policy
    assert a.research is None
    assert a.simulation.monte_carlo is None


def test_reuse_research_and_overrides(store, demo_request):
    first = _run(store, demo_request)
    req = demo_request.model_copy(update={"reuse_research_from": first.analysis_id,
                                          "parameter_overrides": {"taxable_profit_elasticity": 0.4}})
    second = _run(store, req)
    assert second.status == "completed"
    assert second.research == first.research
    assert not any(e.type == "research_step" for e in store.events_after(second.analysis_id))
    tpe = next(p for p in second.simulation.assumptions if p.name == "taxable_profit_elasticity")
    assert tpe.value == 0.4 and tpe.is_user_override


def test_unexpected_error_marks_failed(store, demo_request, monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("precedents exploded")

    monkeypatch.setattr(pipeline.precedents, "find_precedents", boom)
    a = _run(store, demo_request)
    assert a.status == "failed"
    assert "precedents exploded" in a.error
    assert store.get(a.analysis_id).status == "failed"
    events = store.events_after(a.analysis_id)
    assert events[-1].type == "failed"
    assert "Traceback" not in events[-1].message


def test_research_failure_does_not_fail_analysis(store, demo_request, monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(pipeline.research, "run_research", boom)
    a = _run(store, demo_request)
    assert a.status == "completed", a.error
    assert a.research is None and a.simulation is not None
    errors = [e for e in store.events_after(a.analysis_id) if e.type == "error"]
    assert errors and "quota exceeded" in errors[0].message and errors[0].stage == "researching"


def test_unknown_override_fails_cleanly(store, demo_request):
    a = _run(store, demo_request.model_copy(update={"parameter_overrides": {"nope": 1.0}}))
    assert a.status == "failed" and "nope" in a.error
    assert "Invalid simulation parameters" in a.error


def test_invalid_simulation_parameters_fail_with_reason(store, demo_request, monkeypatch):
    def invalid(*_, **__):
        raise ValueError("investment shares must sum to 1")

    monkeypatch.setattr(pipeline.simulation, "simulate", invalid)
    a = _run(store, demo_request)
    assert a.status == "failed"
    assert a.error == "ValueError: Invalid simulation parameters: investment shares must sum to 1"
    assert a.simulation is None and a.verification is None  # never "approved" without numbers
    errors = [e for e in store.events_after(a.analysis_id) if e.type == "error"]
    assert errors and errors[0].stage == "modelling"


def test_store_list_newest_first(store, demo_request):
    ids = [create_analysis(store, demo_request).analysis_id for _ in range(3)]
    listed = store.list(limit=2)
    assert [s.analysis_id for s in listed] == ids[::-1][:2]
    assert listed[0].query == demo_request.query


def test_emitter_seq_unique_across_threads(store, demo_request):
    a = create_analysis(store, demo_request)
    emit = Emitter(store, a.analysis_id)

    def work():
        for _ in range(50):
            emit("log", "x")

    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    seqs = [e.seq for e in store.events_after(a.analysis_id)]
    assert seqs == list(range(1, 201))


def test_store_file_path_creates_parent(tmp_path, demo_request):
    s = AnalysisStore(tmp_path / "nested" / "jane.db")
    a = create_analysis(s, demo_request)
    assert s.get(a.analysis_id).analysis_id == a.analysis_id
    s.close()
