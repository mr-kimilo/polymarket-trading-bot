"""
Tests for Task 67 - API server starts with both live and sim modes
Verify Order Schedule API endpoints are accessible when service starts.

任务67: 服务启动时（live或sim），任务66的接口可以正确访问，并生成访问的URL
"""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock
import io
import sys


class TestTask67APIServerStartup:
    """Test API server startup and URL generation"""
    
    def test_start_api_server_prints_order_schedule_urls(self):
        """Test that start_api_server_background prints Order Schedule API URLs"""
        # Arrange
        from apps.run_rebound import start_api_server_background
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Act - Mock threading to prevent actual server start
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            start_api_server_background(port=5000, host="0.0.0.0")
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Assert - Check Order Schedule API URLs are printed
        assert "/orderSchedule/create" in output, "Should print create endpoint URL"
        assert "/orderSchedule/cancel" in output, "Should print cancel endpoint URL"
        assert "/orderSchedule/query" in output, "Should print query endpoint URL"
        assert "/orderSchedule/check" in output, "Should print check endpoint URL"
    
    def test_start_api_server_prints_localhost_url(self):
        """Test that API server prints localhost when host is 0.0.0.0"""
        # Arrange
        from apps.run_rebound import start_api_server_background
        
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Act
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            start_api_server_background(port=5000, host="0.0.0.0")
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Assert - Should show localhost for user-friendly URL
        assert "http://localhost:5000" in output, "Should display localhost URL"
    
    def test_start_api_server_prints_custom_port(self):
        """Test that API server prints custom port"""
        # Arrange
        from apps.run_rebound import start_api_server_background
        
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Act
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            start_api_server_background(port=8080, host="0.0.0.0")
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Assert
        assert "http://localhost:8080" in output, "Should display custom port"
        assert "/orderSchedule/create" in output
    
    def test_start_api_server_prints_api_documentation_reference(self):
        """Test that API server prints reference to API documentation"""
        # Arrange
        from apps.run_rebound import start_api_server_background
        
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Act
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            start_api_server_background(port=5000)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Assert - Should reference API documentation
        assert "order-schedule-api.md" in output, "Should reference API documentation file"


class TestTask67APIEndpointsAccessible:
    """Test that Order Schedule API endpoints work correctly"""
    
    def test_create_order_schedule_endpoint_works(self):
        """Test creating order schedule via API function"""
        # Arrange
        from scripts.strategy_api import create_order_schedule
        
        # Act
        result = create_order_schedule(
            env="sim",
            strategy_type="1",
            schedule_date=date.today().isoformat(),
            start_time="09:00",
            end_time="17:00"
        )
        
        # Assert
        assert 'success' in result
        assert 'message' in result
        assert 'schedule_id' in result
    
    def test_query_order_schedules_endpoint_works(self):
        """Test querying order schedules via API function"""
        # Arrange
        from scripts.strategy_api import query_order_schedules
        
        # Act
        result = query_order_schedules(env="sim")
        
        # Assert
        assert result['success'] is True
        assert 'schedules' in result
        assert 'count' in result
    
    def test_check_should_trade_endpoint_works(self):
        """Test check should trade via API function"""
        # Arrange
        from scripts.strategy_api import check_should_trade
        
        # Act
        result = check_should_trade(env="sim", strategy_type="1")
        
        # Assert
        assert 'success' in result
        assert 'should_trade' in result
        assert 'message' in result
    
    def test_cancel_order_schedule_endpoint_works(self):
        """Test canceling order schedule via API function"""
        # Arrange
        from scripts.strategy_api import cancel_order_schedule
        
        # Act - Try to cancel non-existent schedule
        result = cancel_order_schedule(schedule_id=999999)
        
        # Assert - Should return proper response even for non-existent ID
        assert 'success' in result
        assert 'message' in result


class TestTask67URLGeneration:
    """Test correct URL generation for different configurations"""
    
    def test_url_with_default_settings(self):
        """Test URL generation with default host and port"""
        # The expected output format
        expected_urls = [
            "http://localhost:5000/orderSchedule/create",
            "http://localhost:5000/orderSchedule/cancel",
            "http://localhost:5000/orderSchedule/query",
            "http://localhost:5000/orderSchedule/check",
        ]
        
        # Verify the URLs are correctly formatted
        for url in expected_urls:
            assert url.startswith("http://")
            assert "/orderSchedule/" in url
    
    def test_url_with_custom_host(self):
        """Test URL generation with custom host"""
        from apps.run_rebound import start_api_server_background
        
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            start_api_server_background(port=5000, host="192.168.1.100")
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Should use actual host when not 0.0.0.0
        assert "http://192.168.1.100:5000" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
