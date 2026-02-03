"""
任务61测试脚本 - 验证策略3支持动态stage_buy配置

测试内容：
1. 验证_get_allowed_order_segments()方法正确解析stage_buy
2. 验证数据库中可以设置不同的stage_buy值
3. 验证策略3可以在A/B/C任意阶段下单
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.strategy_impl import Strategy3
from strategies.base_rebound import BaseReboundConfig
from src.database import Database


def test_parse_stage_buy():
    """测试stage_buy解析功能"""
    print("\n" + "="*60)
    print("测试1: stage_buy解析功能")
    print("="*60)
    
    # 创建假的bot和config用于测试
    class FakeBot:
        pass
    
    config = BaseReboundConfig(
        coin="BTC",
        simulation_mode=True,
        size=3.0
    )
    
    strategy = Strategy3(FakeBot(), config)
    
    # 测试不同的stage_buy配置
    test_cases = [
        ("A", ["A"]),
        ("B", ["B"]),
        ("C", ["C"]),
        ("A,B", ["A", "B"]),
        ("B,C", ["B", "C"]),
        ("A,B,C", ["A", "B", "C"]),
        ("a", ["A"]),  # 小写应该转大写
        ("A, B, C", ["A", "B", "C"]),  # 带空格应该正确解析
        ("", ["A"]),  # 空字符串应该返回默认A
    ]
    
    passed = 0
    failed = 0
    
    for stage_buy, expected in test_cases:
        # 模拟从数据库加载的参数
        strategy._dynamic_params = {"stage_buy": stage_buy}
        result = strategy._get_allowed_order_segments()
        
        if result == expected:
            print(f"✅ stage_buy='{stage_buy}' -> {result}")
            passed += 1
        else:
            print(f"❌ stage_buy='{stage_buy}' -> {result} (expected {expected})")
            failed += 1
    
    print(f"\n解析测试: {passed} 通过, {failed} 失败")
    return failed == 0


def test_database_stage_buy():
    """测试数据库stage_buy字段"""
    print("\n" + "="*60)
    print("测试2: 数据库stage_buy字段")
    print("="*60)
    
    try:
        db = Database()
        
        # 创建测试规则
        test_rules = [
            {"env": "test_a", "stage_buy": "A", "take_profit": 0.50, "stop_loss": 0.20},
            {"env": "test_b", "stage_buy": "B", "take_profit": 0.60, "stop_loss": 0.25},
            {"env": "test_c", "stage_buy": "C", "take_profit": 0.70, "stop_loss": 0.30},
            {"env": "test_ab", "stage_buy": "A,B", "take_profit": 0.80, "stop_loss": 0.20},
        ]
        
        print("\n创建测试规则...")
        created_ids = []
        for rule in test_rules:
            rule_id = db.create_strategy3_rule(**rule)
            if rule_id:
                created_ids.append(rule_id)
                print(f"✅ 创建规则 ID={rule_id}, env={rule['env']}, stage_buy={rule['stage_buy']}")
            else:
                print(f"❌ 创建规则失败: {rule}")
        
        # 测试激活和读取
        print("\n测试激活和读取...")
        for rule_id, rule in zip(created_ids, test_rules):
            # 激活规则
            success = db.activate_strategy3_rule(rule_id)
            if not success:
                print(f"❌ 激活规则 {rule_id} 失败")
                continue
            
            # 读取激活的规则
            active_rule = db.get_active_strategy3_rule(rule['env'])
            if active_rule:
                if active_rule['stage_buy'] == rule['stage_buy']:
                    print(f"✅ 规则 {rule_id}: stage_buy={active_rule['stage_buy']}, "
                          f"take_profit={active_rule['take_profit']}, "
                          f"stop_loss={active_rule['stop_loss']}")
                else:
                    print(f"❌ 规则 {rule_id}: stage_buy不匹配 "
                          f"(expected={rule['stage_buy']}, got={active_rule['stage_buy']})")
            else:
                print(f"❌ 无法读取规则 {rule_id}")
        
        print("\n✅ 数据库测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_should_enter_trade():
    """测试should_enter_trade方法在不同阶段的行为"""
    print("\n" + "="*60)
    print("测试3: should_enter_trade阶段检查")
    print("="*60)
    
    class FakeBot:
        pass
    
    class FakePrices:
        def get_current_price(self, side):
            return 0.20  # 低于30%阈值
    
    config = BaseReboundConfig(
        coin="BTC",
        simulation_mode=True,
        size=3.0
    )
    
    strategy = Strategy3(FakeBot(), config)
    strategy.prices = FakePrices()
    strategy.btc_price_start = 95000
    strategy.btc_price_current = 94980  # 小幅下跌
    
    # 模拟价格历史（用于快速下跌检测）
    import time
    from strategies.base_rebound import PriceRecord
    now = time.time()
    strategy._price_history = {
        "UP": [
            PriceRecord(now - 70, 0.35),
            PriceRecord(now - 60, 0.32),
            PriceRecord(now - 30, 0.28),
            PriceRecord(now, 0.20),
        ],
        "DOWN": [
            PriceRecord(now - 70, 0.35),
            PriceRecord(now - 60, 0.32),
            PriceRecord(now - 30, 0.28),
            PriceRecord(now, 0.20),
        ]
    }
    
    test_cases = [
        # (stage_buy配置, 当前segment, 是否应该允许)
        ("A", "A", True),
        ("A", "B", False),
        ("A", "C", False),
        ("B", "A", False),
        ("B", "B", True),
        ("B", "C", False),
        ("C", "A", False),
        ("C", "B", False),
        ("C", "C", True),
        ("A,B", "A", True),
        ("A,B", "B", True),
        ("A,B", "C", False),
        ("A,B,C", "A", True),
        ("A,B,C", "B", True),
        ("A,B,C", "C", True),
    ]
    
    passed = 0
    failed = 0
    
    for stage_buy, segment, should_allow in test_cases:
        # 重置状态
        strategy._active_positions = {}
        strategy._current_period_orders = set()
        strategy._dynamic_params = {"stage_buy": stage_buy}
        
        # 测试
        can_enter, info = strategy.should_enter_trade("UP", segment)
        
        if can_enter == should_allow:
            status = "✅"
            passed += 1
        else:
            status = "❌"
            failed += 1
        
        print(f"{status} stage_buy={stage_buy:<5} segment={segment} -> "
              f"can_enter={can_enter} (expected={should_allow})")
    
    print(f"\n阶段检查测试: {passed} 通过, {failed} 失败")
    return failed == 0


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("任务61测试: 策略3支持动态stage_buy配置")
    print("="*60)
    
    results = []
    
    # 测试1: 解析功能
    results.append(("stage_buy解析", test_parse_stage_buy()))
    
    # 测试2: 数据库
    results.append(("数据库stage_buy", test_database_stage_buy()))
    
    # 测试3: 入场检查
    results.append(("阶段入场检查", test_should_enter_trade()))
    
    # 汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    if all_passed:
        print("🎉 所有测试通过！任务61实现正确")
    else:
        print("⚠️  部分测试失败，需要检查")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
