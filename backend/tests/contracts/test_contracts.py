"""Contract round-trips and helpers. Owner: agent-1."""
from datetime import date

import pytest
from pydantic import ValidationError

from jane_avenue import contracts as c


def test_every_public_name_is_exported():
    for name in c.__all__:
        assert hasattr(c, name), name
    assert c.CONTRACT_VERSION == "1.1.0"
    assert c.STAGES == ("parsing", "researching", "precedents", "modelling", "verifying", "reporting")
    assert "revenue_behavioural_gbp_bn" in c.METRIC_NAMES


@pytest.mark.parametrize(("d", "fy"), [(date(2027, 4, 1), "2027-28"), (date(2027, 3, 31), "2026-27"),
                                       (date(2099, 12, 31), "2099-00")])
def test_fiscal_year_of(d, fy):
    assert c.fiscal_year_of(d) == fy


def test_fiscal_year_range():
    assert c.fiscal_year_range("2027-28", 3) == ["2027-28", "2028-29", "2029-30"]


def test_policy_helpers(demo_policy):
    assert demo_policy.change_pp() == 3.0
    assert demo_policy.direction() == "increase"
    assert demo_policy.model_copy(update={"proposed_rate_pct": 23.0}).direction() == "decrease"
    assert c.PolicySpec(policy_type="unsupported").change_pp() is None


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        c.PolicySpec(policy_type="unsupported", surprise=1)


def test_request_limits():
    with pytest.raises(ValidationError):
        c.AnalysisRequest(query="x" * 2001)
    with pytest.raises(ValidationError):
        c.AnalysisRequest(query="   ")
    with pytest.raises(ValidationError):
        c.ParseRequest(query="   ")
    with pytest.raises(ValidationError):
        c.AnalysisOptions(monte_carlo_draws=20001)


def test_analysis_round_trip(demo_request):
    now = c.utcnow()
    a = c.Analysis(analysis_id="abc", created_at=now, updated_at=now, status="queued", mode="mock",
                   request=demo_request)
    assert c.Analysis.model_validate_json(a.model_dump_json()) == a
