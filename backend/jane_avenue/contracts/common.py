"""Shared primitives. FROZEN CONTRACT: change only through a `contract-change` PR (PROJECT.md).

Units: *_pct = percent (25.0 = 25%); *_gbp_bn = £bn nominal; unsuffixed rates/shares = fractions;
fiscal years "YYYY-YY"; revenue sign = Exchequer view (positive = more tax).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict

CONTRACT_VERSION = "1.0.0"


class Contract(BaseModel):
    """Base class for every contract model. Unknown fields are rejected."""
    model_config = ConfigDict(extra="forbid")


Mode = Literal["mock", "live", "cached"]
TaxName = Literal["corporation_tax", "vat"]
Confidence = Literal["high", "medium", "low"]
EvidenceClass = Literal["observed_outcome", "official_costing", "model_scenario", "assumption", "ai_interpretation"]


class YearValue(Contract):
    fiscal_year: str
    value: float


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fiscal_year_of(d: date) -> str:
    """UK fiscal year containing d (CT financial years start 1 April)."""
    start = d.year if (d.month, d.day) >= (4, 1) else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def fiscal_year_range(first: str, n: int) -> list[str]:
    start = int(first[:4])
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(start, start + n)]
