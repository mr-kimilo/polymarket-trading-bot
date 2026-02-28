#!/bin/bash
# ============================================================
#  Start All Services (Linux)
#  启动所有服务（监控 + 交易策略）
# ============================================================
#
# 使用方式:
#   ./deploy/start_all.sh          # 前台运行（测试用）
#   ./deploy/start_all.sh --bg     # 后台运行（推荐）
#
# 推荐：使用 systemd 服务（见部署指南）
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

mkdir -p logs

echo "============================================================"
echo "  Polymarket Full Monitor Suite (Linux)"
echo "============================================================"
echo ""
echo "  [1] 15-minute monitor"
echo "  [2] 5-minute monitor"
echo "  [3] Rebound strategy (LIVE)"
echo ""

# 启动15分钟监控（后台）
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting 15-minute monitor..."
nohup "$SCRIPT_DIR/start_monitor.sh" >> logs/monitor_15m.log 2>&1 &
MONITOR_15M_PID=$!
echo "  PID: $MONITOR_15M_PID"

# 启动5分钟监控（后台）
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting 5-minute monitor..."
nohup "$SCRIPT_DIR/start_5m_monitor.sh" >> logs/monitor_5m.log 2>&1 &
MONITOR_5M_PID=$!
echo "  PID: $MONITOR_5M_PID"

# 启动交易策略（后台）
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Rebound strategy (LIVE)..."
nohup "$SCRIPT_DIR/run_rebound_live.sh" >> logs/rebound_live.log 2>&1 &
REBOUND_PID=$!
echo "  PID: $REBOUND_PID"

echo ""
echo "============================================================"
echo "  All services started!"
echo ""
echo "  PIDs:"
echo "    15m Monitor: $MONITOR_15M_PID"
echo "    5m Monitor:  $MONITOR_5M_PID"
echo "    Rebound:     $REBOUND_PID"
echo ""
echo "  View logs:"
echo "    tail -f logs/monitor_15m.log"
echo "    tail -f logs/monitor_5m.log"
echo "    tail -f logs/rebound_live.log"
echo ""
echo "  Stop all:"
echo "    kill $MONITOR_15M_PID $MONITOR_5M_PID $REBOUND_PID"
echo "============================================================"

# 保存 PID 文件以便后续停止
echo "$MONITOR_15M_PID" > logs/monitor_15m.pid
echo "$MONITOR_5M_PID" > logs/monitor_5m.pid
echo "$REBOUND_PID" > logs/rebound_live.pid
