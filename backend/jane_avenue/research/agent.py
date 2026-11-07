"""Owner: agent-2. STUB: deterministic mock research (agent-1 M0). Agent-2 replaces this with the Gemini tool loop.

Everything here is a clearly labelled placeholder: `is_placeholder` sources, `unverified` evidence, `mode="mock"`.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from ..contracts import Evidence, PolicySpec, ResearchFindings, ResearchStep, Source, utcnow

_STUB_STEPS: tuple[tuple[str, str, str], ...] = (
    ("plan", "Plan research questions", "Mock plan: revenue effects, behavioural response, investment, confounders."),
    ("search", "Search official sources", "Mock search (no network in mock mode)."),
    ("fetch", "Fetch documents", "Mock fetch of placeholder OBR and IFS home pages."),
    ("extract", "Extract evidence", "Mock evidence items, unverified."),
    ("synthesis", "Synthesise findings", "Mock summary; no numbers are produced here."),
)


def _sources() -> list[Source]:
    now = utcnow()
    return [
        Source(source_id="S1", title="Office for Budget Responsibility (placeholder)", url="https://obr.uk/",
               publisher="Office for Budget Responsibility", publisher_type="obr", retrieved_at=now,
               access_method="fixture", reliability_tier=1, is_placeholder=True),
        Source(source_id="S2", title="Institute for Fiscal Studies (placeholder)", url="https://ifs.org.uk/",
               publisher="Institute for Fiscal Studies", publisher_type="ifs", retrieved_at=now,
               access_method="fixture", reliability_tier=2, is_placeholder=True),
    ]


def _evidence() -> list[Evidence]:
    return [
        Evidence(evidence_id="E1", source_id="S1", kind="qualitative", topic="revenue",
                 claim="Placeholder: official costings of CT rate changes include behavioural responses.",
                 verification_status="unverified", confidence="low"),
        Evidence(evidence_id="E2", source_id="S2", kind="qualitative", topic="elasticity",
                 claim="Placeholder: taxable profits respond to the CT rate.",
                 verification_status="unverified", confidence="low"),
    ]


def run_research(
    spec: PolicySpec, *, on_step: Callable[[ResearchStep], None] | None = None, use_cache: bool = True
) -> ResearchFindings:
    started = utcnow()
    trace: list[ResearchStep] = []
    for i, (kind, title, detail) in enumerate(_STUB_STEPS, start=1):
        step = ResearchStep(step_id=i, ts=utcnow(), kind=kind, title=title, detail=detail,  # type: ignore[arg-type]
                            source_ids=["S1", "S2"] if kind in ("fetch", "extract") else [],
                            evidence_ids=["E1", "E2"] if kind == "extract" else [])
        trace.append(step)
        if on_step is not None:
            on_step(step)
        time.sleep(0.05)
    return ResearchFindings(
        policy=spec,
        mode="mock",
        model=None,
        summary="Placeholder research summary (mock mode). See evidence E1 and E2.",
        research_questions=[
            "What were the revenue effects of past UK CT main-rate changes?",
            "What behavioural assumptions do OBR and HMRC use in costings?",
            "How elastic are taxable profits to the CT rate?",
            "How does the CT rate affect investment through the cost of capital?",
        ],
        sources=_sources(),
        evidence=_evidence(),
        trace=trace,
        started_at=started,
        completed_at=utcnow(),
    )
