@echo off
REM ============================================================================
REM Polymarket Data Monitor + Rebound Strategy
REM 
REM This script runs both:
REM 1. orderbook.py - Data monitor (saves JSON files)
REM 2. run_rebound.py - Rebound strategy (simulation mode)
REM 
REM Usage: Double-click to run
REM ============================================================================

title Polymarket Monitor + Rebound Strategy

cd /d "%~dp0"

REM Ensure directories exist
if not exist "logs" mkdir logs
if not exist "files" mkdir files

echo ============================================================================
echo    Polymarket Data Monitor + Rebound Strategy
echo ============================================================================
echo.
echo [%date% %time%] Starting...
echo.

REM Start keep-awake PowerShell script in background
echo [1/3] Starting keep-awake process...
start "KeepAwake" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0keep_awake.ps1"
echo       Done.
echo.

REM Check/create virtual environment
echo [2/3] Checking Python environment...
if not exist ".venv\Scripts\python.exe" (
    echo       Creating virtual environment...
    python -m venv .venv
    echo       Installing dependencies...
    .venv\Scripts\python.exe -m pip install --upgrade pip > logs\pip_install.log 2>&1
    .venv\Scripts\python.exe -m pip install -r requirements.txt >> logs\pip_install.log 2>&1
    .venv\Scripts\python.exe -m pip install rich >> logs\pip_install.log 2>&1
)
echo       Done.
echo.

REM Start Rebound Strategy in a separate window (simulation mode)
echo [3/3] Starting Rebound Strategy (SIMULATION mode)...
start "Rebound Strategy - BTC" cmd /k ".venv\Scripts\python.exe apps/run_rebound.py --coin BTC"
echo       Started in new window.
echo.

echo ============================================================================
echo    Monitor Status: RUNNING
echo    
echo    Window 1: Data Monitor (this window)
echo      - Coin: BTC
echo      - Mode: Silent (data saved to files/)
echo      - Auto-Restart: Every 12 hours
echo    
echo    Window 2: Rebound Strategy
echo      - Coin: BTC
echo      - Mode: SIMULATION (no real orders)
echo      - Trigger: A segment, price drop below 0.30
echo    
echo    Press Ctrl+C to stop
echo ============================================================================
echo.

set RESTART_COUNT=0

:RESTART_LOOP
set /a RESTART_COUNT+=1

if %RESTART_COUNT% GTR 1 (
    echo.
    echo [%date% %time%] === Auto-Restart #%RESTART_COUNT% ===
    echo Waiting 5 seconds before restart...
    ping -n 6 127.0.0.1 > nul
)

echo [%date% %time%] Starting data monitor...

REM Run Python directly
.venv\Scripts\python.exe orderbook.py --coin BTC --silent --max-runtime 12

REM Capture exit code immediately
set PYEXIT=%ERRORLEVEL%

echo.
echo [%date% %time%] Monitor exited with code: %PYEXIT%

REM Exit code 42 means restart requested
if "%PYEXIT%"=="42" (
    echo [%date% %time%] Restart requested by Python script.
    goto RESTART_LOOP
)

REM Any non-zero exit (crash) - also restart
if not "%PYEXIT%"=="0" (
    echo [%date% %time%] Crash detected. Will restart.
    ping -n 11 127.0.0.1 > nul
    goto RESTART_LOOP
)

REM Exit code 0 - normal exit, stop
echo.
echo [%date% %time%] Normal exit. Stopping all processes.
echo.

REM Cleanup: kill keep-awake and rebound strategy
taskkill /FI "WINDOWTITLE eq KeepAwake*" > nul 2>&1
taskkill /FI "WINDOWTITLE eq Rebound Strategy*" > nul 2>&1

echo Done.
