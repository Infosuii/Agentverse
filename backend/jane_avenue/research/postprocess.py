"""Trust rules applied in code to every live research result (MASTER_PROMPT 9.2 step 5). Owner: agent-2.

Nothing the model returns is trusted:
- a source survives only if its URL came from grounding metadata or one of our fetches;
- evidence must point at a surviving source;
- parameter evidence must name a known engine parameter and cite at least one verified evidence item;
- interpretations must cite at least one verified evidence item (failed citations are removed);
- summary and interpretation sentences that contain a number absent from the evidence (and from the policy itself)
  are removed, since Gemini must not introduce numbers;
- IDs are renumbered densely (S1.., E1.., I1..) and every reference, including `[E3]` in prose, is rewritten;
- trace details are clipped.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from ..contracts import Evidence, ResearchFindings

ALLOWED_ACCESS = ("google_search", "url_fetch", "url_context", "curated_dataset")
MAX_DETAIL = 500

_REF = re.compile(r"\[\s*([ESI]\d+(?:\s*[,;]\s*[ESI]?\d+)*)\s*\]")
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(\"'])")


def clip(text: str, limit: int = MAX_DETAIL) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def numbers_in(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in _NUMBER.findall(_REF.sub(" ", text or ""))]


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def value_in_quote(value: float, quote: str | None) -> bool:
    """True when `value` appears in `quote`, allowing for scale words (bn, m, k) and percent <-> fraction."""
    for n in numbers_in(quote or ""):
        for candidate in (n, n * 1e3, n * 1e6, n * 1e9, n / 100, n * 100, -n):
            if _close(candidate, value):
                return True
    return False


def allowed_numbers(findings: ResearchFindings, evidence: Iterable[Evidence]) -> set[float]:
    """Numbers prose may use: those in verified quotes (never model-written claims), quote-checked values, the policy
    itself, and small counts ("two studies", "3 fiscal events")."""
    allowed: set[float] = {float(i) for i in range(11)}
    for e in evidence:
        allowed.update(numbers_in(e.quote or ""))
        if e.value is not None:
            allowed.add(abs(e.value))
    p = findings.policy
    for v in (p.baseline_rate_pct, p.proposed_rate_pct, p.change_pp(), p.horizon_years):
        if v is not None:
            allowed.add(abs(float(v)))
    if p.effective_date:
        allowed.update({float(p.effective_date.year), float(p.effective_date.day),
                        float(p.effective_date.year % 100), float((p.effective_date.year + 1) % 100)})
    allowed.update(numbers_in(p.description))
    return allowed


def unquoted_numbers(claim: str, quote: str | None) -> list[float]:
    """Numbers in a model-written claim that do not appear in its quote."""
    quoted = numbers_in(quote or "")
    return [n for n in numbers_in(claim) if not any(_close(n, q) for q in quoted)]


def strip_new_numbers(text: str, allowed: set[float]) -> tuple[str, list[str]]:
    """Drop sentences containing a number that is not in `allowed`. Returns (text, removed sentences)."""
    kept: list[str] = []
    removed: list[str] = []
    for sentence in _SENTENCE.split(text.strip()):
        if any(not any(_close(n, a) for a in allowed) for n in numbers_in(sentence)):
            removed.append(sentence)
        else:
            kept.append(sentence)
    return " ".join(kept), removed


def _rewrite_refs(text: str, emap: dict[str, str], imap: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        new: list[str] = []
        for raw in re.split(r"\s*[,;]\s*", m.group(1)):
            ref = raw if raw[0] in "ESI" else "E" + raw
            mapped = emap.get(ref) if ref[0] == "E" else imap.get(ref) if ref[0] == "I" else None
            if mapped and mapped not in new:
                new.append(mapped)
        return f"[{', '.join(new)}]" if new else ""

    return re.sub(r"\s+([.,;:])", r"\1", _REF.sub(repl, text)).strip()


def postprocess(findings: ResearchFindings, *, allowed_urls: set[str],
                parameter_names: Iterable[str]) -> tuple[ResearchFindings, list[str]]:
    """Apply the trust rules. Returns (clean findings, human-readable notes about everything that was dropped)."""
    notes: list[str] = []
    names = set(parameter_names)

    sources = []
    for s in findings.sources:
        if s.access_method in ALLOWED_ACCESS and s.url in allowed_urls:
            sources.append(s)
        else:
            notes.append(f"Dropped source {s.source_id}: its URL did not come from grounding or a fetch.")
    smap = {s.source_id: f"S{i}" for i, s in enumerate(sources, start=1)}

    evidence = []
    for e in findings.evidence:
        if e.source_id in smap:
            evidence.append(e)
        else:
            notes.append(f"Dropped evidence {e.evidence_id}: source {e.source_id} does not exist.")
    emap = {e.evidence_id: f"E{i}" for i, e in enumerate(evidence, start=1)}
    usable = {e.evidence_id for e in evidence if e.verification_status == "verified"}

    allowed = allowed_numbers(findings, [e for e in evidence if e.evidence_id in usable])

    interpretations = []
    for it in findings.interpretations:
        ids = [emap[x] for x in it.supporting_evidence_ids if x in usable]
        statement, removed = strip_new_numbers(it.statement, allowed)
        if removed:
            notes.append(f"Removed {len(removed)} sentence(s) with unsupported numbers from {it.interpretation_id}.")
        if not ids or not statement:
            notes.append(f"Dropped interpretation {it.interpretation_id}: no verified supporting evidence or text.")
            continue
        interpretations.append(it.model_copy(update={"supporting_evidence_ids": ids, "statement": statement}))
    imap = {it.interpretation_id: f"I{i}" for i, it in enumerate(interpretations, start=1)}
    interpretations = [it.model_copy(update={"interpretation_id": imap[it.interpretation_id],
                                             "statement": _rewrite_refs(it.statement, emap, imap)})
                       for it in interpretations]

    params = []
    for pe in findings.parameter_evidence:
        ids = [emap[x] for x in pe.evidence_ids if x in usable]
        if pe.parameter not in names:
            notes.append(f"Dropped parameter evidence for unknown parameter {pe.parameter!r}.")
        elif not ids:
            notes.append(f"Dropped parameter evidence for {pe.parameter}: it cites no verified evidence.")
        else:
            note, removed = strip_new_numbers(pe.note, allowed)
            if removed:
                notes.append(f"Removed unsupported numbers from the note on {pe.parameter}.")
            params.append(pe.model_copy(update={"evidence_ids": ids, "note": _rewrite_refs(note, emap, imap)}))

    confounders = []
    for c in findings.confounders:
        description, removed = strip_new_numbers(c.description, allowed)
        if removed:
            notes.append(f"Removed unsupported numbers from confounder {c.name!r}.")
        confounders.append(c.model_copy(update={"evidence_ids": [emap[x] for x in c.evidence_ids if x in emap],
                                                "description": _rewrite_refs(description, emap, imap)}))

    summary, removed = strip_new_numbers(_rewrite_refs(findings.summary, emap, imap), allowed)
    if removed:
        notes.append(f"Removed {len(removed)} summary sentence(s) containing numbers not found in the evidence.")
    if not summary:
        summary = "No summary could be produced from the verified evidence."

    trace = [st.model_copy(update={"detail": clip(st.detail),
                                   "source_ids": [smap.get(x, x) for x in st.source_ids
                                                  if x in smap or x.startswith("D-")],  # curated IDs stay as-is
                                   "evidence_ids": [emap[x] for x in st.evidence_ids if x in emap]})
             for st in findings.trace]

    clean = findings.model_copy(update={
        "sources": [s.model_copy(update={"source_id": smap[s.source_id]}) for s in sources],
        "evidence": [e.model_copy(update={"evidence_id": emap[e.evidence_id], "source_id": smap[e.source_id]})
                     for e in evidence],
        "interpretations": interpretations,
        "confounders": confounders,
        "parameter_evidence": params,
        "summary": summary,
        "trace": trace,
    })
    return clean, notes
