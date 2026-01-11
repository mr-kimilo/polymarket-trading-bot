@echo off
REM ============================================================================
REM Polymarket Data Monitor - Silent Mode
REM 
REM This script runs the orderbook monitor in silent mode to collect
REM 15-minute market data and save to JSON files.
REM 
REM Usage:
REM   - Double-click to run manually
REM   - Add to Task Scheduler for automatic startup
REM   - Add to Startup folder: shell:startup
REM ============================================================================

title Polymarket Silent Monitor - BTC

echo [%date% %time%] Starting Polymarket Silent Monitor...
echo [%date% %time%] Press Ctrl+C to stop

REM Change to script directory
cd /d "%~dp0"

REM Ensure logs directory exists
if not exist "logs" mkdir logs

REM Setup or activate virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment and installing requirements...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    if exist "requirements.txt" (
        echo Installing Python dependencies from requirements.txt...
        .venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel > logs\pip_install.log 2>&1
        .venv\Scripts\python.exe -m pip install -r requirements.txt >> logs\pip_install.log 2>&1
    ) else (
        echo requirements.txt not found; ensure dependencies installed manually. > logs\pip_install.log
    )
    echo Ensuring 'rich' is installed...
    .venv\Scripts\python.exe -m pip install rich >> logs\pip_install.log 2>&1
) else (
    call .venv\Scripts\activate.bat
)

REM Run the monitor in silent mode using the venv python
echo [%date% %time%] Starting Polymarket Silent Monitor...
echo [%date% %time%] Press Ctrl+C to stop

.venv\Scripts\python.exe orderbook.py --coin BTC --silent >> logs\silent_monitor.log 2>&1

echo [%date% %time%] Monitor stopped. >> logs\silent_monitor.log
REM Exit without pause for automatic/unattended operation
exit /b 0

