# agent-9 · Precedents view, verification view, policy assessment report (Antigravity)

> Paste this whole file into a fresh **Antigravity** agent session opened on a clone of `Infosuii/Agentverse`. Use Antigravity's browser to check your pages against the running app.

You are **agent-9** in an eleven-agent build of **Jane Avenue**, an AI-powered UK fiscal policy simulator, on `Infosuii/Agentverse`. You are agent-9 and no other agent.

## 0. Start-up (every session)

1. **Identity.** Commit with `git -c user.name=agent-9`. Use the `gh` CLI for all GitHub actions.
2. **Read:**
   - `AGENTS.md`
   - `.agents/PROTOCOL.md`
   - `PROJECT.md`
   - `docs/MASTER_PROMPT.md`: sections 1–8, 9.4, 9.7, **9.8**, **9.10**, 10–12, and Appendices A and B.
   - Before writing any Gemini call, read the Gemini docs listed in rule 12 of `docs/MASTER_PROMPT.md`. Call Gemini only through agent-2's `llm/` module.
3. **Sync:** run `git fetch --all --prune`, then read:
   - your inbox, Issue #17
   - the coordination Issue, #8
   - the contracts Issue, #20
   - the open PRs
4. **Create your task Issues** if they do not exist yet:
   ```
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-9][M1] Precedents tab, verification tab, template report + report tab" --label agent-9 --label M1 --label status:in-progress --body "Brief: docs/prompts/agent-09-precedents-verification-report.md (M1)."
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-9][M2] Gemini narrative report, citations, print/PDF, precedent charts" --label agent-9 --label M2 --label status:todo --body "Brief: docs/prompts/agent-09-precedents-verification-report.md (M2)."
   ```
   Then comment `CLAIM: agent-9` on the M1 Issue.
5. **Branch:** work on `agents/agent-9-issue-<n>`. Check GitHub every 3–5 minutes.

## 1. Mission

You own three analyst-facing deliverables:

1. **Historical precedents.** How similar past UK changes played out, with official costings and observed outcomes clearly separated.
2. **The verification panel.** What the independent verifier found, and why a forecast might be withheld.
3. **The evidence-backed policy assessment.** This is both the backend generator and the report page. Gemini writes the prose, but code inserts every number.

## 2. You own

- `backend/jane_avenue/report/` and `backend/tests/report/`
- `frontend/src/features/precedents/`
- `frontend/src/features/verification/`
- `frontend/src/features/report/`

## 3. Interfaces

**You provide:** `report.generate_report(analysis) -> PolicyAssessment` (Appendix B) and `report.key_figures(analysis) -> list[KeyFigure]`.

**You consume:**

| Agent | What you use |
|---|---|
| agent-2 | `llm.get_llm()`, `generate_structured`, `LLMUnavailable` |
| agent-5 | `verification.check_report(report, analysis)` to validate drafts (REPORT-001) |
| agent-6 | `PrecedentAnalysis` |
| agent-7 | UI primitives and hooks |
| agent-8 | Chart wrappers (`TimelineChart`, `BarCompare`) and `ProvenanceNumber` |

## 4. M1 (by about T0 + 5 h)

1. **Report backend, template path** (`report/generator.py`, `report/template.py`):
   - **`key_figures`** is deterministic. It produces:
     - central `revenue_behavioural_gbp_bn` for year 1 and the final year
     - central `revenue_static_gbp_bn` for the final year
     - `business_investment_pct` for the final year
     - `gdp_level_pct` for the final year
     - the Monte Carlo p5–p95 range for behavioural revenue in the final year, as two figures
     - the top precedent's official costing, if one exists (`evidence_class="official_costing"`)

     Each figure carries `display` (use the same formatting rules as the frontend `format.ts`), `calc_step_ids` and `source_ids`. Figure IDs are stable: `rev_behav_central_y1`, `rev_behav_central_final`, `rev_behav_p5_final`, `rev_behav_p95_final`, and so on.
   - **The template** produces a complete, readable assessment with these sections:
     1. Executive summary
     2. Policy assessed
     3. Evidence from research (with `[S#]` citations)
     4. Historical precedents
     5. Modelled impacts (with a scenario table)
     6. Uncertainty and sensitivity (top 3 tornado drivers)
     7. Verification findings
     8. Limitations and caveats
     9. References (numbered; title, publisher, URL)
   - **If the forecast is withheld,** omit model figures, explain the decline reasons, and keep the research and precedents sections.
   - **`markdown`** holds the full document.
   - **Tests:**
     - every figure equals the engine value
     - the withheld path has no model figures
     - every reference resolves to `analysis.sources`
2. **Precedents tab:**
   - A `TimelineChart` of the CT main rate from 1982 to today, built from `usePrecedents()`. Mark each change on it and highlight the matched ones.
   - Ranked precedent cards from `analysis.precedents.matches`. Each card shows:
     - the change (old → new, effective date, fiscal event)
     - a similarity bar with a breakdown tooltip
     - comparability notes, which are confounders, shown as amber chips
     - a macro context mini-table
   - The summary text.
   - Placeholder flags shown wherever `is_placeholder` is set.
3. **Verification tab:**
   - An overall status card (approved, approved_with_warnings, or forecast_withheld), plus counts by status and the summary.
   - Decline reasons, prominent when present.
   - Checks grouped by category. Each check shows a severity or status icon, the title, the detail, the method (rule, recompute, source_fetch or llm_critic) and its `affected_ids`, which link to the evidence (research tab), assumption (assumptions tab) or metric (scenarios tab).
   - Filters: failed or warn only, and by category.
   - The critic model, when present.
4. **Report tab:**
   - Render `analysis.report.markdown` with `react-markdown` and `remark-gfm`.
   - Show a key-figures strip above the report, using `ProvenanceNumber` and evidence badges.
   - Add a "Download .md" button linked to `/api/analyses/{id}/report.md`.
   - Add a "Print / Save as PDF" button that calls `window.print()`, with print CSS: A4, margins, hidden navigation, page breaks before headings.
   - Show `generated_by` (gemini or template) and the verification status.

## 5. M2 (by about T0 + 14 h)

1. **Gemini narrative** (`report/narrative.py`), live mode only:
   - **Input.** Build an LLM-facing JSON that contains no raw model numbers:
     - the policy description
     - the research summary and evidence claims (with IDs)
     - precedent summaries
     - figures as `{figure_id, label, direction: "increase"|"decrease"|"none", magnitude_class: "small"|"moderate"|"large", evidence_class}`
     - top tornado drivers by label
     - the verification overall result and its warnings
     - the scope warnings
   - **Prompt.** `generate_structured` takes a `NarrativeDraft` schema with one markdown body per section. The system instruction says:
     - write for a government analyst, in neutral and cautious language
     - state every quantity only as `{{fig:<figure_id>}}`
     - cite sources only as `[S#]` or `[D-…]` using the provided IDs
     - do not introduce any other number, date or source
     - use "is estimated to" and "under these assumptions", never "will cause"
     - mark interpretations as such
   - **Substitution.** Replace each `{{fig:id}}` with `KeyFigure.display`. An unknown ID counts as a failure. Turn each `[S#]` into a numbered footnote reference.
   - **Validation.** Call agent-5's `check_report`.
     - If REPORT-001 or CAUSAL-001 fails, retry once with the offending snippets quoted in the prompt.
     - If it fails again, use the template.
     - Set `generated_by` to `gemini` or `template`, and set `model` when Gemini was used.
   - **Tests.** With `MockLLM`, cover:
     - substitution
     - an unknown placeholder rejected
     - raw digits rejected, then the fallback used
     - citations resolved
2. **Precedent charts:**
   - A `BarCompare` per matched change showing official costing (violet), observed change in receipts (slate) and our model scenario for an equivalent change (blue, optional). The legend must explain the differences: ex-ante versus outturn versus model, and confounding.
   - Receipts as a percentage of GDP around each change, from t−1 to t+2.
3. **Report polish:**
   - An executive summary box.
   - A scenario table.
   - Figure provenance links that deep-link into agent-8's calculation inspector (`?metric=&year=`).
   - A references list with the access date.

## 6. Decisions already made

- The template report must be good enough to demo on its own. Gemini is an enhancement, never a dependency.
- Observed outcome, official costing and model scenario never share a colour or a label (`theme.ts` evidence classes).

## 7. Coordination

- **Your reviewer** is agent-7. You review agent-8's PRs.
- **Agent-5:** agree the REPORT-001 whitelist rules early (inbox #5), for example that fiscal-year labels like "2027-28", policy rates and section numbers are allowed.
- **Agent-6:** agree the costing and outcome fields you display (inbox #6).

## 8. Done means

- The precedents, verification and report tabs are complete.
- The template report is solid, the Gemini narrative is safe, and no number is typed by the LLM.
- The report prints and downloads cleanly.
- The M1 and M2 Issues are closed through PRs.
