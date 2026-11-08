#!/usr/bin/env bash
# Start Jane Avenue backend (:8000) and frontend (:5173) for local development on macOS/Linux.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d ".venv" ]; then
  echo "Creating Python 3.13 virtual environment in .venv..."
  python3.13 -m venv .venv || python3 -m venv .venv
fi

VENV_PY="$REPO_ROOT/.venv/bin/python"

if [ -f "backend/requirements-dev.txt" ]; then
  echo "Installing backend dependencies..."
  "$VENV_PY" -m pip install -q -r backend/requirements-dev.txt
fi

if [ -f "frontend/package.json" ] && [ ! -d "frontend/node_modules" ]; then
  echo "Installing frontend dependencies..."
  (cd frontend && if [ -f "package-lock.json" ]; then npm ci; else npm install; fi)
fi

export PYTHONPATH="$REPO_ROOT/backend"
# JANE_MODE is not forced: .env or auto-detection decides (live when GEMINI_API_KEY is set, mock otherwise).

echo "Starting backend on http://localhost:8000..."
(cd backend && "$VENV_PY" -m uvicorn jane_avenue.api.app:app --reload --port 8000) &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [ -f "frontend/package.json" ]; then
  echo "Starting frontend on http://localhost:5173..."
  cd frontend
  npm run dev
else
  echo "frontend/package.json not present yet. Waiting on backend..."
  wait "$BACKEND_PID"
fi
