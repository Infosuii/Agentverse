"""Verification fixtures. Owner: agent-5.

- `golden_analysis`: the real mock-mode pipeline output for the golden query (stubs and placeholders included).
- `clean_analysis`: the same analysis with every placeholder resolved and two verified, quoted evidence items, plus a
  registry whose baseline and datasets are not placeholders. Every check passes on it, so each injected fault must
  turn exactly its target check from pass to warn/fail.
"""
from __future__ import annotations

from datetime import date

import pytest

from jane_avenue.contracts import Analysis, AnalysisOptions, AnalysisRequest, Evidence, Source, utcnow
from jane_avenue.data import registry
from jane_avenue.orchestrator import create_analysis, run_analysis
from jane_avenue.store import AnalysisStore

GOLDEN_QUERY = "What would happen if the UK increased corporation tax from 25% to 28%?"


def run_pipeline(query: str = GOLDEN_QUERY, draws: int = 200) -> Analysis:
    store = AnalysisStore(":memory:")
    try:
        request = AnalysisRequest(query=query, options=AnalysisOptions(monte_carlo_draws=draws))
        analysis = run_analysis(store, create_analysis(store, request).analysis_id)
    finally:
        store.close()
    assert analysis.status == "completed", analysis.error
    return analysis


@pytest.fixture(scope="session")
def _golden() -> Analysis:
    return run_pipeline()


@pytest.fixture
def golden_analysis(_golden: Analysis) -> Analysis:
    return _golden.model_copy(deep=True)


@pytest.fixture
def clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry reads used by the checks return verified (non-placeholder), current data with the same numbers."""
    baseline = registry.load_baseline().model_copy(update={
        "is_placeholder": False, "extrapolated_from": None, "vintage": f"OBR EFO {date.today():%B %Y}"})
    datasets = [d.model_copy(update={"is_placeholder": False}) for d in registry.list_datasets()]
    monkeypatch.setattr(registry, "load_baseline", lambda vintage="latest": baseline.model_copy(deep=True))
    monkeypatch.setattr(registry, "list_datasets", lambda: [d.model_copy(deep=True) for d in datasets])


def _clean(analysis: Analysis) -> Analysis:
    a = analysis.model_copy(deep=True)
    now = utcnow()
    sources = [
        Source(source_id="S1", title="Economic and fiscal outlook", url="https://obr.uk/efo/economic-and-fiscal-outlook",
               publisher="Office for Budget Responsibility", publisher_type="obr", retrieved_at=now,
               access_method="url_fetch", reliability_tier=1, url_verified=True),
        Source(source_id="S2", title="Corporate tax elasticities", url="https://ifs.org.uk/publications/ct-elasticities",
               publisher="Institute for Fiscal Studies", publisher_type="ifs", retrieved_at=now,
               access_method="url_fetch", reliability_tier=2, url_verified=True),
    ]
    evidence = [
        Evidence(evidence_id="E1", source_id="S1", kind="quantitative", topic="revenue",
                 claim="The 2023 main-rate rise was costed at about £12bn a year.",
                 quote="raise around £12 billion a year", value=12.0, unit="£bn", period="2023-24",
                 verification_status="verified", confidence="high"),
        Evidence(evidence_id="E2", source_id="S2", kind="quantitative", topic="elasticity",
                 claim="The taxable profit elasticity is about 0.2.", quote="an elasticity of around 0.2",
                 value=0.2, unit="elasticity", verification_status="verified", confidence="medium"),
    ]
    assert a.research is not None and a.precedents is not None and a.simulation is not None
    a.research.sources, a.research.evidence = sources, evidence
    for s in a.precedents.sources:
        s.is_placeholder = False
    for m in a.precedents.matches:
        m.change.is_placeholder = False
    for x in a.simulation.assumptions:
        x.is_placeholder = False
    a.simulation.baseline_vintage = f"OBR EFO {date.today():%B %Y}"
    a.sources = [*sources, *(s.model_copy(update={"is_placeholder": False}) for s in a.sources
                             if s.source_id not in {"S1", "S2"})]
    return a


@pytest.fixture
def clean_analysis(golden_analysis: Analysis, clean_registry: None) -> Analysis:
    return _clean(golden_analysis)
