#!/usr/bin/env python3
"""
Test script for placing a single order on Polymarket.
This verifies the signing and order submission process.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_order():
    """Test placing a small order."""
    from src.bot import TradingBot
    from src.config import Config
    from src.gamma_client import GammaClient
    
    print("=" * 60)
    print("Testing Order Placement")
    print("=" * 60)
    
    # Load config
    config = Config.load()
    print(f"\n1. Config loaded:")
    print(f"   Safe address: {config.safe_address}")
    print(f"   Signature type: {config.clob.signature_type}")
    print(f"   Chain ID: {config.clob.chain_id}")
    
    # Initialize bot
    print("\n2. Initializing bot...")
    private_key = os.getenv("POLY_PRIVATE_KEY")
    if not private_key:
        print("   ERROR: POLY_PRIVATE_KEY not set")
        return
    
    # Add 0x prefix if missing
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key
    
    bot = TradingBot(config=config, private_key=private_key)
    
    if not bot.is_initialized():
        print("   ERROR: Bot not properly initialized")
        return
    
    print(f"   Bot initialized successfully")
    print(f"   Signer address: {bot.signer.address}")
    
    # Get current BTC market
    print("\n3. Getting current BTC 15-minute market...")
    gc = GammaClient()
    market_data = gc.get_market_info("BTC")
    
    if not market_data:
        print("   ERROR: Could not get current market")
        return
    
    print(f"   Market slug: {market_data.get('slug')}")
    
    # Get token info for "UP" outcome
    token_ids = market_data.get("token_ids", {})
    if not token_ids or "up" not in token_ids:
        print("   ERROR: Could not get UP token")
        print(f"   Available tokens: {list(token_ids.keys()) if token_ids else 'None'}")
        return
    
    up_token = token_ids["up"]
    print(f"   UP token ID: {up_token[:40]}...")
    
    # Place a small test order
    # Use a low price that won't get filled (limit order)
    # Note: If price is close to market price, order becomes "marketable" and needs min $1 size
    test_price = 0.02  # Low price
    test_size = 50.0   # size * price = $1 minimum for marketable orders
    
    print(f"\n4. Placing test order:")
    print(f"   Token: UP")
    print(f"   Side: BUY")
    print(f"   Price: {test_price}")
    print(f"   Size: {test_size}")
    print(f"   Fee rate: 1000 bps (10%)")
    
    try:
        result = await bot.place_order(
            token_id=up_token,
            price=test_price,
            size=test_size,
            side="BUY",
            fee_rate_bps=1000,  # 10% fee for BTC 15m markets
        )
        
        print(f"\n5. Result:")
        print(f"   Success: {result.success}")
        print(f"   Order ID: {result.order_id}")
        print(f"   Status: {result.status}")
        print(f"   Message: {result.message}")
        
        if result.success and result.order_id:
            print(f"\n6. Cancelling test order...")
            # Cancel the order immediately
            try:
                cancel_result = await bot.cancel_order(result.order_id)
                print(f"   Cancel result: {cancel_result}")
            except Exception as e:
                print(f"   Cancel failed: {e}")
        
    except Exception as e:
        print(f"\n   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_order())
