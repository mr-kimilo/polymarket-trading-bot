"""
Tests for Task 14: Fix BUY order fill verification in _execute_trade().

Instructions used: [clean-architecture.instructions.md, unit-and-integration-tests.instructions.md,
                    coding-style-python.instructions.md]

Root causes fixed:
1. GTC BUY order submission success ≠ order filled. result.success only means the order
   was accepted by CLOB, not that it was matched/filled.
2. No fill verification after placing GTC buy orders - code treated CLOB acceptance
   as fill confirmation, inserting DB records for unfilled positions.
3. No cancellation and retry with higher price when BUY order doesn't fill.
4. DB entry_price used mid_price instead of actual fill price.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
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
    )
    mock_bot = MagicMock()
    mock_bot.get_order = AsyncMock()
    mock_bot.place_order = AsyncMock()
    mock_bot.cancel_order = AsyncMock()
    mock_bot.clob_client = MagicMock()

    strategy = ReboundStrategy(bot=mock_bot, config=config)
    strategy.db = MagicMock()
    strategy.db.create_rebound_order = MagicMock(return_value=1)
    strategy.log = MagicMock()
    strategy.btc_price_current = 90000.0
    strategy.btc_price_start = 90050.0
    # Mock market.token_ids property
    strategy.market = MagicMock()
    strategy.market.token_ids = {"up": "token_up", "down": "token_down"}
    strategy.market.current_market = MagicMock()
    strategy.market.current_market.slug = "test-market"
    # Mock prices
    strategy.prices = MagicMock()
    strategy.prices.get_current_price = MagicMock(return_value=0.30)
    strategy._get_rebound_trend_summary = MagicMock(return_value=None)
    return strategy


def _make_order_result(success: bool = True, order_id: str = "ord_buy_1", status: str = "live"):
    from src.bot import OrderResult
    return OrderResult(success=success, order_id=order_id, status=status, message="ok")


class TestBuyFillVerification:
    """Test BUY order fill verification in _execute_trade."""

    @pytest.mark.asyncio
    async def test_buy_fills_immediately(self):
        """BUY order that fills on first attempt should succeed."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": True, "size_matched": 10.0, "status": "matched"}
        )

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        strategy.bot.place_order.assert_called_once()
        strategy._wait_for_order_fill.assert_called_once()
        strategy.db.create_rebound_order.assert_called_once()
        # Active position should be created
        assert "up" in strategy._active_positions

    @pytest.mark.asyncio
    async def test_buy_not_filled_cancels_and_retries(self):
        """BUY not filled → cancel → retry with higher price."""
        strategy = _make_strategy()

        # First attempt: accepted but not filled. Second attempt: filled.
        strategy.bot.place_order.side_effect = [
            _make_order_result(order_id="ord_1"),
            _make_order_result(order_id="ord_2"),
        ]
        strategy._wait_for_order_fill = AsyncMock(side_effect=[
            {"filled": False, "size_matched": 0, "status": "timeout"},
            {"filled": True, "size_matched": 10.0, "status": "matched"},
        ])
        strategy.bot.cancel_order.return_value = MagicMock(success=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        assert strategy.bot.place_order.call_count == 2
        strategy.bot.cancel_order.assert_called_once_with("ord_1")

    @pytest.mark.asyncio
    async def test_buy_all_retries_fail_returns_false(self):
        """When all retry attempts fail, should return False and record buy_failed."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": False, "size_matched": 0, "status": "timeout"}
        )
        strategy.bot.cancel_order.return_value = MagicMock(success=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is False
        # 4 attempts total (1 initial + 3 retries)
        assert strategy.bot.place_order.call_count == 4
        # buy_failed DB record should be created
        failed_order = strategy.db.create_rebound_order.call_args[0][0]
        assert failed_order.status == "buy_failed"
        # No active position
        assert "up" not in strategy._active_positions

    @pytest.mark.asyncio
    async def test_buy_progressive_premium_increases(self):
        """Each retry should use progressively higher buy price."""
        strategy = _make_strategy()
        strategy.prices.get_current_price.return_value = 0.30

        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": False, "size_matched": 0, "status": "timeout"}
        )
        strategy.bot.cancel_order.return_value = MagicMock(success=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        # Extract buy prices from place_order calls
        prices = [call.kwargs["price"] for call in strategy.bot.place_order.call_args_list]

        # Prices should be: 0.32, 0.34, 0.36, 0.38
        # (current_price=0.30 + premium where premium = 0.02 + attempt * 0.02)
        assert len(prices) == 4
        for i in range(1, len(prices)):
            assert prices[i] > prices[i - 1], \
                f"Price at attempt {i+1} ({prices[i]}) should be > attempt {i} ({prices[i-1]})"

    @pytest.mark.asyncio
    async def test_buy_price_capped_at_0_99(self):
        """Buy price should never exceed 0.99 even with premium."""
        strategy = _make_strategy()
        strategy.prices.get_current_price.return_value = 0.98

        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": False, "size_matched": 0, "status": "timeout"}
        )
        strategy.bot.cancel_order.return_value = MagicMock(success=True)

        trigger_info = {"segment": "A", "up_price": 0.98, "down_price": 0.02, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        prices = [call.kwargs["price"] for call in strategy.bot.place_order.call_args_list]
        for p in prices:
            assert p <= 0.99, f"Buy price {p} should be capped at 0.99"

    @pytest.mark.asyncio
    async def test_buy_order_rejected_returns_false_immediately(self):
        """If CLOB rejects the order (result.success=False), return False without retry."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = _make_order_result(success=False)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is False
        # Only one attempt since order was rejected
        strategy.bot.place_order.assert_called_once()
        # No DB insert for rejected orders (not even buy_failed)
        strategy.db.create_rebound_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_entry_price_updated_to_fill_price(self):
        """DB and active_positions should use fill price, not mid_price."""
        strategy = _make_strategy()
        strategy.prices.get_current_price.return_value = 0.30

        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": True, "size_matched": 10.0, "status": "matched"}
        )

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        # buy_price = min(0.30 + 0.02, 0.99) = 0.32
        saved_order = strategy.db.create_rebound_order.call_args[0][0]
        assert saved_order.entry_price == 0.32  # fill price, not mid_price 0.30

        # Active position entry price should also be the fill price
        assert strategy._active_positions["up"]["entry_price"] == 0.32

    @pytest.mark.asyncio
    async def test_simulation_mode_skips_fill_verification(self):
        """Simulation mode should not place orders or verify fills."""
        strategy = _make_strategy(simulation_mode=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        strategy.bot.place_order.assert_not_called()
        # DB should still be inserted with simulated status
        strategy.db.create_rebound_order.assert_called_once()
        saved_order = strategy.db.create_rebound_order.call_args[0][0]
        assert saved_order.is_simulated is True

    @pytest.mark.asyncio
    async def test_strategy3_pnl_tracking_uses_fill_price(self):
        """Strategy 3 P&L peak price should use actual fill price."""
        strategy = _make_strategy(strategy_type="3")
        strategy.prices.get_current_price.return_value = 0.25

        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": True, "size_matched": 10.0, "status": "matched"}
        )

        trigger_info = {"segment": "A", "up_price": 0.25, "down_price": 0.75, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        # buy_price = min(0.25 + 0.02, 0.99) = 0.27
        assert strategy._position_peak_price["up"] == 0.27

    @pytest.mark.asyncio
    async def test_cancel_failure_does_not_block_retry(self):
        """If cancel fails, retry should still proceed."""
        strategy = _make_strategy()
        strategy.bot.place_order.side_effect = [
            _make_order_result(order_id="ord_1"),
            _make_order_result(order_id="ord_2"),
        ]
        strategy._wait_for_order_fill = AsyncMock(side_effect=[
            {"filled": False, "size_matched": 0, "status": "timeout"},
            {"filled": True, "size_matched": 10.0, "status": "matched"},
        ])
        strategy.bot.cancel_order.side_effect = Exception("cancel API error")

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        assert strategy.bot.place_order.call_count == 2

    @pytest.mark.asyncio
    async def test_no_bot_in_live_mode_returns_false(self):
        """Live mode without bot should return False."""
        strategy = _make_strategy(simulation_mode=False)
        strategy.bot = None

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is False
