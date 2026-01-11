@echo off
REM ============================================================================
REM Polymarket Data Monitor with Keep-Awake
REM 
REM This script:
REM 1. Starts a PowerShell keep-awake process in background
REM 2. Runs the orderbook monitor in silent mode with live status output
REM 
REM The keep-awake process simulates keyboard activity (F15 key) every 60
REM seconds to prevent Windows from sleeping. This method doesn't require
REM admin privileges.
REM 
REM Usage:
REM   - Double-click to run
REM   - Add to Startup folder: shell:startup
REM   - Press Ctrl+C in the main window to stop (keep-awake will also stop)
REM ============================================================================

title Polymarket Monitor with Keep-Awake

echo ============================================================================
echo    Polymarket Data Monitor with Keep-Awake
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
echo   [3/4] Starting Polymarket BTC Monitor...
echo.
echo ============================================================================
echo    Monitor Status: RUNNING
echo    Coin: BTC
echo    Mode: Silent (data saved to files/ directory)
echo    Logs: logs/silent_monitor.log
echo    Keep-Awake: Active (system will not sleep)
echo ============================================================================
echo.
echo   [4/4] Monitoring started at %date% %time%
echo.
echo   Press Ctrl+C to stop the monitor
echo.
echo ----------------------------------------------------------------------------
echo   Live Status (updates every minute):
echo ----------------------------------------------------------------------------

REM Run the monitor in silent mode
REM Note: Output shown in console, also logged by Python to logs/silent_monitor.log
.venv\Scripts\python.exe orderbook.py --coin BTC --silent

echo.
echo ============================================================================
echo    Monitor Status: STOPPED
echo ============================================================================
echo.
echo [%date% %time%] Monitor stopped.

REM Kill the keep-awake process when main script ends
echo [%date% %time%] Stopping keep-awake process...
taskkill /FI "WINDOWTITLE eq KeepAwake*" >nul 2>&1
powershell -Command "Get-Process powershell | Where-Object {$_.MainWindowTitle -like '*KeepAwake*'} | Stop-Process -Force" >nul 2>&1

echo [%date% %time%] All processes stopped.
echo.
echo Press any key to exit...
pause >nul
