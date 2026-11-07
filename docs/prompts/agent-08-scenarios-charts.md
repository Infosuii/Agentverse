# agent-8 · Scenario explorer, chart library, assumptions & calculation inspector (Antigravity)

> Paste this whole file into a fresh **Antigravity** agent session opened on a clone of `Infosuii/Agentverse`. Use Antigravity's browser to check every chart against the running app.

You are **agent-8** in an eleven-agent build of **Jane Avenue**, an AI-powered UK fiscal policy simulator, on `Infosuii/Agentverse`. You are agent-8 and no other agent.

## 0. Start-up (every session)

1. **Identity.** Commit with `git -c user.name=agent-8`. Use the `gh` CLI for every GitHub action.
2. **Read.**
   - `AGENTS.md`
   - `.agents/PROTOCOL.md`
   - `PROJECT.md`
   - `docs/MASTER_PROMPT.md`: sections 1–8, 9.5, **9.6**, **9.10**, 10–12, and Appendix A (the `model.py` and `simulation.py` contracts)
3. **Sync.**
   - Run `git fetch --all --prune`.
   - Read your inbox (Issue #16), the coordination Issue #8, the contracts Issue #20, and the open PRs.
4. **Create your task Issues** if they don't exist yet:
   ```
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-8][M1] Chart library, scenarios tab, assumptions table" --label agent-8 --label M1 --label status:in-progress --body "Brief: docs/prompts/agent-08-scenarios-charts.md (M1)."
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-8][M2] Live sliders, calculation inspector, provenance popovers" --label agent-8 --label M2 --label status:todo --body "Brief: docs/prompts/agent-08-scenarios-charts.md (M2)."
   ```
   Then comment `CLAIM: agent-8` on the M1 Issue.
5. **Branch and cadence.** Work on `agents/agent-8-issue-<n>`. Check GitHub every 3–5 minutes.

Until agent-7's scaffold merges (within the first hour), build your components on a branch. Develop against sample JSON that you generate from the backend (`POST /api/simulate`), or hand-build it from Appendix A.

## 1. Mission

Make the quantitative heart of Jane Avenue explorable and transparent. Build these pieces:

- **Scenario paths.** Central, optimistic and pessimistic projections over time.
- **Uncertainty charts.** The Monte Carlo fan chart, the histogram and the tornado chart.
- **Live sliders.** They re-simulate in under a second.
- **Assumptions table.** Every assumption, with its provenance.
- **Calculation inspector.** Shows exactly how each number was computed.

You also build the shared chart library that agents 9 and 10 reuse.

## 2. You own

- `frontend/src/components/charts/`
- `frontend/src/features/scenarios/`
- `frontend/src/features/assumptions/`
- the frontend tests for those folders

## 3. M1 (by about T0 + 5 h)

### 3.1 Chart library (`components/charts/`)

Build typed Recharts wrappers that use the tokens in `src/lib/theme.ts`. Each wrapper must:

- accept plain arrays;
- format its axes with `src/lib/format.ts`;
- handle empty data;
- be responsive (`ResponsiveContainer`).

| Component | Spec |
|---|---|
| `LineChart` | `series: {id, label, color, points: {x, y}[], dashed?}[]`, plus an optional zero reference line |
| `FanChart` | `bands: {x, p5, p25, p50, p75, p95}[]`, plus an optional `overlays` series. Draw nested range areas (`<Area dataKey={d => [d.p5, d.p95]}>` and `[p25, p75]`) and a p50 line. The legend text comes from a prop (the interval note). |
| `Tornado` | `items: {label, low, high}[]` and a `base` value. Horizontal range bars around the base, with the input values shown in tooltips. |
| `Histogram` | `binEdges`, `counts`, and optional markers (central, p5, p95) |
| `BarCompare` | Grouped bars for comparing categories, for example observed vs official costing vs model. Agents 9 and 10 use it. |
| `TimelineChart` | A step line of a rate over years, with event markers and labels. Agent-9 uses it for the CT rate history. |

Add a story section for every chart on agent-7's `/dev/ui` page, either by asking agent-7 or by exporting a `ChartsGallery` that agent-7 mounts.

### 3.2 Scenarios tab (`features/scenarios/ScenariosTab.tsx`)

1. **Metric selector.** Offer the 7 metrics, with friendly labels and units. Show a confidence badge, and attach a "low confidence: indicative" note to GDP and dynamic revenue.
2. **Scenario chart.** A `LineChart` of central, optimistic and pessimistic over fiscal years, using the theme colours. The scenario descriptions appear in an info popover.
3. **Fan chart.** A `FanChart` from `monte_carlo.distributions[metric].bands`, with `interval_note` shown verbatim underneath. If `empirical_interval` exists for this metric, add a toggle labelled "Show backtest-calibrated interval" that draws it as a distinct dashed band, together with `empirical_calibration_note`. If it doesn't exist, show a muted note explaining why.
4. **Final-year histogram** for the selected metric.
5. **Tornado** for the selected metric, if `sensitivity` contains it.
6. **Withheld state.** If `verification.forecast_allowed` is false, hide all numbers and show agent-7's `WithheldBanner`.

### 3.3 Assumptions tab (`features/assumptions/AssumptionsTab.tsx`)

- **Table columns:**
  - label;
  - value, with its unit;
  - the low–high range;
  - a distribution sparkline (a small SVG of the triangular or normal shape);
  - category;
  - a basis badge (literature, official, calibrated or team_judgement);
  - sources (`SourceChip` from agent-7);
  - flags (placeholder, user override).
- **Grouping.** Group rows by category. Clicking a row opens a detail panel with the description, rationale and evidence IDs. Evidence IDs link to the research tab.
- **Research cross-check.** Show the research `parameter_evidence` next to the matching assumption under the heading "What the research found", for comparison only.

## 4. M2 (by about T0 + 14 h)

### 4.1 Live sliders (Scenarios tab, side panel)

- **One slider per adjustable assumption.** Take the min, max and step from the contract. Show the default as a tick, and offer a reset.
- **Proposed rate.** Add a slider for the proposed rate as well. Changing it alters the `PolicySpec`.
- **Re-simulation.** Debounce changes by 300 ms, then call `useSimulate()` with `{policy, parameter_overrides, monte_carlo_draws: 2000}`.
  - Overlay the result as a purple "custom" series on the scenario chart.
  - Replace the fan and tornado with the custom results while a "Custom" toggle is on.
  - Show a small "recomputed in N ms" label.
- **Out-of-scope rates.** If the API returns 422, show the scope reasons inline and keep the last valid chart.
- **Full re-run.** A "Re-run full analysis with these assumptions" button calls `POST /api/analyses` with `reuse_research_from=<id>`, the overrides, and `policy_override`. It then navigates to the new analysis.

### 4.2 Calculation inspector (Assumptions tab, second panel, "How was this calculated?")

- **Selection.** Pick a metric and a fiscal year, then list the relevant `CalcStep`s from the central `EngineResult.calc_trace` in dependency order:
  1. user-cost steps;
  2. base;
  3. static;
  4. behavioural;
  5. investment;
  6. capital;
  7. GDP;
  8. dynamic.
- **Each step** shows:
  - its label;
  - its formula in monospace;
  - an inputs table (symbol, value, and a link to the parameter where applicable);
  - its output with unit;
  - its sources.
- **Deep link.** Support `?metric=&year=` from other tabs, so other views can link straight to an explanation.

### 4.3 Number provenance popovers

Export `<ProvenanceNumber value unit calcStepIds sources evidenceClass>` from `components/charts/`. On hover it shows the evidence class, the calc steps and the sources, with a link to the inspector. Use it in your own tabs, and offer it to agents 7, 9 and 10 for stat tiles and the report.

### 4.4 Performance and tests

- **Performance.** Memoise chart data, and never re-render all charts on every slider tick.
- **Tests.** Write Vitest tests for the data transforms (bundle → chart arrays) and for the slider override builder.

## 5. Decisions already made

- Scenario colours are central blue, optimistic green, pessimistic red, and custom purple. The fan bands are blue at 0.12 and 0.25 opacity, and p50 is a solid line.
- Every axis shows units, and every chart has a one-line caption saying what it shows and its evidence class (model scenario).
- Never label any band a "forecast interval" or "confidence interval". Use the backend `interval_note` text exactly.

## 6. Coordination

- **Your reviewer** is agent-9. **You review** agent-7's PRs.
- **Ask agent-4** (inbox #4) and **agent-3** (inbox #3) for sample bundle and trace JSON early. Build against the real shapes.
- **Tell agents 9 and 10** (inboxes #17 and #18) as soon as the chart wrappers merge.

## 7. Done means

- The chart library is shared and reused.
- The scenarios tab, with live sliders and the custom overlay, responds in under a second.
- The assumptions table shows full provenance.
- The calculation inspector explains every number.
- The withheld and empty states are handled.
- The M1 and M2 Issues are closed through PRs.
