#!/usr/bin/env python3
"""查询数据库订单的脚本"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# 连接数据库
conn = psycopg2.connect(
    host=os.environ.get('DATABASE_HOST', '127.0.0.1'),
    port=os.environ.get('DATABASE_PORT', 5432),
    dbname=os.environ.get('DATABASE_NAME', 'poly_market'),
    user=os.environ.get('DATABASE_USER', 'sniper_user'),
    password=os.environ.get('DATABASE_PASSWORD', 'sniper_pass_dev')
)

cursor = conn.cursor()
cursor.execute('''
    SELECT id, side, is_simulated, status, entry_price, created_at 
    FROM rebound_orders 
    ORDER BY id DESC 
    LIMIT 15
''')
rows = cursor.fetchall()

print("最近的订单:")
print("-" * 80)
print(f"{'ID':>4} | {'Side':>5} | {'Simulated':>9} | {'Status':>10} | {'Price':>8} | {'Created'}")
print("-" * 80)
for r in rows:
    print(f"{r[0]:>4} | {r[1]:>5} | {str(r[2]):>9} | {r[3]:>10} | {r[4]:>8.4f} | {r[5]}")

# 统计模拟和真实订单数量
cursor.execute('SELECT COUNT(*) FROM rebound_orders WHERE is_simulated = true')
sim_count = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM rebound_orders WHERE is_simulated = false')
live_count = cursor.fetchone()[0]

print("-" * 80)
print(f"模拟订单: {sim_count}, 真实订单: {live_count}")

cursor.close()
conn.close()
