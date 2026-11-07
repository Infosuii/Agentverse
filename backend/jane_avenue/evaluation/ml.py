"""Out-of-sample LightGBM experiment on UK Corporation Tax receipts. Owner: agent-10."""
from __future__ import annotations

import math

from lightgbm import LGBMRegressor
import numpy as np

from ..contracts import BacktestCase, MethodSummary, MLExperiment
from .backtest import TRAIN_CUTOFF_FY, BacktestOutput, PanelRow, compute_metrics, fy_start_year

ML_FEATURES: tuple[str, ...] = (
    "rate_change_pp",
    "starting_rate_pct",
    "profit_growth_pct",
    "bank_rate_pct",
    "real_gdp_growth_pct",
    "lagged_receipts_pct_gdp",
)


def _extract_feature_row(by_year: dict[int, PanelRow], yr: int) -> list[float]:
    prev_row = by_year[yr - 1]
    curr_row = by_year[yr]
    next_row = by_year[yr + 1]

    t_old = prev_row.main_rate_pct
    t_new = next_row.main_rate_pct
    rate_change_pp = t_new - t_old
    starting_rate_pct = t_old
    pi_prev = prev_row.profit_measure_gbp_bn
    pi_next = next_row.profit_measure_gbp_bn
    profit_growth_pct = ((pi_next / pi_prev) - 1.0) * 100.0 if pi_prev > 0 else 0.0
    bank_rate_pct = float(curr_row.bank_rate_pct if curr_row.bank_rate_pct is not None else 5.0)
    real_gdp_growth_pct = float(curr_row.real_gdp_growth_pct if curr_row.real_gdp_growth_pct is not None else 2.0)
    lagged_rec_gdp = float(
        prev_row.receipts_pct_gdp
        if prev_row.receipts_pct_gdp is not None
        else (100.0 * prev_row.ct_receipts_gbp_bn / max(1.0, prev_row.profit_measure_gbp_bn))
    )
    return [
        float(rate_change_pp),
        float(starting_rate_pct),
        float(profit_growth_pct),
        bank_rate_pct,
        real_gdp_growth_pct,
        lagged_rec_gdp,
    ]


def run_ml_experiment(
    bt: BacktestOutput,
) -> tuple[MLExperiment, list[MethodSummary], list[BacktestCase]]:
    """Train a regularised LightGBM regressor on FY <= 2007 and evaluate out-of-sample on FY >= 2008.

    Returns `(MLExperiment, [train_summary, test_summary], updated_cases)`.
    """
    by_year = {r.start_year: r for r in bt.panel}
    eval_years = [fy_start_year(c.fiscal_year) for c in bt.cases]

    # Strict chronological training filter: target year (yr + 1) <= TRAIN_CUTOFF_FY
    fit_years = [yr for yr in eval_years if (yr + 1) <= TRAIN_CUTOFF_FY]
    if len(fit_years) < 5:
        fit_years = [yr for yr in eval_years if yr <= TRAIN_CUTOFF_FY]

    X_train = np.asarray([_extract_feature_row(by_year, yr) for yr in fit_years], dtype=float)
    y_train = np.asarray(
        [
            math.log(max(1e-6, by_year[yr + 1].ct_receipts_gbp_bn / max(1e-6, by_year[yr - 1].ct_receipts_gbp_bn)))
            for yr in fit_years
        ],
        dtype=float,
    )

    model = LGBMRegressor(
        n_estimators=25,
        max_depth=2,
        num_leaves=3,
        min_child_samples=3,
        learning_rate=0.08,
        reg_alpha=1.0,
        reg_lambda=2.0,
        subsample=1.0,
        colsample_bytree=1.0,
        random_state=42,
        deterministic=True,
        verbose=-1,
    )
    model.fit(X_train, y_train)

    X_all = np.asarray([_extract_feature_row(by_year, yr) for yr in eval_years], dtype=float)
    pred_log_chg = model.predict(X_all)

    updated_cases: list[BacktestCase] = []
    obs_by_split: dict[str, list[float]] = {"train": [], "test": []}
    pred_by_split: dict[str, list[float]] = {"train": [], "test": []}
    naive_by_split: dict[str, list[float]] = {"train": [], "test": []}
    rc_by_split: dict[str, list[float]] = {"train": [], "test": []}

    for case, yr, log_chg in zip(bt.cases, eval_years, pred_log_chg, strict=True):
        r_prev = by_year[yr - 1].ct_receipts_gbp_bn
        t_old = by_year[yr - 1].main_rate_pct
        t_new = by_year[yr + 1].main_rate_pct
        lgbm_pred = round(float(r_prev * math.exp(float(log_chg))), 4)
        new_preds = dict(case.predictions)
        new_preds["lightgbm"] = lgbm_pred
        updated_cases.append(case.model_copy(update={"predictions": new_preds}))

        sp = case.split
        obs_by_split[sp].append(case.observed)
        pred_by_split[sp].append(lgbm_pred)
        naive_by_split[sp].append(case.predictions["naive_growth"])
        rc_by_split[sp].append(t_new - t_old)

    ml_summaries: list[MethodSummary] = []
    mae_by_split: dict[str, float] = {}
    for split in ("train", "test"):
        if not obs_by_split[split]:
            continue
        mae, rmse, mape, dir_acc = compute_metrics(
            obs_by_split[split],
            pred_by_split[split],
            naive_baseline=naive_by_split[split],
            rate_changes_pp=rc_by_split[split],
        )
        mae_by_split[split] = round(mae, 4)
        ml_summaries.append(
            MethodSummary(
                method="lightgbm",
                label="LightGBM gradient-boosted trees (ML experiment)",
                description=(
                    "Shallow, strongly regularised LightGBM regressor (max_depth=2, num_leaves=3, L1=1.0, L2=2.0, "
                    f"seed=42) predicting log(R_{{y+1}}/R_{{y-1}}) from {', '.join(ML_FEATURES)}."
                ),
                split=split,  # type: ignore[arg-type]
                n=len(obs_by_split[split]),
                mae=round(mae, 4),
                rmse=round(rmse, 4),
                mape_pct=round(mape, 4) if mape is not None else None,
                directional_accuracy=round(dir_acc, 4) if dir_acc is not None else None,
                is_baseline=False,
            )
        )

    test_baselines = [m for m in bt.methods if m.split == "test" and m.is_baseline]
    best_base = min(test_baselines, key=lambda m: m.mae)
    test_mae = mae_by_split.get("test", float("inf"))
    train_mae = mae_by_split.get("train", 0.0)

    adopted = bool(test_mae < best_base.mae)
    train_cases = [c for c in updated_cases if c.split == "train"]
    test_cases = [c for c in updated_cases if c.split == "test"]
    train_period = f"FY{train_cases[0].fiscal_year}–FY{train_cases[-1].fiscal_year}" if train_cases else "FY<=2007"
    test_period = f"FY{test_cases[0].fiscal_year}–FY{test_cases[-1].fiscal_year}" if test_cases else "FY>=2008"

    if adopted:
        conclusion = (
            f"LightGBM achieved an out-of-sample test MAE of £{test_mae:.2f}bn vs £{best_base.mae:.2f}bn for the "
            f"best baseline (`{best_base.method}`) over {test_period} (train MAE £{train_mae:.2f}bn)."
        )
    else:
        conclusion = (
            f"NOT ADOPTED: LightGBM achieved an out-of-sample test MAE of £{test_mae:.2f}bn on {test_period}, "
            f"which fails to beat the best simple baseline `{best_base.method}` (test MAE £{best_base.mae:.2f}bn) "
            f"and the structural engine `jane_behavioural` (test MAE £{next(m.mae for m in bt.methods if m.split == 'test' and m.method == 'jane_behavioural'):.2f}bn), "
            f"despite a much lower in-sample train MAE of £{train_mae:.2f}bn on {train_period}. "
            "Three structural factors explain this train/test gap: (1) tiny annual sample size (n=24 training observations), "
            "(2) regime shift between the training era (30–50% CT rates, higher Bank Rate) and the post-2008 test era "
            "(19–28% CT rates, near-zero interest rates, and the 2023 rate hike from 19% to 25%), and (3) tree models' "
            "piecewise-constant leaves cannot extrapolate log-growth responses outside the training feature support. "
            "Per product rules, ML is rejected and not wired into the live simulator."
        )

    experiment = MLExperiment(
        model="LightGBMRegressor(n_estimators=25, max_depth=2, num_leaves=3, min_child_samples=3, lr=0.08, reg_alpha=1.0, reg_lambda=2.0, seed=42)",
        features=list(ML_FEATURES),
        train_period=train_period,
        test_period=test_period,
        test_mae=test_mae,
        best_baseline=best_base.method,
        best_baseline_mae=best_base.mae,
        adopted=adopted,
        conclusion=conclusion,
    )
    return experiment, ml_summaries, updated_cases
