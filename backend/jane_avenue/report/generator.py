"""Report generator entrypoint (MASTER_PROMPT section 9.8). Owner: agent-9.

`generate_report(analysis) -> PolicyAssessment`
- Attempts `generate_narrative_report(analysis)` (which uses `get_llm()` and falls back to `build_template_report`
  on `LLMUnavailable`, withheld forecasts, or after one retry on `REPORT-001` / `CAUSAL-001` / placeholder failure).
"""
from __future__ import annotations

from ..contracts import Analysis, PolicyAssessment
from ..llm import LLMClient
from .narrative import generate_narrative_report
from .template import build_template_report, key_figures

__all__ = ["build_template_report", "generate_narrative_report", "generate_report", "key_figures"]


def generate_report(analysis: Analysis, *, llm_client: LLMClient | None = None) -> PolicyAssessment:
    """Produce a 9-section PolicyAssessment with deterministic key_figures and full markdown."""
    return generate_narrative_report(analysis, llm_client=llm_client)
