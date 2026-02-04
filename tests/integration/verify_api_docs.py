"""
验证 API 文档的准确性 (任务66)

检查文档中的所有示例是否与实际实现匹配
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.strategy_api import create_order_schedule, cancel_order_schedule, query_order_schedules, check_should_trade
import inspect


def verify_function_signature(func, expected_params):
    """验证函数签名是否匹配文档"""
    sig = inspect.signature(func)
    actual_params = list(sig.parameters.keys())
    
    if actual_params == expected_params:
        print(f"  ✅ {func.__name__} 参数匹配: {expected_params}")
        return True
    else:
        print(f"  ❌ {func.__name__} 参数不匹配")
        print(f"     文档: {expected_params}")
        print(f"     实际: {actual_params}")
        return False


def verify_return_structure(func, sample_call, expected_keys):
    """验证返回值结构是否匹配文档"""
    try:
        result = sample_call()
        actual_keys = set(result.keys())
        expected_keys_set = set(expected_keys)
        
        if expected_keys_set.issubset(actual_keys):
            print(f"  ✅ {func.__name__} 返回值包含所有文档字段: {expected_keys}")
            return True
        else:
            missing = expected_keys_set - actual_keys
            print(f"  ❌ {func.__name__} 返回值缺少字段: {missing}")
            return False
    except Exception as e:
        print(f"  ⚠️  {func.__name__} 调用失败: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("  验证 API 文档准确性")
    print("  文档: docs/api/order-schedule-api.md")
    print("=" * 60 + "\n")
    
    all_passed = True
    
    # 1. 验证 create_order_schedule
    print("1. 验证 create_order_schedule")
    passed = verify_function_signature(
        create_order_schedule,
        ['env', 'strategy_type', 'schedule_date', 'start_time', 'end_time']
    )
    all_passed = all_passed and passed
    
    passed = verify_return_structure(
        create_order_schedule,
        lambda: create_order_schedule('sim', '1', '2026-02-05', '09:00', '17:00'),
        ['success', 'message', 'schedule_id']
    )
    all_passed = all_passed and passed
    print()
    
    # 2. 验证 cancel_order_schedule
    print("2. 验证 cancel_order_schedule")
    passed = verify_function_signature(
        cancel_order_schedule,
        ['schedule_id']
    )
    all_passed = all_passed and passed
    
    passed = verify_return_structure(
        cancel_order_schedule,
        lambda: cancel_order_schedule(999999),  # 不存在的ID
        ['success', 'message']
    )
    all_passed = all_passed and passed
    print()
    
    # 3. 验证 query_order_schedules
    print("3. 验证 query_order_schedules")
    passed = verify_function_signature(
        query_order_schedules,
        ['env', 'strategy_type', 'schedule_date', 'status']
    )
    all_passed = all_passed and passed
    
    passed = verify_return_structure(
        query_order_schedules,
        lambda: query_order_schedules(),
        ['success', 'message', 'schedules', 'count']
    )
    all_passed = all_passed and passed
    print()
    
    # 4. 验证 check_should_trade
    print("4. 验证 check_should_trade")
    passed = verify_function_signature(
        check_should_trade,
        ['env', 'strategy_type']
    )
    all_passed = all_passed and passed
    
    passed = verify_return_structure(
        check_should_trade,
        lambda: check_should_trade('sim', '1'),
        ['success', 'should_trade', 'message']
    )
    all_passed = all_passed and passed
    print()
    
    # 总结
    print("=" * 60)
    if all_passed:
        print("✅ 所有验证通过！文档与实现一致。")
    else:
        print("❌ 部分验证失败，请更新文档或代码。")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
