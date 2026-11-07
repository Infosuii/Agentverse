"""Append-only, hash-chained audit log (JSON lines). Owner: agent-4.

Each event's hash = SHA-256(prev_hash + canonical JSON of the event body), so
editing or deleting any earlier line breaks verify_chain().
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contracts.schemas import AuditEvent

GENESIS = "0" * 64


def _path(path: str | Path | None) -> Path:
    return Path(path or os.environ.get("AUDIT_LOG_PATH", ".cache/audit.jsonl"))


def _digest(prev_hash: str, body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev_hash + canon).encode("utf-8")).hexdigest()


def _last_hash(p: Path) -> str:
    if not p.exists():
        return GENESIS
    last = GENESIS
    with open(p, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = json.loads(line)["hash"]
    return last


def log(actor: str, alert_id: str | None, payload: dict, path: str | Path | None = None) -> AuditEvent:
    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = _last_hash(p)
    body = {
        "event_id": uuid.uuid4().hex,
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "alert_id": alert_id,
        "payload": payload,
        "prev_hash": prev,
    }
    event = AuditEvent(**body, hash=_digest(prev, body))
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(body | {"hash": event.hash}, default=str) + "\n")
    return event


def verify_chain(path: str | Path | None = None) -> bool:
    p = _path(path)
    if not p.exists():
        return True
    prev = GENESIS
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            h = rec.pop("hash")
            if rec.get("prev_hash") != prev or _digest(prev, rec) != h:
                return False
            prev = h
    return True
