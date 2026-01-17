#!/usr/bin/env python3
"""
Rebound Strategy Runner

Entry point for running the Rebound strategy.

策略说明:
- 在15分钟周期的A段（15-10分钟），当检测到UP或DOWN价格
  快速下跌到30以下且BTC下跌不超过50美元时，买入下跌方
- 持有到15分钟结束
- 支持模拟模式（--simulation）用于回测

Usage:
    # 模拟模式（默认）
    python apps/run_rebound.py --coin BTC
    
    # 真实交易模式（谨慎使用）
    python apps/run_rebound.py --coin BTC --live
    
    # 自定义参数
    python apps/run_rebound.py --coin BTC --size 20 --drop-threshold 0.25
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Suppress noisy logs
logging.getLogger("src.websocket_client").setLevel(logging.WARNING)
logging.getLogger("src.bot").setLevel(logging.WARNING)

# Auto-load .env file
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.console import Colors
from src.bot import TradingBot
from src.config import Config
from strategies.rebound import ReboundStrategy, ReboundConfig


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Rebound Strategy for Polymarket 15-minute markets"
    )
    parser.add_argument(
        "--coin",
        type=str,
        default="BTC",
        choices=["BTC", "ETH", "SOL", "XRP"],
        help="Coin to trade (default: BTC)"
    )
    parser.add_argument(
        "--size",
        type=float,
        default=10.0,
        help="Trade size in USDC (default: 10.0)"
    )
    parser.add_argument(
        "--drop-threshold",
        type=float,
        default=0.30,
        help="Price must drop below this value to trigger (default: 0.30)"
    )
    parser.add_argument(
        "--btc-drop-max",
        type=float,
        default=50.0,
        help="Maximum BTC price drop allowed in USD (default: 50.0)"
    )
    parser.add_argument(
        "--segments",
        type=str,
        default="A",
        help="Active segments for trading, comma separated (default: A)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable LIVE trading mode (default: simulation mode)"
    )
    parser.add_argument(
        "--simulation",
        action="store_true",
        default=True,
        help="Enable simulation mode (default: True)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()
    
    # 确定模式
    simulation_mode = not args.live
    
    # Enable debug logging if requested
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("src.websocket_client").setLevel(logging.DEBUG)

    # Check environment
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    safe_address = os.environ.get("POLY_SAFE_ADDRESS")

    if not simulation_mode and (not private_key or not safe_address):
        print(f"{Colors.RED}Error: POLY_PRIVATE_KEY and POLY_SAFE_ADDRESS must be set for LIVE mode{Colors.RESET}")
        print("Set them in .env file or export as environment variables")
        print("Or use --simulation mode for testing")
        sys.exit(1)

    # Print startup info
    mode_str = f"{Colors.YELLOW}SIMULATION{Colors.RESET}" if simulation_mode else f"{Colors.RED}LIVE TRADING{Colors.RESET}"
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}Rebound Strategy{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"Mode: {mode_str}")
    print(f"Coin: {args.coin}")
    print(f"Size: ${args.size:.2f} USDC")
    print(f"Drop Threshold: {args.drop_threshold:.2f}")
    print(f"BTC Drop Max: ${args.btc_drop_max:.2f}")
    print(f"Active Segments: {args.segments}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    
    if not simulation_mode:
        print(f"{Colors.RED}WARNING: LIVE TRADING MODE ENABLED!{Colors.RESET}")
        print(f"{Colors.RED}Real orders will be placed. Press Ctrl+C within 5 seconds to cancel.{Colors.RESET}\n")
        try:
            import time
            for i in range(5, 0, -1):
                print(f"Starting in {i}...", end="\r")
                time.sleep(1)
            print()
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Cancelled by user.{Colors.RESET}")
            sys.exit(0)

    # Initialize bot (only needed for live trading)
    bot = None
    if not simulation_mode:
        try:
            config = Config.load("config.yaml")
        except Exception:
            config = Config()
        
        config.safe_address = safe_address
        
        bot = TradingBot(
            config=config,
            private_key=private_key
        )
        
        if not bot.is_initialized():
            print(f"{Colors.RED}Error: Failed to initialize trading bot{Colors.RESET}")
            sys.exit(1)
    else:
        # 模拟模式下创建一个虚拟的bot对象
        bot = None

    # Create strategy config
    active_segments = [s.strip().upper() for s in args.segments.split(",")]
    
    strategy_config = ReboundConfig(
        coin=args.coin,
        size=args.size,
        price_drop_threshold=args.drop_threshold,
        btc_drop_max=args.btc_drop_max,
        active_segments=active_segments,
        simulation_mode=simulation_mode
    )

    # Create and run strategy
    strategy = ReboundStrategy(bot, strategy_config)
    
    try:
        asyncio.run(strategy.run())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Strategy stopped by user.{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
