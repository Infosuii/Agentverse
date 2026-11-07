"""Autonomous tool loop, research cache and answer_question. Offline: scripted MockLLM turns + fake fetch.
Owner: agent-2."""
from __future__ import annotations

import dataclasses
import json
from datetime import date
from typing import Any

import pytest

from jane_avenue.config import get_settings
from jane_avenue.contracts import PolicySpec, ResearchStep
from jane_avenue.data import registry
from jane_avenue.llm import Citation, GroundedAnswer, MockLLM, ToolTurn
from jane_avenue.llm.client import parse_turn
from jane_avenue.research import agent, answer_question, cache, loop, run_research
from jane_avenue.research.tools import FetchedDoc

SPEC = PolicySpec(policy_type="corporation_tax_main_rate", tax="corporation_tax", baseline_rate_pct=25.0,
                  proposed_rate_pct=28.0, effective_date=date(2027, 4, 1), horizon_years=5,
                  description="Raise the CT main rate from 25% to 28% from 1 April 2027")
REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
GOV, IFS, ONS = "https://www.gov.uk/ct-stats", "https://ifs.org.uk/report.pdf", "https://www.ons.gov.uk/receipts"
FINAL = {REDIRECT + "gov": GOV, REDIRECT + "ifs": IFS, REDIRECT + "ons": ONS}
TEXT = {
    GOV: "Onshore Corporation Tax receipts totalled GBP 82.3 billion in 2023 to 2024. The increase was mainly due "
         "to the rise in the main rate to 25%.",
    IFS: "The elasticity of taxable profits with respect to the tax rate is substantial in the literature.",
    ONS: "Corporation tax receipts are volatile and move with company profits over the economic cycle.",
}
ITEM = {"topic": "revenue", "kind": "quantitative"}
GROUNDED = GroundedAnswer(text="Receipts rose after the 2023 rise.", queries=["ct receipts 2023"], citations=[
    Citation(REDIRECT + "gov", "www.gov.uk", "Receipts rose."), Citation(REDIRECT + "ifs", "ifs.org.uk"),
    Citation(REDIRECT + "obr", "obr.uk"), Citation(REDIRECT + "ons", "ons.gov.uk"),
    Citation(REDIRECT + "news", "bbc.co.uk")])


def _turn(*calls: tuple[str, dict[str, Any]], n: int = 0) -> ToolTurn:
    steps: list[dict[str, Any]] = [{"type": "thought", "signature": f"sig-t{n}"}]
    steps += [{"type": "function_call", "id": f"c{n}{i}", "name": name, "arguments": args}
              for i, (name, args) in enumerate(calls)]
    return parse_turn({"status": "requires_action", "steps": steps})


def _results(history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {h["call_id"]: json.loads(h["result"][0]["text"]) for h in history if h.get("type") == "function_result"}


def _n_results(history: list[dict[str, Any]]) -> int:
    return sum(h.get("type") == "function_result" for h in history)


@pytest.fixture(autouse=True)
def _no_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent, "MOCK_STEP_DELAY_S", 0)
    monkeypatch.setattr(agent, "CACHE_STEP_DELAY_S", 0)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path):  # noqa: ANN201
    settings = dataclasses.replace(get_settings(), mode="live", gemini_api_key="test", research_cache_dir=tmp_path)
    monkeypatch.setattr(agent, "get_settings", lambda: settings)
    llm = MockLLM()
    monkeypatch.setattr(agent, "get_llm", lambda: llm)
    monkeypatch.setattr(agent, "WORKERS", 1)
    fetched: list[str] = []

    def fake_fetch(url: str) -> FetchedDoc:
        fetched.append(url)
        final = FINAL.get(url, url.replace(REDIRECT, "https://") if url.startswith(REDIRECT + "ex") else url)
        if final in TEXT:
            return FetchedDoc(url, final, 200, "text/html", TEXT[final], "f" * 64, f"Title of {final}")
        if "obr" in url:
            return FetchedDoc(url, "https://obr.uk/" + url.rsplit("/", 1)[-1], 403, "text/html", "", None, None,
                              "HTTP 403")
        if final.startswith("https://ex"):
            return FetchedDoc(url, final, 200, "text/html", f"Document {final} about corporation tax.", "e" * 64,
                              final)
        return FetchedDoc(url, final, 404, "text/html", "", None, None, "HTTP 404")

    monkeypatch.setattr(agent, "fetch_url", fake_fetch)
    llm.register_structured("Write between 4 and 7", lambda: {"questions": ["Q1 revenue?", "Q2 elasticity?",
                                                                            "Q3 investment?", "Q4 baseline?"]})
    llm.register_structured("Verified evidence (the only facts", lambda: {
        "summary": "Receipts were GBP 82.3 billion [E1]. Profits are elastic [E3].", "interpretations": [],
        "confounders": [], "parameter_evidence": [{"parameter": "taxable_profit_elasticity", "value": None,
                                                   "low": None, "high": None, "evidence_ids": ["E3"], "note": ""}],
        "open_questions": []})
    llm.register_structured(IFS, lambda: {"items": []})  # top-up extraction for the thinly evidenced IFS document
    llm.register_search("ct receipts 2023", GROUNDED)
    return llm, fetched, tmp_path


def _happy_script(seen: list[list[dict[str, Any]]]):  # noqa: ANN202
    def script(history: list[dict[str, Any]]) -> ToolTurn:
        seen.append(list(history))
        n = _n_results(history)
        if n == 0:
            return _turn(("search", {"query": "ct receipts 2023"}), n=0)
        if n == 1:
            return _turn(("fetch_url", {"source_id": "S1", "focus": "receipts"}),
                         ("fetch_url", {"source_id": "S2", "focus": "elasticity"}),
                         ("fetch_url", {"source_id": "S3", "focus": "costing"}), n=1)
        if n == 4:
            dataset_id = registry.list_datasets()[0].dataset_id
            return _turn(("record_evidence", {"source_id": "S1", "items": [
                {**ITEM, "claim": "Receipts were GBP 82.3 billion.", "value": 82.3,
                 "quote": "Onshore Corporation Tax receipts totalled GBP 82.3 billion in 2023 to 2024."},
                {**ITEM, "claim": "Invented.", "quote": "Receipts collapsed after the rise."}]}),
                ("fetch_url", {"source_id": "S4", "focus": "cycle"}), ("lookup_dataset", {"dataset_id": dataset_id}),
                ("get_precedents", {"k": 3}), ("record_evidence", {"source_id": "S5", "items": []}), n=2)
        if n == 9:
            return _turn(("record_evidence", {"source_id": "S2", "items": [
                {"topic": "elasticity", "kind": "qualitative", "claim": "Profits are elastic.",
                 "quote": "The elasticity of taxable profits with respect to the tax rate is substantial"}]}),
                ("record_evidence", {"source_id": "S4", "items": [
                    {"topic": "macro_context", "kind": "qualitative", "claim": "Receipts are cyclical.",
                     "quote": "Corporation tax receipts are volatile"},
                    {"topic": "macro_context", "kind": "qualitative", "claim": "They move with profits.",
                     "quote": "move with company profits over the economic cycle"}]}),
                ("finish", {"reason": "covered"}), n=3)
        raise AssertionError(f"unexpected turn after {n} results")
    return script


def test_autonomous_loop_end_to_end(env) -> None:
    llm, fetched, tmp_path = env
    seen: list[list[dict[str, Any]]] = []
    llm.register_tool_loop("Research questions:", _happy_script(seen))
    steps: list[ResearchStep] = []
    f = run_research(SPEC, on_step=steps.append, use_cache=False)

    assert f.mode == "live"
    # stateless history: each turn gets earlier steps verbatim (thought signatures) and a result per call id
    assert {"type": "thought", "signature": "sig-t0"} in seen[1]
    search = _results(seen[1])["c00"]
    assert search["ok"] and [x["source_id"] for x in search["sources"]] == ["S1", "S3", "S4", "S2", "S5"]  # by tier
    assert search["sources"][0]["supports"] == "Receipts rose."
    fetches = _results(seen[2])
    assert fetches["c10"]["source_id"] == "S1" and "<untrusted_document>" in fetches["c10"]["excerpt"]
    assert "82.3" in fetches["c10"]["excerpt"]
    assert fetches["c12"] == {"ok": False, "error": "HTTP 403"}
    later = _results(seen[3])
    assert [r["status"] for r in later["c20"]["recorded"]] == ["verified", "failed"]
    assert later["c24"]["ok"] is False and "only documents returned by fetch_url" in later["c24"]["error"]
    assert later["c22"]["ok"] and later["c23"]["ok"]
    # provenance: every source is a grounding citation; fetched ones carry their real URL and are verified
    assert all(s.access_method == "google_search" for s in f.sources)
    by_url = {s.url: s for s in f.sources}
    assert all(by_url[u].url_verified for u in (GOV, IFS, ONS))
    assert by_url["https://obr.uk/obr"].url_verified is False   # refused, but its real URL was learned
    assert REDIRECT + "news" not in fetched                      # tier 3 was never fetched
    # evidence verified in code; parameter evidence cites verified evidence only
    assert [(e.evidence_id, e.verification_status) for e in f.evidence] == [
        ("E1", "verified"), ("E2", "failed"), ("E3", "verified"), ("E4", "verified"), ("E5", "verified")]
    assert [(p.parameter, p.evidence_ids) for p in f.parameter_evidence] == [("taxable_profit_elasticity", ["E3"])]
    # one step per tool call
    kinds = [s.kind for s in f.trace]
    assert kinds[:5] == ["plan", "search", "fetch", "fetch", "fetch"]
    assert kinds.count("dataset_lookup") == 2 and kinds.count("fetch") == 4
    dataset = next(s for s in f.trace if s.tool == "lookup_dataset")
    assert dataset.source_ids == [registry.list_datasets()[0].source_id]  # curated D- IDs survive renumbering
    assert any(s.kind == "reason" and s.title == "Agent finished" for s in f.trace)
    assert not any("fixed search sequence" in s.title for s in f.trace)  # 3 documents: no top-up needed
    assert [s.step_id for s in steps] == [s.step_id for s in f.trace]
    # a successful live run is written to the cache
    assert cache.cache_path(SPEC, tmp_path).is_file()


def test_tool_call_and_document_budgets_are_enforced(env) -> None:
    llm, fetched, _ = env
    llm.register_search("many sources", GroundedAnswer(text="x", citations=[
        Citation(f"{REDIRECT}ex{i}.gov.uk/doc", f"ex{i}.gov.uk") for i in range(15)]))
    nxt = iter(range(1, 100))

    def greedy(history: list[dict[str, Any]]) -> ToolTurn:
        if _n_results(history) == 0:
            return _turn(("search", {"query": "many sources"}), n=0)
        return _turn(*[("fetch_url", {"source_id": f"S{next(nxt)}", "focus": "x"}) for _ in range(5)],
                     n=len(history))

    llm.register_tool_loop("Research questions:", greedy)
    f = run_research(SPEC, use_cache=False)
    assert len([c for c in llm.calls if c[0] == "tool_turn"]) == 4  # 1 + 5 + 5 + 1 calls, then the budget stops it
    assert len(fetched) == 8                                         # the document budget
    assert sum(s.title == "Skipped a fetch" for s in f.trace) == 3
    assert any(s.title == "Tool-call budget reached" for s in f.trace)


def test_hosts_that_refuse_twice_are_not_fetched_again(env) -> None:
    llm, fetched, _ = env
    llm.register_search("obr pages", GroundedAnswer(text="x", citations=[
        Citation(f"{REDIRECT}obr{i}", "obr.uk") for i in range(3)]))

    def script(history: list[dict[str, Any]]) -> ToolTurn:
        if _n_results(history) == 0:
            return _turn(("search", {"query": "obr pages"}), n=0)
        return _turn(*[("fetch_url", {"source_id": f"S{i}", "focus": "x"}) for i in (1, 2, 3)],
                     ("finish", {"reason": "done"}), n=1)

    llm.register_tool_loop("Research questions:", script)
    run_research(SPEC, use_cache=False)
    assert [u for u in fetched if "obr" in u] == [f"{REDIRECT}obr0", f"{REDIRECT}obr1"]


def test_time_budget_stops_the_loop_and_falls_back(env, monkeypatch: pytest.MonkeyPatch) -> None:
    llm, _, _ = env
    monkeypatch.setattr(loop, "LOOP_BUDGET_S", 0.0)
    llm.register_tool_loop("Research questions:", lambda h: pytest.fail("no turn should start"))
    f = run_research(SPEC, use_cache=False)
    titles = [s.title for s in f.trace]
    assert "Research time budget reached" in titles
    assert "Topping up with the fixed search sequence" in titles
    assert f.mode == "mock"  # the top-up found nothing either (no searches scripted), and there is no cache


def test_cache_replay_and_fallback_chain(env, monkeypatch: pytest.MonkeyPatch) -> None:
    llm, _, tmp_path = env
    llm.register_tool_loop("Research questions:", _happy_script([]))
    live = run_research(SPEC, use_cache=False)

    replayed: list[ResearchStep] = []
    hit = run_research(SPEC, on_step=replayed.append, use_cache=True)
    assert hit.mode == "cached" and hit.evidence == live.evidence and hit.sources == live.sources
    assert [s.title for s in replayed] == [s.title for s in live.trace]

    # JANE_MODE=cached replays without any LLM
    cached_settings = dataclasses.replace(agent.get_settings(), mode="cached")
    monkeypatch.setattr(agent, "get_settings", lambda: cached_settings)
    assert run_research(SPEC).mode == "cached"

    # live failure with use_cache=False still falls back to the cache, with a warning saying why
    live_settings = dataclasses.replace(cached_settings, mode="live")
    monkeypatch.setattr(agent, "get_settings", lambda: live_settings)
    monkeypatch.setattr(agent, "get_llm", lambda: MockLLM())
    fallback = run_research(SPEC, use_cache=False)
    assert fallback.mode == "cached"
    assert any(s.kind == "warning" and "replaying cached research" in s.title for s in fallback.trace)


def test_cache_never_downgrades_and_ignores_corrupt_files(tmp_path) -> None:
    from jane_avenue.contracts import Evidence, ResearchFindings, Source, utcnow

    def findings(n_verified: int) -> ResearchFindings:
        src = Source(source_id="S1", title="t", url="https://www.gov.uk/x", publisher="p", access_method="url_fetch")
        ev = [Evidence(evidence_id=f"E{i}", source_id="S1", kind="qualitative", topic="revenue", claim="c",
                       verification_status="verified") for i in range(1, n_verified + 1)]
        return ResearchFindings(policy=SPEC, mode="live", summary="s", sources=[src], evidence=ev,
                                started_at=utcnow())

    assert cache.save(findings(5), tmp_path) is not None
    assert cache.save(findings(2), tmp_path) is None            # a weaker run does not replace the file
    assert len(cache.load(SPEC, tmp_path).evidence) == 5
    assert cache.save(findings(6), tmp_path) is not None        # an equal or better run does
    assert cache.save(findings(9).model_copy(update={"mode": "mock"}), tmp_path) is None  # only live runs
    cache.cache_path(SPEC, tmp_path).write_text("{not json", encoding="utf-8")
    assert cache.load(SPEC, tmp_path) is None


def test_answer_question_mock_mode_is_a_labelled_placeholder() -> None:
    answer, sources, evidence = answer_question("How elastic are UK taxable profits?")
    assert answer.startswith("Placeholder") and sources and all(s.is_placeholder for s in sources)
    assert evidence


def test_answer_question_live_runs_a_small_loop_and_strips_new_numbers(env) -> None:
    llm, _, _ = env
    question = "What were onshore corporation tax receipts in 2023-24?"

    def script(history: list[dict[str, Any]]) -> ToolTurn:
        n = _n_results(history)
        if n == 0:
            return _turn(("search", {"query": "ct receipts 2023"}), n=0)
        if n == 1:
            return _turn(("fetch_url", {"source_id": "S1", "focus": "receipts"}), n=1)
        return _turn(("record_evidence", {"source_id": "S1", "items": [
            {**ITEM, "claim": "Receipts were GBP 82.3 billion.", "value": 82.3,
             "quote": "Onshore Corporation Tax receipts totalled GBP 82.3 billion in 2023 to 2024."},
            {**ITEM, "claim": "Main rate rose.", "quote": "the rise in the main rate to 25%"}]}),
            ("finish", {"reason": "done"}), n=2)

    llm.register_tool_loop(question, script)
    llm.register_text("Answer the question", "Receipts were GBP 82.3 billion [E1]. They will reach GBP 99 billion.")
    answer, sources, evidence = answer_question(question)
    assert answer == "Receipts were GBP 82.3 billion [E1]."
    assert GOV in [s.url for s in sources]
    assert [e.verification_status for e in evidence] == ["verified", "verified"]
    prompt = next(p for kind, p in llm.calls if kind == "tool_turn")
    assert f"at most {agent.QA_MAX_CALLS} tool calls" in prompt
