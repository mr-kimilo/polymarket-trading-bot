"""
测试任务57: 策略3止损扩展到B和C阶段

验证止损逻辑是否在B和C阶段都能正常触发
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from strategies.rebound import ReboundStrategy, ReboundConfig
from src.bot import TradingBot


def test_stop_loss_bc_stages():
    """测试B和C阶段的止损功能"""
    
    print("="*60)
    print("任务57测试: 策略3止损扩展到B和C阶段")
    print("="*60)
    
    # 创建策略配置
    print("\n1. 创建策略3配置...")
    config = ReboundConfig(
        coin="BTC",
        size=3.0,
        strategy_type="3",
        simulation_mode=True,
        profit_and_loss_enabled=True,
        take_profit_base=0.8,
        take_profit_reduce_loss=0.1,
        stop_loss_stage_bc=0.2  # 亏损超过20%触发止损
    )
    print(f"   ✓ 策略类型: {config.strategy_type}")
    print(f"   ✓ 止损阈值: {config.stop_loss_stage_bc:.0%}")
    
    # 创建Bot
    print("\n2. 创建TradingBot...")
    bot = TradingBot(
        config=None,
        private_key="0x" + "0"*64,
        safe_address="0x" + "0"*40
    )
    print("   ✓ Bot创建成功")
    
    # 创建策略
    print("\n3. 创建Rebound策略...")
    strategy = ReboundStrategy(bot=bot, config=config)
    print("   ✓ 策略创建成功")
    
    # 测试止损逻辑
    print("\n4. 测试止损逻辑...")
    
    # 模拟持仓
    strategy._active_positions["up"] = {
        "entry_price": 0.30,  # 入场价格 0.30
        "size": 10.0,
        "token_id": "test_token",
        "db_id": 1
    }
    
    # 设置当前市场时间（模拟不同阶段）
    strategy._market_start_time = time.time()
    
    # 测试场景
    test_scenarios = [
        {
            "stage": "A",
            "segment": "A",
            "current_price": 0.24,  # 亏损20%
            "should_trigger": False,
            "reason": "A段不触发止损"
        },
        {
            "stage": "B",
            "segment": "B",
            "current_price": 0.24,  # 亏损20%
            "should_trigger": True,
            "reason": "B段亏损20%应触发止损"
        },
        {
            "stage": "C",
            "segment": "C",
            "current_price": 0.24,  # 亏损20%
            "should_trigger": True,
            "reason": "C段亏损20%应触发止损"
        },
        {
            "stage": "B",
            "segment": "B",
            "current_price": 0.27,  # 亏损10%
            "should_trigger": False,
            "reason": "B段亏损10%不触发止损（未超过20%）"
        },
        {
            "stage": "C",
            "segment": "C",
            "current_price": 0.23,  # 亏损23.3%
            "should_trigger": True,
            "reason": "C段亏损23.3%应触发止损"
        }
    ]
    
    print("\n测试场景:")
    print("-" * 60)
    
    for i, scenario in enumerate(test_scenarios, 1):
        # 重置持仓（避免前一个测试影响）
        strategy._active_positions["up"] = {
            "entry_price": 0.30,
            "size": 10.0,
            "token_id": "test_token",
            "db_id": 1
        }
        
        # 设置当前价格
        strategy.prices.record("up", scenario["current_price"])
        
        # Mock get_current_segment 方法返回指定阶段
        original_method = strategy.get_current_segment
        strategy.get_current_segment = lambda: scenario["segment"]
        
        # 计算亏损百分比
        loss_pct = (0.30 - scenario["current_price"]) / 0.30
        
        # 执行P&L评估
        positions_before = len(strategy._active_positions)
        strategy._evaluate_positions_for_profit_and_loss()
        positions_after = len(strategy._active_positions)
        
        # 恢复原方法
        strategy.get_current_segment = original_method
        
        # 检查是否触发止损（持仓是否被平仓）
        triggered = (positions_before > positions_after)
        
        # 验证结果
        status = "✓" if triggered == scenario["should_trigger"] else "✗"
        expected = "应触发" if scenario["should_trigger"] else "不应触发"
        actual = "已触发" if triggered else "未触发"
        
        print(f"\n场景 {i}: {scenario['reason']}")
        print(f"  阶段: {scenario['segment']} (预期: {scenario['stage']})")
        print(f"  价格: {scenario['current_price']:.4f} (入场: 0.30)")
        print(f"  亏损: {loss_pct:.2%}")
        print(f"  预期: {expected}")
        print(f"  实际: {actual}")
        print(f"  结果: {status}")
        
        if triggered != scenario["should_trigger"]:
            print("  ❌ 测试失败!")
            return False
    
    print("\n" + "="*60)
    print("✅ 所有测试通过!")
    print("="*60)
    
    return True


def verify_code_changes():
    """验证代码修改"""
    print("\n5. 验证代码修改...")
    
    # 读取源代码
    rebound_file = Path(__file__).parent.parent / "strategies" / "rebound.py"
    
    with open(rebound_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # 检查关键修改点
    checks = [
        ('if segment in ["B", "C"]:', "止损检查扩展到B和C阶段"),
        ('任务57', "代码包含任务57标记"),
        ('stop_loss_stage_', "止损原因包含阶段信息"),
    ]
    
    all_ok = True
    for check_str, description in checks:
        if check_str in code:
            print(f"   ✓ {description}")
        else:
            print(f"   ✗ {description}")
            all_ok = False
    
    return all_ok


def print_summary():
    """打印任务57总结"""
    print("\n" + "="*60)
    print("任务57完成总结")
    print("="*60)
    
    print("\n修改内容:")
    print("- 修改 strategies/rebound.py 的 _evaluate_positions_for_profit_and_loss() 方法")
    print("- 将止损检查从 'if segment == \"C\"' 改为 'if segment in [\"B\", \"C\"]'")
    print("- 止损原因从 'stop_loss_stage_bc' 改为动态 f'stop_loss_stage_{segment.lower()}'")
    
    print("\n功能说明:")
    print("- B阶段(10-5分钟): 亏损 ≥ 20% 触发止损")
    print("- C阶段(5-0分钟): 亏损 ≥ 20% 触发止损")
    print("- A阶段(15-10分钟): 不触发止损，给予时间反弹")
    
    print("\n配置参数:")
    print("- stop_loss_stage_bc: 0.2 (20%)")
    print("  注: 参数名 stage_bc 表示在B和C阶段都生效")
    
    print("\n使用方法:")
    print("- 配置已自动生效，无需额外设置")
    print("- 运行策略3: python apps/run_rebound.py --coin BTC --strategy-type 3")
    print("- 真实交易: python apps/run_rebound.py --coin BTC --strategy-type 3 --live --size 3")


if __name__ == "__main__":
    try:
        # 验证代码修改
        code_ok = verify_code_changes()
        
        if not code_ok:
            print("\n❌ 代码验证失败，请检查修改")
            sys.exit(1)
        
        # 测试止损逻辑
        test_ok = test_stop_loss_bc_stages()
        
        if test_ok:
            print_summary()
            sys.exit(0)
        else:
            print("\n❌ 测试失败")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
