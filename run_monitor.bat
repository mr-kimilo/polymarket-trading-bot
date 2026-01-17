@echo off
chcp 65001 >nul
REM ============================================================================
REM Polymarket Data Monitor - Main Entry Point with Auto-Restart
REM 
REM This is the main script to run. It handles:
REM 1. Setting up keep-awake process
REM 2. Running the monitor in an infinite loop
REM 3. Auto-restarting on exit code 42 or crashes
REM 
REM Usage: Double-click to run, or add to Startup folder
REM ============================================================================

title Polymarket Monitor

cd /d "%~dp0"

REM Ensure directories exist
if not exist "logs" mkdir logs
if not exist "files" mkdir files

echo ============================================================================
echo    Polymarket Data Monitor with Keep-Awake
echo ============================================================================
echo.
echo [%date% %time%] Starting...
echo.

REM Start keep-awake PowerShell script in background
echo [1/2] Starting keep-awake process...
start "KeepAwake" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0keep_awake.ps1"
echo       Done.
echo.

REM Check/create virtual environment
echo [2/2] Checking Python environment...
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

echo ============================================================================
echo    Monitor Status: RUNNING
echo    Coin: BTC
echo    Mode: Silent (data saved to files/)
echo    Auto-Restart: Every 12 hours
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

echo [%date% %time%] Starting monitor...

REM Run Python directly without call
.venv\Scripts\python.exe orderbook.py --coin BTC --silent --max-runtime 12

REM Capture exit code immediately
set PYEXIT=%ERRORLEVEL%

echo.
echo [%date% %time%] Python exited with code: %PYEXIT%

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
echo [%date% %time%] Normal exit. Stopping monitor.
echo.

REM Cleanup: kill keep-awake
taskkill /FI "WINDOWTITLE eq KeepAwake*" > nul 2>&1

echo Done.
pause
