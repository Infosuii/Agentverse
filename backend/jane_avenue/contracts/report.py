from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .common import Contract, EvidenceClass
from .model import MetricName
from .simulation import ScenarioName


class KeyFigure(Contract):
    figure_id: str
    label: str
    value: float
    unit: str
    display: str                        # "£3.1bn"
    evidence_class: EvidenceClass
    metric: MetricName | None = None
    scenario: ScenarioName | None = None
    fiscal_year: str | None = None
    calc_step_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class ReportSection(Contract):
    section_id: str
    heading: str
    body_markdown: str
    source_ids: list[str] = Field(default_factory=list)
    figure_ids: list[str] = Field(default_factory=list)


class PolicyAssessment(Contract):
    title: str
    generated_at: datetime
    generated_by: Literal["gemini", "template"]
    model: str | None = None
    executive_summary: str
    key_figures: list[KeyFigure]
    sections: list[ReportSection]
    caveats: list[str]
    verification_overall: str
    forecast_withheld: bool
    markdown: str
