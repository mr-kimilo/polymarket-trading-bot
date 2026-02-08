#!/usr/bin/env python3
"""
检查数据库锁和阻塞的脚本
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

host = os.environ.get("DATABASE_HOST", "127.0.0.1")
port = int(os.environ.get("DATABASE_PORT", "5432"))
dbname = os.environ.get("DATABASE_NAME", "poly_market")
user = os.environ.get("DATABASE_USER", "")
password = os.environ.get("DATABASE_PASSWORD", "")

print(f"连接数据库 {dbname}@{host}:{port}...")
conn = psycopg2.connect(
    host=host, port=port, dbname=dbname, user=user, password=password
)

print("\n=== 当前活动连接 ===")
with conn.cursor() as cur:
    cur.execute("""
    SELECT 
        pid,
        usename,
        application_name,
        client_addr,
        backend_start,
        state,
        state_change,
        LEFT(query, 100) as query
    FROM pg_stat_activity
    WHERE datname = %s AND state != 'idle'
    ORDER BY backend_start;
    """, (dbname,))
    
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"\nPID: {row[0]}")
            print(f"  用户: {row[1]}")
            print(f"  应用: {row[2]}")
            print(f"  客户端: {row[3]}")
            print(f"  开始时间: {row[4]}")
            print(f"  状态: {row[5]}")
            print(f"  状态变更: {row[6]}")
            print(f"  查询: {row[7]}")
    else:
        print("没有活动连接")

print("\n\n=== 当前锁 ===")
with conn.cursor() as cur:
    cur.execute("""
    SELECT 
        l.locktype,
        l.relation::regclass as table_name,
        l.mode,
        l.granted,
        a.pid,
        a.usename,
        a.application_name,
        a.backend_start,
        LEFT(a.query, 100) as query
    FROM pg_locks l
    LEFT JOIN pg_stat_activity a ON l.pid = a.pid
    WHERE a.datname = %s OR a.datname IS NULL
    ORDER BY a.backend_start NULLS LAST;
    """, (dbname,))
    
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"\nLock类型: {row[0]}, 表: {row[1]}, 模式: {row[2]}, 已授予: {row[3]}")
            if row[4]:
                print(f"  PID: {row[4]}, 用户: {row[5]}, 应用: {row[6]}")
                print(f"  开始时间: {row[7]}")
                print(f"  查询: {row[8]}")
    else:
        print("没有锁")

print("\n\n=== 阻塞情况 ===")
with conn.cursor() as cur:
    cur.execute("""
    SELECT 
        blocked_locks.pid AS blocked_pid,
        blocked_activity.usename AS blocked_user,
        blocking_locks.pid AS blocking_pid,
        blocking_activity.usename AS blocking_user,
        blocked_activity.query AS blocked_statement,
        blocking_activity.query AS blocking_statement
    FROM pg_catalog.pg_locks blocked_locks
    JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
    JOIN pg_catalog.pg_locks blocking_locks 
        ON blocking_locks.locktype = blocked_locks.locktype
        AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
        AND blocking_locks.pid != blocked_locks.pid
    JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
    WHERE NOT blocked_locks.granted;
    """)
    
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"\n被阻塞PID: {row[0]} (用户: {row[1]})")
            print(f"阻塞者PID: {row[2]} (用户: {row[3]})")
            print(f"被阻塞语句: {row[4]}")
            print(f"阻塞语句: {row[5]}")
    else:
        print("没有阻塞")

conn.close()
print("\n完成！")
