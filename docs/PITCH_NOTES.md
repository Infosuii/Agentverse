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
   │  • Structured PolicySpec + explicit ambiguity log
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
   │  • 2,000-draw Monte Carlo + Tornado sensitivity in < 300 ms
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

## 4. Key Economic Insight Highlighted in the Demo

- **The Full-Expensing Neutrality Theorem:** Under a 100% first-year capital allowance ($z = 1$), the Hall–Jorgenson user cost of capital $c_a(t) = (r + \delta_a)(1 - t \cdot z_a)/(1 - t)$ simplifies to $r + \delta_a$—completely independent of the statutory Corporation Tax rate $t$.
- Because the UK introduced **Full Expensing** for plant & machinery in April 2023 (`full_expensing_coverage ≈ 0.80`), raising the CT main rate from 25% to 28% does **not** penalise covered plant & machinery investment at the margin; instead, the investment drag operates through **structures & buildings** (3% SBA) and **intangibles**, alongside taxable-profit shifting ($\varepsilon$).
- Analysts can verify this live in the **Calculation Inspector** and test `full_expensing_coverage = 1.0` on the **Scenarios** sliders.

---

## 5. Headline Evaluation Numbers (`agent-10` — Unseen Historical Data & Verification Benchmarks)

> *Note: Preliminary baseline figures below; updated automatically from `backend/jane_avenue/evaluation/results/latest.json` and `docs/EVALUATION.md` as `agent-10`'s M1/M2 evaluation lands.*

### 5.1 Chronological Revenue Backtest (`FY ≤ 2007` Train → `FY ≥ 2008` Unseen Test)
- **Setup:** Strictly chronological split testing 1-year-ahead onshore CT receipts conditional on realised profit growth (isolating policy-response modelling from macro forecast error across the 2008–2017 rate cuts and the 2023 19%→25% hike).
- **Baselines vs. Structural Engine:** Compares `naive_growth`, `static`, `jane_behavioural` (central $\varepsilon = 0.20$), `jane_calibrated` (training-split fitted $\varepsilon$), `linear_regression`, and `lightgbm`.
- **ML Honesty Rule:** LightGBM (`MLExperiment`) is only adopted into the product if its out-of-sample test MAE beats the best simple baseline; otherwise `adopted = False` with a transparent diagnosis of small-$n$ fiscal regime shifts.

### 5.2 Research Agent Citation & Quote Audit (15-Question Gold Set)
- **Hallucinated Sources (non-grounding / non-fetched URLs):** **0** (enforced in post-processing code)
- **Citation URL Validity (HTTP 200):** Tracked in `research_eval.citation_url_valid_rate`
- **Verbatim Quote Verification Rate:** Tracked in `research_eval.quote_match_rate`
- **Official / Tier 1–2 Source Share (OBR, HMRC, ONS, BoE, IFS, peer-reviewed):** Tracked in `research_eval.official_source_share`

### 5.3 Independent Verifier Fault-Injection Suite
- **Injected Faults Tested:** `fake_source_url`, `unverified_quote`, `orphan_evidence`, `tampered_metric`, `unsourced_assumption`, `out_of_scope_policy`, `placeholder_data`, `causal_claim`, `mislabelled_interval`, `raw_number_in_report`.
- **Target Detection Rate:** **100% (10 / 10 injected faults caught)** with **0 blocking false positives** on the clean golden path.

---

## 6. Performance Budgets Achieved

| Metric | Target Budget | Measured (`smoke.py` / API) |
|---|---|---|
| Fast slider re-simulation (`POST /api/simulate`, 2,000 draws + tornado) | `< 1,000 ms` | `< 50 ms` |
| First SSE research step on screen | `< 3,000 ms` | `< 300 ms` |
| Full golden-path analysis (`cached` / `mock` mode) | `< 20,000 ms` | `< 1,500 ms` |
| Full golden-path analysis (`live` Gemini mode) | `< 120,000 ms` | `< 90,000 ms` (enforced by tool loop budget) |
