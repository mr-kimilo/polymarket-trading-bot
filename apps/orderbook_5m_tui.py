#!/usr/bin/env python3
"""
Orderbook 5M TUI - Real-time Orderbook Viewer for 5-Minute Markets

A terminal-based UI for viewing real-time orderbook data
for Polymarket 5-minute Up/Down markets.

Features:
- Real-time WebSocket orderbook updates
- Dual orderbook display (Up/Down)
- Market countdown timer
- Price history tracking
- Order depth change monitoring
- JSON data export per 5-minute period

Usage:
    python apps/orderbook_5m_tui.py --coin BTC
    python apps/orderbook_5m_tui.py --coin BTC --silent
"""

import sys
import asyncio
import argparse
import logging
import time
import json
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional
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

# 5-minute market constants
PERIOD_MINUTES = 5
PERIOD_SECONDS = PERIOD_MINUTES * 60

# Maximum runtime (hours) before auto-restart
MAX_RUNTIME_HOURS = 12
# Health check interval (seconds)
HEALTH_CHECK_INTERVAL = 60
# Max no-data time (seconds)
MAX_NO_DATA_SECONDS = 300


class PriceSnapshot:
    """每分钟价格快照"""

    def __init__(
        self,
        timestamp: float,
        up_price: float,
        down_price: float,
        btc_price: Optional[float] = None,
        minute_index: int = 0,
    ) -> None:
        self.timestamp = timestamp
        self.up_price = up_price
        self.down_price = down_price
        self.btc_price_start: Optional[float] = btc_price
        self.btc_price_end: Optional[float] = btc_price
        self.minute = int(timestamp / 60)
        self.minute_index = minute_index


class DepthSnapshot:
    """订单深度快照"""

    def __init__(
        self,
        timestamp: float,
        up_bid_depth: float,
        up_ask_depth: float,
        down_bid_depth: float,
        down_ask_depth: float,
        up_bid_levels: int,
        up_ask_levels: int,
        down_bid_levels: int,
        down_ask_levels: int,
    ) -> None:
        self.timestamp = timestamp
        self.up_bid_depth = up_bid_depth
        self.up_ask_depth = up_ask_depth
        self.down_bid_depth = down_bid_depth
        self.down_ask_depth = down_ask_depth
        self.up_bid_levels = up_bid_levels
        self.up_ask_levels = up_ask_levels
        self.down_bid_levels = down_bid_levels
        self.down_ask_levels = down_ask_levels


class Orderbook5mTUI:
    """Real-time orderbook viewer for 5-minute markets with depth tracking."""

    def __init__(
        self,
        coin: str = "BTC",
        silent: bool = False,
        max_runtime_hours: float = MAX_RUNTIME_HOURS,
    ) -> None:
        """Initialize 5M TUI.

        Args:
            coin: Cryptocurrency to monitor (BTC, ETH, SOL, XRP)
            silent: If True, run in silent mode (no UI output, only save JSON files)
            max_runtime_hours: Maximum runtime in hours before auto-restart
        """
        self.coin = coin.upper()
        self.silent = silent
        self.max_runtime_hours = max_runtime_hours
        # Use interval="5m" for 5-minute market discovery
        self.market = MarketManager(
            coin=self.coin,
            interval="5m",
            market_check_interval=15.0,  # Check more often for 5-min markets
        )
        self.prices = PriceTracker()
        self.running = False

        # Timing and health
        self.start_time: float = time.time()
        self.last_data_time: float = time.time()
        self.should_restart: bool = False

        # Silent mode logging
        self.log_file: Optional[Path] = None
        if self.silent:
            log_dir = Path(__file__).parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            self.log_file = log_dir / "silent_monitor_5m.log"

        # Market start prices
        self.start_prices: Dict[str, Optional[float]] = {"up": None, "down": None}
        self.market_start_time: Optional[float] = None

        # Minute snapshots (max 5 for 5-minute period)
        self.minute_snapshots: deque = deque(maxlen=PERIOD_MINUTES)
        self.last_snapshot_minute: Optional[int] = None

        # Depth snapshots (record every 30 seconds for finer granularity)
        self.depth_snapshots: deque = deque(maxlen=20)
        self.last_depth_snapshot_time: float = 0

        # BTC spot price
        self.btc_price_start: Optional[float] = None
        self.btc_price_current: Optional[float] = None
        self.last_btc_price_update: float = 0

        # Market switch counter
        self.market_switch_count: int = 0
        self.current_market_slug: Optional[str] = None
        self.market_switching: bool = False

    def _log(self, message: str) -> None:
        """Output message to console and log file (silent mode)."""
        print(message, flush=True)
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
            except Exception:
                pass

    def _reset_for_new_market(self) -> None:
        """Reset state for new 5-minute market period."""
        self.market_switching = True

        # Save current period data
        self._save_period_data()

        # Reset state
        self.start_prices = {"up": None, "down": None}
        self.market_start_time = None
        self.minute_snapshots.clear()
        self.last_snapshot_minute = None
        self.depth_snapshots.clear()
        self.last_depth_snapshot_time = 0
        self.btc_price_start = None
        self.last_btc_price_update = 0
        self.prices = PriceTracker()
        self.market_switch_count += 1

    def _save_period_data(self) -> None:
        """Save 5-minute period data to JSON file."""
        if len(self.minute_snapshots) == 0:
            return

        files_dir = Path(__file__).parent.parent / "files" / "5m"
        files_dir.mkdir(parents=True, exist_ok=True)

        if self.market_start_time:
            file_time = datetime.fromtimestamp(self.market_start_time)
        else:
            file_time = datetime.fromtimestamp(self.minute_snapshots[0].timestamp)

        filename = file_time.strftime("%Y-%m-%d-%H-%M") + ".json"
        filepath = files_dir / filename

        start_up = self.start_prices.get("up")
        start_down = self.start_prices.get("down")

        data: Dict[str, Any] = {
            "coin": self.coin,
            "interval": "5m",
            "market_slug": self.current_market_slug,
            "period_start": file_time.isoformat(),
            "btc_price_start": self.btc_price_start,
            "btc_price_end": self.btc_price_current,
            "up_start": start_up,
            "down_start": start_down,
            "minutes": [],
            "depth_history": [],
        }

        for snapshot in self.minute_snapshots:
            up_change_pct = (
                ((snapshot.up_price - start_up) / start_up * 100) if start_up else 0
            )
            down_change_pct = (
                ((snapshot.down_price - start_down) / start_down * 100)
                if start_down
                else 0
            )
            btc_delta = (
                (snapshot.btc_price_end or 0) - (snapshot.btc_price_start or 0)
                if snapshot.btc_price_start
                else 0
            )

            data["minutes"].append({
                "minute_index": snapshot.minute_index,
                "time": datetime.fromtimestamp(snapshot.timestamp).strftime("%H:%M"),
                "timestamp": snapshot.timestamp,
                "up": snapshot.up_price,
                "up_pct": round(up_change_pct, 2),
                "down": snapshot.down_price,
                "down_pct": round(down_change_pct, 2),
                "btc_start": snapshot.btc_price_start,
                "btc_end": snapshot.btc_price_end,
                "btc_delta": round(btc_delta, 2) if btc_delta else 0,
            })

        for depth in self.depth_snapshots:
            data["depth_history"].append({
                "time": datetime.fromtimestamp(depth.timestamp).strftime("%H:%M:%S"),
                "timestamp": depth.timestamp,
                "up_bid_depth": round(depth.up_bid_depth, 1),
                "up_ask_depth": round(depth.up_ask_depth, 1),
                "down_bid_depth": round(depth.down_bid_depth, 1),
                "down_ask_depth": round(depth.down_ask_depth, 1),
                "up_bid_levels": depth.up_bid_levels,
                "up_ask_levels": depth.up_ask_levels,
                "down_bid_levels": depth.down_bid_levels,
                "down_ask_levels": depth.down_ask_levels,
            })

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _record_depth_snapshot(self) -> None:
        """Record order depth snapshot every 30 seconds."""
        current_time = time.time()
        if current_time - self.last_depth_snapshot_time < 30:
            return

        up_ob = self.market.get_orderbook("up")
        down_ob = self.market.get_orderbook("down")

        up_bid_depth = sum(level.size for level in up_ob.bids) if up_ob else 0.0
        up_ask_depth = sum(level.size for level in up_ob.asks) if up_ob else 0.0
        down_bid_depth = sum(level.size for level in down_ob.bids) if down_ob else 0.0
        down_ask_depth = sum(level.size for level in down_ob.asks) if down_ob else 0.0
        up_bid_levels = len(up_ob.bids) if up_ob else 0
        up_ask_levels = len(up_ob.asks) if up_ob else 0
        down_bid_levels = len(down_ob.bids) if down_ob else 0
        down_ask_levels = len(down_ob.asks) if down_ob else 0

        snapshot = DepthSnapshot(
            timestamp=current_time,
            up_bid_depth=up_bid_depth,
            up_ask_depth=up_ask_depth,
            down_bid_depth=down_bid_depth,
            down_ask_depth=down_ask_depth,
            up_bid_levels=up_bid_levels,
            up_ask_levels=up_ask_levels,
            down_bid_levels=down_bid_levels,
            down_ask_levels=down_ask_levels,
        )
        self.depth_snapshots.append(snapshot)
        self.last_depth_snapshot_time = current_time

    async def run(self) -> None:
        """Run the 5M TUI."""
        self.running = True

        @self.market.on_book_update
        async def handle_book(snapshot):  # pyright: ignore[reportUnusedFunction]
            for side, token_id in self.market.token_ids.items():
                if token_id == snapshot.asset_id:
                    if self.market_switching:
                        self.market_switching = False

                    self.last_data_time = time.time()
                    self.prices.record(side, snapshot.mid_price)

                    if self.start_prices[side] is None:
                        self.start_prices[side] = snapshot.mid_price
                        if self.market_start_time is None:
                            self.market_start_time = time.time()
                            self._fetch_btc_price(is_start=True)

                    self._record_minute_snapshot()
                    self._record_depth_snapshot()
                    break

        @self.market.on_connect
        def on_connect():  # pyright: ignore[reportUnusedFunction]
            pass

        @self.market.on_disconnect
        def on_disconnect():  # pyright: ignore[reportUnusedFunction]
            pass

        @self.market.on_market_change
        def on_market_change(old_slug: str, new_slug: str):  # pyright: ignore[reportUnusedFunction]
            """Reset state on market switch."""
            self._reset_for_new_market()
            self.current_market_slug = new_slug

        # Start market manager
        if not await self.market.start():
            print(f"{Colors.RED}Failed to start market manager (5m){Colors.RESET}")
            return

        await self.market.wait_for_data(timeout=5.0)

        try:
            if self.silent:
                self._log(f"[Silent Mode] Monitoring {self.coin} 5-minute market...")
                self._log("[Silent Mode] Data will be saved to files/5m/ directory")
                self._log(f"[Silent Mode] Max runtime: {self.max_runtime_hours} hours")
                self._log("[Silent Mode] Press Ctrl+C to stop")
                last_status_time = 0.0
                last_health_check = time.time()
                while self.running:
                    current_time = time.time()

                    # Auto-restart check
                    runtime_hours = (current_time - self.start_time) / 3600
                    if runtime_hours >= self.max_runtime_hours:
                        self._log(
                            f"\n[Auto-Restart] Max runtime reached ({self.max_runtime_hours}h)."
                        )
                        self.should_restart = True
                        self.running = False
                        break

                    # Health check
                    if current_time - last_health_check >= HEALTH_CHECK_INTERVAL:
                        last_health_check = current_time
                        no_data_seconds = current_time - self.last_data_time

                        if no_data_seconds > MAX_NO_DATA_SECONDS:
                            self._log(
                                f"\n[Health Check] No data for {int(no_data_seconds)}s. Restarting..."
                            )
                            self.should_restart = True
                            self.running = False
                            break

                        if not self.market.is_connected:
                            self._log("\n[Health Check] WebSocket disconnected. Restarting...")
                            self.should_restart = True
                            self.running = False
                            break

                    # BTC price update
                    if current_time - self.last_btc_price_update > 5:
                        self._fetch_btc_price(is_start=False)

                    # Depth snapshot
                    self._record_depth_snapshot()

                    # Periodic status
                    if current_time - last_status_time >= 60:
                        last_status_time = current_time
                        slug = (
                            self.market.current_market.slug
                            if self.market.current_market
                            else "N/A"
                        )
                        snapshots_count = len(self.minute_snapshots)
                        depth_count = len(self.depth_snapshots)
                        runtime_str = f"{runtime_hours:.1f}h/{self.max_runtime_hours}h"
                        self._log(
                            f"[{datetime.now().strftime('%H:%M:%S')}] {self.coin} 5m | {slug} | "
                            f"{snapshots_count}/{PERIOD_MINUTES} min | "
                            f"depth: {depth_count} | Runtime: {runtime_str}"
                        )

                    await asyncio.sleep(1.0)
            else:
                # Normal mode with rich.Live UI
                console = Console()
                with Live(console=console, refresh_per_second=2, screen=True) as live:
                    while self.running:
                        if time.time() - self.last_btc_price_update > 5:
                            self._fetch_btc_price(is_start=False)

                        self._record_depth_snapshot()
                        content = self._build_display()
                        live.update(Text.from_ansi(content))
                        await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            if self.silent and len(self.minute_snapshots) > 0:
                self._log("\n[Silent Mode] Saving final period data...")
                self._save_period_data()
            await self.market.stop()

    def _fetch_btc_price(self, is_start: bool = False) -> None:
        """Fetch BTC spot price from Binance (primary) with fallbacks.

        When is_start=True, uses Binance Kline API to get the actual
        open price of the current 5-minute candle instead of the
        current ticker price.
        """
        price: Optional[float] = None

        if is_start:
            # Use Binance Kline API to get the real open price of this 5m candle
            price = self._fetch_binance_5m_open_price()

        if not price:
            # Fallback / regular update: use ticker price
            price = self._fetch_binance_ticker_price()

        # Fallback 1: CoinGecko
        if not price:
            try:
                url = "https://api.coingecko.com/api/v3/simple/price"
                cg_params: Dict[str, str] = {"ids": "bitcoin", "vs_currencies": "usd"}
                response = requests.get(url, params=cg_params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    price = data.get("bitcoin", {}).get("usd")
            except Exception:
                pass

        # Fallback 2: CoinCap
        if not price:
            try:
                url = "https://api.coincap.io/v2/assets/bitcoin"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    price_str = data.get("data", {}).get("priceUsd")
                    if price_str:
                        price = float(price_str)
            except Exception:
                pass

        if price:
            if is_start:
                self.btc_price_start = price
                self.btc_price_current = price
            else:
                self.btc_price_current = price
            self.last_btc_price_update = time.time()

    def _fetch_binance_5m_open_price(self) -> Optional[float]:
        """Fetch the open price of the current 5-minute Binance kline.

        Uses Binance Kline API to get the actual candle open price,
        ensuring we show the exact price at the start of the 5-minute window.

        Returns:
            Open price of current 5m candle, or None on failure
        """
        try:
            from datetime import timezone as tz

            now = datetime.now(tz.utc)
            minute = (now.minute // 5) * 5
            window_start = now.replace(minute=minute, second=0, microsecond=0)
            start_ms = int(window_start.timestamp() * 1000)

            url = "https://api.binance.com/api/v3/klines"
            params: Dict[str, str] = {
                "symbol": "BTCUSDT",
                "interval": "5m",
                "startTime": str(start_ms),
                "limit": "1",
            }
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                klines = response.json()
                if klines and len(klines) > 0:
                    # kline format: [open_time, open, high, low, close, ...]
                    return float(klines[0][1])
        except Exception:
            pass
        return None

    def _fetch_binance_ticker_price(self) -> Optional[float]:
        """Fetch current BTC ticker price from Binance.

        Returns:
            Current BTCUSDT price, or None on failure
        """
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            params: Dict[str, str] = {"symbol": "BTCUSDT"}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price_str = data.get("price")
                if price_str:
                    return float(price_str)
        except Exception:
            pass
        return None

    def _record_minute_snapshot(self) -> None:
        """Record per-minute price snapshot."""
        current_time = time.time()
        current_minute = int(current_time / 60)

        up_price = self.prices.get_current_price("up")
        down_price = self.prices.get_current_price("down")

        if up_price <= 0 or down_price <= 0:
            return

        # Update previous snapshot's ending BTC price
        if len(self.minute_snapshots) > 0:
            last_snapshot = self.minute_snapshots[-1]
            last_snapshot.btc_price_end = self.btc_price_current

        # One snapshot per minute
        if self.last_snapshot_minute == current_minute:
            return

        minute_index = len(self.minute_snapshots) + 1
        snapshot = PriceSnapshot(
            current_time,
            up_price,
            down_price,
            self.btc_price_current,
            minute_index,
        )
        self.minute_snapshots.append(snapshot)
        self.last_snapshot_minute = current_minute

    def _build_display(self) -> str:
        """Build display content string for terminal."""
        lines: List[str] = []

        # Header
        ws_status = (
            f"{Colors.GREEN}Connected{Colors.RESET}"
            if self.market.is_connected
            else f"{Colors.RED}Disconnected{Colors.RESET}"
        )
        market = self.market.current_market
        countdown = "--:--"
        if market:
            mins, secs = market.get_countdown()
            countdown = format_countdown(mins, secs)

        lines.append(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        period_info = (
            f" | Period: #{self.market_switch_count + 1}"
            if self.market_switch_count > 0
            else ""
        )
        switching_info = (
            f" | {Colors.YELLOW}Switching...{Colors.RESET}"
            if self.market_switching
            else ""
        )
        lines.append(
            f"{Colors.CYAN}Orderbook 5M TUI{Colors.RESET} | {self.coin} | "
            f"{ws_status} | Ends: {countdown}{period_info}{switching_info}"
        )
        lines.append(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")

        # BTC spot price (from Binance)
        if self.coin == "BTC" and self.btc_price_start:
            lines.append(f"{Colors.BOLD}Bitcoin Spot Price (Binance):{Colors.RESET}")
            btc_change = (
                self.btc_price_current - self.btc_price_start
                if self.btc_price_current
                else 0
            )
            btc_change_pct = (
                (btc_change / self.btc_price_start * 100) if self.btc_price_start else 0
            )
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

        lines.append(
            f"{Colors.GREEN}{'UP':^39}{Colors.RESET}|{Colors.RED}{'DOWN':^39}{Colors.RESET}"
        )
        lines.append(
            f"{'Bid':>9} {'Size':>9} | {'Ask':>9} {'Size':>9}|"
            f"{'Bid':>9} {'Size':>9} | {'Ask':>9} {'Size':>9}"
        )
        lines.append("-" * 80)

        up_bids = up_ob.bids[:10] if up_ob else []
        up_asks = up_ob.asks[:10] if up_ob else []
        down_bids = down_ob.bids[:10] if down_ob else []
        down_asks = down_ob.asks[:10] if down_ob else []

        for i in range(10):
            up_bid = (
                f"{up_bids[i].price:>9.4f} {up_bids[i].size:>9.1f}"
                if i < len(up_bids)
                else f"{'--':>9} {'--':>9}"
            )
            up_ask = (
                f"{up_asks[i].price:>9.4f} {up_asks[i].size:>9.1f}"
                if i < len(up_asks)
                else f"{'--':>9} {'--':>9}"
            )
            down_bid = (
                f"{down_bids[i].price:>9.4f} {down_bids[i].size:>9.1f}"
                if i < len(down_bids)
                else f"{'--':>9} {'--':>9}"
            )
            down_ask = (
                f"{down_asks[i].price:>9.4f} {down_asks[i].size:>9.1f}"
                if i < len(down_asks)
                else f"{'--':>9} {'--':>9}"
            )
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

        # Depth summary
        lines.append("")
        lines.append(f"{Colors.BOLD}Order Depth Summary:{Colors.RESET}")
        up_bid_total = sum(level.size for level in up_bids)
        up_ask_total = sum(level.size for level in up_asks)
        down_bid_total = sum(level.size for level in down_bids)
        down_ask_total = sum(level.size for level in down_asks)
        lines.append(
            f"UP   Bid Total: {up_bid_total:>10.1f}  |  Ask Total: {up_ask_total:>10.1f}  |  "
            f"Ratio: {(up_bid_total / up_ask_total if up_ask_total > 0 else 0):.2f}"
        )
        lines.append(
            f"DOWN Bid Total: {down_bid_total:>10.1f}  |  Ask Total: {down_ask_total:>10.1f}  |  "
            f"Ratio: {(down_bid_total / down_ask_total if down_ask_total > 0 else 0):.2f}"
        )

        # Depth change history
        if len(self.depth_snapshots) >= 2:
            lines.append("")
            lines.append(f"{Colors.BOLD}Depth Change (30s intervals):{Colors.RESET}")
            lines.append(
                f"{'Time':<10} {'UP Bid':>10} {'UP Ask':>10} {'DN Bid':>10} {'DN Ask':>10} | "
                f"{'UP B/A':>7} {'DN B/A':>7}"
            )
            lines.append("-" * 75)

            recent_depths = list(self.depth_snapshots)[-8:]  # Last 8 entries (4 min)
            for depth in recent_depths:
                time_str = datetime.fromtimestamp(depth.timestamp).strftime("%H:%M:%S")
                up_ratio = (
                    depth.up_bid_depth / depth.up_ask_depth
                    if depth.up_ask_depth > 0
                    else 0
                )
                down_ratio = (
                    depth.down_bid_depth / depth.down_ask_depth
                    if depth.down_ask_depth > 0
                    else 0
                )
                lines.append(
                    f"{time_str:<10} "
                    f"{depth.up_bid_depth:>10.1f} {depth.up_ask_depth:>10.1f} "
                    f"{depth.down_bid_depth:>10.1f} {depth.down_ask_depth:>10.1f} | "
                    f"{up_ratio:>7.2f} {down_ratio:>7.2f}"
                )

        # Price history
        up_history = self.prices.get_history_count("up")
        down_history = self.prices.get_history_count("down")
        up_vol = self.prices.get_volatility("up", 60)
        down_vol = self.prices.get_volatility("down", 60)

        lines.append("")
        lines.append(
            f"History: UP={up_history} DOWN={down_history} | "
            f"60s Volatility: UP={up_vol:.4f} DOWN={down_vol:.4f}"
        )

        # Market probability prices
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
            lines.append("UP   - Current: --  Start: --  Change: --")

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
            lines.append("DOWN - Current: --  Start: --  Change: --")

        # Running time
        if self.market_start_time:
            elapsed = int(time.time() - self.market_start_time)
            mins_elapsed, secs_elapsed = divmod(elapsed, 60)
            lines.append(f"Running time: {mins_elapsed}m {secs_elapsed}s")

        # 5-minute period minute-by-minute
        if len(self.minute_snapshots) > 0:
            lines.append("")
            lines.append(
                f"{Colors.BOLD}5-Minute Period - Minute-by-Minute Changes:{Colors.RESET}"
            )
            if self.coin == "BTC" and self.btc_price_start:
                lines.append(
                    f"{'Min':<4} {'Time':<6} {'UP':>7} {'UP%':>8} {'DOWN':>7} {'DOWN%':>8} "
                    f"| {'BTC Start':>11} {'BTC End':>11} {'BTC Δ':>9}"
                )
                lines.append("-" * 95)
            else:
                lines.append(
                    f"{'Min':<4} {'Time':<6} {'UP':>7} {'UP%':>8} {'DOWN':>7} {'DOWN%':>8}"
                )
                lines.append("-" * 50)

            for snapshot in self.minute_snapshots:
                if start_up and start_down:
                    up_change_pct = (snapshot.up_price - start_up) / start_up * 100
                    down_change_pct = (snapshot.down_price - start_down) / start_down * 100
                    time_str = datetime.fromtimestamp(snapshot.timestamp).strftime("%H:%M")
                    up_color = Colors.GREEN if up_change_pct >= 0 else Colors.RED
                    down_color = Colors.GREEN if down_change_pct >= 0 else Colors.RED

                    if self.coin == "BTC" and self.btc_price_start:
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

            remaining = PERIOD_MINUTES - len(self.minute_snapshots)
            if remaining > 0:
                lines.append(
                    f"{Colors.DIM}... {remaining} more minutes remaining{Colors.RESET}"
                )

            lines.append(
                f"Progress: {len(self.minute_snapshots)}/{PERIOD_MINUTES} minutes"
            )

        lines.append(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        lines.append(f"{Colors.DIM}Press Ctrl+C to exit{Colors.RESET}")

        return "\n".join(lines)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code: 0 for normal exit, 42 for restart request
    """
    parser = argparse.ArgumentParser(
        description="Orderbook TUI for Polymarket 5-minute markets"
    )
    parser.add_argument(
        "--coin",
        type=str,
        default="BTC",
        choices=["BTC", "ETH", "SOL", "XRP"],
        help="Coin to monitor (default: BTC)",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Run in silent mode (no UI, only save JSON data files)",
    )
    parser.add_argument(
        "--max-runtime",
        type=float,
        default=MAX_RUNTIME_HOURS,
        help=f"Maximum runtime in hours before auto-restart (default: {MAX_RUNTIME_HOURS})",
    )

    args = parser.parse_args()

    tui = Orderbook5mTUI(
        coin=args.coin,
        silent=args.silent,
        max_runtime_hours=args.max_runtime,
    )

    try:
        asyncio.run(tui.run())
        if tui.should_restart:
            print("\n[Restart] Exiting with code 42 for auto-restart...")
            return 42
        return 0
    except KeyboardInterrupt:
        print("\nExiting...")
        return 0


if __name__ == "__main__":
    sys.exit(main())
