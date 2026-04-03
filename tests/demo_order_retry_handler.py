"""
测试订单重试处理器

演示如何使用统一的错误处理类
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from lib.order_retry_handler import (
    PolymarketOrderRetryHandler, 
    RetryConfig,
    ErrorCategory
)


async def test_retryable_error():
    """测试可重试的错误（425 service not ready）"""
    print("\n=== 测试1: 可重试错误（425） ===")
    
    handler = PolymarketOrderRetryHandler(
        RetryConfig(max_retries=3, base_wait_time=1.0)
    )
    
    attempt = 0
    
    async def failing_operation():
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            raise Exception("425 service not ready")
        return {"success": True, "order_id": "test_123"}
    
    result = await handler.execute_with_retry(
        failing_operation,
        operation_name="Test Order"
    )
    
    print(f"✓ 成功: attempts={result.attempts}, result={result.result}")
    print(f"  错误历史: {len(result.error_history)} errors")
    for err in result.error_history:
        print(f"    - {err}")


async def test_non_retryable_error():
    """测试不可重试的错误（invalid signature）"""
    print("\n=== 测试2: 不可重试错误（invalid signature） ===")
    
    handler = PolymarketOrderRetryHandler(
        RetryConfig(max_retries=3, base_wait_time=1.0)
    )
    
    async def invalid_signature_operation():
        raise Exception("400 invalid signature")
    
    result = await handler.execute_with_retry(
        invalid_signature_operation,
        operation_name="Invalid Order"
    )
    
    print(f"✗ 失败: attempts={result.attempts}")
    print(f"  错误类别: {result.error_category.value}")
    print(f"  原因: 签名错误是不可重试的")


async def test_max_retries():
    """测试达到最大重试次数"""
    print("\n=== 测试3: 达到最大重试次数 ===")
    
    handler = PolymarketOrderRetryHandler(
        RetryConfig(max_retries=2, base_wait_time=0.5)
    )
    
    async def always_failing():
        raise Exception("Server error 503")
    
    result = await handler.execute_with_retry(
        always_failing,
        operation_name="Failing Order"
    )
    
    print(f"✗ 失败: attempts={result.attempts}")
    print(f"  错误类别: {result.error_category.value}")
    print(f"  错误历史: {len(result.error_history)} attempts")


async def test_error_classification():
    """测试错误分类功能"""
    print("\n=== 测试4: 错误分类 ===")
    
    handler = PolymarketOrderRetryHandler()
    
    test_errors = [
        "425 service not ready",
        "429 too many requests",
        "500 internal server error",
        "invalid signature",
        "insufficient balance",
        "duplicated order",
        "connection timeout",
        "unknown error"
    ]
    
    print("错误分类结果:")
    for error_msg in test_errors:
        category = handler.classify_error(Exception(error_msg))
        retryable = "✓ 可重试" if handler.is_retryable(category) else "✗ 不可重试"
        print(f"  {error_msg:30s} → {category.value:20s} {retryable}")


async def test_error_stats():
    """测试错误统计功能"""
    print("\n=== 测试5: 错误统计 ===")
    
    handler = PolymarketOrderRetryHandler(
        RetryConfig(max_retries=1, base_wait_time=0.1)
    )
    
    # 模拟多个失败操作
    errors_to_simulate = [
        "425 service not ready",
        "425 service not ready",
        "429 rate limit",
        "500 server error",
        "503 service unavailable",
    ]
    
    for error_msg in errors_to_simulate:
        async def failing_op():
            raise Exception(error_msg)
        
        await handler.execute_with_retry(failing_op, operation_name="Test")
    
    # 显示统计
    stats = handler.get_error_stats()
    print("错误统计:")
    for error_type, count in stats.items():
        print(f"  {error_type:25s}: {count} 次")


async def main():
    """运行所有测试"""
    print(Colors.CYAN + Colors.BOLD)
    print("="*60)
    print(" 订单重试处理器测试")
    print("="*60)
    print(Colors.RESET)
    
    await test_retryable_error()
    await test_non_retryable_error()
    await test_max_retries()
    await test_error_classification()
    await test_error_stats()
    
    print(Colors.GREEN + "\n✓ 所有测试完成!" + Colors.RESET)


# 简单的颜色支持
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"


if __name__ == "__main__":
    asyncio.run(main())
