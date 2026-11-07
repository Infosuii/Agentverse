"""Shared test setup. Owner: agent-1.

Mock mode and an in-memory database are forced BEFORE any `jane_avenue` import, so no test can reach Gemini or
write a database file, and CI needs no secrets (MASTER_PROMPT rule 8).
"""
import os

os.environ["JANE_MODE"] = "mock"
os.environ["JANE_DB_PATH"] = ":memory:"
os.environ["JANE_LOAD_DOTENV"] = "0"  # otherwise load_dotenv() would re-add a key from a developer's .env
os.environ.pop("GEMINI_API_KEY", None)

from datetime import date  # noqa: E402

import pytest  # noqa: E402

from jane_avenue.contracts import AnalysisOptions, AnalysisRequest, PolicySpec  # noqa: E402

GOLDEN_QUERY = "What would happen if the UK increased corporation tax from 25% to 28%?"


@pytest.fixture
def demo_policy() -> PolicySpec:
    return PolicySpec(policy_type="corporation_tax_main_rate", tax="corporation_tax", baseline_rate_pct=25.0,
                      proposed_rate_pct=28.0, effective_date=date(2027, 4, 1), horizon_years=5,
                      description="Raise the CT main rate from 25% to 28% from 1 April 2027",
                      raw_query=GOLDEN_QUERY, parse_method="manual")


@pytest.fixture
def demo_request() -> AnalysisRequest:
    return AnalysisRequest(query=GOLDEN_QUERY, options=AnalysisOptions(monte_carlo_draws=500))
