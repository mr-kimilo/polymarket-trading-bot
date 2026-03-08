"""查询最近的DB订单记录"""
from dotenv import load_dotenv
load_dotenv()

import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('DATABASE_HOST', '127.0.0.1'),
    port=int(os.getenv('DATABASE_PORT', 5432)),
    dbname=os.getenv('DATABASE_NAME', 'poly_market'),
    user=os.getenv('DATABASE_USER', 'sniper_user'),
    password=os.getenv('DATABASE_PASSWORD', 'sniper_pass_dev'),
)
cur = conn.cursor()

# 最近10条所有状态
cur.execute("""
    SELECT id, coin, side, entry_price, size, status, strategy_type, env, token_id, created_at
    FROM rebound_orders ORDER BY id DESC LIMIT 10
""")
rows = cur.fetchall()
print("=== 最近10条DB记录（所有状态）===")
for r in rows:
    token_short = str(r[8])[-20:] if r[8] else 'N/A'
    print(f"  ID={r[0]:4d} | {str(r[1]):4s} | {str(r[2]):4s} | entry={r[3]} | size={r[4]:.2f} | status={r[5]:8s} | strat={r[6]} | env={r[7]} | ...{token_short} | {r[9]}")

# 最近1小时内的订单
cur.execute("""
    SELECT id, coin, side, entry_price, size, status, token_id, created_at, close_price, close_at
    FROM rebound_orders WHERE created_at > NOW() - INTERVAL '1 hour' ORDER BY id DESC
""")
recent = cur.fetchall()
print(f"\n=== 最近1小时内订单 ({len(recent)} 笔) ===")
for r in recent:
    token_short = str(r[6])[-30:] if r[6] else 'N/A'
    print(f"  ID={r[0]} | {r[1]} | {r[2]} | entry={r[3]} | size={r[4]:.2f} | status={r[5]} | close={r[8]} | close_at={r[9]}")
    print(f"    token=...{token_short}")

conn.close()
