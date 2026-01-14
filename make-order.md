# Polymarket BTC 15分钟交易指南

## 📋 目录

- [下单逻辑概述](#下单逻辑概述)
- [止盈止损逻辑](#止盈止损逻辑)
- [配置参数说明](#配置参数说明)
- [运行交易策略](#运行交易策略)
- [手动下单示例](#手动下单示例)

---

## 下单逻辑概述

### 核心组件架构

```
TradingBot (src/bot.py)
    ├── OrderSigner      - 订单签名
    ├── ClobClient       - CLOB API 客户端
    └── RelayerClient    - 无Gas交易中继器

BaseStrategy (strategies/base.py)
    ├── MarketManager    - 市场管理和WebSocket
    ├── PriceTracker     - 价格追踪
    └── PositionManager  - 仓位和止盈止损管理

FlashCrashStrategy (strategies/flash_crash.py)
    └── 继承 BaseStrategy，实现闪崩交易逻辑
```

### 下单流程

1. **市场发现**: `MarketManager` 自动发现当前15分钟市场
2. **价格监控**: 通过WebSocket实时接收orderbook数据
3. **信号触发**: 策略检测到买入/卖出信号
4. **订单创建**: 
   ```python
   order = Order(
       token_id=token_id,      # 市场token ID (UP或DOWN)
       price=price,            # 价格 (0-1之间)
       size=size,              # 数量
       side="BUY" | "SELL",    # 买入或卖出
       maker=safe_address,     # 你的Safe钱包地址
       fee_rate_bps=0,         # 手续费率 (基点)
   )
   ```
5. **订单签名**: `OrderSigner` 使用私钥签名订单
6. **提交订单**: 通过CLOB API或Relayer提交
7. **结果返回**: `OrderResult` 包含订单状态

### 关键代码位置

| 功能 | 文件 | 方法 |
|------|------|------|
| 下单 | `src/bot.py` | `place_order()` |
| 批量下单 | `src/bot.py` | `place_orders()` |
| 取消订单 | `src/bot.py` | `cancel_order()` |
| 执行买入 | `strategies/base.py` | `execute_buy()` |
| 执行卖出 | `strategies/base.py` | `execute_sell()` |

---

## 止盈止损逻辑

### 止盈止损计算方式

止盈止损基于**绝对价格变化（美元）**，而非百分比：

```python
# Position类中的计算逻辑 (lib/position_manager.py)

# 止盈价格 = 入场价格 + 止盈阈值
take_profit_price = entry_price + take_profit_delta  # 如: 0.35 + 0.10 = 0.45

# 止损价格 = 入场价格 - 止损阈值  
stop_loss_price = entry_price - stop_loss_delta      # 如: 0.35 - 0.05 = 0.30
```

### 触发条件

```python
# 止盈检查
if current_price >= take_profit_price:
    # 触发止盈，卖出获利

# 止损检查  
if current_price <= stop_loss_price:
    # 触发止损，卖出止损
```

### PnL (盈亏) 计算

```python
# 未实现盈亏
pnl = (current_price - entry_price) * size

# 示例：
# 入场价: 0.35, 当前价: 0.45, 数量: 100
# PnL = (0.45 - 0.35) * 100 = $10.00
```

### 止盈止损流程

```
主循环 (BaseStrategy.run())
    │
    ├── 每tick调用 _check_exits()
    │       │
    │       └── PositionManager.check_all_exits()
    │               │
    │               ├── 检查每个仓位的 take_profit / stop_loss
    │               │
    │               └── 返回需要退出的仓位列表
    │
    └── 对需要退出的仓位执行 execute_sell()
```

---

## 配置参数说明

### 策略配置 (StrategyConfig)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `coin` | `"ETH"` | 交易币种: BTC, ETH, SOL, XRP |
| `size` | `5.0` | 每笔交易金额 (USDC) |
| `max_positions` | `1` | 最大同时持仓数 |
| `take_profit` | `0.10` | 止盈阈值 (美元) |
| `stop_loss` | `0.05` | 止损阈值 (美元) |

### Flash Crash策略专用配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `drop_threshold` | `0.30` | 闪崩触发阈值 (概率绝对变化) |
| `price_lookback_seconds` | `10` | 价格回溯时间窗口 (秒) |

### 推荐配置组合

#### 保守配置（适合新手）
```bash
--size 5.0 --take-profit 0.05 --stop-loss 0.03 --drop 0.35
```
- 小金额，低风险
- 止盈 5 cents, 止损 3 cents
- 需要较大闪崩才触发

#### 标准配置
```bash
--size 10.0 --take-profit 0.10 --stop-loss 0.05 --drop 0.30
```
- 中等金额
- 止盈 10 cents, 止损 5 cents
- 风险收益比 2:1

#### 激进配置
```bash
--size 20.0 --take-profit 0.15 --stop-loss 0.08 --drop 0.25
```
- 较大金额
- 止盈 15 cents, 止损 8 cents
- 更敏感的触发阈值

---

## 运行交易策略

### 环境准备

1. **配置环境变量** (`.env`文件):
   ```bash
   POLY_PRIVATE_KEY=0x你的私钥
   POLY_SAFE_ADDRESS=0x你的Safe钱包地址
   ```

2. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

### 运行Flash Crash策略

```bash
# 基本运行
python apps/run_flash_crash.py --coin BTC

# 完整参数
python apps/run_flash_crash.py \
    --coin BTC \
    --size 10.0 \
    --drop 0.30 \
    --lookback 10 \
    --take-profit 0.10 \
    --stop-loss 0.05

# 调试模式
python apps/run_flash_crash.py --coin BTC --debug
```

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--coin` | 字符串 | ETH | 交易币种 |
| `--size` | 浮点数 | 5.0 | 交易金额 (USDC) |
| `--drop` | 浮点数 | 0.30 | 闪崩触发阈值 |
| `--lookback` | 整数 | 10 | 回溯窗口 (秒) |
| `--take-profit` | 浮点数 | 0.10 | 止盈 (美元) |
| `--stop-loss` | 浮点数 | 0.05 | 止损 (美元) |
| `--debug` | 标志 | - | 启用调试日志 |

---

## 手动下单示例

### Python代码示例

```python
import asyncio
from src.bot import TradingBot
from src.config import Config

async def manual_trade():
    # 初始化Bot
    config = Config.from_env()
    bot = TradingBot(
        config=config,
        private_key="0x你的私钥"
    )
    
    # 下单参数
    token_id = "市场token_id"  # 从gamma API获取
    price = 0.35               # 买入价格
    size = 20.0                # 数量
    
    # 买入
    result = await bot.place_order(
        token_id=token_id,
        price=price,
        size=size,
        side="BUY"
    )
    
    if result.success:
        print(f"订单成功: {result.order_id}")
    else:
        print(f"订单失败: {result.message}")
    
    # 卖出（平仓）
    sell_result = await bot.place_order(
        token_id=token_id,
        price=price + 0.10,  # 止盈价格
        size=size,
        side="SELL"
    )

# 运行
asyncio.run(manual_trade())
```

### 获取当前市场Token ID

```python
from lib.market_manager import MarketManager

async def get_market_info():
    manager = MarketManager(coin="BTC")
    await manager.start()
    
    market = manager.current_market
    print(f"市场: {market.slug}")
    print(f"UP Token: {manager.token_ids['up']}")
    print(f"DOWN Token: {manager.token_ids['down']}")
    
    await manager.stop()
```

---

## 风险提示

⚠️ **重要警告**:

1. **资金风险**: 交易有风险，可能损失全部本金
2. **测试先行**: 先用小金额测试，确认策略正常工作
3. **止损必须**: 永远设置止损，不要抱有侥幸心理
4. **网络风险**: 网络延迟可能导致订单执行价格不理想
5. **市场风险**: 15分钟市场波动剧烈，价格可能快速变化

---

## 快速开始清单

- [ ] 配置 `.env` 文件 (私钥和Safe地址)
- [ ] 确认账户有足够USDC余额
- [ ] 先运行 `orderbook.py` 观察市场
- [ ] 用小金额 (如 $5) 测试交易
- [ ] 确认止盈止损正常工作
- [ ] 逐步增加交易金额

---

*文档生成日期: 2026-01-13*
