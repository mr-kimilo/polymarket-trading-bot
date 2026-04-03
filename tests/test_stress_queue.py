"""
压力测试 - 订单队列管理器 & 重试处理器

测试高并发、边界条件、内存泄漏、竞争条件等稳定性问题。
使用 pytest + pytest-asyncio。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import random
import time
import gc
from unittest.mock import AsyncMock

import pytest

from lib.order_queue_manager import (
    OrderQueueManager,
    OrderPriority,
    OrderStatus,
    EventType,
)
from lib.order_retry_handler import (
    PolymarketOrderRetryHandler,
    RetryConfig,
    ErrorCategory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def retry_handler():
    return PolymarketOrderRetryHandler(
        RetryConfig(max_retries=3, base_wait_time=0.01, max_wait_time=0.05)
    )


@pytest.fixture
async def queue_manager():
    """Provide a started manager and stop it after the test."""
    mgr = OrderQueueManager(max_workers=3, max_queue_size=200)
    await mgr.start()
    yield mgr
    await mgr.stop(timeout=5.0)


# ===========================================================================
# 1. 高并发压测 - OrderQueueManager
# ===========================================================================

class TestHighConcurrency:
    """高并发场景：大量任务 + 多worker"""

    @pytest.mark.asyncio
    async def test_100_tasks_3_workers(self):
        """100个任务、3个worker并发执行"""
        mgr = OrderQueueManager(max_workers=3, max_queue_size=200)
        await mgr.start()

        completed = []

        async def fast_op(idx: int):
            await asyncio.sleep(random.uniform(0.001, 0.01))
            completed.append(idx)
            return {"idx": idx}

        task_ids = []
        for i in range(100):
            tid = await mgr.submit(lambda i=i: fast_op(i))
            task_ids.append(tid)

        for tid in task_ids:
            await mgr.wait_for(tid, timeout=30.0)

        await mgr.stop(timeout=10.0)

        stats = mgr.get_stats()
        assert stats.total_submitted == 100
        assert stats.total_completed == 100
        assert stats.total_failed == 0
        assert len(completed) == 100

    @pytest.mark.asyncio
    async def test_500_tasks_10_workers(self):
        """500个任务、10个worker 极端并发"""
        mgr = OrderQueueManager(max_workers=10, max_queue_size=600)
        await mgr.start()

        counter = {"done": 0}

        async def tiny_op():
            await asyncio.sleep(0.001)
            counter["done"] += 1
            return "ok"

        task_ids = []
        for _ in range(500):
            tid = await mgr.submit(tiny_op)
            task_ids.append(tid)

        for tid in task_ids:
            await mgr.wait_for(tid, timeout=60.0)

        await mgr.stop(timeout=10.0)

        assert counter["done"] == 500
        stats = mgr.get_stats()
        assert stats.total_completed == 500
        assert stats.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_throughput_measurement(self):
        """吞吐量测试：测量每秒处理任务数"""
        mgr = OrderQueueManager(max_workers=5, max_queue_size=300)
        await mgr.start()

        async def noop():
            return "ok"

        start = time.monotonic()
        task_ids = []
        for _ in range(200):
            tid = await mgr.submit(noop)
            task_ids.append(tid)

        for tid in task_ids:
            await mgr.wait_for(tid, timeout=30.0)

        elapsed = time.monotonic() - start
        await mgr.stop(timeout=5.0)

        throughput = 200 / elapsed
        # 无阻塞操作应该很快
        assert throughput > 50, f"Throughput too low: {throughput:.1f} tasks/s"


# ===========================================================================
# 2. 优先级正确性压测
# ===========================================================================

class TestPriorityUnderLoad:
    """在高负载下验证优先级调度的正确性"""

    @pytest.mark.asyncio
    async def test_urgent_always_first(self):
        """URGENT任务必须在队列积压时被优先处理"""
        mgr = OrderQueueManager(max_workers=1, max_queue_size=50)
        await mgr.start()

        execution_order: list[str] = []

        async def track_op(label: str):
            execution_order.append(label)
            await asyncio.sleep(0.01)
            return label

        # 先提交一个慢任务占住唯一的worker
        blocker_id = await mgr.submit(
            lambda: asyncio.sleep(0.2),
            priority=OrderPriority.NORMAL,
        )

        # 趁worker忙时大量提交不同优先级任务
        await asyncio.sleep(0.05)  # 确保blocker已经开始执行

        low_ids = []
        for i in range(5):
            tid = await mgr.submit(
                lambda i=i: track_op(f"LOW_{i}"),
                priority=OrderPriority.LOW,
            )
            low_ids.append(tid)

        urgent_ids = []
        for i in range(3):
            tid = await mgr.submit(
                lambda i=i: track_op(f"URGENT_{i}"),
                priority=OrderPriority.URGENT,
            )
            urgent_ids.append(tid)

        # 等待所有完成
        await mgr.wait_for(blocker_id, timeout=10.0)
        for tid in urgent_ids + low_ids:
            await mgr.wait_for(tid, timeout=10.0)

        await mgr.stop(timeout=5.0)

        # 验证URGENT任务排在LOW之前
        urgent_positions = [
            execution_order.index(f"URGENT_{i}")
            for i in range(3)
            if f"URGENT_{i}" in execution_order
        ]
        low_positions = [
            execution_order.index(f"LOW_{i}")
            for i in range(5)
            if f"LOW_{i}" in execution_order
        ]

        if urgent_positions and low_positions:
            assert max(urgent_positions) < min(low_positions), (
                f"URGENT tasks should complete before LOW tasks. "
                f"Order: {execution_order}"
            )


# ===========================================================================
# 3. 重试机制压测
# ===========================================================================

class TestRetryStorms:
    """重试风暴 / 大量失败的场景"""

    @pytest.mark.asyncio
    async def test_all_tasks_fail_then_retry(self):
        """所有任务失败2次后成功"""
        mgr = OrderQueueManager(max_workers=3, max_queue_size=100, default_max_retries=5)
        await mgr.start()

        counters: dict[int, int] = {}

        async def flaky_op(idx: int):
            counters[idx] = counters.get(idx, 0) + 1
            if counters[idx] <= 2:
                raise Exception("425 service not ready")
            return {"idx": idx, "attempts": counters[idx]}

        task_ids = []
        for i in range(20):
            tid = await mgr.submit(lambda i=i: flaky_op(i))
            task_ids.append(tid)

        for tid in task_ids:
            result = await mgr.wait_for(tid, timeout=30.0)
            assert result["attempts"] == 3

        await mgr.stop(timeout=5.0)

        stats = mgr.get_stats()
        assert stats.total_completed == 20
        assert stats.total_failed == 0
        assert stats.total_retries == 40  # 20 tasks * 2 retries each

    @pytest.mark.asyncio
    async def test_permanent_failures_exhaust_retries(self):
        """永久失败的任务必须在耗尽重试后标记FAILED"""
        mgr = OrderQueueManager(max_workers=2, max_queue_size=50, default_max_retries=3)
        await mgr.start()

        async def always_fail():
            raise Exception("500 internal server error")

        task_ids = []
        for _ in range(10):
            tid = await mgr.submit(always_fail)
            task_ids.append(tid)

        for tid in task_ids:
            with pytest.raises(Exception, match="500"):
                await mgr.wait_for(tid, timeout=30.0)

        await mgr.stop(timeout=5.0)

        stats = mgr.get_stats()
        assert stats.total_failed == 10
        assert stats.total_retries == 20  # 10 tasks * 2 retries each (3 attempts = 2 retries)

    @pytest.mark.asyncio
    async def test_mixed_success_failure(self):
        """50%成功率的混合场景"""
        mgr = OrderQueueManager(max_workers=3, max_queue_size=100, default_max_retries=2)
        await mgr.start()

        async def coin_flip(idx: int):
            if idx % 2 == 0:
                return {"idx": idx, "status": "ok"}
            raise Exception("Random failure")

        task_ids = []
        for i in range(30):
            tid = await mgr.submit(lambda i=i: coin_flip(i))
            task_ids.append(tid)

        success_count = 0
        fail_count = 0
        for tid in task_ids:
            try:
                await mgr.wait_for(tid, timeout=30.0)
                success_count += 1
            except Exception:
                fail_count += 1

        await mgr.stop(timeout=5.0)

        assert success_count == 15
        assert fail_count == 15


# ===========================================================================
# 4. 队列满 / 边界条件
# ===========================================================================

class TestBoundaryConditions:
    """边界条件和队列容量测试"""

    @pytest.mark.asyncio
    async def test_queue_full_raises(self):
        """队列满时提交新任务应抛出异常"""
        mgr = OrderQueueManager(max_workers=1, max_queue_size=3)
        await mgr.start()

        # 先用一个慢任务占住worker
        blocker_id = await mgr.submit(lambda: asyncio.sleep(5.0))
        await asyncio.sleep(0.05)

        # 填满队列
        for _ in range(3):
            await mgr.submit(lambda: asyncio.sleep(0.1))

        # 下一个应该失败
        with pytest.raises(asyncio.QueueFull):
            await mgr.submit(lambda: asyncio.sleep(0.1))

        await mgr.stop(timeout=1.0)

    @pytest.mark.asyncio
    async def test_submit_after_stop_raises(self):
        """停止后提交应抛出RuntimeError"""
        mgr = OrderQueueManager(max_workers=1)
        await mgr.start()
        await mgr.stop(timeout=2.0)

        with pytest.raises(RuntimeError, match="not running"):
            await mgr.submit(lambda: asyncio.sleep(0.1))

    @pytest.mark.asyncio
    async def test_wait_for_nonexistent_task(self):
        """等待不存在的任务应抛出KeyError"""
        mgr = OrderQueueManager(max_workers=1)
        await mgr.start()

        with pytest.raises(KeyError):
            await mgr.wait_for("nonexistent_task_999")

        await mgr.stop(timeout=2.0)

    @pytest.mark.asyncio
    async def test_wait_for_timeout(self):
        """wait_for超时应抛出TimeoutError"""
        mgr = OrderQueueManager(max_workers=1)
        await mgr.start()

        tid = await mgr.submit(lambda: asyncio.sleep(10.0))

        with pytest.raises(asyncio.TimeoutError):
            await mgr.wait_for(tid, timeout=0.3)

        await mgr.stop(timeout=1.0)

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self):
        """多次调用start不应出错"""
        mgr = OrderQueueManager(max_workers=2)
        await mgr.start()
        await mgr.start()  # Should be a no-op

        assert mgr._running is True
        assert len(mgr._workers) == 2  # Should not double workers

        await mgr.stop(timeout=2.0)

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self):
        """多次调用stop不应出错"""
        mgr = OrderQueueManager(max_workers=2)
        await mgr.start()
        await mgr.stop(timeout=2.0)
        await mgr.stop(timeout=2.0)  # Should be idempotent


# ===========================================================================
# 5. 事件系统压测
# ===========================================================================

class TestEventSystemStress:
    """事件发布/订阅的稳定性"""

    @pytest.mark.asyncio
    async def test_many_event_handlers(self):
        """注册大量事件处理器"""
        mgr = OrderQueueManager(max_workers=2, max_queue_size=50)

        counters = {"completed": 0, "submitted": 0}

        for _ in range(50):
            mgr.on(EventType.ORDER_COMPLETED, lambda d: counters.__setitem__(
                "completed", counters["completed"] + 1
            ))
            mgr.on(EventType.ORDER_SUBMITTED, lambda d: counters.__setitem__(
                "submitted", counters["submitted"] + 1
            ))

        await mgr.start()

        task_ids = []
        for _ in range(10):
            tid = await mgr.submit(lambda: asyncio.sleep(0.01))
            task_ids.append(tid)

        for tid in task_ids:
            await mgr.wait_for(tid, timeout=10.0)

        await mgr.stop(timeout=5.0)

        # 50 handlers x 10 events each
        assert counters["completed"] == 500
        assert counters["submitted"] == 500

    @pytest.mark.asyncio
    async def test_event_handler_exception_does_not_crash(self):
        """事件处理器抛异常不应影响队列运行"""
        mgr = OrderQueueManager(max_workers=2, max_queue_size=50)

        def bad_handler(data):
            raise ValueError("Event handler crash!")

        mgr.on(EventType.ORDER_COMPLETED, bad_handler)

        await mgr.start()

        task_ids = []
        for _ in range(5):
            tid = await mgr.submit(lambda: asyncio.sleep(0.01))
            task_ids.append(tid)

        for tid in task_ids:
            result = await mgr.wait_for(tid, timeout=10.0)
            assert result is None  # asyncio.sleep returns None

        await mgr.stop(timeout=5.0)

        stats = mgr.get_stats()
        assert stats.total_completed == 5

    @pytest.mark.asyncio
    async def test_async_event_handler(self):
        """异步事件处理器正确执行"""
        mgr = OrderQueueManager(max_workers=2, max_queue_size=50)
        results = []

        async def async_handler(data):
            await asyncio.sleep(0.001)
            results.append(data.get("task_id"))

        mgr.on(EventType.ORDER_COMPLETED, async_handler)

        await mgr.start()

        task_ids = []
        for _ in range(5):
            tid = await mgr.submit(lambda: asyncio.sleep(0.01))
            task_ids.append(tid)

        for tid in task_ids:
            await mgr.wait_for(tid, timeout=10.0)

        await mgr.stop(timeout=5.0)

        assert len(results) == 5


# ===========================================================================
# 6. 取消任务测试
# ===========================================================================

class TestCancelTask:
    """取消任务的稳定性"""

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self):
        """取消PENDING状态任务"""
        mgr = OrderQueueManager(max_workers=1, max_queue_size=10)
        await mgr.start()

        # 先占住worker
        blocker = await mgr.submit(lambda: asyncio.sleep(2.0))
        await asyncio.sleep(0.05)

        # 提交另一个任务（将处于PENDING）
        target = await mgr.submit(lambda: asyncio.sleep(0.1))
        status = mgr.get_task_status(target)
        assert status == OrderStatus.PENDING

        # 取消
        cancelled = await mgr.cancel_task(target)
        assert cancelled is True
        assert mgr.get_task_status(target) == OrderStatus.CANCELLED

        await mgr.stop(timeout=1.0)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_false(self):
        """取消不存在的任务返回False"""
        mgr = OrderQueueManager(max_workers=1)
        await mgr.start()

        result = await mgr.cancel_task("fake_task_id")
        assert result is False

        await mgr.stop(timeout=2.0)

    @pytest.mark.asyncio
    async def test_cancelled_task_not_executed(self):
        """取消的任务不应被worker执行"""
        mgr = OrderQueueManager(max_workers=1, max_queue_size=10)
        await mgr.start()

        executed = []

        # Block the worker
        blocker = await mgr.submit(lambda: asyncio.sleep(0.3))
        await asyncio.sleep(0.05)

        # Submit a task and cancel it before worker picks it up
        tid = await mgr.submit(
            lambda: executed.append("should_not_run") or asyncio.sleep(0.01),
        )
        await mgr.cancel_task(tid)

        # Submit a normal task after
        after_tid = await mgr.submit(
            lambda: executed.append("after") or asyncio.sleep(0.01),
        )

        await mgr.wait_for(blocker, timeout=5.0)
        await mgr.wait_for(after_tid, timeout=5.0)
        await mgr.stop(timeout=2.0)

        assert "should_not_run" not in executed
        assert "after" in executed


# ===========================================================================
# 7. 回调函数稳定性
# ===========================================================================

class TestCallbackStability:
    """on_success / on_failure 回调测试"""

    @pytest.mark.asyncio
    async def test_success_callback_called(self):
        """成功回调被正确调用"""
        mgr = OrderQueueManager(max_workers=2)
        await mgr.start()

        results = []

        async def on_success(result):
            results.append(result)

        tid = await mgr.submit(
            lambda: asyncio.sleep(0.01),
            on_success=on_success,
        )
        await mgr.wait_for(tid, timeout=5.0)
        await mgr.stop(timeout=2.0)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_failure_callback_called(self):
        """失败回调被正确调用"""
        mgr = OrderQueueManager(max_workers=2, default_max_retries=1)
        await mgr.start()

        errors = []

        async def on_failure(error):
            errors.append(str(error))

        tid = await mgr.submit(
            lambda: (_ for _ in ()).throw(Exception("boom")),
            on_failure=on_failure,
            max_retries=1,
        )

        with pytest.raises(Exception, match="boom"):
            await mgr.wait_for(tid, timeout=5.0)

        await mgr.stop(timeout=2.0)

        assert len(errors) == 1
        assert "boom" in errors[0]

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_crash(self):
        """回调自身抛异常不影响任务状态"""
        mgr = OrderQueueManager(max_workers=2)
        await mgr.start()

        async def crashing_callback(result):
            raise RuntimeError("callback crash!")

        tid = await mgr.submit(
            lambda: asyncio.sleep(0.01),
            on_success=crashing_callback,
        )
        result = await mgr.wait_for(tid, timeout=5.0)
        await mgr.stop(timeout=2.0)

        # Task should still be marked completed despite callback crash
        assert mgr.get_task_status(tid) == OrderStatus.COMPLETED


# ===========================================================================
# 8. PolymarketOrderRetryHandler 压测
# ===========================================================================

class TestRetryHandlerStress:
    """重试处理器的稳定性测试"""

    @pytest.mark.asyncio
    async def test_rapid_sequential_retries(self, retry_handler):
        """快速连续执行100次重试操作"""
        success_count = 0

        for i in range(100):
            attempt_counter = {"n": 0}

            async def flaky():
                attempt_counter["n"] += 1
                if attempt_counter["n"] == 1:
                    raise Exception("425 service not ready")
                return "ok"

            result = await retry_handler.execute_with_retry(flaky, f"op_{i}")
            if result.success:
                success_count += 1

        assert success_count == 100

    @pytest.mark.asyncio
    async def test_concurrent_retry_operations(self, retry_handler):
        """并发执行多个重试操作"""

        async def flaky_op(idx: int):
            counter = {"n": 0}

            async def inner():
                counter["n"] += 1
                if counter["n"] <= 1:
                    raise Exception("503 server error")
                return {"idx": idx}

            return await retry_handler.execute_with_retry(inner, f"concurrent_{idx}")

        tasks = [flaky_op(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r.success)
        assert success_count == 50

    @pytest.mark.asyncio
    async def test_all_error_categories(self, retry_handler):
        """所有错误类别的分类正确性"""
        test_cases = [
            ("status_code=425, service not ready", ErrorCategory.SERVICE_NOT_READY),
            ("429 too many requests", ErrorCategory.RATE_LIMIT),
            ("500 internal server error", ErrorCategory.SERVER_ERROR),
            ("502 bad gateway", ErrorCategory.SERVER_ERROR),
            ("503 service unavailable", ErrorCategory.SERVER_ERROR),
            ("invalid signature", ErrorCategory.INVALID_SIGNATURE),
            ("insufficient balance", ErrorCategory.INSUFFICIENT_BALANCE),
            ("duplicated order", ErrorCategory.DUPLICATED_ORDER),
            ("connection timeout", ErrorCategory.NETWORK_ERROR),
            ("network error", ErrorCategory.NETWORK_ERROR),
            ("something completely random", ErrorCategory.UNKNOWN),
        ]

        for error_msg, expected_category in test_cases:
            category = retry_handler.classify_error(Exception(error_msg))
            assert category == expected_category, (
                f"'{error_msg}' should be {expected_category}, got {category}"
            )

    @pytest.mark.asyncio
    async def test_non_retryable_stops_immediately(self, retry_handler):
        """不可重试的错误应立即停止，不再尝试"""
        attempt_count = {"n": 0}

        async def bad_signature():
            attempt_count["n"] += 1
            raise Exception("400 invalid signature")

        result = await retry_handler.execute_with_retry(bad_signature, "sig_test")

        assert not result.success
        assert attempt_count["n"] == 1  # Only 1 attempt, no retries
        assert result.error_category == ErrorCategory.INVALID_SIGNATURE

    @pytest.mark.asyncio
    async def test_error_stats_accumulate(self, retry_handler):
        """错误统计正确累积"""
        retry_handler.reset_stats()

        for _ in range(5):
            async def fail_425():
                raise Exception("425 service not ready")
            await retry_handler.execute_with_retry(fail_425, "stat_test")

        for _ in range(3):
            async def fail_sig():
                raise Exception("invalid signature")
            await retry_handler.execute_with_retry(fail_sig, "sig_test")

        stats = retry_handler.get_error_stats()
        assert stats["service_not_ready"] >= 5
        assert stats["invalid_signature"] >= 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """验证指数退避时间正确"""
        handler = PolymarketOrderRetryHandler(
            RetryConfig(
                max_retries=3,
                base_wait_time=0.1,
                max_wait_time=1.0,
                exponential_backoff=True,
                backoff_multiplier=2.0,
            )
        )

        # UNKNOWN category falls back to base_wait_time=0.1
        # attempt 0: 0.1 * 2^0 = 0.1
        assert abs(handler.calculate_wait_time(0, ErrorCategory.UNKNOWN) - 0.1) < 0.01
        # attempt 1: 0.1 * 2^1 = 0.2
        assert abs(handler.calculate_wait_time(1, ErrorCategory.UNKNOWN) - 0.2) < 0.01
        # attempt 2: 0.1 * 2^2 = 0.4
        assert abs(handler.calculate_wait_time(2, ErrorCategory.UNKNOWN) - 0.4) < 0.01
        # attempt 10: capped at max_wait_time=1.0
        assert handler.calculate_wait_time(10, ErrorCategory.UNKNOWN) == 1.0

        # SERVER_ERROR has custom base wait of 2.0 from error_wait_times
        # attempt 0: 2.0 * 2^0 = 2.0, capped at 1.0
        assert handler.calculate_wait_time(0, ErrorCategory.SERVER_ERROR) == 1.0

        # SERVICE_NOT_READY has custom base wait of 3.0
        # attempt 0: 3.0 * 2^0 = 3.0, capped at 1.0
        assert handler.calculate_wait_time(0, ErrorCategory.SERVICE_NOT_READY) == 1.0


# ===========================================================================
# 9. 队列+重试处理器联合测试
# ===========================================================================

class TestQueueWithRetryHandler:
    """队列管理器 + 重试处理器 组合使用"""

    @pytest.mark.asyncio
    async def test_queue_with_retry_handler_integration(self):
        """通过队列提交使用重试处理器的任务"""
        mgr = OrderQueueManager(max_workers=3, max_queue_size=50, default_max_retries=1)
        handler = PolymarketOrderRetryHandler(
            RetryConfig(
                max_retries=3,
                base_wait_time=0.01,
                max_wait_time=0.05,
                error_wait_times={
                    ErrorCategory.SERVICE_NOT_READY: 0.01,
                    ErrorCategory.RATE_LIMIT: 0.01,
                    ErrorCategory.SERVER_ERROR: 0.01,
                    ErrorCategory.NETWORK_ERROR: 0.01,
                },
            )
        )
        await mgr.start()

        async def order_with_retry(idx: int):
            counter = {"n": 0}

            async def place():
                counter["n"] += 1
                if counter["n"] <= 2:
                    raise Exception("425 service not ready")
                return {"idx": idx, "filled": True}

            result = await handler.execute_with_retry(place, f"order_{idx}")
            if not result.success:
                raise result.error
            return result.result

        task_ids = []
        for i in range(20):
            tid = await mgr.submit(
                lambda i=i: order_with_retry(i),
                priority=OrderPriority.HIGH,
            )
            task_ids.append(tid)

        results = []
        for tid in task_ids:
            r = await mgr.wait_for(tid, timeout=30.0)
            results.append(r)

        await mgr.stop(timeout=5.0)

        assert len(results) == 20
        assert all(r["filled"] for r in results)


# ===========================================================================
# 10. 内存和资源泄漏测试
# ===========================================================================

class TestMemoryAndResources:
    """内存 / 资源泄漏检查"""

    @pytest.mark.asyncio
    async def test_completed_tasks_list_bounded(self):
        """
        _completed_tasks list (used for stats) should be trimmed.
        _tasks dict stays intact until cleanup_finished_tasks is called.
        """
        mgr = OrderQueueManager(
            max_workers=3, max_queue_size=200, max_completed_retention=50
        )
        await mgr.start()

        task_ids = []
        for _ in range(100):
            tid = await mgr.submit(lambda: asyncio.sleep(0.001))
            task_ids.append(tid)

        for tid in task_ids:
            await mgr.wait_for(tid, timeout=10.0)

        await mgr.stop(timeout=5.0)

        # Stats list should be trimmed to retention limit
        assert len(mgr._completed_tasks) <= 50

        # _tasks dict still holds all 100 for wait_for / get_task_status
        assert len(mgr._tasks) == 100

        # Explicit cleanup removes finished tasks from dict
        cleaned = mgr.cleanup_finished_tasks()
        assert cleaned == 100
        assert len(mgr._tasks) == 0

    @pytest.mark.asyncio
    async def test_stats_accuracy_after_many_operations(self):
        """大量操作后统计数据依然准确"""
        mgr = OrderQueueManager(max_workers=3, max_queue_size=100, default_max_retries=3)
        await mgr.start()

        counters: dict[int, int] = {}
        expected_success = 0
        expected_fail = 0

        task_ids = []
        for i in range(50):
            if i % 5 == 0:
                # 永远失败
                async def fail_op():
                    raise Exception("permanent failure")
                tid = await mgr.submit(fail_op, max_retries=2)
                expected_fail += 1
            elif i % 3 == 0:
                # 失败1次后成功
                async def flaky_op(idx=i):
                    counters[idx] = counters.get(idx, 0) + 1
                    if counters[idx] <= 1:
                        raise Exception("transient 503")
                    return "ok"
                tid = await mgr.submit(flaky_op)
                expected_success += 1
            else:
                tid = await mgr.submit(lambda: asyncio.sleep(0.001))
                expected_success += 1
            task_ids.append(tid)

        for tid in task_ids:
            try:
                await mgr.wait_for(tid, timeout=30.0)
            except Exception:
                pass

        await mgr.stop(timeout=5.0)

        stats = mgr.get_stats()
        assert stats.total_submitted == 50
        total_resolved = stats.total_completed + stats.total_failed
        assert total_resolved == 50, (
            f"completed={stats.total_completed} + failed={stats.total_failed} "
            f"= {total_resolved}, expected 50"
        )


# ===========================================================================
# 11. 停止/重启 稳定性
# ===========================================================================

class TestStartStopCycles:
    """启动/停止循环测试"""

    @pytest.mark.asyncio
    async def test_start_stop_restart(self):
        """启动 -> 执行 -> 停止 -> 重启 -> 执行"""
        mgr = OrderQueueManager(max_workers=2, max_queue_size=50)

        # 第一轮
        await mgr.start()
        tid = await mgr.submit(lambda: asyncio.sleep(0.01))
        await mgr.wait_for(tid, timeout=5.0)
        await mgr.stop(timeout=2.0)

        stats1 = mgr.get_stats()
        assert stats1.total_completed >= 1

        # 重启（当前实现重启后stats应该累积，不影响稳定性）
        await mgr.start()
        tid2 = await mgr.submit(lambda: asyncio.sleep(0.01))
        await mgr.wait_for(tid2, timeout=5.0)
        await mgr.stop(timeout=2.0)

    @pytest.mark.asyncio
    async def test_force_stop_with_pending_tasks(self):
        """有pending任务时强制停止"""
        mgr = OrderQueueManager(max_workers=1, max_queue_size=20)
        await mgr.start()

        # 提交一堆慢任务
        for _ in range(10):
            await mgr.submit(lambda: asyncio.sleep(5.0))

        # 快速停止
        await mgr.stop(timeout=0.5)

        # 不应crash
        assert mgr._running is False


# ===========================================================================
# 12. 并发安全性
# ===========================================================================

class TestConcurrencySafety:
    """并发访问安全性"""

    @pytest.mark.asyncio
    async def test_concurrent_submits(self):
        """并发提交不应丢失任务"""
        mgr = OrderQueueManager(max_workers=5, max_queue_size=200)
        await mgr.start()

        async def submit_batch(start: int, count: int):
            ids = []
            for i in range(start, start + count):
                tid = await mgr.submit(lambda: asyncio.sleep(0.001))
                ids.append(tid)
            return ids

        # 并发提交5批，每批20个
        batches = await asyncio.gather(
            submit_batch(0, 20),
            submit_batch(20, 20),
            submit_batch(40, 20),
            submit_batch(60, 20),
            submit_batch(80, 20),
        )

        all_ids = [tid for batch in batches for tid in batch]
        assert len(all_ids) == 100

        # 等待所有完成
        for tid in all_ids:
            await mgr.wait_for(tid, timeout=30.0)

        await mgr.stop(timeout=5.0)

        stats = mgr.get_stats()
        assert stats.total_completed == 100

    @pytest.mark.asyncio
    async def test_concurrent_wait_for_same_task(self):
        """多个协程同时wait_for同一个任务"""
        mgr = OrderQueueManager(max_workers=2)
        await mgr.start()

        tid = await mgr.submit(lambda: asyncio.sleep(0.1))

        # 5个协程同时等待
        results = await asyncio.gather(
            mgr.wait_for(tid, timeout=5.0),
            mgr.wait_for(tid, timeout=5.0),
            mgr.wait_for(tid, timeout=5.0),
            mgr.wait_for(tid, timeout=5.0),
            mgr.wait_for(tid, timeout=5.0),
        )

        # 所有协程应拿到相同结果
        assert all(r is None for r in results)  # asyncio.sleep returns None

        await mgr.stop(timeout=2.0)


# ===========================================================================
# MAIN: 直接运行模式
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
