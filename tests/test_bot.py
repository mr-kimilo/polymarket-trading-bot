"""
Unit Tests for Bot Module

Tests the TradingBot class and related functionality.

Run with:
    pytest tests/test_bot.py -v
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import TradingBot, OrderResult, NotInitializedError
from src.config import Config, BuilderConfig, ClobConfig


class TestOrderResult:
    """Tests for OrderResult dataclass."""

    def test_from_response_success(self):
        """Test creating OrderResult from successful response."""
        response = {
            "success": True,
            "orderId": "order_123",
            "status": "live"
        }

        result = OrderResult.from_response(response)

        assert result.success is True
        assert result.order_id == "order_123"
        assert result.status == "live"
        assert "successfully" in result.message.lower()

    def test_from_response_failure(self):
        """Test creating OrderResult from failed response."""
        response = {
            "success": False,
            "errorMsg": "Insufficient balance"
        }

        result = OrderResult.from_response(response)

        assert result.success is False
        assert result.message == "Insufficient balance"

    def test_order_result_defaults(self):
        """Test OrderResult default values."""
        result = OrderResult(success=True, message="Test")

        assert result.order_id is None
        assert result.status is None
        assert result.data == {}


class TestTradingBot:
    """Tests for TradingBot class."""

    TEST_PRIVATE_KEY = "0x" + "a" * 64
    TEST_SAFE_ADDRESS = "0x" + "b" * 40

    def test_init_with_config(self):
        """Test initialization with Config object."""
        config = Config(
            safe_address=self.TEST_SAFE_ADDRESS,
            use_gasless=False
        )

        bot = TradingBot(config=config)

        assert bot.config == config
        assert bot.signer is None  # No private key provided

    def test_init_with_private_key(self):
        """Test initialization with private key."""
        bot = TradingBot(
            private_key=self.TEST_PRIVATE_KEY,
            safe_address=self.TEST_SAFE_ADDRESS
        )

        assert bot.signer is not None
        # Signer address is derived from private key, not safe_address
        assert bot.signer.address.startswith("0x")
        assert len(bot.signer.address) == 42

    def test_init_with_partial_params(self):
        """Test initialization with partial parameters."""
        # Should work with just safe_address
        bot = TradingBot(safe_address=self.TEST_SAFE_ADDRESS)

        assert bot.config.safe_address == self.TEST_SAFE_ADDRESS

    def test_is_initialized_without_signer(self):
        """Test is_initialized returns False without signer."""
        bot = TradingBot(safe_address=self.TEST_SAFE_ADDRESS)

        assert bot.is_initialized() is False

    def test_is_initialized_with_signer(self):
        """Test is_initialized returns True with signer."""
        bot = TradingBot(
            private_key=self.TEST_PRIVATE_KEY,
            safe_address=self.TEST_SAFE_ADDRESS
        )

        assert bot.is_initialized() is True

    def test_require_signer_without_signer(self):
        """Test require_signer raises when no signer."""
        bot = TradingBot(safe_address=self.TEST_SAFE_ADDRESS)

        with pytest.raises(NotInitializedError):
            bot.require_signer()

    def test_require_signer_with_signer(self):
        """Test require_signer returns signer when available."""
        bot = TradingBot(
            private_key=self.TEST_PRIVATE_KEY,
            safe_address=self.TEST_SAFE_ADDRESS
        )

        signer = bot.require_signer()
        assert signer is not None
        # Signer address is derived from private key
        assert signer.address.startswith("0x")
        assert len(signer.address) == 42

    def test_config_from_yaml(self, tmp_path):
        """Test loading config from YAML file."""
        config_content = '''
safe_address: "0x1234567890123456789012345678901234567890"
rpc_url: https://polygon-rpc.com
default_token_id: "0xabcdef1234567890"
default_size: 5.0
default_price: 0.65
data_dir: test_credentials
log_level: DEBUG
'''
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = Config.load(str(config_file))

        assert config.safe_address == "0x1234567890123456789012345678901234567890"
        assert config.rpc_url == "https://polygon-rpc.com"
        assert config.default_token_id == "0xabcdef1234567890"
        assert config.default_size == 5.0
        assert config.default_price == 0.65
        assert config.data_dir == "test_credentials"
        assert config.log_level == "DEBUG"

    def test_config_with_builder_credentials(self, tmp_path):
        """Test config with Builder credentials enables gasless."""
        config_content = '''
safe_address: "0x1234567890123456789012345678901234567890"
builder:
  api_key: test_key_123
  api_secret: secret_abc
  api_passphrase: passphrase_xyz
'''
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = Config.load(str(config_file))

        assert config.use_gasless is True
        assert config.builder.is_configured()

    def test_config_without_builder_credentials(self, tmp_path):
        """Test config without Builder credentials disables gasless."""
        config_content = '''
safe_address: "0x1234567890123456789012345678901234567890"
builder:
  api_key: ""
  api_secret: ""
  api_passphrase: ""
'''
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = Config.load(str(config_file))

        assert config.use_gasless is False
        assert config.builder.is_configured() is False

    def test_config_validate_missing_safe_address(self, tmp_path):
        """Test config validation fails without safe_address."""
        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert any("safe_address" in error for error in errors)

    def test_config_validate_valid_config(self, tmp_path):
        """Test config validation passes with valid config."""
        config = Config(safe_address=self.TEST_SAFE_ADDRESS)
        errors = config.validate()

        assert len(errors) == 0

    def test_create_order_dict(self):
        """Test creating order dictionary."""
        bot = TradingBot(
            private_key=self.TEST_PRIVATE_KEY,
            safe_address=self.TEST_SAFE_ADDRESS
        )

        order_dict = bot.create_order_dict(
            token_id="1234567890",
            price=0.65,
            size=10.0,
            side="BUY"
        )

        assert order_dict["token_id"] == "1234567890"
        assert order_dict["price"] == 0.65
        assert order_dict["size"] == 10.0
        assert order_dict["side"] == "BUY"

    def test_create_order_dict_side_normalized(self):
        """Test that side is normalized to uppercase."""
        bot = TradingBot(
            private_key=self.TEST_PRIVATE_KEY,
            safe_address=self.TEST_SAFE_ADDRESS
        )

        order_dict = bot.create_order_dict(
            token_id="1234567890",
            price=0.65,
            size=10.0,
            side="buy"
        )

        assert order_dict["side"] == "BUY"


class TestCreateBot:
    """Tests for create_bot convenience function."""

    def test_create_bot_with_config_path(self, tmp_path):
        """Test create_bot with config path."""
        config_content = '''
safe_address: "0x1234567890123456789012345678901234567890"
'''
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        bot = TradingBot(config_path=str(config_file))

        assert bot.config.safe_address == "0x1234567890123456789012345678901234567890"


class TestPlaceOrder:
    """Tests for TradingBot.place_order method."""

    TEST_PRIVATE_KEY = "0x" + "a" * 64
    TEST_SAFE_ADDRESS = "0x" + "b" * 40
    TEST_TOKEN_ID = "71321045679252212594626385532706912750332728571942532289631379312455583992563"

    def _create_bot_with_mock_clob(self):
        """Create a TradingBot with mocked _py_client and clob_client."""
        bot = TradingBot(
            private_key=self.TEST_PRIVATE_KEY,
            safe_address=self.TEST_SAFE_ADDRESS,
        )
        mock_clob = MagicMock()
        mock_clob.get_tick_size.return_value = "0.01"
        mock_clob.get_neg_risk.return_value = True
        mock_clob.get_fee_rate_bps.return_value = 0
        mock_clob.create_order.return_value = MagicMock()
        mock_clob.create_market_order.return_value = MagicMock()
        mock_clob.post_order.return_value = {"success": True, "orderId": "test_order"}
        bot.clob_client = mock_clob
        bot._py_client = mock_clob

        # Patch _run_in_thread to call sync functions directly (avoid threading issues with mocks)
        async def direct_call(func, *args, **kwargs):
            return func(*args, **kwargs)
        bot._run_in_thread = direct_call

        return bot, mock_clob

    @pytest.mark.asyncio
    async def test_place_sell_order_creates_valid_order_args(self):
        """Test that SELL order uses correct OrderArgs without salt."""
        bot, mock_clob = self._create_bot_with_mock_clob()

        mock_signed_order = MagicMock()
        mock_clob.create_order.return_value = mock_signed_order
        mock_clob.post_order.return_value = {
            "success": True,
            "orderId": "sell_123",
            "status": "matched",
        }

        result = await bot.place_order(
            token_id=self.TEST_TOKEN_ID,
            price=0.55,
            size=5.0,
            side="SELL",
            fee_rate_bps=1000,
        )

        # Verify order was created successfully (no TypeError from invalid salt)
        assert result.success is True
        assert result.order_id == "sell_123"

        # Verify create_order was called with correct args
        call_args = mock_clob.create_order.call_args
        order_args = call_args[0][0]
        assert order_args.token_id == self.TEST_TOKEN_ID
        assert order_args.side == "SELL"
        assert order_args.size == 5.0
        assert order_args.price == 0.55
        assert order_args.fee_rate_bps == 1000

    @pytest.mark.asyncio
    async def test_place_buy_order_creates_valid_order_args(self):
        """Test that BUY order uses correct OrderArgs without salt."""
        bot, mock_clob = self._create_bot_with_mock_clob()

        mock_clob.create_order.return_value = MagicMock()
        mock_clob.post_order.return_value = {
            "success": True,
            "orderId": "buy_456",
            "status": "live",
        }

        result = await bot.place_order(
            token_id=self.TEST_TOKEN_ID,
            price=0.45,
            size=10.0,
            side="BUY",
        )

        assert result.success is True
        assert result.order_id == "buy_456"

        call_args = mock_clob.create_order.call_args
        order_args = call_args[0][0]
        assert order_args.side == "BUY"
        assert order_args.price == 0.45
        assert order_args.size == 10.0

    @pytest.mark.asyncio
    async def test_place_order_with_cached_tick_size_skips_api_call(self):
        """Test that cached tick_size avoids redundant API call."""
        bot, mock_clob = self._create_bot_with_mock_clob()

        mock_clob.create_order.return_value = MagicMock()
        mock_clob.post_order.return_value = {
            "success": True,
            "orderId": "cached_789",
            "status": "matched",
        }

        result = await bot.place_order(
            token_id=self.TEST_TOKEN_ID,
            price=0.50,
            size=5.0,
            side="SELL",
            tick_size="0.01",
            neg_risk=True,
        )

        assert result.success is True
        # tick_size and neg_risk not fetched from API
        mock_clob.get_tick_size.assert_not_called()
        mock_clob.get_neg_risk.assert_not_called()

    @pytest.mark.asyncio
    async def test_place_order_fok_order_type(self):
        """Test that FOK order uses create_market_order and passes FOK to post_order."""
        bot, mock_clob = self._create_bot_with_mock_clob()

        mock_clob.create_market_order.return_value = MagicMock()
        mock_clob.post_order.return_value = {
            "success": True,
            "orderId": "fok_001",
            "status": "matched",
        }

        result = await bot.place_order(
            token_id=self.TEST_TOKEN_ID,
            price=0.40,
            size=5.0,
            side="SELL",
            order_type="FOK",
        )

        assert result.success is True
        # FOK should use create_market_order, not create_order
        mock_clob.create_market_order.assert_called_once()
        mock_clob.create_order.assert_not_called()
        # Verify post_order was called with FOK OrderType
        post_call = mock_clob.post_order.call_args
        order_type_arg = post_call[0][1]
        assert str(order_type_arg) == "FOK" or order_type_arg == "FOK"

    @pytest.mark.asyncio
    async def test_place_order_adjusts_price_to_tick(self):
        """Test that price is adjusted to tick boundary."""
        bot, mock_clob = self._create_bot_with_mock_clob()

        mock_clob.create_order.return_value = MagicMock()
        mock_clob.post_order.return_value = {
            "success": True,
            "orderId": "tick_adj",
            "status": "live",
        }

        # Price 0.456 should be rounded to 0.45 with tick=0.01
        await bot.place_order(
            token_id=self.TEST_TOKEN_ID,
            price=0.456,
            size=5.0,
            side="SELL",
        )

        call_args = mock_clob.create_order.call_args
        order_args = call_args[0][0]
        assert order_args.price == 0.45

    @pytest.mark.asyncio
    async def test_place_order_error_msg_marks_failure(self):
        """Test that API errorMsg correctly marks order as failed."""
        bot, mock_clob = self._create_bot_with_mock_clob()

        mock_clob.create_order.return_value = MagicMock()
        mock_clob.post_order.return_value = {
            "success": True,
            "errorMsg": "INVALID_ORDER_NOT_ENOUGH_BALANCE",
            "orderId": None,
        }

        result = await bot.place_order(
            token_id=self.TEST_TOKEN_ID,
            price=0.50,
            size=5.0,
            side="SELL",
        )

        # success=True + errorMsg means order was rejected
        assert result.success is False
        assert "BALANCE" in result.message


class TestGetBestBid:
    """Tests for TradingBot.get_best_bid method."""

    TEST_PRIVATE_KEY = "0x" + "a" * 64
    TEST_SAFE_ADDRESS = "0x" + "b" * 40

    def _create_bot_with_mock(self):
        """Create a TradingBot with mocked clob_client and direct _run_in_thread."""
        bot = TradingBot(
            private_key=self.TEST_PRIVATE_KEY,
            safe_address=self.TEST_SAFE_ADDRESS,
        )
        mock_clob = MagicMock()
        bot.clob_client = mock_clob

        async def direct_call(func, *args, **kwargs):
            return func(*args, **kwargs)
        bot._run_in_thread = direct_call

        return bot, mock_clob

    @pytest.mark.asyncio
    async def test_get_best_bid_returns_highest_bid(self):
        """Test that get_best_bid returns the highest valid bid."""
        bot, mock_clob = self._create_bot_with_mock()
        mock_clob.get_order_book.return_value = {
            "bids": [
                {"price": "0.45", "size": "100"},
                {"price": "0.50", "size": "50"},
                {"price": "0.48", "size": "200"},
            ]
        }

        best_bid = await bot.get_best_bid("token_123")

        assert best_bid == 0.50

    @pytest.mark.asyncio
    async def test_get_best_bid_empty_orderbook(self):
        """Test that get_best_bid returns None for empty orderbook."""
        bot, mock_clob = self._create_bot_with_mock()
        mock_clob.get_order_book.return_value = {"bids": []}

        best_bid = await bot.get_best_bid("token_123")

        assert best_bid is None

    @pytest.mark.asyncio
    async def test_get_best_bid_filters_dust_prices(self):
        """Test that bids <= 0.01 are filtered out."""
        bot, mock_clob = self._create_bot_with_mock()
        mock_clob.get_order_book.return_value = {
            "bids": [
                {"price": "0.01", "size": "1000"},
                {"price": "0.005", "size": "500"},
            ]
        }

        best_bid = await bot.get_best_bid("token_123")

        assert best_bid is None

    @pytest.mark.asyncio
    async def test_get_best_bid_api_error_returns_none(self):
        """Test that API errors return None gracefully."""
        bot, mock_clob = self._create_bot_with_mock()
        mock_clob.get_order_book.side_effect = Exception("API timeout")

        best_bid = await bot.get_best_bid("token_123")

        assert best_bid is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
