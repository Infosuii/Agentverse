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
from jane_avenue.evaluation.ml import ML_FEATURES, run_ml_experiment
from jane_avenue.evaluation.research_eval import RUNS_PATH, evaluate_research_agent, load_gold_questions
from jane_avenue.evaluation.results import RESULTS_PATH
from jane_avenue.evaluation.run import DOCS_EVAL_PATH, run_evaluation
from jane_avenue.evaluation.verifier_eval import evaluate_verifier


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

    # Verify corner-solution bound detection is flagged honestly
    assert bt.calibrated_at_bound is True
    cal_methods = [m for m in bt.methods if m.method == "jane_calibrated"]
    assert cal_methods
    assert "search bound" in cal_methods[0].description.lower()
    assert "corner solution" in cal_methods[0].description.lower()


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


def test_fallback_rates_exclude_reversed_2020_proposal_and_preserve_costing_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_load_series = registry.load_series
    monkeypatch.setattr(
        registry,
        "load_series",
        lambda sid: None if sid == "ct_main_rate" else real_load_series(sid),
    )
    panel = build_annual_panel()
    by_fy = {r.fiscal_year: r for r in panel}
    assert not any(r.is_placeholder for r in panel)
    assert by_fy["2020-21"].main_rate_pct == pytest.approx(19.0)
    assert by_fy["2021-22"].main_rate_pct == pytest.approx(19.0)
    assert by_fy["2022-23"].main_rate_pct == pytest.approx(19.0)

    report = run_evaluation(live=False, write_files=False)
    assert "N445" in report.target_description
    assert "gross of tax credits" in report.target_description
    cases_by_id = {c.case_id: c for c in report.cases}
    assert "D-budget2012" in cases_by_id["CT-MAIN-2012"].notes
    assert "joint phased package" in cases_by_id["CT-MAIN-2012"].notes.lower()
    assert "D-budget2015" in cases_by_id["CT-MAIN-2017"].notes
    assert "Summer Budget 2015" in cases_by_id["CT-MAIN-2017"].notes


def test_ml_experiment_out_of_sample_and_not_adopted() -> None:
    bt = run_backtest()
    ml_res, ml_summaries, updated_cases = run_ml_experiment(bt)
    assert ml_res.features == list(ML_FEATURES)
    assert len(ml_res.features) == 6
    assert ml_res.test_mae is not None
    assert ml_res.best_baseline_mae is not None
    assert ml_res.test_mae > ml_res.best_baseline_mae
    assert ml_res.adopted is False
    assert "NOT ADOPTED" in ml_res.conclusion
    assert len(ml_summaries) == 2
    assert all("lightgbm" in c.predictions for c in updated_cases)


def test_research_eval_offline_rescores_gold_runs() -> None:
    questions = load_gold_questions()
    assert len(questions) == 15
    assert RUNS_PATH.exists()

    reval = evaluate_research_agent(live=False)
    assert reval.n_questions == 15
    assert reval.mode == "cached"
    assert reval.fact_accuracy is not None and reval.fact_accuracy >= 0.90
    assert reval.citation_url_valid_rate is not None and reval.citation_url_valid_rate >= 0.90
    assert reval.quote_match_rate is not None and reval.quote_match_rate >= 0.90
    assert reval.hallucinated_sources == 0
    assert reval.official_source_share is not None and reval.official_source_share >= 0.80


def test_verifier_eval_detects_injected_faults_with_zero_false_positives() -> None:
    veval = evaluate_verifier()
    assert veval.n_fault_cases == 18
    assert veval.detected == 18
    assert veval.n_clean_cases >= 1
    assert veval.false_positives == 0
    assert len(veval.by_fault) == 18
    assert all(veval.by_fault.values())
