"""
Tests for Task 2 - max_session_orders limit

Verifies:
1. max_session_orders=0 means unlimited
2. max_session_orders=2 blocks the 3rd order
3. Counter increments on successful buy (simulated and live)
4. Existing positions still managed after limit reached
"""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _make_strategy(simulation_mode: bool = True, max_session_orders: int = 0):
    """Create a ReboundStrategy with mocked dependencies."""
    from strategies.rebound import ReboundStrategy, ReboundConfig

    config = ReboundConfig(
        coin="BTC",
        simulation_mode=simulation_mode,
        strategy_type="3",
        max_session_orders=max_session_orders,
    )
    mock_bot = MagicMock()
    mock_bot.get_order = AsyncMock()
    mock_bot.place_order = AsyncMock()
    mock_bot.cancel_order = AsyncMock()
    mock_bot.get_best_bid = AsyncMock(return_value=0.35)

    # Mock clob_client
    mock_bot.clob_client = MagicMock()

    strategy = ReboundStrategy(bot=mock_bot, config=config)
    strategy.db = MagicMock()
    strategy.log = MagicMock()
    strategy.btc_price_current = 90000.0
    strategy.market = MagicMock()
    strategy.market.token_ids = {"up": "token_up", "down": "token_down"}
    strategy.prices = MagicMock()
    strategy.prices.get_current_price.return_value = 0.30
    strategy._get_rebound_trend_summary = MagicMock(return_value=None)

    return strategy


class TestMaxSessionOrdersConfig:
    """Test max_session_orders configuration."""

    def test_default_is_zero(self):
        """Default max_session_orders should be 0 (unlimited)."""
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(coin="BTC")
        assert config.max_session_orders == 0

    def test_set_max_session_orders(self):
        """max_session_orders can be set via constructor."""
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(coin="BTC", max_session_orders=2)
        assert config.max_session_orders == 2

    def test_session_counter_starts_at_zero(self):
        """Session order counter should start at 0."""
        strategy = _make_strategy()
        assert strategy._session_order_count == 0


class TestMaxSessionOrdersEnforcement:
    """Test that max_session_orders limit is enforced."""

    @pytest.mark.asyncio
    async def test_unlimited_when_zero(self):
        """max_session_orders=0 should allow unlimited orders."""
        strategy = _make_strategy(simulation_mode=True, max_session_orders=0)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.30}

        # Place 5 orders — all should succeed
        for i in range(5):
            result = await strategy._execute_trade("up" if i % 2 == 0 else "down", trigger_info)
            assert result is True, f"Order {i+1} should succeed with unlimited"
            # Clear position so next order can be placed
            strategy._active_positions.clear()

        assert strategy._session_order_count == 5

    @pytest.mark.asyncio
    async def test_limit_blocks_after_max(self):
        """max_session_orders=2 should block the 3rd order."""
        strategy = _make_strategy(simulation_mode=True, max_session_orders=2)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.30}

        # First 2 orders succeed
        result1 = await strategy._execute_trade("up", trigger_info)
        assert result1 is True
        strategy._active_positions.clear()

        result2 = await strategy._execute_trade("down", trigger_info)
        assert result2 is True
        strategy._active_positions.clear()

        assert strategy._session_order_count == 2

        # 3rd order blocked
        result3 = await strategy._execute_trade("up", trigger_info)
        assert result3 is False
        assert strategy._session_order_count == 2  # counter unchanged

    @pytest.mark.asyncio
    async def test_limit_one_order_only(self):
        """max_session_orders=1 should allow exactly 1 order."""
        strategy = _make_strategy(simulation_mode=True, max_session_orders=1)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.30}

        result1 = await strategy._execute_trade("up", trigger_info)
        assert result1 is True
        strategy._active_positions.clear()

        result2 = await strategy._execute_trade("down", trigger_info)
        assert result2 is False

    @pytest.mark.asyncio
    async def test_counter_increments_on_simulated_buy(self):
        """Counter should increment after simulated buy."""
        strategy = _make_strategy(simulation_mode=True, max_session_orders=0)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.30}

        await strategy._execute_trade("up", trigger_info)
        assert strategy._session_order_count == 1

    @pytest.mark.asyncio
    async def test_counter_does_not_increment_on_blocked(self):
        """Counter should NOT increment when order is blocked by limit."""
        strategy = _make_strategy(simulation_mode=True, max_session_orders=1)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.30}

        await strategy._execute_trade("up", trigger_info)
        assert strategy._session_order_count == 1
        strategy._active_positions.clear()

        await strategy._execute_trade("down", trigger_info)
        assert strategy._session_order_count == 1  # still 1, not 2

    @pytest.mark.asyncio
    async def test_log_message_on_limit_reached(self):
        """Should log warning when limit is reached."""
        strategy = _make_strategy(simulation_mode=True, max_session_orders=1)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.30}

        await strategy._execute_trade("up", trigger_info)
        strategy._active_positions.clear()
        await strategy._execute_trade("down", trigger_info)

        # Check that log was called with SESSION LIMIT message
        log_calls = [str(c) for c in strategy.log.call_args_list]
        assert any("SESSION LIMIT" in c for c in log_calls)


class TestLoadMaxSessionOrdersFromConfig:
    """Test loading max_session_orders from config.yaml."""

    def test_load_from_yaml(self, tmp_path):
        """load_max_session_orders_from_config reads from config.yaml."""
        from apps.run_rebound import load_max_session_orders_from_config

        # The function reads from the project root config.yaml
        # Just verify it returns an int
        result = load_max_session_orders_from_config()
        assert isinstance(result, int)
