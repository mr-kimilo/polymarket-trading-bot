@echo off
chcp 65001 >nul
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

echo Starting BTC monitor...
REM Change to script directory
cd /d "%~dp0"

REM Ensure logs and files directories exist
if not exist "logs" mkdir logs
if not exist "files" mkdir files

REM Create or activate virtual environment if needed
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment and installing requirements...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    if exist "requirements.txt" (
        echo Installing Python dependencies from requirements.txt...
        .venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel > logs\pip_install_background.log 2>&1
        .venv\Scripts\python.exe -m pip install -r requirements.txt >> logs\pip_install_background.log 2>&1
    ) else (
        echo requirements.txt not found; ensure dependencies installed manually. > logs\pip_install_background.log
    )
    REM Ensure 'rich' is installed
    .venv\Scripts\python.exe -m pip install rich >> logs\pip_install_background.log 2>&1
) else (
    call .venv\Scripts\activate.bat
)

REM Start BTC monitor in minimized window using venv python
echo Starting BTC monitor...
start "Polymarket-BTC" /min cmd /c ".venv\Scripts\python.exe orderbook.py --coin BTC --silent >> logs\background_btc.log 2>&1"

REM Optional: Start other coin monitors (uncomment as needed)
REM start "Polymarket-ETH" /min cmd /c "python orderbook.py --coin ETH --silent"
REM start "Polymarket-SOL" /min cmd /c "python orderbook.py --coin SOL --silent"
REM start "Polymarket-XRP" /min cmd /c "python orderbook.py --coin XRP --silent"

echo.
echo Monitors started in background (minimized windows).
echo Data will be saved to: %~dp0files\
echo.
echo To stop: Close the minimized command windows or use Task Manager.
