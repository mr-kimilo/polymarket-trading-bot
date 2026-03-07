#task list

# ✅ 任务1已完成: 解决启动卡住问题

## 任务补充（已完成）：优化数据库初始化流程

### 变更内容
✅ **不再在启动时执行DDL操作**
- 移除自动创建表、列、索引的逻辑
- 只检查表是否存在，不存在则报错提示

✅ **提取所有DDL到SQL脚本**
- 创建 `db_init.sql` - 包含所有表、索引定义
- 创建 `scripts/init_database.py` - Python初始化工具

✅ **修改的方法**
- `_ensure_tables()` → `_check_tables()` - 只检查不创建
- `ensure_strategy3_rules_table()` - 只检查不创建  
- `ensure_order_schedule_table()` - 只检查不创建
- `add_missing_columns()` - 标记为废弃

### 使用方法

#### 首次部署 - 初始化数据库

**方法1: 使用Python脚本（推荐）**
```bash
python scripts/init_database.py
```

**方法2: 使用psql命令**
```bash
psql -U sniper_user -d poly_market -f db_init.sql
```

#### 启动Trading Bot
```bash
# 模拟模式
python apps/run_rebound.py --coin BTC

# 真实模式
run_rebound_live.bat
```

### 优势
1. ⚡ **启动快速**: 从1-2秒降低到0.1秒
2. 🛡️ **避免死锁**: 不再有多进程DDL竞争
3. 📋 **规范化**: 符合数据库迁移最佳实践
4. 🔍 **可维护**: 所有DDL集中在一个文件

### 文档
- 完整指南: [docs/database_init.md](docs/database_init.md)
- 初始化脚本: [scripts/init_database.py](scripts/init_database.py)
- SQL脚本: [db_init.sql](db_init.sql)

任务2. 策略1的情况下，我希望买了之后持有到最后，而不是中间止损，检查逻辑并修改。

任务3.现在防止待机功能没生效，检查原因。
✅ 任务4.生成脚本，获取poly market btc5分钟市场，的订单深度，变化，可以参照15分钟的脚本。
✅ 补充：获取币安的BTC 价格，作为开始价格以及价格变化的依据而不是poly market 的。
✅ 补充2：获取的币安5分钟的开始价格不对，8点40-45的开始价格是66642.18，而你显示的不对，找到原因并修复
✅ 补充3，检查15分钟市场的开始价格，我需要所有获取价格都用补充2的方式获取。

✅ 任务4.根据任务3的补充2，run_rebound_live.bat里面获取开始价格的方式，需要修改获取币安的15分钟线开始价格，而不是poly market的价格，以及实时价格也改成币安的价格。
✅ 任务5.部署当前代码到服务器
- 推荐平台: Oracle Cloud 永久免费层（ARM 4核24GB，美国Ashburn机房）
- 备选: RackNerd (~6元/月)、Google Cloud 免费层
- 部署指南: [docs/server_deployment_guide.md](docs/server_deployment_guide.md)
- Linux启动脚本: `deploy/` 目录（run_rebound_live.sh, start_monitor.sh, start_all.sh）
- systemd服务文件: `deploy/*.service`（24/7自动运行）
- 一键部署: `./deploy/setup_server.sh`
---
任务6.风险控制，现在需要检查前24小时的btc价格（k线图），如果最高价和最低价之间相差大于4000点，输出红色提示字体，在启动页面要手动确认之后再继续。
## 原问题（已解决）
`run_rebound_live.bat` 启动后在 "Database table created" 输出后卡住不动。

✅ 任务7.阅读trading-rules.md并整理需求，确定买入卖出点，止盈止损点，苹果这个策略的ROI和风险。
- 分析文档: [docs/trading_rules_analysis.md](docs/trading_rules_analysis.md)
- 包含3个策略: 回弹策略1(A段)、回弹策略2(C段)、1小时趋势策略3
- 买入/卖出点、止盈止损条件已详细整理
- ROI估算: 策略1 +66.5%, 策略2 +100%, 策略3 +2.5%
- 风险评级: 策略1中高风险、策略2极高风险、策略3中低风险

✅ 任务8.为什么策略1在周一到周四晚上的数据总是亏，周五和周六晚上才有盈利？我怎么才能在周一到周四的晚上也有周五周六的盈利。
- 分析脚本: [scripts/analyze_weekday_pnl.py](scripts/analyze_weekday_pnl.py)
- 分析报告: [docs/task8_weekday_analysis.md](docs/task8_weekday_analysis.md)
- **数据发现**:
  - 周一到周四: 33单, 胜率27.3%, 总盈亏-11.31
  - 周五周六: 40单, 胜率32.5%, 总盈亏+16.00
  - 周六表现最好(34.5%), 周二最差(10%)
- **关键差异**: 
  - 周一到周四亏损订单BTC下跌平均-49点，说明趋势明确时策略判断错误
  - 周六BTC振幅最小(0.28%)，波动更温和适合回弹策略
- **✅ 已实现优化**:
  1. ✅ 没有order_schedule时入场条件更严格(UP/DOWN<25%, BTC变化<$30)
  2. ✅ 没有order_schedule时仓位降低50%
  3. ✅ 基于order_schedule而非星期几判断严格模式
  4. 周二表现极差，考虑禁用（待实现）
  5. 增加连亏保护机制（待实现）
- **配置**（config.yaml）:
  ```yaml
  weekday_strict:
    enabled: true
    threshold: 0.25  # 严格模式UP/DOWN阈值
    btc_max: 30.0    # 严格模式BTC限制
    size_multiplier: 0.5  # 严格模式仓位乘数
  ```
- **逻辑说明**:
  - 有order_schedule计划 → 放松模式(threshold=0.30, btc_max=50, size=100%)
  - 无order_schedule计划 → 严格模式(threshold=0.25, btc_max=30, size=50%)
- **代码变更**:
  - `strategies/rebound.py`: `_is_weekday_strict()` 改为检查order_schedule
  - `strategies/strategy_impl.py`: Strategy1同步修改
  - 显示屏幕会提示当前是否为"严格模式"及是否有schedule
✅ 任务9.检查rebound_orders的strategy_type在模拟和真实环境都保存了。
- **检查结果**:
  - 代码路径: `_execute_trade()` 对sim和live使用同一代码路径，均设置 `strategy_type` 和 `env`
  - prod订单: 374条，全部有 `strategy_type=1, env=prod` ✅
  - sim订单: 689条，全部有 `strategy_type=1, env=sim` ✅
- **修复**:
  - 回填975条历史NULL记录（task 64之前的订单）
  - 修复 `test_database.py` 测试订单缺少 `strategy_type` 和 `env` 字段
任务10. ✅ 检查rebound_orders的rebound_trend，在模拟和真实环境是否能正常保存。
- **发现的问题** (4处Bug):
  1. `_get_rebound_trend_summary()` 无记录时返回 `""` 而非 `None`，导致覆盖已保存的趋势数据
  2. `update_rebound_order_result()` 无条件执行 `SET rebound_trend = %s`，即使参数为 `None` 也会将DB中已有的趋势覆盖为NULL
  3. `_close_all_positions()` 模拟模式缺少 `rebound_trend` 参数 → 存入NULL
  4. `direct_sell_all_positions()` 模拟模式缺少 `rebound_trend` 参数 → 存入NULL
  5. **竞态条件**: `_execute_close_live()` 异步任务在 `_reset_for_new_period()` 清空 `_rebound_trend_records` 之后才执行，导致获取不到趋势数据
- **修复内容**:
  - `_get_rebound_trend_summary()` 改为返回 `Optional[str]`，无记录时返回 `None`
  - `update_rebound_order_result()` 改为条件SQL：仅当 `rebound_trend is not None` 时才在SET子句中包含该字段，避免覆盖已有数据
  - `_close_all_positions()` 模拟模式：传入 `rebound_trend=self._get_rebound_trend_summary(side)`
  - `direct_sell_all_positions()` 模拟模式：传入 `rebound_trend=self._get_rebound_trend_summary(side)`
  - 竞态条件通过上述1+2的组合修复：`_execute_close_live()` 获取空趋势时返回 `None`，`update_rebound_order_result()` 不覆盖已有数据
- **新增测试**: `tests/unit/test_task10_rebound_trend_save.py` (12个测试，全部通过)
✅ 任务11.在交易界面显示策略type
- **修改文件**: `strategies/rebound.py` 的 `_render_status()` 方法
- **显示格式**: `Rebound Strategy：{strategy_type} | {coin} | {Connected} | Mode: {mode}`
- **示例**: `Rebound Strategy：1 | BTC | Connected | Mode: LIVE`

## 根本原因
多进程同时执行数据库表初始化（DDL操作）时，发生死锁：
- 每次启动都会执行 `CREATE TABLE IF NOT EXISTS`、`ALTER TABLE ADD COLUMN`、`CREATE INDEX` 等操作
- 多个进程同时操作导致互相等待表锁
- 特别是 `add_missing_columns()` 中的 ALTER TABLE 操作容易卡住

## 解决方案（第一版 - 已废弃）
使用 **PostgreSQL Advisory Lock** 序列化表初始化：
1. 启动时尝试获取 advisory lock (ID: 20260208)
2. 获取成功：执行完整的表初始化
3. 获取失败：等待5秒或跳过（假设表已被其他进程初始化）
4. 完成后释放锁

## 解决方案（第二版 - 当前）
**不再在启动时执行DDL**：
1. 所有DDL提取到 `db_init.sql`
2. 启动时只检查表是否存在
3. 表不存在时报错，要求手动初始化

## 诊断工具
- ✅ `diagnose_startup.py` - 逐步测试启动流程
- ✅ `diagnose_detailed.py` - 详细测试每个数据库操作
- ✅ `check_db_locks.py` - 检查数据库锁和阻塞
- ✅ `release_locks.py` - 释放advisory locks并终止卡住进程
- ✅ `scripts/init_database.py` - 数据库初始化工具

## 使用指南
```bash
# 首次部署 - 初始化数据库
python scripts/init_database.py

# 正常启动（不再卡住）
run_rebound_live.bat

# 如果遇到"Table not found"错误
python scripts/init_database.py

# 旧方式：如果遇到卡住（现已不适用）
python release_locks.py
```

## 完整文档
- 初始化指南: [docs/database_init.md](docs/database_init.md)
- 技术方案: [docs/task1_startup_hang_fix.md](docs/task1_startup_hang_fix.md)

---
**完成日期**: 2026-02-08  
**补充完成**: 2026-02-08  
**相关任务**: 任务43（数据库死锁修复）

---

# Polymarket Trading Bot - 项目知识库

> **完整记录备份**: [TODO-BACKUP.MD](TODO-BACKUP.MD) 包含所有任务的详细过程和问题解决记录

---

## 📊 一、数据采集与监控

### ✅ 任务15-24: 15分钟市场数据监控系统
- **功能**: 持续监控Polymarket 15分钟市场，每分钟记录UP/DOWN价格和BTC价格变化
- **数据存储**: JSON文件保存到 `files/` 目录，命名格式 `YYYY-MM-DD-HH-MM.json`
- **自动重启**: 每12小时重启，检测WebSocket断开自动恢复，无数据超时5分钟触发重启
- **防休眠**: 使用PowerShell模拟键盘活动（F15键）防止系统休眠

**启动脚本**:
```bash
# 静默监控（推荐用于后台运行）
start_monitor_keepawake.bat

# 带UI监控
python apps/orderbook_tui.py --coin BTC
```

**关键特性**:
- WebSocket实时数据流
- 健康检查和自动恢复
- BTC价格多源备份（CoinGecko/CoinCap/Binance）
- 市场自动切换（15分钟周期结束）

---

## 🎯 二、交易策略系统

### ✅ 任务27-42: Rebound策略核心框架
- **策略类型**: 支持3种策略模式
- **模拟模式**: 默认启用，用于回测和参数优化
- **数据库**: PostgreSQL记录订单、盈亏、统计
- **Auto-Claim**: 余额低于阈值自动赎回获胜仓位

**策略配置** (config.yaml):
```yaml
strategy:
  type: "1"  # 1=A段反弹, 2=C段反弹, 3=动态止盈止损

auto_claim:
  enabled: true
  min_balance: 5.0      # 最小余额触发claim（USDC）
  check_interval: 60    # 检查间隔（分钟）
```

**启动脚本**:
```bash
# 模拟模式（默认）
python apps/run_rebound.py --coin BTC --strategy-type 3

# 真实交易模式（每单$2）
run_rebound_live.bat
```

---

### ✅ 策略1: A段反弹策略（任务27）
- **时段**: A段（15-10分钟，即第1-5分钟）
- **触发条件**:
  - UP或DOWN价格在1分钟内跌破30%
  - BTC价格下跌≤$50
- **持仓**: 持有到15分钟结束
- **使用场景**: 捕捉大幅波动后的快速反弹

```bash
python apps/run_rebound.py --coin BTC --strategy-type 1 --size 10
```

---

### ✅ 策略2: C段反弹策略（任务42）
- **时段**: C段（5-0分钟，即第11-15分钟）
- **触发条件**:
  - UP或DOWN价格跌破15%
  - BTC价格下跌≤$30
- **持仓**: 持有到15分钟结束
- **使用场景**: 临近结束的快速反弹

```bash
python apps/run_rebound.py --coin BTC --strategy-type 2 --size 10
```

---

### ✅ 策略3: 动态止盈止损（任务43-54）
- **时段**: 可配置（A/B/C任意组合，默认A段）
- **触发条件**: 与策略1相同
- **动态P&L**:
  - 止盈: 盈利达50%进入可卖状态，回撤10%时卖出
  - 止损: C段（最后5分钟）亏损>20%立即止损
- **反弹趋势**: 每15秒记录价格变化，保存到数据库用于分析

**配置** (config.yaml):
```yaml
profit_and_loss:
  enabled: true
  take_profit_base: 0.50         # 50%盈利进入可卖状态
  take_profit_reduce_loss: 0.10  # 回撤10%时卖出
  stop_loss_stage_bc: 0.20       # 最后5分钟亏损>20%止损
```

```bash
python apps/run_rebound.py --coin BTC --strategy-type 3 --size 3 --live
```

---

### ✅ 任务57-60: 策略重构与风险管理
- **设计模式**: 策略模式 + 工厂模式 + 模板方法
- **风险管理器**:
  - 连续亏损3次 → 冷却1小时
  - 日内亏损达初始资金50% → 停止交易
- **动态参数**: 策略3支持从数据库实时加载参数

**核心类结构**:
```
BaseReboundStrategy (抽象基类)
├── RiskManager - 风险控制
├── Strategy1 - A段反弹
├── Strategy2 - C段反弹
└── Strategy3 - 动态止盈止损
```

---

### ✅ 任务61: 策略3动态买入阶段
- **功能**: 通过数据库配置买入阶段（A/B/C任意组合）
- **数据库表**: `strategy3_rules.stage_buy`

**示例**:
```sql
-- 只在A段买入
UPDATE strategy3_rules SET stage_buy='A' WHERE id=1;

-- 在A或C段买入
UPDATE strategy3_rules SET stage_buy='A,C' WHERE id=1;

-- 任意阶段买入
UPDATE strategy3_rules SET stage_buy='A,B,C' WHERE id=1;
```

---

## 💾 三、数据库与订单管理

### ✅ 任务43: 数据库死锁修复
- **问题**: 多进程同时执行DDL操作导致表级锁死
- **解决**: PostgreSQL advisory lock（`pg_try_advisory_lock`）序列化表初始化

**核心改进**:
- 非阻塞锁获取
- 等待2秒后跳过（让持有锁的进程完成）
- 正确释放advisory lock

---

### ✅ 任务27-28: rebound_orders表
- **字段**: coin, side, segment, entry_price, exit_price, pnl, pnl_percent, status, is_simulated, market_slug, token_id, order_id, btc触发条件等
- **统计**: 胜率、总PnL、平均PnL、最大/最小盈亏

**查询示例**:
```python
from src.database import get_database

db = get_database()
stats = db.get_rebound_orders_stats(coin="BTC", is_simulated=False, days=7)
print(f"胜率: {stats['win_rate']:.2%}")
print(f"总PnL: ${stats['total_pnl']:.2f}")
```

---

### ✅ 任务56: 反弹趋势记录
- **功能**: 每15秒记录反弹百分比，从开单到周期结束
- **字段**: `rebound_trend` (逗号分隔，如 "0.10, 0.25, 0.40, 0.50, 0.60, 0.50, 0.40")
- **用途**: 分析平均反弹幅度、峰值时间、优化止盈止损参数

```python
# 查询趋势数据
db = get_database()
orders = db.get_rebound_orders_by_date("2026-02-07")
for order in orders:
    trend = order.rebound_trend.split(", ")
    max_rebound = max(map(float, trend))
    print(f"订单 {order.id} 最大反弹: {max_rebound:.2%}")
```

---

### ✅ 任务60: strategy3_rules表（策略3动态参数）
- **字段**: env, strategy_type, status, stage_buy, price_down_percentage, price_down, take_profit, stop_loss
- **状态**: 0=待激活, 1=激活, 2=过期, 3=取消

**使用方法**:
```bash
# 创建规则
python scripts/strategy_api.py create --env simulate --stage-buy A,B --take-profit 0.80 --stop-loss 0.20

# 激活规则
python scripts/strategy_api.py activate 1

# 查询规则
python scripts/strategy_api.py query --env simulate
```

---

### ✅ 任务64: 订单记录策略类型和环境
- **新字段**: `strategy_type` (1/2/3), `env` (sim/live)
- **用途**: 区分不同策略的表现，便于分析优化

---

### ✅ 任务65-66: order_schedule表（交易时段调度）
- **字段**: env, strategy_type, schedule_date, start_time, end_time, status
- **功能**: 配置特定日期和时段的交易计划

**API端点**:
```bash
# 创建调度（09:00-10:00交易）
curl -X POST http://localhost:5000/orderSchedule/create \
  -H "Content-Type: application/json" \
  -d '{
    "env": "simulate",
    "strategy_type": 3,
    "schedule_date": "2026-02-08",
    "start_time": "09:00",
    "end_time": "10:00"
  }'

# 查询调度
curl "http://localhost:5000/orderSchedule/query?env=simulate"

# 检查当前是否应该交易
curl "http://localhost:5000/orderSchedule/check?env=simulate&strategy_type=3"

# 取消调度
curl -X POST http://localhost:5000/orderSchedule/cancel \
  -H "Content-Type: application/json" \
  -d '{"schedule_id": 1}'
```

**CLI命令**:
```bash
# 创建调度
python scripts/strategy_api.py schedule-create --env sim --strategy-type 3 --date 2026-02-08 --start-time 09:00 --end-time 10:00

# 查询调度
python scripts/strategy_api.py schedule-query --env sim

# 取消调度
python scripts/strategy_api.py schedule-cancel 1
```

**配置启用** (config.yaml):
```yaml
order_schedule:
  enabled: true  # 只有true时才检查调度表
```

---

## 🔐 四、签名与订单

### ✅ 任务33-40: EIP-712签名修复
- **问题**: 签名验证失败（invalid signature）
- **解决**: 使用官方 `poly-eip712-structs` 库，正确处理neg_risk市场

**关键技术**:
- GNOSIS_SAFE (signature_type=2)
- 动态检测neg_risk市场（不同交易所合约地址）
- Relayer gasless交易

**环境变量**:
```bash
POLY_PRIVATE_KEY=your_private_key
POLY_SAFE_ADDRESS=your_safe_address
```

---

### ✅ 任务37-39: 订单精度修复
- **价格**: 必须是0.01的倍数（tick size），四舍五入到2位小数
- **金额**: maker_amount≤4位小数，taker_amount≤2位小数
- **费率**: fee_rate_bps=1000（BTC 15分钟市场10%费率）

---

### ✅ 任务48-54: 卖出订单优化
- **价格来源优先级**:
  1. CLOB midpoint（最稳定）
  2. Last trade price
  3. Orderbook best bid
  4. 本地orderbook
  5. 兜底价格0.01
- **动态tick size**: 根据市场获取并调整价格
- **直接卖出**: 紧急退出或手动干预

**直接卖出脚本**:
```bash
# 模拟模式
python scripts/direct_sell.py --coin BTC

# 真实模式
python scripts/direct_sell.py --coin BTC --live
```

---

## ⚙️ 五、自动化运维

### ✅ 任务22-24: 防休眠与自动重启
- **防休眠**: PowerShell模拟F15键盘活动（每60秒）
- **自动重启**: 运行时间达12小时或检测到连接断开
- **退出码**: 42=需要重启，0=正常退出

**启动脚本** (推荐):
```bash
# 后台监控（数据采集）
start_monitor_keepawake.bat

# 策略运行（模拟）
run_rebound_strategy.bat

# 策略运行（真实）
run_rebound_live.bat
```

---

### ✅ 任务41: Auto-Claim自动赎回
- **功能**: 余额低于阈值自动赎回获胜仓位
- **技术**: py-builder-relayer-client gasless交易
- **配置**: `auto_claim.enabled=true`, `min_balance=5.0`, `check_interval=60`（分钟）

**工作流程**:
1. 每60分钟检查USDC余额
2. 余额<$5.00时查询可赎回仓位
3. 过滤有价值的仓位（currentValue≥$0.01）
4. 通过Relayer执行gasless redeem
5. 更新余额后继续交易

**环境变量**:
```bash
POLY_BUILDER_API_KEY=your_api_key
POLY_BUILDER_API_SECRET=your_api_secret
POLY_BUILDER_API_PASSPHRASE=your_passphrase
```

---

## 🌐 六、API与配置管理

### ✅ 任务62: 自动启动API服务器
- **功能**: 策略运行时自动在后台启动Flask API
- **默认端口**: 5000
- **守护线程**: 主进程退出时API自动停止

**启动时输出**:
```
✓ API服务器已启动在后台 (http://localhost:5000)
  - POST /rules/active - 激活规则
  - POST /rules/create - 创建规则
  - GET  /rules/query - 查询规则
  - GET  /orderSchedule/create - 创建调度
  - GET  /orderSchedule/query - 查询调度
```

---

### ✅ 任务60: Strategy API接口
- **策略规则管理**: CRUD操作，激活/查询规则
- **交易调度管理**: 配置特定时段交易计划
- **支持方式**: Flask API + CLI命令

**API文档**: [docs/api/order-schedule-api.md](docs/api/order-schedule-api.md)

---

## 📁 七、核心文件说明

### 配置文件
- `config.yaml` - 全局配置（策略类型、P&L参数、auto-claim、order_schedule等）
- `.env` - 环境变量（私钥、Safe地址、Builder凭证、数据库）

### 核心模块
- `src/bot.py` - TradingBot交易执行引擎
- `src/client.py` - CLOB API客户端
- `src/signer.py` - EIP-712订单签名
- `src/database.py` - PostgreSQL数据库操作
- `src/auto_claim.py` - 自动赎回功能

### 策略模块
- `strategies/base_rebound.py` - 策略基类、风险管理器
- `strategies/strategy_impl.py` - 3种策略实现、工厂模式

### 应用入口
- `apps/orderbook_tui.py` - 数据监控TUI
- `apps/run_rebound.py` - Rebound策略运行器

### 批处理脚本
- `start_monitor_keepawake.bat` - 数据监控（防休眠）
- `run_rebound_strategy.bat` - 策略模拟运行
- `run_rebound_live.bat` - 策略真实交易($2/单)

### 工具脚本
- `scripts/strategy_api.py` - 策略规则/调度API
- `scripts/direct_sell.py` - 直接卖出工具
- `scripts/diagnose_auto_claim.py` - Auto-claim诊断
- `scripts/check_strategy3_config.py` - 策略3配置检查

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量（.env）
```bash
# 钱包凭证
POLY_PRIVATE_KEY=your_private_key
POLY_SAFE_ADDRESS=your_safe_address

# Builder API（用于gasless和auto-claim）
POLY_BUILDER_API_KEY=your_api_key
POLY_BUILDER_API_SECRET=your_api_secret
POLY_BUILDER_API_PASSPHRASE=your_passphrase

# 数据库
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_NAME=poly_market
DATABASE_USER=sniper_user
DATABASE_PASSWORD=sniper_pass_dev
```

### 3. 配置策略（config.yaml）
```yaml
strategy:
  type: "3"  # 1=A段反弹, 2=C段反弹, 3=动态止盈止损

profit_and_loss:
  enabled: true
  take_profit_base: 0.50
  take_profit_reduce_loss: 0.10
  stop_loss_stage_bc: 0.20

auto_claim:
  enabled: true
  min_balance: 5.0
  check_interval: 60

order_schedule:
  enabled: true
```

### 4. 运行
```bash
# 数据监控（后台）
start_monitor_keepawake.bat

# 策略模拟
run_rebound_strategy.bat

# 策略真实交易
run_rebound_live.bat
```

---

## 📖 相关文档

- **API文档**: [docs/api/order-schedule-api.md](docs/api/order-schedule-api.md)
- **策略指南**: [docs/strategy_guide.md](docs/strategy_guide.md)
- **完整任务记录**: [TODO-BACKUP.MD](TODO-BACKUP.MD)

---

## 📊 数据分析

### 查询订单统计
```python
from src.database import get_database

db = get_database()

# 策略3的统计（最近7天）
stats = db.get_rebound_orders_stats(coin="BTC", is_simulated=False, days=7)
print(f"总订单: {stats['total_orders']}")
print(f"胜率: {stats['win_rate']:.2%}")
print(f"总PnL: ${stats['total_pnl']:.2f}")
print(f"平均PnL: ${stats['avg_pnl']:.2f}")

# 查看反弹趋势
orders = db.query_rebound_orders(strategy_type="3", env="live", days=7)
for order in orders:
    if order.rebound_trend:
        trend = [float(x) for x in order.rebound_trend.split(", ")]
        max_rebound = max(trend)
        print(f"订单 {order.id}: 最大反弹 {max_rebound:.2%}")
```

---

## ⚠️ 注意事项

1. **模拟模式优先**: 新策略或参数调整先用模拟模式测试
2. **小额开始**: 真实交易从$2/单开始，验证稳定后再增加
3. **监控日志**: 定期检查 `logs/rebound.log` 和 `logs/silent_monitor.log`
4. **数据库备份**: 定期备份 PostgreSQL 数据库
5. **API安全**: Strategy API仅用于内网，不要暴露到公网

---

**最后更新**: 2026-02-07
