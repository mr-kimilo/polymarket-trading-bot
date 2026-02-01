"""
为 rebound_orders 表添加 rebound_trend 字段

任务56: 添加反弹趋势记录字段到数据库
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.database import get_database


def add_rebound_trend_column():
    """添加 rebound_trend 字段到 rebound_orders 表"""
    
    print("="*60)
    print("添加 rebound_trend 字段到数据库")
    print("="*60)
    
    db = get_database()
    
    # 检查字段是否已存在
    print("\n1. 检查字段是否已存在...")
    with db._conn.cursor() as cur:
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'rebound_orders' 
            AND column_name = 'rebound_trend';
        """)
        result = cur.fetchone()
        
        if result:
            print("   ✓ rebound_trend 字段已存在，无需添加")
            return True
    
    # 添加字段
    print("\n2. 添加 rebound_trend 字段...")
    try:
        with db._conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE rebound_orders 
                ADD COLUMN rebound_trend TEXT;
            """)
        
        print("   ✓ rebound_trend 字段添加成功")
        
        # 验证
        print("\n3. 验证字段...")
        with db._conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'rebound_orders' 
                AND column_name = 'rebound_trend';
            """)
            result = cur.fetchone()
            
            if result:
                print(f"   ✓ 字段验证成功: {result[0]} ({result[1]})")
                return True
            else:
                print("   ❌ 字段验证失败")
                return False
                
    except Exception as e:
        print(f"   ❌ 添加字段失败: {e}")
        return False


if __name__ == "__main__":
    try:
        success = add_rebound_trend_column()
        
        if success:
            print("\n" + "="*60)
            print("✅ 数据库更新完成!")
            print("="*60)
            print("\n现在可以运行策略3，反弹趋势将被记录到数据库:")
            print("  python apps/run_rebound.py --coin BTC --strategy-type 3")
            sys.exit(0)
        else:
            print("\n❌ 数据库更新失败")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 脚本出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
