#!/usr/bin/env python3
"""
详细诊断脚本：逐步测试数据库操作
"""

import sys
import os
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)

def test_step_by_step():
    """逐步测试每个操作"""
    import psycopg2
    
    host = os.environ.get("DATABASE_HOST", "127.0.0.1")
    port = int(os.environ.get("DATABASE_PORT", "5432"))
    dbname = os.environ.get("DATABASE_NAME", "poly_market")
    user = os.environ.get("DATABASE_USER", "")
    password = os.environ.get("DATABASE_PASSWORD", "")
    
    print("\n" + "="*60)
    print("逐步测试数据库操作")
    print("="*60)
    
    # 建立连接
    print("\n1. 建立连接...")
    conn = psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password,
        connect_timeout=5
    )
    conn.autocommit = True
    print("✓ 连接成功")
    
    # 测试advisory lock
    print("\n2. 测试advisory lock...")
    LOCK_ID = 20260208
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s);", (LOCK_ID,))
        lock_acquired = cur.fetchone()[0]
        print(f"✓ Advisory lock acquired: {lock_acquired}")
        
        if lock_acquired:
            # 释放锁
            cur.execute("SELECT pg_advisory_unlock(%s);", (LOCK_ID,))
            print("✓ Lock released")
    
    # 创建表
    print("\n3. 创建rebound_orders表...")
    start = time.time()
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rebound_orders (
            id SERIAL PRIMARY KEY,
            coin VARCHAR(10) NOT NULL,
            side VARCHAR(10) NOT NULL,
            segment VARCHAR(5) NOT NULL,
            entry_price DECIMAL(10, 6) NOT NULL,
            entry_btc_price DECIMAL(15, 2),
            size DECIMAL(15, 4) NOT NULL DEFAULT 0,
            trigger_up_price DECIMAL(10, 6),
            trigger_down_price DECIMAL(10, 6),
            trigger_up_drop DECIMAL(10, 6),
            trigger_down_drop DECIMAL(10, 6),
            btc_drop DECIMAL(15, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            period_start TIMESTAMP,
            period_end TIMESTAMP,
            exit_price DECIMAL(10, 6),
            exit_btc_price DECIMAL(15, 2),
            exit_at TIMESTAMP,
            pnl DECIMAL(15, 4),
            pnl_percent DECIMAL(10, 4),
            rebound_trend TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
            market_slug VARCHAR(255),
            token_id VARCHAR(255),
            order_id VARCHAR(255),
            strategy_type VARCHAR(5),
            env VARCHAR(10)
        );
        """)
    elapsed = time.time() - start
    print(f"✓ 表创建完成 (耗时: {elapsed:.2f}秒)")
    
    # 添加缺失的列
    print("\n4. 添加缺失的列...")
    start = time.time()
    with conn.cursor() as cur:
        print("   4.1. ALTER TABLE strategy_type...")
        cur.execute("ALTER TABLE rebound_orders ADD COLUMN IF NOT EXISTS strategy_type VARCHAR(5);")
        print("   4.2. ALTER TABLE env...")
        cur.execute("ALTER TABLE rebound_orders ADD COLUMN IF NOT EXISTS env VARCHAR(10);")
    elapsed = time.time() - start
    print(f"✓ 列添加完成 (耗时: {elapsed:.2f}秒)")
    
    # 创建索引
    print("\n5. 创建索引...")
    start = time.time()
    with conn.cursor() as cur:
        print("   5.1. 创建coin索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_coin ON rebound_orders(coin);")
        print("   5.2. 创建status索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_status ON rebound_orders(status);")
        print("   5.3. 创建created_at索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_created_at ON rebound_orders(created_at);")
        print("   5.4. 创建is_simulated索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_is_simulated ON rebound_orders(is_simulated);")
        print("   5.5. 创建strategy_type索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_strategy_type ON rebound_orders(strategy_type);")
        print("   5.6. 创建env索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_env ON rebound_orders(env);")
    elapsed = time.time() - start
    print(f"✓ 索引创建完成 (耗时: {elapsed:.2f}秒)")
    
    # 创建order_schedule表
    print("\n6. 创建order_schedule表...")
    start = time.time()
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS order_schedule (
            id SERIAL PRIMARY KEY,
            create_dt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            env VARCHAR(10) NOT NULL,
            strategy_type VARCHAR(5) NOT NULL,
            schedule_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            status INTEGER NOT NULL DEFAULT 0
        );
        """)
    elapsed = time.time() - start
    print(f"✓ order_schedule表创建完成 (耗时: {elapsed:.2f}秒)")
    
    # 创建order_schedule索引
    print("\n7. 创建order_schedule索引...")
    start = time.time()
    with conn.cursor() as cur:
        print("   7.1. 创建env索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_order_schedule_env ON order_schedule(env);")
        print("   7.2. 创建strategy_type索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_order_schedule_strategy_type ON order_schedule(strategy_type);")
        print("   7.3. 创建date索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_order_schedule_date ON order_schedule(schedule_date);")
        print("   7.4. 创建status索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_order_schedule_status ON order_schedule(status);")
    elapsed = time.time() - start
    print(f"✓ order_schedule索引创建完成 (耗时: {elapsed:.2f}秒)")
    
    # 关闭连接
    print("\n8. 关闭连接...")
    conn.close()
    print("✓ 连接已关闭")
    
    print("\n" + "="*60)
    print("✓ 所有操作完成！")
    print("="*60)


if __name__ == "__main__":
    try:
        test_step_by_step()
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
