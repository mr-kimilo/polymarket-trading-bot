@echo off
chcp 65001 >nul
REM ============================================================
REM  Rebound Strategy - LIVE TRADING Mode
REM  真实交易模式 - 请谨慎使用！
REM ============================================================
REM 
REM 配置说明:
REM   --coin BTC      : 交易币种
REM   --size 3        : 每笔交易3美元
REM   --live          : 启用真实交易
REM 
REM 环境变量要求（.env文件）:
REM   POLY_PRIVATE_KEY  : 钱包私钥
REM   POLY_SAFE_ADDRESS : 安全钱包地址
REM ============================================================

title Rebound Strategy - LIVE TRADING
cd /d %~dp0

echo.
echo ============================================================
echo  警告：即将启动真实交易模式！
echo  WARNING: About to start LIVE TRADING mode!
echo ============================================================
echo.
echo  交易参数 Trading Parameters:
echo    币种 Coin: BTC
echo    金额 Size: $3.00 USDC per trade
echo    模式 Mode: LIVE (真实交易)
echo.
echo  请确认以下环境变量已正确配置:
echo    - POLY_PRIVATE_KEY (钱包私钥)
echo    - POLY_SAFE_ADDRESS (安全钱包地址)
echo.
echo ============================================================
echo.

REM 激活虚拟环境（如果存在）
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

:start
echo [%date% %time%] 启动 Rebound 真实交易策略...
echo.

REM 真实交易: --live 启用, --size 2 每笔2美元
python apps/run_rebound.py --coin BTC --size 2 --live

echo.
echo [%date% %time%] 策略已停止。

REM 检查退出代码
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] 检测到错误，10秒后重启...
    timeout /t 10 /nobreak
    goto start
)

echo.
echo 按任意键退出或关闭窗口...
pause >nul
