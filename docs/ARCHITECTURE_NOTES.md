# Architecture notes: decision log

Owner: agent-1. One line per cross-cutting decision. Other agents propose entries through agent-1 (inbox #1) or Issue #8.

| Date | Decision | Reason | Agent |
|---|---|---|---|
| 2026-11-07 | Contracts are Appendix A verbatim in `backend/jane_avenue/contracts/`; ruff ignores UP017 there only. | Byte-for-byte match with the spec; no M0 "improvements". | agent-1 |
| 2026-11-07 | One `Analysis` JSON blob per row in SQLite (`analyses`), plus an `events(analysis_id, seq, body)` table. | Contracts can gain optional fields with no migration. | agent-1 |
| 2026-11-07 | One SQLite connection per store, `check_same_thread=False`, every call under one re-entrant lock. | Simple thread safety for the API thread pool and SSE readers. | agent-1 |
| 2026-11-07 | Event seq is taken and written under the same lock (`AnalysisStore.append_next_event`). | Seqs stay unique and gap-free per analysis across threads. | agent-1 |
| 2026-11-07 | The orchestrator calls module entrypoints through their packages at call time (`policy.parse_policy`, ...). | Owners' replacements and test monkeypatches are picked up without editing the orchestrator. | agent-1 |
| 2026-11-07 | Mutations of the `Analysis` use `model_copy(deep=True)`. | Pydantic copies are shallow; saved snapshots must not share nested state. | agent-1 |
| 2026-11-07 | Research reuse (`reuse_research_from`) deep-copies the earlier `ResearchFindings` and emits no `research_step` events. | Re-run with new assumptions without repeating research. | agent-1 |
| 2026-11-07 | Out-of-scope policies still run research and precedents; modelling is skipped and verification withholds the forecast. | MASTER_PROMPT 9.9. | agent-1 |
| 2026-11-07 | REPORT-001 re-check calls `verification.check_report(report, analysis)` only if it exists (`getattr` guard). | Agent-5 ships it later; no edit needed when it lands. | agent-1 |
| 2026-11-07 | `create_app(store)` with an explicit store runs analyses inline as a background task; without one, on a 2-worker `ThreadPoolExecutor`. | The TestClient completes background tasks before returning; production runs two analyses at once. | agent-1 |
| 2026-11-07 | SSE polls the event table every 250 ms, pings every 15 s, resumes from `after_seq` or `Last-Event-ID` (the larger wins), and ends on `completed`/`failed`. | Resumable, proxy-friendly streaming without a message broker. | agent-1 |
| 2026-11-07 | API errors are `{"message": str, "reasons": [str]}` (`ErrorBody`); FastAPI's own 422 validation body is kept for malformed requests. | The UI can show any error inline; no tracebacks. | agent-1 |
| 2026-11-07 | `operation_id` is the route function name (e.g. `create_analysis`, `stream_events`). | Readable names in the generated frontend client. | agent-1 |
| 2026-11-07 | `export_openapi.py` writes `frontend/src/api/openapi.json` with sorted keys. | Stable output for the CI drift check. | agent-1 |
| 2026-11-07 | Tests run with `--import-mode=importlib` and no `__init__.py` in test folders. | Eleven owners' test files can share basenames without collisions. | agent-1 |
| 2026-11-07 | `backend/scripts/smoke.py` runs one analysis in the current mode on an in-memory DB and prints stage timings, verification and remaining placeholders; `--json`, `--expect-approved` and `--max-seconds` give CI-friendly exit codes (0 ok, 1 failed, 2 check failed). | One command for agent-11 and the demo rehearsal to confirm the golden path. | agent-1 |
| 2026-11-07 | `AnalysisStore.get` serves a 32-entry in-memory LRU of parsed `Analysis` objects; `save` refreshes the entry. Returned objects are shared and read-only. | `GET /api/analyses/{id}` stays under 100 ms as analyses grow with the real engine and research. | agent-1 |
| 2026-11-07 | Every log record carries `analysis_id` and `stage` (context variables + a log-record factory in `orchestrator/logcontext.py`); format `... [analysis=<id> stage=<stage>] message`; level from `JANE_LOG_LEVEL`. | Modules (incl. LLM usage logs) get the context with plain `logging.getLogger(__name__)` calls. | agent-1 |
| 2026-11-07 | `POST /api/analyses` is limited to 6 a minute per client host in live mode (in-memory token bucket); 429 with `Retry-After` and an `ErrorBody`. | Protects the shared Gemini quota; no limit in mock/cached so tests and demos are unaffected. | agent-1 |
| 2026-11-07 | At startup the API logs a warning listing placeholder datasets (and the baseline) still in use. | MASTER_PROMPT 13 "no placeholders"; visible in every dev run until agent-6's curated data lands. | agent-1 |
| 2026-11-07 | Monte Carlo parameters are sampled independently in v1 (no correlations). | Simplicity; no sourced correlation structure yet. Any correlations added later are logged here. | agent-4 |
| 2026-11-07 | "Favourable" (optimistic/pessimistic scenario selection) means higher (lower) cumulative dynamic revenue, for rises and cuts alike; `profit_base_deviation_pct` is set by rule (high/low). | One rule that works for both directions of policy change. | agent-4 |
| 2026-11-07 | The empirical interval is central × (1 + backtest residual quantiles), shown only with ≥ 8 out-of-sample residuals and reported coverage; the main bands stay `interval_kind="assumption_range"`. | Only call something a prediction interval when the backtest calibrates it (MASTER_PROMPT rule 6). | agent-4 |
| 2026-11-07 | A `ValueError` from `simulate`/`compute` (invalid parameters, e.g. investment shares not summing to 1) is a 422 `{"message": "Invalid simulation parameters", "reasons": [...]}` on `/api/simulate`; in a full analysis it fails the run with that reason (and an `error` event) instead of skipping modelling. | A 500 is not actionable; skipping modelling could let verification approve an analysis with no numbers. | agent-1 |
| 2026-11-07 | Measured `/api/simulate` (2,000 draws + tornado, with the real engine #57 merged locally): median about 25 ms end to end. | Budget is under 1 s (MASTER_PROMPT 9.6). | agent-4 |

## Reading the uncertainty

*Written by agent-4 (scenarios and uncertainty). Shown in the UI's Scenarios tab.*

- **Scenarios.** *Central* has every assumption at its central value. *Optimistic* and *pessimistic* take each uncertain assumption, one at a time, to the end of its range that gives higher (or lower) cumulative dynamic revenue. The profit base deviation is set by rule (high or low). They mark a stress envelope of jointly favourable or unfavourable assumptions. They are not probability-weighted, and all of them are unlikely to hold at once.
- **Monte Carlo bands.** 2,000 draws vary all uncertain assumptions together (independently, from their stated distributions) and rerun the model. The shaded bands show the 5th–95th and 25th–75th percentiles of the results, and the line shows the median. They are assumption-driven ranges, not statistical prediction intervals, and the note reports the Monte Carlo standard error of the median.
- **Tornado.** Each uncertain assumption moves from its low to its high value with the others at central, for the final year. Bars are sorted by the size of the swing, so the top bars are the assumptions the result depends on most. Interactions between assumptions are not shown.
- **Why these are not forecasts.** Every range shows what the model implies under its assumptions. None includes model-specification error, data revisions, macroeconomic shocks or other policy changes. Only the separately labelled *empirical prediction interval* is checked against history, and it is shown only when the backtest has enough out-of-sample cases and reports its coverage.
