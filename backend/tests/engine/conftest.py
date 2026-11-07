"""Shared fixtures for engine tests (owner: agent-3).

The baseline is a frozen snapshot, so engine tests do not move when agent-6 updates the curated data. The values are
the OBR EFO October 2026 rows from agent-6's `data/curated/obr_baseline.csv` (PR #42) at the time of writing.
"""
from __future__ import annotations

from datetime import date

import pytest

from jane_avenue.contracts import BaselineProjection, BaselineYear, PolicySpec
from jane_avenue.engine import central_values, default_parameters

_ROWS = (
    ("2025-26", 97.798, 310.083, 3069.799),
    ("2026-27", 109.38664348071333, 311.43368510000005, 3179.867088),
    ("2027-28", 116.2006785394477, 309.68505460000006, 3291.0879740000005),
    ("2028-29", 122.38903958826461, 313.51649080000004, 3414.177574),
    ("2029-30", 127.37846588160546, 317.20275770000006, 3543.027808),
    ("2030-31", 132.59574346866282, 321.16142229999997, 3673.057575),
)


@pytest.fixture
def baseline() -> BaselineProjection:
    return BaselineProjection(
        vintage="OBR EFO October 2026 (test snapshot)", current_main_rate_pct=25.0, current_small_profits_rate_pct=19.0,
        years=[BaselineYear(fiscal_year=fy, ct_receipts_gbp_bn=r, business_investment_gbp_bn=i, nominal_gdp_gbp_bn=g)
               for fy, r, i, g in _ROWS],
        source_ids=["D-obr-efo"],
    )


def make_spec(t0: float = 25.0, t1: float = 28.0, **kw) -> PolicySpec:
    return PolicySpec(policy_type=kw.pop("policy_type", "corporation_tax_main_rate"), tax="corporation_tax",
                      baseline_rate_pct=t0, proposed_rate_pct=t1, effective_date=kw.pop("effective_date",
                                                                                        date(2027, 4, 1)),
                      horizon_years=kw.pop("horizon_years", 5), **kw)


@pytest.fixture
def spec_factory():
    return make_spec


@pytest.fixture
def demo_spec() -> PolicySpec:
    return make_spec()


@pytest.fixture
def central() -> dict[str, float]:
    return central_values(default_parameters())
