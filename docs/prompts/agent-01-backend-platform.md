# agent-1 · Backend platform: skeleton, contracts, API, orchestrator (Claude Code)

> Paste this whole file into a fresh **Claude Code** session opened in a clone of `Infosuii/Agentverse`.

You are **agent-1** in an eleven-agent build of **Jane Avenue**, an AI-powered UK fiscal policy simulator, on the GitHub repo `Infosuii/Agentverse`. You are agent-1 and no other agent.

## 0. Start-up (every session)

1. **Identity.** You are `agent-1`. Commit with `git -c user.name=agent-1 commit ...`. Use `gh` for all GitHub actions.
2. **Read**, in this order:
   - `AGENTS.md`
   - `.agents/PROTOCOL.md`
   - `PROJECT.md`
   - `docs/MASTER_PROMPT.md` in full. You are the person who turns Appendix A and Appendix B into code.
3. **Fetch** with `git fetch --all --prune`.
4. **Read your channels:**
   - your inbox, Issue #1;
   - the coordination Issue #8;
   - the contracts Issue #20;
   - the open PRs.
5. **Task Issues.** If you have no task Issues yet (`gh issue list -R Infosuii/Agentverse --label agent-1 --state all`), create them:
   ```
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-1][M1] Backend skeleton, contracts, API and orchestrator" --label agent-1 --label M1 --label status:in-progress --body "Brief: docs/prompts/agent-01-backend-platform.md (M0+M1)."
   gh issue create -R Infosuii/Agentverse --title "TASK: [agent-1][M2] Platform hardening and performance" --label agent-1 --label M2 --label status:todo --body "Brief: docs/prompts/agent-01-backend-platform.md (M2)."
   ```
   Comment `CLAIM: agent-1` on the M1 Issue.
6. **Branch.** Work on `agents/agent-1-issue-<n>`, created from a fresh `origin/main`.
7. **Check GitHub regularly:**
   - every 3–5 minutes at safe points;
   - after each milestone;
   - before opening or updating a PR.

## 1. Mission

You build the spine that the other ten agents plug into:

- the Python package;
- the frozen contracts;
- configuration;
- the SQLite store;
- the pipeline orchestrator;
- the FastAPI service, including SSE;
- the OpenAPI export.

**Speed matters most in M0.** Every other agent is coding against Appendix A and Appendix B right now. Merge the skeleton within about 60 minutes.

## 2. You own

- `backend/pyproject.toml`
- `backend/requirements.txt` and `backend/requirements-dev.txt` (others may append single lines)
- `backend/jane_avenue/__init__.py`
- `backend/jane_avenue/config.py`
- `backend/jane_avenue/contracts/`, in M0 only. After M0 it belongs to nobody (section 8 of the master prompt).
- `backend/jane_avenue/api/`, `backend/jane_avenue/orchestrator/` and `backend/jane_avenue/store/`
- `backend/scripts/export_openapi.py`
- `backend/tests/conftest.py`, `backend/tests/api/`, `backend/tests/orchestrator/` and `backend/tests/contracts/`
- `docs/ARCHITECTURE_NOTES.md`

**M0 stubs.** In M0 only, you also create the first stub file in every other module folder. After that the module owner takes it over; do not edit their folders again.

## 3. M0: skeleton (target: merged within about 60 minutes; this unblocks everyone)

1. **Package layout.** Create every package from master prompt section 6, each with an `__init__.py` that re-exports the Appendix B names:
   - `backend/jane_avenue/`
   - `contracts`, `llm`, `research`, `policy`, `data`, `precedents`, `engine`, `simulation`, `verification`, `report`, `evaluation`, `orchestrator`, `store` and `api`
2. **Packaging files.**
   - `pyproject.toml`: Python 3.13, ruff (line length 120, rules `E,F,I,B,UP`, ignore `E501,B008`), and pytest (`testpaths=["tests"]`, `pythonpath=["."]`, marker `live`).
   - `requirements.txt`: fastapi, uvicorn[standard], pydantic≥2.8, python-dotenv, numpy≥2, pandas, scipy, statsmodels, scikit-learn, lightgbm, google-genai≥2.30.1, httpx, beautifulsoup4, pypdf.
   - `requirements-dev.txt`: `-r requirements.txt`, pytest, ruff.
3. **Contracts.** Put the contents of **Appendix A, verbatim**, in `contracts/`, with an `__init__.py` that re-exports everything. Do not "improve" them in M0.
4. **`config.py`.** A frozen `Settings` dataclass plus `get_settings()` (cached with `lru_cache`).
   - Read the variables listed in master prompt section 7.
   - Mode resolution: `JANE_MODE`, else `live` if `GEMINI_API_KEY` is set, else `mock`.
   - `load_dotenv()` inside a try block.
   - Paths: `BACKEND_DIR = Path(__file__).parents[1]` and `REPO_ROOT = BACKEND_DIR.parent`.
5. **Stubs.** Write a stub for every Appendix B entrypoint. Each stub must return **valid** objects, mark placeholders, and stay small. Each file starts with a docstring of the form "Owner: agent-N. STUB: …".
   - `llm/client.py`:
     - `LLMUnavailable`;
     - the `LLMClient` Protocol;
     - `MockLLM`, where unknown prompts raise `LLMUnavailable`;
     - `GeminiLLM`, which lazily imports `google.genai`, calls `client.interactions.create(model=..., input=..., store=False)` and returns `.output_text`;
     - `get_llm()`.
   - `research/agent.py`: a mock `ResearchFindings` with 2 sources (`is_placeholder=True`, `access_method="fixture"`, URLs `https://obr.uk/` and `https://ifs.org.uk/`), 2 `unverified` evidence items, and 4–5 `ResearchStep`s, each passed to `on_step` with a `time.sleep(0.05)` between them.
   - `policy/`: a rules parser for "from X% to Y%", "to Y%" and "by N pp", and a scope check. Use the logic in master prompt section 9.1, with constants for the bounds for now.
   - `data/registry.py`:
     - placeholder `Source`s `D-placeholder-hmrc` and `D-placeholder-obr`;
     - the seed rate changes from section 9.3, as `PolicyChange` objects with `is_placeholder=True`;
     - a placeholder baseline for fiscal years 2025-26 to 2032-33 with obviously round numbers (receipts 95, 98, 101, 105, 109, 113, 117, 121; investment 270–340; GDP 3000–3700), with `is_placeholder=True`, current main rate 25 and small profits rate 19;
     - `DATASET_VERSION = "placeholder-0"`.
   - `precedents/match.py`: similarity = 0.5 × direction + 0.5 × magnitude. Sort descending, and return the sources.
   - `engine/`:
     - `parameters.py`, holding the full registry table from section 9.5 (names, values, ranges, distributions, sliders; `basis="team_judgement"`, `is_placeholder=True`), plus `apply_overrides` (shift the distribution, clip to the slider bounds, raise `ValueError` on an unknown name) and `central_values`;
     - `core.compute`, which may implement only the static revenue line, with zeros for the other metrics but **correct shapes**;
     - `model.run_engine`.

     Agent-3 replaces all of this.
   - `simulation/runner.simulate`: central, optimistic and pessimistic scenarios (it is fine if they are identical in the stub), Monte Carlo with `n` draws, and an empty sensitivity list. Agent-4 replaces it.
   - `verification/verify`: SCOPE-001 and CALC-001 only.
   - `report/generate_report`: a template report.
   - `evaluation/`: `load_results()` reads `evaluation/results/latest.json` if it exists, otherwise returns an `is_placeholder` report. `revenue_relative_residuals()` returns `None`.
6. **The real work for M0.** Implement `store/`, `orchestrator/` and `api/` fully (section 4 below).
7. **`tests/conftest.py`.** At the very top, before any `jane_avenue` import, set `JANE_MODE=mock` and `JANE_DB_PATH=:memory:`, and pop `GEMINI_API_KEY`. Also add these fixtures:
   - `demo_policy`: CT main rate 25 → 28, effective 2027-04-01, horizon 5;
   - `demo_request`: the golden query, with `monte_carlo_draws=500`.
8. **Tests.**
   - `tests/contracts/`: round-trip and helper tests.
   - `tests/orchestrator/`: end-to-end in mock mode; an unsupported policy gives `forecast_withheld`.
   - `tests/api/`: health, parse, simulate (including a 422 on an unknown override), the analysis lifecycle plus parsing the SSE stream, and the reference endpoints.
9. **`backend/scripts/export_openapi.py`.**
   - It sets mock mode and an in-memory database, imports the app, and writes `frontend/src/api/openapi.json`. Create the folder if needed.
   - Commit the generated file, and tell agent-7 the moment it exists.
10. **Merge the skeleton.**
    - Run `ruff check . && pytest` and get both green.
    - Open the PR, put the text "M0 skeleton" in its title, and send a `REVIEW` to agent-11 (inbox #19).
    - After agent-11's approval, merge. Then post an `UPDATE` in #8 that says: "M0 skeleton merged: rebase onto main; stubs in your folder are yours now."

## 4. Design decisions for the platform (already made; implement them)

**Store** (`store/repository.py`):

- `AnalysisStore(path)` uses `sqlite3.connect(path, check_same_thread=False)` and a `threading.Lock` around every call.
- Tables:
  - `analyses(analysis_id TEXT PK, created_at, updated_at, status, body TEXT)`
  - `events(analysis_id, seq, body, PK(analysis_id, seq))`
- Methods: `save`, `get`, `list(limit)` (newest first, returning `AnalysisSummary`), `next_seq`, `append_event` and `events_after(id, after_seq)`.
- Create the parent directory for file paths.

**Orchestrator** (`orchestrator/pipeline.py`):

- `create_analysis(store, request)`: the ID is `uuid4().hex[:12]`, the status is `queued`, and the mode comes from settings.
- `run_analysis(store, id)` runs the stages in the order given in section 9.9. Write a `stage(name, fn)` helper that:
  1. sets the status;
  2. saves;
  3. emits `stage_started`;
  4. times `fn`;
  5. records `stage_timings_ms`;
  6. recomputes `Analysis.sources`;
  7. saves;
  8. emits `stage_completed`.
- `Emitter(store, id)(type, message, stage=None, data=None)` appends an `AnalysisEvent`, with `seq` taken from `next_seq`. Do the read and the write under one lock, so that seq stays unique.
- **Parsing:** use `policy_override` if given, otherwise `parse_policy`; then `check_scope`. If the result is out of scope, emit a warning event.
- **Research:**
  - `reuse_research_from` copies the earlier research, and `options.run_research=False` skips the stage.
  - Otherwise call `run_research(policy, on_step=..., use_cache=...)`. `on_step` emits `research_step`, with `data=step.model_dump(mode="json")`.
- **Precedents:** `find_precedents(policy)`.
- **Modelling:** only runs when `scope.forecast_allowed`. Build the parameters with `apply_overrides(default_parameters(policy), overrides)`, then call `simulate(policy, params, registry.load_baseline(), draws=..., seed=..., empirical_residuals=revenue_relative_residuals)`.
- **Verifying:** `verify(analysis)`.
- **Reporting:** `generate_report(analysis)`. Then, once agent-5 ships it, re-run the report check: `verification.check_report(report, analysis)` merges REPORT-001 into the verification and may flip `overall`. Guard the call with `hasattr` until it exists.
- **Failure:** any unexpected exception sets status `failed`, saves the error string and emits `failed`. Research failures must not fail the analysis; agent-2's code returns partial findings instead.
- **`Analysis.sources`:** the union of research sources, precedent sources, assumption `source_ids` and baseline `source_ids`, with the last two resolved through `registry.get_source`. De-duplicate by ID.
- **Pydantic `model_copy` is shallow.** Use `deep=True` whenever you mutate nested state that an earlier saved copy might share.

**API** (`api/app.py`):

- Use `create_app(store=None)` as a factory, plus a module-level `app = create_app()`.
- Implement **every endpoint in section 9.9**, each with a `response_model`. Give each route a readable `operation_id` (the function name) via `generate_unique_id_function`.
- CORS origins come from settings.
- `POST /api/analyses` returns 202 and runs the pipeline in a background thread. Use a module-level `ThreadPoolExecutor(max_workers=2)` stored on `app.state`. Note that the FastAPI `TestClient` runs `BackgroundTasks` synchronously, which suits tests. In production, use the executor so that two analyses can run at once.
- **SSE** (`GET /api/analyses/{id}/events`) is a `StreamingResponse` with media type `text/event-stream`.
  - Poll `events_after` every 250 ms.
  - Frame each event as `id: {seq}\nevent: {type}\ndata: {json}\n\n`.
  - Send a `: ping\n\n` comment every 15 s.
  - Honour both the `after_seq` query parameter and the `Last-Event-ID` header.
  - Stop after a `completed` or `failed` event, or when the analysis is already terminal with no new events.
  - Send the headers `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
- `POST /api/simulate`: if out of scope, return 422 with `{message, reasons}`. A `ValueError` from `apply_overrides` also returns 422.
- **Errors:** return JSON bodies that the UI can show, never a raw traceback.

## 5. M1: vertical slice (by about T0 + 5 h)

- **Replace stubs as owners merge.** Keep the pipeline green: after each merge to `main`, run the end-to-end test. If an owner's merge breaks the pipeline, tell them immediately (`BLOCKER` in their inbox) rather than patching their folder.
- **Second analysis path.** Make `reuse_research_from` plus `parameter_overrides` work. The UI's "Re-run with these assumptions" button depends on it.
- **Golden-path sanity check.** Add a `backend/scripts/smoke.py` that runs the golden query through the pipeline in the current mode and prints a stage-timing table and the verification summary. Agent-11 uses it.
- **`docs/ARCHITECTURE_NOTES.md`.** A decision log: one line per decision, with date, decision, reason and agent. Seed it with the decisions in this prompt.
- **Keep `openapi.json` current.** Regenerate it whenever an endpoint changes, and tell agent-7.

## 6. M2: hardening (by about T0 + 14 h)

- **Performance:**
  - `/api/simulate` under 1 s with 2,000 draws plus sensitivity. Profile it with agent-4.
  - `GET /api/analyses/{id}` under 100 ms. Cache the parsed `Analysis` in memory with an LRU of 32.
- **Structured logging.** Add `logging` with the `analysis_id` and stage on every line, and write live LLM usage (from agent-2) to the logs.
- **Concurrency safety.** Two simultaneous analyses must have no event-sequence collisions. Write a test with threads.
- **Input limits.**
  - Reject `monte_carlo_draws` above 20,000 and queries over 2,000 characters (already in the contracts).
  - Rate-limit `POST /api/analyses` to 6 per minute in live mode: a simple in-memory token bucket.
- **Startup checks.** `GET /api/health` reports whether the data and the cache directory exist. Log a warning at startup if any placeholder dataset is in use.
- **Contracts.** Process contract-change requests in #20 promptly. You are the default second reviewer for contract changes.

## 7. Coordination

- **Your reviewer** is agent-11. **You review** agent-11's PRs. You are also the second reviewer on any `contract-change` PR.
- **Who depends on you:** everyone does in M0, and agent-7 needs `openapi.json`. Post the merge of M0 in #8 immediately.
- **Escalation.** Any request to change Appendix B signatures goes through #20. Default to "add a new function; keep the old one."

## 8. Done means

- **CI:** `pytest` and `ruff` are green on `main`.
- **Golden path:** it runs end to end in mock mode, and the SSE stream works in the browser through agent-7's UI.
- **API surface:** every endpoint in section 9.9 behaves as specified, and `openapi.json` is current.
- **Logs:** the decision log is up to date.
- **Task Issues:** M1 and M2 are closed through PRs.
