"""CLI entrypoint `python -m jane_avenue.evaluation.run [--live]`. Owner: agent-10."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..contracts import EvaluationReport, utcnow
from ..data import registry
from .backtest import BacktestOutput, run_backtest
from .results import RESULTS_PATH

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_EVAL_PATH = REPO_ROOT / "docs" / "EVALUATION.md"


def _build_limitations(bt: BacktestOutput) -> list[str]:
    lims = [
        "Conditional backtest design: predictions of R_{y+1} condition on realised 2-year profit growth from y-1 to y+1 "
        f"(measured via `{bt.profit_proxy_used}`). This isolates tax-rate response modelling from macroeconomic forecast error, "
        "so out-of-sample errors in unconditional real-time forecasting would be larger.",
        "Small sample of policy regime shifts: UK corporation tax main-rate history since FY1982 contains only 16 implemented "
        "statutory rate changes (8 in the FY <= 2007 training split and 8 in the FY >= 2008 test split).",
        "Simultaneous base-broadening and relief confounders: major rate changes coincided with structural base changes—"
        "most notably the 1983–1986 phased rate cuts paired with first-year capital-allowance abolition, and the April 2023 "
        "rise (19% -> 25%) paired with full expensing for plant & machinery and the 19% small profits rate / marginal relief.",
        "Official costings are not ground truth: `official_costing_gbp_bn` reports ex-ante HMT/OBR policy costings (revenue delta "
        "relative to a contemporary Budget baseline under ex-ante macro assumptions), whereas `observed` and model `predictions` "
        "are total fiscal-year CT receipts R_{y+1} (£bn).",
        "Receipts collection lags and composition: CT receipts combine onshore and offshore (North Sea ring-fence) regimes, "
        "Quarterly Instalment Payments (QIPs) timing transitions, bank surcharge, and financial-sector loss carry-forwards.",
        bt.implied_elasticity.summary,
    ]
    if bt.is_placeholder:
        lims.insert(
            0,
            "PLACEHOLDER DATA ACTIVE: One or more input series came from the placeholder registry stub (`is_placeholder=True`). "
            "Numbers will automatically refresh from curated HMRC/OBR/ONS series once merged.",
        )
    return lims


def render_evaluation_markdown(report: EvaluationReport, bt: BacktestOutput) -> str:
    """Render `docs/EVALUATION.md` from the EvaluationReport and BacktestOutput."""
    lines: list[str] = [
        "# Jane Avenue — Evaluation, Historical Backtesting & ML Experiment",
        "",
        f"- **Generated at:** `{report.generated_at.isoformat()}`",
        f"- **Dataset version:** `{report.dataset_version}`",
        f"- **Profit growth measure (`g`):** `{bt.profit_proxy_used}`",
        f"- **Placeholder flag (`is_placeholder`):** `{report.is_placeholder}`",
        "",
        "## 1. Conditional Backtest Design",
        "",
        report.target_description,
        "",
        "- **Chronological split:** Training split `FY <= 2007` (`1985-86` to `2007-08`), out-of-sample test split `FY >= 2008` (`2008-09` onwards). No shuffling is ever performed, and no test-year outcome (`FY >= 2008`) enters training parameter estimation.",
        f"- **Engine central parameters:** `main_rate_profit_share` $s = {bt.main_rate_profit_share:.2f}$, central `taxable_profit_elasticity` $\\varepsilon = {bt.prior_eps if hasattr(bt, 'prior_eps') else bt.prior_elasticity:.2f}$, train-calibrated elasticity $\\hat{{\\varepsilon}}_{{\\text{{train}}}} = {bt.calibrated_elasticity:.3f}$.",
    ]
    if bt.loo_coverage_90 is not None:
        lines.append(
            f"- **Empirical residual interval calibration (`jane_behavioural`):** Across $n = {len(bt.test_relative_residuals)}$ test years ({bt.test_period}), "
            f"the leave-one-out 5th–95th percentile (90%) relative-error interval covered **{bt.loo_covered_count}/{len(bt.test_relative_residuals)} ({bt.loo_coverage_90 * 100:.1f}%)** of observed outcomes."
        )
    lines.extend(
        [
            "",
            "## 2. Methods Evaluated",
            "",
            "| Method | Label | Baseline? | Definition |",
            "|---|---|---|---|",
        ]
    )
    seen_methods: set[str] = set()
    for m in report.methods:
        if m.method in seen_methods:
            continue
        seen_methods.add(m.method)
        lines.append(
            f"| `{m.method}` | {m.label} | {'Yes' if m.is_baseline else 'No'} | {m.description} |"
        )

    lines.extend(
        [
            "",
            "## 3. Backtest Results by Split",
            "",
            "Headline evaluation is on the **out-of-sample `test` split (`FY >= 2008`)**:",
            "",
            "| Split | Method | Baseline? | n | MAE (£bn) | RMSE (£bn) | MAPE (%) | Policy-Effect Directional Accuracy |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for m in sorted(report.methods, key=lambda x: (0 if x.split == "test" else 1, x.mae)):
        mape_str = f"{m.mape_pct:.2f}%" if m.mape_pct is not None else "—"
        dir_str = f"{m.directional_accuracy * 100:.1f}%" if m.directional_accuracy is not None else "—"
        lines.append(
            f"| `{m.split}` | `{m.method}` | {'Yes' if m.is_baseline else 'No'} | {m.n} | {m.mae:.2f} | {m.rmse:.2f} | {mape_str} | {dir_str} |"
        )

    lines.extend(
        [
            "",
            "## 4. Highlight Cases: Statutory Rate-Change Years",
            "",
            "> **Evidence-class note:** `observed` ($R_{y+1}$) is an **observed outcome** (total CT receipts in £bn). "
            "`official_costing_gbp_bn` is an **official costing** (ex-ante HMT/OBR policy-measure delta $\\Delta R$ in £bn relative to a contemporary Budget baseline, **not** total receipts ground truth). "
            "Method columns are **model scenario** conditional predictions of $R_{y+1}$ (£bn).",
            "",
            "| Case ID | Policy Year ($y$) | Split | Target ($y+1$) | Observed $R_{y+1}$ (£bn) | Ex-Ante Official Costing $\\Delta R$ (£bn, ref only) | `naive_growth` (£bn) | `static` (£bn) | `jane_behavioural` (£bn) | `jane_calibrated` (£bn) | `linear_regression` (£bn) | `lightgbm` (£bn) |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    highlight_cases = [c for c in report.cases if c.case_id.startswith("CT-MAIN-")]
    if not highlight_cases:
        highlight_cases = report.cases
    for c in highlight_cases:
        cost_str = f"{c.official_costing_gbp_bn:+.2f}" if c.official_costing_gbp_bn is not None else "—"
        p = c.predictions
        lgbm_str = f"{p['lightgbm']:.2f}" if "lightgbm" in p else "—"
        lines.append(
            f"| `{c.case_id}` | {c.fiscal_year} | `{c.split}` | {c.target} | {c.observed:.2f} | {cost_str} | "
            f"{p.get('naive_growth', 0.0):.2f} | {p.get('static', 0.0):.2f} | {p.get('jane_behavioural', 0.0):.2f} | "
            f"{p.get('jane_calibrated', 0.0):.2f} | {p.get('linear_regression', 0.0):.2f} | {lgbm_str} |"
        )

    lines.extend(
        [
            "",
            "## 5. Implied Taxable-Profit Elasticity Check",
            "",
            bt.implied_elasticity.summary,
            "",
        ]
    )

    if report.ml_experiment is not None:
        ml = report.ml_experiment
        lines.extend(
            [
                "## 6. Out-of-Sample Machine Learning Experiment",
                "",
                f"- **Model:** `{ml.model}`",
                f"- **Features:** `{', '.join(ml.features)}`",
                f"- **Train / Test periods:** `{ml.train_period}` / `{ml.test_period}`",
                f"- **Test MAE (£bn):** `{ml.test_mae:.2f}` vs best baseline `{ml.best_baseline}` (`{ml.best_baseline_mae:.2f}`)"
                if (ml.test_mae is not None and ml.best_baseline_mae is not None)
                else f"- **Best baseline:** `{ml.best_baseline}`",
                f"- **Adopted in product (`adopted`):** `{ml.adopted}`",
                f"- **Conclusion:** {ml.conclusion}",
                "",
            ]
        )

    if report.research_eval is not None:
        reval = report.research_eval
        lines.extend(
            [
                "## 7. Research Agent Citation & Fact Accuracy Evaluation",
                "",
                f"- **Questions evaluated:** `{reval.n_questions}` (`mode={reval.mode}`)",
                f"- **Fact accuracy:** `{reval.fact_accuracy * 100:.1f}%`" if reval.fact_accuracy is not None else "- **Fact accuracy:** N/A",
                f"- **Citation URL validity (HTTP 200):** `{reval.citation_url_valid_rate * 100:.1f}%`" if reval.citation_url_valid_rate is not None else "- **Citation URL validity:** N/A",
                f"- **Verified quote match rate:** `{reval.quote_match_rate * 100:.1f}%`" if reval.quote_match_rate is not None else "- **Quote match rate:** N/A",
                f"- **Hallucinated sources:** `{reval.hallucinated_sources}`",
                f"- **Official (Tier 1) source share:** `{reval.official_source_share * 100:.1f}%`" if reval.official_source_share is not None else "- **Official source share:** N/A",
                f"- **Notes:** {reval.notes}",
                "",
            ]
        )

    if report.verification_eval is not None:
        veval = report.verification_eval
        det_rate = (veval.detected / veval.n_fault_cases * 100.0) if veval.n_fault_cases > 0 else 0.0
        lines.extend(
            [
                "## 8. Independent Verifier Fault-Injection Evaluation",
                "",
                f"- **Injected fault cases detected:** `{veval.detected}/{veval.n_fault_cases} ({det_rate:.1f}%)`",
                f"- **Clean-case blocking false positives:** `{veval.false_positives}/{veval.n_clean_cases}`",
                f"- **Notes:** {veval.notes}",
                "",
            ]
        )

    lines.extend(
        [
            "## 9. Limitations & Honest Caveats",
            "",
        ]
    )
    for lim in report.limitations:
        lines.append(f"- {lim}")
    lines.append("")
    return "\n".join(lines)


def run_evaluation(*, live: bool = False, write_files: bool = True) -> EvaluationReport:
    """Execute the evaluation suite, write `results/latest.json` and `docs/EVALUATION.md`, and return the report."""
    bt = run_backtest()

    # Optional M2 components if already implemented
    ml_exp = None
    methods = list(bt.methods)
    cases = list(bt.cases)
    try:
        from .ml import run_ml_experiment  # type: ignore[import-not-found]

        ml_exp, ml_summaries, cases = run_ml_experiment(bt)
        methods.extend(ml_summaries)
    except ImportError:
        pass

    research_ev = None
    try:
        from .research_eval import evaluate_research_agent  # type: ignore[import-not-found]

        research_ev = evaluate_research_agent(live=live)
    except ImportError:
        pass

    verifier_ev = None
    try:
        from .verifier_eval import evaluate_verifier  # type: ignore[import-not-found]

        verifier_ev = evaluate_verifier()
    except ImportError:
        pass

    cov_clause = (
        f" Leave-one-out 90% (5th–95th percentile) empirical residual interval coverage on {bt.test_period}: "
        f"{bt.loo_covered_count}/{len(bt.test_relative_residuals)} ({bt.loo_coverage_90 * 100:.1f}%)."
        if bt.loo_coverage_90 is not None
        else ""
    )
    target_desc = (
        "Conditional backtest of UK Corporation Tax receipts R_{y+1} (£bn nominal) predicted from information at "
        f"fiscal year y-1, conditioning on realised 2-year profit growth (`{bt.profit_proxy_used}`) from y-1 to y+1. "
        "This conditional design isolates tax-policy response modelling from macroeconomic forecast error. "
        f"Chronological split: train on FY <= 2007, out-of-sample test on FY >= 2008 ({bt.test_period})."
        + cov_clause
    )

    report = EvaluationReport(
        generated_at=utcnow(),
        dataset_version=registry.DATASET_VERSION,
        target_description=target_desc,
        methods=methods,
        cases=cases,
        ml_experiment=ml_exp,
        research_eval=research_ev,
        verification_eval=verifier_ev,
        limitations=_build_limitations(bt),
        is_placeholder=bt.is_placeholder,
    )

    if write_files:
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        DOCS_EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOCS_EVAL_PATH.write_text(render_evaluation_markdown(report, bt), encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Jane Avenue evaluation and backtest suite.")
    parser.add_argument("--live", action="store_true", help="Run live research gold-set evaluation using Gemini.")
    args = parser.parse_args(argv)
    report = run_evaluation(live=args.live, write_files=True)
    test_methods = [m for m in report.methods if m.split == "test"]
    best = min(test_methods, key=lambda m: m.mae) if test_methods else None
    print(
        f"Wrote {RESULTS_PATH} and {DOCS_EVAL_PATH} "
        f"(dataset_version={report.dataset_version}, is_placeholder={report.is_placeholder}, "
        f"best_test_method={best.method if best else 'N/A'} MAE={best.mae if best else 'N/A'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
