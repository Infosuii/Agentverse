# Jane Avenue

**Jane Avenue** is an AI-powered UK fiscal policy simulator and economic research platform built for HM Treasury, HMRC, and OBR policy analysts.

Analysts enter a proposed UK fiscal reform in plain English—for example, *"What would happen if the UK increased corporation tax from 25% to 28%?"* or *"Cut the basic rate of income tax from 20% to 19%"*. Jane Avenue parses the proposal against a historical scope gate, dispatches an autonomous Gemini research agent grounded in official UK primary sources, matches historical UK fiscal precedents, runs a deterministic pure-NumPy econometric and ready-reckoner simulation engine with Monte Carlo uncertainty, audits every claim and calculation through an independent 18-check verifier, and compiles a publication-grade policy assessment.

Every displayed number is traceable to an explicit calculation step, a SHA-256 verified verbatim quote, or a curated official dataset (`ONS`, `OBR`, `HMRC`, `BoE`, `IFS`). When a proposal falls outside validated historical bounds or fails a blocking verification check, the system **withholds the quantitative forecast (`forecast_withheld`)** rather than extrapolating blindly.

---

## Why Jane Avenue?

| Approach | Strength | Failure Mode for Policy Analysts |
|---|---|---|
| **General-Purpose Chatbots** | Fast prose synthesis | Hallucinate £bn figures, fabricate URLs, and conflate ex-ante costings with observed tax receipts. |
| **Static Treasury Spreadsheets** | Transparent arithmetic | Miss qualitative institutional confounders (e.g., the April 2023 introduction of 100% *Full Expensing*) and hide parameter uncertainty behind single point estimates. |
| **Jane Avenue** | **Hybrid AI Research + Structural Econometrics + Independent Verification** | **Gemini never calculates a number.** Pure-NumPy engines compute every projection, Python verifies every verbatim quote against fetched document snapshots, and an 18-check verifier blocks unsupported forecasts. |

---

## System Architecture: The 6-Stage Guardrailed Pipeline

```text
Plain-English Policy Query
   │
   ▼
1. Policy Parser & Scope Gate (backend/jane_avenue/policy/)
   │  • Parses natural language into a structured PolicySpec (Contract v1.2.0)
   │  • Surfaces all parser defaults & ambiguities as editable fields before running
   │  • Validates against UK historical bounds, rejecting negative rates, non-UK taxes & devolved rates
   ▼
2. Autonomous Gemini Research Agent (backend/jane_avenue/research/ + llm/)
   │  • Uses google-genai Interactions API (gemini-3.8-flash / gemini-4-argon, store=False)
   │  • Google Search grounding + official URL fetch (gov.uk, obr.uk, ons.gov.uk, ifs.org.uk, parliament.uk)
   │  • Verifies every quantitative quote verbatim in Python against SHA-256 document text snapshots
   │  • Surfaces conflicting evidence explicitly rather than averaging it away
   ▼
3. Historical Precedents Matcher (backend/jane_avenue/precedents/ + data/)
   │  • Scores reforms by direction (0.30), magnitude (0.25), rate level (0.15), macro z-score (0.20), recency (0.10)
   │  • Covers 16 implemented UK CT rate reforms (1983–2023) + 1,736 wider UK fiscal reforms,
   │    6,928 Treasury scorecard costings, and 1,164 ONS/OBR outturns (back to 1967–68)
   │  • Strictly separates ex-ante Official Costings (OBR/HMT) from ex-post Observed Outcomes (ONS/HMRC)
   ▼
4. Econometric & Ready-Reckoner Simulation Engines (backend/jane_avenue/engine/ + simulation/)
   │  • Pure NumPy — deterministic, zero I/O, zero LLM involvement
   │  • Corporation Tax Structural Engine (engine-1.0.0): Static yield, isoelastic taxable-profit shifting
   │    (ε = 0.20), Hall–Jorgenson / King–Fullerton user cost of capital across Plant & Machinery
   │    (capturing 100% Full Expensing marginal neutrality), Structures (3% SBA), and Intangibles,
   │    capital accumulation, partial-equilibrium GDP feedback, and Devereux–Griffith EMTR/EATR steps
   │  • HMRC Ready-Reckoner Engine (reckoner-1.0.0): 17 UK tax & benefit measures (225 HMRC June 2025 rows)
   │    with piecewise-linear scaling, nonlinear CGT Laffer responses, and nominal GDP uprating
   │  • 2,000-draw Monte Carlo simulation with yearly stochastic profit-base shocks + Tornado sensitivity (< 30 ms)
   ▼
5. Independent 18-Check Verifier (backend/jane_avenue/verification/)
   │  • Recomputes central engine outputs to within 1e-9 (CALC-001)
   │  • Audits source tiers & verbatim quotes (CITE-001..003), evidence sufficiency (EVID-001..004),
   │    assumption bounds (ASSUMP-001..002), zero data placeholders (DATA-001..002), causal wording (CAUSAL-001),
   │    uncertainty bands (UNC-001), and report digit provenance (REPORT-001)
   │  • Enforces forecast_withheld whenever any blocking check fails
   ▼
6. Evidence-Backed Policy Assessment (backend/jane_avenue/report/)
      • Gemini drafts neutral analyst prose using {{fig:id}} placeholders
      • Python substitutes every figure from the engine and verifies zero raw numbers were invented
```

---

## Policy Scope & Economic Modelling Coverage

Since Contract `1.2.0`, Jane Avenue supports three tiers of UK fiscal policy analysis:

1. **UK Corporation Tax Main Rate & Small Profits Rate (`engine-1.0.0`):**
   - Full structural multi-channel simulation over 1–10 fiscal years against the **OBR October 2026 Economic and Fiscal Outlook** baseline (`2025-26` to `2031-32`).
   - Captures the **Full-Expensing Neutrality Theorem**: under a 100% first-year capital allowance ($z = 1$), the Hall–Jorgenson user cost of capital $c_a(t) = (r + \delta_a)(1 - t \cdot z_a)/(1 - t)$ simplifies to $r + \delta_a$, making covered plant & machinery investment invariant to the statutory CT rate at the margin while the investment drag operates through structures ($z = 0.299$) and intangibles ($z = 0.720$).
   - **Golden-Path Benchmark (`25% → 28%` CT from April 2027, 5-year horizon):**
     - **Static Revenue:** `+£7.28bn` (Year 1) → `+£14.39bn` (Year 5)
     - **Behavioural Revenue ($\varepsilon = 0.20$):** `+£7.00bn` (Year 1) → `+£13.30bn` (Year 5)
     - **Dynamic Revenue:** `+£6.99bn` (Year 1) → `+£13.16bn` (Year 5)
     - **Business Investment:** `-0.29%` / `-£1.00bn` (Year 1) → `-0.56%` / `-£2.19bn` (Year 5)
     - **Real GDP Level:** `-0.016%` (Year 1) → `-0.104%` (Year 5)
     - **User Cost of Capital:** `+0.97%` (`Devereux–Griffith EATR: 21.7% → 24.3%`)
2. **17 HMRC Ready-Reckoner Tax & Benefit Measures (`reckoner-1.0.0`):**
   - Reconciled to `1e-9` against HMRC's *Direct effects of illustrative tax changes (June 2025)* (`225` official costing rows):
     - **Income Tax:** Basic Rate (`20%`), Higher Rate (`40%`), Additional Rate (`45%`, asymmetric), Personal Allowance (`£12,570`, piecewise linear)
     - **National Insurance Contributions:** Employee Main Rate (`8%`), Employer Rate (`15%`), Self-Employed Class 4 (`6%`)
     - **Capital & Wealth Taxes:** CGT Lower Rate (`18%`) & Higher Rate (`24%`, nonlinear Laffer curve), Inheritance Tax (`40%`)
     - **Indirect Taxes & Duties:** VAT Standard (`20%`) & Reduced (`5%`), Insurance Premium Tax (`12%`), Fuel Duty (`52.95p/L`), Alcohol Duty, Tobacco Duty
     - **Benefits:** Child Benefit (`£27.05/wk`, asymmetric)
3. **Wider UK Fiscal Proposals (`fiscal_other` — Guardrailed Research Mode):**
   - Public spending proposals, minimum wage changes, and uncosted tax reforms (or extreme CT proposals such as `Raise corporation tax to 45%`, exceeding the `15pp` single-reform historical step limit) still receive live Gemini research and historical precedent matching, while `SCOPE-001` **withholds the quantitative forecast (`forecast_withheld = True`)**.

---

## Out-of-Sample Evaluation, Backtesting & Honest ML Rejection

All evaluation metrics are reproducible offline via `python -m jane_avenue.evaluation.run` and viewable in the app at `/evaluation` (see [docs/EVALUATION.md](docs/EVALUATION.md) and [docs/HMRC_CALIBRATION_AND_STRESS_TEST.md](docs/HMRC_CALIBRATION_AND_STRESS_TEST.md)):

- **Chronological Corporation Tax Backtest (`FY1983-84..FY2007-08` Train → `FY2008-09..FY2024-25` Unseen Test, $n = 17$):**
  - Evaluates 1-year-ahead CT receipts conditional on realised profit growth (`pnfc_gos`) across the 2008–2017 rate cuts and the April 2023 `19% → 25%` hike.
  - **`jane_behavioural` ($\varepsilon = 0.20, s = 0.87$):** **£5.54bn Test MAE (9.36% MAPE)**, outperforming `static` (**£5.71bn**, 9.53% MAPE), `naive_growth` (**£6.56bn**), and `linear_regression` (**£8.35bn**).
  - **Empirical Interval Coverage:** Leave-one-out 90% empirical residual interval covers **14/17 (82.3%)** of unseen post-2008 outcomes.
  - **External HMRC Calibration (`+1pp` CT Main Rate):** Matches HMRC's June 2025 Ready Reckoner within **3.6% (`£3.76bn` vs `£3.90bn`)** in Year 2 and **1.0% (`£3.96bn` vs `£4.00bn`)** in Year 3.
- **ML Honesty Rule (`LightGBMRegressor`, `adopted = False`):**
  - A regularised gradient-boosted tree model (`max_depth=2, num_leaves=3, L1=1.0, L2=2.0`) achieves a lower in-sample train MAE (**£3.27bn**) on `FY <= 2007` but degrades to **£6.33bn** out-of-sample test MAE (`+93%` error growth) because $n = 24$ annual observations cannot support piecewise-constant tree extrapolation across post-2008 fiscal regime shifts. Per project rules, LightGBM is **transparently rejected (`adopted = False`)** and not wired into the live simulator.
- **Research Agent & Verifier Benchmarks:**
  - **15 / 15 (100%)** factual accuracy on the 15-question UK CT benchmark.
  - **15 / 15 (100%)** HTTP-200 URL validity and **15 / 15 (100%)** verbatim quote verification (`0` hallucinated sources, `100%` Tier-1 official source share).
  - **18 / 18 (100%)** fault-injection detection across all 18 verifier checks with **0%** clean-case false positives.

---

## Governance, Privacy & Execution Boundaries

- **Local Execution:** The econometric engines (`engine/`), Monte Carlo & tornado simulator (`simulation/`), 18-check verifier (`verification/`), and SQLite persistence (`store/`) run **100% locally on-device**.
- **Cloud Boundary (`live` mode only):** Only the parsed policy query is sent to the Google Gemini API (`google-genai`) with **`store=False`**, ensuring zero prompt or user-data retention.
- **Human-in-the-Loop Oversight:** Analysts inspect and can override every parsed policy parameter before execution, adjust any of the 19 structural assumptions via live sliders, and audit every verification check and source snapshot before exporting a report.

---

## Prerequisites

- **Python 3.13** (`py -3.13 --version` on Windows, `python3.13 --version` on macOS/Linux)
- **Node.js 22+** and `npm`
- **Git** (and `gh` CLI if using multi-agent collaboration workflows)

---

## How to Run the Project

### Step 1: Clone & Configure Environment

```powershell
# 1. Clone the repository
git clone https://github.com/Infosuii/Agentverse.git
cd Agentverse

# 2. Create your local .env from the template (never commit .env!)
Copy-Item .env.example .env
```
*(On macOS/Linux: `cp .env.example .env`)*

If you want to run live Gemini research, open `.env` and paste your API key:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 2: One-Command Quickstart (`scripts/dev.ps1` / `scripts/dev.sh`)

The development launcher script **automatically creates `.venv`**, installs all Python backend dependencies (`backend/requirements-dev.txt`, including `fastapi`, `numpy`, `scipy`, `statsmodels`, `lightgbm`, `matplotlib`, `google-genai`), installs `frontend/node_modules` if missing, and starts both the **FastAPI backend (`http://localhost:8000`)** and the **Vite React frontend (`http://localhost:5173`)**.

By default, if `JANE_MODE` is not set in the environment, Jane Avenue **auto-detects the runtime mode**:
- **`live` mode** if `GEMINI_API_KEY` is set in `.env`
- **`mock` mode** if `GEMINI_API_KEY` is empty

Choose any of the three modes below:

#### Option A: Live Mode (Real-Time Gemini Interactions API + Google Search Grounding)
Requires `GEMINI_API_KEY` in `.env`:
```powershell
# Windows PowerShell
$env:JANE_MODE = "live"
.\scripts\dev.ps1
```
```bash
# macOS / Linux
JANE_MODE=live ./scripts/dev.sh
```

#### Option B: Cached Mode (Recommended for Demos — Instant Replay of Verified Live Gemini Runs)
Replays committed SHA-256 verified Gemini research traces from `data/research_cache/` (including the `25% → 28%` golden path, `25% → 23%` cut, `25% → 26%` hike, and `25% → 45%` guardrail refusal) in ~5 seconds with zero network dependency, falling back automatically (`live → cache → mock`) on uncached queries:
```powershell
# Windows PowerShell
$env:JANE_MODE = "cached"
.\scripts\dev.ps1
```
```bash
# macOS / Linux
JANE_MODE=cached ./scripts/dev.sh
```
*(You can also toggle **"Use cached research"** directly on the New Analysis page in the UI.)*

#### Option C: Mock Mode (Deterministic Offline Mode — No API Key Required)
Runs the full 6-stage pipeline with real curated datasets and the real econometric engine against deterministic mock research fixtures in under 1 second:
```powershell
# Windows PowerShell
$env:JANE_MODE = "mock"
.\scripts\dev.ps1
```
```bash
# macOS / Linux
JANE_MODE=mock ./scripts/dev.sh
```

Once running, open:
- **Frontend Application:** `http://localhost:5173`
- **Backend Health Check:** `http://localhost:8000/api/health`
- **Interactive OpenAPI / Swagger Docs:** `http://localhost:8000/docs`

---

### Alternative: Running Backend & Frontend in Separate Terminals

If you prefer to manage the backend and frontend processes separately:

**1. First-time dependency installation:**
```powershell
# Create virtual environment and install backend dependencies
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements-dev.txt

# Install frontend dependencies
cd frontend
npm ci
cd ..
```

**2. Start Terminal 1 — Backend API (`http://localhost:8000`):**
```powershell
# Windows PowerShell (omit $env:JANE_MODE to auto-detect from .env, or set "live" / "cached" / "mock")
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m uvicorn jane_avenue.api.app:app --reload --port 8000
```
```bash
# macOS / Linux
PYTHONPATH=backend ./.venv/bin/python -m uvicorn jane_avenue.api.app:app --reload --port 8000
```

**3. Start Terminal 2 — Frontend UI (`http://localhost:5173`):**
```powershell
cd frontend
npm run dev
```

---

## Testing, Verification & Data Scripts

### 1. Full CI Check Suite (`scripts/check`)
Runs backend `ruff check` + `pytest -m "not live"`, frontend `tsc --noEmit` + `eslint` + `vitest` + `vite build`, and the OpenAPI schema drift check:
```powershell
.\scripts\check.ps1      # Windows PowerShell
./scripts/check.sh       # macOS / Linux
```

### 2. Golden-Path Pipeline Smoke Check (`backend/scripts/smoke.py`)
Runs the `25% → 28%` Corporation Tax golden query end-to-end against an in-memory SQLite store and prints stage timings, verification status, central projections, and placeholder counts:
```powershell
# Human-readable summary table
.\.venv\Scripts\python.exe backend\scripts\smoke.py --mode mock

# Strict CI / pre-demo assertion (verifies forecast approved and runtime < 20s)
.\.venv\Scripts\python.exe backend\scripts\smoke.py --mode cached --json --expect-approved --max-seconds 20
```

### 3. Re-running the Historical Backtest, ML Experiment & HMRC Calibration Suite
```powershell
$env:PYTHONPATH = "backend"

# Run the offline evaluation suite (writes backend/jane_avenue/evaluation/results/latest.json & docs/EVALUATION.md)
.\.venv\Scripts\python.exe -m jane_avenue.evaluation.run

# Run the HMRC June 2025 Ready-Reckoner calibration & stress-test suite
.\.venv\Scripts\python.exe -m pytest backend/tests/evaluation/test_hmrc_calibration_and_stress.py -v
```

### 4. Playwright End-to-End Browser Tests (`e2e/`)
*(Stop `dev.ps1` / `dev.sh` first so port `:8000` is free for Playwright's isolated mock backend.)*
```powershell
cd e2e
npm ci
npx playwright install --with-deps chromium
npx playwright test
```

### 5. Rebuilding Curated Official Datasets & OpenAPI Types
```powershell
# Rebuild curated CSVs & provenance metadata in data/curated/ (use --offline to rebuild from cached raw files)
.\.venv\Scripts\python.exe data\scripts\build_all.py --offline

# Export OpenAPI schema and regenerate TypeScript types in frontend/src/api/
.\.venv\Scripts\python.exe backend\scripts\export_openapi.py
cd frontend && npm run gen:api && cd ..
```

---

## Repository Structure

```text
Agentverse/
├── backend/
│   ├── jane_avenue/
│   │   ├── api/            # FastAPI app, REST routes, SSE event stream, rate limiter
│   │   ├── charts/         # Server-rendered Matplotlib Monte Carlo trajectory fan charts
│   │   ├── contracts/      # Frozen Pydantic v2 data contracts (v1.2.0)
│   │   ├── data/           # Curated dataset loader, provenance registry & source lookup
│   │   ├── engine/         # Pure-NumPy CT structural model (core.py) & HMRC ready reckoner (reckoner.py)
│   │   ├── evaluation/     # Chronological CT backtest, LightGBM challenger, citation & verifier evals
│   │   ├── llm/            # Google GenAI Interactions API gateway (gemini-3.8-flash / gemini-4-argon)
│   │   ├── orchestrator/   # 6-stage pipeline coordinator & structured log context
│   │   ├── policy/         # Natural-language policy parser, 17-measure matcher & scope gate
│   │   ├── precedents/     # Historical UK CT & wider fiscal precedent similarity engines
│   │   ├── report/         # Template & Gemini narrative report generator with {{fig:id}} substitution
│   │   ├── research/       # Autonomous Gemini research loop, quote verifier & SHA-256 cache
│   │   ├── simulation/     # Central/Optimistic/Pessimistic scenarios, 2,000-draw Monte Carlo & Tornado
│   │   ├── store/          # Thread-safe SQLite repository & LRU cache
│   │   └── verification/   # Independent 18-check verification engine (SCOPE, CITE, EVID, ASSUMP, CALC, DATA, CAUSAL, UNC, REPORT)
│   ├── scripts/            # smoke.py and export_openapi.py utilities
│   └── tests/              # Unit, integration, contract, calibration & stress test suites
├── data/
│   ├── curated/            # Official ONS/OBR/HMRC datasets (.csv + .meta.json + provenance.json)
│   ├── research_cache/     # Committed SHA-256 verified Gemini research traces for cached mode
│   └── scripts/            # Reproducible official data fetch & build pipelines
├── docs/                   # Architecture, evaluation, data provenance, UI design & demo documentation
├── e2e/                    # Playwright end-to-end browser test suite
├── frontend/
│   └── src/
│       ├── api/            # OpenAPI-generated TypeScript schema & typed API client
│       ├── app/            # Router, layout & Forecast Confidence Studio shell
│       ├── components/     # Recharts fan/tornado charts, ProvenanceNumber popover, UI primitives & theme toggle
│       └── features/       # New Analysis, Overview, Research, Precedents, Scenarios, Assumptions, Verification, Report, Evaluation, History
└── scripts/                # Cross-platform dev.ps1 / dev.sh and check.ps1 / check.sh scripts
```

---

## Documentation Index

- **Product & Workstream Ownership:** [PROJECT.md](PROJECT.md)
- **Full Technical Build Specification:** [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md)
- **Architecture Decision Log & Econometric Model Card:** [docs/ARCHITECTURE_NOTES.md](docs/ARCHITECTURE_NOTES.md)
- **4-Minute Live Demo Script:** [docs/DEMO.md](docs/DEMO.md)
- **Pitch Notes & Judging Criteria Mapping:** [docs/PITCH_NOTES.md](docs/PITCH_NOTES.md)
- **Operations & Developer Runbook:** [docs/RUNBOOK.md](docs/RUNBOOK.md)
- **Historical Backtest & ML Evaluation Report:** [docs/EVALUATION.md](docs/EVALUATION.md)
- **HMRC Ready-Reckoner Calibration & Stress-Test Report:** [docs/HMRC_CALIBRATION_AND_STRESS_TEST.md](docs/HMRC_CALIBRATION_AND_STRESS_TEST.md)
- **Curated Data Provenance & Official Sources:** [docs/DATA.md](docs/DATA.md)
- **UI & Design System (Forecast Confidence Studio + Light/Dark Theme):** [docs/UI.md](docs/UI.md)
- **Multi-Agent Collaboration Protocol:** [AGENTS.md](AGENTS.md)

---

*Prototype built for fiscal policy analysis evaluation. Not official HM Treasury, HMRC, or OBR analysis.*
