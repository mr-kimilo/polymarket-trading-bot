"""
高性能订单队列管理器

提供企业级订单处理能力：
- 异步订单队列（支持优先级）
- 并发订单执行器（可配置并发数）
- 事件驱动架构（订阅/发布模式）
- 自动错误恢复和重试
- 实时监控和统计
"""

import asyncio
import inspect
import logging
from typing import Callable, Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
import time


logger = logging.getLogger(__name__)


class OrderPriority(Enum):
    """订单优先级"""
    URGENT = 1      # 紧急（止损、止盈）
    HIGH = 2        # 高（市价单）
    NORMAL = 3      # 正常（限价单）
    LOW = 4         # 低（批量操作）


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"          # 等待执行
    PROCESSING = "processing"    # 执行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    RETRYING = "retrying"        # 重试中
    CANCELLED = "cancelled"      # 已取消


class EventType(Enum):
    """事件类型"""
    ORDER_SUBMITTED = "order_submitted"
    ORDER_STARTED = "order_started"
    ORDER_COMPLETED = "order_completed"
    ORDER_FAILED = "order_failed"
    ORDER_RETRYING = "order_retrying"
    QUEUE_EMPTY = "queue_empty"
    QUEUE_FULL = "queue_full"
    EXECUTOR_IDLE = "executor_idle"
    EXECUTOR_BUSY = "executor_busy"


@dataclass
class OrderTask:
    """订单任务"""
    id: str
    operation: Callable
    priority: OrderPriority = OrderPriority.NORMAL
    context: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    status: OrderStatus = OrderStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # 结果
    result: Any = None
    error: Optional[Exception] = None
    attempts: int = 0
    max_retries: int = 3
    
    # 回调
    on_success: Optional[Callable] = None
    on_failure: Optional[Callable] = None
    
    def __lt__(self, other):
        """优先级排序（数字小的优先）"""
        return self.priority.value < other.priority.value
    
    @property
    def elapsed_time(self) -> float:
        """已用时间"""
        if self.started_at:
            end = self.completed_at or time.time()
            return end - self.started_at
        return 0.0
    
    @property
    def is_retryable(self) -> bool:
        """是否可重试"""
        return self.attempts < self.max_retries


@dataclass
class QueueStats:
    """队列统计"""
    total_submitted: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_cancelled: int = 0
    total_retries: int = 0
    
    pending_count: int = 0
    processing_count: int = 0
    
    avg_execution_time: float = 0.0
    avg_wait_time: float = 0.0
    
    success_rate: float = 0.0
    throughput: float = 0.0  # 每秒处理订单数
    
    priority_distribution: Dict[OrderPriority, int] = field(default_factory=lambda: defaultdict(int))
    
    def update_averages(self, tasks: List[OrderTask]):
        """更新平均值"""
        if not tasks:
            return
        
        execution_times = [t.elapsed_time for t in tasks if t.elapsed_time > 0]
        wait_times = [t.started_at - t.created_at for t in tasks if t.started_at]
        
        if execution_times:
            self.avg_execution_time = sum(execution_times) / len(execution_times)
        if wait_times:
            self.avg_wait_time = sum(wait_times) / len(wait_times)
        
        if self.total_submitted > 0:
            self.success_rate = self.total_completed / self.total_submitted


class OrderQueueManager:
    """
    高性能订单队列管理器
    
    核心功能：
    1. 异步优先级队列
    2. 并发订单执行（可配置worker数量）
    3. 自动重试机制
    4. 事件发布/订阅
    5. 实时统计监控
    
    Example:
        manager = OrderQueueManager(max_workers=3)
        await manager.start()
        
        # 提交订单
        async def place_order():
            return await bot.place_order(...)
        
        task_id = await manager.submit(
            place_order,
            priority=OrderPriority.HIGH,
            context={"symbol": "BTC", "side": "BUY"}
        )
        
        # 等待完成
        result = await manager.wait_for(task_id)
    """
    
    def __init__(
        self,
        max_workers: int = 3,
        max_queue_size: int = 100,
        default_max_retries: int = 3,
        max_completed_retention: int = 1000,
    ):
        """
        初始化队列管理器
        
        Args:
            max_workers: 最大并发worker数量
            max_queue_size: 最大队列长度
            default_max_retries: 默认最大重试次数
            max_completed_retention: 已完成任务最大保留数量（防止内存泄漏）
        """
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.default_max_retries = default_max_retries
        self._max_completed_retention = max_completed_retention
        
        # 队列
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        
        # 任务管理
        self._tasks: Dict[str, OrderTask] = {}
        self._active_tasks: Set[str] = set()
        self._task_events: Dict[str, asyncio.Event] = {}  # 用于wait_for零延迟通知
        
        # Workers
        self._workers: List[asyncio.Task] = []
        self._running = False
        
        # 事件系统
        self._event_handlers: Dict[EventType, List[Callable]] = defaultdict(list)
        
        # 统计
        self._stats = QueueStats()
        self._completed_tasks: List[OrderTask] = []
        
        # 任务ID生成
        self._task_counter = 0
    
    def _generate_task_id(self) -> str:
        """生成唯一任务ID"""
        self._task_counter += 1
        return f"task_{self._task_counter}_{int(time.time() * 1000)}"
    
    async def start(self) -> None:
        """启动队列管理器"""
        if self._running:
            logger.warning("Queue manager already running")
            return
        
        self._running = True
        
        # 启动workers
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker_{i}"))
            self._workers.append(worker)
        
        logger.info(f"Queue manager started with {self.max_workers} workers")
        await self._emit_event(EventType.EXECUTOR_IDLE, {})
    
    async def stop(self, timeout: float = 10.0) -> None:
        """停止队列管理器"""
        if not self._running:
            return
        
        self._running = False
        
        # 等待所有任务完成
        logger.info("Stopping queue manager, waiting for pending tasks...")
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for workers, cancelling...")
            for worker in self._workers:
                worker.cancel()
        
        # 清理workers列表，防止restart时重复
        self._workers.clear()
        
        logger.info("Queue manager stopped")
    
    async def submit(
        self,
        operation: Callable,
        priority: OrderPriority = OrderPriority.NORMAL,
        context: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None,
        on_success: Optional[Callable] = None,
        on_failure: Optional[Callable] = None,
    ) -> str:
        """
        提交订单任务
        
        Args:
            operation: 异步操作函数
            priority: 优先级
            context: 上下文信息
            max_retries: 最大重试次数（None使用默认值）
            on_success: 成功回调
            on_failure: 失败回调
            
        Returns:
            任务ID
        """
        if not self._running:
            raise RuntimeError("Queue manager not running")
        
        # 检查队列是否已满
        if self._queue.full():
            await self._emit_event(EventType.QUEUE_FULL, {"size": self._queue.qsize()})
            raise asyncio.QueueFull("Order queue is full")
        
        # 创建任务
        task = OrderTask(
            id=self._generate_task_id(),
            operation=operation,
            priority=priority,
            context=context or {},
            max_retries=max_retries or self.default_max_retries,
            on_success=on_success,
            on_failure=on_failure,
        )
        
        # 保存任务
        self._tasks[task.id] = task
        self._task_events[task.id] = asyncio.Event()
        
        # 加入队列（PriorityQueue需要元组: (priority, item)）
        await self._queue.put((priority.value, task))
        
        # 更新统计
        self._stats.total_submitted += 1
        self._stats.pending_count += 1
        self._stats.priority_distribution[priority] += 1
        
        # 发布事件
        await self._emit_event(EventType.ORDER_SUBMITTED, {
            "task_id": task.id,
            "priority": priority.value,
            "context": task.context,
        })
        
        logger.debug(f"Task {task.id} submitted with priority {priority.name}")
        
        return task.id
    
    async def _worker(self, name: str) -> None:
        """Worker协程，处理队列中的任务"""
        logger.info(f"Worker {name} started")
        
        while self._running:
            try:
                # 从队列获取任务（带超时，以便能响应停止信号）
                try:
                    _, task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # 执行任务
                await self._execute_task(task, worker_name=name)
                
                # 标记任务完成
                self._queue.task_done()
                
                # 检查队列是否为空
                if self._queue.empty():
                    await self._emit_event(EventType.QUEUE_EMPTY, {})
                
            except Exception as e:
                logger.error(f"Worker {name} error: {e}", exc_info=True)
        
        logger.info(f"Worker {name} stopped")
    
    async def _execute_task(self, task: OrderTask, worker_name: str) -> None:
        """执行单个任务"""
        # 跳过已取消的任务
        if task.status == OrderStatus.CANCELLED:
            logger.info(f"Worker {worker_name} skipping cancelled task {task.id}")
            self._notify_task_done(task.id)
            return

        task.status = OrderStatus.PROCESSING
        task.started_at = task.started_at or time.time()  # 仅首次设置
        task.attempts += 1
        
        self._active_tasks.add(task.id)
        self._stats.pending_count -= 1
        self._stats.processing_count += 1
        
        await self._emit_event(EventType.ORDER_STARTED, {
            "task_id": task.id,
            "worker": worker_name,
            "attempt": task.attempts,
        })
        
        logger.info(
            f"Worker {worker_name} executing {task.id} "
            f"(attempt {task.attempts}/{task.max_retries})"
        )
        
        try:
            # 执行操作
            result = await task.operation()
            
            # 成功
            task.status = OrderStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            
            self._stats.total_completed += 1
            self._stats.processing_count -= 1
            
            # 执行成功回调
            if task.on_success:
                try:
                    await self._invoke_callback(task.on_success, result)
                except Exception as e:
                    logger.error(f"Success callback error: {e}")
            
            # 发布事件
            await self._emit_event(EventType.ORDER_COMPLETED, {
                "task_id": task.id,
                "result": result,
                "elapsed": task.elapsed_time,
                "attempts": task.attempts,
            })
            
            logger.info(
                f"Task {task.id} completed in {task.elapsed_time:.2f}s "
                f"(attempt {task.attempts})"
            )
            
        except Exception as e:
            task.error = e
            
            # 检查是否可重试
            if task.is_retryable:
                # 重试（指数退避，避免紧密循环轰炸服务器）
                task.status = OrderStatus.RETRYING
                self._stats.total_retries += 1
                
                backoff = min(2 ** (task.attempts - 1), 30)
                logger.warning(
                    f"Task {task.id} failed (attempt {task.attempts}), "
                    f"will retry after {backoff}s: {e}"
                )
                
                await asyncio.sleep(backoff)
                
                # 重新加入队列
                await self._queue.put((task.priority.value, task))
                self._stats.pending_count += 1
                self._stats.processing_count -= 1
                
                await self._emit_event(EventType.ORDER_RETRYING, {
                    "task_id": task.id,
                    "error": str(e),
                    "attempt": task.attempts,
                    "max_retries": task.max_retries,
                })
            else:
                # 失败
                task.status = OrderStatus.FAILED
                task.completed_at = time.time()
                
                self._stats.total_failed += 1
                self._stats.processing_count -= 1
                
                # 执行失败回调
                if task.on_failure:
                    try:
                        await self._invoke_callback(task.on_failure, e)
                    except Exception as callback_error:
                        logger.error(f"Failure callback error: {callback_error}")
                
                # 发布事件
                await self._emit_event(EventType.ORDER_FAILED, {
                    "task_id": task.id,
                    "error": str(e),
                    "attempts": task.attempts,
                })
                
                logger.error(
                    f"Task {task.id} failed after {task.attempts} attempts: {e}"
                )
        finally:
            self._active_tasks.discard(task.id)
            if task.status in [OrderStatus.COMPLETED, OrderStatus.FAILED]:
                self._completed_tasks.append(task)
                self._trim_completed_tasks()
                self._notify_task_done(task.id)
    
    async def wait_for(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> Any:
        """
        等待任务完成
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            
        Returns:
            任务结果
            
        Raises:
            KeyError: 任务不存在
            asyncio.TimeoutError: 超时
            Exception: 任务失败时抛出原始异常
        """
        if task_id not in self._tasks:
            raise KeyError(f"Task {task_id} not found")
        
        task = self._tasks[task_id]
        event = self._task_events.get(task_id)
        
        # 快速路径：任务已完成
        if task.status == OrderStatus.COMPLETED:
            return task.result
        if task.status == OrderStatus.FAILED:
            raise task.error or Exception(f"Task {task_id} failed")
        
        # 使用Event等待，零延迟通知（替代0.1s轮询）
        if event:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError(f"Task {task_id} timeout")
        else:
            # 兜底：没有event时回退到轮询
            start = time.time()
            while True:
                if task.status in (OrderStatus.COMPLETED, OrderStatus.FAILED):
                    break
                if timeout and (time.time() - start) > timeout:
                    raise asyncio.TimeoutError(f"Task {task_id} timeout")
                await asyncio.sleep(0.05)
        
        if task.status == OrderStatus.COMPLETED:
            return task.result
        if task.status == OrderStatus.FAILED:
            raise task.error or Exception(f"Task {task_id} failed")
        
        raise asyncio.TimeoutError(f"Task {task_id} timeout")
    
    def _notify_task_done(self, task_id: str) -> None:
        """通知wait_for任务已完成"""
        event = self._task_events.pop(task_id, None)
        if event:
            event.set()

    async def _invoke_callback(self, callback: Callable, arg: Any) -> None:
        """调用回调（自动处理sync/async）"""
        if inspect.iscoroutinefunction(callback):
            await callback(arg)
        else:
            callback(arg)

    def on(self, event_type: EventType, handler: Callable) -> None:
        """注册事件处理器"""
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for {event_type.value}")
    
    async def _emit_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """发布事件"""
        handlers = self._event_handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error for {event_type.value}: {e}")
    
    def get_stats(self) -> QueueStats:
        """获取队列统计信息"""
        self._stats.pending_count = self._queue.qsize()
        self._stats.processing_count = len(self._active_tasks)
        self._stats.update_averages(self._completed_tasks)
        
        return self._stats
    
    def _trim_completed_tasks(self) -> None:
        """裁剪已完成任务列表，防止内存泄漏"""
        if len(self._completed_tasks) > self._max_completed_retention:
            excess = len(self._completed_tasks) - self._max_completed_retention
            self._completed_tasks = self._completed_tasks[excess:]
            logger.debug(
                f"Trimmed {excess} completed tasks from stats list, "
                f"retained {len(self._completed_tasks)}"
            )

    def cleanup_finished_tasks(self) -> int:
        """
        清理已完成/失败的任务，释放内存。
        
        仅在确认不再需要 wait_for 或 get_task_status 时调用。
        
        Returns:
            被清理的任务数量
        """
        to_remove = [
            tid for tid, task in self._tasks.items()
            if task.status in (OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.CANCELLED)
        ]
        for tid in to_remove:
            del self._tasks[tid]
            self._task_events.pop(tid, None)
        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} finished tasks from dict")
        return len(to_remove)
    
    def get_task_status(self, task_id: str) -> Optional[OrderStatus]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        return task.status if task else None
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务（仅对未开始的任务有效）"""
        task = self._tasks.get(task_id)
        
        if not task or task.status != OrderStatus.PENDING:
            return False
        
        task.status = OrderStatus.CANCELLED
        self._stats.total_cancelled += 1
        
        logger.info(f"Task {task_id} cancelled")
        return True
    
    def print_stats(self) -> None:
        """打印统计信息"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print(" 🚀 订单队列统计 (Order Queue Statistics)")
        print("="*60)
        print(f"  提交总数: {stats.total_submitted}")
        print(f"  完成总数: {stats.total_completed}")
        print(f"  失败总数: {stats.total_failed}")
        print(f"  取消总数: {stats.total_cancelled}")
        print(f"  重试总数: {stats.total_retries}")
        print(f"  等待中: {stats.pending_count}")
        print(f"  执行中: {stats.processing_count}")
        print(f"  成功率: {stats.success_rate*100:.1f}%")
        print(f"  平均执行时间: {stats.avg_execution_time:.2f}s")
        print(f"  平均等待时间: {stats.avg_wait_time:.2f}s")
        
        print(f"\n  优先级分布:")
        for priority, count in stats.priority_distribution.items():
            print(f"    {priority.name:10s}: {count:3d}")
        
        print("="*60 + "\n")
