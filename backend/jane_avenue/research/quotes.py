"""Verbatim-quote verification against fetched text (MASTER_PROMPT 9.2 step 3). Owner: agent-2.

The model is never trusted to have copied a quote correctly. `verify_quote` checks it against the snapshot we fetched:

1. Normalise both strings (Unicode NFKC, casefold, unify quote marks / dashes / odd spaces, collapse whitespace).
2. An exact substring match is `verified`.
3. Otherwise anchor on the rarest 4-word shingle of the quote that occurs in the text, and compare windows sized to
   the quote length +/-15% around each anchor with `difflib.SequenceMatcher`. A ratio >= 0.90 is `verified` with a
   note such as "fuzzy match 0.93".
4. Anything else is `failed`, as is a quote shorter than MIN_QUOTE_WORDS words and MIN_QUOTE_CHARS characters.

Quotes elided with "..." are verified part by part: every part must verify on its own.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Literal

QuoteStatus = Literal["verified", "failed"]

FUZZY_THRESHOLD = 0.90
SHINGLE = 4
MIN_QUOTE_WORDS = 6   # a quote must be at least this many words ...
MIN_QUOTE_CHARS = 30  # ... or this many normalised characters, else "25%" or "higher than" would verify trivially
_MAX_ANCHORS = 40  # windows compared per quote part; bounds the cost on very repetitive pages

_CHAR_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "`": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "«": '"', "»": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", " ": " ", "​": "", "­": "", "﻿": "",
})
_WS = re.compile(r"\s+")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_ELLIPSIS = re.compile(r"\s*(?:\.\s*\.\s*\.|…)\s*")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP).casefold()
    return _WS.sub(" ", text).strip()


def _numbers(s: str) -> list[str]:
    return _NUM.findall(s)


def _best_fuzzy(q: str, t: str) -> tuple[float, str]:
    """Best SequenceMatcher ratio between normalised quote `q` and windows of normalised text `t`, and that window."""
    words = q.split(" ")
    if len(words) < SHINGLE:
        return 0.0, ""
    padded = f" {t} "
    # (count, offset of the shingle inside q, shingle) for shingles that occur in the text at all
    found: list[tuple[int, int, str]] = []
    offset = 0
    for i in range(len(words) - SHINGLE + 1):
        shingle = " ".join(words[i:i + SHINGLE])
        count = padded.count(f" {shingle} ")
        if count:
            found.append((count, offset, shingle))
        offset += len(words[i]) + 1
    if not found:
        return 0.0, ""
    found.sort(key=lambda f: f[0])
    best, best_window = 0.0, ""
    n = len(q)
    sizes = sorted({max(1, round(n * f)) for f in (0.85, 0.92, 1.0, 1.08, 1.15)})
    anchors = 0
    for _, q_off, shingle in found[:3]:  # the three rarest shingles
        start = 0
        while anchors < _MAX_ANCHORS:
            pos = padded.find(f" {shingle} ", start)
            if pos < 0:
                break
            start = pos + 1
            anchors += 1
            t_pos = pos  # index in `t` (the leading pad cancels the space before the shingle)
            for size in sizes:
                lo = max(0, t_pos - q_off - (size - n) // 2)
                window = t[lo:lo + size]
                sm = SequenceMatcher(None, q, window, autojunk=False)
                if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:
                    continue
                ratio = sm.ratio()
                if ratio > best:  # keep a little context so a number cut at the window edge is not missed
                    best, best_window = ratio, t[max(0, lo - 30):lo + size + 30]
            if best >= 0.999:
                return best, best_window
    return best, best_window


def _verify_part(q: str, t: str) -> tuple[QuoteStatus, str | None]:
    if q in t:
        return "verified", None
    ratio, window = _best_fuzzy(q, t)
    if ratio >= FUZZY_THRESHOLD:
        missing = [x for x in _numbers(q) if x not in _numbers(window)]
        if missing:  # near-identical wording but a changed figure is exactly the error we must catch
            return "failed", f"near match {ratio:.2f}, but number(s) {', '.join(missing)} differ from the source"
        return "verified", f"fuzzy match {ratio:.2f}"
    return "failed", f"quote not found in source text (best fuzzy match {ratio:.2f})" if ratio else \
        "quote not found in source text"


def verify_quote(quote: str | None, text: str | None) -> tuple[QuoteStatus, str | None]:
    """Check `quote` against the fetched `text`. Returns (status, note)."""
    if not quote or not quote.strip():
        return "failed", "no quote supplied"
    if not text or not text.strip():
        return "failed", "no fetched text to check against"
    t = normalise(text)
    parts = [normalise(p).strip("\"' ") for p in _ELLIPSIS.split(quote)]
    parts = [p for p in parts if p]
    if not parts:
        return "failed", "no quote supplied"
    whole = " ".join(parts)
    if len(whole.split(" ")) < MIN_QUOTE_WORDS and len(whole) < MIN_QUOTE_CHARS:
        return "failed", (f"quote too short to verify (needs {MIN_QUOTE_WORDS} words or {MIN_QUOTE_CHARS} "
                          "characters)")
    if len(parts) == 1:
        return _verify_part(parts[0], t)
    notes: list[str] = []
    for part in parts:
        if len(part.split(" ")) < 3:
            continue  # a 1-2 word fragment between ellipses proves nothing on its own; skip it
        status, note = _verify_part(part, t)
        if status == "failed":
            return "failed", f"elided quote: a part was not found ({note})"
        if note:
            notes.append(note)
    if not notes and all(len(p.split(" ")) < 3 for p in parts):
        return "failed", "elided quote has no checkable part"
    return "verified", "elided quote; " + ("; ".join(notes) if notes else "all parts exact")
