"""
Base Rebound Strategy - 策略基础类 (任务57重构)

使用策略模式和工厂模式重构rebound策略：
- BaseReboundStrategy: 策略基类，定义通用逻辑
- Strategy1, Strategy2, Strategy3: 具体策略实现
- StrategyFactory: 工厂类，根据类型创建策略

设计模式：
1. 策略模式 (Strategy Pattern): 不同策略封装为独立类
2. 工厂模式 (Factory Pattern): 根据配置创建对应策略
3. 模板方法模式 (Template Method): 基类定义流程，子类实现细节
"""

import time
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, Optional, List, Tuple, Any
from enum import Enum

from lib.console import Colors, format_countdown, LogBuffer
from lib.market_manager import MarketManager, MarketInfo
from lib.price_tracker import PriceTracker
from src.bot import TradingBot
from src.websocket_client import OrderbookSnapshot
from src.database import ReboundOrder, OrderStatus, get_database


class TradingState(str, Enum):
    """交易状态"""
    RUNNING = "running"      # 正常运行
    PAUSED = "paused"        # 暂停（连续失败）
    STOPPED = "stopped"      # 停止（达到日限额）
    COOLDOWN = "cooldown"    # 冷却中


@dataclass
class RiskConfig:
    """风险控制配置 (任务58)"""
    # 连续失败控制
    max_consecutive_losses: int = 3  # 连续失败次数
    cooldown_duration: int = 3600    # 冷却时间（秒，1小时）
    
    # 日内止损
    daily_loss_limit_percent: float = 0.50  # 日内最大亏损比例（50%）
    
    # 初始资金（用于计算日内止损）
    initial_balance: float = 100.0


@dataclass
class BaseReboundConfig:
    """Rebound策略基础配置"""
    
    # 策略类型
    strategy_type: str = "1"
    
    # 基础配置
    coin: str = "BTC"
    size: float = 10.0  # USDC交易金额
    
    # 触发条件
    price_drop_threshold: float = 0.30  # UP/DOWN价格跌破阈值
    btc_drop_max: float = 50.0  # BTC最大下跌幅度（美元）
    rapid_drop_window: int = 60  # 快速下跌检测窗口（秒）
    
    # 时间段定义（分钟数）
    segment_a_start: int = 15
    segment_a_end: int = 10
    segment_b_start: int = 10
    segment_b_end: int = 5
    segment_c_start: int = 5
    segment_c_end: int = 0
    
    # 活跃时间段
    active_segments: List[str] = field(default_factory=lambda: ["A"])
    order_segments: List[str] = field(default_factory=lambda: ["A"])
    
    # 模拟模式
    simulation_mode: bool = True
    
    # 市场设置
    market_check_interval: float = 30.0
    auto_switch_market: bool = True
    update_interval: float = 0.8
    
    # Auto-claim设置
    auto_claim_enabled: bool = True
    auto_claim_min_balance: float = 5.0
    auto_claim_check_interval: int = 300
    
    # 风险控制 (任务58)
    risk_config: RiskConfig = field(default_factory=RiskConfig)
    
    # P&L设置 (策略3)
    profit_and_loss_enabled: bool = False
    strategy3_take_profit_base: float = 0.8
    strategy3_take_profit_pullback: float = 0.1
    strategy3_stop_loss_stage_a: float = 0.35
    strategy3_stop_loss_stage_bc: float = 0.2
    strategy3_use_gtc_order: bool = True
    strategy3_sell_discount: float = 0.03
    
    # 直接卖出开关
    direct_sell_enabled: bool = False


@dataclass 
class PriceRecord:
    """价格记录用于检测快速下跌"""
    timestamp: float
    price: float


class RiskManager:
    """
    风险管理器 (任务58)
    
    功能：
    1. 连续失败检测和冷却控制
    2. 日内PnL监控和止损
    """
    
    def __init__(self, config: RiskConfig):
        self.config = config
        
        # 连续失败追踪
        self._consecutive_losses: int = 0
        self._cooldown_until: Optional[float] = None
        
        # 日内PnL追踪
        self._today_pnl: float = 0.0
        self._today_date: Optional[date] = None
        self._daily_stopped: bool = False
        
        # 初始余额
        self._initial_balance = config.initial_balance
    
    def record_trade_result(self, pnl: float) -> None:
        """
        记录交易结果
        
        Args:
            pnl: 交易盈亏
        """
        # 更新日期
        today = date.today()
        if self._today_date != today:
            self._today_date = today
            self._today_pnl = 0.0
            self._daily_stopped = False
            self._consecutive_losses = 0
        
        # 更新日内PnL
        self._today_pnl += pnl
        
        # 更新连续亏损计数
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
    
    def check_can_trade(self) -> Tuple[bool, str]:
        """
        检查是否可以交易
        
        Returns:
            (can_trade, reason)
        """
        now = time.time()
        
        # 1. 检查冷却期
        if self._cooldown_until and now < self._cooldown_until:
            remaining = int(self._cooldown_until - now)
            return False, f"冷却中，剩余 {remaining // 60} 分钟"
        else:
            self._cooldown_until = None
        
        # 2. 检查日内止损
        if self._daily_stopped:
            return False, "今日已达到止损限额，停止交易"
        
        daily_loss_limit = self._initial_balance * self.config.daily_loss_limit_percent
        if self._today_pnl <= -daily_loss_limit:
            self._daily_stopped = True
            return False, f"日内亏损达到 ${abs(self._today_pnl):.2f} (>{self.config.daily_loss_limit_percent*100:.0f}%)，停止交易"
        
        # 3. 检查连续亏损
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            self._cooldown_until = now + self.config.cooldown_duration
            self._consecutive_losses = 0  # 重置计数
            return False, f"连续亏损 {self.config.max_consecutive_losses} 次，进入冷却期 {self.config.cooldown_duration // 60} 分钟"
        
        return True, ""
    
    def get_status(self) -> Dict[str, Any]:
        """获取风险状态"""
        return {
            "consecutive_losses": self._consecutive_losses,
            "max_consecutive_losses": self.config.max_consecutive_losses,
            "today_pnl": self._today_pnl,
            "daily_loss_limit": self._initial_balance * self.config.daily_loss_limit_percent,
            "daily_stopped": self._daily_stopped,
            "in_cooldown": self._cooldown_until is not None and time.time() < self._cooldown_until,
            "cooldown_remaining": max(0, int((self._cooldown_until or 0) - time.time())) if self._cooldown_until else 0
        }
    
    def set_initial_balance(self, balance: float) -> None:
        """设置初始余额（用于计算日内止损限额）"""
        self._initial_balance = balance
        self.config.initial_balance = balance


class BaseReboundStrategy(ABC):
    """
    Rebound策略基类 (模板方法模式)
    
    定义通用流程，子类实现具体策略逻辑
    """
    
    def __init__(self, bot: TradingBot, config: BaseReboundConfig):
        self.bot = bot
        self.config = config
        
        # 核心组件
        self.market = MarketManager(
            coin=config.coin,
            market_check_interval=config.market_check_interval,
            auto_switch_market=config.auto_switch_market,
        )
        self.prices = PriceTracker()
        self.db = get_database()
        
        # 风险管理 (任务58)
        self.risk_manager = RiskManager(config.risk_config)
        
        # 状态
        self.running = False
        self._log_buffer = LogBuffer(max_size=10)
        
        # 价格历史
        self._price_history: Dict[str, List[PriceRecord]] = {"up": [], "down": []}
        
        # BTC价格
        self.btc_price_start: Optional[float] = None
        self.btc_price_current: Optional[float] = None
        self.last_btc_update: float = 0
        
        # 当前周期订单
        self._current_period_orders: List[int] = []
        self._active_positions: Dict[str, Dict] = {}
        self._position_peak_price: Dict[str, float] = {}
        
        # 市场时间
        self._market_start_time: Optional[float] = None
        self._period_start_prices: Dict[str, float] = {}
        
        # 反弹趋势记录 (任务56/59)
        self._rebound_trend_records: Dict[str, List[float]] = {"up": [], "down": []}
        self._last_trend_record_time: float = 0
        self._trend_record_interval: float = 15.0
        self._closed_positions_for_trend: Dict[str, Dict] = {}
        
        # Auto-claim
        self._last_claim_check: float = 0
        self._auto_claimer = None
        if config.auto_claim_enabled and not config.simulation_mode:
            self._init_auto_claimer()
    
    def _init_auto_claimer(self) -> None:
        """初始化AutoClaimer"""
        try:
            from src.auto_claim import AutoClaimer
            import os
            
            safe_address = os.environ.get("POLY_SAFE_ADDRESS", "")
            private_key = os.environ.get("POLY_PRIVATE_KEY", "")
            
            if safe_address:
                self._auto_claimer = AutoClaimer(
                    safe_address=safe_address,
                    private_key=private_key,
                    min_balance=self.config.auto_claim_min_balance
                )
                self.log(f"AutoClaimer initialized (min balance: ${self.config.auto_claim_min_balance})", "info")
        except Exception as e:
            self.log(f"Failed to initialize AutoClaimer: {e}", "error")
    
    @property
    def is_connected(self) -> bool:
        return self.market.is_connected
    
    @property
    def current_market(self) -> Optional[MarketInfo]:
        return self.market.current_market
    
    @property
    def token_ids(self) -> Dict[str, str]:
        return self.market.token_ids
    
    def log(self, msg: str, level: str = "info") -> None:
        """记录日志"""
        self._log_buffer.add(msg, level)
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "info": "",
            "success": f"{Colors.GREEN}✓{Colors.RESET} ",
            "warning": f"{Colors.YELLOW}!{Colors.RESET} ",
            "error": f"{Colors.RED}✗{Colors.RESET} ",
            "trade": f"{Colors.CYAN}${Colors.RESET} ",
            "debug": f"{Colors.BLUE}[D]{Colors.RESET} ",
        }.get(level, "")
        print(f"[{timestamp}] {prefix}{msg}", flush=True)
    
    def get_current_segment(self) -> Optional[str]:
        """获取当前所在的时间段"""
        market = self.current_market
        if not market:
            return None
        mins, _ = market.get_countdown()
        if self.config.segment_a_end < mins <= self.config.segment_a_start:
            return "A"
        elif self.config.segment_b_end < mins <= self.config.segment_b_start:
            return "B"
        elif self.config.segment_c_end < mins <= self.config.segment_c_start:
            return "C"
        return None
    
    # ==================== 模板方法 ====================
    
    @abstractmethod
    def should_enter_trade(self, side: str, segment: str) -> Tuple[bool, Dict]:
        """
        判断是否应该入场
        
        Args:
            side: "up" or "down"
            segment: "A", "B", or "C"
            
        Returns:
            (should_enter, trigger_info)
        """
        pass
    
    @abstractmethod
    def should_exit_trade(self, side: str, segment: str, position: Dict) -> Tuple[bool, str, float]:
        """
        判断是否应该出场
        
        Args:
            side: Position side
            segment: Current segment
            position: Position info
            
        Returns:
            (should_exit, reason, exit_price)
        """
        pass
    
    def get_strategy_name(self) -> str:
        """获取策略名称"""
        return f"Strategy{self.config.strategy_type}"
    
    # ==================== 趋势记录 (任务56/59) ====================
    
    def _record_rebound_trend(self) -> None:
        """
        记录反弹趋势 (任务56/59 - 所有策略都记录)
        """
        now = time.time()
        
        if now - self._last_trend_record_time < self._trend_record_interval:
            return
        
        self._last_trend_record_time = now
        
        # 合并活跃持仓和已关闭但需要继续记录趋势的持仓
        positions_to_track: Dict[str, Dict] = {}
        
        for side, pos in self._active_positions.items():
            positions_to_track[side] = {
                "entry_price": pos.get("entry_price", 0),
                "db_id": pos.get("db_id"),
                "is_active": True
            }
        
        for side, closed_info in self._closed_positions_for_trend.items():
            if side not in positions_to_track:
                positions_to_track[side] = {
                    "entry_price": closed_info.get("entry_price", 0),
                    "db_id": closed_info.get("db_id"),
                    "is_active": False
                }
        
        if not positions_to_track:
            return
        
        for side, info in positions_to_track.items():
            entry_price = info.get("entry_price", 0)
            if entry_price <= 0:
                continue
            
            current_price = self.prices.get_current_price(side)
            if current_price <= 0:
                continue
            
            rebound_pct = (current_price - entry_price) / entry_price
            self._rebound_trend_records[side].append(rebound_pct)
            
            status = "ACTIVE" if info.get("is_active") else "CLOSED"
            self.log(
                f"[TREND] {side.upper()} ({status}) rebound: {rebound_pct:.2%}",
                "debug"
            )
    
    def _get_rebound_trend_summary(self, side: str) -> str:
        """获取反弹趋势摘要"""
        records = self._rebound_trend_records.get(side, [])
        if not records:
            return ""
        return ", ".join([f"{r:.2f}" for r in records])
    
    def _save_final_rebound_trends(self) -> None:
        """在15分钟周期结束时保存所有订单的最终反弹趋势"""
        orders_to_update: List[Tuple[str, int]] = []
        
        for side, info in self._closed_positions_for_trend.items():
            db_id = info.get("db_id")
            if db_id:
                orders_to_update.append((side, db_id))
        
        for side, pos in self._active_positions.items():
            db_id = pos.get("db_id")
            if db_id and not any(s == side and d == db_id for s, d in orders_to_update):
                orders_to_update.append((side, db_id))
        
        for side, db_id in orders_to_update:
            trend_summary = self._get_rebound_trend_summary(side)
            if trend_summary:
                self.db.update_rebound_trend_only(db_id, trend_summary)
                self.log(f"[TREND] Saved final trend for order {db_id}: {trend_summary}", "info")
    
    # ==================== 风险检查 (任务58) ====================
    
    def _check_risk_before_trade(self) -> Tuple[bool, str]:
        """交易前风险检查"""
        return self.risk_manager.check_can_trade()
    
    def _record_trade_result(self, pnl: float) -> None:
        """记录交易结果"""
        self.risk_manager.record_trade_result(pnl)
        
        # 输出风险状态
        status = self.risk_manager.get_status()
        if status["consecutive_losses"] > 0:
            self.log(
                f"[RISK] 连续亏损: {status['consecutive_losses']}/{status['max_consecutive_losses']}",
                "warning"
            )
        if status["today_pnl"] < 0:
            self.log(
                f"[RISK] 日内PnL: ${status['today_pnl']:.2f} / -${status['daily_loss_limit']:.2f}",
                "warning" if abs(status["today_pnl"]) > status["daily_loss_limit"] * 0.5 else "info"
            )
