@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="
where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    echo Python is not installed or not available in PATH.
    echo Install Python 3.11 or later, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating local virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Installing Playwright browser for local fallback collection...
".venv\Scripts\python.exe" -m playwright install chromium

echo Starting Lily Jobs locally...
netstat -ano | findstr ":8501" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo Lily Jobs already appears to be running on http://localhost:8501
    start "" "http://localhost:8501"
    pause
    exit /b 0
)

echo Opening http://localhost:8501 in your browser...
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8501'"
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.headless false

pause
