# 订单重试处理器使用指南

## 概述

`PolymarketOrderRetryHandler` 是一个统一的错误处理和重试管理类，替代了之前分散在各处的异常处理代码。

## 核心优势

### ✅ **之前**：分散的错误处理
```python
# 买单代码中
if not result.success:
    error_msg = result.message.lower()
    if "425" in error_msg or "service not ready" in error_msg:
        if attempt < max_buy_retries:
            wait_time = (attempt + 1) * 3
            await asyncio.sleep(wait_time)
            continue
    return False

# 卖单代码中（类似的重复代码）
if "425" in error_msg or "service not ready" in error_msg:
    wait_time = min((retry + 1) * 2, 10)
    await sleep(wait_time)
```

**问题**：
- ❌ 重复代码多
- ❌ 逻辑分散
- ❌ 难以维护
- ❌ 没有统一的错误分类
- ❌ 缺乏错误统计

---

### ✅ **现在**：统一的错误处理类
```python
# 简洁的业务代码
async def place_buy_order():
    return await self.bot.place_order(...)

retry_result = await self._retry_handler.execute_with_retry(
    place_buy_order,
    operation_name="BUY"
)

if retry_result.success:
    # 处理成功结果
    pass
```

**优势**：
- ✅ 代码简洁
- ✅ 逻辑集中
- ✅ 易于测试
- ✅ 自动错误分类
- ✅ 完整的错误统计

---

## 功能特性

### 1. 自动错误分类

自动识别8种错误类型：

| 错误类型 | 示例 | 是否可重试 |
|---------|------|-----------|
| `SERVICE_NOT_READY` | 425 service not ready | ✅ 是 |
| `RATE_LIMIT` | 429 too many requests | ✅ 是 |
| `SERVER_ERROR` | 500, 502, 503, 504 | ✅ 是 |
| `NETWORK_ERROR` | timeout, connection | ✅ 是 |
| `INVALID_SIGNATURE` | invalid signature | ❌ 否 |
| `INSUFFICIENT_BALANCE` | not enough balance | ❌ 否 |
| `DUPLICATED_ORDER` | duplicated order | ❌ 否 |
| `UNKNOWN` | 其他错误 | ❌ 否 |

### 2. 智能等待策略

#### 指数退避（默认）
```
第1次: 3秒
第2次: 6秒  (3 * 2^1)
第3次: 12秒 (3 * 2^2)
```

#### 针对不同错误的定制等待时间
```python
error_wait_times = {
    ErrorCategory.SERVICE_NOT_READY: 3.0,   # 425
    ErrorCategory.RATE_LIMIT: 5.0,          # 429
    ErrorCategory.SERVER_ERROR: 2.0,        # 5xx
    ErrorCategory.NETWORK_ERROR: 1.0,       # timeout
}
```

### 3. 错误统计

策略结束时自动输出统计信息：
```
============================================================
错误统计 (Error Statistics)
============================================================
Total Errors: 15
  service_not_ready        :   8 ( 53.3%)
  rate_limit               :   4 ( 26.7%)
  server_error             :   3 ( 20.0%)
============================================================
```

---

## 使用示例

### 基础用法

```python
from lib.order_retry_handler import (
    PolymarketOrderRetryHandler, 
    RetryConfig
)

# 创建处理器
handler = PolymarketOrderRetryHandler(
    RetryConfig(
        max_retries=3,
        base_wait_time=3.0,
        exponential_backoff=True
    )
)

# 执行带重试的操作
async def place_order():
    return await bot.place_order(...)

result = await handler.execute_with_retry(
    place_order,
    operation_name="BUY BTC UP"
)

if result.success:
    print(f"成功! 尝试次数: {result.attempts}")
    print(f"结果: {result.result}")
else:
    print(f"失败: {result.error_category.value}")
    print(f"错误历史: {result.error_history}")
```

### 高级配置

```python
# 自定义配置
config = RetryConfig(
    max_retries=5,                    # 最多重试5次
    base_wait_time=2.0,               # 基础等待2秒
    max_wait_time=30.0,               # 最大等待30秒
    exponential_backoff=True,         # 使用指数退避
    backoff_multiplier=2.5,           # 退避倍数2.5
    error_wait_times={                # 特殊错误等待时间
        ErrorCategory.SERVICE_NOT_READY: 5.0,
        ErrorCategory.RATE_LIMIT: 10.0,
    }
)

handler = PolymarketOrderRetryHandler(config)
```

### 错误处理

```python
result = await handler.execute_with_retry(operation)

if not result.success:
    # 检查是否是不可重试的错误
    if result.error_category in [
        ErrorCategory.INVALID_SIGNATURE,
        ErrorCategory.INSUFFICIENT_BALANCE
    ]:
        # 需要人工干预
        notify_admin(result.error)
    else:
        # 可以稍后重试
        schedule_retry(operation)
```

---

## 代码对比

### 买单重构前后

#### ❌ 重构前（~50行复杂代码）
```python
for attempt in range(max_buy_retries + 1):
    result = await self.bot.place_order(...)
    
    if not result.success:
        error_msg = result.message.lower()
        if "425" in error_msg or "service not ready" in error_msg:
            if attempt < max_buy_retries:
                wait_time = (attempt + 1) * 3
                self.log(f"Service not ready, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
        self.log(f"Order rejected: {result.message}")
        return False
    
    # ... 更多代码
```

#### ✅ 重构后（~10行清晰代码）
```python
async def place_buy_order():
    return await self.bot.place_order(...)

retry_result = await self._retry_handler.execute_with_retry(
    place_buy_order,
    operation_name="BUY BTC UP"
)

if not retry_result.success:
    if retry_result.error_category == ErrorCategory.INVALID_SIGNATURE:
        return False
```

---

## 测试

运行测试验证功能：
```bash
python tests/test_order_retry_handler.py
```

测试覆盖：
- ✅ 可重试错误处理
- ✅ 不可重试错误识别
- ✅ 最大重试次数
- ✅ 错误分类准确性
- ✅ 错误统计功能

---

## 集成到策略

`ReboundStrategy` 中已经集成，创建策略时自动初始化：

```python
class ReboundStrategy:
    def __init__(self, bot, config):
        # ... 其他初始化
        
        # 统一的订单重试处理器
        self._retry_handler = PolymarketOrderRetryHandler(
            RetryConfig(
                max_retries=3,
                base_wait_time=3.0,
                exponential_backoff=True,
                backoff_multiplier=2.0
            )
        )
```

策略结束时自动显示错误统计：
```python
finally:
    self._print_error_stats()  # 显示所有错误统计
    self._print_summary()       # 显示交易摘要
```

---

## 架构优势

### Clean Architecture 原则
- ✅ **单一职责**：错误处理职责独立
- ✅ **依赖倒置**：业务代码不依赖具体实现
- ✅ **开闭原则**：易于扩展新的错误类型

### Domain-Driven Design
- ✅ **Domain Service**：错误处理作为领域服务
- ✅ **Value Object**：ErrorCategory 作为值对象
- ✅ **Ubiquitous Language**：统一的错误术语

### 可测试性
- ✅ **独立测试**：不需要真实的API
- ✅ **模拟错误**：可以控制错误类型
- ✅ **验证行为**：检查重试次数和等待时间

---

## 未来扩展

可以轻松添加新功能：

1. **断路器模式**（Circuit Breaker）
```python
class PolymarketOrderRetryHandler:
    def __init__(self, config):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60
        )
```

2. **重试队列**
```python
async def add_to_retry_queue(self, operation):
    await self.retry_queue.put(operation)
```

3. **指标监控**
```python
def export_metrics(self):
    return {
        "total_attempts": self.total_attempts,
        "success_rate": self.success_count / self.total_attempts,
        "avg_retry_count": ...,
    }
```

---

## 总结

通过引入 `PolymarketOrderRetryHandler`，我们实现了：

1. **代码简洁度提升 80%**：从 ~100行 → ~20行
2. **可维护性提升**：集中管理，易于修改
3. **可测试性提升**：独立测试，无需真实API
4. **可观测性提升**：完整的错误统计和日志
5. **可扩展性提升**：易于添加新的错误类型和策略

**建议**：所有涉及外部API调用的地方都应使用此错误处理器！
