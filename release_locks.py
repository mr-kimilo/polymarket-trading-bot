#!/usr/bin/env python3
"""
释放所有advisory locks并终止卡住的连接
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
conn.autocommit = True

print("\n=== 查找持有advisory lock的连接 ===")
with conn.cursor() as cur:
    cur.execute("""
    SELECT pid, classid, objid, objsubid
    FROM pg_locks
    WHERE locktype = 'advisory'
    """)
    
    locks = cur.fetchall()
    if locks:
        for lock in locks:
            print(f"PID: {lock[0]}, Lock ID: {lock[1]},{lock[2]},{lock[3]}")
    else:
        print("没有advisory locks")

print("\n=== 释放lock ID 20260208 ===")
with conn.cursor() as cur:
    # 尝试释放我们的advisory lock
    cur.execute("SELECT pg_advisory_unlock_all();")
    print("✓ 释放了当前会话的所有advisory locks")

print("\n=== 查找长时间运行的连接 ===")
with conn.cursor() as cur:
    cur.execute("""
    SELECT 
        pid,
        usename,
        application_name,
        state,
        now() - backend_start as duration,
        LEFT(query, 100) as query
    FROM pg_stat_activity
    WHERE datname = %s 
      AND pid != pg_backend_pid()
      AND state != 'idle'
      AND now() - backend_start > interval '10 seconds'
    ORDER BY backend_start;
    """, (dbname,))
    
    long_running = cur.fetchall()
    if long_running:
        print(f"发现 {len(long_running)} 个长时间运行的连接:")
        for conn_info in long_running:
            print(f"\nPID: {conn_info[0]}, 用户: {conn_info[1]}, 应用: {conn_info[2]}")
            print(f"  状态: {conn_info[3]}, 时长: {conn_info[4]}")
            print(f"  查询: {conn_info[5]}")
            
        print("\n是否要终止这些连接? (y/N): ", end='', flush=True)
        answer = input().strip().lower()
        if answer == 'y':
            with conn.cursor() as cur2:
                for conn_info in long_running:
                    pid = conn_info[0]
                    try:
                        cur2.execute("SELECT pg_terminate_backend(%s);", (pid,))
                        print(f"✓ 终止了 PID {pid}")
                    except Exception as e:
                        print(f"✗ 无法终止 PID {pid}: {e}")
    else:
        print("没有长时间运行的连接")

conn.close()
print("\n完成！")
