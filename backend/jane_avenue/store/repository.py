"""SQLite store for analyses and their event streams (MASTER_PROMPT 9.9). Owner: agent-1.

One connection per store, shared across threads (`check_same_thread=False`), with every call under one lock.
Bodies are contract JSON, so the store never needs a schema migration when contracts gain optional fields.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from ..contracts import Analysis, AnalysisEvent, AnalysisSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    status      TEXT NOT NULL,
    body        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS analyses_created ON analyses (created_at DESC);
CREATE TABLE IF NOT EXISTS events (
    analysis_id TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    body        TEXT NOT NULL,
    PRIMARY KEY (analysis_id, seq)
);
"""

R = TypeVar("R")


class AnalysisStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:" and not self.path.startswith("file:"):
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---- helpers -----------------------------------------------------------------------------------------------
    def _locked(self, fn: Callable[[sqlite3.Connection], R]) -> R:
        with self._lock:
            result = fn(self._conn)
            self._conn.commit()
            return result

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- analyses ----------------------------------------------------------------------------------------------
    def save(self, analysis: Analysis) -> None:
        row = (analysis.analysis_id, analysis.created_at.isoformat(), analysis.updated_at.isoformat(),
               analysis.status, analysis.model_dump_json())
        self._locked(lambda c: c.execute(
            "INSERT INTO analyses (analysis_id, created_at, updated_at, status, body) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(analysis_id) DO UPDATE SET updated_at=excluded.updated_at, status=excluded.status, "
            "body=excluded.body", row))

    def get(self, analysis_id: str) -> Analysis | None:
        row = self._locked(lambda c: c.execute(
            "SELECT body FROM analyses WHERE analysis_id = ?", (analysis_id,)).fetchone())
        return Analysis.model_validate_json(row[0]) if row else None

    def status(self, analysis_id: str) -> str | None:
        row = self._locked(lambda c: c.execute(
            "SELECT status FROM analyses WHERE analysis_id = ?", (analysis_id,)).fetchone())
        return row[0] if row else None

    def list(self, limit: int = 50) -> list[AnalysisSummary]:
        rows = self._locked(lambda c: c.execute(
            "SELECT body FROM analyses ORDER BY created_at DESC, rowid DESC LIMIT ?", (max(0, limit),)).fetchall())
        out: list[AnalysisSummary] = []
        for (body,) in rows:
            a = Analysis.model_validate_json(body)
            out.append(AnalysisSummary(
                analysis_id=a.analysis_id, created_at=a.created_at, status=a.status, query=a.request.query,
                policy_description=a.policy.description if a.policy else None,
                verification_overall=a.verification.overall if a.verification else None))
        return out

    # ---- events ------------------------------------------------------------------------------------------------
    def next_seq(self, analysis_id: str) -> int:
        row = self._locked(lambda c: c.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM events WHERE analysis_id = ?", (analysis_id,)).fetchone())
        return int(row[0]) + 1

    def append_event(self, event: AnalysisEvent) -> None:
        self._locked(lambda c: c.execute("INSERT INTO events (analysis_id, seq, body) VALUES (?, ?, ?)",
                                         (event.analysis_id, event.seq, event.model_dump_json())))

    def append_next_event(self, analysis_id: str, build: Callable[[int], AnalysisEvent]) -> AnalysisEvent:
        """Take the next seq and append the event built for it under one lock, so seqs stay unique across threads."""
        with self._lock:  # re-entrant: next_seq and append_event take the same lock
            event = build(self.next_seq(analysis_id))
            self.append_event(event)
            return event

    def events_after(self, analysis_id: str, after_seq: int = 0) -> list[AnalysisEvent]:
        rows = self._locked(lambda c: c.execute(
            "SELECT body FROM events WHERE analysis_id = ? AND seq > ? ORDER BY seq", (analysis_id, after_seq)
        ).fetchall())
        return [AnalysisEvent.model_validate_json(b) for (b,) in rows]
