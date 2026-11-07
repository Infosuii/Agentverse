"""Verification checks, one module per category, registered in catalogue order (MASTER_PROMPT 9.7). Owner: agent-5."""
from __future__ import annotations

from ._base import CheckFn, CheckMeta, Outcome, check, meta_of
from .calculation import calc_001, calc_002, calc_003
from .citation import cite_002, cite_003
from .data import data_001, data_002
from .evidence import evid_001, evid_004
from .scope import scope_001, scope_002, scope_003

# Run order = catalogue order. REPORT-001 is run separately, after the report exists (`verify.check_report`).
ALL_CHECKS: tuple[CheckFn, ...] = (
    scope_001, scope_002, scope_003,
    cite_002, cite_003,
    evid_001, evid_004,
    calc_001, calc_002, calc_003,
    data_001, data_002,
)

__all__ = ["ALL_CHECKS", "CheckFn", "CheckMeta", "Outcome", "check", "meta_of"]
