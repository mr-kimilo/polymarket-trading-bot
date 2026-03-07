"""Task 9: Check and backfill strategy_type in rebound_orders (temporary)"""
from dotenv import load_dotenv
load_dotenv()
from src.database import get_database

db = get_database()
if not db.is_connected:
    print("DB not connected")
    exit(1)

with db._conn.cursor() as cur:
    # Check before
    cur.execute("SELECT COUNT(*) FROM rebound_orders WHERE strategy_type IS NULL")
    null_before = cur.fetchone()[0]
    print(f"Orders with NULL strategy_type BEFORE backfill: {null_before}")

    if null_before > 0:
        # Backfill sim orders
        cur.execute(
            "UPDATE rebound_orders SET strategy_type = '1', env = 'sim' "
            "WHERE strategy_type IS NULL AND is_simulated = true"
        )
        sim_count = cur.rowcount

        # Backfill prod orders
        cur.execute(
            "UPDATE rebound_orders SET strategy_type = '1', env = 'prod' "
            "WHERE strategy_type IS NULL AND is_simulated = false"
        )
        prod_count = cur.rowcount

        db._conn.commit()
        print(f"Backfilled: {sim_count} sim orders, {prod_count} prod orders")

    # Verify
    cur.execute("SELECT COUNT(*) FROM rebound_orders WHERE strategy_type IS NULL")
    print(f"Orders with NULL strategy_type AFTER: {cur.fetchone()[0]}")

    # Final summary
    cur.execute(
        "SELECT env, strategy_type, COUNT(*) FROM rebound_orders "
        "GROUP BY env, strategy_type ORDER BY env, strategy_type"
    )
    rows = cur.fetchall()
    print("\n=== Final breakdown ===")
    for r in rows:
        print(f"  env={r[0]!s:<8} strategy_type={r[1]!s:<6} count={r[2]}")
