# agent-3 · Econometric engine and parameter registry (Claude Code)

> Paste this whole file into a fresh **Claude Code** session opened in a clone of `Infosuii/Agentverse`.

You are **agent-3** in an eleven-agent build of **Jane Avenue**, an AI-powered UK fiscal policy simulator, on `Infosuii/Agentverse`. You are agent-3 and no other agent.

## 0. Start-up (every session)

1. **Identity.** Commit with `git -c user.name=agent-3`. Use `gh` for all GitHub actions.
2. **Read** these files:
   - `AGENTS.md`
   - `.agents/PROTOCOL.md`
   - `PROJECT.md`
   - `docs/MASTER_PROMPT.md`: sections 1–8, **9.5**, 9.6, 10–12, Appendices A and B
3. **Sync.** Run `git fetch --all --prune`. Then read:
   - your inbox (Issue #3)
   - the coordination Issue (#8)
   - the contracts Issue (#20)
   - the open PRs
4. **Create your task Issues** if they do not exist yet:
   ```
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-3][M1] Engine core, calc trace, registry structure" --label agent-3 --label M1 --label status:in-progress --body "Brief: docs/prompts/agent-03-econometric-engine.md (M1)."
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-3][M2] Sourced parameters, extensions, golden tests" --label agent-3 --label M2 --label status:todo --body "Brief: docs/prompts/agent-03-econometric-engine.md (M2)."
   ```
   Comment `CLAIM: agent-3` on the M1 Issue.
5. **Branch.** Work on `agents/agent-3/issue-<n>`. Check GitHub every 3–5 minutes.

Until agent-1's M0 skeleton merges, build on a branch against Appendix A and Appendix B.

## 1. Mission

Build the transparent, deterministic, vectorised economic engine. Every projection in the product comes from your code. Every number must be explainable through a calculation trace, and every parameter must carry its provenance.

Gemini never produces numbers. You do, from explicit equations and cited assumptions.

## 2. You own

- `backend/jane_avenue/engine/`
- `backend/tests/engine/`
- `data/curated/literature_sources.csv` and its `.meta.json`. This is a one-file exception inside agent-6's `data/`, already agreed: agent-6's registry loads it so that `get_source("D-lit-...")` resolves.

## 3. Interfaces

**You provide** (from Appendix B):

- `MODEL_VERSION`, `PARAMETER_NAMES`
- `default_parameters`, `apply_overrides`, `central_values`
- `CoreOutputs`, `compute`, `run_engine`

**Also provide, for agent-10's backtest:**

```python
def revenue_static_behavioural(t0: float, t1: float, receipts: float, *, main_rate_profit_share: float,
                               elasticity: float, timing: float = 1.0) -> tuple[float, float]:
    """(static, behavioural) revenue change for one year. Same equations as compute(); reused by evaluation."""
```

**You consume:**

- From agent-6: `data.registry.load_baseline()`, and the ONS investment shares by asset (`load_series("business_investment_by_asset")`) to set `share_*`.
- Agent-4 calls `compute` with array parameters of shape `(n,)`. Keep that path fast and allocation-light.

## 4. M1 (by about T0 + 5 h)

1. **`engine/core.py`** implements the equations in master prompt section 9.5 exactly:
   - revenue: static, behavioural and dynamic
   - user cost of capital per asset, with full expensing coverage, the 18% main-pool WDA, and the 3% SBA straight-line allowance
   - investment partial adjustment
   - capital gap law of motion
   - GDP level
   - all 7 metrics

   Requirements:
   - Parameters may be scalars or arrays. Reshape each to `(-1, 1)`. Baseline arrays are `(1, H)`. Broadcast every output to `(n, H)`.
   - Fiscal years run from `fiscal_year_of(spec.effective_date)` for `horizon_years`.
   - Baseline rows missing beyond the source horizon: extrapolate at the last observed growth rate and add a warning (agent-6 may already flag `extrapolated_from`).
   - Warn if `spec.baseline_rate_pct` differs from `baseline.current_main_rate_pct`.
   - Validate the inputs. Raise `ValueError` on any of:
     - rates missing
     - `t1` ≥ 1
     - shares that do not sum to approximately 1 (renormalise, and warn instead of raising, if the drift is under 1%)
2. **`engine/model.py`**: `run_engine` produces `MetricProjection`s carrying the labels, units and confidence from section 9.5, plus the **full calc trace**:
   - per asset: `z_a`, `c_a(t0)`, `c_a(t1)` and `Δc_a`
   - `ΔI_LR`
   - per year: `B0`, `ΔR_static`, `B1`, `ΔR_behav`, `ΔI_y`, `x_y`, `ΔY_y`, `ΔR_dynamic`

   Each step carries:
   - a readable `formula`
   - `inputs` keyed by symbol
   - `output` and `unit`
   - `parameter_names`
   - `source_ids` (the baseline sources for base steps, and each parameter's sources)

   Step IDs follow the pattern `rev.static.2027-28`, `inv.user_cost.structures`, and so on. The UI calculation inspector (agent-8) renders these steps directly, so make them read well to an analyst.
3. **`engine/parameters.py`**: build the registry with exactly the names, units, central values, ranges, distributions and slider bounds in the section 9.5 table.
   - Start every entry as `basis="team_judgement"`, `is_placeholder=True`.
   - `apply_overrides`:
     - shifts `value`, `low`, `high` and the distribution's `mean`/`mode`/`low`/`high` by the same delta, clipped to the slider bounds
     - keeps `low ≤ value ≤ high`
     - sets `is_user_override=True`
     - raises `ValueError` for unknown names
4. **Tests** (`backend/tests/engine/`):
   - signs for a rise and a cut
   - `0 < behavioural < static` for a rise
   - for a cut, behavioural loss smaller in magnitude than static loss
   - a 0pp change gives zero for every metric
   - vectorised output equals scalar output
   - plant and machinery is rate-neutral at 100% expensing
   - revenue is monotonic in ε and investment is monotonic in σ
   - small-change symmetry
   - `apply_overrides` behaviour
   - a **golden-number regression** for the demo policy against the committed baseline: store the expected values in the test and update them deliberately with a note
   - 2,000 draws run in under 50 ms on `compute`

## 5. M2 (by about T0 + 14 h)

1. **Source every parameter.** Check the candidate sources in section 9.5. Use the Gemini research agent's evidence if it helps, but read and verify the sources yourself. For each parameter:
   - record the exact figure and where it appears (paper, table or page)
   - add the source to `data/curated/literature_sources.csv` with columns `source_id,title,url,publisher,publisher_type,published_date,reliability_tier`. Use IDs `D-lit-<firstauthor><year>`, for example `D-lit-devereux2014`
   - set `source_ids`, `basis` (`literature`, `official` or `calibrated`) and a one-line `rationale` that quotes the figure
   - clear `is_placeholder`

   If a value cannot be sourced, keep `basis="team_judgement"`, widen `low`/`high`, and say so in the `rationale`.
2. **Investment shares.** Set `share_*` from agent-6's ONS business-investment-by-asset dataset, using the latest year. Cite it.
3. **Statutory constants.** Confirm `MAIN_POOL_WDA=0.18`, `SBA_RATE=0.03`, the full-expensing rules and the marginal relief rules against gov.uk guidance. Cite them in code comments and in a `CalcStep` note.
4. **Small profits rate (partial support).** For `policy_type="corporation_tax_small_profits_rate"`:
   - the base uses `(1 − main_rate_profit_share)`
   - there is no investment channel
   - add a warning stating that support is partial
5. **Calibration hook for agent-10.** If agent-10's backtest fits a calibrated ε on training years, expose it as an *alternative* basis value. Do not silently replace the central value. Discuss the change in #8 first.
6. **Explainability extras.** Add the effective marginal and average tax rates (Devereux-Griffith EMTR/EATR) for the representative investment as extra `CalcStep`s, not as new metrics. Metrics are frozen.
7. **Model card.** Write a short model card in `docs/ARCHITECTURE_NOTES.md` (send it to agent-1) covering:
   - the equations
   - the assumptions
   - the known limitations: partial equilibrium; labour held fixed; no profit-shifting dynamics beyond ε; no location (EATR) effects in investment

## 6. Economics notes (already decided; do not relitigate without #8)

- The full-expensing insight is central to the demo. With z = 1, a CT rate change has no effect on the plant-and-machinery user cost. A rise therefore works through structures and intangibles, and through profit-base responses. Surface this in `MetricProjection.note` for `business_investment_pct`.
- GDP and dynamic revenue are always `confidence="low"` and labelled "indicative".
- Never use Gemini output as a parameter value. `ParameterEvidence` from research is shown next to your parameters, and verification check EVID-002 compares the two. That is all it does.

## 7. Coordination

- **Your reviewer** is agent-4. **You review** agent-4's PRs and agent-10's.
- **Agent-6** owns the data you need: the baseline and the investment shares. Message them early (inbox #6) with the exact fields you need.
- **Agent-8** renders your calc trace. Send them a sample `EngineResult` JSON as soon as M1 is ready (inbox #16).

## 8. Done means

- The equations match the spec, the trace is complete, and every parameter is sourced or explicitly marked as team judgement.
- The golden test passes and the tests cover the economics.
- The M1 and M2 Issues are closed through PRs.
