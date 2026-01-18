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
    
    # 基础配置
    coin: str = "BTC"
    size: float = 10.0  # USDC交易金额
    
    # 触发条件
    price_drop_threshold: float = 0.30  # UP/DOWN价格跌破30%
    btc_drop_max: float = 50.0  # BTC最大下跌幅度（美元）
    rapid_drop_window: int = 60  # 快速下跌检测窗口（秒）
    
    # 时间段定义（分钟数）
    segment_a_start: int = 15  # A段开始（倒计时）
    segment_a_end: int = 10    # A段结束
    segment_b_start: int = 10  # B段开始
    segment_b_end: int = 5     # B段结束
    segment_c_start: int = 5   # C段开始
    segment_c_end: int = 0     # C段结束
    
    # 只在A段触发交易
    active_segments: List[str] = field(default_factory=lambda: ["A"])
    
    # 模拟模式
    simulation_mode: bool = True  # 默认启用模拟模式
    
    # 市场设置
    market_check_interval: float = 30.0
    auto_switch_market: bool = True
    
    # 显示设置
    update_interval: float = 0.5
    
    # Auto-claim设置
    auto_claim_enabled: bool = True  # 是否启用自动claim
    auto_claim_min_balance: float = 10.0  # 最小余额阈值（USDC）
    auto_claim_check_interval: int = 300  # 检查间隔（秒，默认5分钟）


@dataclass 
class PriceRecord:
    """价格记录用于检测快速下跌"""
    timestamp: float
    price: float


class ReboundStrategy:
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
        
        # 市场开始时间
        self._market_start_time: Optional[float] = None
        self._period_start_prices: Dict[str, float] = {}
        
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
            token_id=token_id
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
            
            mode_str = "SIMULATED" if self.config.simulation_mode else "REAL"
            self.log(
                f"[{mode_str}] Opened {side.upper()} position @ {current_price:.4f} "
                f"(size={size:.2f}, segment={trigger_info.get('segment')})",
                "trade"
            )
            return True
        
        return False
    
    def _close_all_positions(self, use_prices: Optional[Dict[str, float]] = None) -> None:
        """
        关闭所有持仓并更新数据库
        在15分钟周期结束时调用
        
        Args:
            use_prices: 可选，指定用于计算PnL的价格。
                       如果不提供，则使用当前价格追踪器中的价格。
                       用于市场切换时，使用旧市场的最后价格。
        """
        for side, pos_info in list(self._active_positions.items()):
            # 优先使用传入的价格（旧市场的最后价格）
            if use_prices and side in use_prices:
                current_price = use_prices[side]
            else:
                current_price = self.prices.get_current_price(side)
            
            entry_price = pos_info.get("entry_price", 0)
            size = pos_info.get("size", 0)
            db_id = pos_info.get("db_id")
            
            if current_price > 0 and entry_price > 0:
                pnl = (current_price - entry_price) * size
                pnl_percent = (current_price - entry_price) / entry_price * 100
                
                # 更新数据库
                if db_id:
                    self.db.update_rebound_order_result(
                        order_id=db_id,
                        exit_price=current_price,
                        exit_btc_price=self.btc_price_current,
                        pnl=pnl,
                        pnl_percent=pnl_percent,
                        status=OrderStatus.CLOSED.value
                    )
                
                mode_str = "SIMULATED" if self.config.simulation_mode else "REAL"
                color = Colors.GREEN if pnl >= 0 else Colors.RED
                self.log(
                    f"[{mode_str}] Closed {side.upper()} @ {current_price:.4f} "
                    f"PnL: {color}${pnl:+.2f} ({pnl_percent:+.1f}%){Colors.RESET}",
                    "success" if pnl >= 0 else "warning"
                )
        
        # 清空持仓
        self._active_positions.clear()
        self._current_period_orders.clear()
    
    def _reset_for_new_period(self) -> None:
        """为新的15分钟周期重置状态"""
        # 在关闭持仓前，保存当前价格（旧市场的最后价格）
        # 这样可以确保使用正确的价格计算PnL
        last_prices: Dict[str, float] = {}
        for side in ["up", "down"]:
            price = self.prices.get_current_price(side)
            if price > 0:
                last_prices[side] = price
        
        # 使用旧市场的最后价格关闭现有持仓
        self._close_all_positions(use_prices=last_prices if last_prices else None)
        
        # 重置价格历史
        self._price_history = {"up": [], "down": []}
        
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
        
        # 检查是否已有持仓
        if len(self._active_positions) > 0:
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
