# 服务器部署指南 - Polymarket Trading Bot

> 本指南帮助你将交易机器人从本地 Windows 部署到云服务器（Linux），实现 24/7 不间断运行。

---

## 一、服务器推荐

### 需求分析

| 需求 | 说明 |
|------|------|
| 访问 Polymarket | 需要能访问 `clob.polymarket.com`、`polygon-rpc.com`、Binance API |
| 低延迟 | 服务器靠近 Polymarket 基础设施（美国东部） |
| 月费 ≤ 10元 | 约 $1.4 USD/月 |
| 配置要求 | 1 CPU / 512MB+ RAM / 10GB+ 存储 / Python 3.10+ |

### 推荐方案（按优先级排序）

#### ⭐ 方案1：Oracle Cloud 永久免费（强烈推荐）

| 项目 | 说明 |
|------|------|
| **价格** | **永久免费** |
| **配置** | ARM 实例: 4 OCPU + 24GB RAM（或 AMD x86: 1 OCPU + 1GB RAM） |
| **机房** | 美国 Phoenix / Ashburn / 日本东京 / 韩国首尔 |
| **延迟** | 美国机房到 Polymarket 延迟 < 10ms |
| **优点** | 免费、配置高、稳定、支持 Ubuntu |
| **缺点** | 注册需要信用卡验证（不扣费）、偶尔回收闲置实例 |
| **注册** | https://www.oracle.com/cloud/free/ |

**推荐选择**: US East (Ashburn) 区域，ARM 实例，Ubuntu 22.04

#### 方案2：Google Cloud 永久免费层

| 项目 | 说明 |
|------|------|
| **价格** | **永久免费**（e2-micro 实例） |
| **配置** | 0.25 vCPU + 1GB RAM + 30GB 存储 |
| **机房** | 美国 Oregon / Iowa / South Carolina |
| **延迟** | < 30ms |
| **优点** | 免费、Google 基础设施稳定 |
| **缺点** | 配置较低、需要信用卡、超出免费额度会扣费 |
| **注册** | https://cloud.google.com/free |

#### 方案3：RackNerd 超值 VPS

| 项目 | 说明 |
|------|------|
| **价格** | ~$10.28/年（约 **6元/月**） |
| **配置** | 1 vCPU + 768MB RAM + 15GB SSD |
| **机房** | 美国洛杉矶 / 纽约 / 达拉斯 等 |
| **延迟** | < 50ms (美国西海岸) |
| **优点** | 便宜、KVM 虚拟化、多机房选择 |
| **缺点** | 特价需要等促销、客服一般 |
| **购买** | https://www.racknerd.com （关注 Black Friday / 新年特价） |

#### 方案4：CloudCone VPS

| 项目 | 说明 |
|------|------|
| **价格** | ~$1.99/月（约 **14元/月**，略超预算） |
| **配置** | 1 vCPU + 512MB RAM + 10GB SSD |
| **机房** | 美国洛杉矶 |
| **延迟** | < 50ms |
| **优点** | 按小时计费、随时删除停止计费 |
| **购买** | https://cloudcone.com |

#### 方案5：Contabo VPS（超高性价比）

| 项目 | 说明 |
|------|------|
| **价格** | €4.99/月（约 **38元/月**，超预算但配置极高） |
| **配置** | 4 vCPU + 8GB RAM + 50GB SSD |
| **机房** | 美国、德国、英国 |
| **优点** | 性价比极高、适合运行多个策略 |
| **购买** | https://contabo.com |

### 🏆 最终建议

**首选 Oracle Cloud 免费层**（ARM 实例），原因：
1. ✅ 完全免费，0 成本
2. ✅ 配置极高 (4核 24GB)
3. ✅ 美国 Ashburn 机房延迟极低
4. ✅ 可同时运行 PostgreSQL + 多个策略 + 监控
5. ✅ Ubuntu 22.04 官方支持

如果 Oracle 注册不成功，**备选 RackNerd**（约 6元/月）。

---

## 二、部署步骤（以 Oracle Cloud ARM + Ubuntu 22.04 为例）

### 第1步：创建服务器

1. 注册 Oracle Cloud：https://www.oracle.com/cloud/free/
2. 登录控制台 → Compute → Instances → Create Instance
3. 配置：
   - **Name**: `polymarket-bot`
   - **Image**: Ubuntu 22.04 (Canonical)
   - **Shape**: VM.Standard.A1.Flex（ARM，选 1 OCPU + 6GB RAM 即可）
   - **Region**: US East (Ashburn) ← 推荐，距离 Polymarket 最近
   - **Networking**: 确保分配公网 IP
   - **SSH Key**: 上传你的 SSH 公钥（或让系统生成）
4. 点击 Create，等待实例启动（约2分钟）

### 第2步：连接服务器

```bash
# Windows 使用 PowerShell 或 Git Bash
ssh -i <你的私钥路径> ubuntu@<服务器公网IP>

# 例如
ssh -i ~/.ssh/oracle_key ubuntu@129.146.xxx.xxx
```

> 💡 **Windows 用户推荐工具**：
> - [MobaXterm](https://mobaxterm.mobatek.net/) - 免费 SSH 客户端，支持文件传输
> - [Termius](https://termius.com/) - 跨平台 SSH 客户端
> - Windows Terminal + SSH 命令

### 第3步：服务器初始化

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 3.11+ 和必要工具
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 设置 Python 3.11 为默认
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/python python3 /usr/bin/python3.11 1

# 验证版本
python3 --version  # 应该显示 3.11.x

# 安装 PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 启动 PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 第4步：配置 PostgreSQL

```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 psql 中执行：
CREATE USER sniper_user WITH PASSWORD '你的密码';
CREATE DATABASE poly_market OWNER sniper_user;
GRANT ALL PRIVILEGES ON DATABASE poly_market TO sniper_user;
\q
```

### 第5步：上传项目代码

**方法A：使用 Git（推荐）**
```bash
# 在服务器上
cd ~
git clone <你的仓库地址> polymarket-trading-bot
cd polymarket-trading-bot
```

**方法B：使用 SCP 直接上传**
```powershell
# 在本地 Windows PowerShell 中执行
scp -i <私钥路径> -r D:\production\polymarket-trading-bot ubuntu@<服务器IP>:~/polymarket-trading-bot
```

**方法C：使用 MobaXterm 拖拽上传**
- 打开 MobaXterm → SSH 连接服务器 → 左侧文件面板拖拽上传

### 第6步：配置项目环境

```bash
cd ~/polymarket-trading-bot

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 如果 ARM 架构安装 psycopg2-binary 失败，使用：
sudo apt install -y libpq-dev python3-dev
pip install psycopg2
```

### 第7步：配置环境变量

```bash
# 复制配置模板
cp .env.example .env
cp config.example.yaml config.yaml

# 编辑 .env 文件
nano .env
```

在 `.env` 中填入（与本地相同的值）：
```dotenv
POLY_PRIVATE_KEY=你的私钥
POLY_SAFE_ADDRESS=你的Safe钱包地址
POLY_BUILDER_API_KEY=你的Builder API Key
POLY_BUILDER_API_SECRET=你的Builder API Secret
POLY_BUILDER_API_PASSPHRASE=你的Builder API Passphrase

# 数据库配置（如果需要）
DATABASE_URL=postgresql://sniper_user:你的密码@localhost:5432/poly_market
```

```bash
# 编辑 config.yaml
nano config.yaml
# 填入和本地相同的配置
```

### 第8步：初始化数据库

```bash
cd ~/polymarket-trading-bot
source .venv/bin/activate

# 方法1：使用Python脚本
python scripts/init_database.py

# 方法2：直接使用SQL
sudo -u postgres psql -d poly_market -f db_init.sql
```

### 第9步：测试运行

```bash
cd ~/polymarket-trading-bot
source .venv/bin/activate

# 测试单元测试
pytest tests/ -v

# 测试模拟模式（不真实交易）
python apps/run_rebound.py --coin BTC --size 1

# 确认能连接 Polymarket
python -c "import requests; r=requests.get('https://clob.polymarket.com/time'); print('OK:', r.status_code)"

# 确认能连接 Binance
python -c "import requests; r=requests.get('https://api.binance.com/api/v3/time'); print('OK:', r.status_code)"
```

### 第10步：使用 Linux 启动脚本运行

项目已包含 Linux 版启动脚本（参见 `deploy/` 目录）：

```bash
# 添加执行权限
chmod +x deploy/*.sh

# 启动真实交易（带自动重启）
./deploy/run_rebound_live.sh

# 启动15分钟监控
./deploy/start_monitor.sh

# 启动5分钟监控
./deploy/start_5m_monitor.sh

# 启动全部服务（推荐）
./deploy/start_all.sh
```

### 第11步：设置 systemd 服务（24/7 运行）

使用 systemd 确保机器人在服务器重启后自动运行：

```bash
# 安装服务文件
sudo cp deploy/polymarket-bot.service /etc/systemd/system/
sudo cp deploy/polymarket-monitor.service /etc/systemd/system/

# 编辑服务文件，确认路径和用户名正确
sudo nano /etc/systemd/system/polymarket-bot.service

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable polymarket-bot
sudo systemctl enable polymarket-monitor
sudo systemctl start polymarket-bot
sudo systemctl start polymarket-monitor

# 查看状态
sudo systemctl status polymarket-bot
sudo systemctl status polymarket-monitor

# 查看日志
journalctl -u polymarket-bot -f
journalctl -u polymarket-monitor -f
```

---

## 三、日常运维

### 查看状态
```bash
# 查看服务状态
sudo systemctl status polymarket-bot

# 实时查看日志
journalctl -u polymarket-bot -f

# 查看最近100行日志
journalctl -u polymarket-bot --no-pager -n 100
```

### 重启服务
```bash
sudo systemctl restart polymarket-bot
```

### 停止服务
```bash
sudo systemctl stop polymarket-bot
```

### 更新代码
```bash
cd ~/polymarket-trading-bot
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart polymarket-bot
sudo systemctl restart polymarket-monitor
```

### 数据库备份
```bash
# 备份
pg_dump -U sniper_user poly_market > backup_$(date +%Y%m%d).sql

# 恢复
psql -U sniper_user poly_market < backup_20260225.sql
```

---

## 四、安全加固

### 防火墙配置
```bash
# Oracle Cloud 默认只开放 22 端口
# 如果需要额外端口（如API服务器），在 Oracle Console → Security List 中添加

# 服务器本地防火墙（可选）
sudo ufw enable
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 5432/tcp   # PostgreSQL（仅本地需要，建议不开放外部）
sudo ufw status
```

### SSH 安全
```bash
# 禁止密码登录，只允许密钥登录
sudo nano /etc/ssh/sshd_config
# 设置: PasswordAuthentication no
sudo systemctl restart sshd
```

### 环境变量安全
```bash
# 确保 .env 文件权限正确
chmod 600 .env

# 确保 .env 不会被 git 提交
echo ".env" >> .gitignore
```

---

## 五、性能监控

```bash
# 系统资源使用
htop

# 磁盘空间
df -h

# Python 进程状态
ps aux | grep python

# 网络延迟测试
ping -c 5 clob.polymarket.com
curl -o /dev/null -s -w "Time: %{time_total}s\n" https://clob.polymarket.com/time
```

---

## 六、常见问题

### Q: ARM 架构兼容性问题？
Oracle Cloud ARM 实例使用 aarch64 架构，大部分 Python 包都支持。如遇问题：
```bash
# 安装编译工具
sudo apt install -y build-essential libffi-dev
# 重新安装有问题的包
pip install --no-binary :all: <包名>
```

### Q: PostgreSQL 连接被拒绝？
```bash
# 检查 pg_hba.conf 是否允许本地连接
sudo nano /etc/postgresql/14/main/pg_hba.conf
# 确保有这一行:
# local   all   sniper_user   md5
sudo systemctl restart postgresql
```

### Q: WebSocket 连接断开？
Linux 服务器不需要防待机（keep_awake），但需要处理网络波动。启动脚本已包含自动重启逻辑。

### Q: 时区问题？
```bash
# 设置为UTC（推荐）
sudo timedatectl set-timezone UTC

# 或设置为北京时间
sudo timedatectl set-timezone Asia/Shanghai
```

### Q: 磁盘空间不足？
```bash
# 清理旧的数据文件
find ~/polymarket-trading-bot/files/ -name "*.json" -mtime +30 -delete

# 清理日志
journalctl --vacuum-time=7d
```
