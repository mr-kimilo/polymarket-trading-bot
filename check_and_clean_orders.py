#!/usr/bin/env python3
"""
检查并清理未取消的挂单
Quick script to check and cancel pending orders that may be locking funds
"""
import asyncio
from dotenv import load_dotenv
from src import create_bot_from_env

async def check_and_clean_orders():
    """检查并取消所有挂单"""
    load_dotenv()
    
    print("=" * 80)
    print("检查挂单状态")
    print("=" * 80)
    print()
    
    bot = create_bot_from_env()
    
    print("1️⃣  获取所有挂单...")
    try:
        open_orders = await bot.get_open_orders()
        print(f"   找到 {len(open_orders)} 个挂单")
        print()
        
        if not open_orders:
            print("✅ 没有挂单，资金未被锁定")
            return
        
        print("⚠️  发现以下挂单:")
        for i, order in enumerate(open_orders, 1):
            order_id = order.get('id', 'N/A')
            side = order.get('side', 'N/A')
            price = order.get('price', 'N/A')
            size = order.get('originalSize', 'N/A')
            status = order.get('status', 'N/A')
            token_id = order.get('asset_id', 'N/A')
            
            print(f"   {i}. Order ID: {order_id}")
            print(f"      Side: {side}, Price: {price}, Size: {size}")
            print(f"      Status: {status}, Token: {token_id[:20]}...")
            print()
        
        # 询问是否取消
        response = input("是否取消所有挂单？(y/n): ").strip().lower()
        
        if response == 'y':
            print()
            print("2️⃣  取消所有挂单...")
            result = await bot.cancel_all_orders()
            
            if result.success:
                print("✅ 所有挂单已取消，资金已释放")
            else:
                print(f"❌ 取消失败: {result.message}")
        else:
            print("⏭️  跳过取消操作")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_and_clean_orders())
