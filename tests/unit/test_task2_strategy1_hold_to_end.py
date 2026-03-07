"""
Tests for Task 2 - Strategy 1 holds positions until period end (no stop-loss).

任务2: 策略1买入后持有到周期结束，不中途止损。
验证策略1和策略2不会触发止盈止损逻辑。
"""

import pytest
from unittest.mock import MagicMock, patch


class TestReboundConfigPnlDisabledForStrategy1:
    """ReboundConfig should disable P&L for strategy 1 and 2."""

    def test_strategy1_disables_profit_and_loss(self):
        """Strategy 1 must have profit_and_loss_enabled=False after __post_init__."""
        # Arrange & Act
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(strategy_type="1")

        # Assert
        assert config.profit_and_loss_enabled is False

    def test_strategy1_overrides_pnl_even_if_passed_true(self):
        """Strategy 1 __post_init__ should force P&L off even when True is passed."""
        # Arrange & Act
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(strategy_type="1", profit_and_loss_enabled=True)

        # Assert
        assert config.profit_and_loss_enabled is False

    def test_strategy2_disables_profit_and_loss(self):
        """Strategy 2 must have profit_and_loss_enabled=False after __post_init__."""
        # Arrange & Act
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(strategy_type="2")

        # Assert
        assert config.profit_and_loss_enabled is False

    def test_strategy2_overrides_pnl_even_if_passed_true(self):
        """Strategy 2 __post_init__ should force P&L off even when True is passed."""
        # Arrange & Act
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(strategy_type="2", profit_and_loss_enabled=True)

        # Assert
        assert config.profit_and_loss_enabled is False

    def test_strategy3_enables_profit_and_loss(self):
        """Strategy 3 must have profit_and_loss_enabled=True."""
        # Arrange & Act
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(strategy_type="3")

        # Assert
        assert config.profit_and_loss_enabled is True

    def test_strategy1_holds_only_in_segment_a(self):
        """Strategy 1 active_segments and order_segments must be ['A']."""
        # Arrange & Act
        from strategies.rebound import ReboundConfig

        config = ReboundConfig(strategy_type="1")

        # Assert
        assert config.active_segments == ["A"]
        assert config.order_segments == ["A"]


class TestEvaluatePositionsGuard:
    """_evaluate_positions_for_profit_and_loss must skip strategy 1 and 2."""

    @patch("strategies.rebound.get_database")
    def test_strategy1_pnl_evaluation_does_not_close_positions(self, mock_db):
        """For strategy 1, P&L evaluation should never close any position."""
        # Arrange
        from strategies.rebound import ReboundStrategy, ReboundConfig

        mock_db.return_value = MagicMock()

        config = ReboundConfig(strategy_type="1", simulation_mode=True)
        strategy = ReboundStrategy(bot=None, config=config)

        # Simulate an active position with heavy loss
        strategy._active_positions = {
            "up": {
                "db_id": 1,
                "entry_price": 0.50,
                "size": 10.0,
                "entry_time": 1000000,
                "_tp_eligible": False,
            }
        }
        strategy._position_peak_price = {"up": 0.50}

        # Mock prices to simulate a 50% loss (should trigger stop-loss for S3)
        strategy.prices = MagicMock()
        strategy.prices.get_current_price.return_value = 0.25

        # Mock segment to be in C (where S3 would stop-loss at 20%)
        strategy.get_current_segment = MagicMock(return_value="C")

        # Act
        strategy._evaluate_positions_for_profit_and_loss()

        # Assert - position must still be open
        assert "up" in strategy._active_positions
        assert strategy._active_positions["up"]["entry_price"] == 0.50

    @patch("strategies.rebound.get_database")
    def test_strategy2_pnl_evaluation_does_not_close_positions(self, mock_db):
        """For strategy 2, P&L evaluation should never close any position."""
        # Arrange
        from strategies.rebound import ReboundStrategy, ReboundConfig

        mock_db.return_value = MagicMock()

        config = ReboundConfig(strategy_type="2", simulation_mode=True)
        strategy = ReboundStrategy(bot=None, config=config)

        strategy._active_positions = {
            "down": {
                "db_id": 2,
                "entry_price": 0.40,
                "size": 10.0,
                "entry_time": 1000000,
                "_tp_eligible": False,
            }
        }
        strategy._position_peak_price = {"down": 0.40}

        strategy.prices = MagicMock()
        strategy.prices.get_current_price.return_value = 0.20

        strategy.get_current_segment = MagicMock(return_value="C")

        # Act
        strategy._evaluate_positions_for_profit_and_loss()

        # Assert - position must still be open
        assert "down" in strategy._active_positions

    @patch("strategies.rebound.get_database")
    def test_strategy3_pnl_evaluation_does_close_position_on_stop_loss(self, mock_db):
        """Strategy 3 P&L evaluation should close position on stop-loss."""
        # Arrange
        from strategies.rebound import ReboundStrategy, ReboundConfig

        mock_db_instance = MagicMock()
        # V2动态参数: 返回None让策略回退到config默认值
        mock_db_instance.get_active_strategy3_rule.return_value = None
        mock_db.return_value = mock_db_instance

        config = ReboundConfig(strategy_type="3", simulation_mode=True)
        strategy = ReboundStrategy(bot=None, config=config)

        strategy._active_positions = {
            "up": {
                "db_id": 3,
                "entry_price": 0.50,
                "size": 10.0,
                "entry_time": 1000000,
                "_tp_eligible": False,
            }
        }
        strategy._position_peak_price = {"up": 0.50}

        strategy.prices = MagicMock()
        # 60% loss - exceeds the 20% stop-loss threshold for stage B/C
        strategy.prices.get_current_price.return_value = 0.20

        strategy.get_current_segment = MagicMock(return_value="C")

        # Act
        strategy._evaluate_positions_for_profit_and_loss()

        # Assert - position should be closed (removed from active)
        assert "up" not in strategy._active_positions


class TestStrategyImplHoldToEnd:
    """Verify Strategy1/Strategy2 in strategy_impl.py hold to period end."""

    def test_strategy1_should_exit_trade_always_false(self):
        """Strategy1.should_exit_trade must always return False."""
        # Arrange
        from strategies.strategy_impl import Strategy1
        from strategies.base_rebound import BaseReboundConfig

        config = BaseReboundConfig(strategy_type="1")
        mock_bot = MagicMock()

        with patch("strategies.base_rebound.get_database") as mock_db:
            mock_db.return_value = MagicMock()
            strategy = Strategy1(mock_bot, config)

        position = {"entry_price": 0.50, "size": 10.0, "db_id": 1}

        # Act - test with various loss scenarios
        for segment in ["A", "B", "C"]:
            should_exit, reason, price = strategy.should_exit_trade("up", segment, position)

            # Assert
            assert should_exit is False
            assert reason == ""
            assert price == 0.0

    def test_strategy1_config_disables_pnl(self):
        """Strategy1.__init__ must set profit_and_loss_enabled=False."""
        # Arrange
        from strategies.strategy_impl import Strategy1
        from strategies.base_rebound import BaseReboundConfig

        config = BaseReboundConfig(strategy_type="1", profit_and_loss_enabled=True)
        mock_bot = MagicMock()

        with patch("strategies.base_rebound.get_database") as mock_db:
            mock_db.return_value = MagicMock()
            strategy = Strategy1(mock_bot, config)

        # Assert
        assert strategy.config.profit_and_loss_enabled is False

    def test_strategy2_should_exit_trade_always_false(self):
        """Strategy2.should_exit_trade must always return False."""
        # Arrange
        from strategies.strategy_impl import Strategy2
        from strategies.base_rebound import BaseReboundConfig

        config = BaseReboundConfig(strategy_type="2")
        mock_bot = MagicMock()

        with patch("strategies.base_rebound.get_database") as mock_db:
            mock_db.return_value = MagicMock()
            strategy = Strategy2(mock_bot, config)

        position = {"entry_price": 0.40, "size": 10.0, "db_id": 2}

        # Act
        should_exit, reason, price = strategy.should_exit_trade("down", "C", position)

        # Assert
        assert should_exit is False

    def test_strategy2_config_disables_pnl(self):
        """Strategy2.__init__ must set profit_and_loss_enabled=False."""
        # Arrange
        from strategies.strategy_impl import Strategy2
        from strategies.base_rebound import BaseReboundConfig

        config = BaseReboundConfig(strategy_type="2", profit_and_loss_enabled=True)
        mock_bot = MagicMock()

        with patch("strategies.base_rebound.get_database") as mock_db:
            mock_db.return_value = MagicMock()
            strategy = Strategy2(mock_bot, config)

        # Assert
        assert strategy.config.profit_and_loss_enabled is False


class TestRunReboundPnlConfig:
    """Verify run_rebound.py only enables P&L for strategy 3."""

    def test_load_pnl_config_with_strategy1_returns_disabled(self):
        """When strategy_type=1, profit_and_loss_enabled should be False
        regardless of config.yaml setting."""
        # Arrange
        from strategies.rebound import ReboundConfig

        # Simulate what run_rebound.py does:
        # pnl_config["enabled"] is True from config.yaml
        # but final_strategy_type is "1"
        pnl_enabled = True and ("1" == "3")  # False

        config = ReboundConfig(
            strategy_type="1",
            profit_and_loss_enabled=pnl_enabled,
        )

        # Assert
        assert config.profit_and_loss_enabled is False

    def test_load_pnl_config_with_strategy3_returns_enabled(self):
        """When strategy_type=3, profit_and_loss_enabled should be True."""
        # Arrange
        from strategies.rebound import ReboundConfig

        pnl_enabled = True and ("3" == "3")  # True

        config = ReboundConfig(
            strategy_type="3",
            profit_and_loss_enabled=pnl_enabled,
        )

        # Assert
        assert config.profit_and_loss_enabled is True
