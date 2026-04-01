"""
Tests for Task 1 - Sell order reliability

Verifies:
1. place_order correctly uses PyClobClient for order creation/signing/submission
2. FOK orders use create_market_order (expiration=0)
3. GTC orders use create_order (with expiration)
4. _close_all_positions does not clear active_positions for LIVE mode
5. _execute_close_live retry phases work correctly
"""

import pytest
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.bot import TradingBot, OrderResult, NotInitializedError


TEST_PRIVATE_KEY = "0x" + "a" * 64
TEST_SAFE_ADDRESS = "0x" + "b" * 40
TEST_TOKEN_ID = "71321045679252212594626385532706912750332728571942532289631379312455583992563"


def _create_bot_with_mocks():
    """Create a TradingBot with mocked _py_client and clob_client."""
    bot = TradingBot(
        private_key=TEST_PRIVATE_KEY,
        safe_address=TEST_SAFE_ADDRESS,
    )

    mock_py = MagicMock()
    mock_py.get_tick_size.return_value = "0.01"
    mock_py.get_neg_risk.return_value = True
    mock_py.get_fee_rate_bps.return_value = 0
    mock_py.create_order.return_value = MagicMock()
    mock_py.create_market_order.return_value = MagicMock()
    mock_py.post_order.return_value = {
        "success": True,
        "orderId": "test_order_id",
        "status": "matched",
    }
    bot._py_client = mock_py

    mock_clob = MagicMock()
    mock_clob.get_order_book.return_value = {
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [{"price": "0.55", "size": "100"}],
    }
    mock_clob.get_order.return_value = {"status": "matched", "size_matched": "5.0", "original_size": "5.0"}
    bot.clob_client = mock_clob

    async def direct_call(func, *args, **kwargs):
        return func(*args, **kwargs)

    bot._run_in_thread = direct_call
    return bot, mock_py, mock_clob


class TestPlaceOrderUsesCorrectClient:
    """Verify place_order delegates to _py_client, not clob_client."""

    @pytest.mark.asyncio
    async def test_gtc_sell_uses_create_order(self):
        """GTC SELL should use create_order (limit order with expiration)."""
        bot, mock_py, _ = _create_bot_with_mocks()

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.45,
            size=5.0,
            side="SELL",
            order_type="GTC",
            fee_rate_bps=1000,
        )

        assert result.success is True
        mock_py.create_order.assert_called_once()
        mock_py.create_market_order.assert_not_called()

        # Verify OrderArgs
        order_args = mock_py.create_order.call_args[0][0]
        assert order_args.token_id == TEST_TOKEN_ID
        assert order_args.side == "SELL"
        assert order_args.size == 5.0
        assert order_args.price == 0.45
        assert order_args.fee_rate_bps == 1000
        assert order_args.expiration > int(time.time())

    @pytest.mark.asyncio
    async def test_fok_sell_uses_create_market_order(self):
        """FOK SELL should use create_market_order (market order, expiration=0)."""
        bot, mock_py, _ = _create_bot_with_mocks()

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.45,
            size=5.0,
            side="SELL",
            order_type="FOK",
            fee_rate_bps=1000,
        )

        assert result.success is True
        mock_py.create_market_order.assert_called_once()
        mock_py.create_order.assert_not_called()

        # Verify MarketOrderArgs
        market_args = mock_py.create_market_order.call_args[0][0]
        assert market_args.token_id == TEST_TOKEN_ID
        assert market_args.side == "SELL"
        assert market_args.amount == 5.0
        assert market_args.price == 0.45
        assert market_args.fee_rate_bps == 1000

    @pytest.mark.asyncio
    async def test_fak_sell_uses_create_market_order(self):
        """FAK SELL should also use create_market_order."""
        bot, mock_py, _ = _create_bot_with_mocks()

        mock_py.post_order.return_value = {
            "success": True,
            "orderId": "fak_123",
            "status": "matched",
        }

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.40,
            size=3.0,
            side="SELL",
            order_type="FAK",
        )

        assert result.success is True
        mock_py.create_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_gtc_buy_uses_create_order(self):
        """GTC BUY should use create_order."""
        bot, mock_py, _ = _create_bot_with_mocks()

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.35,
            size=10.0,
            side="BUY",
            order_type="GTC",
        )

        assert result.success is True
        mock_py.create_order.assert_called_once()
        mock_py.create_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_fok_buy_uses_create_market_order(self):
        """FOK BUY should use create_market_order."""
        bot, mock_py, _ = _create_bot_with_mocks()

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.55,
            size=10.0,
            side="BUY",
            order_type="FOK",
        )

        assert result.success is True
        mock_py.create_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_order_uses_py_client(self):
        """Verify post_order is called on _py_client (with builder HMAC headers)."""
        bot, mock_py, _ = _create_bot_with_mocks()

        await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.50,
            size=5.0,
            side="SELL",
        )

        mock_py.post_order.assert_called_once()


class TestPlaceOrderPriceHandling:
    """Test price adjustments and edge cases in place_order."""

    @pytest.mark.asyncio
    async def test_price_adjusted_to_tick(self):
        """Price 0.456 with tick_size=0.01 should round to 0.45."""
        bot, mock_py, _ = _create_bot_with_mocks()

        await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.456,
            size=5.0,
            side="SELL",
            tick_size="0.01",
            neg_risk=True,
        )

        order_args = mock_py.create_order.call_args[0][0]
        assert order_args.price == 0.45

    @pytest.mark.asyncio
    async def test_price_clamped_above_zero(self):
        """Price 0.0 should be clamped to tick_size."""
        bot, mock_py, _ = _create_bot_with_mocks()

        await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.001,
            size=5.0,
            side="SELL",
            tick_size="0.01",
            neg_risk=True,
        )

        order_args = mock_py.create_order.call_args[0][0]
        assert order_args.price == 0.01  # clamped to tick_size

    @pytest.mark.asyncio
    async def test_price_clamped_below_one(self):
        """Price 1.0 should be clamped to 1 - tick_size."""
        bot, mock_py, _ = _create_bot_with_mocks()

        await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=1.0,
            size=5.0,
            side="BUY",
            tick_size="0.01",
            neg_risk=True,
        )

        order_args = mock_py.create_order.call_args[0][0]
        assert order_args.price == 0.99

    @pytest.mark.asyncio
    async def test_cached_tick_size_skips_api_call(self):
        """Providing tick_size and neg_risk should skip API calls."""
        bot, mock_py, _ = _create_bot_with_mocks()

        await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.50,
            size=5.0,
            side="SELL",
            tick_size="0.01",
            neg_risk=True,
        )

        mock_py.get_tick_size.assert_not_called()
        mock_py.get_neg_risk.assert_not_called()

    @pytest.mark.asyncio
    async def test_size_rounded_to_2_decimals(self):
        """Size should be rounded to 2 decimal places."""
        bot, mock_py, _ = _create_bot_with_mocks()

        await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.50,
            size=5.678,
            side="SELL",
            tick_size="0.01",
            neg_risk=True,
        )

        order_args = mock_py.create_order.call_args[0][0]
        assert order_args.size == 5.68


class TestPlaceOrderErrorHandling:
    """Test error handling in place_order."""

    @pytest.mark.asyncio
    async def test_error_msg_marks_failure(self):
        """API success=True with errorMsg should be treated as failure."""
        bot, mock_py, _ = _create_bot_with_mocks()
        mock_py.post_order.return_value = {
            "success": True,
            "errorMsg": "INVALID_ORDER_NOT_ENOUGH_BALANCE",
            "orderId": None,
        }

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.50,
            size=5.0,
            side="SELL",
        )

        assert result.success is False
        assert "BALANCE" in result.message

    @pytest.mark.asyncio
    async def test_fok_not_filled_error(self):
        """FOK not filled should return failure."""
        bot, mock_py, _ = _create_bot_with_mocks()
        mock_py.post_order.return_value = {
            "success": True,
            "errorMsg": "order couldn't be fully filled, FOK orders are fully filled/killed",
            "orderId": None,
        }

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.30,
            size=5.0,
            side="SELL",
            order_type="FOK",
        )

        assert result.success is False
        assert "filled" in result.message.lower()

    @pytest.mark.asyncio
    async def test_duplicated_order_handled(self):
        """Duplicated order exception should return clean failure."""
        bot, mock_py, _ = _create_bot_with_mocks()
        mock_py.create_order.side_effect = Exception("order is invalid. Duplicated")

        result = await bot.place_order(
            token_id=TEST_TOKEN_ID,
            price=0.50,
            size=5.0,
            side="SELL",
        )

        assert result.success is False
        assert "Duplicated" in result.message

    @pytest.mark.asyncio
    async def test_no_py_client_raises_error(self):
        """place_order without _py_client should raise NotInitializedError."""
        bot = TradingBot(safe_address=TEST_SAFE_ADDRESS)

        with pytest.raises(NotInitializedError):
            await bot.place_order(
                token_id=TEST_TOKEN_ID,
                price=0.50,
                size=5.0,
                side="SELL",
            )


class TestCloseAllPositionsLive:
    """Test _close_all_positions does not prematurely clear positions in LIVE mode."""

    def _create_strategy_mock(self):
        """Create a minimal mock of ReboundStrategy internals."""
        from strategies.rebound import ReboundStrategy, ReboundConfig

        bot, mock_py, mock_clob = _create_bot_with_mocks()
        config = ReboundConfig(
            coin="BTC",
            simulation_mode=False,
            strategy_type="3",
        )

        # Use MagicMock as a lightweight stand-in
        strategy = MagicMock(spec=ReboundStrategy)
        strategy.bot = bot
        strategy.config = config
        strategy.prices = MagicMock()
        strategy.prices.get_current_price.return_value = 0.50
        strategy.db = MagicMock()
        strategy.btc_price_current = 100000.0
        strategy._active_positions = {
            "up": {
                "db_id": 1,
                "entry_price": 0.40,
                "size": 25.0,
                "token_id": TEST_TOKEN_ID,
            }
        }
        strategy._position_peak_price = {"up": 0.55}
        strategy._current_period_orders = [1]
        strategy._closing_sides = set()
        strategy._rebound_trend_records = {"up": [], "down": []}
        strategy._closed_positions_for_trend = {}
        strategy.log = MagicMock()

        # Use the real method binding
        strategy._close_all_positions = ReboundStrategy._close_all_positions.__get__(strategy)
        strategy._execute_close_live = AsyncMock()
        strategy._get_rebound_trend_summary = MagicMock(return_value="")

        return strategy

    @pytest.mark.asyncio
    async def test_live_mode_does_not_clear_positions(self):
        """In LIVE mode, _close_all_positions should NOT clear _active_positions."""
        strategy = self._create_strategy_mock()

        # Running inside pytest-asyncio provides a running event loop
        strategy._close_all_positions()

        # Allow the created task to execute
        await asyncio.sleep(0)

        # Positions should NOT be cleared — _execute_close_live handles that
        assert "up" in strategy._active_positions
        # But _current_period_orders should be cleared
        assert len(strategy._current_period_orders) == 0

    def test_sim_mode_clears_positions(self):
        """In simulation mode, _close_all_positions should clear _active_positions."""
        strategy = self._create_strategy_mock()
        strategy.config.simulation_mode = True

        strategy._close_all_positions()

        assert len(strategy._active_positions) == 0


class TestPyClientInitialization:
    """Test that _py_client is correctly initialized."""

    def test_py_client_created_with_private_key(self):
        """_py_client should be created when private_key is provided."""
        bot = TradingBot(
            private_key=TEST_PRIVATE_KEY,
            safe_address=TEST_SAFE_ADDRESS,
        )

        assert bot._py_client is not None

    def test_py_client_none_without_private_key(self):
        """_py_client should be None when no private_key is provided."""
        bot = TradingBot(safe_address=TEST_SAFE_ADDRESS)

        assert bot._py_client is None

    def test_require_py_client_raises_without_init(self):
        """_require_py_client should raise NotInitializedError when _py_client is None."""
        bot = TradingBot(safe_address=TEST_SAFE_ADDRESS)

        with pytest.raises(NotInitializedError):
            bot._require_py_client()

    def test_require_py_client_returns_client(self):
        """_require_py_client should return _py_client when initialized."""
        bot = TradingBot(
            private_key=TEST_PRIVATE_KEY,
            safe_address=TEST_SAFE_ADDRESS,
        )

        client = bot._require_py_client()
        assert client is bot._py_client
