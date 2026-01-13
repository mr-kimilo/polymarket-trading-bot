@echo off
REM ============================================================================
REM Polymarket Data Monitor with Keep-Awake and Auto-Restart
REM 
REM This script:
REM 1. Starts a PowerShell keep-awake process in background
REM 2. Runs the orderbook monitor in silent mode with live status output
REM 3. Auto-restarts every 12 hours or when connection is lost
REM 
REM The keep-awake process simulates keyboard activity (F15 key) every 60
REM seconds to prevent Windows from sleeping. This method doesn't require
REM admin privileges.
REM 
REM Features:
REM   - Auto-restart every 12 hours to prevent connection issues
REM   - Auto-restart on connection loss (no data for 5 minutes)
REM   - Crash recovery with automatic restart
REM   - Exit code 42 = restart requested, 0 = normal exit
REM 
REM Usage:
REM   - Double-click to run
REM   - Add to Startup folder: shell:startup
REM   - Press Ctrl+C twice to fully stop (once to stop Python, once to exit loop)
REM ============================================================================

title Polymarket Monitor with Keep-Awake

setlocal enabledelayedexpansion

echo ============================================================================
echo    Polymarket Data Monitor with Keep-Awake and Auto-Restart
echo ============================================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Ensure directories exist
if not exist "logs" mkdir logs
if not exist "files" mkdir files

echo [%date% %time%] Initializing...
echo.
echo   [1/4] Setting up keep-awake process...

REM Start keep-awake PowerShell script in background (minimized, hidden)
start "KeepAwake" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0keep_awake.ps1"

echo         Keep-awake started (F15 key every 60s)
echo.
echo   [2/4] Checking Python environment...

REM Setup or activate virtual environment
if not exist ".venv\Scripts\activate.bat" goto CREATE_VENV
goto ACTIVATE_VENV

:CREATE_VENV
echo         Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat
if exist "requirements.txt" (
    echo         Installing dependencies, please wait...
    .venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel > logs\pip_install.log 2>&1
    .venv\Scripts\python.exe -m pip install -r requirements.txt >> logs\pip_install.log 2>&1
)
.venv\Scripts\python.exe -m pip install rich >> logs\pip_install.log 2>&1
echo         Environment ready!
goto CONTINUE_START

:ACTIVATE_VENV
call .venv\Scripts\activate.bat
echo         Virtual environment activated
goto CONTINUE_START

:CONTINUE_START

echo.
echo   [3/4] Starting Polymarket BTC Monitor (with auto-restart)...
echo.
echo ============================================================================
echo    Monitor Status: RUNNING
echo    Coin: BTC
echo    Mode: Silent (data saved to files/ directory)
echo    Logs: logs/silent_monitor.log
echo    Keep-Awake: Active (system will not sleep)
echo    Auto-Restart: Every 12 hours or on connection loss
echo ============================================================================
echo.
echo   [4/4] Monitoring started at %date% %time%
echo.
echo   Press Ctrl+C twice to fully stop the monitor
echo.
echo ----------------------------------------------------------------------------
echo   Live Status (updates every minute):
echo ----------------------------------------------------------------------------

set RESTART_COUNT=0

:MONITOR_LOOP
set /a RESTART_COUNT+=1

if %RESTART_COUNT% GTR 1 (
    echo.
    echo ============================================================================
    echo    [Auto-Restart #%RESTART_COUNT%] Restarting monitor at %date% %time%
    echo ============================================================================
    echo.
    REM Wait 5 seconds before restart
    timeout /t 5 /nobreak > nul
)

REM Run the monitor in silent mode with 12-hour max runtime
REM Exit codes: 0 = normal exit (Ctrl+C), 42 = restart requested
.venv\Scripts\python.exe orderbook.py --coin BTC --silent --max-runtime 12

set EXIT_CODE=%ERRORLEVEL%

echo.
echo [%date% %time%] Monitor exited with code: %EXIT_CODE%

REM Check if restart is requested (exit code 42)
if %EXIT_CODE% EQU 42 (
    echo [%date% %time%] Restart requested. Restarting in 5 seconds...
    goto MONITOR_LOOP
)

REM Also restart on crash (non-zero exit code except for manual exit)
if %EXIT_CODE% NEQ 0 (
    echo [%date% %time%] Unexpected exit. Restarting in 10 seconds...
    timeout /t 10 /nobreak > nul
    goto MONITOR_LOOP
)

echo.
echo ============================================================================
echo    Monitor Status: STOPPED (Normal Exit)
echo    Total Restarts: %RESTART_COUNT%
echo ============================================================================
echo.
echo [%date% %time%] Monitor stopped normally.

REM Kill the keep-awake process when main script ends
echo [%date% %time%] Stopping keep-awake process...
taskkill /FI "WINDOWTITLE eq KeepAwake*" >nul 2>&1
powershell -Command "Get-Process powershell | Where-Object {$_.MainWindowTitle -like '*KeepAwake*'} | Stop-Process -Force" >nul 2>&1

echo [%date% %time%] All processes stopped.
echo.
endlocal
exit /b 0
