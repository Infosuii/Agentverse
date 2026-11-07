"""Gemini research agent (MASTER_PROMPT 9.2). Owner: agent-2.

Live mode: plan -> grounded searches -> fetch official documents -> extract evidence with verbatim quotes ->
synthesise -> post-process. Gemini chooses questions and extracts quotes; code verifies every quote, keeps only
grounded or fetched sources, and strips numbers the evidence does not contain. Every step streams via `on_step`.

Mock mode replays a clearly labelled placeholder fixture. `run_research` never raises: on failure it emits a
`warning` step and falls back (live -> mock in M1; the cache joins the chain in M2).
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass
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
from ..llm import LLMUnavailable, get_llm
from . import prompts
from .cache import cache_key
from .domains import classify, host_of, is_grounding_redirect
from .postprocess import clip, postprocess, unquoted_numbers, value_in_quote
from .quotes import verify_quote
from .schemas import ExtractedEvidenceList, ResearchPlan, Synthesis
from .tools import FetchedDoc, fetch_url, strip_injection

log = logging.getLogger(__name__)

FIXTURE = Path(__file__).parent / "fixtures" / "ct_main_rate.json"
MOCK_STEP_DELAY_S = 0.05
MAX_FETCH = 8               # readable documents per run
MAX_FETCH_ATTEMPTS = 16
WORKERS = 4
DEEP_SYNTHESIS_BUDGET_S = 70.0  # past this, synthesis uses the fast model only, to stay under 120 s overall
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
        self.by_url: dict[str, str] = {}           # grounding or fetched URL -> source_id
        self.question_of: dict[str, str] = {}      # source_id -> first question that surfaced it
        self.allowed_urls: set[str] = set()
        self.evidence: list[Evidence] = []
        self.refusals: dict[str, int] = {}  # host -> 401/403/429 responses this run
        self.t0 = time.monotonic()

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

    # -- search
    def _add_source(self, url: str, title: str | None, question: str) -> str:
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

    def search(self, questions: list[str]) -> None:
        def one(q: str):  # noqa: ANN202
            t0 = time.monotonic()
            prompt = prompts.SEARCH_PROMPT.format(question=q, description=self.description)
            return q, self.llm.search_grounded(prompt, system=prompts.SEARCH_SYSTEM, model=self.fast), _ms(t0)

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(one, q) for q in questions]
            for fut in as_completed(futures):
                try:
                    q, answer, ms = fut.result()
                except Exception as exc:
                    self.tracer.emit("warning", "A search failed", f"{type(exc).__name__}: {exc}")
                    continue
                ids = [self._add_source(c.url, c.title, q) for c in answer.citations]
                domains = sorted({self.sources[i].title for i in ids})
                detail = (f"Queries: {'; '.join(answer.queries[:3]) or q}. "
                          f"{len(ids)} grounded sources: {', '.join(domains) or 'none'}.")
                self.tracer.emit("search", f"Searched: {q}", detail, tool="google_search",
                                 query=answer.queries[0] if answer.queries else q, source_ids=ids, duration_ms=ms)
        if not self.sources:
            raise ResearchFailed("no grounded sources were found")

    # -- fetch
    @staticmethod
    def _host_hint(src: Source) -> str:
        if is_grounding_redirect(src.url):
            hint = (src.title or "").strip().lower()
            return hint[4:] if hint.startswith("www.") else hint
        return host_of(src.url)

    def fetch(self) -> list[_Doc]:
        """Fetch tier-1/2 sources, best first, until MAX_FETCH documents are readable or MAX_FETCH_ATTEMPTS is hit.
        Hosts that refuse us (401/403/429, e.g. a bot challenge) are skipped for the rest of the run; we never try
        to get around such blocks."""
        queue = sorted((s for s in self.sources.values() if s.reliability_tier <= 2),
                       key=lambda s: (s.reliability_tier, int(s.source_id[1:])))
        docs: list[_Doc] = []
        seen_final: set[str] = set()
        blocked: set[str] = set()
        attempts = 0

        def one(src: Source):  # noqa: ANN202
            t0 = time.monotonic()
            return src, fetch_url(src.url), _ms(t0)

        def next_candidate() -> Source | None:
            while queue:
                src = queue.pop(0)
                if self._host_hint(src) not in blocked:
                    return src
            return None

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            pending = set()
            while True:
                while len(pending) < WORKERS and len(docs) + len(pending) < MAX_FETCH \
                        and attempts < MAX_FETCH_ATTEMPTS and (src := next_candidate()) is not None:
                    pending.add(pool.submit(one, src))
                    attempts += 1
                if not pending:
                    break
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for fut in done:
                    self._handle_fetch(*fut.result(), docs, seen_final, blocked)
        return docs

    def _handle_fetch(self, src: Source, doc: FetchedDoc, ms: int, docs: list[_Doc], seen_final: set[str],
                      blocked: set[str]) -> None:
        sid = src.source_id
        if not doc.ok:
            resolved = doc.final_url != src.url and not is_grounding_redirect(doc.final_url)
            if resolved:  # we still learned the real document URL from the redirect
                self.allowed_urls.add(doc.final_url)
                self.sources[sid] = src.model_copy(update={"url": doc.final_url})
            if doc.status in (401, 403, 429):  # refused; after two refusals the host is skipped for this run
                host = host_of(doc.final_url) if resolved else self._host_hint(src)
                self.refusals[host] = self.refusals.get(host, 0) + 1
                if self.refusals[host] >= 2:
                    blocked.add(host)
            self.tracer.emit("fetch", f"Could not fetch {src.publisher}",
                             f"{doc.final_url if resolved else src.title}: {doc.error or f'HTTP {doc.status}'}",
                             tool="fetch_url", source_ids=[sid], duration_ms=ms)
            return
        info = classify(doc.final_url)
        self.allowed_urls.add(doc.final_url)
        self.sources[sid] = src.model_copy(update={
            "url": doc.final_url, "title": clip(doc.title or src.title, 200), "publisher": info.publisher,
            "publisher_type": info.publisher_type, "reliability_tier": info.tier, "url_verified": True,
            "content_sha256": doc.sha256, "retrieved_at": utcnow()})
        if doc.final_url in seen_final:
            self.tracer.emit("fetch", f"Fetched {info.publisher} (duplicate page)", doc.final_url,
                             tool="fetch_url", source_ids=[sid], duration_ms=ms)
            return
        seen_final.add(doc.final_url)
        text, removed = strip_injection(doc.text)
        if removed:
            self.tracer.emit("warning", f"Removed {removed} AI-directed sentence(s) from a fetched page",
                             f"{doc.final_url}: text addressing an AI was stripped before prompting.",
                             source_ids=[sid])
        self.tracer.emit("fetch", f"Fetched {info.publisher}: {self.sources[sid].title}",
                         f"{doc.final_url} ({doc.content_type or 'unknown type'}, {len(doc.text):,} chars)",
                         tool="fetch_url", source_ids=[sid], duration_ms=ms)
        docs.append(_Doc(sid, self.question_of.get(sid, ""), doc, text))

    # -- extract
    def extract(self, docs: list[_Doc]) -> None:
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

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for fut in as_completed([pool.submit(one, d) for d in docs]):
                try:
                    d, out, ms = fut.result()
                except Exception as exc:
                    self.tracer.emit("warning", "Evidence extraction failed for a document",
                                     f"{type(exc).__name__}: {exc}")
                    continue
                src = self.sources[d.source_id]
                ids: list[str] = []
                verified = 0
                for item in out.items[:MAX_ITEMS_PER_DOC]:
                    status, note = verify_quote(item.quote, d.text)
                    value = item.value
                    if value is not None and not value_in_quote(value, item.quote):
                        note = "; ".join(x for x in (note, "value dropped: not found in the quote") if x)
                        value = None
                    stray = unquoted_numbers(item.claim, item.quote)
                    if stray:
                        note = "; ".join(x for x in (note, "claim states a number not found in the quote") if x)
                    eid = f"E{len(self.evidence) + 1}"
                    confidence = ("low" if status == "failed" or stray else
                                  "high" if src.reliability_tier == 1 else "medium")
                    self.evidence.append(Evidence(
                        evidence_id=eid, source_id=d.source_id, kind=item.kind, topic=item.topic,
                        claim=item.claim.strip(), quote=item.quote.strip(), value=value, unit=item.unit,
                        period=item.period, location=item.location, verification_status=status,
                        verification_note=note, confidence=confidence))  # type: ignore[arg-type]
                    ids.append(eid)
                    verified += status == "verified"
                self.tracer.emit("extract", f"Extracted {len(ids)} evidence items from {src.publisher}",
                                 f"{verified} of {len(ids)} quotes verified against the fetched text. {src.title}",
                                 tool="record_evidence", source_ids=[d.source_id], evidence_ids=ids,
                                 duration_ms=ms)

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
        elapsed = time.monotonic() - self.t0
        models = (self.deep, self.fast) if elapsed < DEEP_SYNTHESIS_BUDGET_S else (self.fast,)
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

    def run(self) -> ResearchFindings:
        from ..engine import PARAMETER_NAMES

        started = utcnow()
        questions = self.plan()
        self.search(questions)
        self.extract(self.fetch())
        synth = self.synthesise(questions)
        if synth is None:
            n = sum(e.verification_status == "verified" for e in self.evidence)
            summary = (f"No synthesis is available. {n} evidence items were verified against fetched documents "
                       "and are listed for the analyst to review.")
            synth = Synthesis(summary=summary, interpretations=[], confounders=[], parameter_evidence=[],
                              open_questions=list(questions))
        findings = ResearchFindings(
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
        clean, notes = postprocess(findings, allowed_urls=self.allowed_urls, parameter_names=PARAMETER_NAMES)
        if notes:
            self.tracer.emit("warning", f"Post-processing removed {len(notes)} unsupported item(s)",
                             " ".join(notes))
        verified = sum(e.verification_status == "verified" for e in clean.evidence)
        self.tracer.emit("reason", "Research complete",
                         f"{len(clean.sources)} sources, {len(clean.evidence)} evidence items ({verified} verified).")
        return clean.model_copy(update={"trace": clean.trace + self.tracer.steps[len(clean.trace):],
                                        "completed_at": utcnow()})


def run_research(
    spec: PolicySpec, *, on_step: Callable[[ResearchStep], None] | None = None, use_cache: bool = True
) -> ResearchFindings:
    """Research `spec`. Never raises for ordinary failures: it emits a `warning` step and falls back to mock."""
    settings = get_settings()
    tracer = Tracer(on_step)
    if settings.mode == "mock":
        return _mock_findings(spec, tracer)
    if settings.mode == "cached":
        tracer.emit("warning", "Cached research is not available yet; using the mock fixture",
                    "Replaying committed live runs arrives in M2.")
        return _mock_findings(spec, tracer)
    if not settings.gemini_configured:
        tracer.emit("warning", "Live research unavailable; using the mock fixture", "GEMINI_API_KEY is not set.")
        return _mock_findings(spec, tracer)
    try:
        return LiveResearch(spec, tracer).run()
    except Exception as exc:  # ResearchFailed, LLMUnavailable, or anything unexpected
        log.exception("live research failed; falling back to the mock fixture")
        tracer.emit("warning", "Live research failed; using the mock fixture", f"{type(exc).__name__}: {exc}")
        return _mock_findings(spec, tracer)


def load_fixture() -> dict:
    """The raw mock fixture (for tests and tooling)."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
