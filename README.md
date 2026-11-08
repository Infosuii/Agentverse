# Jane Avenue

Jane Avenue is an AI-powered UK fiscal policy simulator built for government and policy analysts.
It combines live Gemini economic research (grounded in official sources with verbatim quote verification), historical UK tax precedents, and a transparent econometric engine with Monte Carlo uncertainty and independent verification.
Every displayed figure is traceable to a calculation step, verified quote, or curated official dataset, and the system withholds quantitative forecasts when a proposal falls outside validated scope or fails verification.

## Prerequisites

- **Python 3.13** (`py -3.13` on Windows or `python3.13` on macOS/Linux)
- **Node.js 22+** and `npm`
- **GitHub CLI (`gh`)** (for multi-agent collaboration workflows)

## Setup

```powershell
# 1. Clone the repository
git clone https://github.com/Infosuii/Agentverse.git
cd Agentverse

# 2. Copy the environment template
Copy-Item .env.example .env

# 3. Create Python virtual environment and install backend dependencies
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements-dev.txt

# 4. Install frontend dependencies
cd frontend
npm ci
cd ..
```

*(On macOS/Linux, use `cp .env.example .env`, `python3.13 -m venv .venv && source .venv/bin/activate`, or run `./scripts/dev.sh` directly.)*

## Running the App

### 1. Mock Mode (Deterministic, No API Key Required)

By default, `.env.example` sets `JANE_MODE=mock`, which runs the full pipeline deterministically against curated data and mock research fixtures without network calls:

```powershell
# Start both backend (:8000) and frontend (:5173)
.\scripts\dev.ps1
```

Or start each service in its own terminal:

```powershell
# Terminal 1 — Backend API (http://localhost:8000)
$env:JANE_MODE = "mock"
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m uvicorn jane_avenue.api.app:app --reload --port 8000

# Terminal 2 — Frontend UI (http://localhost:5173)
cd frontend
npm run dev
```

### 2. Cached Mode (Replay Verified Live Research Runs)

To replay committed live Gemini research traces from `data/research_cache/` with zero network latency:

```powershell
$env:JANE_MODE = "cached"
.\scripts\dev.ps1
```

### 3. Live Mode (Real Gemini Research + Grounding + Critic)

Set your Gemini API key in `.env` (never commit `.env`):

```ini
GEMINI_API_KEY=your_api_key_here
JANE_MODE=live
```

Then launch the stack with `.\scripts\dev.ps1` (Windows) or `./scripts/dev.sh` (macOS/Linux) and open `http://localhost:5173`.

## Running Checks & Tests

Run the full CI suite locally (backend `ruff` + `pytest`, frontend `typecheck` + `lint` + `test` + `build`, and OpenAPI schema drift check):

```powershell
.\scripts\check.ps1
```

*(On macOS/Linux: `./scripts/check.sh`)*

## Documentation

- **Product & Ownership Summary:** [PROJECT.md](PROJECT.md)
- **Full Build Specification:** [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md)
- **4-Minute Demo Script:** [docs/DEMO.md](docs/DEMO.md)
- **Operations & Runbook:** [docs/RUNBOOK.md](docs/RUNBOOK.md)
- **Historical Backtest & ML Evaluation:** [docs/EVALUATION.md](docs/EVALUATION.md)
- **UI & Design System (Forecast Confidence Studio look):** [docs/UI.md](docs/UI.md)
- **Multi-Agent Collaboration Protocol:** [AGENTS.md](AGENTS.md)

---

*Prototype. Not official government analysis.*
