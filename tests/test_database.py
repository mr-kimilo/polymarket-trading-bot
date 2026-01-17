#!/usr/bin/env python3
"""
Test Database Module

验证数据库连接和CRUD操作
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Auto-load .env file
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import ReboundOrder, OrderStatus, get_database


def test_database():
    """测试数据库操作"""
    print("=" * 60)
    print("Database Module Test")
    print("=" * 60)
    
    # 检查环境变量
    print("\n1. Checking environment variables...")
    db_vars = {
        "DATABASE_HOST": os.environ.get("DATABASE_HOST"),
        "DATABASE_PORT": os.environ.get("DATABASE_PORT"),
        "DATABASE_NAME": os.environ.get("DATABASE_NAME"),
        "DATABASE_USER": os.environ.get("DATABASE_USER"),
        "DATABASE_PASSWORD": "***" if os.environ.get("DATABASE_PASSWORD") else None
    }
    for key, value in db_vars.items():
        status = "✓" if value else "✗"
        print(f"  {status} {key}: {value}")
    
    # 连接数据库
    print("\n2. Connecting to database...")
    db = get_database()
    
    if not db.is_connected:
        print("  ✗ Database not connected!")
        print("  Make sure psycopg2 is installed: pip install psycopg2-binary")
        print("  And database credentials are set in .env file")
        return False
    
    print("  ✓ Connected to database")
    
    # 创建测试订单
    print("\n3. Creating test order...")
    test_order = ReboundOrder(
        coin="BTC",
        side="up",
        segment="A",
        entry_price=0.45,
        entry_btc_price=95000.0,
        size=22.22,
        trigger_up_price=0.65,
        trigger_down_price=0.35,
        trigger_up_drop=0.15,
        btc_drop=25.0,
        period_start=datetime.now(),
        status=OrderStatus.SIMULATED.value,
        is_simulated=True,
        market_slug="test-market-slug"
    )
    
    order_id = db.create_rebound_order(test_order)
    if order_id:
        print(f"  ✓ Created order with ID: {order_id}")
    else:
        print("  ✗ Failed to create order")
        return False
    
    # 读取订单
    print("\n4. Reading order...")
    saved_order = db.get_rebound_order(order_id)
    if saved_order:
        print("  ✓ Retrieved order:")
        print(f"    - Coin: {saved_order.coin}")
        print(f"    - Side: {saved_order.side}")
        print(f"    - Entry Price: {saved_order.entry_price}")
        print(f"    - Size: {saved_order.size}")
        print(f"    - Status: {saved_order.status}")
        print(f"    - Is Simulated: {saved_order.is_simulated}")
    else:
        print("  ✗ Failed to retrieve order")
        return False
    
    # 更新订单
    print("\n5. Updating order result...")
    success = db.update_rebound_order_result(
        order_id=order_id,
        exit_price=0.55,
        exit_btc_price=95050.0,
        pnl=2.22,
        pnl_percent=22.22,
        status=OrderStatus.CLOSED.value
    )
    if success:
        print("  ✓ Order updated successfully")
    else:
        print("  ✗ Failed to update order")
        return False
    
    # 验证更新
    updated_order = db.get_rebound_order(order_id)
    if updated_order:
        print("  Updated values:")
        print(f"    - Exit Price: {updated_order.exit_price}")
        print(f"    - PnL: ${updated_order.pnl:.2f}")
        print(f"    - Status: {updated_order.status}")
    
    # 获取统计
    print("\n6. Getting order statistics...")
    stats = db.get_rebound_orders_stats(coin="BTC", is_simulated=True, days=1)
    if stats:
        print("  ✓ Statistics (BTC, simulated, today):")
        print(f"    - Total Orders: {stats.get('total_orders', 0)}")
        print(f"    - Closed Orders: {stats.get('closed_orders', 0)}")
        print(f"    - Winning Orders: {stats.get('winning_orders', 0)}")
        print(f"    - Win Rate: {stats.get('win_rate', 0):.1f}%")
        print(f"    - Total PnL: ${stats.get('total_pnl', 0):.2f}")
    else:
        print("  ✓ No statistics available (might be first run)")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
