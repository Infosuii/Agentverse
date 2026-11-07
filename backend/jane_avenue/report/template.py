"""Deterministic key figures and template policy assessment (MASTER_PROMPT 9.8). Owner: agent-9."""
from __future__ import annotations

from datetime import date

from .. import data
from ..contracts import (
    Analysis,
    CalcStep,
    KeyFigure,
    MetricName,
    MetricProjection,
    PercentileBand,
    PolicyAssessment,
    ReportSection,
    Source,
    utcnow,
)

MINUS = "−"  # Unicode minus (\u2212), matching frontend/src/lib/format.ts

SECTION_ORDER = (
    "executive_summary",
    "policy",
    "research",
    "precedents",
    "modelled_impacts",
    "uncertainty",
    "verification",
    "limitations",
    "references",
)


def compose_full_markdown(title: str, sections: list[ReportSection]) -> str:
    """Compose the full markdown document from title and sections."""
    md_parts = [f"# {title}"]
    for sec in sections:
        md_parts.append(f"## {sec.heading}\n\n{sec.body_markdown}")
    return "\n\n".join(md_parts) + "\n"


def fmt_gbp_bn(value: float, dp: int = 1) -> str:
    """Format £ billions matching frontend fmtGbpBn: fmt_gbp_bn(3.1) -> '£3.1bn', fmt_gbp_bn(-0.4) -> '−£0.4bn'."""
    rounded = round(float(value), dp)
    abs_str = f"{abs(rounded):.{dp}f}"
    if rounded < 0:
        return f"{MINUS}£{abs_str}bn"
    return f"£{abs_str}bn"


def fmt_pct(value: float, dp: int = 2) -> str:
    """Format percentage matching frontend fmtPct: fmt_pct(-0.05, 2) -> '−0.05%'."""
    rounded = round(float(value), dp)
    abs_str = f"{abs(rounded):.{dp}f}"
    if rounded < 0:
        return f"{MINUS}{abs_str}%"
    return f"{abs_str}%"


def fmt_pp(value: float, dp: int | None = None) -> str:
    """Format percentage-point change matching frontend fmtPp: fmt_pp(3) -> '+3pp', fmt_pp(-2) -> '−2pp'."""
    val = float(value)
    if dp is not None:
        rounded = round(val, dp)
        abs_str = f"{abs(rounded):.{dp}f}"
    elif val.is_integer():
        rounded = float(int(round(val)))
        abs_str = str(int(abs(rounded)))
    else:
        rounded = round(val, 2)
        abs_str = f"{abs(rounded):.2f}".rstrip("0").rstrip(".")
    if rounded > 0:
        return f"+{abs_str}pp"
    if rounded < 0:
        return f"{MINUS}{abs_str}pp"
    return f"{abs_str}pp"


def fmt_date(d: date | None) -> str:
    """Format a date into UK short format ('1 Apr 2027')."""
    if d is None:
        return "—"
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{d.day} {months[d.month - 1]} {d.year}"


def is_forecast_withheld(analysis: Analysis) -> bool:
    """Return True when the quantitative forecast must be withheld."""
    if analysis.scope is not None and not analysis.scope.forecast_allowed:
        return True
    if analysis.verification is not None:
        return not analysis.verification.forecast_allowed
    return analysis.simulation is None


def available_source_map(analysis: Analysis) -> dict[str, Source]:
    """Return lookup map of sources, preferring analysis.sources when populated."""
    if analysis.sources:
        return {s.source_id: s for s in analysis.sources}
    seen: dict[str, Source] = {}
    if analysis.research:
        for s in analysis.research.sources:
            seen.setdefault(s.source_id, s)
    if analysis.precedents:
        for s in analysis.precedents.sources:
            seen.setdefault(s.source_id, s)
    for s in data.registry.list_sources():
        seen.setdefault(s.source_id, s)
    return seen


def _filter_source_ids(candidate_ids: list[str], source_map: dict[str, Source]) -> list[str]:
    out: list[str] = []
    for sid in candidate_ids:
        if sid in source_map and sid not in out:
            out.append(sid)
    return out


def _find_metric(metrics: list[MetricProjection], name: MetricName) -> MetricProjection | None:
    for m in metrics:
        if m.metric == name:
            return m
    return None


def _find_band(bands: list[PercentileBand], fiscal_year: str) -> PercentileBand | None:
    for b in bands:
        if b.fiscal_year == fiscal_year:
            return b
    return None


def _trace_for_metric(
    calc_trace: list[CalcStep],
    metric: MetricName,
    fiscal_year: str,
    fallback_source_ids: list[str],
    source_map: dict[str, Source],
) -> tuple[list[str], list[str]]:
    tokens_by_metric: dict[MetricName, tuple[str, ...]] = {
        "revenue_static_gbp_bn": ("static", "base"),
        "revenue_behavioural_gbp_bn": ("behav", "static", "base"),
        "revenue_dynamic_gbp_bn": ("dyn", "behav", "gdp"),
        "business_investment_pct": ("inv", "ucc", "cost"),
        "business_investment_gbp_bn": ("inv", "ucc", "cost"),
        "gdp_level_pct": ("gdp", "cap", "inv"),
        "cost_of_capital_pct": ("ucc", "cost"),
    }
    default_step_prefix: dict[MetricName, str] = {
        "revenue_static_gbp_bn": "rev.static",
        "revenue_behavioural_gbp_bn": "rev.behav",
        "revenue_dynamic_gbp_bn": "rev.dynamic",
        "business_investment_pct": "inv.pct",
        "business_investment_gbp_bn": "inv.gbp",
        "gdp_level_pct": "gdp.pct",
        "cost_of_capital_pct": "ucc.pct",
    }
    tokens = tokens_by_metric.get(metric, ())
    step_ids: list[str] = []
    raw_sources: list[str] = []
    for step in calc_trace:
        fy_match = step.fiscal_year == fiscal_year or step.step_id.endswith(fiscal_year)
        if fy_match and any(tok in step.step_id.lower() for tok in tokens):
            step_ids.append(step.step_id)
            raw_sources.extend(step.source_ids)
    if not step_ids:
        step_ids = [f"{default_step_prefix[metric]}.{fiscal_year}"]
    raw_sources.extend(fallback_source_ids)
    return step_ids, _filter_source_ids(raw_sources, source_map)


def key_figures(analysis: Analysis) -> list[KeyFigure]:
    """Deterministically extract key figures from the central scenario, MC bands, and top precedent."""
    withheld = is_forecast_withheld(analysis)
    source_map = available_source_map(analysis)
    figures: list[KeyFigure] = []

    sim = analysis.simulation
    if not withheld and sim is not None and sim.scenarios:
        central_scen = next((s for s in sim.scenarios if s.scenario.name == "central"), sim.scenarios[0])
        central = central_scen.result
        fys = central.fiscal_years
        y1 = fys[0] if fys else None
        final_fy = fys[-1] if fys else None

        fallback_sources: list[str] = []
        for a in sim.assumptions:
            fallback_sources.extend(a.source_ids)
        for step in central.calc_trace:
            fallback_sources.extend(step.source_ids)
        if not fallback_sources and source_map:
            fallback_sources.extend(list(source_map.keys())[:2])

        rev_behav = _find_metric(central.metrics, "revenue_behavioural_gbp_bn")
        if rev_behav and rev_behav.values and y1 and final_fy:
            y1_val = rev_behav.values[0].value
            step_ids_y1, src_y1 = _trace_for_metric(
                central.calc_trace, "revenue_behavioural_gbp_bn", y1, fallback_sources, source_map
            )
            figures.append(
                KeyFigure(
                    figure_id="rev_behav_central_y1",
                    label=f"Central behavioural revenue ({y1})",
                    value=y1_val,
                    unit="£bn",
                    display=fmt_gbp_bn(y1_val),
                    evidence_class="model_scenario",
                    metric="revenue_behavioural_gbp_bn",
                    scenario="central",
                    fiscal_year=y1,
                    calc_step_ids=step_ids_y1,
                    source_ids=src_y1,
                )
            )

            final_val = rev_behav.values[-1].value
            step_ids_fin, src_fin = _trace_for_metric(
                central.calc_trace, "revenue_behavioural_gbp_bn", final_fy, fallback_sources, source_map
            )
            figures.append(
                KeyFigure(
                    figure_id="rev_behav_central_final",
                    label=f"Central behavioural revenue ({final_fy})",
                    value=final_val,
                    unit="£bn",
                    display=fmt_gbp_bn(final_val),
                    evidence_class="model_scenario",
                    metric="revenue_behavioural_gbp_bn",
                    scenario="central",
                    fiscal_year=final_fy,
                    calc_step_ids=step_ids_fin,
                    source_ids=src_fin,
                )
            )

        rev_static = _find_metric(central.metrics, "revenue_static_gbp_bn")
        if rev_static and rev_static.values and final_fy:
            st_val = rev_static.values[-1].value
            step_ids_st, src_st = _trace_for_metric(
                central.calc_trace, "revenue_static_gbp_bn", final_fy, fallback_sources, source_map
            )
            figures.append(
                KeyFigure(
                    figure_id="rev_static_central_final",
                    label=f"Central static revenue ({final_fy})",
                    value=st_val,
                    unit="£bn",
                    display=fmt_gbp_bn(st_val),
                    evidence_class="model_scenario",
                    metric="revenue_static_gbp_bn",
                    scenario="central",
                    fiscal_year=final_fy,
                    calc_step_ids=step_ids_st,
                    source_ids=src_st,
                )
            )

        inv_pct = _find_metric(central.metrics, "business_investment_pct")
        if inv_pct and inv_pct.values and final_fy:
            inv_val = inv_pct.values[-1].value
            step_ids_inv, src_inv = _trace_for_metric(
                central.calc_trace, "business_investment_pct", final_fy, fallback_sources, source_map
            )
            figures.append(
                KeyFigure(
                    figure_id="inv_pct_central_final",
                    label=f"Business investment change ({final_fy})",
                    value=inv_val,
                    unit="%",
                    display=fmt_pct(inv_val),
                    evidence_class="model_scenario",
                    metric="business_investment_pct",
                    scenario="central",
                    fiscal_year=final_fy,
                    calc_step_ids=step_ids_inv,
                    source_ids=src_inv,
                )
            )

        gdp_pct = _find_metric(central.metrics, "gdp_level_pct")
        if gdp_pct and gdp_pct.values and final_fy:
            gdp_val = gdp_pct.values[-1].value
            step_ids_gdp, src_gdp = _trace_for_metric(
                central.calc_trace, "gdp_level_pct", final_fy, fallback_sources, source_map
            )
            figures.append(
                KeyFigure(
                    figure_id="gdp_pct_central_final",
                    label=f"GDP level change ({final_fy})",
                    value=gdp_val,
                    unit="%",
                    display=fmt_pct(gdp_val),
                    evidence_class="model_scenario",
                    metric="gdp_level_pct",
                    scenario="central",
                    fiscal_year=final_fy,
                    calc_step_ids=step_ids_gdp,
                    source_ids=src_gdp,
                )
            )

        if sim.monte_carlo and final_fy:
            mc_dist = next(
                (d for d in sim.monte_carlo.distributions if d.metric == "revenue_behavioural_gbp_bn"),
                None,
            )
            band_final = _find_band(mc_dist.bands, final_fy) if mc_dist else None
            if band_final is not None:
                step_ids_mc, src_mc = _trace_for_metric(
                    central.calc_trace, "revenue_behavioural_gbp_bn", final_fy, fallback_sources, source_map
                )
                figures.append(
                    KeyFigure(
                        figure_id="rev_behav_p5_final",
                        label=f"Behavioural revenue p5 ({final_fy})",
                        value=band_final.p5,
                        unit="£bn",
                        display=fmt_gbp_bn(band_final.p5),
                        evidence_class="model_scenario",
                        metric="revenue_behavioural_gbp_bn",
                        scenario="central",
                        fiscal_year=final_fy,
                        calc_step_ids=step_ids_mc,
                        source_ids=src_mc,
                    )
                )
                figures.append(
                    KeyFigure(
                        figure_id="rev_behav_p95_final",
                        label=f"Behavioural revenue p95 ({final_fy})",
                        value=band_final.p95,
                        unit="£bn",
                        display=fmt_gbp_bn(band_final.p95),
                        evidence_class="model_scenario",
                        metric="revenue_behavioural_gbp_bn",
                        scenario="central",
                        fiscal_year=final_fy,
                        calc_step_ids=step_ids_mc,
                        source_ids=src_mc,
                    )
                )

    if analysis.precedents and analysis.precedents.matches:
        top_change = analysis.precedents.matches[0].change
        if top_change.official_costings:
            costing = top_change.official_costings[0]
            costing_sources = _filter_source_ids([costing.source_id], source_map) or _filter_source_ids(
                top_change.source_ids, source_map
            )
            figures.append(
                KeyFigure(
                    figure_id="top_precedent_official_costing",
                    label=f"Official costing ({top_change.change_id}, {costing.fiscal_year})",
                    value=costing.value_gbp_bn,
                    unit="£bn",
                    display=fmt_gbp_bn(costing.value_gbp_bn),
                    evidence_class="official_costing",
                    fiscal_year=costing.fiscal_year,
                    calc_step_ids=[],
                    source_ids=costing_sources,
                )
            )

    return figures


def _format_references_section(
    ordered_source_ids: list[str],
    source_map: dict[str, Source],
) -> tuple[str, list[str]]:
    valid_ids = _filter_source_ids(ordered_source_ids, source_map)
    if not valid_ids and source_map:
        valid_ids = list(source_map.keys())
    if not valid_ids:
        return "No external or curated sources were cited in this assessment.", []

    lines: list[str] = []
    for idx, sid in enumerate(valid_ids, start=1):
        src = source_map[sid]
        accessed = (
            f" (accessed {src.retrieved_at.strftime('%Y-%m-%d')})"
            if src.retrieved_at is not None
            else ""
        )
        lines.append(f"{idx}. **[{src.source_id}]** {src.title} — *{src.publisher}*. <{src.url}>{accessed}")
    return "\n".join(lines), valid_ids


def build_template_report(
    analysis: Analysis,
    figures: list[KeyFigure] | None = None,
) -> PolicyAssessment:
    """Build a complete, deterministic 9-section policy assessment."""
    figs = key_figures(analysis) if figures is None else figures
    fig_map = {f.figure_id: f for f in figs}
    source_map = available_source_map(analysis)
    withheld = is_forecast_withheld(analysis)
    policy = analysis.policy
    overall = analysis.verification.overall if analysis.verification else "not_verified"

    title_desc = (
        policy.description or policy.raw_query
        if policy and (policy.description or policy.raw_query)
        else analysis.request.query
    )
    title = f"Policy Assessment: {title_desc}"

    decline_reasons: list[str] = []
    if analysis.verification and analysis.verification.decline_reasons:
        decline_reasons.extend(analysis.verification.decline_reasons)
    if analysis.scope and not analysis.scope.forecast_allowed:
        for r in analysis.scope.reasons:
            if r not in decline_reasons:
                decline_reasons.append(r)
    if withheld and not decline_reasons:
        decline_reasons.append("Quantitative forecast withheld due to scope or verification constraints.")

    cited_source_ids: list[str] = []

    def remember_sources(sids: list[str]) -> list[str]:
        valid = _filter_source_ids(sids, source_map)
        for sid in valid:
            if sid not in cited_source_ids:
                cited_source_ids.append(sid)
        return valid

    # 1. Executive summary
    f_y1 = fig_map.get("rev_behav_central_y1")
    f_fin = fig_map.get("rev_behav_central_final")
    f_p5 = fig_map.get("rev_behav_p5_final")
    f_p95 = fig_map.get("rev_behav_p95_final")
    f_inv = fig_map.get("inv_pct_central_final")
    f_gdp = fig_map.get("gdp_pct_central_final")
    f_st = fig_map.get("rev_static_central_final")
    f_cost = fig_map.get("top_precedent_official_costing")

    exec_fig_ids: list[str] = []
    exec_src_ids: list[str] = []
    if withheld:
        reasons_str = "; ".join(decline_reasons)
        executive_summary = (
            f"Quantitative model projections are withheld for this request ({reasons_str}). "
            "Empirical evidence from research and historical UK corporation tax precedents are summarised below."
        )
        exec_section_body = executive_summary
    elif f_y1 and f_fin:
        exec_fig_ids.extend([f_y1.figure_id, f_fin.figure_id])
        exec_src_ids.extend(f_y1.source_ids + f_fin.source_ids)
        if f_p5 and f_p95:
            exec_fig_ids.extend([f_p5.figure_id, f_p95.figure_id])
        inv_gdp_clause = ""
        if f_inv and f_gdp:
            exec_fig_ids.extend([f_inv.figure_id, f_gdp.figure_id])
            inv_gdp_clause = (
                f" Under these assumptions, business investment is estimated to change by {f_inv.display} "
                f"and indicative GDP level by {f_gdp.display} in {f_fin.fiscal_year}."
            )
        executive_summary = (
            f"Under the central scenario assumptions, the proposed policy is estimated to change Exchequer "
            f"corporation tax revenue (behavioural) by {f_y1.display} in {f_y1.fiscal_year} and by "
            f"{f_fin.display} in {f_fin.fiscal_year} (with p5–p95 Monte Carlo bands reported in key figures)."
            f"{inv_gdp_clause}"
        )
        exec_section_body = executive_summary
    else:
        executive_summary = "Policy assessment generated under deterministic template rules."
        exec_section_body = executive_summary

    exec_section = ReportSection(
        section_id="executive_summary",
        heading="Executive summary",
        body_markdown=exec_section_body,
        source_ids=remember_sources(exec_src_ids),
        figure_ids=exec_fig_ids,
    )

    # 2. Policy assessed
    if policy:
        rate_str = (
            f"from {policy.baseline_rate_pct:g}% to {policy.proposed_rate_pct:g}% "
            f"({fmt_pp(policy.change_pp() or 0.0)})"
            if policy.baseline_rate_pct is not None and policy.proposed_rate_pct is not None
            else "unspecified rate change"
        )
        amb_text = (
            "\n\n**Parser assumptions and ambiguities:**\n" + "\n".join(f"- {a}" for a in policy.ambiguities)
            if policy.ambiguities
            else ""
        )
        scope_text = ""
        if analysis.scope:
            scope_notes = analysis.scope.reasons + analysis.scope.warnings
            notes_line = f" ({'; '.join(scope_notes)})" if scope_notes else ""
            scope_text = f"\n- **Scope status:** `{analysis.scope.status}`{notes_line}"
        policy_body = (
            f"- **Description:** {policy.description or policy.raw_query}\n"
            f"- **Policy type:** `{policy.policy_type}`\n"
            f"- **Rate adjustment:** {rate_str}\n"
            f"- **Effective date:** {fmt_date(policy.effective_date)}\n"
            f"- **Horizon:** {policy.horizon_years} fiscal years"
            f"{scope_text}{amb_text}"
        )
    else:
        policy_body = f"Raw query: {analysis.request.query}"

    policy_section = ReportSection(
        section_id="policy",
        heading="Policy assessed",
        body_markdown=policy_body,
        source_ids=[],
        figure_ids=[],
    )

    # 3. Evidence from research
    research_src_ids: list[str] = []
    if analysis.research:
        r_lines = [analysis.research.summary]
        for ev in analysis.research.evidence:
            sid = ev.source_id
            cite = f"[{sid}]" if sid in source_map else ""
            if sid in source_map:
                research_src_ids.append(sid)
            val_part = f" ({ev.value:g} {ev.unit or ''})".rstrip() if ev.value is not None else ""
            quote_part = f' — *"{ev.quote}"*' if ev.quote else ""
            r_lines.append(f"- **[{ev.evidence_id}]** {ev.claim}{val_part} {cite}{quote_part}".strip())
        for interp in analysis.research.interpretations:
            ev_refs = ", ".join(f"[{eid}]" for eid in interp.supporting_evidence_ids)
            r_lines.append(
                f"- **[AI interpretation · {interp.interpretation_id}]** {interp.statement}"
                + (f" (supported by {ev_refs})" if ev_refs else "")
            )
        research_body = "\n".join(r_lines)
    else:
        research_body = "Live literature and official-document research was skipped or unavailable for this run."

    research_section = ReportSection(
        section_id="research",
        heading="Evidence from research",
        body_markdown=research_body,
        source_ids=remember_sources(research_src_ids),
        figure_ids=[],
    )

    # 4. Historical precedents
    prec_src_ids: list[str] = []
    prec_fig_ids: list[str] = []
    if analysis.precedents and analysis.precedents.matches:
        p_lines = [
            "Historical UK corporation tax changes ranked by direction, magnitude, starting rate level, "
            "macroeconomic context, and recency (official costings and observed outcomes are distinct evidence; "
            "similarity does not establish causation):"
        ]
        for m in analysis.precedents.matches:
            c = m.change
            valid_c_srcs = _filter_source_ids(c.source_ids, source_map)
            prec_src_ids.extend(valid_c_srcs)
            cite_str = " ".join(f"[{sid}]" for sid in valid_c_srcs)
            delta_pp = fmt_pp(c.new_rate_pct - c.old_rate_pct)
            notes_str = f" — Confounders: {'; '.join(m.comparability_notes)}" if m.comparability_notes else ""
            p_lines.append(
                f"- **{c.change_id}** ({c.effective_date.year}, {c.old_rate_pct:g}% → {c.new_rate_pct:g}%, "
                f"{delta_pp}): {c.fiscal_event or 'UK Corporation Tax reform'} {cite_str}{notes_str}".strip()
            )
        if f_cost:
            prec_fig_ids.append(f_cost.figure_id)
            prec_src_ids.extend(f_cost.source_ids)
            p_lines.append(
                f"\nTop precedent official ex-ante costing (`official_costing`): **{f_cost.display}** "
                f"in {f_cost.fiscal_year}."
            )
        prec_body = "\n".join(p_lines)
    else:
        prec_body = "No matching historical UK corporation tax precedents were identified. No causal conclusion is drawn."

    precedents_section = ReportSection(
        section_id="precedents",
        heading="Historical precedents",
        body_markdown=prec_body,
        source_ids=remember_sources(prec_src_ids),
        figure_ids=prec_fig_ids,
    )

    # 5. Modelled impacts (with scenario table)
    model_fig_ids: list[str] = []
    model_src_ids: list[str] = []
    if withheld:
        reasons_bullets = "\n".join(f"- {r}" for r in decline_reasons)
        model_body = (
            "**Quantitative forecast withheld.** Jane Avenue does not produce model projections when a policy "
            "falls outside validated bounds or fails a blocking verification check.\n\n"
            f"**Reasons for withholding:**\n{reasons_bullets}"
        )
    elif f_y1 and f_fin:
        table_rows: list[str] = [
            "| Metric | Horizon / Scenario | Evidence class | Estimate |",
            "| --- | --- | --- | --- |",
            f"| Behavioural revenue change | {f_y1.fiscal_year} (Central) | `model_scenario` | {f_y1.display} |",
            f"| Behavioural revenue change | {f_fin.fiscal_year} (Central) | `model_scenario` | {f_fin.display} |",
        ]
        model_fig_ids.extend([f_y1.figure_id, f_fin.figure_id])
        model_src_ids.extend(f_y1.source_ids + f_fin.source_ids)
        if f_st:
            table_rows.append(
                f"| Static revenue change | {f_st.fiscal_year} (Central) | `model_scenario` | {f_st.display} |"
            )
            model_fig_ids.append(f_st.figure_id)
            model_src_ids.extend(f_st.source_ids)
        if f_p5 and f_p95:
            model_fig_ids.extend([f_p5.figure_id, f_p95.figure_id])
        if f_inv:
            table_rows.append(
                f"| Business investment change | {f_inv.fiscal_year} (Central) | `model_scenario` | {f_inv.display} |"
            )
            model_fig_ids.append(f_inv.figure_id)
            model_src_ids.extend(f_inv.source_ids)
        if f_gdp:
            table_rows.append(
                f"| GDP level change (indicative) | {f_gdp.fiscal_year} (Central) | `model_scenario` | {f_gdp.display} |"
            )
            model_fig_ids.append(f_gdp.figure_id)
            model_src_ids.extend(f_gdp.source_ids)

        model_body = (
            "Under the central econometric specification, static revenue changes are adjusted for taxable-profit "
            "elasticity and user-cost-of-capital investment channels:\n\n" + "\n".join(table_rows)
        )
    else:
        model_body = "No econometric simulation output was generated for this analysis."

    model_section = ReportSection(
        section_id="modelled_impacts",
        heading="Modelled impacts",
        body_markdown=model_body,
        source_ids=remember_sources(model_src_ids),
        figure_ids=model_fig_ids,
    )

    # 6. Uncertainty and sensitivity (top 3 tornado drivers)
    unc_fig_ids: list[str] = []
    unc_src_ids: list[str] = []
    if withheld:
        unc_body = (
            "Monte Carlo uncertainty bands and parameter sensitivity rankings are omitted because the "
            "quantitative forecast is withheld."
        )
    else:
        mc = analysis.simulation.monte_carlo if analysis.simulation else None
        draws_clause = f" across {mc.n_draws} Monte Carlo parameter draws" if mc else ""
        note = (
            f"assumption-driven ranges{draws_clause}, not statistical prediction intervals; "
            "they exclude model and data uncertainty"
        )
        unc_lines: list[str] = []
        if f_p5 and f_p95:
            unc_fig_ids.extend([f_p5.figure_id, f_p95.figure_id])
            unc_src_ids.extend(f_p5.source_ids + f_p95.source_ids)
            unc_lines.append(
                f"In {f_p5.fiscal_year}, the Monte Carlo p5–p95 range for behavioural revenue reflects "
                f"{note} (reported in the key figures strip)."
            )
        else:
            unc_lines.append(f"Uncertainty bands represent {note}.")

        tornado_items = []
        if analysis.simulation and analysis.simulation.sensitivity:
            rev_sens = next(
                (s for s in analysis.simulation.sensitivity if s.metric == "revenue_behavioural_gbp_bn"),
                analysis.simulation.sensitivity[0],
            )
            tornado_items = rev_sens.items[:3]

        if tornado_items:
            unc_lines.append("\n**Top sensitivity drivers (tornado analysis):**")
            for item in tornado_items:
                unc_lines.append(f"- **{item.label}** (`{item.parameter}`)")
        elif analysis.simulation and analysis.simulation.assumptions:
            adjustable = [a for a in analysis.simulation.assumptions if a.adjustable][:3]
            if adjustable:
                unc_lines.append("\n**Primary uncertain parameters:**")
                for a in adjustable:
                    unc_lines.append(f"- **{a.label}** (`{a.name}`)")
                    unc_src_ids.extend(a.source_ids)

        unc_body = "\n".join(unc_lines)

    uncertainty_section = ReportSection(
        section_id="uncertainty",
        heading="Uncertainty and sensitivity",
        body_markdown=unc_body,
        source_ids=remember_sources(unc_src_ids),
        figure_ids=unc_fig_ids,
    )

    # 7. Verification findings
    if analysis.verification:
        v = analysis.verification
        v_lines = [
            f"- **Overall status:** `{v.overall}`",
            f"- **Forecast gate:** `{'forecast_allowed' if v.forecast_allowed else 'forecast_withheld'}`",
        ]
        if v.decline_reasons:
            v_lines.append("- **Decline reasons:** " + "; ".join(v.decline_reasons))
        flagged = [c for c in v.checks if c.status in ("fail", "warn")]
        if flagged:
            v_lines.append("\n**Flagged checks:**")
            for chk in flagged:
                title_clean = chk.title.replace("5-year", "five-year")
                v_lines.append(f"- **{chk.check_id}** (`{chk.status}`, {chk.severity}): {title_clean}")
        verif_body = "\n".join(v_lines)
    else:
        verif_body = "Independent verification has not yet run on this analysis."

    verification_section = ReportSection(
        section_id="verification",
        heading="Verification findings",
        body_markdown=verif_body,
        source_ids=[],
        figure_ids=[],
    )

    # 8. Limitations and caveats
    caveats: list[str] = [
        "Prototype. Not official government analysis.",
        "Projections are conditional on the OBR baseline forecast and explicit model assumptions; they are not unconditional macroeconomic predictions.",
        "GDP and dynamic revenue estimates rely on a partial-equilibrium user-cost-of-capital channel with fixed labour supply and carry low confidence.",
        "Historical UK corporation tax changes frequently coincided with base-broadening or capital-allowance reforms (such as full expensing), which confound simple outturn comparisons.",
    ]
    if analysis.scope and analysis.scope.warnings:
        for w in analysis.scope.warnings:
            if w not in caveats:
                caveats.append(w)

    limitations_body = "\n".join(f"- {c}" for c in caveats)
    limitations_section = ReportSection(
        section_id="limitations",
        heading="Limitations and caveats",
        body_markdown=limitations_body,
        source_ids=[],
        figure_ids=[],
    )

    # 9. References
    refs_body, ref_source_ids = _format_references_section(cited_source_ids, source_map)
    references_section = ReportSection(
        section_id="references",
        heading="References",
        body_markdown=refs_body,
        source_ids=ref_source_ids,
        figure_ids=[],
    )

    sections = [
        exec_section,
        policy_section,
        research_section,
        precedents_section,
        model_section,
        uncertainty_section,
        verification_section,
        limitations_section,
        references_section,
    ]

    md_parts = [f"# {title}"]
    for sec in sections:
        md_parts.append(f"## {sec.heading}\n\n{sec.body_markdown}")
    markdown = "\n\n".join(md_parts) + "\n"

    return PolicyAssessment(
        title=title,
        generated_at=utcnow(),
        generated_by="template",
        model=None,
        executive_summary=executive_summary,
        key_figures=figs,
        sections=sections,
        caveats=caveats,
        verification_overall=overall,
        forecast_withheld=withheld,
        markdown=markdown,
    )
