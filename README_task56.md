# 任务56 - 策略3配置检查与反弹趋势记录

## 快速开始

### 1. 检查策略3配置

```bash
python scripts/check_strategy3_config.py
```

这个脚本会检查：
- ✅ 策略类型配置（strategy.type = "3"）
- ✅ 止盈止损配置（take_profit_base, take_profit_reduce_loss, stop_loss_stage_c）
- ✅ 自动claim配置
- ✅ 环境变量配置
- ✅ ReboundConfig 实例化

### 2. 添加数据库字段（首次运行）

```bash
python scripts/add_rebound_trend_column.py
```

这会在 `rebound_orders` 表中添加 `rebound_trend TEXT` 字段。

### 3. 测试反弹趋势记录功能

```bash
python scripts/test_rebound_trend.py
```

验证反弹趋势记录功能正常工作。

### 4. 运行策略3

**模拟模式**（推荐先测试）：
```bash
python apps/run_rebound.py --coin BTC --strategy-type 3
```

**真实交易**：
```bash
python apps/run_rebound.py --coin BTC --strategy-type 3 --live --size 3
```

或使用批处理：
```bash
run_rebound_live.bat
```

## 功能说明

### 反弹趋势记录

策略3在运行时会：

1. **每15秒记录一次**反弹百分比
2. 反弹百分比计算：`(当前价格 - 入场价格) / 入场价格`
3. 记录到内存数组：`[0.10, 0.25, 0.40, 0.50, 0.60, ...]`
4. **平仓时保存**到数据库 `rebound_trend` 字段

### 数据格式

数据库中的 `rebound_trend` 字段示例：

```
"0.10, 0.25, 0.40, 0.50, 0.60, 0.50, 0.40"
```

表示：
- 15秒: 反弹 +10%
- 30秒: 反弹 +25%
- 45秒: 反弹 +40%
- 60秒: 反弹 +50%
- 75秒: 反弹 +60% (峰值)
- 90秒: 反弹 +50% (回落)
- 105秒: 反弹 +40% (继续回落，可能触发止盈)

### 策略3参数

```yaml
profit_and_loss:
  enabled: true
  take_profit_base: 0.8          # 盈利达到 80% 时进入止盈监控
  take_profit_reduce_loss: 0.1   # 从峰值回落 10% 时执行止盈
  stop_loss_stage_c: 0.2         # C段(10-15分钟)亏损超过 20% 时止损
```

## 查看数据

### 数据库查询

```sql
-- 查看最近的反弹趋势记录
SELECT 
    id,
    side,
    entry_price,
    exit_price,
    pnl_percent,
    rebound_trend,
    created_at
FROM rebound_orders
WHERE rebound_trend IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

### 分析反弹趋势

```python
import psycopg2

# 连接数据库
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    database="poly_market",
    user="sniper_user",
    password="sniper_pass_dev"
)

# 查询数据
cur = conn.cursor()
cur.execute("""
    SELECT rebound_trend, pnl_percent 
    FROM rebound_orders 
    WHERE rebound_trend IS NOT NULL
""")

# 分析
for row in cur.fetchall():
    trend_str, pnl = row
    trend = [float(x) for x in trend_str.split(',')]
    
    peak = max(trend)
    final = trend[-1]
    
    print(f"Peak: {peak:.2%}, Final: {final:.2%}, PnL: {pnl:.2%}")
```

## 文件说明

### 新增脚本
- `scripts/check_strategy3_config.py` - 配置检查脚本
- `scripts/test_rebound_trend.py` - 功能测试脚本
- `scripts/add_rebound_trend_column.py` - 数据库字段添加脚本

### 修改文件
- `strategies/rebound.py` - 添加反弹趋势记录功能
- `src/database.py` - 添加 rebound_trend 字段支持

### 文档
- `task56_completion_report.md` - 详细完成报告
- `README_task56.md` - 本文档

## 后续工作

通过收集的反弹趋势数据，可以：

1. **统计分析**：
   - 平均反弹幅度
   - 峰值时间分布
   - 回撤特征

2. **参数优化**：
   - 测试不同的 `take_profit_base` 值（60%, 70%, 80%, 90%）
   - 测试不同的 `take_profit_reduce_loss` 值（5%, 10%, 15%）
   - 找到最佳组合

3. **策略改进**：
   - 基于历史数据预测反弹峰值
   - 动态调整止盈参数
   - 多级止盈策略

## 问题排查

### rebound_trend 字段不存在

运行：
```bash
python scripts/add_rebound_trend_column.py
```

或手动执行：
```sql
ALTER TABLE rebound_orders ADD COLUMN rebound_trend TEXT;
```

### 没有记录趋势数据

检查：
1. 策略类型是否为 "3"
2. 是否有持仓（无持仓不记录）
3. 时间间隔是否达到15秒

### 配置检查失败

运行：
```bash
python scripts/check_strategy3_config.py
```

查看具体错误信息并修复。

## 联系方式

如有问题，请查看：
- `task56_completion_report.md` - 详细技术文档
- `TODO.MD` - 任务56完成说明
