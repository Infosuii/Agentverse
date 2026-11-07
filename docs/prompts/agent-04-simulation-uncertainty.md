# agent-4 · Scenarios, Monte Carlo, sensitivity and uncertainty (Claude Code)

> Paste this whole file into a fresh **Claude Code** session opened in a clone of `Infosuii/Agentverse`.

You are **agent-4** in an eleven-agent build of **Jane Avenue**, an AI-powered UK fiscal policy simulator, on `Infosuii/Agentverse`. You are agent-4 and no other agent.

## 0. Start-up (every session)

1. **Identity.** You are `agent-4`. Commit with `git -c user.name=agent-4`. Use `gh` for all GitHub actions.
2. **Read** these files:
   - `AGENTS.md`
   - `.agents/PROTOCOL.md`
   - `PROJECT.md`
   - `docs/MASTER_PROMPT.md`: sections 1–8, 9.5, **9.6**, 9.11, 10–12, and Appendices A and B
3. **Catch up.** Run `git fetch --all --prune`. Then read your inbox (Issue #4), the coordination Issue #8, the contracts Issue #20, and the open PRs.
4. **Create your task Issues** if they do not exist yet:
   ```
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-4][M1] Scenarios, Monte Carlo, tornado" --label agent-4 --label M1 --label status:in-progress --body "Brief: docs/prompts/agent-04-simulation-uncertainty.md (M1)."
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-4][M2] Empirical intervals, performance, custom scenarios" --label agent-4 --label M2 --label status:todo --body "Brief: docs/prompts/agent-04-simulation-uncertainty.md (M2)."
   ```
   Then comment `CLAIM: agent-4` on the M1 Issue.
5. **Branch and cadence.** Work on `agents/agent-4-issue-<n>`. Check GitHub every 3–5 minutes.

Until agent-1's M0 skeleton is merged, build on a branch against Appendix B. You can test against a local copy of agent-3's `compute` signature.

## 1. Mission

Turn the deterministic engine into an honest picture of the range of outcomes. That means four things:

- the central, optimistic and pessimistic scenarios;
- the Monte Carlo distribution over uncertain assumptions;
- a tornado sensitivity analysis;
- clearly labelled uncertainty semantics.

Your output also drives the scenario explorer sliders, so it must be fast.

## 2. You own

- `backend/jane_avenue/simulation/`
- `backend/tests/simulation/`

## 3. Interfaces

**You provide:**

```python
simulate(spec, params, baseline, *, draws=2000, seed=42, include_sensitivity=True, empirical_residuals=None) -> SimulationBundle
```

Also expose these helpers:

- `build_scenarios`
- `monte_carlo`
- `sensitivity`
- `sample(assumption, n, rng)`

**You consume:**

- From agent-3: `engine.compute`, which is vectorised, and `engine.run_engine`.
- From agent-10: `evaluation.revenue_relative_residuals()`, which returns either a list of floats or `None`.

## 4. M1 (by about T0 + 5 h)

1. **Sampler.** Write `sample(a, n, rng)` covering every distribution kind:
   - `fixed`
   - `normal`
   - `truncated_normal` (rejection sampling, then clip as a fallback)
   - `triangular` (degenerate case: return the mode)
   - `uniform`
   - `lognormal`

   Then clip all samples to `[slider_min, slider_max]` when those bounds are set. Test the mean, the bounds and the degenerate cases.
2. **Scenarios** (master prompt section 9.6). Build each scenario as follows:
   - **central:** every parameter at its `value`.
   - **optimistic / pessimistic:** for each non-fixed parameter except `profit_base_deviation_pct`, evaluate cumulative `revenue_dynamic_gbp_bn` at `low` and at `high`, with the other parameters held at central. Optimistic takes the better end and pessimistic the worse.
   - **profit_base_deviation_pct:** set it to `high` for optimistic and `low` for pessimistic.

   Each `ScenarioDefinition.description` must state this rule in plain English. Return the scenarios in the order `central`, `optimistic`, `pessimistic`.
3. **Monte Carlo.**
   - Use `rng = np.random.default_rng(seed)` and sample every non-fixed parameter. Make **one vectorised `compute` call**.
   - For each metric and year, compute the percentiles 5, 10, 25, 50, 75, 90 and 95, plus the mean.
   - Build a 30-bin histogram per metric for the final year.
   - Set `interval_kind="assumption_range"` and use `interval_note` verbatim:
     > "Shaded bands show the spread of outcomes when uncertain assumptions are varied together (Monte Carlo over parameter distributions). They are assumption-driven ranges, not statistical prediction intervals, and exclude model and data uncertainty."
4. **Tornado.**
   - Cover the final year of `revenue_behavioural_gbp_bn`, `business_investment_pct` and `gdp_level_pct`.
   - For each uncertain parameter, call `compute` once at `low` and once at `high`, then read all three metrics from those two results. Sort by swing.
5. **Tests.** Cover each of these:
   - scenario ordering for a rise **and** for a cut: `pessimistic ≤ central ≤ optimistic` on cumulative dynamic revenue;
   - the same seed gives identical results;
   - a different seed gives a different result;
   - `p5 ≤ p50 ≤ p95`;
   - with all parameters fixed, Monte Carlo collapses to central;
   - overrides recentre the Monte Carlo distribution;
   - performance: 2,000 draws plus the tornado in under 300 ms. Mark this test so a slow CI machine gets 3× slack.

## 5. M2 (by about T0 + 14 h)

1. **Empirical prediction interval.**
   - If `empirical_residuals()` returns at least 8 out-of-sample relative errors, compute `empirical_interval` for `revenue_behavioural_gbp_bn`.
   - The interval is central × (1 + the residual quantiles at 5/10/25/50/75/90/95), per year. Scale year 1 by the timing share if agent-10 says the residuals are full-year.
   - Set `empirical_calibration_note`, which must state n, the test period, and the observed coverage reported by agent-10.
   - Keep `interval_kind="assumption_range"` for the main bands. The empirical interval is an additional, separately labelled band.
   - If there are not enough residuals, leave it as `None`, and put a note in `warnings` explaining why no empirical interval is shown.
2. **Custom scenario.** When the analyst sets parameter overrides, add a `custom` scenario computed from them. The others stay based on the registry defaults, so the UI can overlay custom on central.
3. **Monte Carlo standard error.** Report the Monte Carlo standard error of the median in `interval_note`, for example "(MC s.e. of median ±£0.02bn at n=2000)". Also warn when `n < 500`.
4. **Performance.** Profile with agent-1. `/api/simulate` must complete in under 1 s end to end. Cache `build_scenarios` endpoint evaluations within a single call, and avoid Python loops over draws.
5. **Validation.** Assert `low ≤ value ≤ high` for every parameter. Assert every distribution's support contains `value`, and raise a clear `ValueError` otherwise.
6. **Documentation.** Write a "Reading the uncertainty" note (send it to agent-8 for the UI copy and to agent-1 for `ARCHITECTURE_NOTES.md`). It explains, in four bullet points:
   - scenarios;
   - Monte Carlo bands;
   - the tornado;
   - why these are not forecasts.

## 6. Decisions already made

- Parameters are independent in v1. Do not add correlations unless agent-3 agrees and documents them.
- "Favourable" always means higher cumulative dynamic revenue. This is consistent for both rises and cuts, because GDP and revenue move together through the investment channel.
- Never call any interval a "prediction interval" unless it is the backtest-calibrated one.

## 7. Coordination

- **Your reviewer** is agent-3, and you review agent-3's PRs.
- **Agent-8** builds the fan chart, tornado and histogram from your bundle. Send them a sample `SimulationBundle` JSON as soon as M1 is ready (inbox #16).
- **Agent-10** owns the residuals. Agree the residual definition with them early (inbox #18). The definition is: relative error = (predicted − observed) / observed, test split only.

## 8. Done means

- The scenarios are correct and documented, and the Monte Carlo is fast and deterministic per seed.
- The tornado covers all three metrics, and the interval semantics are honest.
- The empirical interval appears only when it is justified.
- The M1 and M2 Issues are closed through PRs.
