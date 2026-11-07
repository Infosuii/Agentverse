# Run all CI checks locally on Windows PowerShell.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$PythonCmd = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $PythonCmd = (Resolve-Path ".venv\Scripts\python.exe").Path
} elseif (Test-Path "backend\.venv\Scripts\python.exe") {
    $PythonCmd = (Resolve-Path "backend\.venv\Scripts\python.exe").Path
}

$env:JANE_MODE = "mock"
$env:JANE_DB_PATH = ":memory:"
$env:PYTHONPATH = Join-Path $RepoRoot "backend"

if (Test-Path "backend\requirements-dev.txt") {
    Write-Host "=== Backend: ruff check ==="
    & $PythonCmd -m ruff check backend
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "=== Backend: pytest (not live) ==="
    & $PythonCmd -m pytest backend -m "not live"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Skipping backend checks (backend/requirements-dev.txt not found yet)."
}

if (Test-Path "frontend\package.json") {
    Push-Location frontend
    try {
        Write-Host "=== Frontend: typecheck ==="
        npm run typecheck
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "=== Frontend: lint ==="
        npm run lint
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "=== Frontend: test ==="
        npm test -- --run
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "=== Frontend: build ==="
        npm run build
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Skipping frontend checks (frontend/package.json not found yet)."
}

if ((Test-Path "backend\scripts\export_openapi.py") -and (Test-Path "frontend\package.json")) {
    Write-Host "=== OpenAPI drift check ==="
    & $PythonCmd backend\scripts\export_openapi.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Push-Location frontend
    try {
        npm run gen:api
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }

    git diff --exit-code frontend/src/api/
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Skipping OpenAPI drift check (export_openapi.py or frontend/package.json not found yet)."
}

Write-Host "All checks passed!"
