"""Owner: agent-9. `generate_report(analysis) -> PolicyAssessment` (MASTER_PROMPT section 9.8)."""
from __future__ import annotations

from .generator import generate_report
from .narrative import (
    NARRATIVE_HEADER,
    NARRATIVE_SYSTEM_PROMPT,
    NarrativeDraft,
    build_narrative_input,
    generate_narrative_report,
)
from .template import (
    SECTION_ORDER,
    build_template_report,
    compose_full_markdown,
    fmt_date,
    fmt_gbp_bn,
    fmt_pct,
    fmt_pp,
    is_forecast_withheld,
    key_figures,
)

__all__ = [
    "NARRATIVE_HEADER",
    "NARRATIVE_SYSTEM_PROMPT",
    "NarrativeDraft",
    "SECTION_ORDER",
    "build_narrative_input",
    "build_template_report",
    "compose_full_markdown",
    "fmt_date",
    "fmt_gbp_bn",
    "fmt_pct",
    "fmt_pp",
    "generate_narrative_report",
    "generate_report",
    "is_forecast_withheld",
    "key_figures",
]
