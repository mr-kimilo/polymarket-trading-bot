#!/bin/bash
# ============================================================
#  15-minute BTC Orderbook Monitor (Linux)
#  数据监控 - 15分钟市场
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

mkdir -p logs files

RESTART_COUNT=0

while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))

    if [ $RESTART_COUNT -gt 1 ]; then
        echo ""
        echo "[Auto-Restart #$RESTART_COUNT] $(date '+%Y-%m-%d %H:%M:%S')"
        sleep 5
    fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting BTC 15-minute orderbook monitor..."
    python orderbook.py --coin BTC --silent --max-runtime 12
    EXIT_CODE=$?

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Monitor exited with code: $EXIT_CODE"

    if [ $EXIT_CODE -eq 42 ]; then
        echo "Restart requested. Restarting in 5 seconds..."
        sleep 5
    elif [ $EXIT_CODE -ne 0 ]; then
        echo "Unexpected exit. Restarting in 10 seconds..."
        sleep 10
    else
        echo "Normal exit."
        break
    fi
done
