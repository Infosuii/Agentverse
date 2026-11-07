"""Small LLM-facing schemas for structured output. Owner: agent-2.

These are deliberately NOT the contracts: they are flat, all fields required (nullable where empty is allowed), so
the constrained-decoding grammar stays small. Code converts them into contract objects and enforces the trust rules.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TopicName = Literal["revenue", "investment", "gdp", "profit_shifting", "elasticity", "macro_context", "policy_history",
                    "distribution", "other"]
KindName = Literal["quantitative", "qualitative", "historical_event", "counter_evidence"]
Level = Literal["high", "medium", "low"]


class ResearchPlan(BaseModel):
    questions: list[str] = Field(description="4 to 7 single-sentence research questions.")


class ExtractedEvidence(BaseModel):
    claim: str = Field(description="One sentence stating what the quote shows.")
    quote: str = Field(description="Copied exactly from the document; one to three consecutive sentences.")
    value: float | None = Field(description="A single number exactly as written in the quote, else null.")
    unit: str | None
    period: str | None
    location: str | None = Field(description="Section, table or page, else null.")
    topic: TopicName
    kind: KindName


class ExtractedEvidenceList(BaseModel):
    items: list[ExtractedEvidence]


class SynthInterpretation(BaseModel):
    statement: str
    evidence_ids: list[str]
    confidence: Level


class SynthConfounder(BaseModel):
    name: str
    description: str
    evidence_ids: list[str]
    likely_direction: Literal["raises_revenue", "lowers_revenue", "ambiguous"]


class SynthParameterEvidence(BaseModel):
    parameter: str = Field(description="One of the listed model parameter names.")
    value: float | None
    low: float | None
    high: float | None
    evidence_ids: list[str]
    note: str


class Synthesis(BaseModel):
    summary: str
    interpretations: list[SynthInterpretation]
    confounders: list[SynthConfounder]
    parameter_evidence: list[SynthParameterEvidence]
    open_questions: list[str]
