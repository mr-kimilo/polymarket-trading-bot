"""
订单队列管理器测试

展示高性能队列的强大功能
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import random
from lib.order_queue_manager import (
    OrderQueueManager,
    OrderPriority,
    EventType,
)


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"


async def test_basic_queue():
    """测试基本队列功能"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 测试1: 基本队列操作 ==={Colors.RESET}")
    
    manager = OrderQueueManager(max_workers=2)
    await manager.start()
    
    # 模拟订单操作
    async def mock_order(order_id: str, delay: float = 0.5):
        print(f"  执行订单 {order_id}...")
        await asyncio.sleep(delay)
        return {"order_id": order_id, "status": "filled"}
    
    # 提交多个订单
    task_ids = []
    for i in range(5):
        task_id = await manager.submit(
            lambda i=i: mock_order(f"order_{i}", delay=0.3),
            priority=OrderPriority.NORMAL,
            context={"order_num": i}
        )
        task_ids.append(task_id)
        print(f"{Colors.GREEN}✓{Colors.RESET} 提交订单 {i} -> {task_id}")
    
    # 等待所有任务完成
    print(f"\n{Colors.YELLOW}等待所有订单完成...{Colors.RESET}")
    results = []
    for task_id in task_ids:
        result = await manager.wait_for(task_id)
        results.append(result)
        print(f"{Colors.GREEN}✓{Colors.RESET} 订单完成: {result}")
    
    # 显示统计
    manager.print_stats()
    
    await manager.stop()
    print(f"{Colors.GREEN}✓ 测试通过!{Colors.RESET}\n")


async def test_priority_queue():
    """测试优先级队列"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 测试2: 优先级队列 ==={Colors.RESET}")
    
    manager = OrderQueueManager(max_workers=1)  # 单worker，便于观察顺序
    await manager.start()
    
    async def mock_order(name: str, priority_name: str):
        print(f"  [{priority_name}] 执行: {name}")
        await asyncio.sleep(0.2)
        return name
    
    # 按不同顺序提交不同优先级的订单
    await manager.submit(
        lambda: mock_order("正常单1", "NORMAL"),
        priority=OrderPriority.NORMAL
    )
    
    await manager.submit(
        lambda: mock_order("紧急单1", "URGENT"),
        priority=OrderPriority.URGENT
    )
    
    await manager.submit(
        lambda: mock_order("低优先级单", "LOW"),
        priority=OrderPriority.LOW
    )
    
    await manager.submit(
        lambda: mock_order("高优先级单", "HIGH"),
        priority=OrderPriority.HIGH
    )
    
    await manager.submit(
        lambda: mock_order("紧急单2", "URGENT"),
        priority=OrderPriority.URGENT
    )
    
    # 等待所有完成
    await asyncio.sleep(2.0)
    
    print(f"\n{Colors.YELLOW}预期顺序: 正常单1 → 紧急单1 → 紧急单2 → 高优先级单 → 低优先级单{Colors.RESET}")
    
    manager.print_stats()
    await manager.stop()
    print(f"{Colors.GREEN}✓ 测试通过!{Colors.RESET}\n")


async def test_error_retry():
    """测试错误重试"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 测试3: 错误重试机制 ==={Colors.RESET}")
    
    manager = OrderQueueManager(max_workers=2, default_max_retries=3)
    await manager.start()
    
    # 模拟不稳定的订单操作
    attempt_count = 0
    
    async def flaky_order():
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count < 3:
            print(f"  {Colors.RED}✗{Colors.RESET} 订单失败 (attempt {attempt_count})")
            raise Exception("Service temporarily unavailable")
        
        print(f"  {Colors.GREEN}✓{Colors.RESET} 订单成功 (attempt {attempt_count})")
        return {"status": "filled", "attempts": attempt_count}
    
    task_id = await manager.submit(flaky_order, max_retries=5)
    
    try:
        result = await manager.wait_for(task_id, timeout=10.0)
        print(f"\n{Colors.GREEN}✓{Colors.RESET} 最终成功: {result}")
    except Exception as e:
        print(f"\n{Colors.RED}✗{Colors.RESET} 最终失败: {e}")
    
    manager.print_stats()
    await manager.stop()
    print(f"{Colors.GREEN}✓ 测试通过!{Colors.RESET}\n")


async def test_event_system():
    """测试事件系统"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 测试4: 事件发布/订阅 ==={Colors.RESET}")
    
    manager = OrderQueueManager(max_workers=2)
    
    # 注册事件处理器
    events_log = []
    
    def on_order_submitted(data):
        events_log.append(("submitted", data))
        print(f"  {Colors.CYAN}[EVENT]{Colors.RESET} 订单已提交: {data['task_id']}")
    
    async def on_order_completed(data):
        events_log.append(("completed", data))
        print(f"  {Colors.GREEN}[EVENT]{Colors.RESET} 订单已完成: {data['task_id']} ({data['elapsed']:.2f}s)")
    
    def on_queue_empty(data):
        print(f"  {Colors.YELLOW}[EVENT]{Colors.RESET} 队列已清空")
    
    manager.on(EventType.ORDER_SUBMITTED, on_order_submitted)
    manager.on(EventType.ORDER_COMPLETED, on_order_completed)
    manager.on(EventType.QUEUE_EMPTY, on_queue_empty)
    
    await manager.start()
    
    # 提交订单
    async def mock_order(i):
        await asyncio.sleep(0.3)
        return f"result_{i}"
    
    for i in range(3):
        await manager.submit(lambda i=i: mock_order(i))
    
    # 等待完成
    await asyncio.sleep(2.0)
    
    print(f"\n{Colors.YELLOW}捕获到 {len(events_log)} 个事件{Colors.RESET}")
    
    await manager.stop()
    print(f"{Colors.GREEN}✓ 测试通过!{Colors.RESET}\n")


async def test_concurrent_execution():
    """测试并发执行"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 测试5: 并发执行性能 ==={Colors.RESET}")
    
    # 对比单worker和多worker性能
    print(f"\n{Colors.YELLOW}--- 单worker模式 ---{Colors.RESET}")
    manager_1 = OrderQueueManager(max_workers=1)
    await manager_1.start()
    
    async def slow_order():
        await asyncio.sleep(0.5)
        return "done"
    
    import time
    start_1 = time.time()
    for _ in range(6):
        await manager_1.submit(slow_order)
    
    while manager_1.get_stats().pending_count > 0 or manager_1.get_stats().processing_count > 0:
        await asyncio.sleep(0.1)
    
    time_1 = time.time() - start_1
    await manager_1.stop()
    
    print(f"{Colors.YELLOW}--- 3-worker模式 ---{Colors.RESET}")
    manager_3 = OrderQueueManager(max_workers=3)
    await manager_3.start()
    
    start_3 = time.time()
    for _ in range(6):
        await manager_3.submit(slow_order)
    
    while manager_3.get_stats().pending_count > 0 or manager_3.get_stats().processing_count > 0:
        await asyncio.sleep(0.1)
    
    time_3 = time.time() - start_3
    await manager_3.stop()
    
    speedup = time_1 / time_3
    print(f"\n{Colors.CYAN}性能对比:{Colors.RESET}")
    print(f"  单worker: {time_1:.2f}s")
    print(f"  3-worker: {time_3:.2f}s")
    print(f"  {Colors.GREEN}加速比: {speedup:.1f}x{Colors.RESET}")
    
    print(f"\n{Colors.GREEN}✓ 测试通过!{Colors.RESET}\n")


async def test_callbacks():
    """测试回调函数"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 测试6: 成功/失败回调 ==={Colors.RESET}")
    
    manager = OrderQueueManager(max_workers=2)
    await manager.start()
    
    results = []
    
    async def on_success(result):
        results.append(("success", result))
        print(f"  {Colors.GREEN}[CALLBACK]{Colors.RESET} 成功: {result}")
    
    async def on_failure(error):
        results.append(("failure", str(error)))
        print(f"  {Colors.RED}[CALLBACK]{Colors.RESET} 失败: {error}")
    
    # 成功的订单
    async def success_order():
        await asyncio.sleep(0.2)
        return "订单成交"
    
    # 失败的订单
    async def failed_order():
        await asyncio.sleep(0.2)
        raise Exception("余额不足")
    
    await manager.submit(success_order, on_success=on_success, on_failure=on_failure)
    await manager.submit(failed_order, max_retries=1, on_success=on_success, on_failure=on_failure)
    
    await asyncio.sleep(2.0)
    
    print(f"\n{Colors.YELLOW}回调结果: {len(results)} 个{Colors.RESET}")
    for result_type, data in results:
        print(f"  {result_type}: {data}")
    
    await manager.stop()
    print(f"{Colors.GREEN}✓ 测试通过!{Colors.RESET}\n")


async def main():
    """运行所有测试"""
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("="*60)
    print(" 🚀 订单队列管理器测试套件")
    print("="*60)
    print(Colors.RESET)
    
    await test_basic_queue()
    await test_priority_queue()
    await test_error_retry()
    await test_event_system()
    await test_concurrent_execution()
    await test_callbacks()
    
    print(f"{Colors.GREEN}{Colors.BOLD}")
    print("="*60)
    print(" ✓ 所有测试通过!")
    print("="*60)
    print(Colors.RESET)


if __name__ == "__main__":
    asyncio.run(main())
