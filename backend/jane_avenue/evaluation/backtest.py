"""Historical UK Corporation Tax backtest harness and baselines. Owner: agent-10."""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

import jane_avenue.engine as engine_pkg

from ..config import get_settings
from ..contracts import BacktestCase, MethodSummary
from ..data import registry
from ..engine import default_parameters

TRAIN_CUTOFF_FY = 2007  # Train on FY <= 2007, test on FY >= 2008 (chronological split)


def fy_start_year(fiscal_year: str) -> int:
    """Return integer start year of a UK fiscal year string 'YYYY-YY'."""
    return int(str(fiscal_year)[:4])


def format_fy(start_year: int) -> str:
    """Format an integer start year into 'YYYY-YY'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _revenue_static_behavioural(
    t0: float,
    t1: float,
    receipts: float,
    *,
    main_rate_profit_share: float,
    elasticity: float,
    timing: float = 1.0,
) -> tuple[float, float]:
    """Call engine.revenue_static_behavioural if present, else use exact Master Prompt §9.5 equations."""
    fn = getattr(engine_pkg, "revenue_static_behavioural", None)
    if callable(fn):
        res = fn(
            t0,
            t1,
            receipts,
            main_rate_profit_share=main_rate_profit_share,
            elasticity=elasticity,
            timing=timing,
        )
        return float(res[0]), float(res[1])
    if t0 <= 0:
        return 0.0, 0.0
    b0 = main_rate_profit_share * receipts / t0
    delta_static = (t1 - t0) * b0 * timing
    b1 = b0 * (((1.0 - t1) / (1.0 - t0)) ** elasticity)
    delta_behav = (t1 * b1 - t0 * b0) * timing
    return float(delta_static), float(delta_behav)


@dataclass
class PanelRow:
    """One fiscal year row in the annual evaluation panel."""

    fiscal_year: str
    start_year: int
    ct_receipts_gbp_bn: float
    main_rate_pct: float
    rate_change_pp: float
    profit_measure_gbp_bn: float
    profit_growth_pct: float | None
    profit_proxy_used: str  # "pnfc_gos" | "nominal_gdp" | "placeholder_baseline"
    bank_rate_pct: float | None = None
    real_gdp_growth_pct: float | None = None
    receipts_pct_gdp: float | None = None
    official_costing_gbp_bn: float | None = None
    change_id: str | None = None
    is_placeholder: bool = False


@dataclass
class ImpliedElasticityResult:
    """Result of regressing log(receipts / profits) on log(1 - t), controlling for the cycle."""

    n_obs: int
    implied_base_elasticity: float | None
    std_error: float | None
    engine_prior_elasticity: float
    profit_proxy_used: str
    summary: str


@dataclass
class BacktestOutput:
    """Complete output from running the historical CT revenue backtest."""

    panel: list[PanelRow]
    methods: list[MethodSummary]
    cases: list[BacktestCase]
    calibrated_elasticity: float
    prior_elasticity: float
    main_rate_profit_share: float
    profit_proxy_used: str
    is_placeholder: bool
    test_relative_residuals: list[float]
    test_period: str
    loo_coverage_90: float | None
    loo_covered_count: int
    implied_elasticity: ImpliedElasticityResult
    notes: list[str] = field(default_factory=list)


def _series_map(series_id: str) -> dict[str, float]:
    ts = registry.load_series(series_id)
    if ts is None:
        return {}
    return {pt.period: float(pt.value) for pt in ts.points}


def _recover_gdp_from_curated_receipts() -> dict[str, float]:
    """If nominal_gdp series is not yet in macro_annual, recover OBR GDP from ct_receipts_pct_gdp."""
    curated_csv = get_settings().data_dir / "curated" / "ct_receipts.csv"
    if not curated_csv.exists():
        return {}
    try:
        df = pd.read_csv(curated_csv)
    except Exception:
        return {}
    if "fiscal_year" not in df.columns or "ct_receipts_gbp_bn" not in df.columns or "ct_receipts_pct_gdp" not in df.columns:
        return {}
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        fy = str(row["fiscal_year"])
        rec = float(row["ct_receipts_gbp_bn"])
        pct = float(row["ct_receipts_pct_gdp"])
        if pct > 0:
            out[fy] = 100.0 * rec / pct
    return out


def _rates_from_policy_changes(start_yr: int = 1982, end_yr: int = 2026) -> dict[str, float]:
    """Reconstruct annual main rate schedule from registry.load_policy_changes() if ct_main_rate series is absent."""
    changes = sorted(registry.load_policy_changes("corporation_tax"), key=lambda c: c.effective_date)
    if not changes:
        return {}
    current_rate = float(changes[0].old_rate_pct)
    change_by_year = {c.effective_date.year: float(c.new_rate_pct) for c in changes}
    out: dict[str, float] = {}
    for yr in range(start_yr, end_yr + 1):
        if yr in change_by_year:
            current_rate = change_by_year[yr]
        out[format_fy(yr)] = current_rate
    return out


def build_annual_panel() -> list[PanelRow]:
    """Build annual fiscal-year panel from FY1985 (or earliest available outturn year) using agent-6's registry.

    Until agent-6's series land on main, builds deterministically from the registry placeholder baseline
    and seed rate changes and sets `is_placeholder=True`. Never fabricates external numbers.
    """
    receipts_map = _series_map("ct_receipts")
    rates_map = _series_map("ct_main_rate") or _rates_from_policy_changes(1982, 2026)
    pnfc_map = _series_map("pnfc_gos")
    gdp_map = _series_map("nominal_gdp") or _recover_gdp_from_curated_receipts()
    bank_rate_map = _series_map("bank_rate")
    real_gdp_map = _series_map("real_gdp_growth")

    changes = registry.load_policy_changes("corporation_tax")
    change_by_fy: dict[str, registry.PolicyChange] = {}
    costing_by_fy: dict[str, float] = {}
    for ch in changes:
        if (
            abs(ch.new_rate_pct - ch.old_rate_pct) <= 1e-9
            or "reversed" in ch.change_id.lower()
            or "reversed" in ch.notes.lower()
        ):
            continue
        fy = format_fy(ch.effective_date.year)
        change_by_fy[fy] = ch
        if ch.official_costings:
            # Prefer costing for the first full year (y+1) or effective year (y)
            target_fy = format_fy(ch.effective_date.year + 1)
            matching = [c.value_gbp_bn for c in ch.official_costings if c.fiscal_year == target_fy]
            if not matching:
                matching = [c.value_gbp_bn for c in ch.official_costings]
            if matching:
                costing_by_fy[fy] = float(matching[0])

    datasets_meta = {d.dataset_id: d for d in registry.list_datasets()}
    any_meta_placeholder = any(
        datasets_meta[k].is_placeholder
        for k in ("ct_receipts", "ct_main_rate_history", "macro_annual")
        if k in datasets_meta
    )

    if receipts_map:
        # Real curated receipts from agent-6 are available
        use_pnfc = len(pnfc_map) >= 10 and all(fy in pnfc_map for fy in receipts_map)
        profit_map = pnfc_map if use_pnfc else gdp_map
        profit_proxy = "pnfc_gos" if use_pnfc else "nominal_gdp"
        is_placeholder = bool(any_meta_placeholder or not profit_map)

        # If neither pnfc_gos nor nominal_gdp is populated yet, fall back to baseline GDP scale marked placeholder
        if not profit_map:
            base = registry.load_baseline()
            base_gdp = base.years[0].nominal_gdp_gbp_bn if base.years else 3000.0
            profit_map = {fy: base_gdp for fy in receipts_map}
            profit_proxy = "placeholder_baseline"
            is_placeholder = True

        fys = sorted(fy for fy in receipts_map if fy in rates_map and fy in profit_map and fy_start_year(fy) >= 1982)
        rows: list[PanelRow] = []
        for idx, fy in enumerate(fys):
            yr = fy_start_year(fy)
            prev_fy = format_fy(yr - 1)
            rate = rates_map[fy]
            prev_rate = rates_map.get(prev_fy, rate)
            rate_change = round(rate - prev_rate, 6)
            prof = profit_map[fy]
            prev_prof = profit_map.get(prev_fy)
            prof_growth = ((prof / prev_prof) - 1.0) * 100.0 if (prev_prof and prev_prof > 0 and idx > 0) else None
            gdp_val = gdp_map.get(fy)
            rec_pct_gdp = (100.0 * receipts_map[fy] / gdp_val) if (gdp_val and gdp_val > 0) else None
            ch = change_by_fy.get(fy)
            rows.append(
                PanelRow(
                    fiscal_year=fy,
                    start_year=yr,
                    ct_receipts_gbp_bn=receipts_map[fy],
                    main_rate_pct=rate,
                    rate_change_pp=rate_change,
                    profit_measure_gbp_bn=prof,
                    profit_growth_pct=prof_growth,
                    profit_proxy_used=profit_proxy,
                    bank_rate_pct=bank_rate_map.get(fy),
                    real_gdp_growth_pct=real_gdp_map.get(fy),
                    receipts_pct_gdp=rec_pct_gdp,
                    official_costing_gbp_bn=costing_by_fy.get(fy),
                    change_id=ch.change_id if ch else None,
                    is_placeholder=is_placeholder,
                )
            )
        return rows

    # Fallback when agent-6's curated series have not yet landed on main (M0 stub registry active):
    # Use ONLY the M0 stub's load_baseline() and load_policy_changes() seed schedule, marked is_placeholder=True.
    baseline = registry.load_baseline()
    b_years = baseline.years
    g_gdp = (b_years[-1].nominal_gdp_gbp_bn / b_years[0].nominal_gdp_gbp_bn) ** (1.0 / max(1, len(b_years) - 1)) - 1.0
    anchor_gdp = b_years[0].nominal_gdp_gbp_bn
    anchor_rec = b_years[0].ct_receipts_gbp_bn
    anchor_rate = baseline.current_main_rate_pct
    params = default_parameters()
    s_share = params["main_rate_profit_share"].value

    rows = []
    start_years = list(range(1985, 2026))
    for idx, yr in enumerate(start_years):
        fy = format_fy(yr)
        prev_fy = format_fy(yr - 1)
        rate = rates_map.get(fy, anchor_rate)
        prev_rate = rates_map.get(prev_fy, rate)
        rate_change = round(rate - prev_rate, 6)
        # Scale stub baseline backwards deterministically by the stub baseline's own growth rate and rate ratio
        steps_from_2025 = yr - 2025
        gdp_val = anchor_gdp * ((1.0 + g_gdp) ** steps_from_2025)
        rate_factor = s_share * (rate / anchor_rate) + (1.0 - s_share)
        rec_val = anchor_rec * ((1.0 + g_gdp) ** steps_from_2025) * rate_factor
        ch = change_by_fy.get(fy)
        rows.append(
            PanelRow(
                fiscal_year=fy,
                start_year=yr,
                ct_receipts_gbp_bn=rec_val,
                main_rate_pct=rate,
                rate_change_pp=rate_change,
                profit_measure_gbp_bn=gdp_val,
                profit_growth_pct=g_gdp * 100.0 if idx > 0 else None,
                profit_proxy_used="placeholder_baseline",
                bank_rate_pct=None,
                real_gdp_growth_pct=None,
                receipts_pct_gdp=100.0 * rec_val / gdp_val,
                official_costing_gbp_bn=costing_by_fy.get(fy),
                change_id=ch.change_id if ch else None,
                is_placeholder=True,
            )
        )
    return rows


def compute_metrics(
    observed: Sequence[float],
    predicted: Sequence[float],
    *,
    naive_baseline: Sequence[float] | None = None,
    rate_changes_pp: Sequence[float] | None = None,
) -> tuple[float, float, float | None, float | None]:
    """Compute (MAE, RMSE, MAPE_pct, directional_accuracy) on a split.

    Directional accuracy measures how often the sign of the predicted policy effect
    `(predicted - naive_baseline)` matches the sign of the observed excess movement
    `(observed - naive_baseline)` on rate-change years (or total change sign when no
    naive_baseline is supplied).
    """
    n = len(observed)
    if n == 0 or len(predicted) != n:
        raise ValueError("observed and predicted must be non-empty sequences of equal length")

    obs_arr = np.asarray(observed, dtype=float)
    pred_arr = np.asarray(predicted, dtype=float)
    errors = pred_arr - obs_arr
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors**2)))

    nonzero_mask = np.abs(obs_arr) > 1e-9
    if np.any(nonzero_mask):
        mape_pct = float(np.mean(np.abs(errors[nonzero_mask] / obs_arr[nonzero_mask])) * 100.0)
    else:
        mape_pct = None

    dir_acc: float | None = None
    if naive_baseline is not None:
        base_arr = np.asarray(naive_baseline, dtype=float)
        if rate_changes_pp is not None:
            rc_arr = np.asarray(rate_changes_pp, dtype=float)
            mask = np.abs(rc_arr) > 1e-9
        else:
            mask = np.ones(n, dtype=bool)
        if np.any(mask):
            obs_eff = obs_arr[mask] - base_arr[mask]
            pred_eff = pred_arr[mask] - base_arr[mask]
            # For naive_growth where pred_eff == 0 everywhere, compare against statutory rate change sign or 0
            matches = []
            for o_d, p_d in zip(obs_eff, pred_eff, strict=True):
                if abs(p_d) <= 1e-12:
                    matches.append(float(abs(o_d) <= 1e-12))
                else:
                    matches.append(float((o_d > 0) == (p_d > 0)))
            dir_acc = float(np.mean(matches))
    return mae, rmse, mape_pct, dir_acc


def compute_implied_elasticity(panel: Sequence[PanelRow], prior_elasticity: float) -> ImpliedElasticityResult:
    """Regress log(receipts / profits) on log(1 - t), controlling for real GDP growth when available.

    Under B_y = B_0 * (1 - t_y)^epsilon and R_y = t_y * B_y,
    log(R_y / (t_y * Pi_y)) = alpha + epsilon * log(1 - t_y) + gamma * cycle_y + u_y.
    We also report the direct regression of log(R_y / Pi_y) on log(1 - t_y) per prompt §5.2.
    """
    valid = [
        r
        for r in panel
        if r.ct_receipts_gbp_bn > 0 and r.profit_measure_gbp_bn > 0 and 0 < r.main_rate_pct < 100
    ]
    proxy = valid[0].profit_proxy_used if valid else "nominal_gdp"
    if len(valid) < 5:
        return ImpliedElasticityResult(
            n_obs=len(valid),
            implied_base_elasticity=None,
            std_error=None,
            engine_prior_elasticity=prior_elasticity,
            profit_proxy_used=proxy,
            summary="Insufficient observations to estimate implied taxable-profit elasticity.",
        )

    # Regress log(implied base / profit proxy) = log((R_y / t_y) / Pi_y) on log(1 - t_y) and cycle control,
    # as well as log(R_y / Pi_y) on log(1 - t_y). Note that d log(R/Pi) / d log(1-t) = -(1-t)/t + epsilon.
    t_frac = np.array([r.main_rate_pct / 100.0 for r in valid], dtype=float)
    y_base_share = np.array(
        [math.log((r.ct_receipts_gbp_bn / (r.main_rate_pct / 100.0)) / r.profit_measure_gbp_bn) for r in valid],
        dtype=float,
    )
    x_log_net = np.log(1.0 - t_frac)

    has_cycle = all(r.real_gdp_growth_pct is not None for r in valid)
    if has_cycle:
        cycle = np.array([float(r.real_gdp_growth_pct or 0.0) for r in valid], dtype=float)
        X = np.column_stack([np.ones(len(valid)), x_log_net, cycle])
    else:
        X = np.column_stack([np.ones(len(valid)), x_log_net])

    beta, _, _, _ = np.linalg.lstsq(X, y_base_share, rcond=None)
    eps_hat = float(beta[1])
    resid = y_base_share - X @ beta
    dof = max(1, len(valid) - X.shape[1])
    sigma2 = float(np.sum(resid**2) / dof)
    try:
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = float(math.sqrt(max(0.0, cov[1, 1])))
    except np.linalg.LinAlgError:
        se = None

    cycle_note = "controlling for real GDP growth" if has_cycle else "without real GDP growth control (series unavailable)"
    summary = (
        f"OLS of log((receipts/t)/{proxy}) on log(1-t) over n={len(valid)} fiscal years ({cycle_note}) "
        f"yields an implied base elasticity of {eps_hat:.3f}"
        + (f" (SE {se:.3f})" if se is not None else "")
        + f", compared with the engine central prior of {prior_elasticity:.2f}. "
        "Because UK rate cuts in the 1980s and 2010s coincided with base-broadening capital-allowance reforms "
        "and post-2008 financial-sector profit shifts, macro time-series regressions confound rate effects with "
        "base definitions; we retain the micro-econometric literature prior (0.20) as central."
    )
    return ImpliedElasticityResult(
        n_obs=len(valid),
        implied_base_elasticity=round(eps_hat, 4),
        std_error=round(se, 4) if se is not None else None,
        engine_prior_elasticity=prior_elasticity,
        profit_proxy_used=proxy,
        summary=summary,
    )


def run_backtest(panel: list[PanelRow] | None = None) -> BacktestOutput:
    """Run the chronological conditional backtest on the annual CT panel.

    Target: Predict R_{y+1} from information at y-1, conditional on realised profit growth
    from y-1 to y+1. Train split: FY <= 2007; Test split: FY >= 2008.
    """
    if panel is None:
        panel = build_annual_panel()

    by_year = {r.start_year: r for r in panel}
    params = default_parameters()
    s_share = float(params["main_rate_profit_share"].value)
    prior_eps = float(params["taxable_profit_elasticity"].value)

    # Build evaluation observations for each year y where y-1 and y+1 exist
    eval_years = sorted(yr for yr in by_year if (yr - 1) in by_year and (yr + 1) in by_year)
    if not eval_years:
        raise ValueError("Panel has no contiguous (y-1, y, y+1) triples for backtesting")

    # Strict chronological split:
    # - A case is assigned to "train" if y <= 2007, and "test" if y >= 2008.
    # - Parameter estimation (jane_calibrated, linear_regression) uses ONLY rows where y+1 <= 2007
    #   so that no test-period outcome (FY >= 2008) ever appears in training targets.
    fit_years = [yr for yr in eval_years if (yr + 1) <= TRAIN_CUTOFF_FY]
    if not fit_years:
        # Fallback if the available series starts after 2005 (e.g. truncated toy panel in unit tests)
        fit_years = [yr for yr in eval_years if yr <= TRAIN_CUTOFF_FY]

    def _row_features(yr: int) -> tuple[float, float, float, float, float]:
        """Return (r_prev, r_obs_next, t_old, t_new, g_2yr) for evaluation year yr."""
        r_prev = by_year[yr - 1].ct_receipts_gbp_bn
        r_next = by_year[yr + 1].ct_receipts_gbp_bn
        t_old = by_year[yr - 1].main_rate_pct / 100.0
        t_new = by_year[yr + 1].main_rate_pct / 100.0
        pi_prev = by_year[yr - 1].profit_measure_gbp_bn
        pi_next = by_year[yr + 1].profit_measure_gbp_bn
        g_2yr = (pi_next / pi_prev) - 1.0 if pi_prev > 0 else 0.0
        return r_prev, r_next, t_old, t_new, g_2yr

    # 1. Fit jane_calibrated elasticity on fit_years only
    def _sse_for_eps(eps: float) -> float:
        sq_err = 0.0
        for yr in fit_years:
            r_prev, r_next, t_old, t_new, g_2yr = _row_features(yr)
            naive = r_prev * (1.0 + g_2yr)
            _, d_behav = _revenue_static_behavioural(
                t_old, t_new, naive, main_rate_profit_share=s_share, elasticity=float(eps), timing=1.0
            )
            pred = naive + d_behav
            sq_err += (pred - r_next) ** 2
        return sq_err

    if fit_years:
        opt = minimize_scalar(_sse_for_eps, bounds=(0.0, 1.5), method="bounded")
        calibrated_eps = float(opt.x) if opt.success else prior_eps
    else:
        calibrated_eps = prior_eps

    # 2. Fit log-change OLS (`linear_regression`) on fit_years only:
    # log(R_{y+1} / R_{y-1}) = beta_0 + beta_1 * (t_new - t_old) + beta_2 * log(1 + g_2yr)
    if len(fit_years) >= 3:
        X_train = []
        y_train = []
        for yr in fit_years:
            r_prev, r_next, t_old, t_new, g_2yr = _row_features(yr)
            X_train.append([1.0, t_new - t_old, math.log(max(1e-6, 1.0 + g_2yr))])
            y_train.append(math.log(max(1e-6, r_next / max(1e-6, r_prev))))
        beta_ols, _, _, _ = np.linalg.lstsq(np.asarray(X_train), np.asarray(y_train), rcond=None)
    else:
        beta_ols = np.array([0.0, 0.0, 1.0], dtype=float)

    method_meta = (
        (
            "naive_growth",
            "Naive profit-growth baseline",
            "R̂_{y+1} = R_{y-1} × (1 + g_{y-1→y+1}), assuming receipts grow one-for-one with the profit proxy and ignoring tax-rate changes.",
            True,
        ),
        (
            "static",
            "Static tax-rate scaling baseline",
            "R̂_{y+1} = naive × (s·t_new/t_old + (1−s)), scaling the main-rate share s of receipts proportionally to the statutory rate change with zero behavioural response.",
            True,
        ),
        (
            "jane_behavioural",
            "Jane Avenue behavioural engine (central prior ε)",
            f"Engine static + behavioural revenue equation with central taxable-profit elasticity ε = {prior_eps:.2f} and main-rate profit share s = {s_share:.2f}.",
            False,
        ),
        (
            "jane_calibrated",
            "Jane Avenue behavioural engine (train-calibrated ε)",
            f"Same structural revenue equation with elasticity ε = {calibrated_eps:.3f} fitted by nonlinear least squares on FY ≤ {TRAIN_CUTOFF_FY} training data only.",
            False,
        ),
        (
            "linear_regression",
            "Log-change OLS baseline",
            f"OLS regression of log(R_{{y+1}}/R_{{y-1}}) on statutory rate change Δt and log(1+g) fitted on FY ≤ {TRAIN_CUTOFF_FY} training data only.",
            True,
        ),
    )

    cases: list[BacktestCase] = []
    rate_changes_by_split: dict[str, list[float]] = {"train": [], "test": []}
    obs_by_split: dict[str, list[float]] = {"train": [], "test": []}
    preds_by_split: dict[str, dict[str, list[float]]] = {
        "train": {m[0]: [] for m in method_meta},
        "test": {m[0]: [] for m in method_meta},
    }

    for yr in eval_years:
        row = by_year[yr]
        next_row = by_year[yr + 1]
        r_prev, r_next, t_old, t_new, g_2yr = _row_features(yr)
        split: str = "train" if yr <= TRAIN_CUTOFF_FY else "test"

        naive_pred = r_prev * (1.0 + g_2yr)
        d_static, d_behav = _revenue_static_behavioural(
            t_old, t_new, naive_pred, main_rate_profit_share=s_share, elasticity=prior_eps, timing=1.0
        )
        _, d_cal = _revenue_static_behavioural(
            t_old, t_new, naive_pred, main_rate_profit_share=s_share, elasticity=calibrated_eps, timing=1.0
        )
        static_pred = naive_pred + d_static
        jane_behav_pred = naive_pred + d_behav
        jane_cal_pred = naive_pred + d_cal

        x_vec = np.array([1.0, t_new - t_old, math.log(max(1e-6, 1.0 + g_2yr))], dtype=float)
        ols_log_chg = float(np.dot(beta_ols, x_vec))
        ols_pred = float(r_prev * math.exp(ols_log_chg))

        preds = {
            "naive_growth": round(naive_pred, 4),
            "static": round(static_pred, 4),
            "jane_behavioural": round(jane_behav_pred, 4),
            "jane_calibrated": round(jane_cal_pred, 4),
            "linear_regression": round(ols_pred, 4),
        }

        obs_by_split[split].append(r_next)
        rate_changes_by_split[split].append((t_new - t_old) * 100.0)
        for m_name, val in preds.items():
            preds_by_split[split][m_name].append(val)

        case_id = row.change_id if row.change_id else f"FY-{row.fiscal_year}"
        rate_diff_pp = (t_new - t_old) * 100.0
        note_parts = [
            f"Info year {by_year[yr - 1].fiscal_year} (R={r_prev:.2f}bn, t={t_old * 100:.1f}%) → target {next_row.fiscal_year} (t={t_new * 100:.1f}%, Δt={rate_diff_pp:+.1f}pp, 2yr profit growth={g_2yr * 100:+.1f}%)."
        ]
        if row.change_id:
            note_parts.append(
                f"Rate-change event {row.change_id}: implied static ΔR={d_static:+.2f}bn, behavioural ΔR={d_behav:+.2f}bn vs naive."
            )
        if row.official_costing_gbp_bn is not None:
            note_parts.append(
                f"Ex-ante official costing ({row.official_costing_gbp_bn:+.2f}bn) is a policy-change delta under ex-ante macro forecasts, not total receipts ground truth."
            )

        cases.append(
            BacktestCase(
                case_id=case_id,
                fiscal_year=row.fiscal_year,
                split=split,  # type: ignore[arg-type]
                target=f"ct_receipts_gbp_bn ({next_row.fiscal_year})",
                observed=round(r_next, 4),
                official_costing_gbp_bn=row.official_costing_gbp_bn,
                predictions=preds,
                notes=" ".join(note_parts),
            )
        )

    summaries: list[MethodSummary] = []
    for split in ("train", "test"):
        obs_list = obs_by_split[split]
        if not obs_list:
            continue
        naive_list = preds_by_split[split]["naive_growth"]
        rc_list = rate_changes_by_split[split]
        for m_id, m_label, m_desc, is_base in method_meta:
            p_list = preds_by_split[split][m_id]
            mae, rmse, mape, dir_acc = compute_metrics(
                obs_list, p_list, naive_baseline=naive_list, rate_changes_pp=rc_list
            )
            summaries.append(
                MethodSummary(
                    method=m_id,
                    label=m_label,
                    description=m_desc,
                    split=split,  # type: ignore[arg-type]
                    n=len(obs_list),
                    mae=round(mae, 4),
                    rmse=round(rmse, 4),
                    mape_pct=round(mape, 4) if mape is not None else None,
                    directional_accuracy=round(dir_acc, 4) if dir_acc is not None else None,
                    is_baseline=is_base,
                )
            )

    # Compute test relative residuals (pred - obs) / obs for jane_behavioural
    test_cases = [c for c in cases if c.split == "test"]
    test_residuals = [
        (c.predictions["jane_behavioural"] - c.observed) / c.observed
        for c in test_cases
        if c.observed > 0
    ]

    # Leave-one-out 5-95% empirical interval coverage on test cases using u = 1/(1+r) - 1 = obs/pred - 1
    loo_covered = 0
    loo_coverage: float | None = None
    if len(test_residuals) >= 8:
        u_arr = np.asarray([1.0 / (1.0 + r) - 1.0 for r in test_residuals], dtype=float)
        for i, tc in enumerate(test_cases):
            other_u = np.delete(u_arr, i)
            q5, q95 = np.percentile(other_u, (5, 95))
            pred_val = tc.predictions["jane_behavioural"]
            if pred_val * (1.0 + float(q5)) <= tc.observed <= pred_val * (1.0 + float(q95)):
                loo_covered += 1
        loo_coverage = round(loo_covered / len(test_residuals), 4)

    test_period = (
        f"FY{test_cases[0].fiscal_year} to FY{test_cases[-1].fiscal_year}"
        if test_cases
        else "N/A"
    )
    proxy_used = panel[0].profit_proxy_used if panel else "nominal_gdp"
    is_placeholder = any(r.is_placeholder for r in panel)
    implied_el = compute_implied_elasticity(panel, prior_eps)

    return BacktestOutput(
        panel=panel,
        methods=summaries,
        cases=cases,
        calibrated_elasticity=round(calibrated_eps, 4),
        prior_elasticity=prior_eps,
        main_rate_profit_share=s_share,
        profit_proxy_used=proxy_used,
        is_placeholder=is_placeholder,
        test_relative_residuals=[round(r, 6) for r in test_residuals],
        test_period=test_period,
        loo_coverage_90=loo_coverage,
        loo_covered_count=loo_covered,
        implied_elasticity=implied_el,
    )
