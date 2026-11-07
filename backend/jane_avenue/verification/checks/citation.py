"""Citation checks CITE-001..003 (MASTER_PROMPT 9.7). Owner: agent-5."""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx

from ...contracts import Analysis, Source
from ._base import Outcome, check, listing, plural

FETCH_LIMIT = 10
FETCH_TIMEOUT_S = 5.0
RESEARCH_ACCESS = ("google_search", "url_fetch", "url_context")  # sources that must carry a verified URL
_RESERVED_SUFFIXES = (".invalid", ".test", ".example", ".localhost", ".local")  # RFC 2606 / 6761: never real sites
_RESERVED_HOSTS = ("example.com", "example.org", "example.net", "localhost")


def url_problem(url: str) -> str | None:
    """Why `url` cannot be a real, retrievable source, or None if it is well-formed."""
    if not url or url != url.strip() or any(ch.isspace() for ch in url):
        return "is empty or contains spaces"
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return "is not an http(s) URL"
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or "." not in host:
        return "has no valid host name"
    if host.endswith(_RESERVED_SUFFIXES) or any(host == h or host.endswith("." + h) for h in _RESERVED_HOSTS):
        return "uses a reserved domain that never hosts real documents"
    return None


def fetch_ok(url: str) -> bool:
    """HEAD the URL (falling back to a streamed GET when HEAD is refused) and report whether it resolves."""
    headers = {"User-Agent": "JaneAvenue-verifier/1.0"}
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_S, follow_redirects=True, headers=headers) as client:
            response = client.head(url)
            if response.status_code in (403, 405) or response.status_code >= 500:
                with client.stream("GET", url) as streamed:
                    return streamed.status_code < 400
            return response.status_code < 400
    except httpx.HTTPError:
        return False


FETCH: Callable[[str], bool] = fetch_ok  # replaced in tests; never reached in mock mode


def _fetch_all(sources: list[Source]) -> dict[str, bool]:
    if not sources:
        return {}
    with ThreadPoolExecutor(max_workers=min(FETCH_LIMIT, len(sources))) as pool:
        results = list(pool.map(lambda s: FETCH(s.url), sources))
    return {s.source_id: ok for s, ok in zip(sources, results, strict=True)}


def cited_source_ids(analysis: Analysis) -> set[str]:
    """Sources that something relies on: evidence, assumptions or official costings."""
    ids: set[str] = set()
    if analysis.research:
        ids |= {e.source_id for e in analysis.research.evidence}
    if analysis.simulation:
        ids |= {sid for a in analysis.simulation.assumptions for sid in a.source_ids}
    if analysis.precedents:
        ids |= {c.source_id for m in analysis.precedents.matches for c in m.change.official_costings}
    return ids


@check("CITE-001", "citation", "error", "source_fetch", "Source URLs are real and retrievable")
def cite_001(analysis: Analysis) -> Outcome:
    """Every non-placeholder URL must be well-formed. Sources that are cited must also be verified: fetched during
    research, or (live mode) re-fetched now. Uncited Google Search grounding results are listed for context only:
    many were never fetched, and some hosts refuse bots, so requiring them would fail every live run."""
    sources = [s for s in analysis.sources if not s.is_placeholder]
    if not sources:
        return Outcome("skipped", "No non-placeholder sources to check (placeholders are reported by DATA-001).")
    malformed = [(s.source_id, why) for s in sources if (why := url_problem(s.url)) is not None]
    if malformed:
        return Outcome("issue", "Source URLs that cannot be real documents: "
                                + "; ".join(f"{sid} {why}" for sid, why in malformed) + ".",
                       [sid for sid, _ in malformed])
    cited = cited_source_ids(analysis)
    unverified = [s for s in sources
                  if s.access_method in RESEARCH_ACCESS and not s.url_verified and s.source_id in cited]
    uncited = sum(1 for s in sources if s.access_method in RESEARCH_ACCESS and not s.url_verified
                  and s.source_id not in cited)
    was, are = ("was", "is") if uncited == 1 else ("were", "are")
    context = (f" {plural(uncited, 'uncited search result')} {was} not fetched and {are} shown for context only."
               if uncited else "")
    if analysis.mode == "mock":
        return Outcome("skipped", f"All {plural(len(sources), 'source URL')} are well-formed; re-fetching is skipped "
                                  "in mock mode.")
    if analysis.mode == "cached":
        if unverified:
            ids = [s.source_id for s in unverified]
            return Outcome("issue", f"Cited {listing(ids)} {'was' if len(ids) == 1 else 'were'} never fetched and "
                                    f"verified during the recorded research run.{context}", ids)
        return Outcome("pass", f"All {plural(len(sources), 'source URL')} are well-formed, and every cited source was "
                               f"verified when the research was recorded.{context}")
    to_fetch, too_many = unverified[:FETCH_LIMIT], unverified[FETCH_LIMIT:]
    results = _fetch_all(to_fetch)
    failed = [sid for sid, ok in results.items() if not ok] + [s.source_id for s in too_many]
    if failed:
        extra = f" ({len(too_many)} more were over the {FETCH_LIMIT}-fetch limit)" if too_many else ""
        return Outcome("issue", f"Could not retrieve cited {listing(failed)} within {FETCH_TIMEOUT_S:g}s, and "
                                f"{'it was' if len(failed) == 1 else 'they were'} not verified during research"
                                f"{extra}.{context}", failed)
    fetched = f"; re-fetched {plural(len(results), 'unverified URL')} successfully" if results else ""
    return Outcome("pass", f"All {plural(len(sources), 'source URL')} are well-formed and every cited source is "
                           f"verified{fetched}.{context}")


@check("CITE-002", "citation", "error", "rule", "Quantitative evidence has verified verbatim quotes")
def cite_002(analysis: Analysis) -> Outcome:
    if analysis.research is None:
        return Outcome("skipped", "No research findings to check.")
    quantitative = [e for e in analysis.research.evidence if e.kind == "quantitative" or e.value is not None]
    if not quantitative:
        return Outcome("pass", "No quantitative evidence items to check.")
    no_quote = [e.evidence_id for e in quantitative if not (e.quote or "").strip()]
    unverified = [e.evidence_id for e in quantitative
                  if e.evidence_id not in no_quote and e.verification_status != "verified"]
    if no_quote or unverified:
        parts = []
        if no_quote:
            parts.append(f"{listing(no_quote)} {'has' if len(no_quote) == 1 else 'have'} no verbatim quote")
        if unverified:
            parts.append(f"{listing(unverified)} {'is' if len(unverified) == 1 else 'are'} not verified against "
                         "the source text")
        return Outcome("issue", "Quantitative evidence " + "; ".join(parts) + ".", no_quote + unverified)
    return Outcome("pass", f"All {plural(len(quantitative), 'quantitative evidence item')} have verified quotes.")


@check("CITE-003", "citation", "error", "rule", "Every cited source ID exists")
def cite_003(analysis: Analysis) -> Outcome:
    known = {s.source_id for s in analysis.sources}
    cited: list[tuple[str, str]] = []  # (where, source_id)
    if analysis.research:
        cited += [(e.evidence_id, e.source_id) for e in analysis.research.evidence]
    if analysis.simulation:
        cited += [(a.name, sid) for a in analysis.simulation.assumptions for sid in a.source_ids]
    if analysis.precedents:
        cited += [(f"{m.change.change_id}.costing.{c.fiscal_year}", c.source_id)
                  for m in analysis.precedents.matches for c in m.change.official_costings]
    if not cited:
        return Outcome("pass", "Nothing cites a source yet.")
    missing = [(where, sid) for where, sid in cited if sid not in known]
    if missing:
        detail = "; ".join(f"{where} cites {sid}" for where, sid in missing[:8])
        more = f" (and {len(missing) - 8} more)" if len(missing) > 8 else ""
        return Outcome("issue", f"{plural(len(missing), 'citation')} point to sources that are not in the analysis: "
                                f"{detail}{more}.", [where for where, _ in missing])
    return Outcome("pass", f"All {plural(len(cited), 'citation')} resolve to sources in the analysis.")
