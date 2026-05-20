$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue

function Invoke-BasePython {
    if ($pythonCommand) {
        & python @args
        return
    }
    if ($pythonLauncher) {
        & py -3 @args
        return
    }
    throw "Python is not installed or not available in PATH."
}

if (-not $pythonCommand -and -not $pythonLauncher) {
    Write-Host "Python is not installed or not available in PATH."
    Write-Host "Install Python 3.11 or later, then run this script again."
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating local virtual environment..."
    Invoke-BasePython -m venv .venv
}

Write-Host "Installing dependencies..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "Installing Playwright browser for local fallback collection..."
& ".venv\Scripts\python.exe" -m playwright install chromium

Write-Host "Starting Lily Jobs locally..."
if (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "Lily Jobs already appears to be running on http://localhost:8501"
    Start-Process "http://localhost:8501"
    Read-Host "Press Enter to exit"
    exit 0
}

Write-Host "Opening http://localhost:8501 in your browser..."
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8501'"
)
& ".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.headless false
