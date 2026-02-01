# Task 58 Analysis: Strategy 3 Auto Stop-Loss Failed

## Problem Summary
策略三自动止损失败，订单778在A段损失超过42%但未自动止损，用户手动close了订单。

## Order Details (订单778)
```
订单ID: 778
币种: BTC
方向: DOWN
时段: A
入场价: 0.285000
出场价: 0.165000  
入场BTC: 78651.84
出场BTC: 78724.81
盈亏: $-1.26 (-42.1%)
状态: closed
模拟: False (LIVE真实交易)
周期开始: 2026-02-01 17:32:02
创建时间: 2026-02-01 17:32:03
退出时间: 2026-02-01 17:35:08 (仅3分钟后)
反弹趋势: 0.00, -0.14, -0.21, -0.25, -0.25, -0.39, -0.40, -0.46
```

## Root Cause Analysis

### 1. 止损逻辑检查 (strategies/rebound.py:1038-1045)
```python
# Stop-loss check for B and C stages (任务57: 扩展止损到B和C阶段)
segment = self.get_current_segment()
if segment in ["B", "C"]:  # ❌ 只在B和C段检查
    loss_frac = (entry - current_price) / entry
    if loss_frac >= self.config.stop_loss_stage_bc:
        self.log(f"Stage {segment} stop-loss for {side.upper()}: loss={loss_frac:.2%}", "warning")
        self._close_position(side, current_price, reason=f"stop_loss_stage_{segment.lower()}")
```

### 2. 时间段定义
- **A段**: 15-10分钟倒计时 (5分钟duration) 
- **B段**: 10-5分钟倒计时 (5分钟duration)
- **C段**: 5-0分钟倒计时 (5分钟duration)

### 3. 订单时间线
- **17:32:02**: 周期开始，订单进入A段
- **17:32:03**: 订单创建 (DOWN @ 0.285)
- **17:35:08**: 用户手动关闭 (@ 0.165, loss -42%)
- **17:37:00**: A段应该结束，进入B段 (但订单已被手动关闭)

### 4. 问题根源
**止损逻辑工作正常，但设计不适合A段LIVE交易**：
- ✅ 止损代码逻辑正确
- ✅ P&L evaluation正在运行 (反弹趋势有记录)
- ✅ 配置正确 (profit_and_loss.enabled: true, strategy.type: "3")
- ❌ **A段没有止损保护** (by design per task 57)
- ❌ **LIVE交易在A段损失42%无法自动止损**
- ❌ **用户被迫手动干预**

## Technical Details

### Stop-Loss Calculation
For a DOWN position:
```
loss_frac = (entry - current_price) / entry
         = (0.285 - 0.165) / 0.285  
         = 0.42 (42% loss)
```

This IS >= 0.2 (20% threshold), so stop-loss WOULD have triggered if we were in segment B or C.

### PnL Calculation
```
pnl = (exit_price - entry_price) * size
    = (0.165 - 0.285) * 10.53
    = -1.26 USD
    
pnl_percent = (exit_price - entry_price) / entry_price * 100
            = (0.165 - 0.285) / 0.285 * 100
            = -42.1%
```

### Rebound Trend Analysis
反弹趋势记录显示价格持续下跌：
```
0.00, -0.14, -0.21, -0.25, -0.25, -0.39, -0.40, -0.46
```

价格在3分钟内从entry price持续下跌到-46%相对亏损。

## Issue Classification

### Current Behavior (任务57设计)
- ✅ A段 (15-10分钟): **不触发止损** - 给予时间反弹
- ✅ B段 (10-5分钟): 亏损≥20%触发止损  
- ✅ C段 (5-0分钟): 亏损≥20%触发止损

### Problem for LIVE Trading
- ❌ A段无止损保护，LIVE订单可能在A段产生巨额亏损
- ❌ 用户必须手动监控A段持仓
- ❌ 订单778在A段仅3分钟就亏损42%

## Solutions

### Option 1: 为A段添加更宽松的止损 (推荐)
为不同段设置不同的止损阈值：
- A段: 30-40%止损 (更宽松，允许反弹)
- B段: 25%止损 (中等)
- C段: 20%止损 (更严格)

```python
# 修改 strategies/rebound.py
segment = self.get_current_segment()
if segment == "A":
    if loss_frac >= self.config.stop_loss_stage_a:  # e.g., 0.35 (35%)
        self.log(f"Stage A emergency stop-loss: loss={loss_frac:.2%}", "warning")
        self._close_position(side, current_price, reason="stop_loss_stage_a")
elif segment in ["B", "C"]:
    if loss_frac >= self.config.stop_loss_stage_bc:
        self.log(f"Stage {segment} stop-loss: loss={loss_frac:.2%}", "warning")
        self._close_position(side, current_price, reason=f"stop_loss_stage_{segment.lower()}")
```

配置参数：
```yaml
profit_and_loss:
  enabled: true
  take_profit_base: 0.8
  take_profit_reduce_loss: 0.1
  stop_loss_stage_a: 0.35    # A段35%紧急止损（新增）
  stop_loss_stage_bc: 0.2    # B/C段20%止损
```

### Option 2: LIVE模式使用更严格的止损
对LIVE和SIMULATED模式使用不同的止损逻辑：
- SIMULATED: A段无止损 (原设计)
- LIVE: A段也启用止损 (保护真实资金)

```python
if not self.config.simulation_mode:
    # LIVE mode: stop-loss in all segments
    if segment in ["A", "B", "C"]:
        loss_frac = (entry - current_price) / entry
        if loss_frac >= self.config.stop_loss_stage_bc:
            self._close_position(side, current_price, reason=f"stop_loss_stage_{segment.lower()}")
else:
    # SIMULATED mode: stop-loss only in B and C
    if segment in ["B", "C"]:
        loss_frac = (entry - current_price) / entry
        if loss_frac >= self.config.stop_loss_stage_bc:
            self._close_position(side, current_price, reason=f"stop_loss_stage_{segment.lower()}")
```

### Option 3: 添加绝对止损阈值
无论什么时段，亏损超过某个绝对值(如50%)立即止损：

```python
# 绝对紧急止损 (所有时段)
if loss_frac >= self.config.emergency_stop_loss:  # e.g., 0.5 (50%)
    self.log(f"EMERGENCY stop-loss: loss={loss_frac:.2%}!", "error")
    self._close_position(side, current_price, reason="emergency_stop_loss")
    return

# 常规止损 (B和C段)
segment = self.get_current_segment()
if segment in ["B", "C"]:
    if loss_frac >= self.config.stop_loss_stage_bc:
        self._close_position(side, current_price, reason=f"stop_loss_stage_{segment.lower()}")
```

## Recommendation

**推荐使用 Option 1**: 为A段添加更宽松的止损阈值（如35%）

理由：
1. ✅ 保持策略设计理念：A段允许反弹空间
2. ✅ 提供风险保护：防止极端损失
3. ✅ 灵活可配置：不同段不同阈值
4. ✅ 适用所有模式：LIVE和SIMULATED都受保护
5. ✅ 向后兼容：不改变现有B/C段逻辑

## Files to Modify

### 1. strategies/rebound.py
- 修改 `ReboundConfig` 添加 `stop_loss_stage_a` 参数
- 修改 `_evaluate_positions_for_profit_and_loss()` 添加A段止损检查

### 2. config.yaml
- 添加 `profit_and_loss.stop_loss_stage_a: 0.35` 配置

### 3. 测试脚本
- 创建 `scripts/test_task58_stop_loss_stage_a.py` 测试A段止损

## Test Cases

应该测试的场景：
1. ✅ A段亏损20%: 不触发 (< 35%阈值)
2. ✅ A段亏损35%: 触发A段止损
3. ✅ A段亏损40%: 触发A段止损  
4. ✅ B段亏损20%: 触发B段止损
5. ✅ C段亏损20%: 触发C段止损
6. ✅ B/C段亏损15%: 不触发

## Conclusion

任务58的根本原因不是bug，而是**设计缺陷**：
- ✅ 代码逻辑正确实现了任务57的需求
- ✅ P&L evaluation正常运行
- ❌ **A段无止损保护导致LIVE交易风险过高**
- 📋 **建议实施Option 1，为A段添加紧急止损保护**

这样既能保持策略的反弹理念，又能在极端情况下保护用户资金。
