"""Publisher and reliability tier from a URL's domain (agent-2 brief section 6). Owner: agent-2."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from ..contracts import PublisherType


@dataclass(frozen=True)
class DomainInfo:
    publisher: str
    publisher_type: PublisherType
    tier: int  # 1 official, 2 IFS / peer-reviewed / international bodies, 3 other


# Most specific first: ons.gov.uk and legislation.gov.uk must win over gov.uk.
_DOMAINS: tuple[tuple[str, DomainInfo], ...] = (
    ("obr.uk", DomainInfo("Office for Budget Responsibility", "obr", 1)),
    ("ons.gov.uk", DomainInfo("Office for National Statistics", "ons", 1)),
    ("legislation.gov.uk", DomainInfo("legislation.gov.uk", "parliament", 1)),
    ("gov.uk", DomainInfo("GOV.UK", "other", 1)),  # publisher_type refined from the path below
    ("bankofengland.co.uk", DomainInfo("Bank of England", "boe", 1)),
    ("parliament.uk", DomainInfo("UK Parliament", "parliament", 1)),
    ("ifs.org.uk", DomainInfo("Institute for Fiscal Studies", "ifs", 2)),
    ("oecd.org", DomainInfo("OECD", "international_org", 2)),
    ("imf.org", DomainInfo("International Monetary Fund", "international_org", 2)),
    ("nber.org", DomainInfo("National Bureau of Economic Research", "academic", 2)),
    ("doi.org", DomainInfo("DOI", "academic", 2)),
    ("sciencedirect.com", DomainInfo("ScienceDirect", "academic", 2)),
    ("jstor.org", DomainInfo("JSTOR", "academic", 2)),
    ("aeaweb.org", DomainInfo("American Economic Association", "academic", 2)),
    ("ox.ac.uk", DomainInfo("Oxford University Centre for Business Taxation", "academic", 2)),
    ("cepr.org", DomainInfo("CEPR", "academic", 2)),
)
_NEWS = ("bbc.co.uk", "bbc.com", "ft.com", "reuters.com", "theguardian.com", "telegraph.co.uk", "thetimes.co.uk",
         "economist.com", "bloomberg.com", "cityam.com", "independent.co.uk", "sky.com")
_GROUNDING_REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def is_grounding_redirect(url: str) -> bool:
    return any(_matches(host_of(url), h) for h in _GROUNDING_REDIRECT_HOSTS)


def classify(url: str, title_hint: str | None = None) -> DomainInfo:
    """Classify a URL. For grounding redirect URLs the real domain is unknown until fetched, so `title_hint`
    (grounding titles are usually the bare domain, e.g. "obr.uk") is used instead."""
    host = host_of(url)
    if (not host or is_grounding_redirect(url)) and title_hint:
        hint = title_hint.strip().lower()
        host = hint[4:] if hint.startswith("www.") else hint
    for domain, info in _DOMAINS:
        if _matches(host, domain):
            if domain == "gov.uk":
                text = f"{url} {title_hint or ''}".lower()
                if "hm-revenue-customs" in text or "hmrc" in text:
                    return DomainInfo("HM Revenue & Customs", "hmrc", 1)
                if "hm-treasury" in text or "treasury" in text:
                    return DomainInfo("HM Treasury", "hmt", 1)
            return info
    if any(_matches(host, d) for d in _NEWS):
        return DomainInfo(host, "news", 3)
    return DomainInfo(host or "unknown", "other", 3)
