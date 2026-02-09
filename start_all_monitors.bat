@echo off
chcp 65001 >nul
REM ============================================================================
REM Polymarket Full Monitor Suite with Keep-Awake
REM 
REM This script starts all monitoring components:
REM 1. Keep-Awake process (prevents system sleep)
REM 2. Data Monitor (saves market data to JSON files)
REM 3. Rebound Strategy (simulation mode - monitors for trading signals)
REM 
REM Both monitors run independently with auto-restart capability.
REM 
REM Features:
REM   - Keep-awake prevents system sleep (SetThreadExecutionState API)
REM   - Data monitor saves 15-min period data to files/
REM   - Rebound strategy detects rapid price drops
REM   - Auto-restart every 12 hours
REM   - Crash recovery with automatic restart
REM 
REM Usage:
REM   - Double-click to run
REM   - Add to Startup folder: shell:startup
REM   - Press Ctrl+C to stop all processes
REM ============================================================================

title Polymarket Full Monitor Suite

setlocal enabledelayedexpansion

echo ============================================================================
echo    Polymarket Full Monitor Suite with Keep-Awake
echo ============================================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Ensure directories exist
if not exist "logs" mkdir logs
if not exist "files" mkdir files

echo [%date% %time%] Initializing...
echo.

REM ============================================================================
REM Step 1: Keep-Awake
REM ============================================================================
echo   [1/4] Setting up keep-awake process...
start "KeepAwake" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0keep_awake.ps1"
echo         Keep-awake started (F15 key every 60s)
echo.

REM ============================================================================
REM Step 2: Python Environment
REM ============================================================================
echo   [2/4] Checking Python environment...

if not exist ".venv\Scripts\python.exe" (
    echo         Creating virtual environment...
    python -m venv .venv
    echo         Installing dependencies, please wait...
    .venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel > logs\pip_install.log 2>&1
    .venv\Scripts\python.exe -m pip install -r requirements.txt >> logs\pip_install.log 2>&1
    .venv\Scripts\python.exe -m pip install rich psycopg2-binary >> logs\pip_install.log 2>&1
    echo         Environment ready!
) else (
    echo         Virtual environment found
)
echo.

REM ============================================================================
REM Step 3: Start Rebound Strategy (separate window)
REM ============================================================================
echo   [3/4] Starting Rebound Strategy (SIMULATION mode)...
start "Rebound Strategy - BTC [SIMULATION]" cmd /k "cd /d "%~dp0" && .venv\Scripts\python.exe apps/run_rebound.py --coin BTC"
echo         Started in separate window
echo         Mode: SIMULATION (no real orders)
echo         Trigger: A segment, price drop below 0.30
echo.

REM ============================================================================
REM Step 4: Start Data Monitor (this window)
REM ============================================================================
echo   [4/4] Starting Data Monitor...
echo.
echo ============================================================================
echo    MONITOR STATUS: RUNNING
echo ============================================================================
echo.
echo    Data Monitor (this window):
echo      - Coin: BTC
echo      - Mode: Silent (data saved to files/)
echo      - Auto-Restart: Every 12 hours
echo      - Logs: logs/silent_monitor.log
echo.
echo    Rebound Strategy (separate window):
echo      - Coin: BTC
echo      - Mode: SIMULATION
echo      - Active Segments: A (15-10 min)
echo      - Database: rebound_orders table
echo.
echo    Keep-Awake: Active (system will not sleep)
echo.
echo ============================================================================
echo    Press Ctrl+C to stop all processes
echo ============================================================================
echo.
echo ----------------------------------------------------------------------------
echo    Live Status (Data Monitor):
echo ----------------------------------------------------------------------------

set RESTART_COUNT=0

:MONITOR_LOOP
set /a RESTART_COUNT+=1

if %RESTART_COUNT% GTR 1 (
    echo.
    echo ============================================================================
    echo    [Auto-Restart #%RESTART_COUNT%] Restarting data monitor at %date% %time%
    echo ============================================================================
    echo.
    timeout /t 5 /nobreak > nul
)

REM Run the data monitor
.venv\Scripts\python.exe orderbook.py --coin BTC --silent --max-runtime 12

set EXIT_CODE=%ERRORLEVEL%

echo.
echo [%date% %time%] Data monitor exited with code: %EXIT_CODE%

if %EXIT_CODE% EQU 42 goto DO_RESTART
if %EXIT_CODE% NEQ 0 goto DO_CRASH_RESTART
goto NORMAL_EXIT

:DO_RESTART
echo [%date% %time%] Restart requested. Restarting in 5 seconds...
goto MONITOR_LOOP

:DO_CRASH_RESTART
echo [%date% %time%] Unexpected exit. Restarting in 10 seconds...
timeout /t 10 /nobreak > nul
goto MONITOR_LOOP

:NORMAL_EXIT
echo.
echo ============================================================================
echo    MONITOR STATUS: STOPPED (Normal Exit)
echo    Total Restarts: %RESTART_COUNT%
echo ============================================================================
echo.
echo [%date% %time%] Stopping all processes...

REM Kill the keep-awake and rebound strategy processes
taskkill /FI "WINDOWTITLE eq KeepAwake*" > nul 2>&1
taskkill /FI "WINDOWTITLE eq Rebound Strategy*" > nul 2>&1

echo [%date% %time%] All processes stopped.
echo.
pause
