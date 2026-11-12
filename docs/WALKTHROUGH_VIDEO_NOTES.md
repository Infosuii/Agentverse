# Jane Avenue: video walkthrough notes

These notes go with the video `jane-avenue-walkthrough.mp4` (12 min 52 s, 1920×1200, with voiceover and burned-in subtitles; a separate `.srt` subtitle file is included). Use them to find a part of the video, or to review how the website works without watching.

**How it was recorded.** The repository has no hosted URL, so the video shows the real Jane Avenue website running locally from this repository (`main` at `436f2f2`) in **Cached Research** mode (`JANE_MODE=cached`). That mode replays recorded, verified Gemini research runs, so no API key is needed. Every figure below was read from the site during the recording, which was made on 8 November 2026. Monte Carlo runs use the default seed (42) and 2,000 draws, so the same queries give the same numbers. Because of the date, policies with no stated date default to **1 April 2027**. If you run it on or after 1 January 2027, the default moves to 1 April 2028 and the figures shift by a year (see `docs/DEMO.md`).

> The site's footer says: *Prototype. Not official government analysis.* Say the same whenever you present its results.

---

## Timestamps

| Time | Section |
|---|---|
| 0:00 | Introduction |
| 0:29 | 1 · Ask a policy question |
| 0:55 | 2 · Check the parsed policy and scope gate |
| 1:50 | 3 · Run the analysis and watch the pipeline |
| 2:22 | 4 · Overview: the headline numbers |
| 4:03 | 5 · Research: the evidence base |
| 5:06 | 6 · Precedents: what happened before |
| 6:05 | 7 · Scenarios: uncertainty and what-ifs |
| 7:29 | 8 · Assumptions: every input on the table |
| 8:05 | 9 · Verification: can the numbers be trusted? |
| 8:53 | 10 · Report: the document to share |
| 9:17 | 11 · When the site refuses to forecast |
| 10:01 | 12 · Other taxes, benefits and spending |
| 10:56 | 13 · History: return to past analyses |
| 11:04 | 14 · Evaluation: how reliable is the method? |
| 11:58 | 15 · Using the results in a decision |

---

## 0:00 · Introduction
- Jane Avenue is the Agentverse project's AI-powered UK fiscal policy simulator. You type a proposed tax, benefit or spending change in plain English. It returns researched evidence, modelled impacts and an independent verification.
- The **Mode** badge (top right) shows the run mode: *Cached Research*, *Live Gemini* or *Mock*.
- The footer disclaimer: a prototype, not official government analysis.

## 0:29 · 1. Ask a policy question (home page `/`)
- Type the policy into the question box. **Enter** runs it, and **Shift+Enter** adds a new line.
- There are six example prompts: CT 25%→28% (golden path), CT 25%→23% cut, CT to 45% (scope gate), VAT 20%→21%, personal allowance +£1,000, and NHS spending +£10bn (research only).
- Clicking an example fills the box and parses it.

## 0:55 · 2. Check the parsed policy and scope gate
- The **Parsed Policy Specification & Scope Gate** card shows how the site understood the question. For the golden path: policy type *UK Corporation Tax — Main Rate*, baseline **25%**, proposed **28%**, rate change **+3pp**.
- **Parser assumptions & ambiguities** lists the defaults it filled in: effective date assumed **1 April 2027**, horizon assumed **5 years**. *Edit these fields before running if they are not what you mean.*
- **Scope gate:** "Quantitative forecast allowed". The historical UK CT range is **19%–52%**, and the largest single change was **6pp**.
- **Simulation & Research Options:** Monte Carlo draws (default 2,000), run research agent, use cached research. Then click **Run analysis**.

## 1:50 · 3. Run the analysis and watch the pipeline (`/analyses/:id`)
- Six stages run live: **Parse & scope → Research → Precedents → Model & Monte Carlo → Verify → Report**. A tick marks each completed stage.
- The **Live Research Agent Timeline** streams every step: planned questions, searches, fetched documents and extracted quotes.
- When the analysis finishes, a notice appears: *Your policy assessment is ready … Approved with warnings.*

## 2:22 · 4. Overview: the headline numbers
- **Check the verdict badge in the header first** (here: *Approved with warnings*).
- Headline projections from the central scenario:

| Card | Value | p5–p95 range | Confidence |
|---|---|---|---|
| Behavioural revenue 2027-28 (year 1) | **£7.0bn** | £5.3bn to £8.5bn | medium |
| Behavioural revenue 2031-32 (year 5) | **£13.3bn** | £10.7bn to £15.1bn | medium |
| Business investment 2031-32 | **−0.56%** | (user cost of capital channel) | medium |
| GDP level 2031-32 | **−0.10%** | (partial equilibrium capital stock effect) | **low (indicative)** |

- Every number has an evidence label. **Model scenario** means the econometric engine calculated it; the AI did not write it.
- **How to quote it:** "about £7bn in the first year, between £5.3bn and £8.5bn under the model's assumptions (model scenario)."
- The **Policy & Evidence Summary** gives the research summary. **[E#]** refers to an evidence item and **[S#]** to a source.
- The workstream links show the counts: 37 evidence items across 24 sources, 5 precedents, the scenarios, 19 assumptions, 18 audit checks, and the report.

## 4:03 · 5. Research: the evidence base
- The research agent planned **6 research questions**, ran searches, and fetched documents (for example from GOV.UK, the IFS and the American Economic Association).
- The **Evidence Browser** holds **37 items**: **35 verified** (verbatim quote checked against the source text) and **2 failed**. Failed items are flagged in red, not hidden.
- You can filter by topic, verification status and evidence kind, or search claims and quotes.
- Example: **E1** says onshore CT receipts are projected to reach 3.5% of GDP in 2027-28 (source S4).
- Clicking a source opens the source drawer. **S4** is the *Economic and fiscal outlook – October 2026* (GOV.UK). The drawer lists every quote taken from that source and whether each one was verified.
- **Decision use:** cite only evidence marked *Quote verified*.

## 5:06 · 6. Precedents: what happened before
- The **UK CT Main Rate Timeline (1982–present)** shows the rate history. Blue markers are the **5 matched precedents**.
- The closest match is **CT-MAIN-2023: 19% → 25% (+6pp)**, effective 1 April 2023, with a similarity of **60%**.
- **Confounders:** the small profits rate with marginal relief, and full expensing, were introduced at the same time.
- Two kinds of evidence are kept separate:
  - **Official costing** (made before the change at Spring Budget 2021): ex-ante HMT estimates.
  - **Observed outcome** (actual receipts): **£83.3bn** in 2022-23 and **£92.4bn** in 2023-24.
- **Decision use:** treat precedents as context and a sense check. As the site says, "similarity does not establish causation".

## 6:05 · 7. Scenarios: uncertainty and what-ifs
- The **Metric selector** offers 7 modelled outputs: behavioural, static and dynamic revenue; business investment (% and £bn); GDP level; cost of capital.
- **Scenario paths:** central, optimistic and pessimistic. Optimistic and pessimistic are stress tests made of favourable or unfavourable assumptions; they are not forecasts.
- **Monte Carlo:** 2,000 draws with the uncertain assumptions varied together. The bands show the p5–p95 and p25–p75 ranges.
- **Interval note:** these are assumption-driven ranges, *not* statistical prediction intervals. They exclude model and data uncertainty.
- **Tornado (2031-32):** the biggest drivers are the **profit base deviation from baseline** and the **taxable profit elasticity**. These are the assumptions to scrutinise.
- **Live sliders:** in the video, the proposed rate drops from 28% to 26%. The model recomputes in milliseconds, and a dashed purple custom path appears well below the central path.
- **Re-run full analysis with these assumptions** repeats verification and the report. **Reset all** restores the defaults.

## 7:29 · 8. Assumptions: every input on the table
- The registry lists all **19 parameters**. Each has a central value, a low–high range, a distribution, a basis (Literature / Official / Team judgement) and sources.
- Example: taxable profit elasticity **0.2** (range 0.05–0.5, triangular distribution, basis: Literature).
- The **Calculation Inspector** shows how a number was calculated, step by step: each formula, its inputs and the linked parameters, in dependency order. You can pick any metric and fiscal year.

## 8:05 · 9. Verification: can the numbers be trusted?
- **18 checks:** 16 passed, 1 warning, 1 failed, 0 skipped. Verdict: **Approved with warnings**.
- **CITE-002 (failed, severity: error):** evidence item E19 is not verified against its source text. Because this check is not blocking, the forecast is still shown, with a warning.
- **DATA-002 (warning):** baseline years after 2031-32 are extrapolated, not official forecasts.
- **CALC-001:** an independent recompute reproduces all 35 central-scenario values.
- **Blocking checks** (for example SCOPE-001): if one fails, the forecast is withheld.
- **Decision use:** read this page before citing any number, and pass on its warnings.

## 8:53 · 10. Report: the document to share
- The **Policy Assessment** has **10 sections**, from the executive summary to sources and data provenance.
- Code inserts the numbers; the AI does not write them. There are **8 traceable figures**. Hover over one to see its calculation steps and sources.
- **Download .md** gives an editable Markdown copy. **Print / Save as PDF** is for circulating it.

## 9:17 · 11. When the site refuses to forecast
- Query: *Raise corporation tax to 45%*. The baseline is assumed to be the current rate of 25%.
- The scope gate marks it **Unsupported**: "The proposed 20pp change is far outside any UK precedent (limit 15pp)."
- After it runs, a **Quantitative forecast withheld** banner appears and every headline card reads *Forecast withheld*. Research and precedents are still available.
- **Decision use:** a withheld forecast is a finding in its own right. Quote no figure.

## 10:01 · 12. Other taxes, benefits and spending
- **VAT 20% → 21%** is *Partially supported*. Measures in HMRC's ready reckoner are scaled from HMRC's official costings: HMRC costs the first 3 years, and later years repeat the third-year effect grown with nominal GDP.
  - Year 1 (2027-28): **£9.1bn** (p5–p95 £7.8bn to £9.7bn).
  - **Placeholder (unverified)** badge: this offline recording has no cached research for VAT, so the research shown is a labelled placeholder. In live mode with a Gemini API key it is researched for real. Never quote placeholder material.
- **NHS spending +£10bn** is research only. No validated model exists yet, so the policy is researched and reported but no forecast is made.

## 10:56 · 13. History
- `/history` lists every analysis with its status and verification verdict. Click **Open →** to return to one.

## 11:04 · 14. Evaluation: how reliable is the method? (`/evaluation`)
- **Backtest on 17 unseen years (FY2008-09 to FY2024-25):** the central engine's mean absolute error (MAE) is **£5.54bn**, against **£5.71bn** for the best simple baseline (static).
- **LightGBM (machine learning) was rejected:** its test MAE was **£6.33bn**, worse than the baseline, so it is not used in the simulator.
- **Research agent benchmark (15 questions):** 100% fact accuracy, 100% citation URL validity, 100% quote match, 0 hallucinated sources.
- **Verifier fault injection:** 18 of 18 faults detected.
- **Methodological limitations:** for example, there are only 16 past rate changes, and other reforms happened at the same time.

## 11:58 · 15. Decision checklist
1. Check that the parsed policy and its assumptions match what you mean.
2. Read the verification verdict first. If the forecast is withheld, quote no numbers.
3. Quote central figures with their p5–p95 range and their "Model scenario" label.
4. Use the tornado chart to find the assumptions that matter, then test them with the sliders.
5. Back claims with verified evidence and precedents, and name the confounders.
6. Check the Evaluation page to see how reliable the method has been on past data.
7. Share the Report (Markdown or PDF) with its warnings and caveats.

---

## Reproducing the video
The recorder lives in [`scripts/walkthrough-video/`](../scripts/walkthrough-video/README.md). It drives the running site with Playwright, adds the subtitles, highlights and cursor, records the frames over CDP, voices the narration with RHVoice, and builds the MP4 with ffmpeg.
