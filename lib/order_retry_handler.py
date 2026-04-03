"""
订单重试处理器 - 统一的错误处理和重试机制

提供强大的错误处理能力：
- 自动识别可重试错误（425, 429, 5xx等）
- 智能等待策略（指数退避、固定延迟）
- 错误分类和统计
- 可配置的重试策略
"""

import asyncio
import logging
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """错误分类"""
    SERVICE_NOT_READY = "service_not_ready"  # 425
    RATE_LIMIT = "rate_limit"  # 429
    SERVER_ERROR = "server_error"  # 5xx
    INVALID_SIGNATURE = "invalid_signature"  # 400 invalid signature
    INSUFFICIENT_BALANCE = "insufficient_balance"  # 余额不足
    DUPLICATED_ORDER = "duplicated_order"  # 重复订单
    NETWORK_ERROR = "network_error"  # 网络错误
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_wait_time: float = 3.0  # 基础等待时间（秒）
    max_wait_time: float = 30.0  # 最大等待时间
    exponential_backoff: bool = True  # 是否使用指数退避
    backoff_multiplier: float = 2.0  # 退避倍数
    
    # 不同错误类型的特殊等待时间
    error_wait_times: Dict[ErrorCategory, float] = None
    
    def __post_init__(self):
        if self.error_wait_times is None:
            self.error_wait_times = {
                ErrorCategory.SERVICE_NOT_READY: 3.0,
                ErrorCategory.RATE_LIMIT: 5.0,
                ErrorCategory.SERVER_ERROR: 2.0,
                ErrorCategory.NETWORK_ERROR: 1.0,
            }


@dataclass
class RetryResult:
    """重试结果"""
    success: bool
    result: Any = None
    attempts: int = 0
    error: Optional[Exception] = None
    error_category: Optional[ErrorCategory] = None
    error_history: List[str] = None
    
    def __post_init__(self):
        if self.error_history is None:
            self.error_history = []


class PolymarketOrderRetryHandler:
    """
    Polymarket订单重试处理器
    
    统一管理所有订单相关的错误处理和重试逻辑，让业务代码专注于业务逻辑。
    
    Example:
        handler = PolymarketOrderRetryHandler(RetryConfig(max_retries=5))
        
        async def place_order():
            return await bot.place_order(...)
        
        result = await handler.execute_with_retry(place_order)
        if result.success:
            print(f"Success after {result.attempts} attempts")
        else:
            print(f"Failed: {result.error}")
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        初始化重试处理器
        
        Args:
            config: 重试配置，如果为None则使用默认配置
        """
        self.config = config or RetryConfig()
        self._error_stats: Dict[ErrorCategory, int] = {}
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """
        对错误进行分类
        
        Args:
            error: 异常对象或错误消息
            
        Returns:
            错误分类
        """
        error_msg = str(error).lower()
        
        # 检查各种错误模式
        if "425" in error_msg or "service not ready" in error_msg:
            return ErrorCategory.SERVICE_NOT_READY
        
        if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
            return ErrorCategory.RATE_LIMIT
        
        if any(code in error_msg for code in ["500", "502", "503", "504"]):
            return ErrorCategory.SERVER_ERROR
        
        if "invalid signature" in error_msg or "signature mismatch" in error_msg:
            return ErrorCategory.INVALID_SIGNATURE
        
        if "insufficient balance" in error_msg or "not enough balance" in error_msg:
            return ErrorCategory.INSUFFICIENT_BALANCE
        
        if "duplicated" in error_msg or "duplicate" in error_msg:
            return ErrorCategory.DUPLICATED_ORDER
        
        if any(keyword in error_msg for keyword in ["timeout", "connection", "network"]):
            return ErrorCategory.NETWORK_ERROR
        
        return ErrorCategory.UNKNOWN
    
    def is_retryable(self, category: ErrorCategory) -> bool:
        """
        判断错误是否可以重试
        
        Args:
            category: 错误分类
            
        Returns:
            是否可重试
        """
        # 不可重试的错误类型
        non_retryable = {
            ErrorCategory.INVALID_SIGNATURE,  # 签名错误需要修复配置
            ErrorCategory.INSUFFICIENT_BALANCE,  # 余额不足
            ErrorCategory.DUPLICATED_ORDER,  # 重复订单
        }
        
        return category not in non_retryable
    
    def calculate_wait_time(self, attempt: int, category: ErrorCategory) -> float:
        """
        计算等待时间
        
        Args:
            attempt: 当前尝试次数（从0开始）
            category: 错误分类
            
        Returns:
            等待时间（秒）
        """
        # 获取该错误类型的基础等待时间
        base_wait = self.config.error_wait_times.get(
            category, 
            self.config.base_wait_time
        )
        
        if self.config.exponential_backoff:
            # 指数退避：base * (multiplier ^ attempt)
            wait_time = base_wait * (self.config.backoff_multiplier ** attempt)
        else:
            # 线性增长：base * (attempt + 1)
            wait_time = base_wait * (attempt + 1)
        
        # 限制在最大等待时间内
        return min(wait_time, self.config.max_wait_time)
    
    async def execute_with_retry(
        self,
        operation: Callable,
        operation_name: str = "operation",
        context: Optional[Dict[str, Any]] = None,
    ) -> RetryResult:
        """
        执行操作并自动重试
        
        Args:
            operation: 要执行的异步操作（async function）
            operation_name: 操作名称，用于日志记录
            context: 上下文信息（如订单参数），用于日志
            
        Returns:
            RetryResult包含执行结果和详细信息
        """
        attempt = 0
        error_history = []
        
        while attempt <= self.config.max_retries:
            try:
                logger.debug(
                    f"[RETRY] {operation_name} attempt {attempt + 1}/{self.config.max_retries + 1}"
                )
                
                # 执行操作
                result = await operation()
                
                # 成功
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    error_history=error_history
                )
                
            except Exception as e:
                # 分类错误
                category = self.classify_error(e)
                error_msg = f"Attempt {attempt + 1}: {category.value} - {str(e)}"
                error_history.append(error_msg)
                
                # 更新统计
                self._error_stats[category] = self._error_stats.get(category, 0) + 1
                
                logger.warning(f"[RETRY] {operation_name} failed: {error_msg}")
                
                # 检查是否可重试
                if not self.is_retryable(category):
                    logger.error(
                        f"[RETRY] {operation_name} failed with non-retryable error: {category.value}"
                    )
                    return RetryResult(
                        success=False,
                        attempts=attempt + 1,
                        error=e,
                        error_category=category,
                        error_history=error_history
                    )
                
                # 检查是否还有重试机会
                if attempt >= self.config.max_retries:
                    logger.error(
                        f"[RETRY] {operation_name} failed after {attempt + 1} attempts"
                    )
                    return RetryResult(
                        success=False,
                        attempts=attempt + 1,
                        error=e,
                        error_category=category,
                        error_history=error_history
                    )
                
                # 计算等待时间并等待
                wait_time = self.calculate_wait_time(attempt, category)
                logger.info(
                    f"[RETRY] {operation_name} will retry in {wait_time:.1f}s "
                    f"(error: {category.value})"
                )
                await asyncio.sleep(wait_time)
                
                attempt += 1
        
        # 不应该到达这里，但以防万一
        return RetryResult(
            success=False,
            attempts=attempt,
            error=Exception("Max retries exceeded"),
            error_history=error_history
        )
    
    def get_error_stats(self) -> Dict[str, int]:
        """获取错误统计信息"""
        return {cat.value: count for cat, count in self._error_stats.items()}
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self._error_stats.clear()
