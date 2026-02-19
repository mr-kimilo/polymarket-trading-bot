@echo off
REM Start the 5-minute BTC orderbook monitor in silent mode
REM Data will be saved to files/5m/ directory

:loop
echo [%date% %time%] Starting BTC 5-minute orderbook monitor...
python orderbook_5m.py --coin BTC --silent --max-runtime 12

REM Check exit code - 42 means restart requested
if %ERRORLEVEL% EQU 42 (
    echo [%date% %time%] Auto-restart triggered. Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
    goto loop
)

echo [%date% %time%] Monitor exited normally.
pause
