"""Owner: agent-6. STUB: placeholder registry (agent-1 M0). Agent-6 replaces this with curated, sourced datasets.

EVERY value here is a placeholder (`is_placeholder=True`): round numbers for wiring only, not real data.
The rate history is the unverified seed list from MASTER_PROMPT section 9.3.
"""
from __future__ import annotations

from datetime import date

from ..contracts import (
    BaselineProjection,
    BaselineYear,
    DatasetMeta,
    MacroContext,
    PolicyChange,
    Source,
    TimeSeries,
    fiscal_year_range,
)

DATASET_VERSION = "placeholder-0"

_SOURCES: dict[str, Source] = {
    "D-placeholder-hmrc": Source(source_id="D-placeholder-hmrc", title="HMRC Corporation Tax rates (placeholder)",
                                 url="https://www.gov.uk/government/organisations/hm-revenue-customs",
                                 publisher="HM Revenue & Customs", publisher_type="hmrc",
                                 access_method="curated_dataset", reliability_tier=1, is_placeholder=True),
    "D-placeholder-obr": Source(source_id="D-placeholder-obr", title="OBR Economic and Fiscal Outlook (placeholder)",
                                url="https://obr.uk/", publisher="Office for Budget Responsibility",
                                publisher_type="obr", access_method="curated_dataset", reliability_tier=1,
                                is_placeholder=True),
}

# (financial year the change took effect, old rate %, new rate %), unverified seed list.
_SEED_CHANGES: tuple[tuple[int, float, float], ...] = (
    (1983, 52, 50), (1984, 50, 45), (1985, 45, 40), (1986, 40, 35), (1990, 35, 34), (1991, 34, 33),
    (1997, 33, 31), (1999, 31, 30), (2008, 30, 28), (2011, 28, 26), (2012, 26, 24), (2013, 24, 23),
    (2014, 23, 21), (2015, 21, 20), (2017, 20, 19), (2023, 19, 25),
)

_BASELINE_FIRST_YEAR = "2025-26"
_RECEIPTS = (95, 98, 101, 105, 109, 113, 117, 121)
_INVESTMENT = (270, 280, 290, 300, 310, 320, 330, 340)
_GDP = (3000, 3100, 3200, 3300, 3400, 3500, 3600, 3700)


def get_source(source_id: str) -> Source | None:
    return _SOURCES.get(source_id)


def list_sources() -> list[Source]:
    return list(_SOURCES.values())


def list_datasets() -> list[DatasetMeta]:
    return [
        DatasetMeta(dataset_id="ct_main_rate_history", title="CT main rate history (placeholder)",
                    description="Unverified seed list of UK CT main-rate changes.", publisher="HMRC",
                    source_url="https://www.gov.uk/government/organisations/hm-revenue-customs",
                    licence="Open Government Licence v3.0", file="curated/ct_main_rate_history.csv",
                    source_id="D-placeholder-hmrc", is_placeholder=True),
        DatasetMeta(dataset_id="obr_baseline", title="OBR baseline (placeholder)",
                    description="Round placeholder numbers for wiring only.", publisher="OBR",
                    source_url="https://obr.uk/", licence="Open Government Licence v3.0",
                    file="curated/obr_baseline.csv", source_id="D-placeholder-obr", is_placeholder=True),
    ]


def load_policy_changes(tax: str = "corporation_tax") -> list[PolicyChange]:
    """Oldest first."""
    if tax != "corporation_tax":
        return []
    return [
        PolicyChange(change_id=f"CT-MAIN-{fy}", tax="corporation_tax", policy_type="corporation_tax_main_rate",
                     effective_date=date(fy, 4, 1), old_rate_pct=old, new_rate_pct=new,
                     notes="Placeholder seed row; not yet verified.", source_ids=["D-placeholder-hmrc"],
                     is_placeholder=True)
        for fy, old, new in _SEED_CHANGES
    ]


def load_baseline(vintage: str = "latest") -> BaselineProjection:
    years = fiscal_year_range(_BASELINE_FIRST_YEAR, len(_RECEIPTS))
    return BaselineProjection(
        vintage="placeholder",
        current_main_rate_pct=25.0,
        current_small_profits_rate_pct=19.0,
        years=[BaselineYear(fiscal_year=fy, ct_receipts_gbp_bn=r, business_investment_gbp_bn=i, nominal_gdp_gbp_bn=g)
               for fy, r, i, g in zip(years, _RECEIPTS, _INVESTMENT, _GDP, strict=True)],
        source_ids=["D-placeholder-obr"],
        is_placeholder=True,
        notes="Placeholder round numbers for wiring only. Not real data.",
    )


def load_macro_context(period: str) -> MacroContext | None:
    return None


def load_series(series_id: str) -> TimeSeries | None:
    return None
