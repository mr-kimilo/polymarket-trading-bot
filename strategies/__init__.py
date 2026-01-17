"""
Strategies - Trading Strategy Implementations

This package contains trading strategy implementations:

- base: Base class for all strategies
- flash_crash: Flash crash volatility strategy
- rebound: Rebound strategy for rapid price drops in 15-minute markets

Usage:
    from strategies.base import BaseStrategy, StrategyConfig
    from strategies.flash_crash import FlashCrashStrategy, FlashCrashConfig
    from strategies.rebound import ReboundStrategy, ReboundConfig
"""

from strategies.base import BaseStrategy, StrategyConfig
from strategies.flash_crash import FlashCrashStrategy, FlashCrashConfig
from strategies.rebound import ReboundStrategy, ReboundConfig

__all__ = [
    "BaseStrategy",
    "StrategyConfig",
    "FlashCrashStrategy",
    "FlashCrashConfig",
    "ReboundStrategy",
    "ReboundConfig",
]
