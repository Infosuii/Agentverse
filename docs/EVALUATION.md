# Jane Avenue — Evaluation, Historical Backtesting & ML Experiment

- **Generated at:** `2026-11-07T19:00:56.403961+00:00`
- **Dataset version:** `10bb93bda87c`
- **Profit growth measure (`g`):** `pnfc_gos`
- **Placeholder flag (`is_placeholder`):** `False`

## 1. Conditional Backtest Design

Conditional backtest of UK Corporation Tax receipts R_{y+1} (£bn nominal) predicted from information at fiscal year y-1, conditioning on realised 2-year profit growth (`pnfc_gos`) from y-1 to y+1. This conditional design isolates tax-policy response modelling from macroeconomic forecast error. Chronological split: train on FY <= 2007, out-of-sample test on FY >= 2008 (FY2008-09 to FY2024-25). Leave-one-out 90% (5th–95th percentile) empirical residual interval coverage on FY2008-09 to FY2024-25: 15/17 (88.2%).

- **Chronological split:** Training split `FY <= 2007` (`1985-86` to `2007-08`), out-of-sample test split `FY >= 2008` (`2008-09` onwards). No shuffling is ever performed, and no test-year outcome (`FY >= 2008`) enters training parameter estimation.
- **Engine parameter vintage (`default_parameters()`):** `main_rate_profit_share` $s = 0.85$, central `taxable_profit_elasticity` $\varepsilon = 0.20$; train-calibrated elasticity $\varepsilon$ reached the search bound of `1.500` on `[0.0, 1.5]` (corner solution; not identified on FY ≤ 2007 data because the 1984–86 cuts came with capital-allowance base-broadening, so a large $\varepsilon$ here mostly absorbs the base changes; out-of-sample MAE is statistically indistinguishable from the central prior on $n = 17$, and it is not exposed as an alternative engine parameter).
- **Empirical residual interval calibration (`jane_behavioural`):** Across $n = 17$ test years (FY2008-09 to FY2024-25), the leave-one-out 5th–95th percentile (90%) relative-error interval covered **15/17 (88.2%)** of observed outcomes.

## 2. Methods Evaluated

| Method | Label | Baseline? | Definition |
|---|---|---|---|
| `naive_growth` | Naive profit-growth baseline | Yes | R̂_{y+1} = R_{y-1} × (1 + g_{y-1→y+1}), assuming receipts grow one-for-one with the profit proxy and ignoring tax-rate changes. |
| `static` | Static tax-rate scaling baseline | Yes | R̂_{y+1} = naive × (s·t_new/t_old + (1−s)), scaling the main-rate share s of receipts proportionally to the statutory rate change with zero behavioural response. |
| `jane_behavioural` | Jane Avenue behavioural engine (central prior ε) | No | Engine static + behavioural revenue equation with central taxable-profit elasticity ε = 0.20 and main-rate profit share s = 0.85. |
| `jane_calibrated` | Jane Avenue behavioural engine (train-calibrated ε; bound hit) | No | Same structural revenue equation with elasticity ε reached the search bound of 1.500 on [0.0, 1.5] (corner solution; not identified on FY ≤ 2007 training data because the 1984–86 rate cuts coincided with capital-allowance base-broadening). Out-of-sample MAE is statistically indistinguishable from the central prior on n = 17; not exposed as an engine parameter. |
| `linear_regression` | Log-change OLS baseline | Yes | OLS regression of log(R_{y+1}/R_{y-1}) on statutory rate change Δt and log(1+g) fitted on FY ≤ 2007 training data only. |

## 3. Backtest Results by Split

Headline evaluation is on the **out-of-sample `test` split (`FY >= 2008`)**. On $n = 17$ test years, `jane_behavioural` (central micro-econometric prior) and `jane_calibrated` (bound-constrained corner solution on pre-2008 data) are **statistically indistinguishable on $n = 17$**:

| Split | Method | Baseline? | n | MAE (£bn) | RMSE (£bn) | MAPE (%) | Policy-Effect Directional Accuracy* |
|---|---|---|---:|---:|---:|---:|---:|
| `test` | `jane_calibrated` | No | 17 | 5.29 | 6.68 | 9.43% | 54.5% |
| `test` | `jane_behavioural` | No | 17 | 5.48 | 7.01 | 9.29% | 54.5% |
| `test` | `static` | Yes | 17 | 5.65 | 7.19 | 9.46% | 54.5% |
| `test` | `naive_growth` | Yes | 17 | 6.56 | 8.25 | 11.09% | 0.0%* |
| `test` | `linear_regression` | Yes | 17 | 8.35 | 10.90 | 13.89% | 45.5% |
| `train` | `linear_regression` | Yes | 25 | 3.80 | 4.88 | 14.34% | 58.3% |
| `train` | `jane_calibrated` | No | 25 | 3.91 | 4.78 | 15.60% | 50.0% |
| `train` | `naive_growth` | Yes | 25 | 3.94 | 4.82 | 15.92% | 0.0%* |
| `train` | `jane_behavioural` | No | 25 | 4.13 | 4.90 | 17.44% | 33.3% |
| `train` | `static` | Yes | 25 | 4.17 | 4.93 | 17.70% | 33.3% |

\* *Directional accuracy compares the sign of each method's predicted policy rate effect $(\hat{R}_{y+1} - \hat{R}^{\text{naive}}_{y+1})$ against the observed excess movement $(R_{y+1} - \hat{R}^{\text{naive}}_{y+1})$ on rate-change years. For `naive_growth`, directional accuracy is `0.0%` by construction because it predicts no rate effect $(\Delta \hat{R}^{\text{rate}} = 0)$.*

## 4. Highlight Cases: Statutory Rate-Change Years

> **Evidence-class note:** `observed` ($R_{y+1}$) is an **observed outcome** (total CT receipts in £bn). `official_costing_gbp_bn` is an **official costing** (ex-ante HMT/OBR policy-measure delta $\Delta R$ in £bn relative to a contemporary Budget baseline, **not** total receipts ground truth). Method columns are **model scenario** conditional predictions of $R_{y+1}$ (£bn).

| Case ID | Policy Year ($y$) | Split | Target ($y+1$) | Observed $R_{y+1}$ (£bn) | Ex-Ante Official Costing $\Delta R$ (£bn, ref only) | `naive_growth` (£bn) | `static` (£bn) | `jane_behavioural` (£bn) | `jane_calibrated` (£bn) | `linear_regression` (£bn) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `CT-MAIN-1983` | 1983-84 | `train` | ct_receipts_gbp_bn (1984-85) | 8.34 | — | 7.55 | 6.69 | 6.84 | 7.95 | 9.25 |
| `CT-MAIN-1984` | 1984-85 | `train` | ct_receipts_gbp_bn (1985-86) | 10.71 | — | 8.40 | 6.97 | 7.18 | 8.77 | 11.02 |
| `CT-MAIN-1985` | 1985-86 | `train` | ct_receipts_gbp_bn (1986-87) | 13.49 | — | 9.72 | 7.88 | 8.10 | 9.71 | 12.17 |
| `CT-MAIN-1986` | 1986-87 | `train` | ct_receipts_gbp_bn (1987-88) | 15.73 | — | 12.90 | 11.53 | 11.69 | 12.76 | 14.70 |
| `CT-MAIN-1990` | 1990-91 | `train` | ct_receipts_gbp_bn (1991-92) | 18.26 | — | 22.35 | 21.27 | 21.38 | 22.10 | 22.86 |
| `CT-MAIN-1991` | 1991-92 | `train` | ct_receipts_gbp_bn (1992-93) | 15.78 | — | 21.55 | 21.01 | 21.07 | 21.42 | 21.34 |
| `CT-MAIN-1997` | 1997-98 | `train` | ct_receipts_gbp_bn (1998-99) | 30.03 | — | 28.69 | 27.21 | 27.35 | 28.25 | 29.27 |
| `CT-MAIN-1999` | 1999-00 | `train` | ct_receipts_gbp_bn (2000-01) | 32.42 | — | 29.44 | 28.63 | 28.70 | 29.16 | 28.95 |
| `CT-MAIN-2008` | 2008-09 | `test` | ct_receipts_gbp_bn (2009-10) | 36.63 | — | 45.45 | 42.87 | 43.08 | 44.43 | 45.45 |
| `CT-MAIN-2011` | 2011-12 | `test` | ct_receipts_gbp_bn (2012-13) | 39.84 | — | 47.59 | 41.81 | 42.19 | 44.74 | 51.71 |
| `CT-MAIN-2012` | 2012-13 | `test` | ct_receipts_gbp_bn (2013-14) | 38.93 | -0.73 | 46.09 | 41.57 | 41.85 | 43.70 | 48.75 |
| `CT-MAIN-2013` | 2013-14 | `test` | ct_receipts_gbp_bn (2014-15) | 41.09 | -0.82 | 45.55 | 40.71 | 40.97 | 42.73 | 48.96 |
| `CT-MAIN-2014` | 2014-15 | `test` | ct_receipts_gbp_bn (2015-16) | 43.02 | — | 42.88 | 38.12 | 38.37 | 39.99 | 45.56 |
| `CT-MAIN-2015` | 2015-16 | `test` | ct_receipts_gbp_bn (2016-17) | 49.30 | — | 41.66 | 39.98 | 40.06 | 40.62 | 41.39 |
| `CT-MAIN-2017` | 2017-18 | `test` | ct_receipts_gbp_bn (2018-19) | 56.30 | -1.60 | 53.91 | 51.62 | 51.73 | 52.44 | 54.81 |
| `CT-MAIN-2023` | 2023-24 | `test` | ct_receipts_gbp_bn (2024-25) | 95.70 | +16.25 | 84.83 | 107.60 | 106.15 | 97.26 | 72.86 |

## 5. Implied Taxable-Profit Elasticity Check

OLS of log((receipts/t)/pnfc_gos) on log(1-t) over n=44 fiscal years (controlling for real GDP growth) yields an implied base elasticity of 2.642 (SE 0.185), compared with the engine central prior of 0.20. Because UK rate cuts in the 1980s and 2010s coincided with base-broadening capital-allowance reforms and post-2008 financial-sector profit shifts, macro time-series regressions confound rate effects with base definitions; we retain the micro-econometric literature prior (0.20) as central.

## 9. Limitations & Honest Caveats

- Conditional backtest design: predictions of R_{y+1} condition on realised 2-year profit growth from y-1 to y+1 (measured via `pnfc_gos`). This isolates tax-rate response modelling from macroeconomic forecast error, so out-of-sample errors in unconditional real-time forecasting would be larger.
- Small sample of policy regime shifts: UK corporation tax main-rate history since FY1982 contains only 16 implemented statutory rate changes (8 in the FY <= 2007 training split and 8 in the FY >= 2008 test split).
- Simultaneous base-broadening and relief confounders: major rate changes coincided with structural base changes—most notably the 1983–1986 phased rate cuts paired with first-year capital-allowance abolition, and the April 2023 rise (19% -> 25%) paired with full expensing for plant & machinery and the 19% small profits rate / marginal relief.
- Train-calibrated elasticity corner solution: fitting ε by nonlinear least squares on FY <= 2007 reached the search bound of 1.500 on [0.0, 1.5] (not identified on FY <= 2007 data because the 1984–86 cuts came with capital-allowance base-broadening, so a large ε mostly absorbs the base changes). Its out-of-sample MAE on n = 17 test years is statistically indistinguishable from the central prior (ε = 0.20), so it is not exposed as an alternative engine parameter.
- Official costings are not ground truth: `official_costing_gbp_bn` reports ex-ante HMT/OBR policy costings (revenue delta relative to a contemporary Budget baseline under ex-ante macro assumptions), whereas `observed` and model `predictions` are total fiscal-year CT receipts R_{y+1} (£bn).
- Receipts collection lags and composition: CT receipts combine onshore and offshore (North Sea ring-fence) regimes, Quarterly Instalment Payments (QIPs) timing transitions, bank surcharge, and financial-sector loss carry-forwards.
- OLS of log((receipts/t)/pnfc_gos) on log(1-t) over n=44 fiscal years (controlling for real GDP growth) yields an implied base elasticity of 2.642 (SE 0.185), compared with the engine central prior of 0.20. Because UK rate cuts in the 1980s and 2010s coincided with base-broadening capital-allowance reforms and post-2008 financial-sector profit shifts, macro time-series regressions confound rate effects with base definitions; we retain the micro-econometric literature prior (0.20) as central.
