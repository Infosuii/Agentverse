"""Research tools: our own document fetch and untrusted-text hygiene. Owner: agent-2.

Every fetched page is UNTRUSTED DATA (MASTER_PROMPT rule 13). It is never followed as instructions; text that
addresses an AI is stripped before the page goes into a prompt, and the caller logs a `warning` step.
"""
from __future__ import annotations

import hashlib
import io
import ipaddress
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "JaneAvenue/0.1 (research prototype)"
TIMEOUT_S = 15.0
MAX_CHARS = 400_000
MAX_PDF_PAGES = 60
MAX_BYTES = 25_000_000


@dataclass(frozen=True)
class FetchedDoc:
    url: str
    final_url: str
    status: int                 # HTTP status; 0 when the request itself failed
    content_type: str
    text: str                   # extracted, whitespace-collapsed text, capped at MAX_CHARS
    sha256: str | None          # SHA-256 of `text` (the snapshot), None when nothing was extracted
    title: str | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and bool(self.text.strip())


def _failed(url: str, error: str, status: int = 0, final_url: str | None = None, content_type: str = "") -> FetchedDoc:
    return FetchedDoc(url=url, final_url=final_url or url, status=status, content_type=content_type, text="",
                      sha256=None, title=None, error=error)


def _is_public_http_url(url: str) -> str | None:
    """Return an error string when `url` must not be fetched (non-http scheme, or a local / private address)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "only public http(s) URLs can be fetched"
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return f"refusing to fetch non-public host {host}"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None  # a domain name; no DNS lookup here (tests run offline)
    if not ip.is_global:
        return f"refusing to fetch non-public address {host}"
    return None


_SPACES = re.compile(r"[ \t\f\v ]+")
_NEWLINES = re.compile(r"\s*\n\s*")


def _collapse(text: str) -> str:
    return _NEWLINES.sub("\n", _SPACES.sub(" ", text)).strip()


def _html_to_text(html: str) -> tuple[str, str | None]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    for tag in soup(["script", "style", "nav", "noscript", "template", "svg"]):
        tag.decompose()
    return _collapse(soup.get_text("\n")), title or None


def _pdf_to_text(data: bytes) -> tuple[str, str | None]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # one bad page must not lose the document
            pages.append("")
    title = None
    try:
        title = (reader.metadata.title or None) if reader.metadata else None
    except Exception:
        title = None
    return _collapse("\n".join(pages)), title


def fetch_url(url: str, *, client: httpx.Client | None = None) -> FetchedDoc:
    """Fetch `url` and extract readable text. Never raises: failures come back as a FetchedDoc with `error` set."""
    blocked = _is_public_http_url(url)
    if blocked:
        return _failed(url, blocked)
    own = client is None
    http = client or httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        resp = http.get(url)
        final_url = str(resp.url)
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if resp.status_code >= 400:
            return _failed(url, f"HTTP {resp.status_code}", resp.status_code, final_url, ctype)
        data = resp.content[:MAX_BYTES]
        is_pdf = "pdf" in ctype or data[:5] == b"%PDF-" or urlparse(final_url).path.lower().endswith(".pdf")
        if is_pdf:
            text, title = _pdf_to_text(data)
            ctype = ctype or "application/pdf"
        elif ctype in ("", "text/html", "application/xhtml+xml") or "html" in ctype:
            text, title = _html_to_text(resp.text)
        elif ctype.startswith("text/"):
            text, title = _collapse(resp.text), None
        else:
            return _failed(url, f"unsupported content type {ctype!r}", resp.status_code, final_url, ctype)
        text = text[:MAX_CHARS]
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
        return FetchedDoc(url=url, final_url=final_url, status=resp.status_code, content_type=ctype, text=text,
                          sha256=sha, title=title, error=None if text else "no text could be extracted")
    except httpx.TimeoutException:
        return _failed(url, f"timed out after {TIMEOUT_S:.0f} s")
    except Exception as exc:  # network errors, malformed PDFs, decoding problems
        log.warning("fetch failed url=%s error=%s", url, exc)
        return _failed(url, f"{type(exc).__name__}: {exc}"[:300])
    finally:
        if own:
            http.close()


# Text that addresses an AI system rather than a human reader. Matched case-insensitively; the whole sentence
# containing a match is removed.
_INJECTION = re.compile(
    r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|preceding)\s+(?:instructions|prompts?|directions)"
    r"|disregard\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts?)"
    r"|forget\s+(?:all\s+|your\s+)?(?:previous|prior)\s+instructions"
    r"|(?:new|updated|override)\s+(?:system\s+)?instructions\s*:"
    r"|system\s+prompt"
    r"|you\s+are\s+(?:now\s+)?(?:an?\s+)?(?:ai|a\.i\.|large\s+language\s+model|llm|language\s+model|chatbot|assistant)\b"
    r"|(?:attention|note|message|instructions?)\s+(?:to|for)\s+(?:any\s+|all\s+)?(?:ai|llms?|language\s+models?"
    r"|chatbots?|assistants?|gemini|chatgpt|claude)\b"
    r"|(?:as\s+an?\s+)?(?:ai|llm)\s+(?:model\s+)?(?:reading|processing|summari[sz]ing)\s+this",
    re.IGNORECASE,
)
_SENTENCE_AROUND = re.compile(r"[^.!?\n]*(?:" + _INJECTION.pattern + r")[^.!?\n]*[.!?]?", re.IGNORECASE)


def strip_injection(text: str) -> tuple[str, int]:
    """Remove sentences that address an AI. Returns (clean text, number of sentences removed)."""
    cleaned, n = _SENTENCE_AROUND.subn(" ", text)
    return (_collapse(cleaned) if n else text), n
