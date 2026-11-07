"""API surface (MASTER_PROMPT 9.9). Owner: agent-1.

With an explicit store, `create_app` runs analyses inline as a background task, which the TestClient completes
before `post` returns, so the SSE stream is already terminal when it is read.
"""
import json

import pytest
from fastapi.testclient import TestClient

from jane_avenue import contracts as c
from jane_avenue.api.app import create_app
from jane_avenue.store import AnalysisStore

GOLDEN = "What would happen if the UK increased corporation tax from 25% to 28%?"


@pytest.fixture
def client():
    store = AnalysisStore(":memory:")
    with TestClient(create_app(store)) as tc:
        yield tc
    store.close()


def _sse(text: str) -> list[dict]:
    frames = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if fields:
            frames.append(fields)
    return frames


def _create(client, **body) -> str:
    r = client.post("/api/analyses", json={"query": GOLDEN, "options": {"monte_carlo_draws": 200}, **body})
    assert r.status_code == 202, r.text
    created = c.AnalysisCreated.model_validate(r.json())
    assert created.status == "queued"
    return created.analysis_id


def test_health(client):
    h = c.HealthResponse.model_validate(client.get("/api/health").json())
    assert h.status == "ok" and h.mode == "mock" and h.contract_version == c.CONTRACT_VERSION
    assert h.gemini_configured is False


def test_parse_and_scope(client):
    r = client.post("/api/policy/parse", json={"query": GOLDEN})
    assert r.status_code == 200
    parsed = c.ParseResponse.model_validate(r.json())
    assert parsed.policy.baseline_rate_pct == 25 and parsed.policy.proposed_rate_pct == 28
    assert parsed.scope.forecast_allowed
    edited = parsed.policy.model_copy(update={"proposed_rate_pct": 45.0})
    r = client.post("/api/policy/scope", json=edited.model_dump(mode="json"))
    assert c.ParseResponse.model_validate(r.json()).scope.status == "unsupported"
    vat = c.ParseResponse.model_validate(client.post("/api/policy/parse", json={"query": "Raise VAT to 22%"}).json())
    assert vat.policy.policy_type == "vat_standard_rate" and vat.policy.baseline_rate_pct is None
    assert not vat.scope.forecast_allowed


def test_parse_rejects_short_query(client):
    r = client.post("/api/policy/parse", json={"query": "x"})
    assert r.status_code == 422
    body = r.json()
    assert body["message"] == "Invalid request" and "body.query" in body["reasons"][0]


def test_every_error_has_message_body(client):
    assert client.get("/api/nope").json() == {"message": "Not Found", "reasons": []}
    assert client.post("/api/analyses", json={"query": GOLDEN, "options": {"monte_carlo_draws": 99999}}).json()["reasons"]


def test_openapi_422_is_error_body(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in paths.values():
        for op in path.values():
            if "422" in op["responses"]:
                ref = op["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
                assert ref.endswith("/ErrorBody"), op["operationId"]


def test_analysis_lifecycle_and_sse(client):
    aid = _create(client)
    a = c.Analysis.model_validate(client.get(f"/api/analyses/{aid}").json())
    assert a.status == "completed", a.error

    r = client.get(f"/api/analyses/{aid}/events")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache" and r.headers["x-accel-buffering"] == "no"
    frames = _sse(r.text)
    events = [c.AnalysisEvent.model_validate(json.loads(f["data"])) for f in frames]
    assert [int(f["id"]) for f in frames] == [e.seq for e in events] == list(range(1, len(events) + 1))
    assert all(f["event"] == e.type for f, e in zip(frames, events, strict=True))
    assert events[-1].type == "completed"
    assert any(e.type == "research_step" for e in events)

    # resume: query parameter and Last-Event-ID header
    tail = _sse(client.get(f"/api/analyses/{aid}/events", params={"after_seq": len(events) - 2}).text)
    assert [int(f["id"]) for f in tail] == [len(events) - 1, len(events)]
    tail = _sse(client.get(f"/api/analyses/{aid}/events", headers={"Last-Event-ID": str(len(events) - 1)}).text)
    assert [int(f["id"]) for f in tail] == [len(events)]

    listed = [c.AnalysisSummary.model_validate(x) for x in client.get("/api/analyses").json()]
    assert listed[0].analysis_id == aid and listed[0].verification_overall == a.verification.overall

    report = c.PolicyAssessment.model_validate(client.get(f"/api/analyses/{aid}/report").json())
    md = client.get(f"/api/analyses/{aid}/report.md")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert "attachment" in md.headers["content-disposition"]
    assert md.text == report.markdown


def test_executor_mode_streams_live_events():
    """Production path: the pipeline runs on the thread pool while the SSE stream polls for new events."""
    store = AnalysisStore(":memory:")
    with TestClient(create_app(store, use_executor=True)) as tc:
        r = tc.post("/api/analyses", json={"query": GOLDEN, "options": {"monte_carlo_draws": 200}})
        aid = r.json()["analysis_id"]
        with tc.stream("GET", f"/api/analyses/{aid}/events") as resp:
            text = "".join(resp.iter_text())
        frames = _sse(text)
        assert frames[-1]["event"] == "completed"
        assert [int(f["id"]) for f in frames] == list(range(1, len(frames) + 1))
        assert c.Analysis.model_validate(tc.get(f"/api/analyses/{aid}").json()).status == "completed"
    store.close()


def test_rerun_with_reused_research(client):
    first = _create(client)
    second = _create(client, reuse_research_from=first, parameter_overrides={"taxable_profit_elasticity": 0.3})
    a1 = c.Analysis.model_validate(client.get(f"/api/analyses/{first}").json())
    a2 = c.Analysis.model_validate(client.get(f"/api/analyses/{second}").json())
    assert a2.status == "completed" and a2.research == a1.research
    assert client.post("/api/analyses", json={"query": GOLDEN, "reuse_research_from": "missing"}).status_code == 404


def test_unknown_analysis_404(client):
    for path in ("/api/analyses/nope", "/api/analyses/nope/events", "/api/analyses/nope/report",
                 "/api/analyses/nope/report.md"):
        r = client.get(path)
        assert r.status_code == 404, path
        assert "message" in r.json()


def test_report_not_ready_409(client):
    aid = _create(client, options={"generate_report": False, "monte_carlo_draws": 0})
    r = client.get(f"/api/analyses/{aid}/report")
    assert r.status_code == 409 and r.json()["message"]


def test_simulate(client, demo_policy):
    body = {"policy": demo_policy.model_dump(mode="json"), "monte_carlo_draws": 300}
    r = client.post("/api/simulate", json=body)
    assert r.status_code == 200, r.text
    bundle = c.SimulationBundle.model_validate(r.json())
    assert bundle.scenarios[0].scenario.name == "central"
    assert bundle.monte_carlo.n_draws == 300


def test_simulate_unknown_override_422(client, demo_policy):
    body = {"policy": demo_policy.model_dump(mode="json"), "parameter_overrides": {"nope": 1.0}}
    r = client.post("/api/simulate", json=body)
    assert r.status_code == 422
    assert "nope" in " ".join(r.json()["reasons"])


def test_simulate_out_of_scope_422(client, demo_policy):
    spec = demo_policy.model_copy(update={"proposed_rate_pct": 45.0})
    r = client.post("/api/simulate", json={"policy": spec.model_dump(mode="json")})
    assert r.status_code == 422 and r.json()["reasons"]


def test_reference_endpoints(client, demo_policy):
    params = [c.Assumption.model_validate(x) for x in client.get("/api/parameters").json()]
    assert {p.name for p in params} >= {"taxable_profit_elasticity", "user_cost_elasticity"}
    changes = [c.PolicyChange.model_validate(x) for x in client.get("/api/precedents").json()]
    assert changes and changes == sorted(changes, key=lambda x: x.effective_date)
    match = c.PrecedentAnalysis.model_validate(
        client.post("/api/precedents/match", params={"k": 3}, json=demo_policy.model_dump(mode="json")).json())
    assert len(match.matches) <= 3
    sources = [c.Source.model_validate(x) for x in client.get("/api/sources").json()]
    assert sources
    one = client.get(f"/api/sources/{sources[0].source_id}")
    assert c.Source.model_validate(one.json()) == sources[0]
    assert client.get("/api/sources/D-nope").status_code == 404
    assert [c.DatasetMeta.model_validate(x) for x in client.get("/api/datasets").json()]
    c.EvaluationReport.model_validate(client.get("/api/evaluation").json())


def test_operation_ids_are_function_names(client):
    ops = {op["operationId"] for path in client.get("/openapi.json").json()["paths"].values() for op in path.values()}
    assert {"health", "parse_policy", "create_analysis", "get_analysis", "stream_events", "simulate"} <= ops
