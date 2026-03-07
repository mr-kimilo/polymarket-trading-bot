@echo off
chcp 65001 >nul
REM ============================================================================
REM Rebound Strategy Runner - Simulation Mode
REM 
REM This script runs the Rebound trading strategy in SIMULATION mode.
REM No real orders will be placed.
REM 
REM Strategy (V2 mode - uses config.yaml strategy.type):
REM   - Monitors BTC 15-minute markets
REM   - Dynamic parameters loaded from strategy3_rules DB table
REM   - Triggers based on configured segments (stage_buy from DB)
REM   - Take-profit/stop-loss per dynamic DB rules
REM   - Records all trades to database (simulated)
REM 
REM Usage:
REM   - Double-click to run
REM   - Use --live flag for real trading (modify this file)
REM ============================================================================

title Rebound Strategy - BTC [SIMULATION]

cd /d "%~dp0"

REM Ensure directories exist
if not exist "logs" mkdir logs

echo ============================================================================
echo    Rebound Strategy - SIMULATION MODE
echo ============================================================================
echo.
echo [%date% %time%] Starting...
echo.

REM Check/create virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    echo Installing dependencies...
    .venv\Scripts\python.exe -m pip install --upgrade pip > logs\pip_install.log 2>&1
    .venv\Scripts\python.exe -m pip install -r requirements.txt >> logs\pip_install.log 2>&1
    .venv\Scripts\python.exe -m pip install rich psycopg2-binary flask >> logs\pip_install.log 2>&1
)

echo.
echo ============================================================================
echo    Strategy Configuration:
echo      - Coin: BTC
echo      - Mode: SIMULATION (no real orders)
echo      - Size: $10 USDC per trade
echo      - Strategy type: from config.yaml (V2 dynamic params)
echo      - Parameters: loaded from strategy3_rules DB table
echo    
echo    Press Ctrl+C to stop
echo ============================================================================
echo.

set RESTART_COUNT=0

:STRATEGY_LOOP
set /a RESTART_COUNT+=1

if %RESTART_COUNT% GTR 1 (
    echo.
    echo [%date% %time%] === Restart #%RESTART_COUNT% ===
    timeout /t 5 /nobreak > nul
)

REM Run Rebound Strategy in simulation mode (strategy type from config.yaml)
.venv\Scripts\python.exe apps/run_rebound.py --coin BTC --simulation --size 10

set EXIT_CODE=%ERRORLEVEL%

echo.
echo [%date% %time%] Strategy exited with code: %EXIT_CODE%

REM Restart on crash (non-zero exit)
if %EXIT_CODE% NEQ 0 (
    echo [%date% %time%] Restarting in 10 seconds...
    timeout /t 10 /nobreak > nul
    goto STRATEGY_LOOP
)

echo.
echo [%date% %time%] Strategy stopped normally.
pause
