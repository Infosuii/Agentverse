"""Unit and integration tests for historical backtest and evaluation. Owner: agent-10."""
from __future__ import annotations

import pytest

from jane_avenue.contracts import BacktestCase, EvaluationReport
from jane_avenue.data import registry
from jane_avenue.evaluation import empirical_calibration_info, load_results, revenue_relative_residuals
from jane_avenue.evaluation.backtest import (
    TRAIN_CUTOFF_FY,
    PanelRow,
    build_annual_panel,
    compute_implied_elasticity,
    compute_metrics,
    fy_start_year,
    run_backtest,
)
from jane_avenue.evaluation.results import RESULTS_PATH
from jane_avenue.evaluation.run import DOCS_EVAL_PATH, run_evaluation


def test_chronological_split_has_no_test_years_in_training() -> None:
    bt = run_backtest()
    train_cases = [c for c in bt.cases if c.split == "train"]
    test_cases = [c for c in bt.cases if c.split == "test"]
    assert train_cases and test_cases

    train_years = {fy_start_year(c.fiscal_year) for c in train_cases}
    test_years = {fy_start_year(c.fiscal_year) for c in test_cases}
    assert max(train_years) <= TRAIN_CUTOFF_FY
    assert min(test_years) >= TRAIN_CUTOFF_FY + 1
    assert train_years.isdisjoint(test_years)

    # Verify chronological ordering is preserved in cases
    case_years = [fy_start_year(c.fiscal_year) for c in bt.cases]
    assert case_years == sorted(case_years)


def test_metrics_on_toy_data() -> None:
    obs = [100.0, 200.0, 50.0, 150.0]
    pred = [110.0, 180.0, 55.0, 150.0]
    naive = [100.0, 190.0, 50.0, 140.0]
    rate_changes = [2.0, -2.0, 0.0, 1.0]

    mae, rmse, mape, dir_acc = compute_metrics(
        obs, pred, naive_baseline=naive, rate_changes_pp=rate_changes
    )
    # Absolute errors: [10, 20, 5, 0] -> mean = 35 / 4 = 8.75
    assert mae == pytest.approx(8.75)
    # Squared errors: [100, 400, 25, 0] -> mean = 525 / 4 = 131.25 -> sqrt = 11.456439
    assert rmse == pytest.approx(131.25**0.5)
    # Relative errors (%): [10%, 10%, 10%, 0%] -> mean = 7.5%
    assert mape == pytest.approx(7.5)
    # Rate-change indices are 0 (+2pp), 1 (-2pp), 3 (+1pp):
    # idx 0: obs-naive = 0, pred-naive = +10 -> mismatch (0)
    # idx 1: obs-naive = +10, pred-naive = -10 -> mismatch (0)
    # idx 3: obs-naive = +10, pred-naive = +10 -> match (1)
    assert dir_acc == pytest.approx(1.0 / 3.0)


def test_residuals_returns_none_below_8_cases() -> None:
    few_cases = [
        BacktestCase(
            case_id=f"C-{i}",
            fiscal_year=f"{2010 + i}-{str(2011 + i)[-2:]}",
            split="test",
            target="ct_receipts_gbp_bn",
            observed=50.0,
            predictions={"jane_behavioural": 52.5},
        )
        for i in range(7)
    ]
    assert revenue_relative_residuals(few_cases) is None
    assert empirical_calibration_info(few_cases) is None

    eight_cases = [
        *few_cases,
        BacktestCase(
            case_id="C-7",
            fiscal_year="2017-18",
            split="test",
            target="ct_receipts_gbp_bn",
            observed=50.0,
            predictions={"jane_behavioural": 47.5},
        ),
    ]
    residuals = revenue_relative_residuals(eight_cases)
    assert residuals is not None
    assert len(residuals) == 8
    assert residuals[0] == pytest.approx(0.05)
    assert residuals[-1] == pytest.approx(-0.05)

    cal_info = empirical_calibration_info(eight_cases)
    assert cal_info is not None
    assert cal_info["n"] == 8
    assert cal_info["test_period"] == "FY2010-11–FY2017-18"
    assert isinstance(cal_info["loo_covered"], int)
    assert 0.0 <= float(cal_info["loo_coverage_90"]) <= 1.0  # type: ignore[arg-type]


def test_report_validates_and_files_exist() -> None:
    report = run_evaluation(live=False, write_files=True)
    assert isinstance(report, EvaluationReport)
    assert RESULTS_PATH.exists()
    assert DOCS_EVAL_PATH.exists()

    loaded = load_results()
    assert loaded.dataset_version == report.dataset_version
    assert not loaded.is_placeholder
    assert "conditional backtest" in loaded.target_description.lower()

    method_names = {m.method for m in loaded.methods}
    assert {"naive_growth", "static", "jane_behavioural", "jane_calibrated", "linear_regression"} <= method_names

    # Rate-change cases include CT-MAIN-2023 with official costing reference
    by_id = {c.case_id: c for c in loaded.cases}
    assert "CT-MAIN-2023" in by_id
    assert by_id["CT-MAIN-2023"].official_costing_gbp_bn is not None

    residuals = revenue_relative_residuals()
    assert residuals is not None
    assert len(residuals) >= 8


def test_placeholder_fallback_when_series_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "load_series", lambda _sid: None)
    panel = build_annual_panel()
    assert panel
    assert all(r.is_placeholder for r in panel)
    assert panel[0].profit_proxy_used == "placeholder_baseline"


def test_implied_elasticity_on_panel() -> None:
    panel = build_annual_panel()
    res = compute_implied_elasticity(panel, 0.20)
    assert res.n_obs >= 30
    assert res.implied_base_elasticity is not None
    assert res.std_error is not None
    assert "0.20" in res.summary
    assert isinstance(PanelRow, type)
