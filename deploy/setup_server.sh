#!/bin/bash
# ============================================================
#  Polymarket Trading Bot - 服务器快速部署脚本
#  Server Quick Setup Script
# ============================================================
#
# 在新服务器上运行此脚本即可完成全部配置:
#   chmod +x deploy/setup_server.sh
#   ./deploy/setup_server.sh
#
# 前提条件:
#   - Ubuntu 22.04 LTS
#   - sudo 权限
#   - 已上传项目代码到 ~/polymarket-trading-bot
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "============================================================"
echo "  Polymarket Trading Bot - Server Setup"
echo "============================================================"
echo ""

# -------- 1. 系统依赖 --------
echo "[1/7] Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib \
    libpq-dev python3-dev build-essential \
    git curl htop

echo "  Done."

# -------- 2. Python 设置 --------
echo ""
echo "[2/7] Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
echo "  Done. Python $(python --version)"

# -------- 3. PostgreSQL 设置 --------
echo ""
echo "[3/7] Setting up PostgreSQL..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 检查用户是否已存在
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='sniper_user'" | grep -q 1; then
    echo "  User sniper_user already exists."
else
    echo "  Creating database user..."
    read -sp "  Enter database password for sniper_user: " DB_PASS
    echo ""
    sudo -u postgres psql -c "CREATE USER sniper_user WITH PASSWORD '$DB_PASS';"
fi

# 检查数据库是否已存在
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='poly_market'" | grep -q 1; then
    echo "  Database poly_market already exists."
else
    echo "  Creating database..."
    sudo -u postgres psql -c "CREATE DATABASE poly_market OWNER sniper_user;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE poly_market TO sniper_user;"
fi

echo "  Done."

# -------- 4. 初始化数据库表 --------
echo ""
echo "[4/7] Initializing database tables..."
source .venv/bin/activate
python scripts/init_database.py || {
    echo "  Python init failed, trying SQL directly..."
    sudo -u postgres psql -d poly_market -f db_init.sql
}
echo "  Done."

# -------- 5. 配置文件 --------
echo ""
echo "[5/7] Checking configuration files..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  Created .env from template. Please edit it with your credentials:"
    echo "    nano .env"
else
    echo "  .env already exists."
fi

if [ ! -f "config.yaml" ]; then
    cp config.example.yaml config.yaml
    echo "  Created config.yaml from template. Please edit if needed:"
    echo "    nano config.yaml"
else
    echo "  config.yaml already exists."
fi

chmod 600 .env
echo "  Done."

# -------- 6. 创建必要目录 --------
echo ""
echo "[6/7] Creating directories..."
mkdir -p logs files files/5m credentials
echo "  Done."

# -------- 7. 添加执行权限 --------
echo ""
echo "[7/7] Setting script permissions..."
chmod +x deploy/*.sh
echo "  Done."

# -------- 完成 --------
echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Edit your credentials:"
echo "     nano .env"
echo ""
echo "  2. Test connection:"
echo "     source .venv/bin/activate"
echo "     python -c \"import requests; print(requests.get('https://clob.polymarket.com/time').status_code)\""
echo ""
echo "  3. Test simulation mode:"
echo "     python apps/run_rebound.py --coin BTC --size 1"
echo ""
echo "  4. Start live trading:"
echo "     ./deploy/run_rebound_live.sh"
echo ""
echo "  5. Or install as systemd services (recommended for 24/7):"
echo "     sudo cp deploy/*.service /etc/systemd/system/"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable polymarket-bot polymarket-monitor"
echo "     sudo systemctl start polymarket-bot polymarket-monitor"
echo ""
echo "============================================================"
