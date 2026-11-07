"""Verification checks, one module per category, registered in catalogue order (MASTER_PROMPT 9.7). Owner: agent-5."""
from __future__ import annotations

from ._base import CheckFn, CheckMeta, Outcome, check, meta_of
from .calculation import calc_001, calc_002, calc_003
from .causal import causal_001
from .citation import cite_001, cite_002, cite_003
from .data import data_001, data_002
from .evidence import evid_001, evid_002, evid_003, evid_004
from .report import report_001
from .scope import scope_001, scope_002, scope_003
from .uncertainty import unc_001

# Run order = catalogue order. REPORT-001 needs the finished report, so it runs in `check_report`, which also re-runs
# CAUSAL-001 so that the report prose is reviewed too.
ALL_CHECKS: tuple[CheckFn, ...] = (
    scope_001, scope_002, scope_003,
    cite_001, cite_002, cite_003,
    evid_001, evid_002, evid_003, evid_004,
    calc_001, calc_002, calc_003,
    data_001, data_002,
    causal_001,
    unc_001,
)
REPORT_CHECKS: tuple[CheckFn, ...] = (causal_001, report_001)
CATALOGUE: tuple[CheckFn, ...] = (*ALL_CHECKS, report_001)

__all__ = ["ALL_CHECKS", "CATALOGUE", "REPORT_CHECKS", "CheckFn", "CheckMeta", "Outcome", "check", "meta_of"]
