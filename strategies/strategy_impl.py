"""
Strategy Implementations - 具体策略实现 (任务57重构)

包含三种策略：
- Strategy1: A段反弹策略 (UP/DOWN<30%, BTC下跌<$50)
- Strategy2: C段反弹策略 (UP/DOWN<15%, BTC下跌<$30)
- Strategy3: 动态止盈止损策略 (带P&L管理)
"""

from typing import Dict, Tuple, Optional
from .base_rebound import BaseReboundStrategy, BaseReboundConfig, PriceRecord


class Strategy1(BaseReboundStrategy):
    """
    策略1: A段反弹策略
    
    触发条件：
    - 在A段（15-10分钟）
    - UP/DOWN价格跌破30%
    - BTC价格下跌不超过$50
    
    持仓：持有到15分钟结束
    """
    
    def __init__(self, bot, config: BaseReboundConfig):
        # 确保配置正确
        config.active_segments = ["A"]
        config.order_segments = ["A"]
        config.price_drop_threshold = 0.30
        config.btc_drop_max = 50.0
        super().__init__(bot, config)
    
    def should_enter_trade(self, side: str, segment: str) -> Tuple[bool, Dict]:
        """策略1入场条件"""
        if segment != "A":
            return False, {}
        
        # 检查是否已有持仓
        if self._active_positions:
            return False, {}
        
        # 检查本周期是否已下单
        if self._current_period_orders:
            return False, {}
        
        # 获取当前价格
        current_price = self.prices.get_current_price(side)
        if current_price <= 0:
            return False, {}
        
        # 检查价格是否跌破阈值
        if current_price >= self.config.price_drop_threshold:
            return False, {}
        
        # 检查BTC条件
        if not self._check_btc_condition():
            return False, {}
        
        # 检测快速下跌（1分钟内）
        if not self._detect_rapid_drop(side):
            return False, {}
        
        trigger_info = {
            "current_price": current_price,
            "threshold": self.config.price_drop_threshold,
            "btc_drop": (self.btc_price_start or 0) - (self.btc_price_current or 0),
        }
        
        return True, trigger_info
    
    def should_exit_trade(self, side: str, segment: str, position: Dict) -> Tuple[bool, str, float]:
        """策略1出场条件 - 持有到周期结束"""
        # 策略1不主动出场，等待周期结束
        return False, "", 0.0
    
    def _check_btc_condition(self) -> bool:
        """检查BTC价格条件"""
        if self.btc_price_start is None or self.btc_price_current is None:
            return True
        drop = self.btc_price_start - self.btc_price_current
        return drop <= self.config.btc_drop_max
    
    def _detect_rapid_drop(self, side: str) -> bool:
        """检测快速下跌"""
        history = self._price_history.get(side, [])
        if len(history) < 2:
            return False
        
        now = history[-1].timestamp
        window_start = now - self.config.rapid_drop_window
        
        # 找到窗口内的最高价
        window_prices = [r.price for r in history if r.timestamp >= window_start]
        if not window_prices:
            return False
        
        max_price = max(window_prices)
        current_price = history[-1].price
        
        # 检查是否从高价快速下跌
        if max_price > self.config.price_drop_threshold and current_price < self.config.price_drop_threshold:
            return True
        
        return False


class Strategy2(BaseReboundStrategy):
    """
    策略2: C段反弹策略
    
    触发条件：
    - 在C段（5-0分钟）
    - UP/DOWN价格跌破15%
    - BTC价格下跌不超过$30
    """
    
    def __init__(self, bot, config: BaseReboundConfig):
        config.active_segments = ["C"]
        config.order_segments = ["C"]
        config.price_drop_threshold = 0.15
        config.btc_drop_max = 30.0
        super().__init__(bot, config)
    
    def should_enter_trade(self, side: str, segment: str) -> Tuple[bool, Dict]:
        """策略2入场条件"""
        if segment != "C":
            return False, {}
        
        if self._active_positions or self._current_period_orders:
            return False, {}
        
        current_price = self.prices.get_current_price(side)
        if current_price <= 0 or current_price >= self.config.price_drop_threshold:
            return False, {}
        
        if not self._check_btc_condition():
            return False, {}
        
        if not self._detect_rapid_drop(side):
            return False, {}
        
        return True, {
            "current_price": current_price,
            "threshold": self.config.price_drop_threshold,
        }
    
    def should_exit_trade(self, side: str, segment: str, position: Dict) -> Tuple[bool, str, float]:
        """策略2出场条件 - 持有到周期结束"""
        return False, "", 0.0
    
    def _check_btc_condition(self) -> bool:
        if self.btc_price_start is None or self.btc_price_current is None:
            return True
        drop = self.btc_price_start - self.btc_price_current
        return drop <= self.config.btc_drop_max
    
    def _detect_rapid_drop(self, side: str) -> bool:
        history = self._price_history.get(side, [])
        if len(history) < 2:
            return False
        
        now = history[-1].timestamp
        window_start = now - self.config.rapid_drop_window
        window_prices = [r.price for r in history if r.timestamp >= window_start]
        
        if not window_prices:
            return False
        
        max_price = max(window_prices)
        current_price = history[-1].price
        
        if max_price > self.config.price_drop_threshold and current_price < self.config.price_drop_threshold:
            return True
        
        return False


class Strategy3(BaseReboundStrategy):
    """
    策略3: 动态止盈止损策略 (任务60/61)
    
    入场：根据数据库配置的stage_buy决定（A/B/C段）
    出场：动态止盈止损
    - 止盈：盈利达到基准后，回撤到一定比例卖出
    - 止损：B/C段亏损达到阈值卖出
    
    支持从数据库动态加载参数 (任务60)
    任务61: 支持配置A/B/C任意阶段买入
    """
    
    def __init__(self, bot, config: BaseReboundConfig):
        config.active_segments = ["A", "B", "C"]
        config.order_segments = ["A"]  # 默认A段，会从数据库动态更新
        config.profit_and_loss_enabled = True
        super().__init__(bot, config)
        
        # 动态参数 (任务60)
        self._dynamic_params: Optional[Dict] = None
        self._last_params_check: float = 0
        self._params_check_interval: float = 60.0  # 每分钟检查一次
        
        # 加载初始参数 (包括stage_buy)
        self.load_dynamic_params()
    
    def should_enter_trade(self, side: str, segment: str) -> Tuple[bool, Dict]:
        """
        策略3入场条件 (任务61)
        
        根据数据库中的stage_buy配置决定在哪个阶段下单
        - stage_buy="A": 只在A段下单
        - stage_buy="B": 只在B段下单
        - stage_buy="C": 只在C段下单
        - stage_buy="A,B": 在A或B段下单
        - stage_buy="A,B,C": 在任意阶段下单
        """
        # 获取允许下单的阶段
        allowed_segments = self._get_allowed_order_segments()
        
        # 检查当前阶段是否允许下单
        if segment not in allowed_segments:
            return False, {}
        
        if self._active_positions or self._current_period_orders:
            return False, {}
        
        # 使用动态参数或配置参数
        threshold = self._get_param("price_down_percentage", self.config.price_drop_threshold)
        btc_drop_max = self._get_param("price_down", self.config.btc_drop_max)
        
        current_price = self.prices.get_current_price(side)
        if current_price <= 0 or current_price >= threshold:
            return False, {}
        
        # 检查BTC条件
        if self.btc_price_start and self.btc_price_current:
            btc_drop = self.btc_price_start - self.btc_price_current
            if btc_drop > btc_drop_max:
                return False, {}
        
        if not self._detect_rapid_drop(side, threshold):
            return False, {}
        
        return True, {
            "current_price": current_price,
            "threshold": threshold,
            "btc_drop_max": btc_drop_max,
            "stage_buy": self._get_param("stage_buy", "A"),
        }
    
    def should_exit_trade(self, side: str, segment: str, position: Dict) -> Tuple[bool, str, float]:
        """策略3出场条件 - 动态止盈止损"""
        current_price = self.prices.get_current_price(side)
        if current_price <= 0:
            return False, "", 0.0
        
        entry_price = position.get("entry_price", 0)
        if entry_price <= 0:
            return False, "", 0.0
        
        # 获取动态参数
        take_profit_base = self._get_param("take_profit", self.config.strategy3_take_profit_base)
        stop_loss = self._get_param("stop_loss", self.config.strategy3_stop_loss_stage_bc)
        
        # 计算盈亏比例
        profit_pct = (current_price - entry_price) / entry_price
        
        # 更新峰值价格
        peak_price = self._position_peak_price.get(side, entry_price)
        if current_price > peak_price:
            peak_price = current_price
            self._position_peak_price[side] = peak_price
        
        # 止盈检查
        if profit_pct >= take_profit_base:
            # 已达到止盈基准，检查回撤
            peak_profit = (peak_price - entry_price) / entry_price
            pullback = peak_profit - profit_pct
            
            if pullback >= self.config.strategy3_take_profit_pullback:
                return True, "take_profit", current_price
        
        # 止损检查 (B/C段)
        if segment in ["B", "C"]:
            loss_pct = -profit_pct
            if loss_pct >= stop_loss:
                return True, f"stop_loss_{segment.lower()}", current_price
        
        # A段紧急止损
        if segment == "A":
            loss_pct = -profit_pct
            if loss_pct >= self.config.strategy3_stop_loss_stage_a:
                return True, "emergency_stop_loss_a", current_price
        
        return False, "", 0.0
    
    def _detect_rapid_drop(self, side: str, threshold: float) -> bool:
        """检测快速下跌"""
        history = self._price_history.get(side, [])
        if len(history) < 2:
            return False
        
        now = history[-1].timestamp
        window_start = now - self.config.rapid_drop_window
        window_prices = [r.price for r in history if r.timestamp >= window_start]
        
        if not window_prices:
            return False
        
        max_price = max(window_prices)
        current_price = history[-1].price
        
        if max_price > threshold and current_price < threshold:
            return True
        
        return False
    
    # ==================== 动态参数 (任务60/61) ====================
    
    def _get_allowed_order_segments(self) -> list:
        """
        获取允许下单的阶段列表 (任务61)
        
        从数据库stage_buy字段解析，支持：
        - "A" -> ["A"]
        - "B" -> ["B"]
        - "C" -> ["C"]
        - "A,B" -> ["A", "B"]
        - "A,B,C" -> ["A", "B", "C"]
        
        Returns:
            允许下单的阶段列表
        """
        stage_buy = self._get_param("stage_buy", "A")
        
        # 如果是字符串，按逗号分割
        if isinstance(stage_buy, str):
            segments = [s.strip().upper() for s in stage_buy.split(",")]
            # 过滤有效的阶段
            valid_segments = [s for s in segments if s in ["A", "B", "C"]]
            return valid_segments if valid_segments else ["A"]
        
        # 如果已经是列表
        if isinstance(stage_buy, list):
            return [s.upper() for s in stage_buy if s.upper() in ["A", "B", "C"]]
        
        # 默认返回A
        return ["A"]
    
    def _get_param(self, param_name: str, default_value) -> any:
        """
        获取动态参数或默认值 (任务60)
        
        Args:
            param_name: 参数名
            default_value: 默认值
            
        Returns:
            参数值
        """
        if self._dynamic_params:
            return self._dynamic_params.get(param_name, default_value)
        return default_value
    
    def load_dynamic_params(self) -> bool:
        """
        从数据库加载动态参数 (任务60/61)
        
        加载的参数包括：
        - stage_buy: 买入阶段 (A/B/C)
        - price_down_percentage: 价格下跌百分比
        - price_down: BTC价格下跌阈值
        - take_profit: 止盈比例
        - stop_loss: 止损比例
        
        Returns:
            是否成功加载
        """
        try:
            params = self.db.get_active_strategy3_rule(
                env="production" if not self.config.simulation_mode else "simulate"
            )
            if params:
                self._dynamic_params = params
                
                # 更新config的order_segments (任务61)
                stage_buy = params.get("stage_buy", "A")
                allowed_segments = self._get_allowed_order_segments()
                self.config.order_segments = allowed_segments
                
                self.log(f"[DYNAMIC] Loaded params: stage_buy={stage_buy}, "
                        f"order_segments={allowed_segments}, "
                        f"threshold={params.get('price_down_percentage')}, "
                        f"btc_drop={params.get('price_down')}, "
                        f"take_profit={params.get('take_profit')}, "
                        f"stop_loss={params.get('stop_loss')}", "info")
                return True
            return False
        except Exception as e:
            self.log(f"[DYNAMIC] Failed to load params: {e}", "warning")
            return False
    
    def check_and_reload_params(self) -> None:
        """检查并重新加载参数"""
        import time
        now = time.time()
        if now - self._last_params_check >= self._params_check_interval:
            self._last_params_check = now
            self.load_dynamic_params()


class StrategyFactory:
    """
    策略工厂 (任务57)
    
    根据策略类型创建对应的策略实例
    """
    
    _strategies = {
        "1": Strategy1,
        "2": Strategy2,
        "3": Strategy3,
    }
    
    @classmethod
    def create(cls, strategy_type: str, bot, config: BaseReboundConfig) -> BaseReboundStrategy:
        """
        创建策略实例
        
        Args:
            strategy_type: 策略类型 ("1", "2", "3")
            bot: TradingBot实例
            config: 策略配置
            
        Returns:
            策略实例
        """
        strategy_class = cls._strategies.get(strategy_type)
        if not strategy_class:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        config.strategy_type = strategy_type
        return strategy_class(bot, config)
    
    @classmethod
    def get_available_strategies(cls) -> list:
        """获取可用策略类型列表"""
        return list(cls._strategies.keys())
    
    @classmethod
    def register_strategy(cls, strategy_type: str, strategy_class: type) -> None:
        """注册新策略"""
        cls._strategies[strategy_type] = strategy_class
