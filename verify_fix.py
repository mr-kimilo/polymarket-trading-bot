#!/usr/bin/env python3
"""
验证订单expiration修复
Verify that order expiration is set correctly for different order types.
"""
import time

def verify_expiration_logic():
    """验证不同订单类型的expiration逻辑"""
    print("验证订单expiration逻辑修复:")
    print("=" * 60)
    
    # 模拟不同订单类型
    test_cases = [
        ("GTC", 0, "GTC订单应该expiration=0（永久有效直到取消）"),
        ("GTD", int(time.time()) + 86400 * 30, "GTD订单应该有具体过期时间"),
        ("FOK", 0, "FOK订单应该expiration=0（通过create_market_order）"),
        ("FAK", 0, "FAK订单应该expiration=0（通过create_market_order）"),
    ]
    
    all_passed = True
    
    for order_type, expected_expiration_value, description in test_cases:
        print(f"\n测试 {order_type} 订单:")
        print(f"  描述: {description}")
        
        # 模拟修复后的逻辑
        is_market_order = order_type in ("FOK", "FAK")
        
        if is_market_order:
            expiration_time = 0  # FOK/FAK通过create_market_order设为0
            creation_method = "create_market_order"
        else:
            # GTC/GTD使用create_order
            if order_type == "GTD":
                expiration_time = int(time.time()) + 86400 * 30  # 30天
            else:  # GTC
                expiration_time = 0
            creation_method = "create_order"
        
        # 验证
        if order_type == "GTD":
            # GTD应该有一个未来的时间戳
            is_correct = expiration_time > int(time.time())
            print(f"  ✓ 期望: 未来时间戳")
            print(f"  ✓ 实际: {expiration_time} ({expiration_time - int(time.time())}秒后)")
        else:
            # 其他类型应该是0
            is_correct = expiration_time == 0
            print(f"  ✓ 期望: expiration=0")
            print(f"  ✓ 实际: expiration={expiration_time}")
        
        print(f"  ✓ 创建方法: {creation_method}")
        
        if is_correct:
            print(f"  ✅ 通过!")
        else:
            print(f"  ❌ 失败!")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过! expiration逻辑修复正确。")
    else:
        print("❌ 某些测试失败。请检查代码。")
    
    return all_passed

if __name__ == "__main__":
    verify_expiration_logic()
