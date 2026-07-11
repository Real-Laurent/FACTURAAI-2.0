@echo off
REM One-click start: launches main.py (folder watcher + Gmail poller +
REM dashboard, all together) in its own window, then opens the dashboard
REM in your browser once it's actually up. Double-click this file, or make
REM a Desktop shortcut to it.

setlocal
cd /d "%~dp0"

set VENV_PY=.venv\Scripts\python.exe

if not exist "%VENV_PY%" (
    echo ERROR: venv not found at "%VENV_PY%"
    echo Run this first:  python scripts\install.py
    pause
    exit /b 1
)

echo Starting FacturaAI...
start "FacturaAI" "%VENV_PY%" main.py

"%VENV_PY%" scripts\open_dashboard.py
if errorlevel 1 (
    echo.
    pause
)
