"""M2 hardening (agent-1 brief section 6): performance, logging, concurrency, input limits, startup checks.
Owner: agent-1."""
import logging
import statistics
import threading
import time

from fastapi.testclient import TestClient

from jane_avenue import contracts as c
from jane_avenue.api.app import create_app, placeholder_data_in_use
from jane_avenue.api.ratelimit import TokenBucket
from jane_avenue.orchestrator import create_analysis, run_analysis
from jane_avenue.store import AnalysisStore

GOLDEN = "What would happen if the UK increased corporation tax from 25% to 28%?"


def _median_ms(fn, n=15):
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)


# ---- performance -------------------------------------------------------------------------------------------------
def test_get_analysis_under_100ms(demo_policy):
    store = AnalysisStore(":memory:")
    tc = TestClient(create_app(store))
    aid = tc.post("/api/analyses", json={"query": GOLDEN, "options": {"monte_carlo_draws": 2000}}).json()["analysis_id"]
    assert _median_ms(lambda: tc.get(f"/api/analyses/{aid}")) < 100


def test_simulate_2000_draws_with_sensitivity_under_1s(demo_policy):
    tc = TestClient(create_app(AnalysisStore(":memory:")))
    body = {"policy": demo_policy.model_dump(mode="json"), "monte_carlo_draws": 2000, "include_sensitivity": True}
    assert tc.post("/api/simulate", json=body).status_code == 200
    assert _median_ms(lambda: tc.post("/api/simulate", json=body), n=5) < 1000


def test_store_lru_serves_cache_and_evicts(demo_request):
    store = AnalysisStore(":memory:", cache_size=3)
    ids = [create_analysis(store, demo_request).analysis_id for _ in range(5)]
    assert store.get(ids[-1]) is store.get(ids[-1])  # served from the cache
    assert list(store._cache) == ids[-3:]  # oldest evicted
    first = store.get(ids[0])  # evicted, so read back from SQLite
    assert first is not None and first.analysis_id == ids[0]
    assert list(store._cache)[-1] == ids[0]
    assert store.get("missing") is None


def test_cache_sees_every_save(demo_request):
    store = AnalysisStore(":memory:")
    a = create_analysis(store, demo_request)
    run_analysis(store, a.analysis_id)
    cached = store.get(a.analysis_id)
    assert cached.status == "completed"
    store._cache.clear()  # force a read from SQLite: it must equal what the cache served
    assert store.get(a.analysis_id) == cached


# ---- structured logging ------------------------------------------------------------------------------------------
def test_log_records_carry_analysis_and_stage(demo_request, caplog):
    store = AnalysisStore(":memory:")
    a = create_analysis(store, demo_request)
    with caplog.at_level(logging.INFO, logger="jane_avenue"):
        run_analysis(store, a.analysis_id)
    ours = [r for r in caplog.records if r.name.startswith("jane_avenue.orchestrator")]
    assert ours and all(r.analysis_id == a.analysis_id for r in ours)
    stages = {r.stage for r in ours if "stage completed" in r.getMessage()}
    assert stages == set(c.STAGES)
    other = logging.getLogger("jane_avenue.test").makeRecord("x", logging.INFO, "f", 1, "m", None, None)
    assert other.analysis_id == "-" and other.stage == "-"


# ---- concurrency -------------------------------------------------------------------------------------------------
def test_two_simultaneous_analyses_keep_their_own_sequences(demo_request):
    store = AnalysisStore(":memory:")
    ids = [create_analysis(store, demo_request).analysis_id for _ in range(2)]
    results = {}
    threads = [threading.Thread(target=lambda i=i: results.__setitem__(i, run_analysis(store, i))) for i in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for i in ids:
        assert results[i].status == "completed", results[i].error
        events = store.events_after(i)
        assert [e.seq for e in events] == list(range(1, len(events) + 1))
        assert all(e.analysis_id == i for e in events) and events[-1].type == "completed"


def test_two_analyses_through_the_api_executor():
    store = AnalysisStore(":memory:")
    with TestClient(create_app(store, use_executor=True)) as tc:
        ids = [tc.post("/api/analyses", json={"query": GOLDEN, "options": {"monte_carlo_draws": 100}}).json()[
            "analysis_id"] for _ in range(2)]
        for i in ids:
            with tc.stream("GET", f"/api/analyses/{i}/events") as resp:
                text = "".join(resp.iter_text())
            assert "event: completed" in text
    for i in ids:
        assert [e.seq for e in store.events_after(i)] == list(range(1, len(store.events_after(i)) + 1))


# ---- input limits ------------------------------------------------------------------------------------------------
def test_request_limits_rejected_with_error_body():
    tc = TestClient(create_app(AnalysisStore(":memory:")))
    for body in ({"query": "x" * 2001}, {"query": GOLDEN, "options": {"monte_carlo_draws": 20001}}):
        r = tc.post("/api/analyses", json=body)
        assert r.status_code == 422 and r.json()["reasons"]


def test_token_bucket_refills():
    now = [0.0]
    bucket = TokenBucket(per_minute=6, clock=lambda: now[0])
    assert all(bucket.take("a")[0] for _ in range(6))
    allowed, retry = bucket.take("a")
    assert not allowed and retry == 10
    assert bucket.take("b")[0]  # other clients are unaffected
    now[0] += 10
    assert bucket.take("a")[0]


def test_rate_limit_returns_429_with_retry_after():
    tc = TestClient(create_app(AnalysisStore(":memory:"), rate_limiter=TokenBucket(per_minute=2)))
    body = {"query": GOLDEN, "options": {"monte_carlo_draws": 0, "run_research": False}}
    assert [tc.post("/api/analyses", json=body).status_code for _ in range(2)] == [202, 202]
    r = tc.post("/api/analyses", json=body)
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert r.json()["message"] and r.json()["reasons"]


def test_no_rate_limit_in_mock_mode():
    app = create_app(AnalysisStore(":memory:"))
    assert app.state.rate_limiter is None


# ---- startup checks ----------------------------------------------------------------------------------------------
def test_startup_warns_about_placeholder_data(caplog):
    with caplog.at_level(logging.WARNING, logger="jane_avenue"):
        create_app(AnalysisStore(":memory:"))
    expected = placeholder_data_in_use()
    warned = [r for r in caplog.records if "placeholder data in use" in r.getMessage()]
    assert bool(warned) == bool(expected)
    assert all(isinstance(i, str) and i for i in expected)
