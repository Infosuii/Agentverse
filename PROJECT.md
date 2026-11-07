# PROJECT.md: what we are building (read after AGENTS.md)

`AGENTS.md` is the authoritative **collaboration** protocol: identity, Issues, branches and PRs. This file is the authoritative **product** summary: what we build, who owns which paths, who reviews whom, and the product rules. The full specification is [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md).

## Product: Jane Avenue

Jane Avenue is an AI-powered UK fiscal policy simulator. An analyst types a proposed tax policy in plain English, for example *"What would happen if the UK increased corporation tax from 25% to 28%?"*. The system then works through these stages:

1. **Parse.** The request is parsed into a structured policy and checked against the scope gate.
2. **Research.** A Gemini agent researches the policy live, using Google Search grounding and fetched official documents, and produces evidence with verbatim, verified quotes.
3. **Precedents.** It retrieves historical UK precedents.
4. **Model.** A transparent econometric engine runs the central, optimistic and pessimistic scenarios, a Monte Carlo simulation and a tornado sensitivity analysis.
5. **Verify.** An independent verifier audits everything. It can withhold the forecast.
6. **Report.** The system writes an evidence-backed assessment. Gemini writes the prose, and code inserts every number.

Historical evaluation shows how well the methods work against simple baselines.

**Hackathon scope:** UK corporation tax main rate, fully working end to end. VAT and FTSE 100 are post-M3 stretch goals only.

## Stack

- **Backend:** Python 3.13, FastAPI, Pydantic v2, numpy/pandas/scipy/statsmodels/lightgbm, SQLite, `google-genai>=2.30.1` (Interactions API).
- **Frontend:** React, Vite, TypeScript, Tailwind v4, React Router, TanStack Query, Recharts, OpenAPI-generated types.
- **Ports:** backend `:8000`, frontend `:5173` (proxy `/api`).

## Workstreams, ownership and reviewers

Only the owner edits a path. Anything outside your paths needs agreement first, either in the owner's inbox or in Issue #8.

| Agent | Tool | Workstream | Owns | Reviewer |
|---|---|---|---|---|
| agent-1 | Claude Code | Backend platform | `backend/` packaging, `config.py`, `api/`, `orchestrator/`, `store/`, `backend/scripts/`, `tests/{conftest,api,orchestrator,contracts}`, `docs/ARCHITECTURE_NOTES.md`; `contracts/` in M0 only | agent-11 |
| agent-2 | Claude Code | Gemini gateway and research agent | `llm/`, `research/`, `data/research_cache/`, `tests/{llm,research}` | agent-5 |
| agent-3 | Claude Code | Econometric engine and parameters | `engine/`, `tests/engine/`, `data/curated/literature_sources.csv` | agent-4 |
| agent-4 | Claude Code | Scenarios, Monte Carlo, sensitivity | `simulation/`, `tests/simulation/` | agent-3 |
| agent-5 | Claude Code | Policy parser, scope gate, verification | `policy/`, `verification/`, `tests/{policy,verification}` | agent-2 |
| agent-6 | Codex | Curated data and precedents | `data/` (except `research_cache/` and `literature_sources.csv`), `backend/jane_avenue/data/`, `precedents/`, `tests/{data,precedents}`, `docs/DATA.md` | agent-10 |
| agent-7 | Antigravity | Frontend foundation and entry flow | `frontend/` scaffold and config, `src/{app,api,components/ui,lib}`, `src/features/{new-analysis,analysis,research,history}` | agent-8 |
| agent-8 | Antigravity | Scenario explorer, charts, assumptions | `src/components/charts/`, `src/features/{scenarios,assumptions}` | agent-9 |
| agent-9 | Antigravity | Precedents, verification and report views; report generator | `backend/jane_avenue/report/`, `tests/report/`, `src/features/{precedents,verification,report}` | agent-7 |
| agent-10 | Antigravity | Evaluation and ML | `backend/jane_avenue/evaluation/`, `tests/evaluation/`, `docs/EVALUATION.md`, `src/features/evaluation/` | agent-3 |
| agent-11 | Antigravity | Integration lead: CI, QA, demo | `.github/`, `.env.example`, `.gitignore`, `README.md`, `scripts/`, `e2e/`, `docs/{DEMO,RUNBOOK,PITCH_NOTES}.md` | agent-1 |

Unless noted otherwise, backend paths are relative to `backend/jane_avenue/` and frontend paths to `frontend/`.

The following are owned by the setup (the human), and changes to them go through #8: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `PROJECT.md`, `.agents/`, `docs/MASTER_PROMPT.md` and `docs/prompts/`.

## Contract changes

`backend/jane_avenue/contracts/` belongs to nobody after M0. To change it:

1. Post a `REQUEST` in Issue #20.
2. Open a PR labelled `contract-change`.
3. Get two agent approvals. Additive optional fields need only one, and agent-1 is the default second reviewer.
4. In the same PR, update the tests and regenerate the API types: run `python backend/scripts/export_openapi.py`, then `cd frontend && npm run gen:api`.

Changes that break the module signatures in MASTER_PROMPT Appendix B are not allowed. Add a new function instead.

## Product rules (non-negotiable; full list in MASTER_PROMPT section 3)

- **Gemini never produces forecast numbers.** Numbers come from `engine/` and `simulation/`. Gemini may extract quoted figures from sources and write prose that uses `{{fig:<id>}}` placeholders.
- **No invented sources.** Sources come only from Google Search grounding metadata, fetched URLs or curated datasets. Quotes are verified in code.
- **Every number is traceable** to a calculation step, a piece of evidence or a dataset row.
- **Every number is labelled** with one of: observed outcome, official costing, model scenario, assumption or AI interpretation.
- **Decline when out of scope** or when a blocking verification check fails (`forecast_withheld`).
- **Monte Carlo bands are assumption-driven ranges.** Call something a "prediction interval" only if the backtest calibrates it.
- **Tests never call live APIs.** `JANE_MODE=mock` is deterministic, and CI has no secrets.
- **Never invent data.** Anything unverified is marked `is_placeholder=True`, and verification surfaces it.
- **Never commit** `.env`, keys, raw downloads (`data/raw/`) or files over 5 MB.
- **Gemini usage:**
  - Go through `backend/jane_avenue/llm/` only.
  - Models: `gemini-3.8-flash` (fast) and `gemini-4-argon` (deep), configurable through the environment.
  - Use `store=False` by default.
  - Read the docs; don't guess API calls.
- **Keep `main` green**, and keep the Appendix B entrypoint signatures stable.

## Milestones

| Milestone | Deadline | Goal |
|---|---|---|
| M0 skeleton | T0 + 1 h | Agents 1, 7 and 11 |
| M1 vertical slice | T0 + 5 h | The golden path in mock mode with real data and the real engine |
| M2 feature complete | T0 + 14 h | |
| M3 demo-ready | T0 + 20 h | |

Agent-11 posts the real clock times in #8.

## Commands (once the skeleton lands)

```
# backend (Windows PowerShell; use source .venv/bin/activate on macOS/Linux)
cd backend
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
ruff check . ; pytest
uvicorn jane_avenue.api.app:app --reload --port 8000

# frontend
cd frontend
npm ci
npm run gen:api
npm run dev            # http://localhost:5173
npm run typecheck ; npm test -- --run ; npm run build
```
