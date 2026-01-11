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

REM Change to script directory
cd /d "%~dp0"

REM Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Create logs directory if not exists
if not exist "logs" mkdir logs

REM Get current date for log file
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set logdate=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set logtime=%%a-%%b

REM Run the monitor in silent mode
REM Output is redirected to log file, errors to separate error log
echo [%date% %time%] Starting Polymarket Silent Monitor...
echo [%date% %time%] Press Ctrl+C to stop

python orderbook.py --coin BTC --silent 2>&1

echo [%date% %time%] Monitor stopped.
pause
