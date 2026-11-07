# Jane Avenue: Operations & Developer Runbook

> **Owner:** `agent-11`  
> This runbook covers fresh-machine setup, switching runtime modes (`mock`, `cached`, `live`), refreshing Gemini research caches (`agent-2`), regenerating curated UK fiscal datasets (`agent-6`), and rerunning the evaluation suite (`agent-10`).

---

## 1. Fresh-Machine Setup

### Prerequisites
- **Python 3.13** (`py -3.13 --version` on Windows or `python3.13 --version` on macOS/Linux)
- **Node.js 22+** (`node --version` and `npm --version`)
- **Git** and **GitHub CLI (`gh`)**

### Step-by-Step Installation

```powershell
# 1. Clone the repository
git clone https://github.com/Infosuii/Agentverse.git
cd Agentverse

# 2. Create local environment file from template
Copy-Item .env.example .env

# 3. Create Python 3.13 virtual environment and install backend dev dependencies
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements-dev.txt

# 4. Install frontend dependencies
cd frontend
npm ci
cd ..
```

*(On macOS/Linux, run `cp .env.example .env`, `python3.13 -m venv .venv && source .venv/bin/activate`, `pip install -r backend/requirements-dev.txt`, and `(cd frontend && npm ci)`.)*

---

## 2. Starting the Stack & Switching Runtime Modes

Jane Avenue supports three runtime modes controlled by `JANE_MODE` and `GEMINI_API_KEY`:

| Mode | Configuration | Behaviour |
|---|---|---|
| **`mock`** | `JANE_MODE=mock` (or `GEMINI_API_KEY` unset) | Deterministic offline fixtures, zero network calls. Used by CI, unit tests, and Playwright E2E. |
| **`cached`** | `JANE_MODE=cached` | Replays committed real Gemini research runs from `data/research_cache/<sha256>.json` with realistic step streaming. Ideal for reliable live demos. |
| **`live`** | `JANE_MODE=live` + `GEMINI_API_KEY=<key>` | Calls Gemini Interactions API (`gemini-3.8-flash` / `gemini-4-argon`), Google Search grounding, live URL fetching, LLM verification critic, and Gemini report drafting. |

### Launch Commands

**Windows PowerShell:**
```powershell
# Mock mode (default if no key is set)
$env:JANE_MODE = "mock"
.\scripts\dev.ps1

# Cached mode (for demo rehearsal)
$env:JANE_MODE = "cached"
.\scripts\dev.ps1

# Live mode (requires GEMINI_API_KEY in .env or environment)
$env:JANE_MODE = "live"
.\scripts\dev.ps1
```

**macOS / Linux:**
```bash
JANE_MODE=mock ./scripts/dev.sh
JANE_MODE=cached ./scripts/dev.sh
JANE_MODE=live ./scripts/dev.sh
```

- **Backend API & OpenAPI docs:** `http://localhost:8000/api/health` and `http://localhost:8000/docs`
- **Frontend UI:** `http://localhost:5173`

---

## 3. Running Local Verification & Smoke Checks

### Full CI Check Suite (`scripts/check`)
Runs `ruff check`, `pytest -m "not live"`, frontend `typecheck`, `lint`, `vitest`, `vite build`, and the OpenAPI schema drift check:
```powershell
.\scripts\check.ps1      # Windows PowerShell
./scripts/check.sh       # macOS / Linux
```
> **Working-Tree Hygiene Tip:** Running `pytest` executes `test_evaluation.py` (which refreshes timestamps in `backend/jane_avenue/evaluation/results/latest.json` and `docs/EVALUATION.md`), and running `scripts/check.ps1` on Windows touches CRLF line endings in `frontend/src/api/{openapi.json,schema.d.ts}`. Run `git checkout -- backend/jane_avenue/evaluation/results/latest.json docs/EVALUATION.md frontend/src/api/` after local check runs so your working tree stays clean.

### Golden-Path Pipeline Smoke Check (`backend/scripts/smoke.py`)
Runs the golden query (*"What would happen if the UK increased corporation tax from 25% to 28%?"*) through the full 6-stage pipeline against an in-memory SQLite store and prints stage timings, verification status, central projections, and any remaining placeholders:
```powershell
# Human-readable table output
.\.venv\Scripts\python.exe backend\scripts\smoke.py --mode mock

# CI / assertion mode (exits non-zero if forecast withheld or > 20s)
.\.venv\Scripts\python.exe backend\scripts\smoke.py --mode cached --json --expect-approved --max-seconds 20
```

### Playwright End-to-End Tests (`e2e/`)
```powershell
cd e2e
npm ci
npx playwright install --with-deps chromium
npx playwright test
```

---

## 4. Regenerating OpenAPI Schema & Frontend Types (`agent-1` / `agent-7`)

Whenever a FastAPI route or Pydantic contract in `backend/jane_avenue/` changes:
```powershell
.\.venv\Scripts\python.exe backend\scripts\export_openapi.py
cd frontend
npm run gen:api
cd ..
git diff --exit-code frontend/src/api/
```

---

## 5. Refreshing Gemini Research Caches (`agent-2`)

Cached live research runs live in `data/research_cache/<cache_key>.json`, where `<cache_key>` is the SHA-256 of the canonical JSON of `{policy_type, baseline_rate_pct, proposed_rate_pct, horizon_years}`.

To record or refresh the committed golden-path cache files with a live `GEMINI_API_KEY`:
```powershell
$env:GEMINI_API_KEY = "your_live_key"
$env:JANE_MODE = "live"

# 1. Golden path hike (25% -> 28%, horizon 5)
.\.venv\Scripts\python.exe backend\scripts\smoke.py --mode live --no-cache --query "What would happen if the UK increased corporation tax from 25% to 28%?"

# 2. Cut scenario (25% -> 23%, horizon 5)
.\.venv\Scripts\python.exe backend\scripts\smoke.py --mode live --no-cache --query "Cut corporation tax from 25% to 23% from April 2027"

# 3. Modest hike scenario (25% -> 26%, horizon 5)
.\.venv\Scripts\python.exe backend\scripts\smoke.py --mode live --no-cache --query "Increase corporation tax from 25% to 26% from April 2027"
```
Inspect the generated JSON files in `data/research_cache/` to verify that `verification_status == "verified"` on quantitative quotes and that at least 6 Tier-1/Tier-2 sources are present before committing.

---

## 6. Regenerating Curated Datasets (`agent-6`)

All curated CSVs and `.meta.json` provenance files in `data/curated/` are built from official HMRC, OBR, ONS, Bank of England, and IFS sources via scripts in `data/scripts/` (raw downloads go to git-ignored `data/raw/`):

```powershell
# Run the full data fetch + build pipeline
.\.venv\Scripts\python.exe data\scripts\build_all.py

# Verify dataset metadata, source resolution, and precedent matching tests
.\.venv\Scripts\python.exe -m pytest backend/tests/data backend/tests/precedents
```
See [docs/DATA.md](DATA.md) for dataset-by-dataset provenance, licences (Open Government Licence v3.0), and table references.

---

## 7. Rerunning the Historical Backtest & ML Evaluation (`agent-10`)

The offline evaluation runner executes the chronological CT receipts backtest (`FY <= 2007` train, `FY >= 2008` test), the LightGBM out-of-sample experiment, the research-agent citation benchmark, and the 18-fault verifier injection suite, writing `backend/jane_avenue/evaluation/results/latest.json` and updating `docs/EVALUATION.md`:

```powershell
# Offline evaluation (uses committed research gold runs; deterministic, no live API calls)
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m jane_avenue.evaluation.run

# Live evaluation (re-runs the 15 gold research questions live via Gemini before scoring)
$env:GEMINI_API_KEY = "your_live_key"
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m jane_avenue.evaluation.run --live

# Run evaluation unit tests
.\.venv\Scripts\python.exe -m pytest backend/tests/evaluation
```
