#!/usr/bin/env python3
"""Check specific orders for task 58"""
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

# 连接数据库
conn = psycopg2.connect(
    host=os.environ.get('DATABASE_HOST', '127.0.0.1'),
    port=os.environ.get('DATABASE_PORT', 5432),
    dbname=os.environ.get('DATABASE_NAME', 'poly_market'),
    user=os.environ.get('DATABASE_USER', 'sniper_user'),
    password=os.environ.get('DATABASE_PASSWORD', 'sniper_pass_dev')
)

cursor = conn.cursor(cursor_factory=RealDictCursor)
cursor.execute('''
    SELECT * FROM rebound_orders 
    WHERE id IN (777, 778)
    ORDER BY id DESC
''')
rows = cursor.fetchall()

print("订单详情:")
print("=" * 80)

for r in rows:
    print(f"\n订单ID: {r['id']}")
    print(f"  币种: {r['coin']}")
    print(f"  方向: {r['side']}")
    print(f"  时段: {r['segment']}")
    print(f"  入场价: {r['entry_price']}")
    print(f"  出场价: {r['exit_price']}")
    print(f"  入场BTC: {r['entry_btc_price']}")
    print(f"  出场BTC: {r['exit_btc_price']}")
    print(f"  盈亏: ${r['pnl']} ({r['pnl_percent']}%)")
    print(f"  状态: {r['status']}")
    print(f"  模拟: {r['is_simulated']}")
    print(f"  周期: {r['period_start']} - {r['period_end']}")
    print(f"  创建时间: {r['created_at']}")
    print(f"  退出时间: {r['exit_at']}")
    print(f"  反弹趋势: {r['rebound_trend']}")
    print("-" * 80)

cursor.close()
conn.close()
