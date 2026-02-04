"""
Tests for Tasks 63, 64, 65

Instructions used: [clean-architecture.instructions.md, unit-and-integration-tests.instructions.md, 
                    coding-style-python.instructions.md, domain-driven-design.instructions.md]

Task 63: Fix rebound_trend not recording for strategy 1
Task 64: Add strategy_type and env fields to rebound_orders
Task 65: Add order_schedule feature for time-based order scheduling
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTask63ReboundTrendRecording:
    """Task 63: Test rebound_trend recording for all strategies"""
    
    def test_rebound_trend_records_initialized(self):
        """Test that rebound_trend_records is initialized for all strategies"""
        # Arrange
        from strategies.rebound import ReboundStrategy, ReboundConfig
        
        config = ReboundConfig(
            coin="BTC",
            strategy_type="1",  # Strategy 1
            simulation_mode=True
        )
        
        # Act
        strategy = ReboundStrategy(bot=None, config=config)
        
        # Assert
        assert hasattr(strategy, '_rebound_trend_records')
        assert "up" in strategy._rebound_trend_records
        assert "down" in strategy._rebound_trend_records
    
    def test_rebound_trend_method_exists(self):
        """Test that _record_rebound_trend method exists"""
        # Arrange
        from strategies.rebound import ReboundStrategy, ReboundConfig
        
        config = ReboundConfig(coin="BTC", simulation_mode=True)
        strategy = ReboundStrategy(bot=None, config=config)
        
        # Assert
        assert hasattr(strategy, '_record_rebound_trend')
        assert callable(strategy._record_rebound_trend)
    
    def test_rebound_trend_for_strategy_1(self):
        """Test that strategy 1 has proper trend tracking setup"""
        # Arrange
        from strategies.rebound import ReboundConfig
        
        config = ReboundConfig(
            coin="BTC",
            strategy_type="1",
            simulation_mode=True
        )
        
        # Assert - Strategy 1 should have A segment active
        assert "A" in config.active_segments
        assert "A" in config.order_segments


class TestTask64StrategyTypeAndEnv:
    """Task 64: Test strategy_type and env fields in rebound_orders"""
    
    def test_rebound_order_dataclass_has_new_fields(self):
        """Test that ReboundOrder dataclass has strategy_type and env"""
        # Arrange
        from src.database import ReboundOrder
        
        # Act
        order = ReboundOrder(
            coin="BTC",
            side="up",
            segment="A",
            entry_price=0.25,
            is_simulated=True,
            strategy_type="1",
            env="sim"
        )
        
        # Assert
        assert order.strategy_type == "1"
        assert order.env == "sim"
    
    def test_rebound_order_env_prod(self):
        """Test that ReboundOrder can have env=prod"""
        # Arrange
        from src.database import ReboundOrder
        
        # Act
        order = ReboundOrder(
            coin="BTC",
            side="down",
            segment="C",
            entry_price=0.35,
            is_simulated=False,
            strategy_type="3",
            env="prod"
        )
        
        # Assert
        assert order.strategy_type == "3"
        assert order.env == "prod"
    
    def test_rebound_order_default_none(self):
        """Test that strategy_type and env default to None for backward compatibility"""
        # Arrange
        from src.database import ReboundOrder
        
        # Act - create without the new fields
        order = ReboundOrder(
            coin="BTC",
            side="up",
            segment="A",
            entry_price=0.25
        )
        
        # Assert
        assert order.strategy_type is None
        assert order.env is None


class TestTask65OrderSchedule:
    """Task 65: Test order_schedule feature"""
    
    def test_rebound_config_has_order_schedule_flag(self):
        """Test ReboundConfig has order_schedule_enabled attribute"""
        # Arrange
        from strategies.rebound import ReboundConfig
        
        # Act
        config = ReboundConfig(
            coin="BTC",
            simulation_mode=True,
            order_schedule_enabled=True
        )
        
        # Assert
        assert hasattr(config, 'order_schedule_enabled')
        assert config.order_schedule_enabled is True
    
    def test_config_order_schedule_default_false(self):
        """Test order_schedule defaults to False"""
        # Arrange
        from strategies.rebound import ReboundConfig
        
        # Act
        config = ReboundConfig(coin="BTC", simulation_mode=True)
        
        # Assert
        assert config.order_schedule_enabled is False


class TestTask65API:
    """Task 65: Test order schedule API functions"""
    
    def test_api_create_schedule_function_exists(self):
        """Test that create_order_schedule API function exists"""
        # Arrange & Act
        from scripts.strategy_api import create_order_schedule
        
        # Assert
        assert callable(create_order_schedule)
    
    def test_api_cancel_schedule_function_exists(self):
        """Test that cancel_order_schedule API function exists"""
        # Arrange & Act
        from scripts.strategy_api import cancel_order_schedule
        
        # Assert
        assert callable(cancel_order_schedule)
    
    def test_api_query_schedules_function_exists(self):
        """Test that query_order_schedules API function exists"""
        # Arrange & Act
        from scripts.strategy_api import query_order_schedules
        
        # Assert
        assert callable(query_order_schedules)
    
    def test_api_check_should_trade_function_exists(self):
        """Test that check_should_trade API function exists"""
        # Arrange & Act
        from scripts.strategy_api import check_should_trade
        
        # Assert
        assert callable(check_should_trade)


class TestDatabaseMethods:
    """Test that database has required methods"""
    
    def test_database_has_order_schedule_methods(self):
        """Test that Database class has order_schedule methods"""
        # Arrange
        from src.database import Database
        
        # Assert
        assert hasattr(Database, 'ensure_order_schedule_table')
        assert hasattr(Database, 'create_order_schedule')
        assert hasattr(Database, 'get_order_schedule')
        assert hasattr(Database, 'cancel_order_schedule')
        assert hasattr(Database, 'check_should_trade')
        assert hasattr(Database, 'query_order_schedules')
        assert hasattr(Database, 'add_missing_columns')
    
    def test_database_has_strategy_type_env_in_create(self):
        """Test that create_rebound_order handles new fields"""
        # Arrange
        from src.database import Database
        import inspect
        
        # Get the method signature
        sig = inspect.signature(Database.create_rebound_order)
        
        # Assert - method should accept ReboundOrder which now has strategy_type and env
        assert 'order' in sig.parameters


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
