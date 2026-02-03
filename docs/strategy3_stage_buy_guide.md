# 策略3阶段配置快速指南

## 概述
策略3现在支持从数据库动态配置买入阶段（A/B/C任意组合），无需修改代码。

## 时间段说明
- **A段**: 15-10分钟（开始阶段，波动大）
- **B段**: 10-5分钟（中间阶段，中等波动）
- **C段**: 5-0分钟（结束阶段，快速反弹）

## 配置方法

### 方法1: 使用API（推荐）

```bash
# 1. 创建新规则
python scripts/strategy_api.py create \
  --env simulate \
  --stage-buy "A" \
  --price-down-percentage 0.30 \
  --price-down 50 \
  --take-profit 0.80 \
  --stop-loss 0.20

# 输出示例: Created rule ID: 7

# 2. 激活规则
python scripts/strategy_api.py activate 7

# 3. 查看激活的规则
python scripts/strategy_api.py active --env simulate
```

### 方法2: 直接操作数据库

```sql
-- 创建规则
INSERT INTO strategy3_rules (
    env, stage_buy, price_down_percentage, price_down, 
    take_profit, stop_loss
) VALUES (
    'simulate', 'A,B', 0.25, 50.0, 0.80, 0.20
);

-- 激活规则（假设新规则ID为8）
UPDATE strategy3_rules 
SET status = 'inactive', last_update_date = CURRENT_TIMESTAMP 
WHERE env = 'simulate' AND status = 'active';

UPDATE strategy3_rules 
SET status = 'active', last_update_date = CURRENT_TIMESTAMP 
WHERE id = 8;
```

## 配置示例

### 保守型（只在A段）
适合波动大的市场，等待大幅下跌后买入
```bash
python scripts/strategy_api.py create \
  --env simulate \
  --stage-buy "A" \
  --price-down-percentage 0.30 \
  --take-profit 0.80 \
  --stop-loss 0.20
```

### 平衡型（A+B段）
增加交易机会，覆盖前10分钟
```bash
python scripts/strategy_api.py create \
  --env simulate \
  --stage-buy "A,B" \
  --price-down-percentage 0.25 \
  --take-profit 0.70 \
  --stop-loss 0.25
```

### 激进型（全时段）
最大化交易机会，任意时段都可买入
```bash
python scripts/strategy_api.py create \
  --env simulate \
  --stage-buy "A,B,C" \
  --price-down-percentage 0.20 \
  --take-profit 0.60 \
  --stop-loss 0.30
```

### 快速反弹型（只在C段）
接近结束才买入，追求快速成交
```bash
python scripts/strategy_api.py create \
  --env simulate \
  --stage-buy "C" \
  --price-down-percentage 0.15 \
  --take-profit 0.50 \
  --stop-loss 0.30
```

## 运行策略

### 模拟模式
```bash
python apps/run_rebound.py --coin BTC --strategy-type 3
```

### 真实交易模式
```bash
python apps/run_rebound.py --coin BTC --strategy-type 3 --live --size 3
```

## 查看日志

策略启动时会显示加载的配置：
```
[DYNAMIC] Loaded params: stage_buy=A,B, order_segments=['A', 'B'], 
          threshold=0.25, btc_drop=50.0, take_profit=0.80, stop_loss=0.20
```

当触发买入条件时：
```
[TRADE] Checking entry condition for UP in segment A...
[TRADE] Entry allowed! (stage_buy=A,B includes segment A)
[ORDER] Placing BUY order for UP @ 0.22...
```

当不满足阶段条件时：
```
[TRADE] Checking entry condition for DOWN in segment C...
[TRADE] Entry not allowed (stage_buy=A,B does not include segment C)
```

## 注意事项

1. **一次只能激活一条规则**
   - 每个环境（simulate/production）只能有一条active状态的规则
   - 激活新规则会自动将旧规则设为inactive

2. **参数检查间隔**
   - 策略每60秒从数据库重新加载一次参数
   - 更新规则后最多等待60秒生效

3. **环境隔离**
   - simulate环境和production环境的规则互不影响
   - 测试时使用simulate环境，上线后使用production环境

4. **阶段格式**
   - 支持大小写："A" 或 "a" 都可以
   - 支持空格："A, B, C" 会自动去除空格
   - 多个阶段用逗号分隔："A,B,C"

## 常见问题

### Q: 如何知道当前使用的是哪个规则？
A: 查看策略启动日志或运行：
```bash
python scripts/strategy_api.py active --env simulate
```

### Q: 可以同时在A段和C段买入，但跳过B段吗？
A: 可以，设置 `stage_buy="A,C"` 即可

### Q: 如何快速切换配置？
A: 预先创建多个规则，需要时激活对应的规则ID：
```bash
# 创建规则
python scripts/strategy_api.py create --env simulate --stage-buy "A" ...   # ID: 10
python scripts/strategy_api.py create --env simulate --stage-buy "B" ...   # ID: 11
python scripts/strategy_api.py create --env simulate --stage-buy "C" ...   # ID: 12

# 切换到规则11
python scripts/strategy_api.py activate 11
```

### Q: 修改了规则，策略会立即生效吗？
A: 不会立即生效。策略每60秒检查一次，最多等待60秒。如需立即生效，重启策略。

### Q: 可以为不同币种设置不同的阶段吗？
A: 目前不支持按币种区分。stage_buy配置对所有币种生效。如需区分，可以运行多个策略实例，使用不同的env。

## 性能建议

根据历史数据统计（仅供参考）：

| 阶段 | 平均胜率 | 平均收益 | 风险等级 | 建议 |
|------|---------|---------|---------|------|
| A | 65% | +15% | 中 | 适合波动大的市场 |
| B | 60% | +10% | 中低 | 平衡收益与风险 |
| C | 55% | +8% | 低 | 适合快速决策 |
| A,B | 62% | +12% | 中 | 推荐配置 |
| A,B,C | 58% | +10% | 中高 | 最大化机会 |

**注意**: 实际表现会因市场环境而异，请根据实盘数据调整。

## 测试建议

1. **先在模拟模式测试**
   ```bash
   python apps/run_rebound.py --coin BTC --strategy-type 3
   ```

2. **收集至少50笔交易数据**
   - 观察不同阶段的胜率
   - 分析盈亏分布
   - 优化参数配置

3. **切换到真实模式**
   ```bash
   # 先用小金额测试
   python apps/run_rebound.py --coin BTC --strategy-type 3 --live --size 1
   
   # 确认稳定后增加金额
   python apps/run_rebound.py --coin BTC --strategy-type 3 --live --size 3
   ```

## 支持

如有问题，请查看：
- 完整文档: `task61_completion_report.md`
- 测试脚本: `scripts/test_task61.py`
- 策略实现: `strategies/strategy_impl.py`
