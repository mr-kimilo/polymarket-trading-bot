"""
Tests for Task 16: Simulation mode should NOT write orders to database.

Instructions used: [clean-architecture.instructions.md, unit-and-integration-tests.instructions.md,
                    coding-style-python.instructions.md]

Root cause:
Strategy 3 in simulation mode created DB records (is_simulated=True, status=SIMULATED),
causing confusion: "database has data but no real orders on Polymarket."

Fix:
Simulation mode now tracks positions in-memory only. Database records are only
created for real (live mode) orders.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_strategy(simulation_mode: bool = False, strategy_type: str = "3"):
    """Create a ReboundStrategy with mocked dependencies."""
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
    strategy.market = MagicMock()
    strategy.market.token_ids = {"up": "token_up", "down": "token_down"}
    strategy.market.current_market = MagicMock()
    strategy.market.current_market.slug = "test-market"
    strategy.prices = MagicMock()
    strategy.prices.get_current_price = MagicMock(return_value=0.30)
    strategy._get_rebound_trend_summary = MagicMock(return_value=None)
    # Mock get_safe_buy_price for live mode tests
    strategy.get_safe_buy_price = AsyncMock(return_value=0.30)
    return strategy


def _make_order_result(success: bool = True, order_id: str = "ord_1", status: str = "live"):
    from src.bot import OrderResult
    return OrderResult(success=success, order_id=order_id, status=status, message="ok")


class TestSimulationModeNoDB:
    """Simulation mode should NOT write to database."""

    @pytest.mark.asyncio
    async def test_simulation_does_not_create_db_record(self):
        """Simulation mode should not call create_rebound_order."""
        strategy = _make_strategy(simulation_mode=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        strategy.db.create_rebound_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_simulation_tracks_position_in_memory(self):
        """Simulation mode should still track positions in _active_positions."""
        strategy = _make_strategy(simulation_mode=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        assert "up" in strategy._active_positions
        pos = strategy._active_positions["up"]
        assert pos["db_id"] is None
        assert pos["entry_price"] == 0.30
        assert pos["token_id"] == "token_up"
        assert pos["size"] > 0

    @pytest.mark.asyncio
    async def test_simulation_prevents_multiple_orders_per_period(self):
        """Simulation mode should still enforce one-order-per-period rule."""
        strategy = _make_strategy(simulation_mode=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        # _current_period_orders should have an entry
        assert len(strategy._current_period_orders) == 1
        # entry should be a simulation marker string
        assert str(strategy._current_period_orders[0]).startswith("sim_")

    @pytest.mark.asyncio
    async def test_simulation_strategy3_pnl_tracking(self):
        """Strategy 3 simulation should still initialize P&L tracking in memory."""
        strategy = _make_strategy(simulation_mode=True, strategy_type="3")
        strategy.config.profit_and_loss_enabled = True

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        assert "up" in strategy._position_peak_price
        assert strategy._position_peak_price["up"] == 0.30
        assert strategy._active_positions["up"]["_tp_eligible"] is False

    @pytest.mark.asyncio
    async def test_simulation_close_does_not_update_db(self):
        """Closing a simulation position should not call DB update."""
        strategy = _make_strategy(simulation_mode=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        strategy.prices.get_current_price.return_value = 0.40
        strategy._close_position("up", exit_price=0.40, reason="test")

        strategy.db.update_rebound_order_result.assert_not_called()
        assert "up" not in strategy._active_positions

    @pytest.mark.asyncio
    async def test_simulation_close_logs_pnl(self):
        """Closing a simulation position should still log PnL."""
        strategy = _make_strategy(simulation_mode=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)

        strategy._close_position("up", exit_price=0.40, reason="test")

        # Should have logged the close
        log_calls = [str(c) for c in strategy.log.call_args_list]
        close_logs = [c for c in log_calls if "Closed" in c and "SIMULATED" in c]
        assert len(close_logs) > 0


class TestLiveModeDBWrites:
    """Live mode should still write to database."""

    @pytest.mark.asyncio
    async def test_live_mode_creates_db_record(self):
        """Live mode should create a DB record when order fills."""
        strategy = _make_strategy(simulation_mode=False)
        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": True, "size_matched": 10.0, "status": "matched"}
        )

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is True
        strategy.db.create_rebound_order.assert_called_once()
        assert strategy._active_positions["up"]["db_id"] == 1

    @pytest.mark.asyncio
    async def test_live_mode_buy_failed_no_db_record(self):
        """Live mode should NOT create a DB record when all retries fail (Task 16 fix)."""
        strategy = _make_strategy(simulation_mode=False)
        strategy.bot.place_order.return_value = _make_order_result()
        strategy._wait_for_order_fill = AsyncMock(
            return_value={"filled": False, "size_matched": 0, "status": "timeout"}
        )
        strategy.bot.cancel_order.return_value = MagicMock(success=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is False
        # 任务16: buy_failed不再写入数据库，只有成功的订单才写入
        strategy.db.create_rebound_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_mode_rejected_no_db_record(self):
        """Live mode should NOT create a DB record when order is rejected."""
        strategy = _make_strategy(simulation_mode=False)
        strategy.bot.place_order.return_value = _make_order_result(success=False)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        result = await strategy._execute_trade("up", trigger_info)

        assert result is False
        strategy.db.create_rebound_order.assert_not_called()


class TestCloseAllPositionsSimulation:
    """_close_all_positions should not write to DB in simulation mode."""

    @pytest.mark.asyncio
    async def test_close_all_simulation_no_db_update(self):
        """Period-end close in simulation should not update DB."""
        strategy = _make_strategy(simulation_mode=True)

        trigger_info = {"segment": "A", "up_price": 0.30, "down_price": 0.70, "btc_drop": 10}
        await strategy._execute_trade("up", trigger_info)
        assert "up" in strategy._active_positions

        strategy.prices.get_current_price.return_value = 0.35
        strategy._close_all_positions()

        strategy.db.update_rebound_order_result.assert_not_called()
        assert len(strategy._active_positions) == 0
