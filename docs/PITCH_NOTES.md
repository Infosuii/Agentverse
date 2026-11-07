# Jane Avenue: Pitch Notes & Architecture Story

> **Owner:** `agent-11` (with evaluation headline numbers from `agent-10`)  
> Ready-to-use talking points, architecture summary, economic insights, and evaluation metrics for the presentation slides.

---

## 1. One-Sentence Pitch

**Jane Avenue** combines live Gemini-grounded economic research, historical UK tax precedents, transparent econometric modelling, and independent verification to help government analysts rigorously explore the consequences of proposed tax policies—and refuses to forecast when the evidence is insufficient.

---

## 2. The Problem & Why Existing AI Tools Fail Policy Analysts

1. **LLMs hallucinate numbers and citations:** Asking a general-purpose chatbot *"What happens if the UK raises Corporation Tax from 25% to 28%?"* yields plausible-sounding but fabricated £bn figures and unverified links.
2. **Spreadsheet models hide context and confounders:** Pure formulas miss qualitative institutional context—such as how the UK's 2023 introduction of 100% *Full Expensing* fundamentally altered the investment channel of Corporation Tax.
3. **Overconfident point estimates:** Policy costings rarely separate ex-ante official costings, ex-post observed outcomes, and assumption-driven model ranges.

---

## 3. Jane Avenue's Trust Architecture (The 6-Stage Guardrailed Pipeline)

```
Plain-English Policy Query
   │
   ▼
1. Policy Parser & Scope Gate (policy/)
   │  • Structured PolicyMeasure + explicit ambiguity log
   │  • Validated against 40+ years of UK CT rate changes (1983–2023)
   ▼
2. Autonomous Gemini Research Agent (research/ + llm/)
   │  • Gemini Interactions API + Google Search grounding + official URL fetch
   │  • Every quantitative claim requires a verbatim quote verified in Python against SHA-256 document snapshots
   ▼
3. Historical Precedents Matcher (precedents/ + data/)
   │  • Weighted similarity across direction, magnitude, rate level, macro z-score, and recency
   │  • Separates ex-ante Official Costings (OBR/HMT) from ex-post Observed Outcomes (HMRC/ONS)
   ▼
4. Vectorised Econometric & Simulation Engine (engine/ + simulation/)
   │  • Pure NumPy — Gemini NEVER calculates a number
   │  • Static, Behavioural (taxable profit elasticity), and Dynamic revenue
   │  • Hall–Jorgenson / King–Fullerton user cost of capital across Plant & Machinery, Structures, and Intangibles
   │  • 2,000-draw Monte Carlo + Tornado sensitivity in < 50 ms
   ▼
5. Independent 18-Check Verifier (verification/)
   │  • Recomputes central engine outputs to 1e-9 (CALC-001)
   │  • Audits source provenance (CITE-001..003), data placeholders (DATA-001), causal claims (CAUSAL-001), and report digits (REPORT-001)
   │  • Can WITHHOLD the quantitative forecast (forecast_withheld)
   ▼
6. Evidence-Backed Policy Assessment (report/)
      • Gemini drafts neutral analyst prose using {{fig:id}} placeholders
      • Python substitutes every number from the engine and verifies zero raw digits were invented
```

---

## 4. Key Economic Insight & Frozen Golden-Path Numbers (`25% -> 28%` CT from April 2027)

- **The Full-Expensing Neutrality Theorem:** Under a 100% first-year capital allowance ($z = 1$), the Hall–Jorgenson user cost of capital $c_a(t) = (r + \delta_a)(1 - t \cdot z_a)/(1 - t)$ simplifies to $r + \delta_a$—completely independent of the statutory Corporation Tax rate $t$.
- Because the UK introduced **Full Expensing** for plant & machinery in April 2023 (`full_expensing_coverage = 0.80`), raising the CT main rate from 25% to 28% does **not** penalise covered plant & machinery investment at the margin; instead, the investment drag operates through **structures & buildings** (3% SBA, $z = 0.299$) and **intangibles** ($z = 0.720$), alongside taxable-profit shifting ($\varepsilon = 0.20$).
- **Frozen Central Scenario Impact (`25% -> 28%` CT from 1 April 2027 vs. OBR October 2026 baseline):**
  - **Static Revenue (`revenue_static_gbp_bn`):** Year 1 (`2027-28`) **`+£7.28bn`** (`+£7.2788bn`), Year 5 (`2031-32`) **`+£14.39bn`** (`+£14.3918bn`)
  - **Behavioural Revenue (`revenue_behavioural_gbp_bn`):** Year 1 **`+£7.00bn`** (`+£7.0020bn`), Year 5 **`+£13.30bn`** (`+£13.2996bn`)
  - **Dynamic Revenue (`revenue_dynamic_gbp_bn`):** Year 1 **`+£6.99bn`** (`+£6.9910bn`), Year 5 **`+£13.16bn`** (`+£13.1614bn`)
  - **Business Investment (`business_investment_pct`):** Year 1 **`-0.29%`** (`-£1.00bn`), Year 5 **`-0.56%`** (`-£2.19bn`)
  - **Real GDP Level (`gdp_level_pct`):** Year 1 **`-0.016%`**, Year 5 **`-0.104%`**
  - **User Cost of Capital (`cost_of_capital_pct`):** **`+0.97%`** (`+0.9706%`); **Devereux–Griffith EATR:** **`21.7% -> 24.3%`**
- Analysts can verify every step live in the **Calculation Inspector** and test `full_expensing_coverage = 1.0` on the **Assumptions & Lab** sliders (`POST /api/v1/simulate` in `< 50 ms`).

---

## 5. Headline Evaluation Numbers (`agent-10` — Unseen Historical Data & Verification Benchmarks)

> *All figures below are reproducible from `backend/jane_avenue/evaluation/results/latest.json` (`dataset_version = 62059e64ffca`, `is_placeholder = false`) and `docs/EVALUATION.md`.*

### 5.1 Chronological Revenue Backtest (`FY1983-84..FY2007-08` Train -> `FY2008-09..FY2024-25` Unseen Test, $n = 17$)
- **Setup:** Strictly chronological out-of-sample split testing 1-year-ahead onshore CT receipts (£bn) conditional on realised profit growth (`pnfc_gos`, isolating policy-response modelling from macro GDP forecast error across the 2008–2017 rate cuts and the 2023 `19% -> 25%` hike).

| Model | Out-of-Sample Test MAE (£bn) | Test RMSE (£bn) | Test MAPE (%) | Directional Accuracy | Notes |
|---|---:|---:|---:|---:|---|
| **`jane_behavioural` ($\varepsilon = 0.20, s = 0.87$)** | **£5.54bn** | **£7.07bn** | **9.36%** | **54.5%** | Default central engine specification; beats `static` and all simple baselines |
| `jane_calibrated` (bound-constrained $\varepsilon = 1.500$) | £5.29bn | £6.67bn | 9.43% | 54.5% | Corner solution on `FY <= 2007` due to 1984–86 base-broadening; not exposed as default |
| **`static` ($s = 0.87$, best simple baseline)** | **£5.71bn** | **£7.26bn** | **9.53%** | **54.5%** | Mechanical rate-change scaling ($\varepsilon = 0$) |
| `lightgbm` (`LGBMRegressor`, 6 features) | £6.33bn | £8.00bn | 12.28% | 54.5% | Train MAE £3.27bn -> overfits $n=24$ training split; **`adopted = False`** |
| `naive_growth` (constant tax-to-profit ratio) | £6.56bn | £8.25bn | 11.09% | 45.5% | Ignores statutory rate changes |
| `linear_regression` (OLS on $\Delta \tau_t, g_t$) | £8.35bn | £10.90bn | 13.89% | 54.5% | Unstable across structural regime shifts |

- **Empirical Interval Calibration:** Leave-one-out 90% empirical residual interval coverage on `FY2008-09..FY2024-25` is **14 / 17 (82.4%)** for `jane_behavioural` (and **15 / 17 (88.2%)** prior to the 2023 full-expensing regime shift).
- **ML Honesty Rule (`adopted = False`):** Strongly regularised `LGBMRegressor` achieves £3.27bn train MAE (`FY1983-84..FY2007-08`) but **£6.33bn** out-of-sample test MAE—failing to beat either `static` (£5.71bn) or `jane_behavioural` (£5.54bn) because $n = 24$ annual observations cannot support non-linear tree splits across shifting fiscal regimes. Following our honesty rule, LightGBM is **rejected (`adopted = False`)** and not wired into the live simulator.

### 5.2 Research Agent Citation & Quote Audit (15-Question UK CT Gold Set)
- **Fact Accuracy (`fact_accuracy`):** **15 / 15 (100.0%)**
- **Citation URL Validity (`citation_url_valid_rate`, HTTP 200):** **15 / 15 (100.0%)**
- **Verbatim Quote Verification Rate (`quote_match_rate`):** **15 / 15 (100.0%)**
- **Hallucinated Sources (`hallucinated_source_count`):** **0** (enforced in post-processing code)
- **Official Tier-1 Source Share (`official_source_share` — OBR, HMRC, ONS, legislation.gov.uk):** **100.0%**

### 5.3 Independent Verifier Fault-Injection Suite (18 Checks)
- **Injected Faults Detected (`fault_detection_rate`):** **18 / 18 (100.0%)** across all 18 check IDs (`SCOPE-001`, `CITE-001..003`, `EVID-001..004`, `ASSUMP-001..002`, `CALC-001..003`, `DATA-001..002`, `CAUSAL-001`, `UNC-001`, `REPORT-001`).
- **Clean-Case Blocking False Positives (`false_positive_rate_on_clean`):** **0 / 1 (0.0%)** on the clean golden path.

---

## 6. Performance Budgets Achieved

| Metric | Target Budget | Measured (`smoke.py` / API) |
|---|---|---|
| Fast slider re-simulation (`POST /api/v1/simulate`, 500–2,000 draws + tornado) | `< 1,000 ms` | **`~15–30 ms`** |
| First SSE research step on screen | `< 3,000 ms` | **`< 200 ms`** |
| Full golden-path analysis (`cached` mode, 54 sources, 37 evidence items) | `< 20,000 ms` | **`5.38 s`** (`modelling=30ms`, `verifying=8ms`, `reporting=5ms`) |
| Full golden-path analysis (`mock` mode) | `< 20,000 ms` | **`0.60 s`** |
| Full golden-path analysis (`live` Gemini mode) | `< 120,000 ms` | **`< 90 s`** (enforced by research tool-loop budget) |
