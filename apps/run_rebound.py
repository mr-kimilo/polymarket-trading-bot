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


def start_api_server_background(port: int = 5000, host: str = "0.0.0.0"):
    """
    在后台线程中启动API服务器 (任务62, 任务67)
    
    Args:
        port: API服务器端口
        host: API服务器主机地址
    """
    import threading
    import time
    
    def run_server():
        try:
            # 导入API模块
            from scripts.strategy_api import create_flask_app
            
            # 创建Flask应用
            app = create_flask_app()
            if app:
                # 禁用Flask的debug模式和reloader，避免冲突
                app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
        except Exception as e:
            print(f"{Colors.YELLOW}API服务器启动失败: {e}{Colors.RESET}", flush=True)
            print(f"{Colors.YELLOW}提示: 如需API功能，请安装Flask: pip install flask{Colors.RESET}", flush=True)
    
    # 在守护线程中运行API服务器
    api_thread = threading.Thread(target=run_server, daemon=True, name="APIServer")
    api_thread.start()
    
    # 等待Flask服务器启动
    time.sleep(0.5)
    
    # 获取实际的访问地址
    display_host = "localhost" if host == "0.0.0.0" else host
    base_url = f"http://{display_host}:{port}"
    
    print(f"{Colors.GREEN}✓ API服务器已启动在后台 ({base_url}){Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  [规则管理 API]{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - POST {base_url}/rules/active - 激活规则{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - GET  {base_url}/rules/query - 查询规则{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - POST {base_url}/rules/create - 创建规则{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - GET  {base_url}/rules/active/<env> - 获取激活规则{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  [订单调度 API] (任务65/66/67){Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - POST {base_url}/orderSchedule/create - 创建调度计划{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - POST {base_url}/orderSchedule/cancel - 取消调度计划{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - GET  {base_url}/orderSchedule/query - 查询调度计划{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - GET  {base_url}/orderSchedule/check - 检查是否应该交易{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  [API文档]{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}  - 完整文档: docs/api/order-schedule-api.md{Colors.RESET}\n", flush=True)


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


def load_direct_sell_from_config() -> bool:
    """从config.yaml加载direct_sell配置"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config.get("direct_sell", {}).get("enabled", False)
        except Exception:
            pass
    return False


def load_order_schedule_from_config() -> bool:
    """从config.yaml加载order_schedule配置 (任务68)"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config.get("order_schedule", {}).get("enabled", False)
        except Exception:
            pass
    return False


def load_auto_claim_from_config() -> dict:
    """从config.yaml加载auto_claim配置"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    defaults = {
        "enabled": True,
        "min_balance": 5.0,
        "check_interval": 300  # 秒
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            auto_claim = config.get("auto_claim", {})
            
            # 从配置中获取值，check_interval需要从分钟转换为秒
            return {
                "enabled": auto_claim.get("enabled", defaults["enabled"]),
                "min_balance": auto_claim.get("min_balance", defaults["min_balance"]),
                "check_interval": auto_claim.get("check_interval", 5) * 60  # 分钟转秒
            }
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Failed to load auto_claim config: {e}{Colors.RESET}")
    
    return defaults


def load_profit_and_loss_from_config() -> dict:
    """从config.yaml加载profit_and_loss配置 (任务61)"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    defaults = {
        "enabled": False,
        "strategy3_take_profit_base": 0.8,
        "strategy3_take_profit_pullback": 0.1,
        "strategy3_stop_loss_stage_a": 0.35,
        "strategy3_stop_loss_stage_bc": 0.2,
        "strategy3_use_gtc_order": True,
        "strategy3_sell_discount": 0.03
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            pnl = config.get("profit_and_loss", {})
            
            return {
                "enabled": pnl.get("enabled", defaults["enabled"]),
                "strategy3_take_profit_base": pnl.get("strategy3_take_profit_base", defaults["strategy3_take_profit_base"]),
                "strategy3_take_profit_pullback": pnl.get("strategy3_take_profit_pullback", defaults["strategy3_take_profit_pullback"]),
                "strategy3_stop_loss_stage_a": pnl.get("strategy3_stop_loss_stage_a", defaults["strategy3_stop_loss_stage_a"]),
                "strategy3_stop_loss_stage_bc": pnl.get("strategy3_stop_loss_stage_bc", defaults["strategy3_stop_loss_stage_bc"]),
                "strategy3_use_gtc_order": pnl.get("strategy3_use_gtc_order", defaults["strategy3_use_gtc_order"]),
                "strategy3_sell_discount": pnl.get("strategy3_sell_discount", defaults["strategy3_sell_discount"])
            }
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Failed to load profit_and_loss config: {e}{Colors.RESET}")
    
    return defaults


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
    parser.add_argument(
        "--api-port",
        type=int,
        default=5000,
        help="API server port (default: 5000)"
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
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}Rebound Strategy{Colors.RESET}", flush=True)
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}", flush=True)
    print(f"Mode: {mode_str}", flush=True)
    print(f"{Colors.CYAN}{strategy_desc}{Colors.RESET}", flush=True)
    print(f"Coin: {args.coin}", flush=True)
    print(f"Size: ${args.size:.2f} USDC", flush=True)
    print(f"Drop Threshold: {drop_threshold:.2f}", flush=True)
    print(f"BTC Drop Max: ${btc_drop_max:.2f}", flush=True)
    print(f"Active Segments: {segments}", flush=True)
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n", flush=True)
    
    # 启动API服务器 (任务62)
    # 在后台启动API服务器，使其他系统可以调用策略管理接口
    try:
        api_port = args.api_port if hasattr(args, 'api_port') else 5000
        start_api_server_background(port=api_port)
    except Exception as e:
        print(f"{Colors.YELLOW}注意: API服务器启动失败 - {e}{Colors.RESET}", flush=True)
        print(f"{Colors.YELLOW}策略将继续运行，但API功能不可用{Colors.RESET}\n", flush=True)
    
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
    
    # Load direct_sell setting from config
    direct_sell_enabled = load_direct_sell_from_config()
    
    # Load auto_claim settings from config
    auto_claim_config = load_auto_claim_from_config()
    
    # Load profit_and_loss settings from config (任务61)
    pnl_config = load_profit_and_loss_from_config()
    
    # Load order_schedule setting from config (任务68)
    order_schedule_enabled = load_order_schedule_from_config()
    
    strategy_config = ReboundConfig(
        strategy_type=final_strategy_type,
        coin=args.coin,
        size=args.size,
        price_drop_threshold=drop_threshold,
        btc_drop_max=btc_drop_max,
        active_segments=active_segments,
        simulation_mode=simulation_mode,
        direct_sell_enabled=direct_sell_enabled,
        auto_claim_enabled=auto_claim_config["enabled"],
        auto_claim_min_balance=auto_claim_config["min_balance"],
        auto_claim_check_interval=auto_claim_config["check_interval"],
        # 任务61: P&L配置
        profit_and_loss_enabled=pnl_config["enabled"],
        strategy3_take_profit_base=pnl_config["strategy3_take_profit_base"],
        strategy3_take_profit_pullback=pnl_config["strategy3_take_profit_pullback"],
        strategy3_stop_loss_stage_a=pnl_config["strategy3_stop_loss_stage_a"],
        strategy3_stop_loss_stage_bc=pnl_config["strategy3_stop_loss_stage_bc"],
        strategy3_use_gtc_order=pnl_config["strategy3_use_gtc_order"],
        strategy3_sell_discount=pnl_config["strategy3_sell_discount"],
        # 任务68: Order Schedule配置
        order_schedule_enabled=order_schedule_enabled
    )

    # Create and run strategy
    strategy = ReboundStrategy(bot, strategy_config)
    
    try:
        asyncio.run(strategy.run())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Strategy stopped by user.{Colors.RESET}", flush=True)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}", flush=True)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
