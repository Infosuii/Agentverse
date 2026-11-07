# Jane Avenue: 4-Minute Live Demo Script

> **Owner:** `agent-11`  
> **Target Duration:** 4 minutes (240 seconds)  
> **Primary Mode:** `cached` for the golden path (instant, deterministic replay of verified live Gemini research) + one live query (`live` mode) to showcase real-time Gemini Interactions API + Google Search grounding.

---

## Pre-Demo Checklist (T-10 minutes)

1. Ensure `.env` has `GEMINI_API_KEY` set and `JANE_RESEARCH_CACHE_DIR=data/research_cache` populated with the 3 bundled cached research runs (`25% -> 28%`, `25% -> 23%`, and `25% -> 26%`). There is no cached run for the `25% -> 45%` guardrail demo: in `cached` mode its Research tab shows the labelled mock fixture ("No cached research for this policy") and a **Placeholder (unverified)** badge. Record one with a live key before the demo, or present that step as a scope-gate demo only.
2. Start backend and frontend via `.\scripts\dev.ps1` (Windows) or `./scripts/dev.sh` (macOS/Linux).
3. Run the smoke check to confirm sub-second simulation and verified golden path:
   ```powershell
   .\.venv\Scripts\python.exe backend\scripts\smoke.py --mode cached --expect-approved --max-seconds 20
   ```
4. Open `http://localhost:5173` at 1440×900 resolution (100% zoom). Keep a second tab pre-opened to `/evaluation` and have the fallback screen recording ready on disk.

---

## Click-by-Click Walkthrough & Talking Points

### 0:00 – 0:40 · Policy Input, Parse Preview & Scope Gate (`/` — New Analysis)

1. **Click:** On `/`, click the example chip **"What would happen if the UK increased corporation tax from 25% to 28%?"** (or type *"What would happen if the UK increased corporation tax from 25% to 28%?"* into the policy input).
2. **Observe:** Within 300 ms, the **Parsed Policy Specification & Scope Gate** card appears:
   - Policy Type: `corporation_tax_main_rate`
   - Baseline Rate: `25%` -> Proposed Rate: `28%` (`+3pp`)
   - Effective Date: `2027-04-01`, Horizon: `5 years` (`2027-28` to `2031-32`)
   - Badge: **Supported scope** (validated against historical UK CT changes `1983–2023`, rate bounds `19%–52%`, single-reform step limit `15pp`).
   - Ambiguities & Defaults panel explicitly lists defaults assumed by the parser.
3. **Talking Point (Judging Criterion — Guardrails & Scope):**
   > *"Jane Avenue never guesses silently. Before touching an econometric model, it parses plain English into a structured `PolicyMeasure`, exposes every default assumption as an editable field, and checks the proposal against the historical range of UK Corporation Tax changes."*

---

### 0:40 – 1:25 · Overview KPIs, Fan Chart & Autonomous Gemini Research (`/analyses/:id`)

1. **Click:** Click **Run analysis ->**.
2. **Observe:** The browser navigates to `/analyses/:id`.
   - The **6-stage pipeline progress rail** (`parsing` -> `researching` -> `precedents` -> `modelling` -> `verifying` -> `reporting`) advances over Server-Sent Events (SSE) with millisecond timings per stage (`modelling=30ms`, `verifying=8ms`, `reporting=5ms`).
   - On the **Overview** tab, highlight the 4 headline KPI cards (`2027-28` Year-1 Behavioural Revenue **`+£7.00bn`**, Year-5 `2031-32` Behavioural Revenue **`+£13.30bn`** vs. Static **`+£14.39bn`** and Dynamic **`+£13.16bn`**, Business Investment **`-0.56%` / `-£2.19bn`**, and Real GDP **`-0.104%`**). Click any KPI number to open its **`ProvenanceNumber` popover** (`formula` + `inputs` + **"Open in Calculation Inspector ->"**).
   - Point out the **Revenue Fan Chart** (`p5–p95` and `p25–p75` bands across 500–2,000 draws) with its mandatory `interval_note` and expandable **"Reading the uncertainty"** guide.
3. **Click:** Switch to the **Research** tab (`54` sources, `37` evidence items, `0` placeholders).
   - Filter by topic or search box, and click an **Extracted Evidence** card to open the **Source Detail Drawer** showing the verbatim quote highlighted in context against the SHA-256 document snapshot.
4. **Talking Point (Judging Criterion — Live AI Research & Anti-Hallucination):**
   > *"Gemini never invents sources or forecast numbers. Using the `google-genai` Interactions API with Google Search grounding and document fetching, the agent extracts verbatim quotes from OBR, HMRC, ONS, and IFS publications. Python code verifies every quote against the fetched text snapshot and drops any URL that didn't come from grounding metadata or a verified fetch."*

---

### 1:25 – 2:00 · Historical Precedents (`/analyses/:id` -> Precedents Tab)

1. **Click:** Click the **Precedents** tab.
2. **Observe:**
   - The **UK CT Main Rate Timeline (`1982–present`)** highlights historical rate changes (`1984`, `1997`, `2008`, `2010`, `2023`) and excludes reversed announcements (`CT-MAIN-2020-REVERSED`) from the implemented step-line.
   - Highlight **April 2023 (`19% -> 25%`, `+6pp`)**: show the side-by-side comparison of **Official Costing** (ex-ante OBR costing) vs. **Observed Outcome** (derived outturn HMRC receipts change), plus confounder badges noting simultaneous **Full Expensing** introduction.
3. **Talking Point (Judging Criterion — Domain Rigour):**
   > *"Ex-ante Treasury costings and ex-post observed tax receipts are fundamentally different kinds of evidence. Jane Avenue never conflates them: every figure carries a distinct provenance badge and surfaces policy confounders like the 2023 full-expensing package."*

---

### 2:00 – 2:50 · Scenarios, Honest Uncertainty & Live Sliders (`Scenarios` & `Assumptions`)

1. **Click:** Click the **Scenarios** tab.
2. **Observe:**
   - **3 Scenario Cards:** **Optimistic**, **Central**, and **Pessimistic** projections satisfying strict revenue ordering (`pessimistic <= central <= optimistic`).
   - **Tornado Chart:** Ranks which uncertain parameters (`taxable_profit_elasticity`, `profit_base_deviation_pct`, `user_cost_elasticity`, `full_expensing_coverage`) drive the largest swing in Year-5 revenue and investment.
3. **Click:** On the same **Scenarios** tab, scroll down to the **Live Assumption Sliders** panel.
   - **Drag a Slider:** Move `taxable_profit_elasticity` or set `full_expensing_coverage = 1.0`. Within `< 50 ms`, `POST /api/simulate` recomputes the engine and overlays the **custom** scenario on the fan chart and tornado.
   - Switch to the **Assumptions** tab and scroll to the **Calculation Inspector** and expand `cost_of_capital_pct` (`+0.97%`), `eatr_pct` (`21.7% -> 24.3%`), and `business_investment_pct` (`-0.29%` in Year 1, `-0.56%` in Year 5).
4. **Talking Point (Judging Criterion — Transparency & Honest Uncertainty):**
   > *"The LLM never calculates a single projection. Every forecast comes from a pure-NumPy Hall–Jorgenson / King–Fullerton user-cost-of-capital and taxable-profit elasticity engine. Notice a crucial UK policy insight: under 100% full expensing (`z = 1`), plant & machinery is marginal-rate neutral, so a CT hike bites through structures and intangibles. Every number can be inspected down to its exact equation and literature source."*

---

### 2:50 – 3:25 · Independent Verification, Policy Report & Withheld Forecast (`Verification` & `Report`)

1. **Click:** Click the **Verification** tab on the `25% -> 28%` analysis, then click the **Report** tab.
   - Show the **18-check audit catalogue** (`16 passed, 1 warning (DATA-002), 1 non-blocking citation error (CITE-002 on E19)`): independent engine recompute within `1e-9` (`CALC-001`), zero data placeholders (`DATA-001`), causal language audit (`CAUSAL-001`), and `REPORT-001` verifying that every number in the narrative report traces to code, cited evidence, or the policy.
   - On the **Report** tab, show clickable inline provenance chips and click **Download .md**.
2. **Click:** Navigate back to **New Analysis** (`/`), click the third example chip **"Raise corporation tax to 45%"**, and click **Run analysis ->**.
   - Show the **`forecast_withheld` banner ("Quantitative forecast withheld")**: because a `+20pp` hike exceeds the validated historical precedent envelope (`SCOPE-001` blocking failure, limit `15pp`), Jane Avenue refuses to fabricate a quantitative forecast while still delivering historical context and research.
3. **Talking Point (Judging Criterion — Trustworthy AI & Refusal):**
   > *"When a policy proposal falls outside historical UK evidence—like a jump to 45%—or if a blocking verification check fails, Jane Avenue withholds the quantitative forecast rather than extrapolating blindly."*

---

### 3:25 – 4:00 · Historical Backtest & Honest ML Evaluation (`/evaluation`)

1. **Click:** Click **Evaluation** in the top navigation bar (`/evaluation`).
2. **Observe:**
   - **Conditional Backtest Table (`FY2008-09..FY2024-25`, $n = 17$ unseen years):** Compares `jane_behavioural` (**Test MAE £5.54bn, MAPE 9.36%**) against `static` (**£5.71bn, MAPE 9.53%**), `naive_growth` (**£6.56bn**), and `linear_regression` (**£8.35bn**), plus **14/17 (82.4%)** leave-one-out 90% empirical interval coverage.
   - **ML Honesty Card (`LightGBMRegressor`, `adopted = False`):** Shows that LightGBM achieved £3.27bn train MAE (`FY1983-84..FY2007-08`) but **£6.33bn** out-of-sample test MAE—worse than both `static` (£5.71bn) and `jane_behavioural` (£5.54bn)—and is therefore transparently rejected (`adopted = False`) and not wired into the live simulator.
   - **Research & Verifier Evaluation Cards:** **15/15 (100%)** fact accuracy, **15/15 (100%)** HTTP-200 URL validity, **15/15 (100%)** verbatim quote verification, **0** hallucinated sources, and **18/18 (100%)** fault-injection detection across the verifier suite.
3. **Talking Point (Judging Criterion — Testing on Unseen Data):**
   > *"Finally, we evaluate every component on unseen data: a strictly chronological conditional backtest on historical UK CT changes since 2008 where our structural behavioural engine (£5.54bn MAE) beats every baseline, an ML experiment (`LightGBM`, £6.33bn test MAE) that we transparently reject under our honesty rule because $n=24$ pre-2008 years cannot support tree extrapolation across regime shifts, a 15-question official-source benchmark with 100% quote verification, and 18/18 fault-injection detection."*

---

## Fallback Plan

| Failure Scenario | Immediate Action |
|---|---|
| **Live Gemini API latency / quota / Wi-Fi drop** | Ensure **Use cached research** is checked on `/`, or start with `JANE_MODE=cached`. The committed `data/research_cache/` replays real verified Gemini traces with zero network dependency. |
| **Cache miss on an ad-hoc judge query** | `run_research` automatically falls back `live -> cache -> mock` without raising an exception, emitting a transparent warning step in the timeline. |
| **Local machine / browser failure** | Play the pre-recorded 4-minute MP4 screen capture of the full golden path + withheld path + evaluation walkthrough while narrating live. |
