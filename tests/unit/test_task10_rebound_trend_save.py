"""
Tests for Task 10: Verify rebound_trend is correctly saved in both sim and live environments.

Instructions used: [clean-architecture.instructions.md, unit-and-integration-tests.instructions.md,
                    coding-style-python.instructions.md]

Root causes fixed:
1. _get_rebound_trend_summary() returned "" when no records → now returns None,
   preventing it from overwriting valid trend data already saved by _save_final_rebound_trends().
2. update_rebound_order_result() always set rebound_trend = %s → now only includes
   rebound_trend in SET clause when the caller explicitly provides a non-None value.
3. _close_all_positions() sim path missed rebound_trend → now passes it.
4. _direct_sell() sim path missed rebound_trend → now passes it.
"""

import pytest
from unittest.mock import MagicMock, patch, call
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestGetReboundTrendSummary:
    """Test _get_rebound_trend_summary() return value changes."""

    def _make_strategy(self):
        from strategies.rebound import ReboundStrategy, ReboundConfig
        config = ReboundConfig(coin="BTC", simulation_mode=True)
        return ReboundStrategy(bot=None, config=config)

    def test_returns_none_when_no_records(self):
        """Should return None (not empty string) when _rebound_trend_records is empty."""
        strategy = self._make_strategy()
        assert strategy._rebound_trend_records["up"] == []
        result = strategy._get_rebound_trend_summary("up")
        assert result is None, "Expected None when no records exist"

    def test_returns_none_for_unknown_side(self):
        """Should return None for an unknown side key."""
        strategy = self._make_strategy()
        result = strategy._get_rebound_trend_summary("unknown")
        assert result is None

    def test_returns_formatted_string_when_records_exist(self):
        """Should return comma-separated percentage string when records exist."""
        strategy = self._make_strategy()
        strategy._rebound_trend_records["up"] = [0.15, 0.25, 0.35]
        result = strategy._get_rebound_trend_summary("up")
        assert result == "0.15, 0.25, 0.35"

    def test_return_type_is_optional_str(self):
        """Return type should be Optional[str] — None or a non-empty string."""
        strategy = self._make_strategy()
        # Empty → None
        assert strategy._get_rebound_trend_summary("down") is None
        # With data → str
        strategy._rebound_trend_records["down"] = [0.10]
        result = strategy._get_rebound_trend_summary("down")
        assert isinstance(result, str)
        assert len(result) > 0


class TestUpdateReboundOrderResultConditionalSQL:
    """Test that update_rebound_order_result does NOT overwrite rebound_trend when not provided."""

    def _make_db(self):
        from src.database import Database
        db = Database.__new__(Database)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        db._conn = mock_conn
        return db, mock_cursor

    def test_rebound_trend_excluded_when_none(self):
        """SQL should NOT include rebound_trend = %s when rebound_trend is None."""
        db, mock_cursor = self._make_db()
        db.update_rebound_order_result(
            order_id=1,
            exit_price=0.50,
            status="closed"
            # rebound_trend not passed → defaults to None
        )
        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "rebound_trend" not in executed_sql, (
            "rebound_trend column must NOT appear in SQL when not provided"
        )

    def test_rebound_trend_included_when_provided(self):
        """SQL SHOULD include rebound_trend = %s when a value is given."""
        db, mock_cursor = self._make_db()
        db.update_rebound_order_result(
            order_id=1,
            exit_price=0.50,
            status="closed",
            rebound_trend="0.10, 0.20, 0.30"
        )
        executed_sql = mock_cursor.execute.call_args[0][0]
        executed_params = mock_cursor.execute.call_args[0][1]
        assert "rebound_trend" in executed_sql, "rebound_trend must appear in SQL when provided"
        assert "0.10, 0.20, 0.30" in executed_params

    def test_existing_trend_not_overwritten_when_none_passed(self):
        """Calling update_rebound_order_result without rebound_trend must not erase DB column."""
        # This verifies that the SQL generated does not SET rebound_trend at all,
        # so the existing DB value is preserved.
        db, mock_cursor = self._make_db()
        db.update_rebound_order_result(order_id=99, exit_price=0.40, status="closed")
        sql = mock_cursor.execute.call_args[0][0]
        # Column must be absent from SET clause
        assert "rebound_trend" not in sql


class TestCloseAllPositionsSimReboundTrend:
    """Test that _close_all_positions() passes rebound_trend in simulation mode."""

    def _make_strategy_with_position(self, side: str, db_id: int):
        from strategies.rebound import ReboundStrategy, ReboundConfig
        config = ReboundConfig(coin="BTC", simulation_mode=True)
        strategy = ReboundStrategy(bot=None, config=config)
        strategy._active_positions[side] = {
            "entry_price": 0.30,
            "size": 10.0,
            "db_id": db_id,
        }
        strategy._rebound_trend_records[side] = [0.05, 0.10, 0.15]
        return strategy

    def test_close_all_positions_passes_rebound_trend(self):
        """_close_all_positions() sim path must call update_rebound_order_result with rebound_trend."""
        strategy = self._make_strategy_with_position("up", db_id=42)
        mock_db = MagicMock()
        strategy.db = mock_db
        # Provide a price so the sim branch is entered
        strategy.prices = MagicMock()
        strategy.prices.get_current_price.return_value = 0.40
        strategy.btc_price_current = 95000.0

        strategy._close_all_positions()

        mock_db.update_rebound_order_result.assert_called_once()
        kwargs = mock_db.update_rebound_order_result.call_args.kwargs
        assert kwargs.get("rebound_trend") == "0.05, 0.10, 0.15", (
            "_close_all_positions must pass rebound_trend to update_rebound_order_result"
        )

    def test_close_all_positions_passes_none_when_no_records(self):
        """When no trend records exist, rebound_trend=None prevents overwriting DB."""
        from strategies.rebound import ReboundStrategy, ReboundConfig
        config = ReboundConfig(coin="BTC", simulation_mode=True)
        strategy = ReboundStrategy(bot=None, config=config)
        strategy._active_positions["down"] = {
            "entry_price": 0.30,
            "size": 5.0,
            "db_id": 7,
        }
        # No trend records recorded yet
        mock_db = MagicMock()
        strategy.db = mock_db
        strategy.prices = MagicMock()
        strategy.prices.get_current_price.return_value = 0.25
        strategy.btc_price_current = 94000.0

        strategy._close_all_positions()

        kwargs = mock_db.update_rebound_order_result.call_args.kwargs
        assert kwargs.get("rebound_trend") is None, (
            "rebound_trend must be None (not empty string) when no records exist"
        )


class TestDirectSellSimReboundTrend:
    """Test that direct_sell_all_positions() passes rebound_trend in simulation mode."""

    def _make_strategy_with_position(self, side: str, db_id: int, trend_records=None):
        from strategies.rebound import ReboundStrategy, ReboundConfig
        config = ReboundConfig(coin="BTC", simulation_mode=True)
        config.direct_sell_enabled = True  # required for direct_sell_all_positions to run
        strategy = ReboundStrategy(bot=None, config=config)
        strategy._active_positions[side] = {
            "entry_price": 0.30,
            "size": 10.0,
            "db_id": db_id,
            "token_id": "0xabc",
        }
        # token_id is in pos_info directly; no need to set strategy.token_ids (read-only property)
        if trend_records:
            strategy._rebound_trend_records[side] = trend_records
        return strategy

    @pytest.mark.asyncio
    async def test_direct_sell_passes_rebound_trend(self):
        """direct_sell_all_positions() sim path must call update_rebound_order_result with rebound_trend."""
        strategy = self._make_strategy_with_position("up", db_id=55, trend_records=[0.08, 0.12])
        mock_db = MagicMock()
        strategy.db = mock_db
        strategy.prices = MagicMock()
        strategy.prices.get_current_price.return_value = 0.38
        strategy.btc_price_current = 96000.0

        # Patch get_safe_sell_price to return a value quickly
        async def mock_safe_sell(token_id, side):
            return 0.37

        with patch.object(strategy, "get_safe_sell_price", side_effect=mock_safe_sell):
            await strategy.direct_sell_all_positions(reason="test")

        mock_db.update_rebound_order_result.assert_called_once()
        kwargs = mock_db.update_rebound_order_result.call_args.kwargs
        assert kwargs.get("rebound_trend") == "0.08, 0.12", (
            "direct_sell_all_positions must pass rebound_trend to update_rebound_order_result"
        )

    @pytest.mark.asyncio
    async def test_direct_sell_passes_none_when_no_trend(self):
        """direct_sell_all_positions() must pass rebound_trend=None when no records to avoid overwrite."""
        strategy = self._make_strategy_with_position("down", db_id=66)
        mock_db = MagicMock()
        strategy.db = mock_db
        strategy.prices = MagicMock()
        strategy.prices.get_current_price.return_value = 0.25
        strategy.btc_price_current = 94500.0

        async def mock_safe_sell(token_id, side):
            return 0.24

        with patch.object(strategy, "get_safe_sell_price", side_effect=mock_safe_sell):
            await strategy.direct_sell_all_positions(reason="test")

        kwargs = mock_db.update_rebound_order_result.call_args.kwargs
        assert kwargs.get("rebound_trend") is None


class TestRaceConditionPrevention:
    """Test that _save_final_rebound_trends data is not overwritten by _execute_close_live."""

    def test_empty_records_return_none_prevents_overwrite(self):
        """
        After _rebound_trend_records is reset (period end), _get_rebound_trend_summary
        returns None, so update_rebound_order_result skips rebound_trend in SQL,
        preserving the trend data saved by _save_final_rebound_trends.
        """
        from strategies.rebound import ReboundStrategy, ReboundConfig
        config = ReboundConfig(coin="BTC", simulation_mode=False)
        strategy = ReboundStrategy(bot=None, config=config)

        # Simulate the state after _reset_for_new_period clears the records
        strategy._rebound_trend_records = {"up": [], "down": []}

        # _get_rebound_trend_summary must return None (not "")
        assert strategy._get_rebound_trend_summary("up") is None
        assert strategy._get_rebound_trend_summary("down") is None
