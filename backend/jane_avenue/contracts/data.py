from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from .common import Contract


class DatasetMeta(Contract):
    dataset_id: str
    title: str
    description: str
    publisher: str
    source_url: str
    licence: str
    retrieved_at: date | None = None
    vintage: str | None = None
    file: str                           # relative to data/
    source_id: str                      # "D-<slug>"
    is_placeholder: bool = False
    notes: str = ""


class TimeSeriesPoint(Contract):
    period: str
    value: float


class TimeSeries(Contract):
    series_id: str
    title: str
    unit: str
    frequency: Literal["annual", "fiscal_year", "quarterly", "monthly"]
    dataset_id: str
    points: list[TimeSeriesPoint]


class MacroContext(Contract):
    period: str
    real_gdp_growth_pct: float | None = None
    cpi_inflation_pct: float | None = None
    bank_rate_pct: float | None = None
    unemployment_rate_pct: float | None = None
    source_ids: list[str] = Field(default_factory=list)


class BaselineYear(Contract):
    fiscal_year: str
    ct_receipts_gbp_bn: float
    business_investment_gbp_bn: float
    nominal_gdp_gbp_bn: float


class BaselineProjection(Contract):
    vintage: str                        # e.g. "OBR EFO March 2026"
    current_main_rate_pct: float
    current_small_profits_rate_pct: float
    years: list[BaselineYear]
    source_ids: list[str]
    extrapolated_from: str | None = None
    is_placeholder: bool = False
    notes: str = ""
