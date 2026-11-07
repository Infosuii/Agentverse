"""backend/scripts/smoke.py (agent-11 uses it for golden-path checks). Owner: agent-1."""
import importlib.util
import json
from pathlib import Path

import pytest

SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "smoke.py"


@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location("jane_smoke", SMOKE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_golden_path_json(smoke, capsys):
    assert smoke.main(["--draws", "100", "--json", "--expect-approved"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "completed" and out["mode"] == "mock"
    assert set(out["stage_timings_ms"]) == {"parsing", "researching", "precedents", "modelling", "verifying",
                                             "reporting"}
    assert out["verification"]["overall"] != "forecast_withheld"
    assert "revenue_behavioural_gbp_bn" in out["headline_central"]


def test_out_of_scope_is_withheld(smoke, capsys):
    assert smoke.main(["--query", "Raise corporation tax from 25% to 45%", "--draws", "0"]) == 0
    assert "forecast_withheld" in capsys.readouterr().out
    assert smoke.main(["--query", "Raise corporation tax from 25% to 45%", "--draws", "0", "--expect-approved"]) == 2


def test_time_budget_flag(smoke):
    assert smoke.main(["--draws", "0", "--no-research", "--json", "--max-seconds", "0"]) == 2
