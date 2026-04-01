"""Fix task13 tests to match new adaptive retry logic in _execute_close_live."""

with open('tests/unit/test_task13_tp_sl_fill_verify.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update _make_strategy to also mock get_best_bid
old_make = '''    mock_bot = MagicMock()
    mock_bot.get_order = AsyncMock()
    mock_bot.place_order = AsyncMock()
    mock_bot.cancel_order = AsyncMock()
    
    # Mock clob_client for get_safe_sell_price
    mock_bot.clob_client = MagicMock()'''

new_make = '''    mock_bot = MagicMock()
    mock_bot.get_order = AsyncMock()
    mock_bot.place_order = AsyncMock()
    mock_bot.cancel_order = AsyncMock()
    mock_bot.get_best_bid = AsyncMock(return_value=0.35)
    
    # Mock clob_client for get_safe_sell_price and pre-fetch
    mock_bot.clob_client = MagicMock()
    mock_bot.clob_client.get_tick_size.return_value = "0.01"
    mock_bot.clob_client.get_neg_risk.return_value = True'''

if old_make in content:
    content = content.replace(old_make, new_make, 1)
    print("Updated _make_strategy")
else:
    print("ERROR: Could not find _make_strategy to update")

# Replace the TestExecuteCloseLiveWithFillVerification class
old_class_start = '''class TestExecuteCloseLiveWithFillVerification:
    """Test _execute_close_live with GTC fill verification."""

    def _make_order_result(self, success: bool = True, order_id: str = "ord_123", status: str = "live"):
        from src.bot import OrderResult
        return OrderResult(success=success, order_id=order_id, status=status, message="ok")

    @pytest.mark.asyncio
    async def test_gtc_order_immediately_matched(self):'''

# Find and replace the entire class
class_start_idx = content.find(old_class_start)
if class_start_idx == -1:
    print("ERROR: Could not find TestExecuteCloseLiveWithFillVerification class")
else:
    # The class extends to end of file
    new_class = '''class TestExecuteCloseLiveWithFillVerification:
    """Test _execute_close_live with adaptive phase-based retry logic.
    
    Phase 1 (retry 0-2): FOK at best bid, no discount, 0.2s delay
    Phase 2 (retry 3-9): FOK with small discount, 0.3s delay
    Phase 3 (retry 10+): GTC with aggressive discount, 0.5s delay
    """

    def _make_order_result(self, success: bool = True, order_id: str = "ord_123", status: str = "live"):
        from src.bot import OrderResult
        return OrderResult(success=success, order_id=order_id, status=status, message="ok")

    @pytest.mark.asyncio
    async def test_gtc_order_immediately_matched(self):
        """Order with status='matched' on first attempt succeeds immediately."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = self._make_order_result(status="matched")
        strategy.bot.get_best_bid.return_value = 0.35
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should have placed the order once and not polled
        strategy.bot.place_order.assert_called_once()
        strategy.bot.get_order.assert_not_called()
        # DB should be updated with sell price
        strategy.db.update_rebound_order_result.assert_called_once()
        call_kwargs = strategy.db.update_rebound_order_result.call_args
        assert call_kwargs[1]["status"] == "closed"

    @pytest.mark.asyncio
    async def test_gtc_order_polls_and_fills(self):
        """Phase 3 GTC order transitions from live to matched via polling."""
        strategy = _make_strategy()

        # First 10 attempts (FOK phase 1+2) fail, 11th (GTC phase 3) gets live then matched
        fok_results = [self._make_order_result(success=True, order_id=f"fok_{i}", status="delayed") for i in range(10)]
        gtc_result = self._make_order_result(status="live", order_id="gtc_1")
        strategy.bot.place_order.side_effect = fok_results + [gtc_result]
        strategy.bot.get_order.return_value = {
            "status": "matched",
            "size_matched": "10.0",
            "original_size": "10.0",
        }
        strategy.bot.get_best_bid.return_value = 0.35
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should have polled the GTC order
        strategy.bot.get_order.assert_called()
        # DB status should be 'closed'
        call_kwargs = strategy.db.update_rebound_order_result.call_args
        assert call_kwargs[1]["status"] == "closed"

    @pytest.mark.asyncio
    async def test_gtc_order_not_filled_cancels_and_retries(self):
        """GTC order not filled -> cancel -> retry with lower price."""
        strategy = _make_strategy()

        # FOK phases all fail (status != matched), then GTC gets live but not filled,
        # then next GTC gets matched
        fok_results = [self._make_order_result(success=True, status="delayed", order_id=f"fok_{i}") for i in range(10)]
        gtc_live = self._make_order_result(status="live", order_id="gtc_1")
        gtc_matched = self._make_order_result(status="matched", order_id="gtc_2")
        strategy.bot.place_order.side_effect = fok_results + [gtc_live, gtc_matched]
        
        # GTC polling: first call returns not filled (live), triggering cancel+retry
        strategy.bot.get_order.return_value = {
            "status": "live",
            "size_matched": "0",
            "original_size": "10.0",
        }
        strategy.bot.cancel_order.return_value = MagicMock(success=True)
        strategy.bot.get_best_bid.return_value = 0.35
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        # Patch _wait_for_order_fill to timeout on first GTC call
        call_count = 0
        original_wait = strategy._wait_for_order_fill

        async def mock_wait(order_id, timeout=15.0, poll_interval=2.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"filled": False, "size_matched": 0, "status": "timeout"}
            return {"filled": True, "size_matched": 10.0, "status": "matched"}

        strategy._wait_for_order_fill = mock_wait

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should have cancelled the first GTC order
        strategy.bot.cancel_order.assert_called_with("gtc_1")

    @pytest.mark.asyncio
    async def test_progressive_discount_increases_on_retries(self):
        """Each retry should apply progressively lower prices."""
        strategy = _make_strategy()

        # All attempts fail
        strategy.bot.place_order.return_value = self._make_order_result(success=False)
        strategy.bot.get_best_bid.return_value = 0.50
        strategy.get_safe_sell_price = AsyncMock(return_value=0.50)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.50, pos_info, db_id=1, reason="tp")

        # Should have attempted max_retries (25) times
        assert strategy.bot.place_order.call_count == 25

        # Verify prices are non-increasing across retries
        prices = []
        for c in strategy.bot.place_order.call_args_list:
            prices.append(c.kwargs.get("price", c[1].get("price") if isinstance(c[1], dict) else None))

        for i in range(1, len(prices)):
            assert prices[i] <= prices[i - 1], f"Price at retry {i} ({prices[i]}) should be <= retry {i-1} ({prices[i-1]})"

    @pytest.mark.asyncio
    async def test_db_status_sell_failed_when_no_fill(self):
        """When all retries fail, DB should have status='sell_failed'."""
        strategy = _make_strategy()
        strategy.bot.place_order.return_value = self._make_order_result(success=False)
        strategy.bot.get_best_bid.return_value = 0.35
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # DB should be updated with status='sell_failed'
        call_kwargs = strategy.db.update_rebound_order_result.call_args
        assert call_kwargs[1]["status"] == "sell_failed"

    @pytest.mark.asyncio
    async def test_fok_order_skips_polling(self):
        """Phase 1 FOK orders should not poll for fill status."""
        strategy = _make_strategy()

        # First FOK attempt succeeds immediately with matched
        strategy.bot.place_order.return_value = self._make_order_result(status="matched")
        strategy.bot.get_best_bid.return_value = 0.35
        strategy.get_safe_sell_price = AsyncMock(return_value=0.35)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.35, pos_info, db_id=1, reason="tp")

        # Should NOT poll order status for FOK
        strategy.bot.get_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_discount_capped_at_50_percent(self):
        """Discount should not exceed 50% regardless of retry count."""
        strategy = _make_strategy()
        strategy.config.strategy3_sell_discount = 0.10  # 10% step

        # Fail all attempts to check discount cap
        strategy.bot.place_order.return_value = self._make_order_result(success=False)
        strategy.bot.get_best_bid.return_value = 0.50
        strategy.get_safe_sell_price = AsyncMock(return_value=0.50)

        pos_info = {"token_id": "token_up", "size": 10.0, "entry_price": 0.30}
        await strategy._execute_close_live("up", 0.50, pos_info, db_id=1, reason="tp")

        # At max retry, discount is capped at 50%, so min price = 0.50 * 0.50 = 0.25
        last_call = strategy.bot.place_order.call_args_list[-1]
        last_price = last_call.kwargs.get("price", last_call[1].get("price") if isinstance(last_call[1], dict) else None)
        # Price should not be lower than 0.50 * 0.50 = 0.25
        assert last_price >= 0.25, f"Price {last_price} should be >= 0.25 (max 50% discount)"
'''

    content = content[:class_start_idx] + new_class
    print("Updated TestExecuteCloseLiveWithFillVerification class")

with open('tests/unit/test_task13_tp_sl_fill_verify.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("File saved")
