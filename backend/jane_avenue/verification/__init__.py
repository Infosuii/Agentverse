"""Independent verification. Owner: agent-5."""
from .faults import FAULT_TARGETS, FAULTS
from .verify import build_report, run_checks, verify

__all__ = ["FAULTS", "FAULT_TARGETS", "build_report", "run_checks", "verify"]
