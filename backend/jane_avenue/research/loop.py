"""Autonomous function-calling research loop (agent-2 brief M2 step 1; MASTER_PROMPT 9.2 "Act"). Owner: agent-2.

The model decides what to do next. Its tools:

- `search(query)`: Google Search grounding. It runs the built-in `google_search` tool through the gateway
  (`search_grounded`) and returns the grounded sources with IDs. Search is wrapped as a function, rather than
  offered as the built-in tool inside this loop, because a function-calling turn returns no `url_citation`
  annotations (checked against the live API). The URLs would then come from the model, not from grounding metadata,
  and MASTER_PROMPT 9.2 requires URLs "from grounding metadata only".
- `fetch_url(source_id)`: our own fetch of a grounded source. The model cannot invent URLs.
- `record_evidence(source_id, items)`: quotes are verified against our snapshot.
- `lookup_dataset(dataset_id)`, `get_precedents(k)`: curated data for context.
- `finish(reason)`.

Our code enforces the budget (MAX_TOOL_CALLS function calls with finish excluded, and LOOP_BUDGET_S wall clock)
and the trust rules. With `store=False` the history is passed manually each turn. Response steps are appended
exactly as received, which carries the thought signatures back to the API (thinking.md, "Stateless mode").
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from ..llm import FunctionCall, function_result, user_input
from . import prompts
from .schemas import ExtractedEvidence

if TYPE_CHECKING:
    from .agent import LiveResearch

MAX_TOOL_CALLS = 12
LOOP_BUDGET_S = 90.0
MAX_TURNS = 10
MIN_TURN_S = 8.0       # do not start a turn with less time left than this
EXCERPT_CHARS = 5000
MAX_RECORD_ITEMS = 5
MAX_DATA_ROWS = 40
MAX_SEARCH_SOURCES = 8  # grounded sources listed back to the model per search
SEARCH_WORKERS = 7      # one per planned question

_ITEM = {
    "type": "object",
    "properties": {
        "quote": {"type": "string", "description": "One to three consecutive sentences copied EXACTLY from the excerpt."},
        "claim": {"type": "string", "description": "One sentence stating what the quote shows; add nothing."},
        "value": {"type": "number", "description": "A single number exactly as written in the quote, if any."},
        "unit": {"type": "string"},
        "period": {"type": "string"},
        "location": {"type": "string", "description": "Section, table or page, if shown."},
        "topic": {"type": "string", "enum": ["revenue", "investment", "gdp", "profit_shifting", "elasticity",
                                             "macro_context", "policy_history", "distribution", "other"]},
        "kind": {"type": "string", "enum": ["quantitative", "qualitative", "historical_event", "counter_evidence"]},
    },
    "required": ["quote", "claim", "topic", "kind"],
}


def tool_declarations(dataset_ids: list[str], *, include_data: bool = True) -> list[dict[str, Any]]:
    datasets = ", ".join(dataset_ids) or "none available"
    tools: list[dict[str, Any]] = [
        {"type": "function", "name": "search",
         "description": "Google Search with grounding. Returns a short grounded answer and the cited sources, each "
                        "with a source_id, its domain and reliability tier (1 official, 2 IFS/academic, 3 other). "
                        "Several searches can run in one turn.",
         "parameters": {"type": "object", "properties": {
             "query": {"type": "string", "description": "A focused search query or question."}},
             "required": ["query"]}},
        {"type": "function", "name": "fetch_url",
         "description": "Download a source returned by search and return the excerpt most relevant to `focus`. "
                        "Prefer tier 1 and 2 sources.",
         "parameters": {"type": "object", "properties": {
             "source_id": {"type": "string", "description": "A source_id returned by search, e.g. S3."},
             "focus": {"type": "string", "description": "What you are looking for in this document."}},
             "required": ["source_id", "focus"]}},
        {"type": "function", "name": "record_evidence",
         "description": "Register evidence from a fetched document. Quotes are checked against the fetched text.",
         "parameters": {"type": "object", "properties": {
             "source_id": {"type": "string", "description": "source_id of a document returned by fetch_url."},
             "items": {"type": "array", "items": _ITEM, "description": f"At most {MAX_RECORD_ITEMS} items."}},
             "required": ["source_id", "items"]}},
    ]
    if include_data:
        tools += [
            {"type": "function", "name": "lookup_dataset",
             "description": f"Rows of a curated UK dataset, for context only (cannot be cited as evidence). "
                            f"dataset_id values: {datasets}.",
             "parameters": {"type": "object", "properties": {"dataset_id": {"type": "string"}},
                            "required": ["dataset_id"]}},
            {"type": "function", "name": "get_precedents",
             "description": "The historical UK corporation tax main-rate changes most similar to this policy, with "
                            "curated costings and outcomes, for context only.",
             "parameters": {"type": "object", "properties": {"k": {"type": "integer", "description": "1-8"}},
                            "required": ["k"]}},
        ]
    tools.append({"type": "function", "name": "finish",
                  "description": "End the research when the questions are covered or the budget is nearly used.",
                  "parameters": {"type": "object", "properties": {"reason": {"type": "string"}},
                                 "required": ["reason"]}})
    return tools


def _jsonable_rows(rows: list[Any]) -> list[Any]:
    return [r.model_dump(mode="json", exclude_none=True) if hasattr(r, "model_dump") else r
            for r in rows[:MAX_DATA_ROWS]]


class ResearchLoop:
    def __init__(self, research: LiveResearch, questions: list[str], *, max_calls: int | None = None,
                 budget_s: float | None = None, task: str | None = None, include_data: bool = True) -> None:
        self.r = research
        self.questions = questions
        self.max_calls = MAX_TOOL_CALLS if max_calls is None else max_calls
        self.budget_s = LOOP_BUDGET_S if budget_s is None else budget_s
        self.task = task
        self.include_data = include_data
        self.calls_used = 0
        self.finished = False

    # ------------------------------------------------------------------------------------------- tool handlers
    def _search_result(self, query: str, answer: Any, ms: int) -> dict[str, Any]:
        r = self.r
        ids = list(dict.fromkeys(r.add_grounded_source(c.url, c.title, query) for c in answer.citations))
        r.tracer.emit("search", f"Searched: {query}",
                      f"Queries: {'; '.join(answer.queries[:3]) or query}. {len(ids)} grounded sources: "
                      f"{', '.join(sorted({r.sources[i].title for i in ids})) or 'none'}.",
                      tool="google_search", query=answer.queries[0] if answer.queries else query, source_ids=ids,
                      duration_ms=ms)
        cited = {}
        for c in answer.citations:
            sid = r.by_url.get(c.url)
            if sid and sid not in cited and c.cited_text:
                cited[sid] = c.cited_text[:200]
        ranked = sorted(ids, key=lambda i: (r.sources[i].reliability_tier, int(i[1:])))[:MAX_SEARCH_SOURCES]
        return {"ok": True, "answer": answer.text[:1200],
                "sources": [{"source_id": i, "domain": r.sources[i].title, "tier": r.sources[i].reliability_tier,
                             "fetched": i in r.docs, "supports": cited.get(i, "")} for i in ranked]}

    def _fetch_prepare(self, call: FunctionCall, *, in_flight: int = 0) -> tuple[str, dict[str, Any] | None]:
        """Checks that need no network. Returns (url, early result); an early result short-circuits the fetch.
        `in_flight` fetches already scheduled in this wave count against the document budget."""
        r = self.r
        sid = str(call.arguments.get("source_id") or "").strip()
        if sid not in r.sources:
            return "", {"ok": False, "error": "unknown source_id: use a source_id returned by search"}
        url = r.sources[sid].url
        if sid in r.docs or url in r.doc_by_url:
            return url, None  # already fetched: answered from the in-memory snapshot
        if r.refused(url):
            return url, {"ok": False, "error": f"{r.sources[sid].title} refuses automated access; try another "
                                               "source (for OBR documents, look for the copy on gov.uk)."}
        if len(r.docs) + in_flight >= r.max_docs:
            return url, {"ok": False, "error": "document budget reached; record evidence or finish"}
        return url, None

    def _excerpt(self, sid: str, focus: str) -> dict[str, Any]:
        from .agent import select_chunks

        r = self.r
        d = r.docs[sid]
        src = r.sources[sid]
        chunks = select_chunks(d.text, f"{focus} {r.description}", n=2, size=EXCERPT_CHARS // 2)
        return {"ok": True, "source_id": sid, "title": src.title, "publisher": src.publisher,
                "reliability_tier": src.reliability_tier,
                "excerpt": "<untrusted_document>\n" + "\n[...]\n".join(chunks) + "\n</untrusted_document>"}

    def _fetch_finish(self, call: FunctionCall, url: str, fetched: Any, ms: int) -> dict[str, Any]:
        r = self.r
        focus = str(call.arguments.get("focus") or "")
        if fetched is None:  # served from the snapshot of an earlier fetch
            sid = r.doc_by_url.get(url) or str(call.arguments.get("source_id"))
            r.tracer.emit("fetch", f"Re-read fetched {r.sources[sid].publisher}", f"Focus: {focus}",
                          tool="fetch_url", source_ids=[sid], duration_ms=ms)
            return self._excerpt(sid, focus)
        sid = r.register_fetch(url, fetched, ms, question=focus)
        if sid is None:
            return {"ok": False, "error": fetched.error or f"HTTP {fetched.status}"}
        return self._excerpt(sid, focus)

    def _record(self, call: FunctionCall, ms: int) -> dict[str, Any]:
        r = self.r
        sid = str(call.arguments.get("source_id") or "")
        if sid not in r.docs:
            return {"ok": False, "error": "unknown source_id: only documents returned by fetch_url can be cited"}
        items, rejected = [], 0
        for raw in list(call.arguments.get("items") or [])[:MAX_RECORD_ITEMS]:
            try:
                data = {"value": None, "unit": None, "period": None, "location": None, **dict(raw)}
                items.append(ExtractedEvidence.model_validate(data))
            except Exception:
                rejected += 1
        results = r.add_evidence(r.docs[sid], items, ms, tool="record_evidence")
        return {"ok": True, "rejected_malformed": rejected,
                "recorded": [{"evidence_id": eid, "status": status, "note": note} for eid, status, note in results]}

    def _lookup(self, call: FunctionCall, ms: int) -> dict[str, Any]:
        from ..data import registry

        dataset_id = str(call.arguments.get("dataset_id") or "")
        metas = {m.dataset_id: m for m in registry.list_datasets()}
        meta = metas.get(dataset_id)
        if meta is None:
            return {"ok": False, "error": f"unknown dataset_id; available: {sorted(metas)}"}
        if "baseline" in dataset_id:
            rows: list[Any] = [registry.load_baseline()]
        elif "rate" in dataset_id or "change" in dataset_id or "history" in dataset_id:
            rows = registry.load_policy_changes("corporation_tax")
        else:
            series = registry.load_series(dataset_id)
            rows = list(series.points) if series else []
        self.r.tracer.emit("dataset_lookup", f"Looked up dataset: {meta.title}",
                           f"{len(rows)} row(s) from {meta.publisher}" +
                           (" (placeholder data)" if meta.is_placeholder else ""),
                           tool="lookup_dataset", source_ids=[meta.source_id], duration_ms=ms)
        return {"ok": True, "dataset": meta.model_dump(mode="json", include={"dataset_id", "title", "publisher",
                                                                             "vintage", "is_placeholder"}),
                "rows": _jsonable_rows(rows)}

    def _precedents(self, call: FunctionCall, ms: int) -> dict[str, Any]:
        from ..precedents import find_precedents

        try:
            k = max(1, min(8, int(call.arguments.get("k") or 5)))
        except (TypeError, ValueError):
            k = 5
        analysis = find_precedents(self.r.spec, k=k)
        matches = [{"change_id": m.change.change_id, "effective_date": str(m.change.effective_date),
                    "old_rate_pct": m.change.old_rate_pct, "new_rate_pct": m.change.new_rate_pct,
                    "similarity": round(m.similarity, 3), "is_placeholder": m.change.is_placeholder,
                    "official_costings": _jsonable_rows(m.change.official_costings),
                    "observed_outcomes": _jsonable_rows(m.change.observed_outcomes), "notes": m.change.notes}
                   for m in analysis.matches]
        source_ids = sorted({s for m in analysis.matches for s in m.change.source_ids})
        self.r.tracer.emit("dataset_lookup", f"Retrieved {len(matches)} UK precedents",
                           ", ".join(f"{m['change_id']} ({m['old_rate_pct']:g}%->{m['new_rate_pct']:g}%)"
                                     for m in matches), tool="get_precedents", source_ids=source_ids,
                           duration_ms=ms)
        return {"ok": True, "method": analysis.method, "matches": matches}

    # ------------------------------------------------------------------------------------------------- turn
    def _execute(self, calls: list[FunctionCall]) -> list[dict[str, Any]]:
        """Run one turn's function calls and return their function_result steps, in call order.
        Searches run in parallel; fetches run in parallel waves (see below); the rest run in order."""
        from .agent import fetch_url

        r = self.r
        results: dict[int, dict[str, Any]] = {}
        budgeted: list[tuple[int, FunctionCall]] = []
        for i, call in enumerate(calls):
            if call.name == "finish":
                self.finished = True
                r.tracer.emit("reason", "Agent finished", str(call.arguments.get("reason") or "")[:400],
                              tool="finish")
                results[i] = {"ok": True}
            elif self.calls_used >= self.max_calls:
                results[i] = {"ok": False, "error": "tool budget exhausted; call finish"}
            else:
                self.calls_used += 1
                budgeted.append((i, call))

        searches = [(i, str(c.arguments.get("query") or "").strip()) for i, c in budgeted if c.name == "search"]
        if searches:
            with ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as pool:
                futures = [pool.submit(_timed, r.search_one, q) for _, q in searches]
                for (i, q), fut in zip(searches, futures, strict=True):
                    try:
                        answer, ms = fut.result()
                        results[i] = self._search_result(q, answer, ms)
                    except Exception as exc:
                        r.tracer.emit("warning", "A search failed", f"{q}: {type(exc).__name__}: {exc}")
                        results[i] = {"ok": False, "error": f"search failed: {type(exc).__name__}"}

        # Fetches run in waves: at most one per host per wave, in parallel, with the checks (refused hosts,
        # document budget, already-fetched sources) re-run before each wave so parallel calls cannot overshoot them.
        pending = [(i, call) for i, call in budgeted if call.name == "fetch_url"]
        while pending:
            wave: list[tuple[int, FunctionCall, str]] = []
            later: list[tuple[int, FunctionCall]] = []
            hosts: set[str] = set()
            for i, call in pending:
                url, early = self._fetch_prepare(call, in_flight=len(wave))
                if early is not None:
                    r.tracer.emit("fetch", "Skipped a fetch", early["error"], tool="fetch_url",
                                  source_ids=[s for s in [str(call.arguments.get("source_id"))] if s in r.sources])
                    results[i] = early
                elif url in r.doc_by_url:
                    results[i] = self._fetch_finish(call, url, None, 0)
                elif r._host_hint(url) in hosts:
                    later.append((i, call))
                else:
                    hosts.add(r._host_hint(url))
                    wave.append((i, call, url))
            if wave:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures = [pool.submit(_timed, fetch_url, url) for _, _, url in wave]
                    for (i, call, url), fut in zip(wave, futures, strict=True):
                        try:
                            doc, ms = fut.result()
                            results[i] = self._fetch_finish(call, url, doc, ms)
                        except Exception as exc:  # fetch_url never raises, but registration must not end the run
                            r.tracer.emit("warning", "Tool fetch_url failed", f"{type(exc).__name__}: {exc}")
                            results[i] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
            pending = later

        for i, call in budgeted:
            if i in results:
                continue
            t0 = time.monotonic()
            try:
                if call.name == "record_evidence":
                    results[i] = self._record(call, _ms(t0))
                elif call.name == "lookup_dataset" and self.include_data:
                    results[i] = self._lookup(call, _ms(t0))
                elif call.name == "get_precedents" and self.include_data:
                    results[i] = self._precedents(call, _ms(t0))
                else:
                    results[i] = {"ok": False, "error": f"unknown tool {call.name!r}"}
            except Exception as exc:  # a broken tool reports an error to the model; it never ends the run
                r.tracer.emit("warning", f"Tool {call.name} failed", f"{type(exc).__name__}: {exc}")
                results[i] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
        return [function_result(call, results[i]) for i, call in enumerate(calls)]

    def run(self) -> None:
        r = self.r
        start = time.monotonic()
        task = self.task or prompts.LOOP_PROMPT.format(
            description=r.description, questions="\n".join(f"{i}. {q}" for i, q in enumerate(self.questions, 1)),
            max_calls=self.max_calls, seconds=int(self.budget_s), max_docs=r.max_docs)
        history: list[dict[str, Any]] = [user_input(task)]
        tools = tool_declarations(r.dataset_ids() if self.include_data else [], include_data=self.include_data)
        for _ in range(MAX_TURNS):
            remaining = self.budget_s - (time.monotonic() - start)
            if remaining < MIN_TURN_S:
                r.tracer.emit("warning", "Research time budget reached",
                              f"Stopped the tool loop after {int(time.monotonic() - start)} s.")
                break
            turn = r.llm.tool_turn(history, tools=tools, system=prompts.LOOP_SYSTEM, model=r.fast,
                                   thinking_level="low", timeout_s=min(60.0, remaining))
            history.extend(turn.steps)
            if not turn.function_calls:
                break  # the model answered in text: it is done
            history.extend(self._execute(turn.function_calls))
            if self.finished:
                break
            if self.calls_used >= self.max_calls:
                r.tracer.emit("warning", "Tool-call budget reached",
                              f"Used {self.calls_used} of {self.max_calls} tool calls; moving on to synthesis.")
                break


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def _timed(fn: Any, arg: Any) -> tuple[Any, int]:
    t0 = time.monotonic()
    return fn(arg), _ms(t0)


__all__ = ["LOOP_BUDGET_S", "MAX_TOOL_CALLS", "ResearchLoop", "tool_declarations"]
