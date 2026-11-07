"""Structured logging: every log record carries the current `analysis_id` and `stage`. Owner: agent-1.

The orchestrator sets both in context variables while it runs. A log-record factory copies them onto every record,
so any module that logs with the standard library (`logging.getLogger(__name__).info(...)`), including agent-2's
LLM usage lines, gets them with no extra arguments, and so does every handler (uvicorn, pytest's caplog).
Outside an analysis both are "-".
"""
from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Iterator
from contextvars import ContextVar

analysis_id_var: ContextVar[str] = ContextVar("jane_analysis_id", default="-")
stage_var: ContextVar[str] = ContextVar("jane_stage", default="-")

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s [analysis=%(analysis_id)s stage=%(stage)s] %(message)s"

_base_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs) -> logging.LogRecord:
    record = _base_factory(*args, **kwargs)
    record.analysis_id = analysis_id_var.get()
    record.stage = stage_var.get()
    return record


if not getattr(logging.getLogRecordFactory(), "_jane", False):
    _record_factory._jane = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(_record_factory)


@contextlib.contextmanager
def analysis_context(analysis_id: str) -> Iterator[None]:
    token = analysis_id_var.set(analysis_id)
    try:
        yield
    finally:
        analysis_id_var.reset(token)


@contextlib.contextmanager
def stage_context(stage: str) -> Iterator[None]:
    token = stage_var.set(stage)
    try:
        yield
    finally:
        stage_var.reset(token)


_configured = False


def configure_logging(level: str | int | None = None) -> None:
    """Give the `jane_avenue` logger one stream handler with the structured format. Idempotent.

    Level comes from `JANE_LOG_LEVEL` (default INFO). uvicorn configures only its own loggers, so these lines are
    printed once.
    """
    global _configured
    if _configured:
        return
    logger = logging.getLogger("jane_avenue")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level or os.environ.get("JANE_LOG_LEVEL", "INFO").upper())
    _configured = True
