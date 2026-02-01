#!/usr/bin/env python3
"""
Direct Sell Script - 直接卖出所有持仓

当需要紧急退出或手动干预时使用此脚本。
将直接以市价卖出所有活跃持仓。

Usage:
    python scripts/direct_sell.py --coin BTC [--live]

Options:
    --coin      币种 (BTC, ETH, etc.)
    --live      启用真实交易模式（默认为模拟模式）
    --reason    卖出原因说明
"""

import os
import sys
import asyncio
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Direct sell all positions")
    parser.add_argument("--coin", type=str, default="BTC", help="Coin to monitor (default: BTC)")
    parser.add_argument("--live", action="store_true", help="Enable LIVE trading mode")
    parser.add_argument("--reason", type=str, default="manual_exit", help="Reason for selling")
    args = parser.parse_args()
    
    from src.bot import TradingBot
    from strategies.rebound import ReboundStrategy, ReboundConfig
    
    print("=" * 60)
    print("DIRECT SELL - 直接卖出所有持仓")
    print("=" * 60)
    
    # Determine mode
    simulation_mode = not args.live
    mode_str = "SIMULATION" if simulation_mode else "LIVE"
    
    print(f"Mode: {mode_str}")
    print(f"Coin: {args.coin}")
    print(f"Reason: {args.reason}")
    print()
    
    if not simulation_mode:
        print("⚠️  WARNING: LIVE MODE - Real trades will be executed!")
        print("    Press Ctrl+C within 5 seconds to cancel...")
        try:
            import time
            for i in range(5, 0, -1):
                print(f"    {i}...")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user.")
            return 1
        print()
    
    # Initialize bot
    try:
        bot = TradingBot(config_path="config.yaml")
    except Exception as e:
        print(f"❌ Failed to initialize bot: {e}")
        return 1
    
    # Create strategy config with direct_sell_enabled
    config = ReboundConfig(
        coin=args.coin,
        simulation_mode=simulation_mode,
        direct_sell_enabled=True,  # Enable direct sell
    )
    
    # Create strategy
    strategy = ReboundStrategy(bot=bot, config=config)
    
    async def run_direct_sell():
        """Execute direct sell"""
        try:
            # Connect to market to get current positions
            print("Connecting to market...")
            await strategy.market.connect()
            
            # Wait for connection
            await asyncio.sleep(2)
            
            if not strategy.is_connected:
                print("❌ Failed to connect to market")
                return False
            
            print(f"✓ Connected to market: {strategy.current_market.slug if strategy.current_market else 'N/A'}")
            
            # Check for active positions
            if not strategy._active_positions:
                print("\n📋 No active positions found.")
                print("   Note: This script only sees positions opened by the current session.")
                print("   To sell positions from previous sessions, you need to:")
                print("   1. Query open orders from database")
                print("   2. Or manually place sell orders via the API")
                return True
            
            # Display positions
            print(f"\n📋 Found {len(strategy._active_positions)} active position(s):")
            for side, pos_info in strategy._active_positions.items():
                entry_price = pos_info.get("entry_price", 0)
                size = pos_info.get("size", 0)
                print(f"   - {side.upper()}: entry={entry_price:.4f}, size={size:.2f}")
            
            # Execute direct sell
            print("\n🚀 Executing direct sell...")
            results = await strategy.direct_sell_all_positions(reason=args.reason)
            
            # Display results
            print("\n📊 Results:")
            for side, success in results.items():
                status = "✓ Success" if success else "✗ Failed"
                print(f"   - {side.upper()}: {status}")
            
            return all(results.values()) if results else True
            
        except Exception as e:
            print(f"❌ Error during direct sell: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Disconnect
            if strategy.market.ws:
                await strategy.market.ws.close()
    
    # Run async function
    success = asyncio.run(run_direct_sell())
    
    if success:
        print("\n✓ Direct sell completed successfully.")
        return 0
    else:
        print("\n✗ Direct sell completed with errors.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
