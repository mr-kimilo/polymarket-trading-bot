#!/bin/bash
# ============================================================
#  5-minute BTC Orderbook Monitor (Linux)
#  数据监控 - 5分钟市场
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

mkdir -p logs files/5m

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting BTC 5-minute orderbook monitor..."
    python orderbook_5m.py --coin BTC --silent --max-runtime 12
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 42 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-restart triggered. Restarting in 5 seconds..."
        sleep 5
    elif [ $EXIT_CODE -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Unexpected exit. Restarting in 10 seconds..."
        sleep 10
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Monitor exited normally."
        break
    fi
done
