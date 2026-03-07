"""
Tests for Task 15: Order schedule strategy_type filtering and market price buy/sell.

Instructions used: [clean-architecture.instructions.md, unit-and-integration-tests.instructions.md,
                    coding-style-python.instructions.md]

Changes:
1. Order schedule queries must filter by strategy_type - verified existing behavior
2. get_safe_sell_price() now prioritizes orderbook best_bid for market-like sell
3. New get_safe_buy_price() uses orderbook best_ask for market-like buy
4. _execute_trade() BUY uses get_safe_buy_price() instead of fixed premium
5. _render_status() shows schedule status for all strategy types
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_strategy(simulation_mode: bool = False, strategy_type: str = "3"):
    """Create a ReboundStrategy instance with mocked dependencies."""
    from strategies.rebound import ReboundStrategy, ReboundConfig

    config = ReboundConfig(
        coin="BTC",
        simulation_mode=simulation_mode,
        strategy_type=strategy_type,
        auto_claim_enabled=False,
        order_schedule_enabled=True,
    )
    mock_bot = MagicMock()
    mock_bot.get_order = AsyncMock()
    mock_bot.place_order = AsyncMock()
    mock_bot.cancel_order = AsyncMock()
    mock_bot.clob_client = MagicMock()

    strategy = ReboundStrategy(bot=mock_bot, config=config)
    strategy.db = MagicMock()
    strategy.db.create_rebound_order = MagicMock(return_value=1)
    strategy.db.check_should_trade = MagicMock(return_value=True)
    strategy.log = MagicMock()
    strategy.btc_price_current = 90000.0
    strategy.btc_price_start = 90050.0
    strategy.market = MagicMock()
    strategy.market.token_ids = {"up": "token_up", "down": "token_down"}
    strategy.market.current_market = MagicMock()
    strategy.market.current_market.slug = "test-market"
    strategy.prices = MagicMock()
    strategy.prices.get_current_price = MagicMock(return_value=0.30)
    strategy._get_rebound_trend_summary = MagicMock(return_value=None)
    return strategy


def _make_order_result(success: bool = True, order_id: str = "ord_1", status: str = "live"):
    from src.bot import OrderResult
    return OrderResult(success=success, order_id=order_id, status=status, message="ok")


class TestScheduleStrategyTypeFiltering:
    """Test that order_schedule checks include strategy_type."""

    def test_is_weekday_strict_passes_strategy_type(self):
        """_is_weekday_strict should pass self.config.strategy_type to check_should_trade."""
        strategy = _make_strategy(strategy_type="3")
        strategy.config.weekday_strict_enabled = True
        strategy.db.check_should_trade = MagicMock(return_value=True)

        result = strategy._is_weekday_strict()

        strategy.db.check_should_trade.assert_called_once_with("prod", "3")
        assert result is False  # has_schedule=True → not strict

    def test_is_weekday_strict_strategy1(self):
        """Strategy 1 should also pass its own strategy_type."""
        strategy = _make_strategy(strategy_type="1")
        strategy.config.weekday_strict_enabled = True
        strategy.db.check_should_trade = MagicMock(return_value=False)

        result = strategy._is_weekday_strict()

        strategy.db.check_should_trade.assert_called_once_with("prod", "1")
        assert result is True  # no schedule → strict

    @pytest.mark.asyncio
    async def test_schedule_check_in_trigger_conditions_uses_strategy_type(self):
        """_check_trigger_conditions schedule check should pass the correct strategy_type."""
        strategy = _make_strategy(strategy_type="3")
        strategy.config.order_schedule_enabled = True
        strategy.db.check_should_trade = MagicMock(return_value=False)  # no schedule

        # Mock segment and other conditions
        strategy.get_current_segment = MagicMock(return_value="A")
        strategy.config.active_segments = ["A", "B", "C"]
        strategy._get_allowed_order_segments = MagicMock(return_value=["A"])
        strategy._active_positions = {}
        strategy._current_period_orders = []

        await strategy._check_trigger_conditions()

        # Should have called check_should_trade with strategy_type="3"
        strategy.db.check_should_trade.assert_called_with(env="prod", strategy_type="3")

    def test_sim_mode_passes_sim_env(self):
        """Simulation mode should pass 'sim' as env."""
        strategy = _make_strategy(simulation_mode=True, strategy_type="3")
        strategy.config.weekday_strict_enabled = True
        strategy.db.check_should_trade = MagicMock(return_value=True)

        strategy._is_weekday_strict()

        strategy.db.check_should_trade.assert_called_once_with("sim", "3")

    def test_weekday_info_includes_schedule_for_strategy3(self):
        """_get_weekday_info should include has_schedule for strategy 3."""
        strategy = _make_strategy(strategy_type="3")
        strategy.config.weekday_strict_enabled = True
        strategy.db.check_should_trade = MagicMock(return_value=True)

        info = strategy._get_weekday_info()

        assert "has_schedule" in info
        assert info["has_schedule"] is True
        strategy.db.check_should_trade.assert_called_with("prod", "3")


class TestGetSafeBuyPrice:
    """Test get_safe_buy_price method for market-like buying."""

    @pytest.mark.asyncio
    async def test_uses_best_ask_from_orderbook(self):
        """Should use the best ask (lowest ask) from orderbook as buy price."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {
            "bids": [{"price": "0.25", "size": "100"}],
            "asks": [
                {"price": "0.32", "size": "50"},
                {"price": "0.35", "size": "100"},
                {"price": "0.30", "size": "200"},
            ],
        }

        price = await strategy.get_safe_buy_price("token_123", "up")

        assert price == 0.30  # best ask = min(0.32, 0.35, 0.30) = 0.30

    @pytest.mark.asyncio
    async def test_falls_back_to_midpoint(self):
        """Should fall back to midpoint + tick when orderbook has no asks."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {"bids": [], "asks": []}
        strategy.bot.clob_client.get_midpoint.return_value = 0.28

        price = await strategy.get_safe_buy_price("token_123", "up")

        assert price == 0.29  # midpoint 0.28 + tick 0.01

    @pytest.mark.asyncio
    async def test_falls_back_to_last_trade(self):
        """Should fall back to last trade price when midpoint also unavailable."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {"bids": [], "asks": []}
        strategy.bot.clob_client.get_midpoint.return_value = 0.0
        strategy.bot.clob_client.get_last_trade_price.return_value = 0.27

        price = await strategy.get_safe_buy_price("token_123", "up")

        assert price == 0.28  # last trade 0.27 + tick 0.01

    @pytest.mark.asyncio
    async def test_falls_back_to_websocket_price(self):
        """Should fall back to WebSocket price + premium when all else fails."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.side_effect = Exception("API error")
        strategy.bot.clob_client.get_midpoint.side_effect = Exception("API error")
        strategy.bot.clob_client.get_last_trade_price.side_effect = Exception("API error")
        strategy.market.get_orderbook = MagicMock(return_value=None)
        strategy.prices.get_current_price = MagicMock(return_value=0.25)

        price = await strategy.get_safe_buy_price("token_123", "up")

        assert price == 0.27  # 0.25 + 0.02 fallback premium

    @pytest.mark.asyncio
    async def test_no_clob_client_uses_fallback(self):
        """Without clob_client, should use WebSocket price + premium."""
        strategy = _make_strategy()
        strategy.bot.clob_client = None
        strategy.prices.get_current_price = MagicMock(return_value=0.40)

        price = await strategy.get_safe_buy_price("token_123", "up")

        assert price == pytest.approx(0.42, abs=0.001)  # 0.40 + 0.02

    @pytest.mark.asyncio
    async def test_price_capped_at_099(self):
        """Buy price should not exceed 0.99."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {
            "bids": [],
            "asks": [{"price": "0.99", "size": "100"}],
        }

        price = await strategy.get_safe_buy_price("token_123", "up")

        assert price == 0.99

    @pytest.mark.asyncio
    async def test_adjusts_to_tick_size(self):
        """Price should be adjusted to nearest tick size."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {
            "bids": [],
            "asks": [{"price": "0.325", "size": "100"}],  # Not aligned to 0.01
        }

        price = await strategy.get_safe_buy_price("token_123", "up")

        # 0.325 rounded up to nearest 0.01 → 0.33
        assert price == 0.33


class TestGetSafeSellPrice:
    """Test get_safe_sell_price prioritizes best bid for market-like sell."""

    @pytest.mark.asyncio
    async def test_uses_best_bid_first(self):
        """Should use the best bid from orderbook as primary price source."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {
            "bids": [
                {"price": "0.25", "size": "100"},
                {"price": "0.28", "size": "50"},
                {"price": "0.20", "size": "200"},
            ],
            "asks": [{"price": "0.32", "size": "100"}],
        }

        price = await strategy.get_safe_sell_price("token_123", "up")

        assert price == 0.28  # best bid = max(0.25, 0.28, 0.20) = 0.28

    @pytest.mark.asyncio
    async def test_falls_back_to_midpoint_when_no_bids(self):
        """Should fall back to midpoint - tick when no valid bids."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {"bids": [], "asks": []}
        strategy.bot.clob_client.get_midpoint.return_value = 0.30

        price = await strategy.get_safe_sell_price("token_123", "up")

        assert price == 0.29  # midpoint 0.30 - tick 0.01

    @pytest.mark.asyncio
    async def test_falls_back_to_last_trade(self):
        """Should fall back to last trade price when midpoint unavailable."""
        strategy = _make_strategy()
        strategy.bot.clob_client.get_tick_size.return_value = "0.01"
        strategy.bot.clob_client.get_order_book.return_value = {"bids": [], "asks": []}
        strategy.bot.clob_client.get_midpoint.return_value = 0.0
        strategy.bot.clob_client.get_last_trade_price.return_value = 0.27

        price = await strategy.get_safe_sell_price("token_123", "up")

        assert price == 0.26  # last trade 0.27 - tick 0.01

    @pytest.mark.asyncio
    async def test_no_clob_client_returns_001(self):
        """Without clob_client, should return fallback price 0.01."""
        strategy = _make_strategy()
        strategy.bot.clob_client = None

        price = await strategy.get_safe_sell_price("token_123", "up")

        assert price == 0.01


class TestExecuteTradeUsesMarketPrice:
    """Test that _execute_trade uses get_safe_buy_price for market-like buying."""

    @pytest.mark.asyncio
    async def test_buy_uses_get_safe_buy_price(self):
        """BUY should call get_safe_buy_price to get market price."""
        strategy = _make_strategy()
        strategy.get_safe_buy_price = AsyncMock(return_value=0.28)
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": True, "size_matched": 10.0, "status": "matched"}
        )
        strategy.bot.place_order.return_value = _make_order_result()

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        strategy.get_safe_buy_price.assert_called()
        # Verify the order was placed at the market price, not current + premium
        call_kwargs = strategy.bot.place_order.call_args
        assert call_kwargs.kwargs["price"] == 0.28

    @pytest.mark.asyncio
    async def test_buy_retry_adds_premium_to_market_price(self):
        """On retry, buy price should be market_price + retry_increment."""
        strategy = _make_strategy()
        strategy.get_safe_buy_price = AsyncMock(return_value=0.28)

        # First attempt fails, second succeeds
        strategy._wait_for_order_fill = AsyncMock(
            side_effect=[
                {"filled": False, "size_matched": 0, "status": "live"},
                {"filled": True, "size_matched": 10.0, "status": "matched"},
            ]
        )
        strategy.bot.place_order.return_value = _make_order_result()
        strategy.bot.cancel_order = AsyncMock()

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        # First call: market price 0.28
        first_call = strategy.bot.place_order.call_args_list[0]
        assert first_call.kwargs["price"] == 0.28
        # Second call: market price 0.28 + 0.02 premium = 0.30
        second_call = strategy.bot.place_order.call_args_list[1]
        assert second_call.kwargs["price"] == pytest.approx(0.30, abs=0.001)

    @pytest.mark.asyncio
    async def test_simulation_mode_does_not_call_buy_price(self):
        """Simulation mode should not call get_safe_buy_price."""
        strategy = _make_strategy(simulation_mode=True)
        strategy.get_safe_buy_price = AsyncMock(return_value=0.28)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        strategy.get_safe_buy_price.assert_not_called()


class TestRenderStatusScheduleDisplay:
    """Test that _render_status shows schedule info for all strategy types."""

    def test_renders_schedule_active_for_strategy3(self):
        """Schedule status should be shown for strategy 3 when schedule is active."""
        strategy = _make_strategy(strategy_type="3")
        strategy.config.order_schedule_enabled = True
        strategy.db.check_should_trade = MagicMock(return_value=True)
        # is_connected is a property delegating to market.is_connected
        strategy.market.is_connected = True
        strategy.market.current_market = MagicMock()
        strategy.market.current_market.get_countdown.return_value = (10, 30)
        strategy.get_current_segment = MagicMock(return_value="A")
        strategy.db.is_connected = False
        strategy._auto_claimer = None
        strategy._log_buffer = MagicMock()
        strategy._log_buffer.messages = []

        # Capture print output
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            strategy._render_status()
        output = f.getvalue()

        assert "Schedule:" in output
        assert "Strategy 3" in output
        assert "在计划交易时间内" in output

    def test_renders_schedule_inactive_for_strategy3(self):
        """Should show inactive schedule for strategy 3."""
        strategy = _make_strategy(strategy_type="3")
        strategy.config.order_schedule_enabled = True
        strategy.db.check_should_trade = MagicMock(return_value=False)
        strategy.market.is_connected = True
        strategy.market.current_market = MagicMock()
        strategy.market.current_market.get_countdown.return_value = (10, 30)
        strategy.get_current_segment = MagicMock(return_value="A")
        strategy.db.is_connected = False
        strategy._auto_claimer = None
        strategy._log_buffer = MagicMock()
        strategy._log_buffer.messages = []

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            strategy._render_status()
        output = f.getvalue()

        assert "Schedule:" in output
        assert "Strategy 3" in output
        assert "不在计划交易时间内" in output

    def test_no_schedule_display_when_disabled(self):
        """Should not show schedule status when order_schedule_enabled is False."""
        strategy = _make_strategy(strategy_type="3")
        strategy.config.order_schedule_enabled = False
        strategy.market.is_connected = True
        strategy.market.current_market = MagicMock()
        strategy.market.current_market.get_countdown.return_value = (10, 30)
        strategy.get_current_segment = MagicMock(return_value="A")
        strategy.db.is_connected = False
        strategy._auto_claimer = None
        strategy._log_buffer = MagicMock()
        strategy._log_buffer.messages = []

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            strategy._render_status()
        output = f.getvalue()

        assert "Schedule:" not in output
