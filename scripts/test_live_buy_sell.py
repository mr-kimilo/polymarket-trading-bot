#!/usr/bin/env python3
"""
任务59: 测试LIVE买卖脚本

测试目的：验证生产环境下真实买卖订单能否成功执行
使用$2进行测试：买入后立即卖出

Usage:
    python scripts/test_live_buy_sell.py
"""

import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import create_bot_from_env
from src.gamma_client import GammaClient


async def get_price_debug_info(clob_client, token_id: str) -> dict:
    """获取价格调试信息"""
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
        info["orderbook_bids"] = bids[:5]  # Top 5
        info["orderbook_asks"] = asks[:5]
        if bids:
            info["best_bid"] = max(float(b.get("price", 0)) for b in bids)
        if asks:
            info["best_ask"] = min(float(a.get("price", 0)) for a in asks)
    except Exception as e:
        info["orderbook_error"] = str(e)
    
    return info


def calculate_safe_buy_price(price_info: dict) -> float:
    """计算安全的买入价格（略高于best_ask以确保成交）"""
    tick_size = float(price_info.get("tick_size", "0.01"))
    
    # 优先使用 best_ask
    if price_info.get("best_ask") and 0 < price_info["best_ask"] < 1:
        return min(price_info["best_ask"] + tick_size, 0.99)
    
    # 其次使用 midpoint
    if price_info.get("midpoint") and 0 < price_info["midpoint"] < 1:
        return min(price_info["midpoint"] + tick_size, 0.99)
    
    # 兜底
    return 0.50


def calculate_safe_sell_price(price_info: dict) -> float:
    """计算安全的卖出价格（略低于best_bid以确保成交）"""
    tick_size = float(price_info.get("tick_size", "0.01"))
    
    # 优先使用 best_bid
    if price_info.get("best_bid") and 0 < price_info["best_bid"] < 1:
        return max(price_info["best_bid"] - tick_size, 0.01)
    
    # 其次使用 midpoint
    if price_info.get("midpoint") and 0 < price_info["midpoint"] < 1:
        return max(price_info["midpoint"] - tick_size, 0.01)
    
    # 兜底
    return 0.01


async def main():
    print("=" * 70)
    print("任务60: LIVE买卖测试脚本 (挂单卖出)")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 测试金额 - API最小订单$1，使用$1.5确保足够
    TEST_AMOUNT_USD = 1.5
    # 卖出价格折扣（比当前价格低3%）
    SELL_DISCOUNT = 0.03
    
    # 初始化
    print("\n[1/6] 初始化 TradingBot...")
    bot = create_bot_from_env()
    
    print("\n[2/6] 获取当前15分钟市场...")
    gamma = GammaClient()
    market = gamma.get_current_15m_market("BTC")
    
    if not market:
        print("❌ 无法获取当前市场")
        return
    
    print(f"✓ 市场: {market.get('question', 'N/A')}")
    
    # 检查市场是否即将结束
    from datetime import timezone
    import datetime as dt
    end_date_str = market.get("endDate", "")
    if end_date_str:
        try:
            end_date = dt.datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            now = dt.datetime.now(timezone.utc)
            time_left = (end_date - now).total_seconds()
            print(f"  - 距离结束: {time_left:.0f} 秒 ({time_left/60:.1f} 分钟)")
            if time_left < 300:  # 5分钟
                print("⚠️  警告: 市场即将结束，价格可能很低，建议等待下一个市场")
        except Exception as e:
            print(f"  - 无法解析结束时间: {e}")
    
    # 解析token IDs - 它们存储在clobTokenIds字段中作为JSON字符串
    import json
    clob_token_ids_str = market.get("clobTokenIds", "[]")
    try:
        clob_token_ids = json.loads(clob_token_ids_str)
    except:
        clob_token_ids = []
    
    up_token_id = clob_token_ids[0] if len(clob_token_ids) > 0 else None
    down_token_id = clob_token_ids[1] if len(clob_token_ids) > 1 else None
    print(f"  - UP Token: {up_token_id[:20]}..." if up_token_id else "  - UP Token: None")
    print(f"  - DOWN Token: {down_token_id[:20]}..." if down_token_id else "  - DOWN Token: None")
    
    # 选择DOWN side进行测试（价格通常更低，更容易测试）
    side = "down"
    token_id = down_token_id
    
    if not token_id:
        print("❌ 无法获取token_id")
        return
    
    print(f"\n[3/6] 获取 {side.upper()} 价格信息...")
    price_info = await get_price_debug_info(bot.clob_client, token_id)
    
    print(f"\n  === 价格调试信息 ===")
    print(f"  Token ID: {price_info['token_id']}")
    print(f"  Tick Size: {price_info.get('tick_size', 'N/A')}")
    print(f"  Midpoint: {price_info.get('midpoint', 'N/A')} (error: {price_info.get('midpoint_error', 'none')})")
    print(f"  Last Trade: {price_info.get('last_trade', 'N/A')} (error: {price_info.get('last_trade_error', 'none')})")
    print(f"  Best Bid: {price_info.get('best_bid', 'N/A')}")
    print(f"  Best Ask: {price_info.get('best_ask', 'N/A')}")
    print(f"  Orderbook Bids (top 5): {price_info.get('orderbook_bids', [])}")
    print(f"  Orderbook Asks (top 5): {price_info.get('orderbook_asks', [])}")
    
    # 计算买入价格和数量
    # 关键: 确保 price * size 的结果只有 2 位小数（以美分为单位）
    # API 要求 maker_amount (USDC) 最多 2 位小数
    buy_price = calculate_safe_buy_price(price_info)
    
    # 为了确保 price * size 是整数美分，我们需要特殊处理
    # 最简单的方法：使用整数 size（如 2.0 shares）
    from math import floor
    raw_size = TEST_AMOUNT_USD / buy_price
    
    # 为了保证 amount 只有 2 位小数：
    # amount = size * price
    # amount * 100 必须是整数
    # size * price * 100 必须是整数
    # 
    # 方法：取整 size 到最接近的使 size*price 为整数美分的值
    # 简化：只使用 size 为 0.5 的倍数，并验证结果
    size_half = floor(raw_size * 2) / 2  # 取到 0.5 的倍数
    amount_cents = round(size_half * buy_price * 100)
    
    # 验证：amount 应该是整数美分
    actual_amount = size_half * buy_price
    if abs(round(actual_amount * 100) - actual_amount * 100) > 0.001:
        # 如果不是整数美分，使用更简单的 size
        size_half = floor(raw_size)  # 使用整数 size
        amount_cents = round(size_half * buy_price * 100)
    
    size = size_half
    
    print("\n[4/6] 准备买入...")
    print(f"  买入价格: {buy_price:.4f}")
    print(f"  买入数量: {size:.2f} shares")
    expected_cost = round(buy_price * size, 2)
    print(f"  预计花费: ${expected_cost:.2f}")
    
    # 验证 amount 精度
    amount_check = size * buy_price * 100
    print(f"  Amount验证: {amount_check:.6f} (应为整数)")
    
    # 确认
    confirm = input("\n确认执行买入? (yes/no): ")
    if confirm.lower() != "yes":
        print("已取消")
        return
    
    # 执行买入 - 使用GTC限价挂单
    print("\n  >>> 执行买入 (GTC限价挂单) <<<")
    try:
        buy_result = await bot.place_order(
            token_id=token_id,
            price=buy_price,
            size=size,
            side='BUY',
            order_type='GTC',  # Good Till Cancelled - 限价挂单
            fee_rate_bps=1000
        )
        
        if buy_result.success:
            print(f"  ✓ 买入成功! Order ID: {buy_result.order_id}")
        else:
            print(f"  ✗ 买入失败: {buy_result.message}")
            return
    except Exception as e:
        print(f"  ✗ 买入异常: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 等待一下让订单生效
    print("\n  等待2秒...")
    await asyncio.sleep(2)
    
    # 重新获取价格信息用于卖出
    print(f"\n[5/6] 重新获取价格信息准备卖出...")
    price_info_sell = await get_price_debug_info(bot.clob_client, token_id)
    
    print(f"\n  === 卖出前价格信息 ===")
    print(f"  Midpoint: {price_info_sell.get('midpoint', 'N/A')}")
    print(f"  Best Bid: {price_info_sell.get('best_bid', 'N/A')}")
    print(f"  Best Ask: {price_info_sell.get('best_ask', 'N/A')}")
    
    sell_price = calculate_safe_sell_price(price_info_sell)
    
    # 任务60: 使用挂单方式卖出，比当前价格低3%
    # 这样订单会挂在orderbook上等待成交，而不是立即成交或取消
    original_sell_price = sell_price
    sell_price = round(sell_price * (1 - SELL_DISCOUNT), 2)  # 降低3%
    sell_price = max(0.01, sell_price)  # 确保最低价格
    
    print("\n[6/6] 准备卖出...")
    print(f"  原始卖出价格: {original_sell_price:.4f}")
    print(f"  挂单卖出价格: {sell_price:.4f} (降低{SELL_DISCOUNT*100:.0f}%)")
    print(f"  卖出数量: {size:.2f} shares")
    print(f"  订单类型: GTC (Good Till Cancelled) 限价挂单")
    
    # 验证卖出价格
    if sell_price <= 0 or sell_price >= 1:
        print(f"  ❌ 卖出价格无效: {sell_price}")
        print(f"  这是导致'invalid price'错误的原因!")
        return
    
    print(f"  ✓ 卖出价格有效: 0 < {sell_price} < 1")
    
    # 执行卖出
    print("\n  >>> 执行卖出 (GTC限价挂单) <<<")
    try:
        sell_result = await bot.place_order(
            token_id=token_id,
            price=sell_price,
            size=size,
            side='SELL',
            order_type='GTC',  # Good Till Cancelled - 限价挂单
            fee_rate_bps=1000
        )
        
        if sell_result.success:
            print(f"  ✓ 卖出成功! Order ID: {sell_result.order_id}")
            pnl = (sell_price - buy_price) * size
            print(f"  PnL: ${pnl:.4f}")
        else:
            print(f"  ✗ 卖出失败: {sell_result.message}")
    except Exception as e:
        print(f"  ✗ 卖出异常: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
