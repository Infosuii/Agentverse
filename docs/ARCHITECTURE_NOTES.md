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
