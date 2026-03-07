"""
Tests for Task 13: Fix TP/SL order fill verification.

Instructions used: [clean-architecture.instructions.md, unit-and-integration-tests.instructions.md,
                    coding-style-python.instructions.md]

Root causes fixed:
1. GTC order submission success ≠ order filled. result.success only means the order
   was accepted by CLOB, not that it was matched. The GTC order may sit on the book unfilled.
2. No order fill verification after placing GTC sell orders.
3. No cancellation of stale GTC orders when they don't fill in time.
4. DB updated with trigger price instead of actual fill price.
5. Progressive price discount on retries to increase fill probability.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_strategy(simulation_mode: bool = False, strategy_type: str = "3"):
    """Create a ReboundStrategy instance with mocked dependencies."""
    from strategies.rebound import ReboundStrategy, ReboundConfig

    config = ReboundConfig(
        coin="BTC",
        simulation_mode=simulation_mode,
        strategy_type=strategy_type,
        strategy3_use_gtc_order=True,
        strategy3_sell_discount=0.03,
        auto_claim_enabled=False,  # Disable auto-claim in tests
    )
    mock_bot = MagicMock()
    mock_bot.get_order = AsyncMock()
    mock_bot.place_order = AsyncMock()
    mock_bot.cancel_order = AsyncMock()
    
    # Mock clob_client for get_safe_sell_price
    mock_bot.clob_client = MagicMock()
    
    strategy = ReboundStrategy(bot=mock_bot, config=config)
    strategy.db = MagicMock()
    strategy.log = MagicMock()
    strategy.btc_price_current = 90000.0
    # Mock market.token_ids property
    strategy.market = MagicMock()
    strategy.market.token_ids = {"up": "token_up", "down": "token_down"}
    strategy._get_rebound_trend_summary = MagicMock(return_value=None)
    return strategy


class TestWaitForOrderFill:
    """Test _wait_for_order_fill polling logic."""

    @pytest.mark.asyncio
    async def test_immediately_matched_order(self):
        """Order with status=matched should return filled=True immediately."""
        strategy = _make_strategy()
        strategy.bot.get_order.return_value = {
            "status": "matched",
            "size_matched": "10.0",
            "original_size": "10.0",
        }

        result = await strategy._wait_for_order_fill("order123", timeout=5.0, poll_interval=0.1)

        assert result["filled"] is True
        assert result["status"] == "matched"

    @pytest.mark.asyncio
    async def test_order_not_found_means_filled(self):
        """Order not found (None) likely means fully matched and removed."""
        strategy = _make_strategy()
        strategy.bot.get_order.return_value = None

        result = await strategy._wait_for_order_fill("order123", timeout=5.0, poll_interval=0.1)

        assert result["filled"] is True
        assert result["status"] == "matched"

    @pytest.mark.asyncio
    async def test_live_order_times_out(self):
        """Order still 'live' after timeout returns filled=False."""
        strategy = _make_strategy()
        strategy.bot.get_order.return_value = {
            "status": "live",
            "size_matched": "0",
            "original_size": "10.0",
        }

        result = await strategy._wait_for_order_fill("order123", timeout=0.3, poll_interval=0.1)

        assert result["filled"] is False
        assert result["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_full_size_matched_returns_filled(self):
        """When size_matched == original_size, order is fully filled."""
        strategy = _make_strategy()
        strategy.bot.get_order.return_value = {
            "status": "live",
            "size_matched": "5.0",
            "original_size": "5.0",
        }

        result = await strategy._wait_for_order_fill("order123", timeout=5.0, poll_interval=0.1)

        assert result["filled"] is True
        assert result["size_matched"] == 5.0

    @pytest.mark.asyncio
    async def test_delayed_then_matched(self):
        """Order starts as 'delayed' then becomes 'matched'."""
        strategy = _make_strategy()
        strategy.bot.get_order.side_effect = [
            {"status": "delayed", "size_matched": "0", "original_size": "10.0"},
            {"status": "matched", "size_matched": "10.0", "original_size": "10.0"},
        ]

        result = await strategy._wait_for_order_fill("order123", timeout=5.0, poll_interval=0.1)

        assert result["filled"] is True

    @pytest.mark.asyncio
    async def test_api_error_continues_polling(self):
        """API errors during polling should not stop the loop."""
        strategy = _make_strategy()
        strategy.bot.get_order.side_effect = [
            Exception("API error"),
            {"status": "matched", "size_matched": "10.0", "original_size": "10.0"},
        ]

        result = await strategy._wait_for_order_fill("order123", timeout=5.0, poll_interval=0.1)

        assert result["filled"] is True


class TestExecuteCloseLiveWithFillVerification:
    """Test _execute_close_live with GTC fill verification."""

    def _make_order_result(self, success: bool = True, order_id: str = "ord_123", status: str = "live"):
        from src.bot import OrderResult
        return OrderResult(success=success, order_id=order_id, status=status, message="ok")

    @pytest.mark.asyncio
    async def test_gtc_order_immediately_matched(self):
        """GTC order with status='matched' skips polling and succeeds."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = self._make_order_result(status="matched")
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should have placed the order once and not polled
        strategy.bot.place_order.assert_called_once()
        strategy.bot.get_order.assert_not_called()
        # DB should be updated with sell price (not exit_price since it was filled)
        strategy.db.update_rebound_order_result.assert_called_once()
        call_kwargs = strategy.db.update_rebound_order_result.call_args
        assert call_kwargs[1]["status"] == "closed"

    @pytest.mark.asyncio
    async def test_gtc_order_polls_and_fills(self):
        """GTC order placed as 'live', polls and finds 'matched'."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = self._make_order_result(status="live")
        strategy.bot.get_order.return_value = {
            "status": "matched",
            "size_matched": "10.0",
            "original_size": "10.0",
        }
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should have polled the order
        strategy.bot.get_order.assert_called()
        # DB status should be 'closed'
        call_kwargs = strategy.db.update_rebound_order_result.call_args
        assert call_kwargs[1]["status"] == "closed"

    @pytest.mark.asyncio
    async def test_gtc_order_not_filled_cancels_and_retries(self):
        """GTC order not filled → cancel → retry with more aggressive price."""
        strategy = _make_strategy()

        # First attempt: placed as live, polling times out
        # Second attempt: immediately matched
        strategy.bot.place_order.side_effect = [
            self._make_order_result(status="live", order_id="ord_1"),
            self._make_order_result(status="matched", order_id="ord_2"),
        ]
        strategy.bot.get_order.return_value = {
            "status": "live",
            "size_matched": "0",
            "original_size": "10.0",
        }
        strategy.bot.cancel_order.return_value = MagicMock(success=True)
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        # Patch _wait_for_order_fill to simulate timeout on first call
        original_wait = strategy._wait_for_order_fill

        call_count = 0

        async def mock_wait(order_id, timeout=15.0, poll_interval=2.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"filled": False, "size_matched": 0, "status": "timeout"}
            return await original_wait(order_id, timeout, poll_interval)

        strategy._wait_for_order_fill = mock_wait

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should have cancelled the first unfilled order
        strategy.bot.cancel_order.assert_called_with("ord_1")
        # Should have placed 2 orders (first unfilled, second matched)
        assert strategy.bot.place_order.call_count == 2

    @pytest.mark.asyncio
    async def test_progressive_discount_increases_on_retries(self):
        """Each retry should apply a larger discount to increase fill probability."""
        strategy = _make_strategy()

        # All attempts fail
        strategy.bot.place_order.return_value = self._make_order_result(success=False)
        strategy.get_safe_sell_price = AsyncMock(return_value=0.50)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.50, pos_info, db_id=1, reason="tp")

        # Check that place_order was called max_retries times (10)
        assert strategy.bot.place_order.call_count == 10

        # Verify each call had progressively lower prices
        prices = [
            call.kwargs["price"] if "price" in call.kwargs else call.args[1]
            for call in strategy.bot.place_order.call_args_list
        ]
        # price keyword argument
        prices = []
        for c in strategy.bot.place_order.call_args_list:
            prices.append(c[1]["price"] if isinstance(c[1], dict) else c.kwargs["price"])

        # Each price should be <= the previous (progressively more aggressive)
        for i in range(1, len(prices)):
            assert prices[i] <= prices[i - 1], f"Price at retry {i} should be <= retry {i - 1}"

    @pytest.mark.asyncio
    async def test_db_status_sell_failed_when_no_fill(self):
        """When all retries fail, DB should have status='sell_failed'."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = self._make_order_result(success=False)
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # DB should be updated with status='sell_failed'
        call_kwargs = strategy.db.update_rebound_order_result.call_args
        assert call_kwargs[1]["status"] == "sell_failed"

    @pytest.mark.asyncio
    async def test_fok_order_skips_polling(self):
        """FOK orders should not poll for fill status - success means filled."""
        strategy = _make_strategy()
        strategy.config.strategy3_use_gtc_order = False

        strategy.bot.place_order.return_value = self._make_order_result(status="matched")
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should NOT poll order status for FOK
        strategy.bot.get_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_discount_capped_at_15_percent(self):
        """Discount should not exceed 15% regardless of retry count."""
        strategy = _make_strategy()
        strategy.config.strategy3_sell_discount = 0.10  # 10% base

        # Fail all attempts to check discount cap
        strategy.bot.place_order.return_value = self._make_order_result(success=False)
        strategy.get_safe_sell_price = AsyncMock(return_value=0.50)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.50, pos_info, db_id=1, reason="tp")

        # At retry 9 (last), discount = 0.10 + 9*0.02 = 0.28, capped at 0.15
        # So sell_price = 0.50 * (1 - 0.15) = 0.425 → rounded to 0.42
        last_call = strategy.bot.place_order.call_args_list[-1]
        last_price = last_call.kwargs.get("price", last_call[1].get("price") if isinstance(last_call[1], dict) else None)
        # Price should not be lower than 0.50 * 0.85 = 0.425
        assert last_price >= 0.42, f"Price {last_price} should be >= 0.42 (max 15% discount)"
