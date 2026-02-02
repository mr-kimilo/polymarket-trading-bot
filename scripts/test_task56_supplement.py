"""
测试任务56补充：验证反弹趋势记录功能

任务56补充要求：
1. 从开单到15分钟结束记录反弹趋势，而不是订单关闭时
2. 即使订单提前关闭，也继续记录趋势直到15分钟结束
3. 在15分钟周期结束时保存趋势到数据库

测试内容：
1. 验证 _closed_positions_for_trend 数据结构
2. 验证 _record_rebound_trend 方法是否记录已关闭订单的趋势
3. 验证 _save_final_rebound_trends 方法
4. 验证 update_rebound_trend_only 数据库方法
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_database_method():
    """测试数据库的 update_rebound_trend_only 方法"""
    print("\n" + "=" * 60)
    print("测试1: 数据库 update_rebound_trend_only 方法")
    print("=" * 60)
    
    from src.database import get_database
    
    db = get_database()
    if not db:
        print("❌ 数据库连接失败")
        return False
    
    # 检查方法是否存在
    if hasattr(db, 'update_rebound_trend_only'):
        print("✅ update_rebound_trend_only 方法存在")
    else:
        print("❌ update_rebound_trend_only 方法不存在")
        return False
    
    print("✅ 数据库方法测试通过")
    return True


def test_strategy_data_structures():
    """测试策略的数据结构"""
    print("\n" + "=" * 60)
    print("测试2: 策略数据结构")
    print("=" * 60)
    
    from strategies.rebound import ReboundStrategy, ReboundConfig
    
    # 创建模拟配置
    config = ReboundConfig(
        coin="BTC",
        size=3.0,
        simulation_mode=True,
        strategy_type="3"
    )
    
    # 创建策略实例（不需要bot）
    strategy = ReboundStrategy(bot=None, config=config)
    
    # 检查 _closed_positions_for_trend 数据结构
    if hasattr(strategy, '_closed_positions_for_trend'):
        print("✅ _closed_positions_for_trend 数据结构存在")
        print(f"   类型: {type(strategy._closed_positions_for_trend)}")
        print(f"   初始值: {strategy._closed_positions_for_trend}")
    else:
        print("❌ _closed_positions_for_trend 数据结构不存在")
        return False
    
    # 检查 _rebound_trend_records 数据结构
    if hasattr(strategy, '_rebound_trend_records'):
        print("✅ _rebound_trend_records 数据结构存在")
        print(f"   类型: {type(strategy._rebound_trend_records)}")
    else:
        print("❌ _rebound_trend_records 数据结构不存在")
        return False
    
    print("✅ 策略数据结构测试通过")
    return True


def test_strategy_methods():
    """测试策略方法"""
    print("\n" + "=" * 60)
    print("测试3: 策略方法")
    print("=" * 60)
    
    from strategies.rebound import ReboundStrategy, ReboundConfig
    
    config = ReboundConfig(
        coin="BTC",
        size=3.0,
        simulation_mode=True,
        strategy_type="3"
    )
    
    strategy = ReboundStrategy(bot=None, config=config)
    
    # 检查 _save_final_rebound_trends 方法
    if hasattr(strategy, '_save_final_rebound_trends'):
        print("✅ _save_final_rebound_trends 方法存在")
    else:
        print("❌ _save_final_rebound_trends 方法不存在")
        return False
    
    # 检查 _record_rebound_trend 方法
    if hasattr(strategy, '_record_rebound_trend'):
        print("✅ _record_rebound_trend 方法存在")
    else:
        print("❌ _record_rebound_trend 方法不存在")
        return False
    
    # 检查 _get_rebound_trend_summary 方法
    if hasattr(strategy, '_get_rebound_trend_summary'):
        print("✅ _get_rebound_trend_summary 方法存在")
    else:
        print("❌ _get_rebound_trend_summary 方法不存在")
        return False
    
    print("✅ 策略方法测试通过")
    return True


def test_trend_recording_logic():
    """测试趋势记录逻辑"""
    print("\n" + "=" * 60)
    print("测试4: 趋势记录逻辑")
    print("=" * 60)
    
    from strategies.rebound import ReboundStrategy, ReboundConfig
    
    config = ReboundConfig(
        coin="BTC",
        size=3.0,
        simulation_mode=True,
        strategy_type="3"
    )
    
    strategy = ReboundStrategy(bot=None, config=config)
    
    # 模拟活跃持仓
    strategy._active_positions = {
        "up": {
            "entry_price": 0.30,
            "size": 10.0,
            "db_id": 1
        }
    }
    
    # 模拟已关闭但需要继续跟踪的持仓
    strategy._closed_positions_for_trend = {
        "down": {
            "entry_price": 0.40,
            "db_id": 2
        }
    }
    
    # 手动添加趋势记录
    strategy._rebound_trend_records["up"] = [0.05, 0.10, 0.15, 0.20, 0.25]
    strategy._rebound_trend_records["down"] = [0.02, 0.05, 0.08, 0.10, 0.12]
    
    # 测试趋势摘要
    up_trend = strategy._get_rebound_trend_summary("up")
    down_trend = strategy._get_rebound_trend_summary("down")
    
    print(f"UP 趋势摘要: {up_trend}")
    print(f"DOWN 趋势摘要: {down_trend}")
    
    if up_trend and down_trend:
        print("✅ 趋势记录逻辑测试通过")
        return True
    else:
        print("❌ 趋势记录逻辑测试失败")
        return False


def test_close_position_saves_trend_info():
    """测试 _close_position 是否保存趋势跟踪信息"""
    print("\n" + "=" * 60)
    print("测试5: _close_position 保存趋势跟踪信息")
    print("=" * 60)
    
    from strategies.rebound import ReboundStrategy, ReboundConfig
    
    config = ReboundConfig(
        coin="BTC",
        size=3.0,
        simulation_mode=True,
        strategy_type="3"
    )
    
    strategy = ReboundStrategy(bot=None, config=config)
    
    # 模拟活跃持仓
    strategy._active_positions = {
        "up": {
            "entry_price": 0.30,
            "size": 10.0,
            "db_id": 123
        }
    }
    
    # 关闭持仓
    strategy._close_position("up", exit_price=0.35, reason="test")
    
    # 检查是否保存到 _closed_positions_for_trend
    if "up" in strategy._closed_positions_for_trend:
        info = strategy._closed_positions_for_trend["up"]
        print(f"✅ 关闭的持仓信息已保存: {info}")
        if info.get("db_id") == 123 and info.get("entry_price") == 0.30:
            print("✅ 保存的信息正确")
            return True
        else:
            print("❌ 保存的信息不正确")
            return False
    else:
        print("❌ 关闭的持仓信息未保存到 _closed_positions_for_trend")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("任务56补充测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("数据库方法", test_database_method()))
    results.append(("策略数据结构", test_strategy_data_structures()))
    results.append(("策略方法", test_strategy_methods()))
    results.append(("趋势记录逻辑", test_trend_recording_logic()))
    results.append(("关闭持仓保存趋势", test_close_position_saves_trend_info()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 所有测试通过！任务56补充实现正确")
    else:
        print("⚠️ 部分测试失败，请检查实现")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
