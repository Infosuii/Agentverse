"""Gemini research agent (MASTER_PROMPT 9.2). Owner: agent-2.

Live mode: plan -> an autonomous tool loop (`loop.py`: Google Search, fetch_url, record_evidence, lookup_dataset,
get_precedents, finish; 12 calls / 90 s) -> top-up extraction -> synthesise -> post-process. If the loop fails or
finds too little, the fixed M1 sequence (grounded search per question -> fetch -> extract) runs instead. Gemini
chooses the steps and the quotes; code verifies every quote, keeps only grounded or fetched sources, and strips
numbers the evidence does not contain. Every step streams via `on_step`.

Fallback chain: live -> cache (`data/research_cache/`) -> mock fixture. `run_research` never raises.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import get_settings
from ..contracts import (
    Confounder,
    Evidence,
    Interpretation,
    ParameterEvidence,
    PolicySpec,
    ResearchFindings,
    ResearchStep,
    Source,
    utcnow,
)
from ..llm import GroundedAnswer, LLMUnavailable, get_llm
from . import cache, prompts
from .cache import cache_key
from .domains import classify, host_of, is_grounding_redirect
from .postprocess import clip, postprocess, unquoted_numbers, value_in_quote
from .quotes import verify_quote
from .schemas import ExtractedEvidence, ExtractedEvidenceList, ResearchPlan, Synthesis
from .tools import FetchedDoc, fetch_url, strip_injection

log = logging.getLogger(__name__)

FIXTURE = Path(__file__).parent / "fixtures" / "ct_main_rate.json"
MOCK_STEP_DELAY_S = 0.05
CACHE_STEP_DELAY_S = 0.15
MAX_FETCH = 8               # readable documents per run
MAX_FETCH_ATTEMPTS = 16
WORKERS = 4
EXTRACT_WORKERS = 6
DEEP_SYNTHESIS_BUDGET_S = 80.0  # past this, synthesis uses the fast model only, to stay under 120 s overall
TOP_UP_BUDGET_S = 85.0          # after the loop, read more grounded sources only before this point of the run
MIN_LOOP_DOCS = 3               # fewer documents than this after the loop (and none left to read) -> search again
LOOP_DEADLINE_S = 70.0          # the loop (at most LOOP_BUDGET_S) must end by this point of the run
EXTRACT_BUDGET_S = 100.0        # top-up extraction for thinly evidenced documents only before this
QA_MAX_CALLS = 6
QA_BUDGET_S = 45.0
QA_MAX_DOCS = 4                 # documents read per question (loop fetches plus the top-up)
MAX_ITEMS_PER_DOC = 6
CHUNK_CHARS = 6000
CHUNKS_PER_DOC = 3

DEFAULT_QUESTIONS = (
    "What revenue effects did official costings and observed receipts show for past UK corporation tax main-rate "
    "changes?",
    "What behavioural assumptions do the OBR and HMRC use when costing changes to the corporation tax main rate?",
    "What does the evidence say about the elasticity of UK taxable profits to the corporation tax rate?",
    "How does the corporation tax rate affect business investment through the user cost of capital?",
)


class ResearchFailed(RuntimeError):
    """Live research produced nothing usable; the caller falls back."""


class Tracer:
    """Numbers, timestamps, clips and streams research steps. All emits happen on the calling thread."""

    def __init__(self, on_step: Callable[[ResearchStep], None] | None) -> None:
        self.steps: list[ResearchStep] = []
        self._on_step = on_step

    def emit(self, kind: str, title: str, detail: str = "", *, tool: str | None = None, query: str | None = None,
             source_ids: list[str] | None = None, evidence_ids: list[str] | None = None,
             duration_ms: int | None = None) -> ResearchStep:
        step = ResearchStep(step_id=len(self.steps) + 1, ts=utcnow(), kind=kind, title=clip(title, 160),  # type: ignore[arg-type]
                            detail=clip(detail), tool=tool, query=query, source_ids=source_ids or [],
                            evidence_ids=evidence_ids or [], duration_ms=duration_ms)
        self.steps.append(step)
        if self._on_step is not None:
            try:
                self._on_step(step)
            except Exception:  # a broken listener must not break research
                log.exception("on_step callback failed")
        return step


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


# ------------------------------------------------------------------------------------------------- mock fixture

def _mock_findings(spec: PolicySpec, tracer: Tracer) -> ResearchFindings:
    """Replay the placeholder fixture through `on_step` (MOCK_STEP_DELAY_S apart) for `spec`."""
    started = utcnow()
    fixture = ResearchFindings.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    for st in fixture.trace:
        tracer.emit(st.kind, st.title, st.detail, tool=st.tool, query=st.query, source_ids=st.source_ids,
                    evidence_ids=st.evidence_ids, duration_ms=st.duration_ms)
        if MOCK_STEP_DELAY_S:
            time.sleep(MOCK_STEP_DELAY_S)
    return fixture.model_copy(update={"policy": spec, "mode": "mock", "model": None, "trace": list(tracer.steps),
                                      "started_at": started, "completed_at": utcnow(),
                                      "cache_key": cache_key(spec)})


# ------------------------------------------------------------------------------------------------- live research

_STOP = frozenset("the a an and or of to in on for by with what how does do did is are was were be that this from "
                  "at as uk its their which when than past use used using about over under between into".split())
_WORD = re.compile(r"[a-z][a-z\-]{2,}")


def select_chunks(text: str, query: str, *, n: int = CHUNKS_PER_DOC, size: int = CHUNK_CHARS) -> list[str]:
    """The `n` chunks of about `size` characters with the most keyword overlap with `query`, in document order."""
    chunks: list[str] = []
    buf = ""
    for para in text.split("\n"):
        while len(para) > size:  # hard-split very long paragraphs (PDF text often has none)
            cut = para.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(para[:cut])
            para = para[cut:].lstrip()
        if buf and len(buf) + len(para) + 1 > size:
            chunks.append(buf)
            buf = ""
        buf = f"{buf}\n{para}" if buf else para
    if buf:
        chunks.append(buf)
    if len(chunks) <= n:
        return chunks
    keywords = {w for w in _WORD.findall(query.lower()) if w not in _STOP} | {"corporation", "rate"}

    def score(chunk: str) -> tuple[int, int]:
        low = chunk.lower()
        return sum(1 for k in keywords if k in low), sum(low.count(k) for k in keywords)

    best = sorted(range(len(chunks)), key=lambda i: score(chunks[i]), reverse=True)[:n]
    return [chunks[i] for i in sorted(best)]


@dataclass
class _Doc:
    source_id: str
    question: str
    fetched: FetchedDoc
    text: str  # snapshot after injection stripping: what the model saw and what quotes are checked against



class LiveResearch:
    """State and steps of one live research run. The autonomous loop (`loop.py`) and the fixed search sequence
    share the same source, fetch and evidence bookkeeping, so the trust rules are applied in one place."""

    def __init__(self, spec: PolicySpec, tracer: Tracer) -> None:
        settings = get_settings()
        self.spec = spec
        self.tracer = tracer
        self.llm = get_llm()
        self.fast = settings.model_fast
        self.deep = settings.model_deep
        self.models_used = [self.fast]
        self.description = spec.description or (
            f"Change the UK corporation tax main rate from {spec.baseline_rate_pct}% to {spec.proposed_rate_pct}%")
        self.sources: dict[str, Source] = {}       # source_id -> Source
        self.by_url: dict[str, str] = {}           # grounding URL -> source_id
        self.question_of: dict[str, str] = {}      # source_id -> question that surfaced it
        self.allowed_urls: set[str] = set()        # URLs from grounding metadata or our fetches (provenance rule)
        self.evidence: list[Evidence] = []
        self.docs: dict[str, _Doc] = {}            # source_id -> readable fetched document
        self.doc_by_url: dict[str, str] = {}       # requested or final URL of a readable document -> source_id
        self.refusals: dict[str, int] = {}         # host -> 401/403/429 responses this run
        self.failed: set[str] = set()              # source_ids whose fetch failed (not retried this run)
        self.max_docs = MAX_FETCH
        self.t0 = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    @staticmethod
    def dataset_ids() -> list[str]:
        from ..data import registry

        try:
            return [m.dataset_id for m in registry.list_datasets()]
        except Exception:
            log.exception("could not list datasets")
            return []

    # -- plan
    def plan(self) -> list[str]:
        t0 = time.monotonic()
        s = self.spec
        prompt = prompts.PLAN_PROMPT.format(description=self.description, baseline=s.baseline_rate_pct,
                                            proposed=s.proposed_rate_pct, effective=s.effective_date or "unknown",
                                            horizon=s.horizon_years)
        questions: list[str] = []
        try:
            plan = self.llm.generate_structured(prompt, ResearchPlan, system=prompts.PLAN_SYSTEM, model=self.fast,
                                                thinking_level="low")
            questions = [q.strip() for q in plan.questions if q.strip()][:7]
        except LLMUnavailable as exc:
            self.tracer.emit("warning", "Planning failed; using the standard question set", str(exc))
        for q in DEFAULT_QUESTIONS:
            if len(questions) >= 4:
                break
            if q not in questions:
                questions.append(q)
        self.tracer.emit("plan", f"Planned {len(questions)} research questions",
                         "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)), duration_ms=_ms(t0))
        return questions

    # -- sources and fetches (shared by the loop and the fixed sequence)
    def add_grounded_source(self, url: str, title: str | None, question: str) -> str:
        if url in self.by_url:
            return self.by_url[url]
        sid = f"S{len(self.sources) + 1}"
        info = classify(url, title)
        self.sources[sid] = Source(source_id=sid, title=title or info.publisher, url=url, publisher=info.publisher,
                                   publisher_type=info.publisher_type, access_method="google_search",
                                   reliability_tier=info.tier)  # type: ignore[arg-type]
        self.by_url[url] = sid
        self.question_of[sid] = question
        self.allowed_urls.add(url)
        return sid

    def _host_hint(self, url: str) -> str:
        """The real host of `url`; for a grounding redirect, the domain its grounding title names."""
        if is_grounding_redirect(url) and url in self.by_url:
            hint = (self.sources[self.by_url[url]].title or "").strip().lower()
            return hint[4:] if hint.startswith("www.") else hint
        return host_of(url)

    def refused(self, url: str) -> bool:
        """True once a host has refused us twice (401/403/429, e.g. a bot challenge). We never try to get around it."""
        return self.refusals.get(self._host_hint(url), 0) >= 2

    def register_fetch(self, url: str, doc: FetchedDoc, ms: int, *, question: str = "") -> str | None:
        """Record a fetch attempt: update or create the Source, keep the snapshot, emit a `fetch` step.
        Returns the source_id of the readable document, or None when the fetch failed."""
        grounded = self.by_url.get(url)
        if not doc.ok:
            resolved = doc.final_url != url and not is_grounding_redirect(doc.final_url)
            if grounded and resolved:  # the redirect still told us the real document URL
                self.allowed_urls.add(doc.final_url)
                self.sources[grounded] = self.sources[grounded].model_copy(update={"url": doc.final_url})
            if doc.status in (401, 403, 429):
                host = host_of(doc.final_url) if resolved else self._host_hint(url)
                self.refusals[host] = self.refusals.get(host, 0) + 1
            if grounded:
                self.failed.add(grounded)
            who = self.sources[grounded].publisher if grounded else host_of(doc.final_url or url)
            self.tracer.emit("fetch", f"Could not fetch {who}",
                             f"{doc.final_url if resolved or not grounded else self.sources[grounded].title}: "
                             f"{doc.error or f'HTTP {doc.status}'}", tool="fetch_url",
                             source_ids=[grounded] if grounded else [], duration_ms=ms)
            return None
        if doc.final_url in self.doc_by_url:  # two URLs, one document
            sid = self.doc_by_url[doc.final_url]
            self.doc_by_url[url] = sid
            self.tracer.emit("fetch", f"Fetched {self.sources[sid].publisher} (duplicate page)", doc.final_url,
                             tool="fetch_url", source_ids=[sid], duration_ms=ms)
            return sid
        info = classify(doc.final_url)
        if grounded:
            sid, base = grounded, self.sources[grounded]
        else:
            sid = f"S{len(self.sources) + 1}"
            base = Source(source_id=sid, title=info.publisher, url=doc.final_url, publisher=info.publisher,
                          access_method="url_fetch")
            self.question_of[sid] = question
        self.allowed_urls.add(doc.final_url)
        self.sources[sid] = base.model_copy(update={
            "url": doc.final_url, "title": clip(doc.title or base.title, 200), "publisher": info.publisher,
            "publisher_type": info.publisher_type, "reliability_tier": info.tier, "url_verified": True,
            "content_sha256": doc.sha256, "retrieved_at": utcnow()})
        text, removed = strip_injection(doc.text)
        if removed:
            self.tracer.emit("warning", f"Removed {removed} AI-directed sentence(s) from a fetched page",
                             f"{doc.final_url}: text addressing an AI was stripped before prompting.",
                             source_ids=[sid])
        self.tracer.emit("fetch", f"Fetched {info.publisher}: {self.sources[sid].title}",
                         f"{doc.final_url} ({doc.content_type or 'unknown type'}, {len(doc.text):,} chars)",
                         tool="fetch_url", source_ids=[sid], duration_ms=ms)
        self.docs[sid] = _Doc(sid, question or self.question_of.get(sid, ""), doc, text)
        self.doc_by_url[url] = self.doc_by_url[doc.final_url] = sid
        return sid

    # -- evidence (shared)
    def add_evidence(self, d: _Doc, items: list[ExtractedEvidence], ms: int, *,
                     tool: str = "record_evidence") -> list[tuple[str, str, str | None]]:
        """Verify each item's quote against the snapshot, check its numbers, store it and emit an `extract` step.
        Returns (evidence_id, status, note) per item."""
        src = self.sources[d.source_id]
        out: list[tuple[str, str, str | None]] = []
        for item in items[:MAX_ITEMS_PER_DOC]:
            status, note = verify_quote(item.quote, d.text)
            value = item.value
            if value is not None and not value_in_quote(value, item.quote):
                note = "; ".join(x for x in (note, "value dropped: not found in the quote") if x)
                value = None
            stray = unquoted_numbers(item.claim, item.quote)
            if stray:
                note = "; ".join(x for x in (note, "claim states a number not found in the quote") if x)
            eid = f"E{len(self.evidence) + 1}"
            confidence = "low" if status == "failed" or stray else "high" if src.reliability_tier == 1 else "medium"
            self.evidence.append(Evidence(
                evidence_id=eid, source_id=d.source_id, kind=item.kind, topic=item.topic, claim=item.claim.strip(),
                quote=item.quote.strip(), value=value, unit=item.unit, period=item.period, location=item.location,
                verification_status=status, verification_note=note, confidence=confidence))  # type: ignore[arg-type]
            out.append((eid, status, note))
        verified = sum(s == "verified" for _, s, _ in out)
        self.tracer.emit("extract", f"Recorded {len(out)} evidence items from {src.publisher}",
                         f"{verified} of {len(out)} quotes verified against the fetched text. {src.title}",
                         tool=tool, source_ids=[d.source_id], evidence_ids=[e for e, _, _ in out], duration_ms=ms)
        return out

    def unread_sources(self) -> list[Source]:
        """Grounded tier-1/2 sources not yet read, not failed and not on a refusing host."""
        return [s for s in self.sources.values()
                if s.access_method == "google_search" and s.reliability_tier <= 2 and s.source_id not in self.docs
                and s.source_id not in self.failed and not self.refused(s.url)]

    def evidence_count(self, sid: str) -> int:
        return sum(e.source_id == sid for e in self.evidence)

    def search_one(self, query: str) -> GroundedAnswer:
        """One grounded Google Search (the loop's `search` tool and the fixed sequence share it)."""
        prompt = prompts.SEARCH_PROMPT.format(question=query, description=self.description)
        return self.llm.search_grounded(prompt, system=prompts.SEARCH_SYSTEM, model=self.fast)

    # -- the fixed search sequence (M1); now the fallback for the autonomous loop
    def search(self, questions: list[str]) -> None:
        def one(q: str):  # noqa: ANN202
            t0 = time.monotonic()
            return q, self.search_one(q), _ms(t0)

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(one, q) for q in questions]
            for fut in as_completed(futures):
                try:
                    q, answer, ms = fut.result()
                except Exception as exc:
                    self.tracer.emit("warning", "A search failed", f"{type(exc).__name__}: {exc}")
                    continue
                ids = [self.add_grounded_source(c.url, c.title, q) for c in answer.citations]
                domains = sorted({self.sources[i].title for i in ids})
                detail = (f"Queries: {'; '.join(answer.queries[:3]) or q}. "
                          f"{len(ids)} grounded sources: {', '.join(domains) or 'none'}.")
                self.tracer.emit("search", f"Searched: {q}", detail, tool="google_search",
                                 query=answer.queries[0] if answer.queries else q, source_ids=ids, duration_ms=ms)
        if not self.sources:
            raise ResearchFailed("no grounded sources were found")

    def fetch(self) -> None:
        """Fetch grounded tier-1/2 sources, best first, until `max_docs` documents are readable or
        MAX_FETCH_ATTEMPTS is hit."""
        queue = sorted((s for s in self.unread_sources()),
                       key=lambda s: (s.reliability_tier, int(s.source_id[1:])))
        attempts = 0

        def one(url: str):  # noqa: ANN202
            t0 = time.monotonic()
            return url, fetch_url(url), _ms(t0)

        busy: dict = {}  # future -> host; at most one request in flight per host, so refusals are noticed early

        def next_url() -> str | None:
            for k, src in enumerate(queue):
                if self.refused(src.url) or src.url in self.doc_by_url:
                    continue
                if self._host_hint(src.url) not in busy.values():
                    del queue[k]
                    return src.url
            return None

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            while True:
                while len(busy) < WORKERS and len(self.docs) + len(busy) < self.max_docs \
                        and attempts < MAX_FETCH_ATTEMPTS and (url := next_url()) is not None:
                    busy[pool.submit(one, url)] = self._host_hint(url)
                    attempts += 1
                if not busy:
                    break
                done, _ = wait(list(busy), return_when=FIRST_COMPLETED)
                for fut in done:
                    busy.pop(fut)
                    url, doc, ms = fut.result()
                    self.register_fetch(url, doc, ms, question=self.question_of.get(self.by_url.get(url, ""), ""))

    def extract(self, docs: list[_Doc]) -> None:
        """Structured evidence extraction for documents (the fixed sequence, and a top-up after the loop)."""
        def one(d: _Doc):  # noqa: ANN202
            t0 = time.monotonic()
            src = self.sources[d.source_id]
            chunks = select_chunks(d.text, f"{d.question} {self.description}")
            prompt = prompts.EXTRACT_PROMPT.format(question=d.question, description=self.description,
                                                   title=src.title, publisher=src.publisher, url=src.url,
                                                   chunks="\n[...]\n".join(chunks), max_items=MAX_ITEMS_PER_DOC)
            out = self.llm.generate_structured(prompt, ExtractedEvidenceList, system=prompts.EXTRACT_SYSTEM,
                                               model=self.fast, thinking_level="low")
            return d, out, _ms(t0)

        with ThreadPoolExecutor(max_workers=EXTRACT_WORKERS) as pool:
            for fut in as_completed([pool.submit(one, d) for d in docs]):
                try:
                    d, out, ms = fut.result()
                except Exception as exc:
                    self.tracer.emit("warning", "Evidence extraction failed for a document",
                                     f"{type(exc).__name__}: {exc}")
                    continue
                self.add_evidence(d, out.items, ms, tool="extract")

    # -- act: the autonomous loop, then a code-driven top-up, then extraction for thinly evidenced documents
    def act(self, questions: list[str]) -> None:
        from .loop import LOOP_BUDGET_S, ResearchLoop

        budget = min(LOOP_BUDGET_S, LOOP_DEADLINE_S - self.elapsed())
        try:
            ResearchLoop(self, questions, budget_s=budget).run()
        except LLMUnavailable as exc:
            self.tracer.emit("warning", "The autonomous research loop failed; continuing with what it found",
                             str(exc))
        if self.elapsed() < TOP_UP_BUDGET_S and len(self.docs) < self.max_docs:
            if not self.unread_sources() and len(self.docs) < MIN_LOOP_DOCS:
                self.tracer.emit("reason", "Topping up with the fixed search sequence",
                                 f"The loop left {len(self.docs)} document(s) and no unread grounded sources; "
                                 "searching each research question.")
                try:
                    self.search(questions)
                except ResearchFailed:
                    pass
            unread = len(self.unread_sources())
            if unread:
                self.tracer.emit("reason", "Reading more grounded sources",
                                 f"{len(self.docs)} document(s) read; fetching up to {self.max_docs - len(self.docs)} "
                                 f"more of {unread} unread tier-1/2 sources the searches found.")
                self.fetch()
        if not self.docs and not self.sources:
            raise ResearchFailed("no grounded or fetched sources were found")
        thin = [d for d in self.docs.values() if self.evidence_count(d.source_id) < 2]
        if thin and self.elapsed() < EXTRACT_BUDGET_S:
            self.extract(thin)

    # -- synthesise
    def synthesise(self, questions: list[str]) -> Synthesis | None:
        from ..engine import default_parameters

        usable = [e for e in self.evidence if e.verification_status == "verified"]
        if not usable:
            self.tracer.emit("warning", "No verified evidence to synthesise",
                             "No extracted quote could be verified against a fetched document.")
            return None
        t0 = time.monotonic()
        lines = []
        for e in usable:
            src = self.sources[e.source_id]
            num = f" Value: {e.value:g} {e.unit or ''} ({e.period or 'period n/a'})." if e.value is not None else ""
            lines.append(f'[{e.evidence_id}] ({src.publisher}; topic {e.topic}; {e.kind}) {e.claim}{num} '
                         f'Quote: "{e.quote}"')
        params = "\n".join(f"- {a.name}: {a.label} ({a.unit})" for a in default_parameters(self.spec).values())
        prompt = prompts.SYNTH_PROMPT.format(description=self.description,
                                             questions="\n".join(f"- {q}" for q in questions),
                                             evidence="\n".join(lines), parameters=params)
        models = (self.deep, self.fast) if self.elapsed() < DEEP_SYNTHESIS_BUDGET_S else (self.fast,)
        for model in dict.fromkeys(models):
            try:
                synth = self.llm.generate_structured(prompt, Synthesis, system=prompts.SYNTH_SYSTEM, model=model,
                                                     thinking_level="low")
            except LLMUnavailable as exc:
                self.tracer.emit("warning", f"Synthesis with {model} failed", str(exc))
                continue
            if model not in self.models_used:
                self.models_used.append(model)
            cited = sorted(set(re.findall(r"E\d+", synth.summary)), key=lambda x: int(x[1:]))
            self.tracer.emit("synthesis", "Synthesised findings",
                             f"{len(synth.interpretations)} interpretations, {len(synth.parameter_evidence)} "
                             f"parameter links and {len(synth.confounders)} confounders from {len(usable)} "
                             f"verified evidence items.", evidence_ids=cited, duration_ms=_ms(t0))
            return synth
        return None

    def findings(self, questions: list[str], synth: Synthesis | None, started: datetime) -> ResearchFindings:
        from ..engine import PARAMETER_NAMES

        if synth is None:
            n = sum(e.verification_status == "verified" for e in self.evidence)
            synth = Synthesis(summary=f"No synthesis is available. {n} evidence items were verified against fetched "
                                      "documents and are listed for the analyst to review.",
                              interpretations=[], confounders=[], parameter_evidence=[],
                              open_questions=list(questions))
        draft = ResearchFindings(
            policy=self.spec, mode="live", model=" + ".join(self.models_used), summary=synth.summary,
            research_questions=questions, sources=list(self.sources.values()), evidence=self.evidence,
            interpretations=[Interpretation(interpretation_id=f"I{i}", statement=x.statement,
                                            supporting_evidence_ids=x.evidence_ids, confidence=x.confidence)
                             for i, x in enumerate(synth.interpretations, 1)],
            confounders=[Confounder(name=c.name, description=c.description, evidence_ids=c.evidence_ids,
                                    likely_direction=c.likely_direction) for c in synth.confounders],
            parameter_evidence=[ParameterEvidence(parameter=p.parameter, value=p.value, low=p.low, high=p.high,
                                                  evidence_ids=p.evidence_ids, note=p.note)
                                for p in synth.parameter_evidence],
            open_questions=synth.open_questions, trace=list(self.tracer.steps), started_at=started,
            cache_key=cache_key(self.spec))
        clean, notes = postprocess(draft, allowed_urls=self.allowed_urls, parameter_names=PARAMETER_NAMES)
        if notes:
            self.tracer.emit("warning", f"Post-processing removed {len(notes)} unsupported item(s)", " ".join(notes))
        verified = sum(e.verification_status == "verified" for e in clean.evidence)
        self.tracer.emit("reason", "Research complete",
                         f"{len(clean.sources)} sources, {len(clean.evidence)} evidence items ({verified} verified) "
                         f"in {int(self.elapsed())} s.")
        return clean.model_copy(update={"trace": clean.trace + self.tracer.steps[len(clean.trace):],
                                        "completed_at": utcnow()})

    def run(self) -> ResearchFindings:
        started = utcnow()
        questions = self.plan()
        self.act(questions)
        return self.findings(questions, self.synthesise(questions), started)


# ------------------------------------------------------------------------------------------------- cache replay

def _replay(cached: ResearchFindings, spec: PolicySpec, tracer: Tracer) -> ResearchFindings:
    """Replay a cached live run through `on_step` (CACHE_STEP_DELAY_S apart) and return it as `mode="cached"`."""
    started = utcnow()
    for st in cached.trace:
        tracer.emit(st.kind, st.title, st.detail, tool=st.tool, query=st.query, source_ids=st.source_ids,
                    evidence_ids=st.evidence_ids, duration_ms=st.duration_ms)
        if CACHE_STEP_DELAY_S:
            time.sleep(CACHE_STEP_DELAY_S)
    return cached.model_copy(update={"policy": spec, "mode": "cached", "trace": list(tracer.steps),
                                     "started_at": started, "completed_at": utcnow(), "cache_key": cache_key(spec)})


def run_research(
    spec: PolicySpec, *, on_step: Callable[[ResearchStep], None] | None = None, use_cache: bool = True
) -> ResearchFindings:
    """Research `spec`. Fallback chain: live -> cache -> mock; each fallback emits a `warning` step saying why.

    - `JANE_MODE=mock`: the labelled placeholder fixture.
    - `use_cache=True` (or `JANE_MODE=cached`) and a cached run exists: replay it (`mode="cached"`).
    - Otherwise live research; a successful live run is written to the cache.
    Never raises for ordinary failures.
    """
    settings = get_settings()
    cache_dir = settings.research_cache_dir
    tracer = Tracer(on_step)
    if settings.mode == "mock":
        return _mock_findings(spec, tracer)
    tried_cache = False
    if use_cache or settings.mode == "cached":
        tried_cache = True
        if (hit := cache.load(spec, cache_dir)) is not None:
            return _replay(hit, spec, tracer)
    if settings.mode == "cached":
        tracer.emit("warning", "No cached research for this policy; using the mock fixture",
                    f"JANE_MODE=cached and no file {cache.cache_key(spec)[:12]}... in the research cache.")
        return _mock_findings(spec, tracer)
    if not settings.gemini_configured:
        why = "GEMINI_API_KEY is not set."
    else:
        try:
            findings = LiveResearch(spec, tracer).run()
            try:
                cache.save(findings, cache_dir)
            except Exception:  # a read-only cache directory must not lose a good live result
                log.exception("could not write the research cache")
            return findings
        except Exception as exc:  # ResearchFailed, LLMUnavailable, or anything unexpected
            log.exception("live research failed")
            why = f"{type(exc).__name__}: {exc}"
    if not tried_cache and (hit := cache.load(spec, cache_dir)) is not None:
        tracer.emit("warning", "Live research unavailable; replaying cached research", why)
        return _replay(hit, spec, tracer)
    tracer.emit("warning", "Live research unavailable; using the mock fixture",
                f"{why} No cached research exists for this policy.")
    return _mock_findings(spec, tracer)


# ------------------------------------------------------------------------------------------------- one question

_QA_SPEC = PolicySpec(policy_type="corporation_tax_main_rate", tax="corporation_tax",
                      description="UK corporation tax research question", parse_method="manual")


def answer_question(question: str, *, max_calls: int = QA_MAX_CALLS,
                    budget_s: float = QA_BUDGET_S) -> tuple[str, list[Source], list[Evidence]]:
    """Single-question research for agent-10's research evaluation: the same tool loop with a smaller budget.

    Returns (answer, sources, evidence) after the same post-processing as `run_research`; the answer cites
    evidence as [E1] and contains no number absent from the verified quotes. In mock mode, or without a key, it
    returns a clearly labelled placeholder answer with the fixture's sources and evidence. Never raises.
    """
    from .loop import ResearchLoop

    settings = get_settings()
    if settings.mode == "mock" or not settings.gemini_configured:
        fixture = ResearchFindings.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
        return ("Placeholder answer (mock mode): no live research was run for this question.",
                fixture.sources, fixture.evidence)
    tracer = Tracer(None)
    spec = _QA_SPEC.model_copy(update={"description": question[:300], "raw_query": question})
    r = LiveResearch(spec, tracer)
    r.max_docs = QA_MAX_DOCS
    started = utcnow()
    try:
        ResearchLoop(r, [question], max_calls=max_calls, budget_s=budget_s, include_data=False,
                     task=prompts.QA_PROMPT.format(question=question, max_calls=max_calls)).run()
        if len(r.docs) < r.max_docs and r.unread_sources():
            r.fetch()  # read the best grounded sources the model's searches found but did not open
        thin = [d for d in r.docs.values() if r.evidence_count(d.source_id) < 2]
        if thin:
            r.extract(thin)
        usable = [e for e in r.evidence if e.verification_status == "verified"]
        answer = "No verified evidence was found for this question."
        if usable:
            lines = "\n".join(f'[{e.evidence_id}] {e.claim} Quote: "{e.quote}"' for e in usable)
            answer = r.llm.generate_text(prompts.QA_ANSWER_PROMPT.format(question=question, evidence=lines),
                                         system=prompts.SYNTH_SYSTEM, model=r.fast, thinking_level="low")
        draft = Synthesis(summary=answer, interpretations=[], confounders=[], parameter_evidence=[],
                          open_questions=[])
        clean = r.findings([question], draft, started)
        return clean.summary, clean.sources, clean.evidence
    except Exception as exc:
        log.exception("answer_question failed")
        return f"Research failed: {type(exc).__name__}: {exc}"[:300], [], []


def load_fixture() -> dict:
    """The raw mock fixture (for tests and tooling)."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
