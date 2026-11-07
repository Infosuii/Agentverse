"""Branches of individual checks that the fault suite does not reach. Owner: agent-5."""
from __future__ import annotations

from datetime import date

import pytest

from jane_avenue.contracts import Analysis
from jane_avenue.verification.checks.calculation import calc_001, calc_002
from jane_avenue.verification.checks.citation import cite_002
from jane_avenue.verification.checks.data import data_002, vintage_date
from jane_avenue.verification.checks.evidence import evid_004
from jane_avenue.verification.checks.scope import scope_001, scope_003


@pytest.mark.parametrize(("mode", "severity", "status"), [("mock", "warning", "warn"), ("cached", "blocking", "fail"),
                                                          ("live", "blocking", "fail")])
def test_evid_004_blocks_only_in_live_and_cached(mode: str, severity: str, status: str,
                                                  golden_analysis: Analysis) -> None:
    assert golden_analysis.research is not None
    golden_analysis.research.mode = mode  # type: ignore[assignment]
    result = evid_004(golden_analysis)
    assert (result.severity, result.status) == (severity, status)


def test_evid_004_passes_in_cached_mode_with_enough_verified_evidence(clean_analysis: Analysis) -> None:
    assert clean_analysis.research is not None
    clean_analysis.research.mode = "cached"
    result = evid_004(clean_analysis)
    assert (result.severity, result.status) == ("blocking", "pass")
    assert "E1" in result.detail and "E2" in result.detail


def test_cite_002_flags_missing_quotes(clean_analysis: Analysis) -> None:
    assert clean_analysis.research is not None
    clean_analysis.research.evidence[1].quote = "  "
    result = cite_002(clean_analysis)
    assert result.status == "fail" and result.affected_ids == ["E2"] and "no verbatim quote" in result.detail


def test_scope_001_fails_when_scope_was_never_checked(clean_analysis: Analysis) -> None:
    clean_analysis.scope = None
    assert scope_001(clean_analysis).status == "fail"


def test_scope_003_names_the_unreliable_years(clean_analysis: Analysis) -> None:
    assert clean_analysis.policy is not None and clean_analysis.simulation is not None
    clean_analysis.policy.horizon_years = 7
    clean_analysis.simulation.scenarios[0].result.fiscal_years += ["2032-33", "2033-34"]
    result = scope_003(clean_analysis)
    assert result.status == "warn" and "gdp_level_pct.2033-34" in result.affected_ids


def test_calc_checks_skip_when_there_is_no_forecast(clean_analysis: Analysis) -> None:
    clean_analysis.simulation = None
    assert calc_001(clean_analysis).status == "skipped"
    assert calc_002(clean_analysis).status == "skipped"


def test_calc_002_warns_when_the_monte_carlo_median_drifts(clean_analysis: Analysis) -> None:
    assert clean_analysis.simulation is not None and clean_analysis.simulation.monte_carlo is not None
    central = clean_analysis.simulation.scenarios[0].result
    for m in central.metrics:
        if m.metric == "revenue_behavioural_gbp_bn":
            for yv in m.values:
                yv.value = 1.0
    for dist in clean_analysis.simulation.monte_carlo.distributions:
        if dist.metric == "revenue_behavioural_gbp_bn":
            for band in dist.bands:
                band.p50 = 2.0
    result = calc_002(clean_analysis)
    assert (result.severity, result.status) == ("error", "warn")


@pytest.mark.parametrize(("vintage", "expected"), [
    ("OBR EFO March 2026", date(2026, 3, 1)), ("OBR EFO Oct 2025", date(2025, 10, 1)), ("2024", date(2024, 1, 1)),
    ("placeholder", None),
])
def test_vintage_date(vintage: str, expected: date | None) -> None:
    assert vintage_date(vintage) == expected


def test_data_002_flags_an_undated_vintage(clean_analysis: Analysis) -> None:
    assert clean_analysis.simulation is not None
    clean_analysis.simulation.baseline_vintage = "placeholder"
    result = data_002(clean_analysis)
    assert result.status == "warn" and "age is unknown" in result.detail
