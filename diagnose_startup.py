#!/usr/bin/env python3
"""
诊断脚本：检查启动过程中的数据库阻塞问题

用于排查run_rebound_live.bat启动后在"Database table created"之后卡住的问题
"""

import sys
import os
import logging
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# 设置详细的日志输出
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)

def test_database_connection():
    """测试数据库连接"""
    print("\n" + "="*60)
    print("步骤1: 测试数据库连接")
    print("="*60)
    
    try:
        import psycopg2
        
        host = os.environ.get("DATABASE_HOST", "127.0.0.1")
        port = int(os.environ.get("DATABASE_PORT", "5432"))
        dbname = os.environ.get("DATABASE_NAME", "poly_market")
        user = os.environ.get("DATABASE_USER", "")
        password = os.environ.get("DATABASE_PASSWORD", "")
        
        print(f"连接参数: host={host}, port={port}, dbname={dbname}, user={user}")
        
        start_time = time.time()
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )
        elapsed = time.time() - start_time
        
        print(f"✓ 数据库连接成功 (耗时: {elapsed:.2f}秒)")
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False


def test_table_operations():
    """测试表操作是否卡住"""
    print("\n" + "="*60)
    print("步骤2: 测试表操作")
    print("="*60)
    
    try:
        from src.database import Database
        
        # 创建Database实例
        print("创建Database实例...")
        start_time = time.time()
        
        db = Database()
        
        elapsed = time.time() - start_time
        print(f"✓ Database实例创建完成 (耗时: {elapsed:.2f}秒)")
        
        if not db.is_connected:
            print("✗ 数据库未连接")
            return False
        
        print("✓ 数据库已连接")
        
        # 关闭连接
        db.close()
        print("✓ 数据库连接已关闭")
        
        return True
    except Exception as e:
        print(f"✗ 表操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_initialization():
    """测试策略初始化是否卡住"""
    print("\n" + "="*60)
    print("步骤3: 测试策略初始化")
    print("="*60)
    
    try:
        from strategies.rebound import ReboundStrategy, ReboundConfig
        
        # 创建模拟模式的配置
        config = ReboundConfig(
            strategy_type="3",
            coin="BTC",
            size=2.0,
            simulation_mode=True
        )
        
        print("创建ReboundStrategy实例（模拟模式）...")
        start_time = time.time()
        
        strategy = ReboundStrategy(bot=None, config=config)
        
        elapsed = time.time() - start_time
        print(f"✓ 策略实例创建完成 (耗时: {elapsed:.2f}秒)")
        
        return True
    except Exception as e:
        print(f"✗ 策略初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_database_locks():
    """检查数据库锁情况"""
    print("\n" + "="*60)
    print("步骤4: 检查数据库锁")
    print("="*60)
    
    try:
        import psycopg2
        
        host = os.environ.get("DATABASE_HOST", "127.0.0.1")
        port = int(os.environ.get("DATABASE_PORT", "5432"))
        dbname = os.environ.get("DATABASE_NAME", "poly_market")
        user = os.environ.get("DATABASE_USER", "")
        password = os.environ.get("DATABASE_PASSWORD", "")
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        
        # 查询当前锁
        query = """
        SELECT 
            locktype,
            relation::regclass as table_name,
            mode,
            granted,
            pid,
            usename,
            application_name,
            state,
            query_start,
            state_change,
            waiting
        FROM pg_locks
        LEFT JOIN pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
        WHERE relation::regclass::text IN ('rebound_orders', 'order_schedule', 'strategy3_rules')
        ORDER BY query_start;
        """
        
        with conn.cursor() as cur:
            cur.execute(query)
            locks = cur.fetchall()
            
            if locks:
                print(f"发现 {len(locks)} 个表锁:")
                for lock in locks:
                    print(f"  - 表: {lock[1]}, 模式: {lock[2]}, "
                          f"已授予: {lock[3]}, PID: {lock[4]}, "
                          f"用户: {lock[5]}, 状态: {lock[7]}")
            else:
                print("✓ 没有发现表锁")
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 检查锁失败: {e}")
        return False


def check_long_running_queries():
    """检查长时间运行的查询"""
    print("\n" + "="*60)
    print("步骤5: 检查长时间运行的查询")
    print("="*60)
    
    try:
        import psycopg2
        
        host = os.environ.get("DATABASE_HOST", "127.0.0.1")
        port = int(os.environ.get("DATABASE_PORT", "5432"))
        dbname = os.environ.get("DATABASE_NAME", "poly_market")
        user = os.environ.get("DATABASE_USER", "")
        password = os.environ.get("DATABASE_PASSWORD", "")
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        
        # 查询运行超过5秒的查询
        query = """
        SELECT 
            pid,
            usename,
            application_name,
            state,
            query_start,
            now() - query_start as duration,
            waiting,
            query
        FROM pg_stat_activity
        WHERE state != 'idle'
          AND query NOT LIKE '%pg_stat_activity%'
          AND now() - query_start > interval '5 seconds'
        ORDER BY query_start;
        """
        
        with conn.cursor() as cur:
            cur.execute(query)
            queries = cur.fetchall()
            
            if queries:
                print(f"发现 {len(queries)} 个长时间运行的查询:")
                for q in queries:
                    print(f"  - PID: {q[0]}, 用户: {q[1]}, 时长: {q[5]}")
                    print(f"    状态: {q[3]}, 等待: {q[6]}")
                    print(f"    查询: {q[7][:100]}")
            else:
                print("✓ 没有发现长时间运行的查询")
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 检查查询失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("Polymarket交易机器人 - 启动诊断脚本")
    print("="*60)
    print("目的: 诊断run_rebound_live.bat启动卡住的问题")
    print("="*60)
    
    results = {
        "数据库连接": test_database_connection(),
        "表操作": test_table_operations(),
        "策略初始化": test_strategy_initialization(),
        "数据库锁检查": check_database_locks(),
        "长查询检查": check_long_running_queries(),
    }
    
    print("\n" + "="*60)
    print("诊断结果摘要")
    print("="*60)
    
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有测试通过，启动过程应该正常")
        print("\n可能的原因:")
        print("1. 之前的进程未正常关闭，占用了数据库连接")
        print("2. 多个进程同时启动导致竞争条件")
        print("3. WebSocket连接建立缓慢")
    else:
        print("✗ 部分测试失败，请检查上述错误信息")
        print("\n建议:")
        print("1. 检查数据库是否正在运行")
        print("2. 检查.env文件中的数据库凭证")
        print("3. 尝试手动连接数据库验证权限")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
