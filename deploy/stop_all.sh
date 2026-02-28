#!/bin/bash
# ============================================================
#  Stop All Services
#  停止所有后台服务
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "Stopping all Polymarket services..."

# 从 PID 文件读取并 kill
for pidfile in logs/monitor_15m.pid logs/monitor_5m.pid logs/rebound_live.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            echo "  Stopping PID $PID ($(basename "$pidfile" .pid))..."
            kill "$PID" 2>/dev/null
            # 也 kill 其子进程
            pkill -P "$PID" 2>/dev/null
        else
            echo "  PID $PID already stopped"
        fi
        rm -f "$pidfile"
    fi
done

# 兜底：kill 所有相关 Python 进程
echo "  Cleaning up remaining Python processes..."
pkill -f "orderbook.py" 2>/dev/null
pkill -f "orderbook_5m.py" 2>/dev/null
pkill -f "run_rebound.py" 2>/dev/null

echo "All services stopped."
