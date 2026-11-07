"""Research cache (MASTER_PROMPT 9.2 "Caching"). Owner: agent-2.

- The key is the SHA-256 of the canonical JSON of {policy_type, baseline_rate_pct, proposed_rate_pct, horizon_years}.
- A live run writes `<JANE_RESEARCH_CACHE_DIR>/<key>.json` (the committed golden runs live in `data/research_cache/`).
- A replay re-emits the stored trace through `on_step` and returns `mode="cached"`.

A live run never replaces a cached file with a weaker one: it only writes when there is no file yet or the new run
has at least as many verified evidence items, so a demo run cannot silently degrade a reviewed golden file.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path

from ..config import get_settings
from ..contracts import PolicySpec, ResearchFindings

log = logging.getLogger(__name__)


def cache_key(spec: PolicySpec) -> str:
    """SHA-256 of the canonical JSON of the four fields that determine the research question."""
    payload = {"policy_type": spec.policy_type, "baseline_rate_pct": spec.baseline_rate_pct,
               "proposed_rate_pct": spec.proposed_rate_pct, "horizon_years": spec.horizon_years}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_path(spec: PolicySpec, cache_dir: Path | None = None) -> Path:
    return (cache_dir or get_settings().research_cache_dir) / f"{cache_key(spec)}.json"


def _verified(findings: ResearchFindings) -> int:
    return sum(e.verification_status == "verified" for e in findings.evidence)


def load(spec: PolicySpec, cache_dir: Path | None = None) -> ResearchFindings | None:
    """The cached findings for `spec`, or None when there is no (valid) cache file."""
    path = cache_path(spec, cache_dir)
    if not path.is_file():
        return None
    try:
        return ResearchFindings.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # a corrupt or outdated file is a cache miss, never a crash
        log.exception("ignoring unreadable research cache file %s", path)
        return None


def save(findings: ResearchFindings, cache_dir: Path | None = None) -> Path | None:
    """Write a live run to the cache (atomically). Returns the path, or None when the existing file was kept."""
    if findings.mode != "live":
        return None
    path = cache_path(findings.policy, cache_dir)
    existing = load(findings.policy, cache_dir)
    if existing is not None and _verified(existing) > _verified(findings):
        log.info("kept cached research %s (%d verified > %d)", path.name, _verified(existing), _verified(findings))
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    data = findings.model_copy(update={"cache_key": cache_key(findings.policy)}).model_dump_json(indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path
