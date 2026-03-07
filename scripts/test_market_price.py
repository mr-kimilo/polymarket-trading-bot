#!/usr/bin/env python3
"""
任务15: 测试市场价格买卖脚本

测试目的：验证 get_safe_buy_price (best ask) 和 get_safe_sell_price (best bid)
是否正确获取市场价格，不执行真实交易。

Usage:
    python scripts/test_market_price.py
    python scripts/test_market_price.py --coin ETH
    python scripts/test_market_price.py --live   # 执行真实$1.5买卖测试
"""

import asyncio
import sys
import os
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import create_bot_from_env
from src.gamma_client import GammaClient


async def get_price_debug_info(clob_client, token_id: str) -> dict:
    """获取完整的价格调试信息"""
    info = {
        "token_id": token_id,
        "midpoint": None,
        "last_trade": None,
        "best_bid": None,
        "best_ask": None,
        "tick_size": None,
        "orderbook_bids": [],
        "orderbook_asks": [],
    }

    try:
        info["tick_size"] = clob_client.get_tick_size(token_id)
    except Exception as e:
        info["tick_size_error"] = str(e)

    try:
        info["midpoint"] = clob_client.get_midpoint(token_id)
    except Exception as e:
        info["midpoint_error"] = str(e)

    try:
        info["last_trade"] = clob_client.get_last_trade_price(token_id)
    except Exception as e:
        info["last_trade_error"] = str(e)

    try:
        ob = clob_client.get_order_book(token_id)
        bids = ob.get("bids", [])
        asks = ob.get("asks", [])
        info["orderbook_bids"] = bids[:5]
        info["orderbook_asks"] = asks[:5]
        if bids:
            valid_bids = [float(b.get("price", 0)) for b in bids if float(b.get("price", 0)) > 0.01]
            if valid_bids:
                info["best_bid"] = max(valid_bids)
        if asks:
            valid_asks = [float(a.get("price", 0)) for a in asks if 0 < float(a.get("price", 0)) < 1]
            if valid_asks:
                info["best_ask"] = min(valid_asks)
    except Exception as e:
        info["orderbook_error"] = str(e)

    return info


async def test_prices(coin: str = "BTC") -> None:
    """测试市场价格获取（只读，不下单）"""
    print("=" * 70)
    print(f"任务15: 市场价格测试 ({coin})")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 初始化
    print("\n[1/4] 初始化 TradingBot...")
    bot = create_bot_from_env()

    print(f"\n[2/4] 获取当前15分钟 {coin} 市场...")
    gamma = GammaClient()
    market = gamma.get_current_15m_market(coin)

    if not market:
        print(f"❌ 无法获取 {coin} 当前市场")
        return

    print(f"✓ 市场: {market.get('question', 'N/A')}")

    clob_token_ids_str = market.get("clobTokenIds", "[]")
    try:
        clob_token_ids = json.loads(clob_token_ids_str)
    except json.JSONDecodeError:
        clob_token_ids = []

    up_token_id = clob_token_ids[0] if len(clob_token_ids) > 0 else None
    down_token_id = clob_token_ids[1] if len(clob_token_ids) > 1 else None

    if not up_token_id or not down_token_id:
        print("❌ 无法获取token_id")
        return

    # 使用策略的方法获取市场价格
    from strategies.rebound import ReboundStrategy, ReboundConfig

    config = ReboundConfig(
        coin=coin,
        simulation_mode=True,
        strategy_type="3",
        auto_claim_enabled=False,
    )
    strategy = ReboundStrategy(bot=bot, config=config)

    for side, token_id in [("UP", up_token_id), ("DOWN", down_token_id)]:
        print(f"\n[3/4] === {side} 价格信息 ===")
        print(f"Token: {token_id[:30]}...")

        # 获取原始价格数据
        price_info = await get_price_debug_info(bot.clob_client, token_id)
        print(f"  Tick Size:   {price_info.get('tick_size', 'N/A')}")
        print(f"  Midpoint:    {price_info.get('midpoint', 'N/A')}")
        print(f"  Last Trade:  {price_info.get('last_trade', 'N/A')}")
        print(f"  Best Bid:    {price_info.get('best_bid', 'N/A')}")
        print(f"  Best Ask:    {price_info.get('best_ask', 'N/A')}")
        print(f"  Top Bids:    {price_info.get('orderbook_bids', [])}")
        print(f"  Top Asks:    {price_info.get('orderbook_asks', [])}")

        # 使用新的市场价格方法
        print(f"\n  --- 任务15: 市场价格计算 ---")
        buy_price = await strategy.get_safe_buy_price(token_id, side.lower())
        sell_price = await strategy.get_safe_sell_price(token_id, side.lower())

        print(f"  get_safe_buy_price (best ask):   {buy_price:.4f}")
        print(f"  get_safe_sell_price (best bid):   {sell_price:.4f}")

        # 对比旧方法
        old_buy_price = (price_info.get("midpoint") or 0.50) + 0.02
        old_sell_price = (price_info.get("midpoint") or 0.50) - float(price_info.get("tick_size") or "0.01")
        print(f"\n  --- 旧方法 (对比) ---")
        print(f"  旧 BUY价格 (mid+0.02):  {old_buy_price:.4f}")
        print(f"  旧 SELL价格 (mid-tick):  {old_sell_price:.4f}")

        spread = buy_price - sell_price if buy_price > 0 and sell_price > 0 else 0
        print(f"\n  市场价格 Spread: {spread:.4f}")

    print(f"\n[4/4] 价格测试完成")
    print("=" * 70)


async def test_live_buy_sell(coin: str = "BTC") -> None:
    """执行真实买卖测试（使用市场价格）"""
    print("=" * 70)
    print(f"任务15: LIVE市场价格买卖测试 ({coin})")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("⚠️  将使用真实USDC进行交易!")
    print("=" * 70)

    TEST_AMOUNT_USD = 1.5

    print("\n[1/6] 初始化 TradingBot...")
    bot = create_bot_from_env()

    print(f"\n[2/6] 获取当前15分钟 {coin} 市场...")
    gamma = GammaClient()
    market = gamma.get_current_15m_market(coin)

    if not market:
        print(f"❌ 无法获取 {coin} 当前市场")
        return

    print(f"✓ 市场: {market.get('question', 'N/A')}")

    clob_token_ids_str = market.get("clobTokenIds", "[]")
    try:
        clob_token_ids = json.loads(clob_token_ids_str)
    except json.JSONDecodeError:
        clob_token_ids = []

    down_token_id = clob_token_ids[1] if len(clob_token_ids) > 1 else None
    if not down_token_id:
        print("❌ 无法获取DOWN token_id")
        return

    # 使用策略方法获取市场价格
    from strategies.rebound import ReboundStrategy, ReboundConfig

    config = ReboundConfig(
        coin=coin,
        simulation_mode=True,
        strategy_type="3",
        auto_claim_enabled=False,
    )
    strategy = ReboundStrategy(bot=bot, config=config)

    side = "down"
    token_id = down_token_id

    print(f"\n[3/6] 获取 DOWN 市场价格...")
    buy_price = await strategy.get_safe_buy_price(token_id, side)
    price_info = await get_price_debug_info(bot.clob_client, token_id)

    print(f"  Best Ask (market buy price): {buy_price:.4f}")
    print(f"  Best Bid: {price_info.get('best_bid', 'N/A')}")
    print(f"  Midpoint: {price_info.get('midpoint', 'N/A')}")

    from math import floor
    raw_size = TEST_AMOUNT_USD / buy_price
    size = floor(raw_size * 100) / 100  # Round down to 2 decimal

    print(f"\n[4/6] 准备买入 (市场价)...")
    print(f"  买入价格: {buy_price:.4f} (来自orderbook best ask)")
    print(f"  买入数量: {size:.2f} shares")
    print(f"  预计花费: ${buy_price * size:.2f}")

    confirm = input("\n确认执行买入? (yes/no): ")
    if confirm.lower() != "yes":
        print("已取消")
        return

    # BUY
    print("\n  >>> 执行买入 (GTC, 市场价) <<<")
    try:
        buy_result = await bot.place_order(
            token_id=token_id,
            price=buy_price,
            size=size,
            side="BUY",
            order_type="GTC",
            fee_rate_bps=1000,
        )
        if buy_result.success:
            print(f"  ✓ 买入订单提交! Order ID: {buy_result.order_id}")
        else:
            print(f"  ✗ 买入失败: {buy_result.message}")
            return
    except Exception as e:
        print(f"  ✗ 买入异常: {e}")
        return

    print("\n  等待3秒...")
    await asyncio.sleep(3)

    # SELL
    print(f"\n[5/6] 获取最新卖出价格...")
    sell_price = await strategy.get_safe_sell_price(token_id, side)
    print(f"  卖出价格: {sell_price:.4f} (来自orderbook best bid)")

    print(f"\n[6/6] 准备卖出 (市场价)...")
    print(f"  卖出价格: {sell_price:.4f}")
    print(f"  卖出数量: {size:.2f} shares")

    try:
        sell_result = await bot.place_order(
            token_id=token_id,
            price=sell_price,
            size=size,
            side="SELL",
            order_type="GTC",
            fee_rate_bps=1000,
        )
        if sell_result.success:
            print(f"  ✓ 卖出订单提交! Order ID: {sell_result.order_id}")
            pnl = (sell_price - buy_price) * size
            print(f"  PnL: ${pnl:.4f}")
        else:
            print(f"  ✗ 卖出失败: {sell_result.message}")
    except Exception as e:
        print(f"  ✗ 卖出异常: {e}")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="任务15: 测试市场价格买卖")
    parser.add_argument("--coin", type=str, default="BTC", help="币种 (默认: BTC)")
    parser.add_argument("--live", action="store_true", help="执行真实买卖测试")
    args = parser.parse_args()

    if args.live:
        asyncio.run(test_live_buy_sell(args.coin))
    else:
        asyncio.run(test_prices(args.coin))
