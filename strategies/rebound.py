"""
Rebound Strategy - 15分钟市场反弹交易策略

策略逻辑:
1. 将15分钟周期分为3段：
   - A段: 15-10分钟（第1-5分钟）
   - B段: 10-5分钟（第6-10分钟）  
   - C段: 5-0分钟（第11-15分钟）

2. 触发条件（在A段）:
   - UP或DOWN价格在1分钟内快速下跌到30以下
   - BTC价格下跌在50美元以内
   
3. 执行:
   - 下单买入下跌的一方，持有到15分钟结束
   
4. 特性:
   - 支持模拟模式（不真实下单，用于回测）
   - 订单记录到数据库
   - 与现有FlashCrash策略完全独立

Usage:
    from strategies.rebound import ReboundStrategy, ReboundConfig
    
    config = ReboundConfig(
        coin="BTC",
        size=10.0,
        simulation_mode=True  # 模拟模式
    )
    strategy = ReboundStrategy(bot, config)
    await strategy.run()
"""

import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List, Tuple

from lib.console import Colors, format_countdown, LogBuffer
from lib.market_manager import MarketManager, MarketInfo
from lib.price_tracker import PriceTracker
from src.bot import TradingBot
from src.websocket_client import OrderbookSnapshot
from src.database import ReboundOrder, OrderStatus, get_database


@dataclass
class ReboundConfig:
    """Rebound策略配置"""
    
    # 策略类型
    # "1": 策略1 - A段, UP/DOWN<30%, BTC下跌<50
    # "2": 策略2 - C段, UP/DOWN<15%, BTC下跌<30
    strategy_type: str = "1"
    
    # 基础配置
    coin: str = "BTC"
    size: float = 10.0  # USDC交易金额
    
    # 触发条件（默认值为策略1的参数，会在__post_init__中根据strategy_type调整）
    price_drop_threshold: float = 0.30  # UP/DOWN价格跌破阈值
    btc_drop_max: float = 50.0  # BTC最大下跌幅度（美元）
    rapid_drop_window: int = 60  # 快速下跌检测窗口（秒）
    
    # 时间段定义（分钟数）
    segment_a_start: int = 15  # A段开始（倒计时）
    segment_a_end: int = 10    # A段结束
    segment_b_start: int = 10  # B段开始
    segment_b_end: int = 5     # B段结束
    segment_c_start: int = 5   # C段开始
    segment_c_end: int = 0     # C段结束
    
    # 活跃时间段（会在__post_init__中根据strategy_type设置）
    active_segments: List[str] = field(default_factory=lambda: ["A"])
    # Segments where new orders are allowed (can be different from active_segments which
    # controls where evaluation/P&L logic runs). By default orders are placed in the same
    # segments as active_segments, but strategy 3 should only place orders in A.
    order_segments: List[str] = field(default_factory=lambda: ["A"])
    
    def __post_init__(self):
        """根据策略类型设置默认参数"""
        if self.strategy_type == "2":
            # 策略2: C段, UP/DOWN<15%, BTC下跌<30
            self.price_drop_threshold = 0.15
            self.btc_drop_max = 30.0
            self.active_segments = ["C"]
            self.order_segments = ["C"]
        elif self.strategy_type == "1":
            # 策略1: A段, UP/DOWN<30%, BTC下跌<50
            self.price_drop_threshold = 0.30
            self.btc_drop_max = 50.0
            self.active_segments = ["A"]
            self.order_segments = ["A"]
        elif self.strategy_type == "3":
            # 策略3: Profit & Loss 模式
            # 启用 P&L 相关逻辑（take-profit / stop-loss）
            self.profit_and_loss_enabled = True
            # 在整个15分钟周期内评估 P&L
            self.active_segments = ["A", "B", "C"]
            # But only place new orders during A (same as strategy 1)
            self.order_segments = ["A"]
    
    # 模拟模式
    simulation_mode: bool = True  # 默认启用模拟模式
    
    # 市场设置
    market_check_interval: float = 30.0
    auto_switch_market: bool = True
    
    # 显示设置
    update_interval: float = 0.8
    
    # Auto-claim设置
    auto_claim_enabled: bool = True  # 是否启用自动claim
    auto_claim_min_balance: float = 5.0  # 最小余额阈值（USDC）
    auto_claim_check_interval: int = 300  # 检查间隔（秒，默认5分钟）

    # Profit & Loss (P&L) settings (used by strategy_type == "3")
    profit_and_loss_enabled: bool = False
    # fraction (decimal) indicating take-profit base (e.g. 0.8 == +80%)
    strategy3_take_profit_base: float = 0.8
    # fraction (decimal) peak->trough drawdown to trigger take-profit reduce (e.g. 0.1 == 10%)
    strategy3_take_profit_pullback: float = 0.1
    # fraction (decimal) loss threshold in stage A to trigger emergency stop-loss (e.g. 0.35 == 35%)
    strategy3_stop_loss_stage_a: float = 0.35
    # fraction (decimal) loss threshold in stage B and C to trigger stop-loss (e.g. 0.2 == 20%)
    strategy3_stop_loss_stage_bc: float = 0.2

    # Sell order configuration (任务61)
    # Use GTC (Good Till Cancelled) limit order instead of FOK for more reliable execution
    strategy3_use_gtc_order: bool = True
    # Sell price discount - sell at X% below current price to ensure order fills (e.g. 0.03 == 3%)
    strategy3_sell_discount: float = 0.03

    # Direct sell switch - when enabled, allows immediate selling of positions
    # Useful for manual intervention or emergency exits
    direct_sell_enabled: bool = False

    # 任务65: 订单计划功能开关
    # 当启用时，只有在order_schedule表中有对应计划的时间段内才会执行交易
    order_schedule_enabled: bool = False


@dataclass 
class PriceRecord:
    """价格记录用于检测快速下跌"""
    timestamp: float
    price: float


class ReboundStrategy:

    async def get_safe_sell_price(self, token_id: str, side: str) -> float:
        """
        获取最安全的卖出价格。
        
        优先级：
        1. CLOB midpoint (最稳定)
        2. Last trade price
        3. Orderbook best bid
        4. 兜底价格 0.01
        
        Args:
            token_id: Market token ID
            side: Position side ("up" or "down")
            
        Returns:
            Safe sell price (0 < price < 1)
        """
        from decimal import Decimal
        
        clob_client = getattr(self.bot, 'clob_client', None)
        if not clob_client:
            self.log("[WARN] get_safe_sell_price: No clob_client available", "warning")
            return 0.01
        
        # Get tick size for proper price adjustment
        try:
            tick_size_str = clob_client.get_tick_size(token_id)
            tick_size = Decimal(tick_size_str)
        except Exception:
            tick_size_str = "0.01"
            tick_size = Decimal("0.01")
        
        sell_price = None
        
        # 任务59: 记录调试信息
        self.log(f"[DEBUG] get_safe_sell_price: token_id={token_id}, side={side}, tick_size={tick_size}", "info")
        
        # 1. Try midpoint first (most stable)
        try:
            midpoint = clob_client.get_midpoint(token_id)
            self.log(f"[DEBUG] get_midpoint returned: {midpoint} (type: {type(midpoint).__name__ if midpoint else 'None'})", "info")
            if midpoint and 0 < midpoint < 1:
                # Slightly below midpoint to increase fill probability
                sell_price = midpoint - float(tick_size)
                self.log(f"[INFO] Using midpoint price: {midpoint} -> {sell_price}", "info")
        except Exception as e:
            self.log(f"[WARN] get_midpoint failed: {e}", "warning")
        
        # 2. Try last trade price
        if not sell_price or sell_price <= 0 or sell_price >= 1:
            try:
                last_price = clob_client.get_last_trade_price(token_id)
                if last_price and 0 < last_price < 1:
                    sell_price = last_price - float(tick_size)
                    self.log(f"[INFO] Using last trade price: {last_price} -> {sell_price}", "info")
            except Exception as e:
                self.log(f"[WARN] get_last_trade_price failed: {e}", "warning")
        
        # 3. Try orderbook best bid
        if not sell_price or sell_price <= 0 or sell_price >= 1:
            try:
                ob_data = clob_client.get_order_book(token_id)
                bids = ob_data.get("bids", [])
                self.log(f"[DEBUG] orderbook bids count: {len(bids)}, first 3: {bids[:3] if bids else 'empty'}", "info")
                if bids:
                    # Get best bid (highest bid price)
                    valid_bids = [float(b.get("price", 0)) for b in bids if float(b.get("price", 0)) > 0.01]
                    self.log(f"[DEBUG] valid_bids (>0.01): {valid_bids[:5] if valid_bids else 'none'}", "info")
                    if valid_bids:
                        best_bid = max(valid_bids)
                        if best_bid and best_bid > 0.01:
                            sell_price = best_bid
                            self.log(f"[INFO] Using orderbook best bid: {sell_price}", "info")
            except Exception as e:
                self.log(f"[WARN] get_order_book failed: {e}", "warning")
        
        # 4. Fallback to local orderbook if available
        if not sell_price or sell_price <= 0 or sell_price >= 1:
            self.log("[DEBUG] Trying local orderbook fallback...", "info")
            if hasattr(self, 'market') and self.market:
                orderbook = self.market.get_orderbook(side)
                self.log(f"[DEBUG] local orderbook: {orderbook.best_bid if orderbook else 'None'}", "info")
                if orderbook and orderbook.best_bid > 0.01:
                    sell_price = orderbook.best_bid
                    self.log(f"[INFO] Using local orderbook best bid: {sell_price}", "info")
        
        # 5. Final fallback
        if not sell_price or sell_price <= 0:
            sell_price = 0.01
            self.log(f"[WARN] Using fallback price: {sell_price}", "warning")
        
        # Adjust to tick size and ensure bounds
        self.log(f"[DEBUG] Before tick adjustment: sell_price={sell_price}", "info")
        sell_price_dec = Decimal(str(sell_price))
        adjusted = (sell_price_dec // tick_size) * tick_size
        adjusted = float(adjusted)
        self.log(f"[DEBUG] After tick adjustment: adjusted={adjusted}", "info")
        
        # Ensure price is within valid bounds
        if adjusted <= 0:
            self.log(f"[DEBUG] adjusted <= 0, setting to tick_size={tick_size}", "info")
            adjusted = float(tick_size)
        if adjusted >= 1:
            self.log(f"[DEBUG] adjusted >= 1, setting to 1-tick_size={1.0 - float(tick_size)}", "info")
            adjusted = 1.0 - float(tick_size)
        
        self.log(f"[DEBUG] Final sell price: {adjusted}", "info")
        return adjusted
    """
    Rebound反弹交易策略
    
    在15分钟周期的A段（15-10分钟），当检测到UP或DOWN价格
    快速下跌到30以下且BTC下跌不超过50美元时，买入下跌方
    持有到15分钟结束。
    """
    
    def __init__(self, bot: TradingBot, config: ReboundConfig):
        """
        初始化策略
        
        Args:
            bot: TradingBot实例，用于真实下单
            config: 策略配置
        """
        self.bot = bot
        self.config = config
        
        # 核心组件
        self.market = MarketManager(
            coin=config.coin,
            market_check_interval=config.market_check_interval,
            auto_switch_market=config.auto_switch_market,
        )
        
        self.prices = PriceTracker()
        
        # 数据库
        self.db = get_database()
        
        # 状态
        self.running = False
        self._log_buffer = LogBuffer(max_size=10)
        
        # 价格历史（用于检测快速下跌）
        self._price_history: Dict[str, List[PriceRecord]] = {
            "up": [],
            "down": []
        }
        
        # BTC价格
        self.btc_price_start: Optional[float] = None
        self.btc_price_current: Optional[float] = None
        self.last_btc_update: float = 0
        # 当前周期的订单
        self._current_period_orders: List[int] = []  # 数据库订单ID列表
        self._active_positions: Dict[str, Dict] = {}  # side -> position info
        # P&L tracking: record peak price (highest observed price after entry) per side
        self._position_peak_price: Dict[str, float] = {}

        # 市场开始时间
        self._market_start_time: Optional[float] = None
        self._period_start_prices: Dict[str, float] = {}

        # 反弹趋势记录 (任务56)
        # 每15秒记录一次反弹百分比，用于分析反弹趋势
        self._rebound_trend_records: Dict[str, List[float]] = {
            "up": [],    # UP side 反弹百分比记录
            "down": []   # DOWN side 反弹百分比记录
        }
        self._last_trend_record_time: float = 0
        self._trend_record_interval: float = 15.0  # 每15秒记录一次
        
        # 任务56补充：已关闭订单的趋势跟踪
        # 即使订单提前关闭，也继续记录趋势直到15分钟结束
        # side -> {"db_id": int, "entry_price": float}
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
            else:
                self.log("AutoClaimer disabled: POLY_SAFE_ADDRESS not set", "warning")
        except Exception as e:
            self.log(f"Failed to initialize AutoClaimer: {e}", "error")
    
    @property
    def is_connected(self) -> bool:
        """WebSocket是否连接"""
        return self.market.is_connected
    
    @property
    def current_market(self) -> Optional[MarketInfo]:
        """当前市场信息"""
        return self.market.current_market
    
    @property
    def token_ids(self) -> Dict[str, str]:
        """当前token IDs"""
        return self.market.token_ids
    
    def log(self, msg: str, level: str = "info") -> None:
        """记录日志"""
        self._log_buffer.add(msg, level)
        # 同时输出到控制台
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "info": "",
            "success": f"{Colors.GREEN}✓{Colors.RESET} ",
            "warning": f"{Colors.YELLOW}!{Colors.RESET} ",
            "error": f"{Colors.RED}✗{Colors.RESET} ",
            "trade": f"{Colors.CYAN}${Colors.RESET} ",
        }.get(level, "")
        print(f"[{timestamp}] {prefix}{msg}", flush=True)
    
    def get_current_segment(self) -> Optional[str]:
        """
        获取当前所在的时间段
        
        Returns:
            "A", "B", "C" 或 None
        """
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
    
    def _record_price(self, side: str, price: float) -> None:
        """记录价格用于快速下跌检测"""
        now = time.time()
        record = PriceRecord(timestamp=now, price=price)
        self._price_history[side].append(record)
        
        # 清理过期记录（保留2分钟内的数据）
        cutoff = now - 120
        self._price_history[side] = [
            r for r in self._price_history[side] 
            if r.timestamp >= cutoff
        ]
    
    def _detect_rapid_drop(self, side: str) -> Optional[Tuple[float, float, float]]:
        """
        检测是否发生快速下跌
        
        Args:
            side: "up" 或 "down"
            
        Returns:
            如果检测到快速下跌，返回 (起始价格, 当前价格, 下跌幅度)
            否则返回 None
        """
        history = self._price_history.get(side, [])
        if len(history) < 2:
            return None
        
        now = time.time()
        window_start = now - self.config.rapid_drop_window
        
        # 获取窗口内的起始价格
        window_records = [r for r in history if r.timestamp >= window_start]
        if not window_records:
            return None
        
        start_price = window_records[0].price
        current_price = window_records[-1].price
        
        # 检查是否跌破阈值
        if current_price < self.config.price_drop_threshold:
            drop = start_price - current_price
            if drop > 0:  # 确实是下跌
                return (start_price, current_price, drop)
        
        return None
    
    def _fetch_btc_price_chainlink(self) -> Optional[float]:
        """通过Chainlink获取BTC价格（Polymarket使用的数据源）"""
        try:
            from web3 import Web3
            
            # Polygon RPC
            rpc_url = 'https://polygon-rpc.com'
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            
            # Chainlink BTC/USD Price Feed on Polygon
            # https://docs.chain.link/data-feeds/price-feeds/addresses?network=polygon
            CHAINLINK_BTC_USD_POLYGON = '0xc907E116054Ad103354f2D350FD2514433D57F6f'
            
            # ABI for Chainlink Price Feed
            PRICE_FEED_ABI = [
                {
                    'inputs': [],
                    'name': 'latestRoundData',
                    'outputs': [
                        {'name': 'roundId', 'type': 'uint80'},
                        {'name': 'answer', 'type': 'int256'},
                        {'name': 'startedAt', 'type': 'uint256'},
                        {'name': 'updatedAt', 'type': 'uint256'},
                        {'name': 'answeredInRound', 'type': 'uint80'}
                    ],
                    'stateMutability': 'view',
                    'type': 'function'
                },
                {
                    'inputs': [],
                    'name': 'decimals',
                    'outputs': [{'name': '', 'type': 'uint8'}],
                    'stateMutability': 'view',
                    'type': 'function'
                }
            ]
            
            contract = w3.eth.contract(address=CHAINLINK_BTC_USD_POLYGON, abi=PRICE_FEED_ABI)
            decimals = contract.functions.decimals().call()
            round_data = contract.functions.latestRoundData().call()
            price = round_data[1] / (10 ** decimals)
            
            return price
        except Exception:
            return None
    
    def _fetch_btc_price(self) -> Optional[float]:
        """获取BTC当前价格
        
        优先使用Chainlink（Polymarket使用的数据源），
        如果失败则回退到其他API。
        """
        import requests
        
        # 首选：Chainlink（与Polymarket使用相同数据源）
        price = self._fetch_btc_price_chainlink()
        if price:
            return price
        
        # 备用: CoinGecko
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "bitcoin", "vs_currencies": "usd"}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price = data.get("bitcoin", {}).get("usd")
                if price:
                    return price
        except Exception:
            pass
        
        # 备用: CoinCap
        try:
            url = "https://api.coincap.io/v2/assets/bitcoin"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price_str = data.get("data", {}).get("priceUsd")
                if price_str:
                    return float(price_str)
        except Exception:
            pass
        
        # 备用: Binance
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {"symbol": "BTCUSDT"}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price_str = data.get("price")
                if price_str:
                    return float(price_str)
        except Exception:
            pass
        
        return None
    
    def _update_btc_price(self) -> None:
        """更新BTC价格"""
        now = time.time()
        if now - self.last_btc_update < 5:  # 每5秒更新一次
            return
        
        price = self._fetch_btc_price()
        if price:
            if self.btc_price_start is None:
                self.btc_price_start = price
            self.btc_price_current = price
            self.last_btc_update = now
    
    def _record_rebound_trend(self) -> None:
        """
        记录反弹趋势 (任务56 + 任务56补充)
        
        每15秒记录一次UP和DOWN的反弹百分比，用于后续分析最佳止盈点。
        反弹百分比 = (当前价格 - 入场价格) / 入场价格
        
        任务56补充：即使订单提前关闭，也继续记录趋势直到15分钟结束。
        这样可以分析从开单到周期结束的完整趋势，用于优化止盈止损参数。
        """
        now = time.time()
        
        # 检查是否到了记录时间
        if now - self._last_trend_record_time < self._trend_record_interval:
            return
        
        # 更新最后记录时间（放在前面，避免重复记录）
        self._last_trend_record_time = now
        
        # 合并活跃持仓和已关闭但需要继续记录趋势的持仓
        positions_to_track: Dict[str, Dict] = {}
        
        # 1. 活跃持仓
        for side, pos in self._active_positions.items():
            positions_to_track[side] = {
                "entry_price": pos.get("entry_price", 0),
                "db_id": pos.get("db_id"),
                "is_active": True
            }
        
        # 2. 已关闭但仍需记录趋势的持仓（任务56补充）
        for side, closed_info in self._closed_positions_for_trend.items():
            if side not in positions_to_track:  # 避免重复
                positions_to_track[side] = {
                    "entry_price": closed_info.get("entry_price", 0),
                    "db_id": closed_info.get("db_id"),
                    "is_active": False
                }
        
        # 如果没有需要跟踪的持仓，直接返回
        if not positions_to_track:
            return
        
        # 记录每个持仓的反弹百分比
        for side, info in positions_to_track.items():
            entry_price = info.get("entry_price", 0)
            if entry_price <= 0:
                continue
            
            current_price = self.prices.get_current_price(side)
            if current_price <= 0:
                continue
            
            # 计算反弹百分比
            rebound_pct = (current_price - entry_price) / entry_price
            
            # 记录到数组
            self._rebound_trend_records[side].append(rebound_pct)
            
            # 记录日志（debug级别）
            status = "ACTIVE" if info.get("is_active") else "CLOSED"
            self.log(
                f"[TREND] {side.upper()} ({status}) rebound: {rebound_pct:.2%} "
                f"(entry={entry_price:.4f}, current={current_price:.4f})",
                "debug"
            )
    
    def _get_rebound_trend_summary(self, side: str) -> str:
        """
        获取反弹趋势记录的摘要字符串
        
        Args:
            side: "up" 或 "down"
            
        Returns:
            逗号分隔的反弹百分比字符串，例如: "0.15, 0.25, 0.35, 0.30, 0.28"
        """
        records = self._rebound_trend_records.get(side, [])
        if not records:
            return ""
        
        # 格式化为百分比字符串（保留2位小数）
        pct_strings = [f"{r:.2f}" for r in records]
        return ", ".join(pct_strings)
    
    def _save_final_rebound_trends(self) -> None:
        """
        任务56补充：在15分钟周期结束时保存所有订单的最终反弹趋势
        
        这个方法会为以下订单更新反弹趋势：
        1. 已提前关闭的订单 (_closed_positions_for_trend)
        2. 仍然活跃的订单 (_active_positions)
        
        趋势记录是从开单到15分钟结束的完整记录，而不是订单关闭时的记录。
        这样可以分析完整的价格走势，用于优化止盈止损参数。
        """
        # 收集所有需要更新趋势的订单
        orders_to_update: List[Tuple[str, int]] = []  # (side, db_id)
        
        # 1. 已提前关闭的订单
        for side, info in self._closed_positions_for_trend.items():
            db_id = info.get("db_id")
            if db_id:
                orders_to_update.append((side, db_id))
        
        # 2. 仍然活跃的订单
        for side, pos in self._active_positions.items():
            db_id = pos.get("db_id")
            if db_id:
                # 检查是否已经在列表中（避免重复）
                if not any(s == side and d == db_id for s, d in orders_to_update):
                    orders_to_update.append((side, db_id))
        
        # 更新每个订单的最终趋势
        for side, db_id in orders_to_update:
            trend_summary = self._get_rebound_trend_summary(side)
            if trend_summary:
                success = self.db.update_rebound_trend_only(db_id, trend_summary)
                if success:
                    self.log(
                        f"[TREND] Saved final trend for order {db_id} ({side.upper()}): {trend_summary}",
                        "info"
                    )
                else:
                    self.log(
                        f"[TREND] Failed to save final trend for order {db_id}",
                        "warning"
                    )
            else:
                self.log(
                    f"[TREND] No trend data to save for order {db_id} ({side.upper()})",
                    "debug"
                )
    
    def _check_btc_condition(self) -> bool:
        """
        检查BTC价格条件
        
        Returns:
            如果BTC下跌在允许范围内返回True
        """
        if self.btc_price_start is None or self.btc_price_current is None:
            return True  # 无法获取价格时不限制
        
        drop = self.btc_price_start - self.btc_price_current
        return drop <= self.config.btc_drop_max
    
    async def _execute_trade(self, side: str, trigger_info: Dict) -> bool:
        """
        执行交易
        
        Args:
            side: "up" 或 "down"
            trigger_info: 触发条件信息
            
        Returns:
            是否成功
        """
        current_price = self.prices.get_current_price(side)
        if current_price <= 0:
            self.log(f"Invalid price for {side}: {current_price}", "error")
            return False
        
        token_id = self.token_ids.get(side)
        if not token_id:
            self.log(f"No token ID for {side}", "error")
            return False
        
        # 计算交易数量
        size = self.config.size / current_price
        
        # 任务64: 确定env值
        env = "sim" if self.config.simulation_mode else "prod"
        
        # 创建订单记录
        order = ReboundOrder(
            coin=self.config.coin,
            side=side,
            segment=trigger_info.get("segment", "A"),
            entry_price=current_price,
            entry_btc_price=self.btc_price_current,
            size=size,
            trigger_up_price=trigger_info.get("up_price"),
            trigger_down_price=trigger_info.get("down_price"),
            trigger_up_drop=trigger_info.get("up_drop"),
            trigger_down_drop=trigger_info.get("down_drop"),
            btc_drop=trigger_info.get("btc_drop"),
            period_start=datetime.now(),
            status=OrderStatus.OPEN.value if not self.config.simulation_mode else OrderStatus.SIMULATED.value,
            is_simulated=self.config.simulation_mode,
            market_slug=self.current_market.slug if self.current_market else None,
            token_id=token_id,
            strategy_type=self.config.strategy_type,  # 任务64
            env=env  # 任务64
        )
        
        # 如果是真实模式，执行下单
        if not self.config.simulation_mode:
            # 检查bot是否存在
            if not self.bot:
                self.log("Error: Bot not initialized for LIVE trading", "error")
                return False
            
            buy_price = min(current_price + 0.02, 0.99)
            self.log(f"[LIVE] Placing order: BUY {side.upper()} @ {buy_price:.4f}, size={size:.2f}", "trade")
            
            # BTC UP/DOWN 15-minute markets have 10% taker fee (1000 bps)
            result = await self.bot.place_order(
                token_id=token_id,
                price=buy_price,
                size=size,
                side="BUY",
                fee_rate_bps=1000  # 10% taker fee for BTC 15m markets
            )
            
            if result.success:
                order.order_id = result.order_id
                self.log(f"[LIVE] Order placed successfully: {result.order_id}", "success")
            else:
                self.log(f"[LIVE] Order failed: {result.message}", "error")
                return False
        else:
            self.log(f"[SIMULATED] Would BUY {side.upper()} @ {current_price:.4f}", "trade")
        
        # 保存到数据库
        db_order_id = self.db.create_rebound_order(order)
        if db_order_id:
            self._current_period_orders.append(db_order_id)
            self._active_positions[side] = {
                "db_id": db_order_id,
                "entry_price": current_price,
                "size": size,
                "entry_time": time.time()
            }
            # initialize P&L tracking for strategy_type == "3"
            if self.config.profit_and_loss_enabled and self.config.strategy_type == "3":
                # record peak at entry and mark TP not yet eligible
                self._position_peak_price[side] = current_price
                self._active_positions[side]["_tp_eligible"] = False
            
            mode_str = "SIMULATED" if self.config.simulation_mode else "REAL"
            self.log(
                f"[{mode_str}] Opened {side.upper()} position @ {current_price:.4f} "
                f"(size={size:.2f}, segment={trigger_info.get('segment')})",
                "trade"
            )
            return True
        
        return False

    async def direct_sell_all_positions(self, reason: str = "direct_sell") -> Dict[str, bool]:
        """
        直接卖出所有持仓（紧急退出/手动干预）
        
        当 config.direct_sell_enabled 为 True 时可用。
        该方法会立即以市价卖出所有活跃持仓。
        
        Args:
            reason: 卖出原因，用于日志记录
            
        Returns:
            Dict[side, success] 每个持仓的卖出结果
        """
        results = {}
        
        if not self.config.direct_sell_enabled:
            self.log("[WARN] Direct sell is disabled. Set direct_sell_enabled=True to enable.", "warning")
            return results
        
        if not self._active_positions:
            self.log("[INFO] No active positions to sell.", "info")
            return results
        
        self.log(f"[DIRECT_SELL] Starting direct sell for {len(self._active_positions)} position(s). Reason: {reason}", "warning")
        
        for side, pos_info in list(self._active_positions.items()):
            try:
                token_id = pos_info.get("token_id") or self.token_ids.get(side)
                size = pos_info.get("size", 0)
                entry_price = pos_info.get("entry_price", 0)
                db_id = pos_info.get("db_id")
                
                if not token_id or size <= 0:
                    self.log(f"[DIRECT_SELL] Invalid position for {side}: token_id={token_id}, size={size}", "error")
                    results[side] = False
                    continue
                
                # Get safe sell price
                sell_price = await self.get_safe_sell_price(token_id, side)
                
                if self.config.simulation_mode:
                    # Simulated mode - just log and update DB
                    exit_price = self.prices.get_current_price(side)
                    if exit_price <= 0:
                        exit_price = sell_price
                    
                    pnl = (exit_price - entry_price) * size
                    pnl_percent = (exit_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                    
                    if db_id:
                        self.db.update_rebound_order_result(
                            order_id=db_id,
                            exit_price=exit_price,
                            exit_btc_price=self.btc_price_current,
                            pnl=pnl,
                            pnl_percent=pnl_percent,
                            status=OrderStatus.CLOSED.value
                        )
                    
                    color = Colors.GREEN if pnl >= 0 else Colors.RED
                    self.log(
                        f"[SIMULATED DIRECT_SELL] Sold {side.upper()} @ {exit_price:.4f} "
                        f"PnL: {color}${pnl:+.2f} ({pnl_percent:+.1f}%){Colors.RESET}",
                        "success" if pnl >= 0 else "warning"
                    )
                    results[side] = True
                else:
                    # LIVE mode - execute real sell
                    await self._execute_close_live(side, sell_price, pos_info, db_id, reason=f"direct_sell:{reason}")
                    results[side] = True
                
                # Cleanup
                if side in self._position_peak_price:
                    del self._position_peak_price[side]
                if side in self._active_positions:
                    del self._active_positions[side]
                    
            except Exception as e:
                self.log(f"[DIRECT_SELL] Error selling {side}: {e}", "error")
                results[side] = False
        
        self._current_period_orders.clear()
        self.log(f"[DIRECT_SELL] Completed. Results: {results}", "info")
        return results
    
    def _close_all_positions(self, use_prices: Optional[Dict[str, float]] = None) -> None:
        """
        关闭所有持仓并更新数据库
        在15分钟周期结束时调用
        
        Args:
            use_prices: 可选，指定用于计算PnL的价格。
                       如果不提供，则使用当前价格追踪器中的价格。
                       用于市场切换时，使用旧市场的最后价格。
        """
        # In LIVE mode we should attempt to execute real SELL orders before updating DB.
        # This function schedules async close tasks when running live and performs DB updates
        # immediately for simulated mode.
        for side, pos_info in list(self._active_positions.items()):
            # 优先使用传入的价格（旧市场的最后价格）
            if use_prices and side in use_prices:
                current_price = use_prices[side]
            else:
                current_price = self.prices.get_current_price(side)

            entry_price = pos_info.get("entry_price", 0)
            size = pos_info.get("size", 0)
            db_id = pos_info.get("db_id")

            if self.config.simulation_mode:
                # Simulated mode: update DB and log synchronously
                if current_price > 0 and entry_price > 0:
                    pnl = (current_price - entry_price) * size
                    pnl_percent = (current_price - entry_price) / entry_price * 100

                    if db_id:
                        self.db.update_rebound_order_result(
                            order_id=db_id,
                            exit_price=current_price,
                            exit_btc_price=self.btc_price_current,
                            pnl=pnl,
                            pnl_percent=pnl_percent,
                            status=OrderStatus.CLOSED.value
                        )

                    mode_str = "SIMULATED"
                    color = Colors.GREEN if pnl >= 0 else Colors.RED
                    self.log(
                        f"[{mode_str}] Closed {side.upper()} @ {current_price:.4f} "
                        f"PnL: {color}${pnl:+.2f} ({pnl_percent:+.1f}%){Colors.RESET}",
                        "success" if pnl >= 0 else "warning"
                    )
            else:
                # LIVE mode: schedule an async sell execution task that will perform
                # the actual order placement and update the DB when done.
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._execute_close_live(side, current_price, pos_info, db_id, reason="period_end"))
                except RuntimeError:
                    # No running loop: try to schedule via asyncio.ensure_future
                    asyncio.ensure_future(self._execute_close_live(side, current_price, pos_info, db_id, reason="period_end"))

            # cleanup peak tracker
            if side in self._position_peak_price:
                del self._position_peak_price[side]

        # 清空持仓记录 locally; DB will be updated by tasks in LIVE mode
        self._active_positions.clear()
        self._current_period_orders.clear()

    async def _execute_close_live(self, side: str, exit_price: float, pos_info: Dict, db_id: Optional[int], reason: str = "") -> None:
        """Execute a LIVE SELL to close a position and update the DB afterwards."""
        # Ensure bot exists
        if not self.bot:
            self.log("Error: Bot not initialized for LIVE closing", "error")
            return

        token_id = pos_info.get("token_id") or self.token_ids.get(side)
        size = pos_info.get("size", 0)
        entry_price = pos_info.get("entry_price", 0)


        # 市价卖出逻辑：优先用盘口买一价（best_bid），无则降级为0.01
        from asyncio import sleep
        max_retries = 10
        retry = 0
        
        # 任务61: 获取配置参数
        use_gtc = getattr(self.config, 'strategy3_use_gtc_order', True)
        sell_discount = getattr(self.config, 'strategy3_sell_discount', 0.03)
        order_type = 'GTC' if use_gtc else 'FOK'
        
        # 任务59: 增加详细的调试日志
        self.log(f"[DEBUG] _execute_close_live started for {side.upper()}, token_id={token_id}, size={size}", "info")
        self.log(f"[DEBUG] Order config: use_gtc={use_gtc}, sell_discount={sell_discount}, order_type={order_type}", "info")
        
        while retry < max_retries:
            # 用更安全的方式获取卖出价格
            sell_price = await self.get_safe_sell_price(token_id, side)
            
            # 任务59: 记录原始返回的价格
            self.log(f"[DEBUG] get_safe_sell_price returned: {sell_price} (type: {type(sell_price).__name__})", "info")

            # 任务58补充: 确保价格在有效范围内 (0 < price < 1)
            if sell_price <= 0 or sell_price >= 1:
                self.log(f"[WARN] Invalid sell_price {sell_price}, using fallback 0.01", "warning")
                sell_price = 0.01
            
            # 任务61: 应用卖出价格折扣（使用GTC挂单时，降低价格以确保成交）
            if use_gtc and sell_discount > 0:
                original_price = sell_price
                sell_price = round(sell_price * (1 - sell_discount), 2)
                sell_price = max(0.01, sell_price)  # 确保最低价格
                self.log(f"[DEBUG] Applied sell discount: {original_price:.4f} -> {sell_price:.4f} (-{sell_discount*100:.0f}%)", "info")
            
            # Ensure size precision matches maker/taker rules (2 decimals for taker_amount)
            try:
                rounded_size = round(float(size), 2)
                if rounded_size <= 0:
                    self.log(f"Error: Invalid size {size} for {side.upper()}, cannot place SELL", "error")
                    return
            except Exception as e:
                self.log(f"Error: Failed to round size {size}: {e}", "error")
                return

            self.log(f"[LIVE] Placing close SELL {side.upper()} @ {sell_price:.4f} size={rounded_size:.2f} (reason: {reason}, retry={retry}, type={order_type})", "trade")


            try:
                # 获取当前市场真实费率
                fee_rate_bps = 1000
                if hasattr(self, 'market') and self.market and self.market.current_market:
                    # Polymarket 15m市场通常只有一个fee，直接取raw数据
                    raw = self.market.current_market.raw if hasattr(self.market.current_market, 'raw') else None
                    if raw and 'takerFeeBps' in raw:
                        fee_rate_bps = int(raw['takerFeeBps'])
                # side参数用当前订单方向
                # 任务61: 使用配置的订单类型 (GTC或FOK)
                result = await self.bot.place_order(
                    token_id=token_id,
                    price=sell_price,
                    size=rounded_size,
                    side='SELL',
                    order_type=order_type,
                    fee_rate_bps=fee_rate_bps
                )

                if result.success:
                    self.log(f"[LIVE] Close SELL placed for {side.upper()} (order={result.order_id}, type={order_type})", "success")
                    break
                else:
                    self.log(f"[LIVE] Close SELL failed for {side.upper()}: {result.message}", "error")
            except Exception as e:
                self.log(f"[LIVE] Exception placing close SELL for {side.upper()}: {e}", "error")

            retry += 1
            await sleep(2)  # 等待2秒后重试，盘口可能有变化

        if retry == max_retries:
            self.log(f"[LIVE] 市价卖出重试{max_retries}次仍未成功，建议人工干预！", "error")

        # Update DB with exit info regardless of order success (use provided exit_price)
        if exit_price and entry_price and db_id:
            pnl = (exit_price - entry_price) * size
            pnl_percent = (exit_price - entry_price) / entry_price * 100
            
            # 获取反弹趋势记录 (任务56)
            rebound_trend = self._get_rebound_trend_summary(side)
            
            self.db.update_rebound_order_result(
                order_id=db_id,
                exit_price=exit_price,
                exit_btc_price=self.btc_price_current,
                pnl=pnl,
                pnl_percent=pnl_percent,
                status=OrderStatus.CLOSED.value,
                rebound_trend=rebound_trend
            )
            color = Colors.GREEN if pnl >= 0 else Colors.RED
            trend_info = f" [Trend: {rebound_trend}]" if rebound_trend else ""
            self.log(
                f"[REAL] Closed {side.upper()} @ {exit_price:.4f} PnL: {color}${pnl:+.2f} ({pnl_percent:+.1f}%){Colors.RESET} {reason}{trend_info}",
                "success" if pnl >= 0 else "warning"
            )

    def _close_position(self, side: str, exit_price: float, reason: str = "") -> None:
        """Close a single position and update DB/logs."""
        pos_info = self._active_positions.get(side)
        if not pos_info:
            return

        entry_price = pos_info.get("entry_price", 0)
        size = pos_info.get("size", 0)
        db_id = pos_info.get("db_id")

        if self.config.simulation_mode:
            # synchronous simulated close
            if exit_price > 0 and entry_price > 0:
                pnl = (exit_price - entry_price) * size
                pnl_percent = (exit_price - entry_price) / entry_price * 100

                if db_id:
                    # 获取反弹趋势记录 (任务56)
                    rebound_trend = self._get_rebound_trend_summary(side)
                    
                    self.db.update_rebound_order_result(
                        order_id=db_id,
                        exit_price=exit_price,
                        exit_btc_price=self.btc_price_current,
                        pnl=pnl,
                        pnl_percent=pnl_percent,
                        status=OrderStatus.CLOSED.value,
                        rebound_trend=rebound_trend
                    )

                mode_str = "SIMULATED"
                color = Colors.GREEN if pnl >= 0 else Colors.RED
                trend_info = f" [Trend: {self._get_rebound_trend_summary(side)}]" if self._rebound_trend_records.get(side) else ""
                self.log(
                    f"[{mode_str}] Closed {side.upper()} @ {exit_price:.4f} PnL: {color}${pnl:+.2f} ({pnl_percent:+.1f}%){Colors.RESET} {reason}{trend_info}",
                    "success" if pnl >= 0 else "warning"
                )

        else:
            # LIVE mode: schedule async sell and DB update via helper
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._execute_close_live(side, exit_price, pos_info, db_id, reason=reason))
            except RuntimeError:
                asyncio.ensure_future(self._execute_close_live(side, exit_price, pos_info, db_id, reason=reason))

        # 任务56补充：将关闭的订单信息保存到 _closed_positions_for_trend
        # 这样可以继续记录趋势直到15分钟结束
        if db_id and entry_price > 0:
            self._closed_positions_for_trend[side] = {
                "db_id": db_id,
                "entry_price": entry_price
            }
            self.log(f"[TREND] Will continue tracking {side.upper()} trend until period end", "debug")

        # cleanup local state
        if side in self._position_peak_price:
            del self._position_peak_price[side]
        if side in self._active_positions:
            del self._active_positions[side]

    def _evaluate_positions_for_profit_and_loss(self) -> None:
        """Evaluate open positions for take-profit or stop-loss rules (strategy 3)."""
        # For each active position, update peak price and evaluate rules
        for side, pos in list(self._active_positions.items()):
            current_price = self.prices.get_current_price(side)
            if current_price <= 0:
                continue

            entry = pos.get("entry_price", 0)
            if entry <= 0:
                continue

            # update peak
            peak = self._position_peak_price.get(side, entry)
            if current_price > peak:
                peak = current_price
                self._position_peak_price[side] = peak

            # check take-profit base eligibility
            # profit_percent as decimal (e.g., 0.8 means +80%)
            profit_percent = (current_price - entry) / entry
            if not pos.get("_tp_eligible") and profit_percent >= self.config.strategy3_take_profit_base:
                # mark eligible when reached base TP
                pos["_tp_eligible"] = True
                self.log(f"Position {side.upper()} reached strategy3_take_profit_base ({profit_percent:.2%}), eligible for TP", "info")

            # if eligible, wait for pullback from peak by reduce_loss fraction
            if pos.get("_tp_eligible"):
                # peak-to-current drawdown fraction
                if peak > 0:
                    drawdown = (peak - current_price) / peak
                    if drawdown >= self.config.strategy3_take_profit_pullback:
                        # Sell to take profit
                        self.log(f"Take-profit trigger for {side.upper()}: peak={peak:.4f}, current={current_price:.4f}, drawdown={drawdown:.2%}", "success")
                        self._close_position(side, current_price, reason="strategy3_take_profit")
                        continue

            # Stop-loss check (任务58: 为A段添加紧急止损保护)
            segment = self.get_current_segment()
            loss_frac = (entry - current_price) / entry
            
            # A段: 更宽松的紧急止损 (35%)
            if segment == "A" and loss_frac >= self.config.strategy3_stop_loss_stage_a:
                self.log(f"Stage A emergency stop-loss for {side.upper()}: loss={loss_frac:.2%}", "error")
                self._close_position(side, current_price, reason="strategy3_stop_loss_stage_a")
                continue
            
            # B和C段: 常规止损 (20%)
            if segment in ["B", "C"] and loss_frac >= self.config.strategy3_stop_loss_stage_bc:
                self.log(f"Stage {segment} stop-loss for {side.upper()}: loss={loss_frac:.2%}", "warning")
                self._close_position(side, current_price, reason=f"strategy3_stop_loss_stage_{segment.lower()}")
    
    def _reset_for_new_period(self) -> None:
        """为新的15分钟周期重置状态"""
        # 在关闭持仓前，保存当前价格（旧市场的最后价格）
        # 这样可以确保使用正确的价格计算PnL
        last_prices: Dict[str, float] = {}
        for side in ["up", "down"]:
            price = self.prices.get_current_price(side)
            if price > 0:
                last_prices[side] = price
        
        # 任务56补充：在周期结束时，更新所有订单的最终反弹趋势
        # 这包括活跃持仓和已提前关闭的持仓
        self._save_final_rebound_trends()
        
        # 使用旧市场的最后价格关闭现有持仓
        self._close_all_positions(use_prices=last_prices if last_prices else None)
        
        # 重置价格历史
        self._price_history = {"up": [], "down": []}
        
        # 重置反弹趋势记录 (任务56)
        self._rebound_trend_records = {"up": [], "down": []}
        self._last_trend_record_time = 0
        
        # 重置已关闭订单的趋势跟踪 (任务56补充)
        self._closed_positions_for_trend.clear()
        
        # 重置BTC开始价格
        self.btc_price_start = self.btc_price_current
        
        # 重置周期开始时间
        self._market_start_time = time.time()
        self._period_start_prices.clear()
        
        self.log("New 15-minute period started", "info")
    
    async def _check_trigger_conditions(self) -> None:
        """检查触发条件并执行交易"""
        segment = self.get_current_segment()
        if segment not in self.config.active_segments:
            return
        
        # Only place new orders in configured order_segments
        if segment not in self.config.order_segments:
            return

        # 检查是否已有持仓
        if len(self._active_positions) > 0:
            return

        # Ensure only one new order per 15-minute period
        if self._current_period_orders:
            # already placed an order this period
            return
        
        # 任务65: 检查订单计划
        if self.config.order_schedule_enabled:
            env = "sim" if self.config.simulation_mode else "prod"
            should_trade = self.db.check_should_trade(
                env=env,
                strategy_type=self.config.strategy_type
            )
            if not should_trade:
                return
        
        # 检查BTC条件
        if not self._check_btc_condition():
            return
        
        # 检测UP和DOWN的快速下跌
        for side in ["up", "down"]:
            drop_info = self._detect_rapid_drop(side)
            if drop_info:
                start_price, current_price, drop = drop_info
                
                self.log(
                    f"Rapid drop detected: {side.upper()} "
                    f"{start_price:.4f} -> {current_price:.4f} (drop={drop:.4f})",
                    "warning"
                )
                
                # 构建触发信息
                trigger_info = {
                    "segment": segment,
                    "up_price": self.prices.get_current_price("up"),
                    "down_price": self.prices.get_current_price("down"),
                    f"{side}_drop": drop,
                    "btc_drop": (self.btc_price_start - self.btc_price_current) 
                               if self.btc_price_start and self.btc_price_current else 0
                }
                
                # 执行交易
                await self._execute_trade(side, trigger_info)
                break  # 只交易一个方向
    
    def _render_status(self) -> None:
        """渲染状态显示"""
        lines = []
        
        # Header
        ws_status = f"{Colors.GREEN}Connected{Colors.RESET}" if self.is_connected else f"{Colors.RED}Disconnected{Colors.RESET}"
        market = self.current_market
        countdown = "--:--"
        segment = "N/A"
        if market:
            mins, secs = market.get_countdown()
            countdown = format_countdown(mins, secs)
            segment = self.get_current_segment() or "N/A"
        
        mode_str = f"{Colors.YELLOW}SIMULATION{Colors.RESET}" if self.config.simulation_mode else f"{Colors.GREEN}LIVE{Colors.RESET}"
        
        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
        lines.append(
            f"{Colors.CYAN}Rebound Strategy{Colors.RESET} | {self.config.coin} | "
            f"{ws_status} | Mode: {mode_str}"
        )
        lines.append(f"Countdown: {countdown} | Segment: {segment}")
        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
        
        # BTC价格
        if self.config.coin == "BTC" and self.btc_price_start:
            btc_drop = (self.btc_price_start - (self.btc_price_current or 0)) 
            color = Colors.GREEN if btc_drop <= 0 else Colors.RED
            lines.append(
                f"BTC: Start=${self.btc_price_start:,.2f} | "
                f"Current={color}${self.btc_price_current:,.2f}{Colors.RESET} | "
                f"Drop={color}${btc_drop:+.2f}{Colors.RESET}"
            )
            lines.append("")
        
        # 当前价格
        up_price = self.prices.get_current_price("up")
        down_price = self.prices.get_current_price("down")
        lines.append(f"UP: {Colors.GREEN}{up_price:.4f}{Colors.RESET} | DOWN: {Colors.RED}{down_price:.4f}{Colors.RESET}")
        lines.append(f"Drop Threshold: < {self.config.price_drop_threshold:.2f}")
        lines.append("")
        
        # 持仓信息
        lines.append(f"{Colors.BOLD}Active Positions:{Colors.RESET}")
        if self._active_positions:
            for side, pos in self._active_positions.items():
                current = self.prices.get_current_price(side)
                entry = pos.get("entry_price", 0)
                size = pos.get("size", 0)
                pnl = (current - entry) * size if current > 0 else 0
                pnl_pct = (current - entry) / entry * 100 if entry > 0 else 0
                color = Colors.GREEN if pnl >= 0 else Colors.RED
                lines.append(
                    f"  {side.upper()}: Entry={entry:.4f} | Current={current:.4f} | "
                    f"PnL={color}${pnl:+.2f} ({pnl_pct:+.1f}%){Colors.RESET}"
                )
        else:
            lines.append(f"  {Colors.CYAN}(no positions){Colors.RESET}")
        
        # 数据库统计
        if self.db.is_connected:
            stats = self.db.get_rebound_orders_stats(
                coin=self.config.coin, 
                is_simulated=self.config.simulation_mode,
                days=7
            )
            if stats:
                lines.append("")
                lines.append(f"{Colors.BOLD}7-Day Stats ({mode_str}):{Colors.RESET}")
                lines.append(
                    f"  Orders: {stats.get('total_orders', 0)} | "
                    f"Closed: {stats.get('closed_orders', 0)} | "
                    f"Win Rate: {stats.get('win_rate', 0):.1f}%"
                )
                lines.append(
                    f"  Total PnL: ${stats.get('total_pnl', 0):.2f} | "
                    f"Avg PnL: ${stats.get('avg_pnl', 0):.2f}"
                )
        
        # 日志
        if self._log_buffer.messages:
            lines.append("")
            lines.append(f"{Colors.BOLD}Recent Events:{Colors.RESET}")
            for msg in self._log_buffer.get_messages()[-5:]:
                lines.append(f"  {msg}")
        
        # 渲染
        output = "\033[H\033[J" + "\n".join(lines)
        print(output, flush=True)
    
    async def run(self) -> None:
        """运行策略"""
        self.running = True
        
        mode_str = "SIMULATION" if self.config.simulation_mode else "LIVE"
        self.log(f"Starting Rebound Strategy in {mode_str} mode for {self.config.coin}", "info")
        
        # 注册回调
        @self.market.on_book_update
        async def handle_book(snapshot: OrderbookSnapshot):
            for side, token_id in self.token_ids.items():
                if token_id == snapshot.asset_id:
                    self.prices.record(side, snapshot.mid_price)
                    self._record_price(side, snapshot.mid_price)
                    
                    # 记录周期开始价格
                    if side not in self._period_start_prices:
                        self._period_start_prices[side] = snapshot.mid_price
                    # evaluate P&L rules for strategy 3
                    if self.config.profit_and_loss_enabled and self.config.strategy_type == "3":
                        self._evaluate_positions_for_profit_and_loss()
                    break
        
        @self.market.on_market_change
        def on_market_change(old_slug: str, new_slug: str):
            self.log(f"Market changed: {old_slug} -> {new_slug}", "warning")
            self._reset_for_new_period()
        
        # 启动市场管理器
        if not await self.market.start():
            self.log("Failed to start market manager", "error")
            return
        
        await self.market.wait_for_data(timeout=5.0)
        self._market_start_time = time.time()
        
        try:
            while self.running:
                # 更新BTC价格
                self._update_btc_price()
                
                # 检查触发条件
                await self._check_trigger_conditions()
                
                # Profit & Loss evaluation (strategy 3)
                if self.config.profit_and_loss_enabled and self.config.strategy_type == "3":
                    self._evaluate_positions_for_profit_and_loss()
                
                # 记录反弹趋势 (任务56)
                self._record_rebound_trend()
                
                # 检查auto-claim（仅在真实模式下）
                await self._check_auto_claim()
                
                # 渲染状态
                self._render_status()
                
                await asyncio.sleep(self.config.update_interval)
                
        except KeyboardInterrupt:
            self.log("Strategy stopped by user", "info")
        finally:
            # 关闭所有持仓
            self._close_all_positions()
            await self.market.stop()
            self._print_summary()
    
    async def _check_auto_claim(self) -> None:
        """检查并执行自动claim"""
        if not self._auto_claimer:
            return
        
        now = time.time()
        if now - self._last_claim_check < self.config.auto_claim_check_interval:
            return
        
        self._last_claim_check = now
        
        try:
            # 首先检查余额
            balance = self._auto_claimer.get_usdc_balance()
            
            if balance < self.config.auto_claim_min_balance:
                self.log(f"Balance ${balance:.2f} < ${self.config.auto_claim_min_balance}, checking for redeemable positions...", "warning")
                
                # 获取可redeem的仓位
                positions = self._auto_claimer.get_redeemable_positions()
                
                if positions:
                    self.log(f"Found {len(positions)} redeemable positions, claiming...", "info")
                    
                    for pos in positions:
                        success = await self._auto_claimer.redeem_position(pos)
                        if success:
                            self.log(f"Claimed: {pos.title} ({pos.outcome}) - ${pos.current_value:.2f}", "success")
                        else:
                            self.log(f"Failed to claim: {pos.title}", "error")
                    
                    # 更新余额显示
                    new_balance = self._auto_claimer.get_usdc_balance()
                    self.log(f"New balance: ${new_balance:.2f}", "info")
                else:
                    self.log("No redeemable positions found", "info")
        except Exception as e:
            self.log(f"Auto-claim error: {e}", "error")
    
    def _print_summary(self) -> None:
        """打印会话统计"""
        print()
        mode_str = "SIMULATION" if self.config.simulation_mode else "LIVE"
        self.log(f"Session Summary ({mode_str} mode):")
        
        if self.db.is_connected:
            stats = self.db.get_rebound_orders_stats(
                coin=self.config.coin,
                is_simulated=self.config.simulation_mode,
                days=1  # 今天的统计
            )
            self.log(f"  Today's Orders: {stats.get('total_orders', 0)}")
            self.log(f"  Closed: {stats.get('closed_orders', 0)}")
            self.log(f"  Win Rate: {stats.get('win_rate', 0):.1f}%")
            self.log(f"  Total PnL: ${stats.get('total_pnl', 0):.2f}")
