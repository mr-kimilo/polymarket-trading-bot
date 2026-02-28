#!/bin/bash
# ============================================================
#  Rebound Strategy - LIVE TRADING Mode (Linux)
#  真实交易模式 - 请谨慎使用！
# ============================================================
#
# 功能:
#   1. 运行 Rebound 真实交易策略
#   2. 崩溃自动重启
#
# 配置说明:
#   --coin BTC      : 交易币种
#   --size 3        : 每笔交易3美元
#   --live          : 启用真实交易
#
# 环境变量要求（.env文件）:
#   POLY_PRIVATE_KEY  : 钱包私钥
#   POLY_SAFE_ADDRESS : 安全钱包地址
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo ""
echo "============================================================"
echo "  警告：即将启动真实交易模式！"
echo "  WARNING: About to start LIVE TRADING mode!"
echo "============================================================"
echo ""
echo "  交易参数 Trading Parameters:"
echo "    币种 Coin: BTC"
echo "    金额 Size: \$3.00 USDC per trade"
echo "    模式 Mode: LIVE (真实交易)"
echo ""

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# 确保日志目录存在
mkdir -p logs

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 Rebound 真实交易策略..."
    echo ""

    # 真实交易: --live 启用, --size 3 每笔3美元
    python apps/run_rebound.py --coin BTC --size 3 --live
    EXIT_CODE=$?

    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 策略已停止 (退出码: $EXIT_CODE)"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到错误，10秒后重启..."
        sleep 10
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 正常退出"
        break
    fi
done
