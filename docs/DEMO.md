# Jane Avenue: 4-Minute Live Demo Script

> **Owner:** `agent-11`  
> **Target Duration:** 4 minutes (240 seconds)  
> **Primary Mode:** `cached` for the golden path (instant, deterministic replay of verified live Gemini research) + one live query (`live` mode) to showcase real-time Gemini Interactions API + Google Search grounding.

---

## Pre-Demo Checklist (T-10 minutes)

1. Ensure `.env` has `GEMINI_API_KEY` set and `JANE_RESEARCH_CACHE_DIR=data/research_cache` populated with the golden-path runs (`25% → 28%` and `25% → 23%`).
2. Start backend and frontend via `.\scripts\dev.ps1` (Windows) or `./scripts/dev.sh` (macOS/Linux).
3. Run the smoke check to confirm sub-second simulation and verified golden path:
   ```powershell
   .\.venv\Scripts\python.exe backend\scripts\smoke.py --mode cached --expect-approved --max-seconds 20
   ```
4. Open `http://localhost:5173` at 1440×900 resolution (100% zoom). Keep a second tab pre-opened to `/evaluation` and have the fallback screen recording ready on disk.

---

## Click-by-Click Walkthrough & Talking Points

### 0:00 – 0:40 · Policy Input, Parse Preview & Scope Gate (`/` — New Analysis)

1. **Click:** On `/`, click the example chip **"What would happen if the UK increased corporation tax from 25% to 28%?"** (or type it into `#policy-query-input`).
2. **Observe:** Within 600 ms, Card **2. Parsed Policy Specification & Scope Gate** appears:
   - Policy Type: `UK Corporation Tax — Main Rate`
   - Baseline Rate: `25%` → Proposed Rate: `28%` (`+3pp`)
   - Effective Date: `2027-04-01`, Horizon: `5 years`
   - Badge: **✓ Supported scope** (validated against historical UK CT changes 1983–2023).
   - Ambiguities panel explicitly lists defaults assumed by the parser (baseline rate from OBR baseline, effective date 1 April next fiscal year, 5-year horizon).
3. **Talking Point (Judging Criterion — Guardrails & Scope):**
   > *"Jane Avenue never guesses silently. Before touching an econometric model, it parses plain English into a structured `PolicySpec`, exposes every default assumption as an editable field, and checks the proposal against the historical range of UK Corporation Tax changes."*

---

### 0:40 – 1:25 · Autonomous Gemini Research & Verbatim Quote Verification (`/analyses/:id/research`)

1. **Click:** Click **Run analysis**.
2. **Observe:** The browser navigates to `/analyses/:id/research`.
   - The **6-stage pipeline progress bar** (`parsing` → `researching` → `precedents` → `modelling` → `verifying` → `reporting`) animates live over Server-Sent Events (SSE) with millisecond timings per stage.
   - The **Live Research Timeline** streams each step (`plan`, `search`, `fetch`, `extract`, `dataset_lookup`, `synthesis`) with source chips (`OBR`, `HMRC`, `ONS`, `IFS`, `Academic`).
   - Scroll to the **Extracted Evidence** cards: each quantitative claim displays a verbatim blockquote, a `Verified` badge (checked in code via exact/fuzzy substring matching against the SHA-256 snapshot of the fetched document), and a clickable `SourceChip`.
   - Point out the rose-bordered **AI Interpretation** cards (`ai_interpretation` badge), visually separated from empirical evidence.
3. **Talking Point (Judging Criterion — Live AI Research & Anti-Hallucination):**
   > *"Gemini never invents sources or forecast numbers. Using the `google-genai` Interactions API with Google Search grounding and document fetching, the agent extracts verbatim quotes from OBR, HMRC, and IFS publications. Python code then verifies every quote against the fetched text snapshot and drops any URL that didn't come from grounding metadata or a verified fetch."*

---

### 1:25 – 2:00 · Historical Precedents (`/analyses/:id/precedents`)

1. **Click:** Click the **Precedents** tab.
2. **Observe:**
   - The **UK CT Main Rate Timeline (1982–present)** highlights historical rate changes and marks the top 5 matches ranked by weighted similarity (direction 30%, magnitude 25%, rate level 15%, macro context z-score 20%, recency 10%).
   - Highlight **FY2023 (19% → 25%)**: show the side-by-side comparison of **Official Costing** (violet badge, ex-ante OBR costing) vs. **Observed Outcome** (slate badge, outturn HMRC receipts), plus amber confounder chips noting simultaneous *Full Expensing* introduction.
3. **Talking Point (Judging Criterion — Domain Rigour):**
   > *"Ex-ante Treasury costings and ex-post observed tax receipts are fundamentally different kinds of evidence. Jane Avenue never conflates them: every figure carries a colour-coded evidence-class badge and surfaces policy confounders like the 2023 full-expensing package."*

---

### 2:00 – 2:50 · Scenarios, Honest Uncertainty & Live Sliders (`/analyses/:id/scenarios` & `/assumptions`)

1. **Click:** Click the **Scenarios** tab.
2. **Observe:**
   - **Scenario paths:** Central (blue), Optimistic (green), and Pessimistic (red) projections across `revenue_static_gbp_bn`, `revenue_behavioural_gbp_bn`, `revenue_dynamic_gbp_bn`, `business_investment_pct`, and `gdp_level_pct`.
   - **Monte Carlo Fan Chart:** Shows 2,000 vectorised draws (`p5–p95` and `p25–p75` bands) with the verbatim honesty note: *"assumption-driven ranges, not statistical prediction intervals, and exclude model and data uncertainty"*. Toggle **Show backtest-calibrated interval** to show the empirical out-of-sample residual band.
   - **Tornado Chart:** Ranks which uncertain parameters drive the largest swing in Year-5 revenue and investment.
   - **Move a Slider:** Drag `taxable_profit_elasticity` or `full_expensing_coverage` in the slider panel. Within `< 300 ms`, `POST /api/simulate` returns 2,000 fresh draws and overlays the purple **Custom** series.
3. **Click:** Switch to the **Assumptions** tab and open the **Calculation Inspector ("How was this calculated?")**.
   - Select `business_investment_pct` for `2027-28`. Show the ordered `CalcStep` chain (`inv.user_cost.plant_machinery`, `inv.user_cost.structures`, `inv.user_cost.intangibles` → `ΔI_LR` → `ΔI_y`) with exact Hall–Jorgenson formulas, symbol inputs, and literature citations (`D-lit-devereux2014`, etc.).
4. **Talking Point (Judging Criterion — Transparency & Honest Uncertainty):**
   > *"The LLM never calculates a single projection. Every forecast comes from a pure-NumPy Hall–Jorgenson / King–Fullerton user-cost-of-capital and taxable-profit elasticity engine. Notice a crucial UK policy insight: under 100% full expensing, plant & machinery is marginal-rate neutral, so a CT hike bites through structures and intangibles. Every number can be inspected down to its exact equation and parameter source."*

---

### 2:50 – 3:25 · Independent Verification, Withheld Forecast & Policy Report (`/verification` & `/report`)

1. **Click:** Click the **Verification** tab on the 25% → 28% analysis, then click the **Report** tab.
   - Show the 18-check audit catalogue across `scope`, `citation`, `evidence`, `assumption`, `calculation` (independent engine recompute within `1e-9`), `data`, `causal_claim`, `uncertainty`, and `report` (`REPORT-001` verifying that every digit in Gemini's prose came from a `{{fig:id}}` code substitution).
   - Click **Download .md** on the Report tab to download the cited assessment.
2. **Click:** Navigate back to **New analysis** (`/`), click the third example chip **"Raise corporation tax to 45%"**, and click **Run analysis**.
   - Show the amber-hatched **`WithheldBanner` ("Quantitative forecast withheld")** across Overview, Scenarios, Verification, and Report: because a `+20pp` hike exceeds the validated historical precedent envelope (`SCOPE-001` blocking failure), Jane Avenue refuses to fabricate a quantitative forecast while still delivering historical context and research.
3. **Talking Point (Judging Criterion — Trustworthy AI & Refusal):**
   > *"When a policy proposal falls outside historical UK evidence—like a jump to 45%—or if a verification check fails, Jane Avenue withholds the quantitative forecast rather than extrapolating blindly."*

---

### 3:25 – 4:00 · Historical Backtest & Honest ML Evaluation (`/evaluation`)

1. **Click:** Click **Evaluation** in the top navigation bar (`/evaluation`).
2. **Observe:**
   - **Conditional Backtest Table & Chart:** Chronological train (`FY ≤ 2007`) vs. unseen test (`FY ≥ 2008`, covering the 2008–2017 cuts and 2023 rise) comparing `naive_growth`, `static`, `jane_behavioural`, `jane_calibrated`, `linear_regression`, and `lightgbm`.
   - **ML Honesty Card:** Shows whether LightGBM beat the simplest baseline out-of-sample on test MAE (`adopted` flag and transparent explanation of small-$n$ fiscal regime shifts).
   - **Research & Verifier Evaluation Cards:** Gold-set fact accuracy, HTTP-200 URL validity, verbatim quote match rate, 0 hallucinated sources, and 100% fault-injection detection across the verifier suite.
3. **Talking Point (Judging Criterion — Testing on Unseen Data):**
   > *"Finally, we evaluate every component on unseen data: a strictly chronological conditional backtest on historical UK CT changes since 2008, an ML experiment that is only adopted if it beats simple baselines out of sample, a 15-question official-source benchmark for the research agent, and fault-injection testing for the verifier."*

---

## Fallback Plan

| Failure Scenario | Immediate Action |
|---|---|
| **Live Gemini API latency / quota / Wi-Fi drop** | Ensure **Use cached research** is checked on `/`, or start with `JANE_MODE=cached`. The committed `data/research_cache/` replays real verified Gemini traces with 150 ms step pacing and zero network dependency. |
| **Cache miss on an ad-hoc judge query** | `run_research` automatically falls back `live → cache → mock` without raising an exception, emitting a transparent `warning` step in the timeline. |
| **Local machine / browser failure** | Play the pre-recorded 4-minute MP4 screen capture of the full golden path + withheld path + evaluation walkthrough while narrating live. |
