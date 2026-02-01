@echo off
chcp 65001 >nul
title Direct Sell - 直接卖出持仓

echo ============================================================
echo           DIRECT SELL - 直接卖出所有持仓
echo ============================================================
echo.
echo 此脚本将直接以市价卖出所有活跃持仓
echo 警告：LIVE模式将执行真实交易！
echo.
echo 选项:
echo   1. 模拟模式 (SIMULATION) - 仅测试，不真实交易
echo   2. 真实模式 (LIVE) - 执行真实卖出
echo   3. 退出
echo.
set /p choice="请选择 (1/2/3): "

if "%choice%"=="1" (
    echo.
    echo 启动模拟模式...
    python scripts/direct_sell.py --coin BTC --reason "manual_exit"
) else if "%choice%"=="2" (
    echo.
    echo ⚠️  警告：即将执行真实交易！
    set /p confirm="确认执行真实卖出? (yes/no): "
    if /i "%confirm%"=="yes" (
        echo.
        echo 启动真实模式...
        python scripts/direct_sell.py --coin BTC --live --reason "manual_exit"
    ) else (
        echo 已取消。
    )
) else if "%choice%"=="3" (
    echo 退出。
    exit /b 0
) else (
    echo 无效选项，退出。
    exit /b 1
)

echo.
echo ============================================================
echo                     操作完成
echo ============================================================
pause
