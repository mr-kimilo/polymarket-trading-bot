#!/usr/bin/env python3
"""
任务61: 紧急卖出持仓脚本

用于卖出当前持有的shares，使用GTC限价挂单。

Usage:
    python scripts/sell_position.py --token TOKEN_ID --size SIZE --price PRICE
    python scripts/sell_position.py --token TOKEN_ID --size SIZE  # 自动获取价格
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import create_bot_from_env


async def get_sell_price(clob_client, token_id: str, discount: float = 0.03) -> float:
    """获取卖出价格（降低discount%以确保成交）"""
    try:
        # 尝试获取midpoint
        midpoint = clob_client.get_midpoint(token_id)
        if midpoint and 0 < midpoint < 1:
            sell_price = midpoint * (1 - discount)
            return max(0.01, round(sell_price, 2))
    except Exception:
        pass
    
    try:
        # 尝试获取orderbook best_bid
        ob = clob_client.get_order_book(token_id)
        bids = ob.get("bids", [])
        if bids:
            best_bid = max(float(b.get("price", 0)) for b in bids if float(b.get("price", 0)) > 0)
            if best_bid > 0:
                sell_price = best_bid * (1 - discount)
                return max(0.01, round(sell_price, 2))
    except Exception:
        pass
    
    return 0.01  # 兜底价格


async def main():
    parser = argparse.ArgumentParser(description="卖出持仓")
    parser.add_argument("--token", type=str, required=True, help="Token ID")
    parser.add_argument("--size", type=float, required=True, help="卖出数量 (shares)")
    parser.add_argument("--price", type=float, default=None, help="卖出价格 (可选)")
    parser.add_argument("--discount", type=float, default=0.03, help="价格折扣 (默认0.03即3%%)")
    parser.add_argument("--order-type", type=str, default="GTC", choices=["GTC", "FOK"], help="订单类型")
    args = parser.parse_args()

    print("=" * 70)
    print("任务61: 紧急卖出持仓脚本")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 初始化
    print("\n[1/3] 初始化 TradingBot...")
    bot = create_bot_from_env()

    token_id = args.token
    size = args.size
    
    print(f"\n[2/3] 准备卖出...")
    print(f"  Token ID: {token_id[:30]}...")
    print(f"  卖出数量: {size} shares")
    
    # 获取卖出价格
    if args.price:
        sell_price = args.price
        print(f"  卖出价格: {sell_price} (用户指定)")
    else:
        sell_price = await get_sell_price(bot.clob_client, token_id, args.discount)
        print(f"  卖出价格: {sell_price} (自动获取，折扣{args.discount*100:.0f}%)")
    
    print(f"  订单类型: {args.order_type}")
    
    # 验证价格
    if sell_price <= 0 or sell_price >= 1:
        print(f"  ❌ 无效价格: {sell_price}")
        return
    
    # 确认
    confirm = input("\n确认执行卖出? (yes/no): ")
    if confirm.lower() != "yes":
        print("已取消")
        return
    
    # 执行卖出
    print(f"\n[3/3] 执行卖出 ({args.order_type})...")
    try:
        result = await bot.place_order(
            token_id=token_id,
            price=sell_price,
            size=size,
            side='SELL',
            order_type=args.order_type,
            fee_rate_bps=1000
        )
        
        if result.success:
            print(f"  ✓ 卖出成功! Order ID: {result.order_id}")
        else:
            print(f"  ✗ 卖出失败: {result.message}")
    except Exception as e:
        print(f"  ✗ 卖出异常: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
