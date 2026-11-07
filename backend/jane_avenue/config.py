"""Runtime configuration (MASTER_PROMPT section 7). Owner: agent-1.

Settings are read once per process from the environment (and a local `.env`, if python-dotenv is installed).
Tests set `JANE_MODE=mock` and `JANE_DB_PATH=:memory:` before importing anything from `jane_avenue`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .contracts import Mode

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

_VALID_MODES: tuple[str, ...] = ("mock", "live", "cached")


@dataclass(frozen=True)
class Settings:
    mode: Mode
    gemini_api_key: str | None
    model_fast: str
    model_deep: str
    data_dir: Path
    research_cache_dir: Path
    db_path: str
    mc_draws: int
    seed: int
    cors_origins: tuple[str, ...]

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)


def _load_dotenv() -> None:
    # Tests and the OpenAPI export set JANE_LOAD_DOTENV=0 so a developer's local .env key can never leak into them.
    if os.environ.get("JANE_LOAD_DOTENV", "1") == "0":
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
        load_dotenv(BACKEND_DIR / ".env")
    except Exception:  # dotenv is optional; never fail startup over it
        pass


def _resolve_mode(raw: str | None, api_key: str | None) -> Mode:
    if raw:
        value = raw.strip().lower()
        if value not in _VALID_MODES:
            raise ValueError(f"JANE_MODE must be one of {_VALID_MODES}, got {raw!r}")
        return value  # type: ignore[return-value]
    return "live" if api_key else "mock"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv()
    env = os.environ
    api_key = env.get("GEMINI_API_KEY") or None
    data_dir = Path(env.get("JANE_DATA_DIR") or REPO_ROOT / "data")
    db_path = env.get("JANE_DB_PATH") or str(BACKEND_DIR / ".data" / "jane.db")
    origins = tuple(o.strip() for o in (env.get("JANE_CORS_ORIGINS") or "http://localhost:5173").split(",") if o.strip())
    return Settings(
        mode=_resolve_mode(env.get("JANE_MODE"), api_key),
        gemini_api_key=api_key,
        model_fast=env.get("JANE_MODEL_FAST") or "gemini-3.8-flash",
        model_deep=env.get("JANE_MODEL_DEEP") or "gemini-4-argon",
        data_dir=data_dir,
        research_cache_dir=Path(env.get("JANE_RESEARCH_CACHE_DIR") or data_dir / "research_cache"),
        db_path=db_path,
        mc_draws=_env_int("JANE_MC_DRAWS", 2000),
        seed=_env_int("JANE_SEED", 42),
        cors_origins=origins,
    )
