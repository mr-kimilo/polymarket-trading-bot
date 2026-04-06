# Bug Fix: 订单 Expiration 设置错误

## 问题描述

在运行live模式时遇到订单被拒绝的错误：

```
BUY order rejected by CLOB: PolyApiException[status_code=400, error_message={'error': "invalid expiration value (1778072626), it should be equal to '0' as the order is not a GTD order"}]
```

## 根本原因

在 `src/bot.py` 的 `place_order` 方法中，对于 **GTC (Good Till Cancelled)** 订单，错误地设置了30天的过期时间戳。根据 Polymarket API 规范：

- **GTC 订单**: `expiration` 必须为 `0`（表示永久有效，直到手动取消）
- **GTD 订单**: `expiration` 必须为具体的时间戳（表示在特定日期过期）
- **FOK/FAK 订单**: `expiration` 为 `0`（通过 `create_market_order` 自动设置）

之前的代码对 GTC 和 GTD 订单都设置了相同的过期时间，违反了 API 规范。

## 修复内容

### 文件: `src/bot.py`

**修改前** (第445-456行):
```python
else:
    # GTC/GTD: use create_order (with expiration)
    order_args = OrderArgs(
        token_id=token_id,
        price=final_price,
        size=adjusted_size,
        side=side,
        fee_rate_bps=fee_rate_bps,
        expiration=int(time.time()) + 86400 * 30,  # ❌ 所有订单都设30天
    )
```

**修改后**:
```python
else:
    # GTC: expiration=0 (永久有效直到取消)
    # GTD: expiration=timestamp (需要指定具体过期时间)
    expiration_time = 0
    if order_type == "GTD":
        # GTD订单：30天后过期
        expiration_time = int(time.time()) + 86400 * 30
    
    order_args = OrderArgs(
        token_id=token_id,
        price=final_price,
        size=adjusted_size,
        side=side,
        fee_rate_bps=fee_rate_bps,
        expiration=expiration_time,  # ✅ 根据订单类型正确设置
    )
```

### 文档注释更新

同时更新了 `place_order` 方法的文档注释，明确说明不同订单类型的 expiration 设置：

```python
"""
Place a limit order on Polymarket CLOB.

Uses py_clob_client SDK for order creation, signing, and submission.
- FOK/FAK orders: use create_market_order (expiration=0)
- GTC orders: expiration=0 (good till cancelled)
- GTD orders: expiration=timestamp (good till specific date)
...
"""
```

## 验证

运行验证脚本 `verify_fix.py`，所有测试通过：

```
✅ GTC 订单: expiration=0
✅ GTD 订单: expiration=<future_timestamp>
✅ FOK 订单: expiration=0
✅ FAK 订单: expiration=0
```

## 影响范围

- **修复范围**: 仅影响 `src/bot.py` 的 `place_order` 方法
- **订单类型**: GTC 订单现在可以正常提交（之前会被 CLOB 拒绝）
- **向后兼容**: 不影响 FOK/FAK/GTD 订单的现有行为
- **策略影响**: 所有使用 `place_order` 的策略将自动受益于此修复

## 测试建议

重新运行live模式测试：

```bash
python apps/run_rebound.py --coin BTC --size 2 --live
```

预期结果：订单应该成功提交，不再出现 `invalid expiration value` 错误。

## 相关文件

- ✅ 修复: `src/bot.py` (第445-460行 + 文档注释)
- ✅ 验证: `verify_fix.py` (新增验证脚本)
- ℹ️  无需修改: `src/signer.py` (内部使用的 Order 类不涉及此问题)

## 技术细节

`src/bot.py` 使用 `py_clob_client` 库的 `OrderArgs` 和 `MarketOrderArgs` 来创建订单：

- `OrderArgs`: 用于 GTC/GTD 订单（通过 `create_order` 方法）
- `MarketOrderArgs`: 用于 FOK/FAK 订单（通过 `create_market_order` 方法）

修复确保 `OrderArgs.expiration` 字段根据订单类型正确设置。

---

**修复日期**: 2026-04-06  
**修复作者**: GitHub Copilot  
**测试状态**: ✅ 验证通过
