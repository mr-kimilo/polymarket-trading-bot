"""
Unit Tests for Risk Control Module

Tests the RiskChecker class and VolatilityResult dataclass.
Verifies 24h BTC volatility checks, warning display, and user confirmation.

Run with:
    pytest tests/test_risk_control.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.risk_control import (
    RiskChecker,
    VolatilityResult,
    check_volatility_before_start,
    DEFAULT_VOLATILITY_THRESHOLD,
)


# --- Fixtures ---


def _make_klines(high_low_pairs: list[tuple[float, float]]) -> list:
    """Build minimal Binance-style klines from (high, low) pairs.

    Binance kline: [open_time, open, high, low, close, volume, ...]
    """
    return [
        [
            1700000000000 + i * 3600000,  # open_time
            str((h + l) / 2),             # open
            str(h),                       # high (index 2)
            str(l),                       # low  (index 3)
            str((h + l) / 2),             # close
            "100.0",                      # volume
        ]
        for i, (h, l) in enumerate(high_low_pairs)
    ]


SAFE_KLINES = _make_klines(
    [(90000, 88000), (89500, 87500), (90500, 87000)]  # range = 90500 - 87000 = 3500
)

HIGH_RISK_KLINES = _make_klines(
    [(95000, 93000), (96000, 91000), (94000, 91500)]  # range = 96000 - 91000 = 5000
)

EXACTLY_THRESHOLD_KLINES = _make_klines(
    [(94000, 90000)]  # range = 4000, not > 4000 so NOT high risk
)


# --- VolatilityResult Tests ---


class TestVolatilityResult:
    """Tests for the VolatilityResult dataclass."""

    def test_safe_result_attributes(self):
        """Test result for safe volatility."""
        result = VolatilityResult(
            high=90000.0,
            low=87000.0,
            price_range=3000.0,
            threshold=4000.0,
            is_high_risk=False,
        )
        assert result.high == 90000.0
        assert result.low == 87000.0
        assert result.price_range == 3000.0
        assert result.is_high_risk is False
        assert result.error is None

    def test_high_risk_result(self):
        """Test result for high-risk volatility."""
        result = VolatilityResult(
            high=96000.0,
            low=91000.0,
            price_range=5000.0,
            threshold=4000.0,
            is_high_risk=True,
        )
        assert result.is_high_risk is True
        assert result.price_range == 5000.0

    def test_from_error(self):
        """Test creating an error result."""
        result = VolatilityResult.from_error("Connection failed", threshold=4000.0)
        assert result.error == "Connection failed"
        assert result.is_high_risk is False
        assert result.high == 0.0
        assert result.low == 0.0

    def test_frozen_dataclass(self):
        """Test that VolatilityResult is immutable."""
        result = VolatilityResult(
            high=90000.0, low=87000.0, price_range=3000.0,
            threshold=4000.0, is_high_risk=False,
        )
        with pytest.raises(AttributeError):
            result.high = 99999.0


# --- RiskChecker Tests ---


class TestRiskChecker:
    """Tests for the RiskChecker class."""

    def test_default_threshold(self):
        """Test default threshold is 4000."""
        checker = RiskChecker()
        assert checker._threshold == DEFAULT_VOLATILITY_THRESHOLD
        assert checker._threshold == 4000.0

    def test_custom_threshold(self):
        """Test custom threshold initialization."""
        checker = RiskChecker(threshold=5000.0)
        assert checker._threshold == 5000.0

    @patch("lib.risk_control.requests.get")
    def test_check_safe_volatility(self, mock_get):
        """Test check returns safe when range < threshold."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAFE_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        checker = RiskChecker(threshold=4000.0)

        # Act
        result = checker.check_24h_volatility()

        # Assert
        assert result.is_high_risk is False
        assert result.high == 90500.0
        assert result.low == 87000.0
        assert result.price_range == 3500.0
        assert result.error is None

    @patch("lib.risk_control.requests.get")
    def test_check_high_risk_volatility(self, mock_get):
        """Test check returns high risk when range > threshold."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = HIGH_RISK_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        checker = RiskChecker(threshold=4000.0)

        # Act
        result = checker.check_24h_volatility()

        # Assert
        assert result.is_high_risk is True
        assert result.price_range == 5000.0
        assert result.high == 96000.0
        assert result.low == 91000.0

    @patch("lib.risk_control.requests.get")
    def test_exact_threshold_not_high_risk(self, mock_get):
        """Test that range exactly equal to threshold is NOT high risk."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = EXACTLY_THRESHOLD_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        checker = RiskChecker(threshold=4000.0)

        # Act
        result = checker.check_24h_volatility()

        # Assert
        assert result.is_high_risk is False
        assert result.price_range == 4000.0

    @patch("lib.risk_control.requests.get")
    def test_network_error_returns_error_result(self, mock_get):
        """Test network failure returns an error result, not exception."""
        import requests
        mock_get.side_effect = requests.RequestException("Timeout")

        checker = RiskChecker()
        result = checker.check_24h_volatility()

        assert result.error is not None
        assert "Timeout" in result.error
        assert result.is_high_risk is False

    @patch("lib.risk_control.requests.get")
    def test_empty_klines_returns_error(self, mock_get):
        """Test empty klines response is handled gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        checker = RiskChecker()
        result = checker.check_24h_volatility()

        assert result.error is not None
        assert result.is_high_risk is False

    @patch("lib.risk_control.requests.get")
    def test_api_called_with_correct_params(self, mock_get):
        """Test Binance API is called with correct parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAFE_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        checker = RiskChecker()
        checker.check_24h_volatility()

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args.kwargs.get("timeout") == 10
        params = call_args.kwargs.get("params") or call_args.args[0] if call_args.args else {}
        if not params:
            params = call_args[1].get("params", {})
        assert params["symbol"] == "BTCUSDT"
        assert params["interval"] == "1h"
        assert params["limit"] == "24"


# --- prompt_confirmation Tests ---


class TestPromptConfirmation:
    """Tests for the user confirmation flow."""

    @patch("lib.risk_control.requests.get")
    def test_safe_result_returns_true_without_prompt(self, mock_get):
        """Test that safe result auto-approves without user input."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAFE_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        checker = RiskChecker(threshold=4000.0)
        result = checker.check_24h_volatility()

        # Should return True without prompting
        confirmed = checker.prompt_confirmation(result)
        assert confirmed is True

    def test_error_result_returns_true(self):
        """Test that error result allows continuing."""
        checker = RiskChecker()
        result = VolatilityResult.from_error("API down", threshold=4000.0)

        confirmed = checker.prompt_confirmation(result)
        assert confirmed is True

    @patch("builtins.input", return_value="Y")
    def test_high_risk_user_confirms_yes(self, mock_input):
        """Test high risk + user types 'Y' -> proceed."""
        checker = RiskChecker()
        result = VolatilityResult(
            high=96000.0, low=91000.0, price_range=5000.0,
            threshold=4000.0, is_high_risk=True,
        )

        confirmed = checker.prompt_confirmation(result)
        assert confirmed is True
        mock_input.assert_called_once()

    @patch("builtins.input", return_value="y")
    def test_high_risk_user_confirms_yes_lowercase(self, mock_input):
        """Test confirmation is case-insensitive."""
        checker = RiskChecker()
        result = VolatilityResult(
            high=96000.0, low=91000.0, price_range=5000.0,
            threshold=4000.0, is_high_risk=True,
        )

        confirmed = checker.prompt_confirmation(result)
        assert confirmed is True

    @patch("builtins.input", return_value="N")
    def test_high_risk_user_declines(self, mock_input):
        """Test high risk + user types 'N' -> cancel."""
        checker = RiskChecker()
        result = VolatilityResult(
            high=96000.0, low=91000.0, price_range=5000.0,
            threshold=4000.0, is_high_risk=True,
        )

        confirmed = checker.prompt_confirmation(result)
        assert confirmed is False

    @patch("builtins.input", return_value="")
    def test_high_risk_empty_input_declines(self, mock_input):
        """Test high risk + empty input -> cancel."""
        checker = RiskChecker()
        result = VolatilityResult(
            high=96000.0, low=91000.0, price_range=5000.0,
            threshold=4000.0, is_high_risk=True,
        )

        confirmed = checker.prompt_confirmation(result)
        assert confirmed is False

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_high_risk_ctrl_c_cancels(self, mock_input):
        """Test Ctrl+C during confirmation cancels."""
        checker = RiskChecker()
        result = VolatilityResult(
            high=96000.0, low=91000.0, price_range=5000.0,
            threshold=4000.0, is_high_risk=True,
        )

        confirmed = checker.prompt_confirmation(result)
        assert confirmed is False

    @patch("builtins.input", side_effect=EOFError)
    def test_high_risk_eof_cancels(self, mock_input):
        """Test EOF (piped input) cancels."""
        checker = RiskChecker()
        result = VolatilityResult(
            high=96000.0, low=91000.0, price_range=5000.0,
            threshold=4000.0, is_high_risk=True,
        )

        confirmed = checker.prompt_confirmation(result)
        assert confirmed is False


# --- check_volatility_before_start Tests ---


class TestCheckVolatilityBeforeStart:
    """Tests for the convenience function."""

    @patch("lib.risk_control.requests.get")
    def test_safe_volatility_continues(self, mock_get):
        """Test safe volatility lets startup continue."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAFE_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Should not raise SystemExit
        check_volatility_before_start(threshold=4000.0)

    @patch("builtins.input", return_value="N")
    @patch("lib.risk_control.requests.get")
    def test_high_risk_user_declines_exits(self, mock_get, mock_input):
        """Test high risk + user declines triggers sys.exit."""
        mock_response = MagicMock()
        mock_response.json.return_value = HIGH_RISK_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(SystemExit) as exc_info:
            check_volatility_before_start(threshold=4000.0)
        assert exc_info.value.code == 0

    @patch("builtins.input", return_value="Y")
    @patch("lib.risk_control.requests.get")
    def test_high_risk_user_confirms_continues(self, mock_get, mock_input):
        """Test high risk + user confirms lets startup continue."""
        mock_response = MagicMock()
        mock_response.json.return_value = HIGH_RISK_KLINES
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Should not raise SystemExit
        check_volatility_before_start(threshold=4000.0)
