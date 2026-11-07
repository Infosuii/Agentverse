# Start Jane Avenue backend (:8000) and frontend (:5173) for local development on Windows PowerShell.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Python 3.13 virtual environment in .venv..."
    py -3.13 -m venv .venv
}

if (Test-Path "backend\requirements-dev.txt") {
    Write-Host "Installing backend dependencies..."
    & $VenvPython -m pip install -q -r backend\requirements-dev.txt
}

if (Test-Path "frontend\package.json") {
    if (-not (Test-Path "frontend\node_modules")) {
        Write-Host "Installing frontend dependencies..."
        Push-Location frontend
        if (Test-Path "package-lock.json") { npm ci } else { npm install }
        Pop-Location
    }
}

Write-Host "Starting backend on http://localhost:8000 and frontend on http://localhost:5173..."
$env:PYTHONPATH = Join-Path $RepoRoot "backend"
if (-not $env:JANE_MODE) { $env:JANE_MODE = "mock" }

$BackendProc = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "jane_avenue.api.app:app", "--reload", "--port", "8000" `
    -WorkingDirectory (Join-Path $RepoRoot "backend") `
    -NoNewWindow -PassThru

try {
    if (Test-Path "frontend\package.json") {
        Set-Location (Join-Path $RepoRoot "frontend")
        npm run dev
    } else {
        Write-Host "frontend/package.json not present yet. Waiting on backend process (Ctrl+C to stop)..."
        Wait-Process -Id $BackendProc.Id
    }
} finally {
    if ($BackendProc -and -not $BackendProc.HasExited) {
        Stop-Process -Id $BackendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
