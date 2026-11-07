"""Write the backend OpenAPI schema to frontend/src/api/openapi.json. Owner: agent-1.

Run from anywhere: `python backend/scripts/export_openapi.py`. Mock mode and an in-memory database are forced
first, so the export never needs a key or touches a database file. Output is stable (sorted keys), so CI can diff it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["JANE_MODE"] = "mock"
os.environ["JANE_DB_PATH"] = ":memory:"
os.environ.pop("GEMINI_API_KEY", None)

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from jane_avenue.api.app import app  # noqa: E402

OUT = BACKEND_DIR.parent / "frontend" / "src" / "api" / "openapi.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                   newline="\n")
    print(f"wrote {OUT.relative_to(BACKEND_DIR.parent)}")


if __name__ == "__main__":
    main()
