#!/usr/bin/env python3
"""
数据库初始化脚本

使用方法:
    python scripts/init_database.py

功能:
    1. 读取 db_init.sql 文件
    2. 连接到PostgreSQL数据库
    3. 执行所有DDL语句
    4. 验证表是否创建成功
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

try:
    import psycopg2
except ImportError:
    print("❌ 错误: psycopg2未安装")
    print("请运行: pip install psycopg2-binary")
    sys.exit(1)


def load_sql_file() -> str:
    """加载 db_init.sql 文件"""
    sql_file = Path(__file__).parent.parent / "db_init.sql"
    
    if not sql_file.exists():
        print(f"❌ 错误: 找不到文件 {sql_file}")
        sys.exit(1)
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        return f.read()


def main():
    print("\n" + "="*60)
    print("Polymarket Trading Bot - 数据库初始化")
    print("="*60 + "\n")
    
    # 获取数据库连接信息
    host = os.environ.get("DATABASE_HOST", "127.0.0.1")
    port = int(os.environ.get("DATABASE_PORT", "5432"))
    dbname = os.environ.get("DATABASE_NAME", "poly_market")
    user = os.environ.get("DATABASE_USER", "")
    password = os.environ.get("DATABASE_PASSWORD", "")
    
    if not user or not password:
        print("❌ 错误: 数据库凭证未配置")
        print("请在 .env 文件中设置:")
        print("  DATABASE_USER=your_user")
        print("  DATABASE_PASSWORD=your_password")
        sys.exit(1)
    
    print(f"📋 数据库连接信息:")
    print(f"  主机: {host}:{port}")
    print(f"  数据库: {dbname}")
    print(f"  用户: {user}")
    print()
    
    # 加载SQL文件
    print("📄 加载 db_init.sql...")
    sql_content = load_sql_file()
    print(f"✓ SQL文件加载成功 ({len(sql_content)} 字符)")
    print()
    
    # 连接数据库
    print("🔌 连接数据库...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=10
        )
        conn.autocommit = True
        print("✓ 数据库连接成功")
        print()
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        sys.exit(1)
    
    # 执行SQL
    print("⚙️  执行DDL语句...")
    try:
        with conn.cursor() as cur:
            cur.execute(sql_content)
        print("✓ DDL语句执行成功")
        print()
    except Exception as e:
        print(f"❌ DDL执行失败: {e}")
        conn.close()
        sys.exit(1)
    
    # 验证表是否创建
    print("🔍 验证表创建...")
    tables_to_check = ['rebound_orders', 'order_schedule', 'strategy3_rules']
    
    try:
        with conn.cursor() as cur:
            for table_name in tables_to_check:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, (table_name,))
                exists = cur.fetchone()[0]
                
                if exists:
                    # 统计表中的记录数
                    cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                    count = cur.fetchone()[0]
                    print(f"  ✓ {table_name} (记录数: {count})")
                else:
                    print(f"  ❌ {table_name} 未创建")
        print()
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        conn.close()
        sys.exit(1)
    
    # 关闭连接
    conn.close()
    
    print("="*60)
    print("✅ 数据库初始化完成！")
    print("="*60)
    print("\n现在可以启动trading bot了:")
    print("  python apps/run_rebound.py --coin BTC")
    print("  或者 run_rebound_live.bat\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
