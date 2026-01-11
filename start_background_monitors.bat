@echo off
REM ============================================================================
REM Polymarket Data Monitor - Background Service
REM 
REM This script runs multiple coin monitors in background (minimized windows)
REM to collect 15-minute market data continuously.
REM 
REM Data is saved to files/ directory as JSON files.
REM 
REM Usage:
REM   - Add to Windows Startup folder: shell:startup
REM   - Or add to Task Scheduler with "Run at startup" trigger
REM ============================================================================

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
    pause
    exit /b 1
)

REM Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Create files directory if not exists
if not exist "files" mkdir files

REM Start BTC monitor in minimized window
echo Starting BTC monitor...
start "Polymarket-BTC" /min cmd /c "python orderbook.py --coin BTC --silent"

REM Optional: Start other coin monitors (uncomment as needed)
REM start "Polymarket-ETH" /min cmd /c "python orderbook.py --coin ETH --silent"
REM start "Polymarket-SOL" /min cmd /c "python orderbook.py --coin SOL --silent"
REM start "Polymarket-XRP" /min cmd /c "python orderbook.py --coin XRP --silent"

echo.
echo Monitors started in background (minimized windows).
echo Data will be saved to: %~dp0files\
echo.
echo To stop: Close the minimized command windows or use Task Manager.
