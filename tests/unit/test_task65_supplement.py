"""
Tests for Task 65 Supplement - Split time_period into start and end

Instructions used: [clean-architecture.instructions.md, unit-and-integration-tests.instructions.md, 
                    coding-style-python.instructions.md, domain-driven-design.instructions.md]

Task 65 Supplement: 将time_period拆分为start, end两个字段
"""

import pytest
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTask65SupplementTableStructure:
    """Test order_schedule table has start and end columns instead of time_period"""
    
    def test_order_schedule_has_start_column(self):
        """Test that order_schedule table has start_time column"""
        # Arrange
        from src.database import Database
        
        db = Database()
        
        # Act
        with db._conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = 'order_schedule' AND column_name = 'start_time';
            """)
            result = cur.fetchone()
        
        # Assert
        assert result is not None, "start_time column should exist"
        assert result[1] == 'time without time zone', "start_time should be TIME type"
    
    def test_order_schedule_has_end_column(self):
        """Test that order_schedule table has end_time column"""
        # Arrange
        from src.database import Database
        
        db = Database()
        
        # Act
        with db._conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = 'order_schedule' AND column_name = 'end_time';
            """)
            result = cur.fetchone()
        
        # Assert
        assert result is not None, "end_time column should exist"
        assert result[1] == 'time without time zone', "end_time should be TIME type"
    
    def test_order_schedule_no_time_period_column(self):
        """Test that old time_period column is removed"""
        # Arrange
        from src.database import Database
        
        db = Database()
        
        # Act
        with db._conn.cursor() as cur:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'order_schedule' AND column_name = 'time_period';
            """)
            result = cur.fetchone()
        
        # Assert
        assert result is None, "time_period column should not exist (replaced by start_time/end_time)"


class TestTask65SupplementDatabaseMethods:
    """Test database methods support start_time and end_time"""
    
    def test_create_order_schedule_with_time_objects(self):
        """Test creating schedule with time objects"""
        # Arrange
        from src.database import Database
        from datetime import time
        
        db = Database()
        
        # Act
        schedule_id = db.create_order_schedule(
            env="sim",
            strategy_type="2",
            schedule_date=date.today(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            status=0
        )
        
        # Assert
        assert schedule_id is not None
        
        # Verify saved data
        schedule = db.get_order_schedule(schedule_id)
        assert schedule is not None
        assert schedule['start_time'] == '09:00:00'
        assert schedule['end_time'] == '10:00:00'
    
    def test_check_should_trade_with_current_time_in_range(self):
        """Test checking if should trade when current time is in range"""
        # Arrange
        from src.database import Database
        from datetime import datetime, time
        
        db = Database()
        
        # Create schedule for current hour
        now = datetime.now()
        current_time = now.time()
        start_time = time(current_time.hour, 0)
        end_time = time(current_time.hour, 59)
        
        _ = db.create_order_schedule(
            env="sim",
            strategy_type="1",
            schedule_date=date.today(),
            start_time=start_time,
            end_time=end_time,
            status=0
        )
        
        # Act
        should_trade = db.check_should_trade(env="sim", strategy_type="1")
        
        # Assert
        assert should_trade is True
    
    def test_check_should_not_trade_outside_time_range(self):
        """Test that trading is not allowed outside scheduled time range"""
        # Arrange
        from src.database import Database
        from datetime import datetime, time
        
        db = Database()
        
        # Clean up any existing schedules for this test
        with db._conn.cursor() as cur:
            cur.execute("DELETE FROM order_schedule WHERE env='sim_test' AND strategy_type='99';")
        
        # Create schedule for a time range that's definitely not current time
        now = datetime.now()
        # Schedule for 2 hours from now
        start_hour = (now.hour + 2) % 24
        start_time = time(start_hour, 0)
        end_time = time(start_hour, 30)
        
        _ = db.create_order_schedule(
            env="sim_test",
            strategy_type="99",
            schedule_date=date.today(),
            start_time=start_time,
            end_time=end_time,
            status=0
        )
        
        # Act
        should_trade = db.check_should_trade(env="sim_test", strategy_type="99")
        
        # Assert
        # If current time is not in [start_hour:00, start_hour:30], should_trade should be False
        current_hour = now.hour
        if current_hour != start_hour:
            assert should_trade is False


class TestTask65SupplementAPIFunctions:
    """Test API functions work with start_time and end_time"""
    
    def test_create_order_schedule_api_with_time_strings(self):
        """Test creating schedule via API with time strings"""
        # Arrange
        from scripts.strategy_api import create_order_schedule
        
        # Act
        result = create_order_schedule(
            env="sim",
            strategy_type="3",
            schedule_date=date.today().isoformat(),
            start_time="14:00",
            end_time="15:00"
        )
        
        # Assert
        assert result['success'] is True
        assert result['schedule_id'] is not None
    
    def test_query_order_schedules_returns_start_end_times(self):
        """Test that query returns start_time and end_time"""
        # Arrange
        from scripts.strategy_api import create_order_schedule, query_order_schedules
        
        # Create a schedule first
        create_result = create_order_schedule(
            env="sim",
            strategy_type="2",
            schedule_date=date.today().isoformat(),
            start_time="10:00",
            end_time="11:00"
        )
        schedule_id = create_result['schedule_id']
        
        # Act
        result = query_order_schedules(env="sim", strategy_type="2")
        
        # Assert
        assert result['success'] is True
        assert result['count'] > 0
        
        # Find our schedule
        schedule = next((s for s in result['schedules'] if s['id'] == schedule_id), None)
        assert schedule is not None
        assert 'start_time' in schedule
        assert 'end_time' in schedule
        assert schedule['start_time'] == '10:00:00'
        assert schedule['end_time'] == '11:00:00'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
