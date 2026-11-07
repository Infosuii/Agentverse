"""Verifier fault-injection evaluation. Owner: agent-10."""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date

import jane_avenue.verification as verification_pkg

from ..config import get_settings
from ..contracts import (
    Analysis,
    AnalysisRequest,
    Evidence,
    ParameterEvidence,
    ReportSection,
    Source,
    VerificationEval,
    utcnow,
)
from ..data import registry
from ..orchestrator.pipeline import create_analysis, run_analysis
from ..store.repository import AnalysisStore


@contextmanager
def _clean_registry_context():
    """Ensure registry baseline and datasets are in a clean non-extrapolated state and mode='mock' during
    deterministic fault-suite evaluation, matching agent-5's `clean_registry` fixture so `DATA-001` and
    `DATA-002` can be fault-injected cleanly without live LLM calls.
    """
    orig_load_baseline = registry.load_baseline
    orig_list_datasets = registry.list_datasets
    prev_mode = os.environ.get("JANE_MODE")
    os.environ["JANE_MODE"] = "mock"
    get_settings.cache_clear()
    clean_base = orig_load_baseline().model_copy(
        update={
            "is_placeholder": False,
            "extrapolated_from": None,
            "vintage": f"OBR EFO {date.today():%B %Y}",
        },
        deep=True,
    )
    clean_datasets = [d.model_copy(update={"is_placeholder": False}, deep=True) for d in orig_list_datasets()]
    registry.load_baseline = lambda vintage="latest": clean_base.model_copy(deep=True)  # type: ignore[assignment]
    registry.list_datasets = lambda: [d.model_copy(deep=True) for d in clean_datasets]  # type: ignore[assignment]
    try:
        yield
    finally:
        registry.load_baseline = orig_load_baseline  # type: ignore[assignment]
        registry.list_datasets = orig_list_datasets  # type: ignore[assignment]
        if prev_mode is None:
            os.environ.pop("JANE_MODE", None)
        else:
            os.environ["JANE_MODE"] = prev_mode
        get_settings.cache_clear()


def build_clean_golden_analysis() -> Analysis:
    """Generate the golden-path 25% -> 28% analysis via the pipeline and prepare a clean baseline for fault injection.

    In mock mode, the M0/M1 research fixture and team-prior assumptions carry `is_placeholder=True` and
    `verification_status="unverified"`, which rightly trigger DATA-001 and EVID-004 on raw mock runs.
    To test all fault injections without clean-case masking (as specified in agent-5's `suite.py`),
    we normalize the golden analysis into a clean reference state while preserving all real engine,
    simulation, scope, and precedent outputs from the pipeline.
    """
    store = AnalysisStore(":memory:")
    created = create_analysis(
        store,
        AnalysisRequest(query="What would happen if the UK increased corporation tax from 25% to 28% from 1 April 2027?"),
    )
    golden = run_analysis(store, created.analysis_id)
    clean = golden.model_copy(deep=True)

    # Ensure sources are non-placeholder tier-1 official sources with verified URLs
    s1 = Source(
        source_id="S1",
        title="OBR Economic and Fiscal Outlook — Corporation Tax",
        url="https://obr.uk/efo/economic-and-fiscal-outlook-march-2025/",
        publisher="Office for Budget Responsibility",
        publisher_type="obr",
        published_date=date(2025, 3, 26),
        retrieved_at=utcnow(),
        access_method="url_fetch",
        reliability_tier=1,
        url_verified=True,
        content_sha256="a" * 64,
        is_placeholder=False,
    )
    s2 = Source(
        source_id="S2",
        title="HMRC Corporation Tax Statistics",
        url="https://www.gov.uk/government/statistics/corporation-tax-statistics-2024",
        publisher="HM Revenue & Customs",
        publisher_type="hmrc",
        published_date=date(2024, 9, 19),
        retrieved_at=utcnow(),
        access_method="url_fetch",
        reliability_tier=1,
        url_verified=True,
        content_sha256="b" * 64,
        is_placeholder=False,
    )

    existing_sources = {s.source_id: s.model_copy(update={"is_placeholder": False, "url_verified": True}) for s in clean.sources}
    existing_sources["S1"] = s1
    existing_sources["S2"] = s2

    if clean.research is not None:
        ev1 = Evidence(
            evidence_id="E1",
            source_id="S1",
            kind="quantitative",
            topic="revenue",
            claim="The 2023 main-rate increase from 19% to 25% was forecast to raise receipts substantially.",
            quote="The increase in the main rate of corporation tax from 19 to 25 per cent raises receipts.",
            value=16.25,
            unit="£bn",
            period="2024-25",
            verification_status="verified",
            confidence="high",
        )
        ev2 = Evidence(
            evidence_id="E2",
            source_id="S2",
            kind="quantitative",
            topic="elasticity",
            claim="Empirical taxable profit elasticity estimates for the UK main rate centre around 0.20.",
            quote="The central elasticity of corporate taxable profits with respect to the net-of-tax rate is 0.20.",
            value=0.20,
            unit="elasticity",
            period="2023-24",
            verification_status="verified",
            confidence="medium",
        )
        clean.research.sources = [s1, s2]
        clean.research.evidence = [ev1, ev2]
        clean.research.summary = "Evidence from official releases [E1] and elasticity estimates [E2] informs the assessment."
        clean.research.interpretations = []
        clean.research.parameter_evidence = [
            ParameterEvidence(
                parameter="taxable_profit_elasticity",
                value=0.20,
                low=0.05,
                high=0.50,
                evidence_ids=["E2"],
                note="Consistent with central engine parameter.",
            )
        ]

    if clean.simulation is not None:
        clean.simulation.baseline_vintage = f"OBR EFO {date.today():%B %Y}"
        for assumption in clean.simulation.assumptions:
            assumption.is_placeholder = False
            if not assumption.source_ids:
                assumption.source_ids = ["S1"]
            if assumption.basis == "team_judgement":
                assumption.basis = "literature"

    if clean.precedents is not None:
        for match in clean.precedents.matches:
            match.change.is_placeholder = False
        clean.precedents.sources = [
            s.model_copy(update={"is_placeholder": False, "url_verified": True}) for s in clean.precedents.sources
        ]

    if clean.report is not None:
        # Ensure report prose contains no raw digits outside key figures or policy rates
        clean.report.executive_summary = "Under these assumptions, the proposed change is estimated to affect receipts [S1]."
        clean.report.sections = [
            ReportSection(
                section_id="exec",
                heading="Executive summary",
                body_markdown="Under these assumptions, the policy is estimated to change revenue [S1].",
                source_ids=["S1"],
            )
        ]

    clean.sources = list(existing_sources.values())
    return clean


def evaluate_verifier(analysis: Analysis | None = None) -> VerificationEval:
    """Run the verifier fault-injection suite on the clean golden analysis via agent-5's `run_fault_suite`."""
    with _clean_registry_context():
        target_analysis = analysis if analysis is not None else build_clean_golden_analysis()
        return verification_pkg.run_fault_suite(target_analysis)
