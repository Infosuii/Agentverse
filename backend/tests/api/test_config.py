"""Settings and mode resolution (MASTER_PROMPT section 7). Owner: agent-1."""
import pytest

from jane_avenue import config


@pytest.fixture
def fresh_settings(monkeypatch):
    config.get_settings.cache_clear()
    yield monkeypatch
    config.get_settings.cache_clear()


def test_tests_run_in_mock_mode_without_a_key():
    s = config.get_settings()
    assert s.mode == "mock" and s.gemini_api_key is None and not s.gemini_configured
    assert s.db_path == ":memory:"


@pytest.mark.parametrize(("mode", "key", "expected"), [(None, None, "mock"), (None, "k", "live"),
                                                        ("cached", "k", "cached"), ("MOCK", "k", "mock")])
def test_mode_resolution(fresh_settings, mode, key, expected):
    for name, value in (("JANE_MODE", mode), ("GEMINI_API_KEY", key)):
        if value is None:
            fresh_settings.delenv(name, raising=False)
        else:
            fresh_settings.setenv(name, value)
    assert config.get_settings().mode == expected


def test_invalid_mode_rejected(fresh_settings):
    fresh_settings.setenv("JANE_MODE", "turbo")
    with pytest.raises(ValueError):
        config.get_settings()


def test_defaults_and_overrides(fresh_settings, tmp_path):
    for name in ("JANE_MODEL_FAST", "JANE_MODEL_DEEP", "JANE_MC_DRAWS", "JANE_SEED", "JANE_CORS_ORIGINS",
                 "JANE_RESEARCH_CACHE_DIR"):
        fresh_settings.delenv(name, raising=False)
    fresh_settings.setenv("JANE_DATA_DIR", str(tmp_path))
    s = config.get_settings()
    assert (s.model_fast, s.model_deep, s.mc_draws, s.seed) == ("gemini-3.8-flash", "gemini-4-argon", 2000, 42)
    assert s.cors_origins == ("http://localhost:5173",)
    assert s.research_cache_dir == tmp_path / "research_cache"
    assert config.REPO_ROOT == config.BACKEND_DIR.parent
    config.get_settings.cache_clear()
    fresh_settings.setenv("JANE_CORS_ORIGINS", "http://a, http://b")
    fresh_settings.setenv("JANE_MC_DRAWS", "500")
    s = config.get_settings()
    assert s.cors_origins == ("http://a", "http://b") and s.mc_draws == 500
