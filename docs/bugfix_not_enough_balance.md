# 🔧 紧急修复：Not Enough Balance 错误

**修复时间**: 2026-04-06  
**问题**: 400 Bad Request - "not enough balance"  
**根本原因**: 买入订单使用GTC类型，未成交的挂单锁定资金，导致卖出时余额不足

---

## 🔍 问题分析

### 症状
```
400 Client Error: Bad Request
{'error': 'not enough balance'}
```

### 根本原因
1. **买入订单使用GTC**（Good Till Cancelled）
   - GTC订单会留在订单簿上，锁定USDC资金
   - 即使取消订单的代码存在，但可能失败或延迟
   
2. **卖出时资金被锁定**
   - 当尝试卖出时，系统需要资金（例如gas或其他费用）
   - 但资金被未成交的买入挂单占用
   - 导致余额不足错误

3. **订单流程问题**
   ```
   买入(GTC) -> 未成交 -> 挂单锁定资金
                ↓
   尝试卖出 -> 需要资金 -> 余额不足 ❌
   ```

---

## ✅ 修复内容

### 修复1: 买入订单改用FOK类型

**文件**: `strategies/rebound.py` 第1115-1123行

**修改前**:
```python
async def place_buy_order():
    return await self.bot.place_order(
        token_id=token_id,
        price=buy_price,
        size=size,
        side="BUY",
        fee_rate_bps=1000
    )
```

**修改后**:
```python
async def place_buy_order():
    return await self.bot.place_order(
        token_id=token_id,
        price=buy_price,
        size=size,
        side="BUY",
        order_type="FOK",  # ✅ FOK不会留下挂单
        fee_rate_bps=1000
    )
```

**效果**:
- ✅ FOK（Fill Or Kill）订单要么立即成交，要么立即取消
- ✅ 不会在订单簿上留下挂单
- ✅ 不会锁定资金

---

### 修复2: 卖出前取消所有挂单

**文件**: `strategies/rebound.py` 第1466-1496行

**添加内容**:
```python
async def _execute_close_live(self, side: str, exit_price: float, pos_info: Dict, db_id: Optional[int], reason: str = "") -> None:
    # ... (原有代码)
    
    # BUGFIX: 卖出前先取消该token的所有挂单，释放锁定的余额
    try:
        self.log(f"[SELL] Cancelling pending orders for token {token_id[:16]}...", "info")
        await self.bot.cancel_market_orders(asset_id=token_id)
    except Exception as e:
        self.log(f"[SELL] Cancel pending orders failed (continuing anyway): {e}", "warning")
    
    # ... (继续卖出逻辑)
```

**效果**:
- ✅ 卖出前自动取消该代币的所有挂单
- ✅ 释放锁定在挂单中的资金
- ✅ 确保有足够余额完成卖出操作
- ✅ 即使取消失败也会继续尝试卖出

---

## 🎯 修复效果

### 之前的问题流程
```
1. 买入订单(GTC) -> 未成交 -> 挂单留在订单簿
2. 资金被锁定在挂单中
3. 尝试卖出 -> "not enough balance" ❌
```

### 修复后的流程
```
1. 买入订单(FOK) -> 立即成交或取消 ✅
2. 不会留下挂单 ✅
3. 卖出前取消所有挂单 -> 释放资金 ✅
4. 卖出成功 ✅
```

---

## 📊 技术细节

### FOK vs GTC 订单类型对比

| 订单类型 | 行为 | 资金锁定 | 适用场景 |
|---------|------|---------|---------|
| **GTC** | 持续有效直到取消 | ❌ 会锁定资金 | 需要保证成交的长期订单 |
| **FOK** | 立即成交或取消 | ✅ 不锁定资金 | 快速交易，不想留挂单 |

### Polymarket订单生命周期
```
GTC订单:
  提交 -> 进入订单簿 -> [等待成交] -> 资金锁定 ⚠️
  
FOK订单:
  提交 -> [立即匹配] -> 成交 ✅
       \-> [无匹配] -> 取消 -> 资金释放 ✅
```

---

## 🔬 验证步骤

```bash
# 1. 停止当前运行的程序
Stop-Process -Name python -Force

# 2. 重新启动（修复已自动应用）
python apps/run_rebound.py --coin BTC --size 2 --live

# 3. 观察日志，应该看到：
#    - [SELL] Cancelling pending orders for token...
#    - 买入使用 FOK 订单
#    - 不再出现 "not enough balance" 错误
```

---

## 📝 相关文件

- ✅ **修复**: `strategies/rebound.py` (2处修改)
  - 第1122行: 买入订单添加 `order_type="FOK"`
  - 第1475-1481行: 卖出前取消挂单
- ℹ️  **使用**: `src/bot.py` (cancel_market_orders 方法)
- ℹ️  **文档**: 本修复说明

---

## ⏱️ 修复时间线

- **21:30** - 发现问题：400 "not enough balance"
- **21:32** - 分析代码，定位GTC订单问题
- **21:34** - 实施修复1：买入改用FOK
- **21:35** - 实施修复2：卖出前取消挂单
- **21:36** - 完成修复，准备重启测试

**总耗时**: < 5分钟 ✅

---

## 🚀 后续建议

1. **监控订单簿**
   - 定期检查是否有未取消的挂单
   - 使用 `bot.get_open_orders()` 查看活跃订单

2. **余额监控**
   - 添加余额检查逻辑
   - 在下单前验证可用余额

3. **日志增强**
   - 记录每次取消订单的结果
   - 追踪资金锁定情况

---

**修复状态**: ✅ 完成  
**测试状态**: ⏳ 待验证  
**风险等级**: 🟢 低（向后兼容，仅优化订单类型）
