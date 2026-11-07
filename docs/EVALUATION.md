# Jane Avenue — Evaluation, Historical Backtesting & ML Experiment

- **Generated at:** `2026-11-07T18:51:06.849816+00:00`
- **Dataset version:** `10bb93bda87c`
- **Profit growth measure (`g`):** `pnfc_gos`
- **Placeholder flag (`is_placeholder`):** `False`

## 1. Conditional Backtest Design

Conditional backtest of UK Corporation Tax receipts R_{y+1} (£bn nominal) predicted from information at fiscal year y-1, conditioning on realised 2-year profit growth (`pnfc_gos`) from y-1 to y+1. This conditional design isolates tax-policy response modelling from macroeconomic forecast error. Chronological split: train on FY <= 2007, out-of-sample test on FY >= 2008 (FY2008-09 to FY2024-25). Leave-one-out 90% (5th–95th percentile) empirical residual interval coverage on FY2008-09 to FY2024-25: 15/17 (88.2%).

- **Chronological split:** Training split `FY <= 2007` (`1985-86` to `2007-08`), out-of-sample test split `FY >= 2008` (`2008-09` onwards). No shuffling is ever performed, and no test-year outcome (`FY >= 2008`) enters training parameter estimation.
- **Engine central parameters:** `main_rate_profit_share` $s = 0.85$, central `taxable_profit_elasticity` $\varepsilon = 0.20$, train-calibrated elasticity $\hat{\varepsilon}_{\text{train}} = 1.500$.
- **Empirical residual interval calibration (`jane_behavioural`):** Across $n = 17$ test years (FY2008-09 to FY2024-25), the leave-one-out 5th–95th percentile (90%) relative-error interval covered **15/17 (88.2%)** of observed outcomes.

## 2. Methods Evaluated

| Method | Label | Baseline? | Definition |
|---|---|---|---|
| `naive_growth` | Naive profit-growth baseline | Yes | R̂_{y+1} = R_{y-1} × (1 + g_{y-1→y+1}), assuming receipts grow one-for-one with the profit proxy and ignoring tax-rate changes. |
| `static` | Static tax-rate scaling baseline | Yes | R̂_{y+1} = naive × (s·t_new/t_old + (1−s)), scaling the main-rate share s of receipts proportionally to the statutory rate change with zero behavioural response. |
| `jane_behavioural` | Jane Avenue behavioural engine (central prior ε) | No | Engine static + behavioural revenue equation with central taxable-profit elasticity ε = 0.20 and main-rate profit share s = 0.85. |
| `jane_calibrated` | Jane Avenue behavioural engine (train-calibrated ε) | No | Same structural revenue equation with elasticity ε = 1.500 fitted by nonlinear least squares on FY ≤ 2007 training data only. |
| `linear_regression` | Log-change OLS baseline | Yes | OLS regression of log(R_{y+1}/R_{y-1}) on statutory rate change Δt and log(1+g) fitted on FY ≤ 2007 training data only. |
| `lightgbm` | LightGBM gradient-boosted trees (ML experiment) | No | Shallow, strongly regularised LightGBM regressor (max_depth=2, num_leaves=3, L1=1.0, L2=2.0, seed=42) predicting log(R_{y+1}/R_{y-1}) from rate_change_pp, starting_rate_pct, profit_growth_pct, bank_rate_pct, real_gdp_growth_pct, lagged_receipts_pct_gdp. |

## 3. Backtest Results by Split

Headline evaluation is on the **out-of-sample `test` split (`FY >= 2008`)**:

| Split | Method | Baseline? | n | MAE (£bn) | RMSE (£bn) | MAPE (%) | Policy-Effect Directional Accuracy |
|---|---|---|---:|---:|---:|---:|---:|
| `test` | `jane_calibrated` | No | 17 | 5.29 | 6.68 | 9.43% | 54.5% |
| `test` | `jane_behavioural` | No | 17 | 5.48 | 7.01 | 9.29% | 54.5% |
| `test` | `static` | Yes | 17 | 5.65 | 7.19 | 9.46% | 54.5% |
| `test` | `lightgbm` | No | 17 | 6.33 | 8.00 | 12.28% | 63.6% |
| `test` | `naive_growth` | Yes | 17 | 6.56 | 8.25 | 11.09% | 0.0% |
| `test` | `linear_regression` | Yes | 17 | 8.35 | 10.90 | 13.89% | 45.5% |
| `train` | `lightgbm` | No | 25 | 3.27 | 4.00 | 14.32% | 58.3% |
| `train` | `linear_regression` | Yes | 25 | 3.80 | 4.88 | 14.34% | 58.3% |
| `train` | `jane_calibrated` | No | 25 | 3.91 | 4.78 | 15.60% | 50.0% |
| `train` | `naive_growth` | Yes | 25 | 3.94 | 4.82 | 15.92% | 0.0% |
| `train` | `jane_behavioural` | No | 25 | 4.13 | 4.90 | 17.44% | 33.3% |
| `train` | `static` | Yes | 25 | 4.17 | 4.93 | 17.70% | 33.3% |

## 4. Highlight Cases: Statutory Rate-Change Years

> **Evidence-class note:** `observed` ($R_{y+1}$) is an **observed outcome** (total CT receipts in £bn). `official_costing_gbp_bn` is an **official costing** (ex-ante HMT/OBR policy-measure delta $\Delta R$ in £bn relative to a contemporary Budget baseline, **not** total receipts ground truth). Method columns are **model scenario** conditional predictions of $R_{y+1}$ (£bn).

| Case ID | Policy Year ($y$) | Split | Target ($y+1$) | Observed $R_{y+1}$ (£bn) | Ex-Ante Official Costing $\Delta R$ (£bn, ref only) | `naive_growth` (£bn) | `static` (£bn) | `jane_behavioural` (£bn) | `jane_calibrated` (£bn) | `linear_regression` (£bn) | `lightgbm` (£bn) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `CT-MAIN-1983` | 1983-84 | `train` | ct_receipts_gbp_bn (1984-85) | 8.34 | — | 7.55 | 6.69 | 6.84 | 7.95 | 9.25 | 7.31 |
| `CT-MAIN-1984` | 1984-85 | `train` | ct_receipts_gbp_bn (1985-86) | 10.71 | — | 8.40 | 6.97 | 7.18 | 8.77 | 11.02 | 7.96 |
| `CT-MAIN-1985` | 1985-86 | `train` | ct_receipts_gbp_bn (1986-87) | 13.49 | — | 9.72 | 7.88 | 8.10 | 9.71 | 12.17 | 10.74 |
| `CT-MAIN-1986` | 1986-87 | `train` | ct_receipts_gbp_bn (1987-88) | 15.73 | — | 12.90 | 11.53 | 11.69 | 12.76 | 14.70 | 13.78 |
| `CT-MAIN-1990` | 1990-91 | `train` | ct_receipts_gbp_bn (1991-92) | 18.26 | — | 22.35 | 21.27 | 21.38 | 22.10 | 22.86 | 23.13 |
| `CT-MAIN-1991` | 1991-92 | `train` | ct_receipts_gbp_bn (1992-93) | 15.78 | — | 21.55 | 21.01 | 21.07 | 21.42 | 21.34 | 23.13 |
| `CT-MAIN-1997` | 1997-98 | `train` | ct_receipts_gbp_bn (1998-99) | 30.03 | — | 28.69 | 27.21 | 27.35 | 28.25 | 29.27 | 30.84 |
| `CT-MAIN-1999` | 1999-00 | `train` | ct_receipts_gbp_bn (2000-01) | 32.42 | — | 29.44 | 28.63 | 28.70 | 29.16 | 28.95 | 33.33 |
| `CT-MAIN-2008` | 2008-09 | `test` | ct_receipts_gbp_bn (2009-10) | 36.63 | — | 45.45 | 42.87 | 43.08 | 44.43 | 45.45 | 50.62 |
| `CT-MAIN-2011` | 2011-12 | `test` | ct_receipts_gbp_bn (2012-13) | 39.84 | — | 47.59 | 41.81 | 42.19 | 44.74 | 51.71 | 48.49 |
| `CT-MAIN-2012` | 2012-13 | `test` | ct_receipts_gbp_bn (2013-14) | 38.93 | -0.73 | 46.09 | 41.57 | 41.85 | 43.70 | 48.75 | 47.84 |
| `CT-MAIN-2013` | 2013-14 | `test` | ct_receipts_gbp_bn (2014-15) | 41.09 | -0.82 | 45.55 | 40.71 | 40.97 | 42.73 | 48.96 | 51.29 |
| `CT-MAIN-2014` | 2014-15 | `test` | ct_receipts_gbp_bn (2015-16) | 43.02 | — | 42.88 | 38.12 | 38.37 | 39.99 | 45.56 | 46.96 |
| `CT-MAIN-2015` | 2015-16 | `test` | ct_receipts_gbp_bn (2016-17) | 49.30 | — | 41.66 | 39.98 | 40.06 | 40.62 | 41.39 | 49.56 |
| `CT-MAIN-2017` | 2017-18 | `test` | ct_receipts_gbp_bn (2018-19) | 56.30 | -1.60 | 53.91 | 51.62 | 51.73 | 52.44 | 54.81 | 59.46 |
| `CT-MAIN-2023` | 2023-24 | `test` | ct_receipts_gbp_bn (2024-25) | 95.70 | +16.25 | 84.83 | 107.60 | 106.15 | 97.26 | 72.86 | 89.64 |

## 5. Implied Taxable-Profit Elasticity Check

OLS of log((receipts/t)/pnfc_gos) on log(1-t) over n=44 fiscal years (controlling for real GDP growth) yields an implied base elasticity of 2.642 (SE 0.185), compared with the engine central prior of 0.20. Because UK rate cuts in the 1980s and 2010s coincided with base-broadening capital-allowance reforms and post-2008 financial-sector profit shifts, macro time-series regressions confound rate effects with base definitions; we retain the micro-econometric literature prior (0.20) as central.

## 6. Out-of-Sample Machine Learning Experiment

- **Model:** `LightGBMRegressor(n_estimators=25, max_depth=2, num_leaves=3, min_child_samples=3, lr=0.08, reg_alpha=1.0, reg_lambda=2.0, seed=42)`
- **Features:** `rate_change_pp, starting_rate_pct, profit_growth_pct, bank_rate_pct, real_gdp_growth_pct, lagged_receipts_pct_gdp`
- **Train / Test periods:** `FY1983-84–FY2007-08` / `FY2008-09–FY2024-25`
- **Test MAE (£bn):** `6.33` vs best baseline `static` (`5.65`)
- **Adopted in product (`adopted`):** `False`
- **Conclusion:** NOT ADOPTED: LightGBM achieved an out-of-sample test MAE of £6.33bn on FY2008-09–FY2024-25, which fails to beat the best simple baseline `static` (test MAE £5.65bn) and the structural engine `jane_behavioural` (test MAE £5.48bn), despite a much lower in-sample train MAE of £3.27bn on FY1983-84–FY2007-08. Three structural factors explain this train/test gap: (1) tiny annual sample size (n=24 training observations), (2) regime shift between the training era (30–50% CT rates, higher Bank Rate) and the post-2008 test era (19–28% CT rates, near-zero interest rates, and the 2023 rate hike from 19% to 25%), and (3) tree models' piecewise-constant leaves cannot extrapolate log-growth responses outside the training feature support. Per product rules, ML is rejected and not wired into the live simulator.

## 7. Research Agent Citation & Fact Accuracy Evaluation

- **Questions evaluated:** `15` (`mode=live`)
- **Fact accuracy:** `100.0%`
- **Citation URL validity (HTTP 200):** `100.0%`
- **Verified quote match rate:** `100.0%`
- **Hallucinated sources:** `0`
- **Official (Tier 1) source share:** `100.0%`
- **Notes:** Evaluated 15 gold factual UK CT questions (15/15 facts accurate, 15/15 source URLs HTTP-verified, 15/15 quotes verified verbatim, 0 hallucinated sources, 15/15 Tier-1 official sources).

## 8. Independent Verifier Fault-Injection Evaluation

- **Injected fault cases detected:** `12/12 (100.0%)`
- **Clean-case blocking false positives:** `0/1`
- **Notes:** Clean case: approved; flagged checks: none.

## 9. Limitations & Honest Caveats

- Conditional backtest design: predictions of R_{y+1} condition on realised 2-year profit growth from y-1 to y+1 (measured via `pnfc_gos`). This isolates tax-rate response modelling from macroeconomic forecast error, so out-of-sample errors in unconditional real-time forecasting would be larger.
- Small sample of policy regime shifts: UK corporation tax main-rate history since FY1982 contains only 16 implemented statutory rate changes (8 in the FY <= 2007 training split and 8 in the FY >= 2008 test split).
- Simultaneous base-broadening and relief confounders: major rate changes coincided with structural base changes—most notably the 1983–1986 phased rate cuts paired with first-year capital-allowance abolition, and the April 2023 rise (19% -> 25%) paired with full expensing for plant & machinery and the 19% small profits rate / marginal relief.
- Official costings are not ground truth: `official_costing_gbp_bn` reports ex-ante HMT/OBR policy costings (revenue delta relative to a contemporary Budget baseline under ex-ante macro assumptions), whereas `observed` and model `predictions` are total fiscal-year CT receipts R_{y+1} (£bn).
- Receipts collection lags and composition: CT receipts combine onshore and offshore (North Sea ring-fence) regimes, Quarterly Instalment Payments (QIPs) timing transitions, bank surcharge, and financial-sector loss carry-forwards.
- OLS of log((receipts/t)/pnfc_gos) on log(1-t) over n=44 fiscal years (controlling for real GDP growth) yields an implied base elasticity of 2.642 (SE 0.185), compared with the engine central prior of 0.20. Because UK rate cuts in the 1980s and 2010s coincided with base-broadening capital-allowance reforms and post-2008 financial-sector profit shifts, macro time-series regressions confound rate effects with base definitions; we retain the micro-econometric literature prior (0.20) as central.
