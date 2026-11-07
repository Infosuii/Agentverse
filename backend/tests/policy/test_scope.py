"""Scope gate: every branch of the MASTER_PROMPT 9.1 table, with bounds derived from the registry. Owner: agent-5."""
from __future__ import annotations

from datetime import date

import pytest

from jane_avenue.contracts import PolicyChange, PolicySpec
from jane_avenue.policy import check_scope
from jane_avenue.policy import scope as scope_module


def _change(year: int, old: float, new: float, policy_type: str = "corporation_tax_main_rate") -> PolicyChange:
    return PolicyChange(change_id=f"CT-{year}", tax="corporation_tax", policy_type=policy_type,  # type: ignore[arg-type]
                        effective_date=date(year, 4, 1), old_rate_pct=old, new_rate_pct=new, source_ids=["D-test"])


PRECEDENTS = [_change(1983, 52, 50), _change(2008, 30, 28), _change(2017, 20, 19), _change(2023, 19, 25),
              _change(2023, 19, 19, "corporation_tax_small_profits_rate")]  # SPR rows are ignored for the bounds


@pytest.fixture(autouse=True)
def registry_changes(monkeypatch: pytest.MonkeyPatch) -> list[PolicyChange]:
    changes = list(PRECEDENTS)
    monkeypatch.setattr(scope_module.registry, "load_policy_changes", lambda tax="corporation_tax": changes)
    return changes


def _spec(baseline: float | None = 25, proposed: float | None = 28, *, policy_type: str = "corporation_tax_main_rate",
          effective: date | None = date(2027, 4, 1), horizon: int = 5) -> PolicySpec:
    return PolicySpec(policy_type=policy_type, tax="corporation_tax", baseline_rate_pct=baseline,  # type: ignore[arg-type]
                      proposed_rate_pct=proposed, effective_date=effective, horizon_years=horizon)


def test_golden_policy_is_supported_with_bounds_from_the_registry() -> None:
    d = check_scope(_spec())
    assert (d.status, d.forecast_allowed, d.reasons, d.warnings) == ("supported", True, [], [])
    assert (d.validated_min_rate_pct, d.validated_max_rate_pct, d.validated_max_change_pp) == (19, 52, 6)


def test_bounds_follow_the_registry_not_constants(registry_changes: list[PolicyChange]) -> None:
    registry_changes.append(_change(2030, 25, 33))
    d = check_scope(_spec())
    assert (d.validated_max_change_pp, d.validated_max_rate_pct) == (8, 52)


@pytest.mark.parametrize("policy_type", ["unsupported", "vat_standard_rate"])
def test_policy_type_other_than_ct_is_unsupported(policy_type: str) -> None:
    d = check_scope(_spec(policy_type=policy_type))
    assert d.status == "unsupported" and not d.forecast_allowed and d.reasons


@pytest.mark.parametrize(("baseline", "proposed"), [(None, 28), (25, None), (None, None)])
def test_missing_rate_is_unsupported(baseline: float | None, proposed: float | None) -> None:
    d = check_scope(_spec(baseline, proposed))
    assert d.status == "unsupported" and "could not be determined" in d.reasons[0]


def test_missing_effective_date_is_unsupported() -> None:
    d = check_scope(_spec(effective=None))
    assert d.status == "unsupported" and d.reasons == ["An effective date is needed."]


def test_zero_change_is_unsupported() -> None:
    d = check_scope(_spec(25, 25))
    assert d.status == "unsupported" and "no change to model" in d.reasons[0]


def test_change_over_15pp_is_unsupported_with_an_analyst_readable_reason() -> None:
    d = check_scope(_spec(25, 45))
    assert d.status == "unsupported" and not d.forecast_allowed
    assert d.reasons == ["The proposed 20pp change is far outside any UK precedent (limit 15pp)."]


def test_exactly_15pp_is_allowed_with_a_warning() -> None:
    d = check_scope(_spec(25, 40))
    assert d.status == "partially_supported" and d.forecast_allowed
    assert any("larger than any UK precedent" in w for w in d.warnings)


def test_change_larger_than_largest_precedent_warns() -> None:
    d = check_scope(_spec(25, 32))  # 7pp > 6pp, rate within 19-52
    assert d.status == "partially_supported" and d.forecast_allowed
    assert d.warnings == ["The 7pp change is larger than any UK precedent (largest 6pp), so the results are an "
                          "extrapolation."]


def test_rate_outside_historical_range_warns() -> None:
    d = check_scope(_spec(20, 15))  # 5pp cut to 15%, below the 19% historical minimum
    assert d.status == "partially_supported" and d.forecast_allowed
    assert d.warnings == ["The proposed rate of 15% is outside the historical range of UK main rates (19%-52%)."]


def test_small_profits_rate_is_partially_supported() -> None:
    d = check_scope(_spec(19, 21, policy_type="corporation_tax_small_profits_rate"))
    assert d.status == "partially_supported" and d.forecast_allowed
    assert any("small profits rate" in w for w in d.warnings)


def test_zero_baseline_rate_is_unsupported() -> None:
    d = check_scope(_spec(0, 5))
    assert d.status == "unsupported" and "above 0%" in d.reasons[0]


@pytest.mark.parametrize("empty", [[], "raise"])
def test_fallback_bounds_when_registry_is_empty_or_broken(monkeypatch: pytest.MonkeyPatch, empty: object) -> None:
    def load(tax: str = "corporation_tax") -> list[PolicyChange]:
        if empty == "raise":
            raise RuntimeError("registry down")
        return []

    monkeypatch.setattr(scope_module.registry, "load_policy_changes", load)
    d = check_scope(_spec())
    assert (d.validated_min_rate_pct, d.validated_max_rate_pct, d.validated_max_change_pp) == (
        scope_module.FALLBACK_MIN_RATE_PCT, scope_module.FALLBACK_MAX_RATE_PCT, scope_module.FALLBACK_MAX_CHANGE_PP)
    assert d.forecast_allowed and any("fallback" in w for w in d.warnings)

