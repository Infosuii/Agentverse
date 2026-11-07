#!/usr/bin/env bash
# Run all CI checks locally on macOS/Linux.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_CMD="python3"
if [ -x ".venv/bin/python" ]; then
  PYTHON_CMD="$REPO_ROOT/.venv/bin/python"
elif [ -x "backend/.venv/bin/python" ]; then
  PYTHON_CMD="$REPO_ROOT/backend/.venv/bin/python"
fi

export JANE_MODE="mock"
export JANE_DB_PATH=":memory:"
export PYTHONPATH="$REPO_ROOT/backend"

if [ -f "backend/requirements-dev.txt" ]; then
  echo "=== Backend: ruff check ==="
  "$PYTHON_CMD" -m ruff check backend

  echo "=== Backend: pytest (not live) ==="
  "$PYTHON_CMD" -m pytest backend -m "not live"
else
  echo "Skipping backend checks (backend/requirements-dev.txt not found yet)."
fi

if [ -f "frontend/package.json" ]; then
  echo "=== Frontend: typecheck, lint, test, build ==="
  (
    cd frontend
    npm run typecheck
    npm run lint
    npm test -- --run
    npm run build
  )
else
  echo "Skipping frontend checks (frontend/package.json not found yet)."
fi

if [ -f "backend/scripts/export_openapi.py" ] && [ -f "frontend/package.json" ]; then
  echo "=== OpenAPI drift check ==="
  "$PYTHON_CMD" backend/scripts/export_openapi.py
  (cd frontend && npm run gen:api)
  git diff --exit-code frontend/src/api/
else
  echo "Skipping OpenAPI drift check (export_openapi.py or frontend/package.json not found yet)."
fi

echo "All checks passed!"
