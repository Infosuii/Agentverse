"""Owner: agent-9. STUB: deterministic template report (agent-1 M0). Agent-9 adds key figures and Gemini prose."""
from __future__ import annotations

from ..contracts import Analysis, PolicyAssessment, ReportSection, utcnow


def generate_report(analysis: Analysis) -> PolicyAssessment:
    policy = analysis.policy
    title = f"Assessment: {policy.description or policy.raw_query}" if policy else "Assessment"
    withheld = analysis.verification is None or not analysis.verification.forecast_allowed
    overall = analysis.verification.overall if analysis.verification else "not_verified"
    if withheld:
        reasons = (analysis.verification.decline_reasons if analysis.verification else []) or ["Not verified."]
        summary = "A quantitative forecast is withheld. Reasons: " + "; ".join(reasons)
    else:
        summary = "Placeholder template report (STUB). Modelled figures are available in the Scenarios tab."
    research = analysis.research.summary if analysis.research else "No research was run."
    sections = [
        ReportSection(section_id="policy", heading="Policy assessed",
                      body_markdown=policy.description if policy and policy.description else "Not parsed."),
        ReportSection(section_id="research", heading="Evidence from research", body_markdown=research),
        ReportSection(section_id="limitations", heading="Limitations",
                      body_markdown="This is a stub report built from placeholder data."),
    ]
    caveats = ["Prototype. Not official government analysis.", "STUB report: placeholder data and template text."]
    md = "\n\n".join([f"# {title}", f"## Executive summary\n\n{summary}",
                      *[f"## {s.heading}\n\n{s.body_markdown}" for s in sections],
                      "## Caveats\n\n" + "\n".join(f"- {c}" for c in caveats)]) + "\n"
    return PolicyAssessment(title=title, generated_at=utcnow(), generated_by="template", executive_summary=summary,
                            key_figures=[], sections=sections, caveats=caveats, verification_overall=overall,
                            forecast_withheld=withheld, markdown=md)
