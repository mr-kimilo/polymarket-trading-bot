#!/usr/bin/env python3
"""
Rebound Strategy Runner

Entry point for running the Rebound strategy.

策略说明:
策略1 (strategy.type="1"):
- 在15分钟周期的A段（15-10分钟），当检测到UP或DOWN价格
  快速下跌到30以下且BTC下跌不超过50美元时，买入下跌方

策略2 (strategy.type="2"):
- 在15分钟周期的C段（5-0分钟），当检测到UP或DOWN价格
  快速下跌到15以下且BTC下跌不超过30美元时，买入下跌方

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
import yaml
from pathlib import Path

# Auto-load .env file early
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path early
sys.path.insert(0, str(Path(__file__).parent.parent))

# Suppress noisy logs
logging.getLogger("src.websocket_client").setLevel(logging.WARNING)
logging.getLogger("src.bot").setLevel(logging.WARNING)

from lib.console import Colors
from src.bot import TradingBot
from src.config import Config
from strategies.rebound import ReboundStrategy, ReboundConfig


def load_strategy_type_from_config() -> str:
    """从config.yaml加载strategy.type配置"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            strategy_type = config.get("strategy", {}).get("type", "1")
            return str(strategy_type)
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Failed to load strategy type from config: {e}{Colors.RESET}")
    return "1"  # 默认策略1


def main():
    """Main entry point."""
    # 首先从config.yaml加载strategy.type
    strategy_type = load_strategy_type_from_config()
    
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
        default=None,  # 将由strategy_type决定
        help="Price must drop below this value to trigger (auto-set by strategy type)"
    )
    parser.add_argument(
        "--btc-drop-max",
        type=float,
        default=None,  # 将由strategy_type决定
        help="Maximum BTC price drop allowed in USD (auto-set by strategy type)"
    )
    parser.add_argument(
        "--segments",
        type=str,
        default=None,  # 将由strategy_type决定
        help="Active segments for trading, comma separated (auto-set by strategy type)"
    )
    parser.add_argument(
        "--strategy-type",
        type=str,
        default=None,
    choices=["1", "2", "3"],
    help="Strategy type: 1=A段/30%%/50USD, 2=C段/15%%/30USD, 3=P&L mode (take-profit / stop-loss). Default: from config.yaml"
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
    
    # 确定策略类型：命令行参数优先，否则使用config.yaml中的配置
    final_strategy_type = args.strategy_type if args.strategy_type else strategy_type
    
    # 根据策略类型设置默认值
    if final_strategy_type == "2":
        # 策略2: C段, UP/DOWN<15%, BTC下跌<30
        default_threshold = 0.15
        default_btc_drop = 30.0
        default_segments = "C"
        strategy_desc = "策略2: C段(5-0分钟), UP/DOWN<15%, BTC下跌<$30"
    else:
        # 策略1: A段, UP/DOWN<30%, BTC下跌<50
        default_threshold = 0.30
        default_btc_drop = 50.0
        default_segments = "A"
        strategy_desc = "策略1: A段(15-10分钟), UP/DOWN<30%, BTC下跌<$50"
    
    # 使用命令行参数覆盖，如果未指定则使用策略默认值
    drop_threshold = args.drop_threshold if args.drop_threshold is not None else default_threshold
    btc_drop_max = args.btc_drop_max if args.btc_drop_max is not None else default_btc_drop
    segments = args.segments if args.segments is not None else default_segments
    
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
    print(f"{Colors.CYAN}{strategy_desc}{Colors.RESET}")
    print(f"Coin: {args.coin}")
    print(f"Size: ${args.size:.2f} USDC")
    print(f"Drop Threshold: {drop_threshold:.2f}")
    print(f"BTC Drop Max: ${btc_drop_max:.2f}")
    print(f"Active Segments: {segments}")
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
    active_segments = [s.strip().upper() for s in segments.split(",")]
    
    strategy_config = ReboundConfig(
        strategy_type=final_strategy_type,
        coin=args.coin,
        size=args.size,
        price_drop_threshold=drop_threshold,
        btc_drop_max=btc_drop_max,
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
