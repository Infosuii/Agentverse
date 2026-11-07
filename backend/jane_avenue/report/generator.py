"""Report generation entrypoint (MASTER_PROMPT 9.8 & Appendix B). Owner: agent-9."""
from __future__ import annotations

from ..contracts import Analysis, PolicyAssessment
from .template import build_template_report, key_figures


def generate_report(analysis: Analysis) -> PolicyAssessment:
    """Generate the evidence-backed PolicyAssessment for an analysis."""
    figures = key_figures(analysis)
    return build_template_report(analysis, figures)


__all__ = ["generate_report", "key_figures"]
