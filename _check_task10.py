"""Task 10: Check rebound_trend in rebound_orders for sim and prod (temporary)"""
from dotenv import load_dotenv
load_dotenv()
from src.database import get_database

db = get_database()
with db._conn.cursor() as cur:
    # Column exists?
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='rebound_orders' AND column_name='rebound_trend'"
    )
    col = cur.fetchone()
    print(f"Column: {col}")

    # Orders with trend data
    cur.execute("SELECT COUNT(*) FROM rebound_orders WHERE rebound_trend IS NOT NULL AND rebound_trend != ''")
    print(f"Orders WITH rebound_trend: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM rebound_orders WHERE rebound_trend IS NULL OR rebound_trend = ''")
    print(f"Orders WITHOUT rebound_trend: {cur.fetchone()[0]}")

    # By env
    cur.execute(
        "SELECT env, "
        "COUNT(*) as total, "
        "COUNT(CASE WHEN rebound_trend IS NOT NULL AND rebound_trend != '' THEN 1 END) as has_trend "
        "FROM rebound_orders GROUP BY env ORDER BY env"
    )
    print("\n=== By env ===")
    for r in cur.fetchall():
        print(f"  env={r[0]!s:<8} total={r[1]:<6} has_trend={r[2]}")

    # Latest prod orders
    cur.execute(
        "SELECT id, env, side, status, rebound_trend "
        "FROM rebound_orders WHERE env='prod' ORDER BY id DESC LIMIT 10"
    )
    print("\n=== Latest prod orders ===")
    for r in cur.fetchall():
        trend = str(r[4]) if r[4] else "None"
        trend_preview = trend[:50] + "..." if len(trend) > 50 else trend
        print(f"  id={r[0]} {r[2]} status={r[3]} trend={trend_preview}")

    # Latest sim orders
    cur.execute(
        "SELECT id, env, side, status, rebound_trend "
        "FROM rebound_orders WHERE env='sim' ORDER BY id DESC LIMIT 10"
    )
    print("\n=== Latest sim orders ===")
    for r in cur.fetchall():
        trend = str(r[4]) if r[4] else "None"
        trend_preview = trend[:50] + "..." if len(trend) > 50 else trend
        print(f"  id={r[0]} {r[2]} status={r[3]} trend={trend_preview}")
