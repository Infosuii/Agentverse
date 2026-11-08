"""The Monte Carlo chart plots REAL draws (issue #98). Owner: agent-5."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient

from jane_avenue import engine
from jane_avenue.api.app import create_app
from jane_avenue.charts import build_monte_carlo_figure, path_indices, render_monte_carlo, summarise
from jane_avenue.contracts import AnalysisOptions, AnalysisRequest, PolicySpec
from jane_avenue.data import registry
from jane_avenue.orchestrator import create_analysis, run_analysis
from jane_avenue.simulation.montecarlo import monte_carlo, simulate_draws
from jane_avenue.store import AnalysisStore

PNG = b"\x89PNG\r\n\x1a\n"
SPEC = PolicySpec(policy_type="corporation_tax_main_rate", tax="corporation_tax", baseline_rate_pct=25,
                  proposed_rate_pct=28, effective_date=date(2027, 4, 1), horizon_years=5)


@pytest.fixture(scope="module")
def draws():
    return simulate_draws(SPEC, engine.default_parameters(SPEC), registry.load_baseline(), draws=500, seed=7)


def test_stored_bands_are_summaries_of_the_same_draws(draws) -> None:
    mc = monte_carlo(SPEC, engine.default_parameters(SPEC), registry.load_baseline(), draws=500, seed=7)
    for dist in mc.distributions:
        stats = summarise(draws.metrics[dist.metric])
        for i, band in enumerate(dist.bands):
            for key in ("p5", "p25", "p50", "p75", "p95", "mean"):
                assert getattr(band, key) == pytest.approx(float(stats[key][i]), abs=1e-12)


def test_every_grey_line_is_an_actual_draw(draws) -> None:
    metric = "revenue_behavioural_gbp_bn"
    fig = build_monte_carlo_figure(draws, metric, n_paths=40)
    lines = [line for line in fig.axes[0].get_lines() if (line.get_gid() or "").startswith("mc-draw-")]
    assert len(lines) == 40
    rows = path_indices(draws.draws, 40, draws.seed)
    assert sorted(int(line.get_gid().split("-")[-1]) for line in lines) == sorted(rows.tolist())
    for line in lines:
        row = int(line.get_gid().split("-")[-1])
        y = np.asarray(line.get_ydata(), dtype=float)
        assert y[0] == 0.0  # the pre-policy year: no change against the baseline
        np.testing.assert_array_equal(y[1:], draws.metrics[metric][row])  # no interpolation, no noise
        assert len(y) == len(draws.fiscal_years) + 1  # annual points only


def test_path_sample_is_reproducible_and_capped(draws) -> None:
    assert path_indices(500, 60, 7).tolist() == path_indices(500, 60, 7).tolist()
    assert len(path_indices(10, 60, 7)) == 10


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_render_returns_png(draws, theme: str) -> None:
    assert render_monte_carlo(draws, "gdp_level_pct", theme=theme, dpi=60).startswith(PNG)


def test_unknown_metric_is_rejected(draws) -> None:
    with pytest.raises(KeyError):
        build_monte_carlo_figure(draws, "not_a_metric")


@pytest.fixture(scope="module")
def client_and_ids():
    store = AnalysisStore(":memory:")
    ids = {}
    for key, query in (("ok", "Raise corporation tax from 25% to 28%"), ("withheld", "Raise corporation tax from "
                                                                                     "25% to 45%")):
        req = AnalysisRequest(query=query, options=AnalysisOptions(monte_carlo_draws=300, generate_report=False))
        ids[key] = run_analysis(store, create_analysis(store, req).analysis_id).analysis_id
    client = TestClient(create_app(store, use_executor=False))
    yield client, ids
    store.close()


def test_analysis_chart_endpoint(client_and_ids) -> None:
    client, ids = client_and_ids
    r = client.get(f"/api/analyses/{ids['ok']}/charts/montecarlo.png", params={"metric": "gdp_level_pct"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content.startswith(PNG)


def test_analysis_chart_rejects_withheld_and_unknown(client_and_ids) -> None:
    client, ids = client_and_ids
    assert client.get(f"/api/analyses/{ids['withheld']}/charts/montecarlo.png").status_code == 409
    assert client.get("/api/analyses/nope/charts/montecarlo.png").status_code == 404
    assert client.get(f"/api/analyses/{ids['ok']}/charts/montecarlo.png",
                      params={"metric": "bogus"}).status_code == 422


def test_simulate_chart_endpoint(client_and_ids) -> None:
    client, _ = client_and_ids
    body = {"policy": SPEC.model_dump(mode="json"), "parameter_overrides": {"taxable_profit_elasticity": 0.4},
            "monte_carlo_draws": 300, "seed": 42}
    r = client.post("/api/simulate/montecarlo.png", json=body, params={"empirical": True})
    assert r.status_code == 200 and r.content.startswith(PNG)
    out = {**body, "policy": {**body["policy"], "proposed_rate_pct": 45}}
    assert client.post("/api/simulate/montecarlo.png", json=out).status_code == 422
