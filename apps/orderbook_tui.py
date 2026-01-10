#!/usr/bin/env python3
"""
Orderbook TUI - Real-time Orderbook Viewer

A terminal-based UI for viewing real-time orderbook data
for Polymarket 15-minute markets.

Features:
- Real-time WebSocket orderbook updates
- Dual orderbook display (Up/Down)
- Market countdown timer
- Price history tracking

Usage:
    python apps/orderbook_tui.py --coin ETH
    python apps/orderbook_tui.py --coin BTC
"""

import os
import sys
import asyncio
import argparse
import logging
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque

# Import rich for terminal UI
from rich.console import Console
from rich.live import Live
from rich.text import Text

# Suppress noisy logs
logging.getLogger("src.websocket_client").setLevel(logging.WARNING)

# Auto-load .env file
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import MarketManager, PriceTracker, Colors
from lib.console import format_countdown


class PriceSnapshot:
    """每分钟价格快照"""
    def __init__(self, timestamp: float, up_price: float, down_price: float, 
                 btc_price: Optional[float] = None, minute_index: int = 0):
        self.timestamp = timestamp
        self.up_price = up_price
        self.down_price = down_price
        self.btc_price_start = btc_price  # 该分钟开始时的BTC价格
        self.btc_price_end: Optional[float] = btc_price  # 该分钟结束时的BTC价格
        self.minute = int(timestamp / 60)  # 用于去重
        self.minute_index = minute_index  # 15分钟周期内的第几分钟 (1-15)


class OrderbookTUI:
    """Real-time orderbook viewer with enhanced price tracking."""

    def __init__(self, coin: str = "ETH"):
        """Initialize TUI."""
        self.coin = coin.upper()
        self.market = MarketManager(coin=self.coin)
        self.prices = PriceTracker()
        self.running = False
        
        # 记录市场开始时的价格
        self.start_prices: Dict[str, Optional[float]] = {
            "up": None,
            "down": None
        }
        self.market_start_time: Optional[float] = None
        
        # 每分钟价格快照（最多保存15个）
        self.minute_snapshots: deque = deque(maxlen=15)
        self.last_snapshot_minute: Optional[int] = None
        
        # BTC实际价格
        self.btc_price_start: Optional[float] = None
        self.btc_price_current: Optional[float] = None
        self.last_btc_price_update: float = 0

    async def run(self) -> None:
        """Run the TUI."""
        self.running = True

        # Register callbacks
        @self.market.on_book_update
        async def handle_book(snapshot):  # pyright: ignore[reportUnusedFunction]
            for side, token_id in self.market.token_ids.items():
                if token_id == snapshot.asset_id:
                    # 记录价格
                    self.prices.record(side, snapshot.mid_price)
                    
                    # 记录市场开始价格（首次）
                    if self.start_prices[side] is None:
                        self.start_prices[side] = snapshot.mid_price
                        if self.market_start_time is None:
                            self.market_start_time = time.time()
                            # 获取开始时的BTC价格
                            self._fetch_btc_price(is_start=True)
                    
                    # 记录每分钟快照
                    self._record_minute_snapshot()
                    break

        @self.market.on_connect
        def on_connect():  # pyright: ignore[reportUnusedFunction]
            pass

        @self.market.on_disconnect
        def on_disconnect():  # pyright: ignore[reportUnusedFunction]
            pass

        # Start market manager
        if not await self.market.start():
            print(f"{Colors.RED}Failed to start market manager{Colors.RESET}")
            return

        await self.market.wait_for_data(timeout=5.0)

        try:
            # 使用 rich.Live 实现平滑刷新
            console = Console()
            with Live(console=console, refresh_per_second=2, screen=True) as live:
                while self.running:
                    # 定期更新BTC价格（每5秒）
                    if time.time() - self.last_btc_price_update > 5:
                        self._fetch_btc_price(is_start=False)
                    
                    # 渲染并更新
                    content = self._build_display()
                    live.update(Text.from_ansi(content))
                    await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            await self.market.stop()

    def _fetch_btc_price(self, is_start: bool = False) -> None:
        """获取BTC实际价格"""
        try:
            # 使用CoinGecko API获取BTC价格
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "bitcoin",
                "vs_currencies": "usd"
            }
            response = requests.get(url, params=params, timeout=3)
            if response.status_code == 200:
                data = response.json()
                price = data.get("bitcoin", {}).get("usd")
                if price:
                    if is_start:
                        self.btc_price_start = price
                        self.btc_price_current = price
                    else:
                        self.btc_price_current = price
                    self.last_btc_price_update = time.time()
        except Exception:
            # 静默失败，不影响主功能
            pass

    def _record_minute_snapshot(self) -> None:
        """记录每分钟的价格快照"""
        current_time = time.time()
        current_minute = int(current_time / 60)
        
        up_price = self.prices.get_current_price("up")
        down_price = self.prices.get_current_price("down")
        
        if up_price <= 0 or down_price <= 0:
            return
        
        # 更新上一个快照的结束BTC价格
        if len(self.minute_snapshots) > 0:
            last_snapshot = self.minute_snapshots[-1]
            last_snapshot.btc_price_end = self.btc_price_current
        
        # 避免同一分钟重复记录新快照
        if self.last_snapshot_minute == current_minute:
            return
        
        # 计算当前是15分钟周期内的第几分钟
        minute_index = len(self.minute_snapshots) + 1
        
        # 记录当前BTC价格到快照
        snapshot = PriceSnapshot(
            current_time, up_price, down_price, 
            self.btc_price_current, minute_index
        )
        self.minute_snapshots.append(snapshot)
        self.last_snapshot_minute = current_minute

    def _build_display(self) -> str:
        """构建显示内容，返回字符串."""
        lines = []

        # Header
        ws_status = f"{Colors.GREEN}Connected{Colors.RESET}" if self.market.is_connected else f"{Colors.RED}Disconnected{Colors.RESET}"
        market = self.market.current_market
        countdown = "--:--"
        if market:
            mins, secs = market.get_countdown()
            countdown = format_countdown(mins, secs)

        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
        lines.append(f"{Colors.CYAN}Orderbook TUI{Colors.RESET} | {self.coin} | {ws_status} | Ends: {countdown}")
        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")

        # BTC实际价格信息
        if self.coin == "BTC" and self.btc_price_start:
            lines.append(f"{Colors.BOLD}Bitcoin Spot Price:{Colors.RESET}")
            btc_change = self.btc_price_current - self.btc_price_start if self.btc_price_current else 0
            btc_change_pct = (btc_change / self.btc_price_start * 100) if self.btc_price_start else 0
            color = Colors.GREEN if btc_change >= 0 else Colors.RED
            lines.append(
                f"Start: ${self.btc_price_start:,.2f}  |  "
                f"Current: {color}${self.btc_price_current:,.2f}{Colors.RESET}  |  "
                f"Change: {color}{btc_change:+,.2f} ({btc_change_pct:+.2f}%){Colors.RESET}"
            )
            lines.append("")

        # Market info
        if market:
            lines.append(f"Market: {market.question}")
            lines.append(f"Slug: {market.slug}")
            lines.append("")

        # Orderbook display
        up_ob = self.market.get_orderbook("up")
        down_ob = self.market.get_orderbook("down")

        lines.append(f"{Colors.GREEN}{'UP':^39}{Colors.RESET}|{Colors.RED}{'DOWN':^39}{Colors.RESET}")
        lines.append(f"{'Bid':>9} {'Size':>9} | {'Ask':>9} {'Size':>9}|{'Bid':>9} {'Size':>9} | {'Ask':>9} {'Size':>9}")
        lines.append("-" * 80)

        # Get 10 levels for TUI
        up_bids = up_ob.bids[:10] if up_ob else []
        up_asks = up_ob.asks[:10] if up_ob else []
        down_bids = down_ob.bids[:10] if down_ob else []
        down_asks = down_ob.asks[:10] if down_ob else []

        for i in range(10):
            up_bid = f"{up_bids[i].price:>9.4f} {up_bids[i].size:>9.1f}" if i < len(up_bids) else f"{'--':>9} {'--':>9}"
            up_ask = f"{up_asks[i].price:>9.4f} {up_asks[i].size:>9.1f}" if i < len(up_asks) else f"{'--':>9} {'--':>9}"
            down_bid = f"{down_bids[i].price:>9.4f} {down_bids[i].size:>9.1f}" if i < len(down_bids) else f"{'--':>9} {'--':>9}"
            down_ask = f"{down_asks[i].price:>9.4f} {down_asks[i].size:>9.1f}" if i < len(down_asks) else f"{'--':>9} {'--':>9}"
            lines.append(f"{up_bid} | {up_ask}|{down_bid} | {down_ask}")

        lines.append("-" * 80)

        # Summary
        up_mid = up_ob.mid_price if up_ob else 0
        down_mid = down_ob.mid_price if down_ob else 0
        up_spread = self.market.get_spread("up")
        down_spread = self.market.get_spread("down")

        lines.append(
            f"Mid: {Colors.GREEN}{up_mid:.4f}{Colors.RESET}  Spread: {up_spread:.4f}           |"
            f"Mid: {Colors.RED}{down_mid:.4f}{Colors.RESET}  Spread: {down_spread:.4f}"
        )

        # Price history stats
        up_history = self.prices.get_history_count("up")
        down_history = self.prices.get_history_count("down")

        up_vol = self.prices.get_volatility("up", 60)
        down_vol = self.prices.get_volatility("down", 60)

        lines.append("")
        lines.append(f"History: UP={up_history} DOWN={down_history} | 60s Volatility: UP={up_vol:.4f} DOWN={down_vol:.4f}")

        # 显示市场概率价格和开始价格
        lines.append("")
        lines.append(f"{Colors.BOLD}Market Probability Prices:{Colors.RESET}")
        
        current_up = self.prices.get_current_price("up")
        current_down = self.prices.get_current_price("down")
        start_up = self.start_prices.get("up")
        start_down = self.start_prices.get("down")
        
        if current_up > 0 and start_up:
            change_up = current_up - start_up
            change_pct_up = (change_up / start_up * 100) if start_up > 0 else 0
            color_up = Colors.GREEN if change_up >= 0 else Colors.RED
            lines.append(
                f"UP   - Current: {color_up}{current_up:.4f}{Colors.RESET}  "
                f"Start: {start_up:.4f}  "
                f"Change: {color_up}{change_up:+.4f} ({change_pct_up:+.2f}%){Colors.RESET}"
            )
        else:
            lines.append(f"UP   - Current: --  Start: --  Change: --")
        
        if current_down > 0 and start_down:
            change_down = current_down - start_down
            change_pct_down = (change_down / start_down * 100) if start_down > 0 else 0
            color_down = Colors.GREEN if change_down >= 0 else Colors.RED
            lines.append(
                f"DOWN - Current: {color_down}{current_down:.4f}{Colors.RESET}  "
                f"Start: {start_down:.4f}  "
                f"Change: {color_down}{change_down:+.4f} ({change_pct_down:+.2f}%){Colors.RESET}"
            )
        else:
            lines.append(f"DOWN - Current: --  Start: --  Change: --")
        
        # 显示运行时间
        if self.market_start_time:
            elapsed = int(time.time() - self.market_start_time)
            mins, secs = divmod(elapsed, 60)
            lines.append(f"Running time: {mins}m {secs}s")
        
        # 显示15分钟内每分钟的价格变化数据
        if len(self.minute_snapshots) > 0:
            lines.append("")
            lines.append(f"{Colors.BOLD}15-Minute Period - Minute-by-Minute Changes:{Colors.RESET}")
            if self.coin == "BTC" and self.btc_price_start:
                lines.append(f"{'Min':<4} {'Time':<6} {'UP':>7} {'UP%':>8} {'DOWN':>7} {'DOWN%':>8} | {'BTC Start':>11} {'BTC End':>11} {'BTC Δ':>9}")
                lines.append("-" * 95)
            else:
                lines.append(f"{'Min':<4} {'Time':<6} {'UP':>7} {'UP%':>8} {'DOWN':>7} {'DOWN%':>8}")
                lines.append("-" * 50)
            
            # 显示所有已记录的分钟数据
            all_snapshots = list(self.minute_snapshots)
            for snapshot in all_snapshots:
                if start_up and start_down:
                    up_change_pct = ((snapshot.up_price - start_up) / start_up * 100)
                    down_change_pct = ((snapshot.down_price - start_down) / start_down * 100)
                    
                    time_str = datetime.fromtimestamp(snapshot.timestamp).strftime("%H:%M")
                    
                    up_color = Colors.GREEN if up_change_pct >= 0 else Colors.RED
                    down_color = Colors.GREEN if down_change_pct >= 0 else Colors.RED
                    
                    if self.coin == "BTC" and self.btc_price_start:
                        # 计算BTC在该分钟内的变化
                        btc_start = snapshot.btc_price_start or 0
                        btc_end = snapshot.btc_price_end or btc_start
                        btc_minute_change = btc_end - btc_start if btc_start > 0 else 0
                        btc_color = Colors.GREEN if btc_minute_change >= 0 else Colors.RED
                        
                        line = (
                            f"{snapshot.minute_index:<4} "
                            f"{time_str:<6} "
                            f"{snapshot.up_price:>7.4f} "
                            f"{up_color}{up_change_pct:+7.2f}%{Colors.RESET} "
                            f"{snapshot.down_price:>7.4f} "
                            f"{down_color}{down_change_pct:+7.2f}%{Colors.RESET} "
                            f"| ${btc_start:>10,.0f} ${btc_end:>10,.0f} "
                            f"{btc_color}{btc_minute_change:+8,.0f}{Colors.RESET}"
                        )
                    else:
                        line = (
                            f"{snapshot.minute_index:<4} "
                            f"{time_str:<6} "
                            f"{snapshot.up_price:>7.4f} "
                            f"{up_color}{up_change_pct:+7.2f}%{Colors.RESET} "
                            f"{snapshot.down_price:>7.4f} "
                            f"{down_color}{down_change_pct:+7.2f}%{Colors.RESET}"
                        )
                    
                    lines.append(line)
            
            # 显示剩余未记录的分钟（用占位符表示）
            remaining = 15 - len(all_snapshots)
            if remaining > 0:
                lines.append(f"{Colors.DIM}... {remaining} more minutes remaining{Colors.RESET}")
            
            lines.append(f"Progress: {len(self.minute_snapshots)}/15 minutes")

        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
        lines.append(f"{Colors.DIM}Press Ctrl+C to exit{Colors.RESET}")

        return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Orderbook TUI for Polymarket 15-minute markets"
    )
    parser.add_argument(
        "--coin",
        type=str,
        default="ETH",
        choices=["BTC", "ETH", "SOL", "XRP"],
        help="Coin to monitor (default: ETH)"
    )

    args = parser.parse_args()

    tui = OrderbookTUI(coin=args.coin)

    try:
        asyncio.run(tui.run())
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
