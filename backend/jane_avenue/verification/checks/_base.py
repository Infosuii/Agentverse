"""Shared plumbing for verification checks (MASTER_PROMPT 9.7). Owner: agent-5.

A check is a plain function `analysis -> Outcome`, decorated with `@check(...)` to attach its catalogue entry. The
decorator turns the `Outcome` into a `VerificationCheck`, so every check reports in the same shape:

- `pass`: nothing found.
- `issue`: the rule found a problem. That is `fail` for error and blocking checks, and `warn` for warning checks.
- `warn`: a softer finding inside an error check (for example CALC-002's Monte Carlo median test).
- `skipped`: the check could not run (nothing to check, or a crash; see `verify.run_checks`).

Checks only read the analysis. They never change it.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import wraps
from typing import Literal

from ...contracts import Analysis, CheckCategory, Severity, VerificationCheck

Method = Literal["rule", "recompute", "source_fetch", "llm_critic"]
OutcomeStatus = Literal["pass", "issue", "warn", "skipped"]
MAX_LISTED = 8  # how many affected items a detail sentence names before saying "and N more"


@dataclass(frozen=True)
class CheckMeta:
    check_id: str
    category: CheckCategory
    severity: Severity
    method: Method
    title: str


@dataclass
class Outcome:
    status: OutcomeStatus
    detail: str
    affected_ids: list[str] = field(default_factory=list)
    severity: Severity | None = None  # overrides the catalogue severity (EVID-004 is a warning in mock mode)


CheckFn = Callable[[Analysis], VerificationCheck]


def build(meta: CheckMeta, outcome: Outcome) -> VerificationCheck:
    severity = outcome.severity or meta.severity
    if outcome.status == "issue":
        status = "warn" if severity in ("warning", "info") else "fail"
    else:
        status = outcome.status
    return VerificationCheck(check_id=meta.check_id, category=meta.category, severity=severity, status=status,
                             title=meta.title, detail=outcome.detail, method=meta.method,
                             affected_ids=list(dict.fromkeys(outcome.affected_ids)))


def check(check_id: str, category: CheckCategory, severity: Severity, method: Method,
          title: str) -> Callable[[Callable[[Analysis], Outcome]], CheckFn]:
    meta = CheckMeta(check_id, category, severity, method, title)

    def decorate(fn: Callable[[Analysis], Outcome]) -> CheckFn:
        @wraps(fn)
        def run(analysis: Analysis) -> VerificationCheck:
            return build(meta, fn(analysis))

        run.meta = meta  # type: ignore[attr-defined]
        return run

    return decorate


def meta_of(fn: CheckFn) -> CheckMeta:
    return fn.meta  # type: ignore[attr-defined]


def listing(items: Iterable[str]) -> str:
    """"E1, E2 and E3", capped at MAX_LISTED names."""
    items = list(dict.fromkeys(items))
    if len(items) > MAX_LISTED:
        shown = ", ".join(items[:MAX_LISTED])
        return f"{shown} and {len(items) - MAX_LISTED} more"
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def plural(n: int, word: str, suffix: str = "s") -> str:
    return f"{n} {word}{'' if n == 1 else suffix}"
