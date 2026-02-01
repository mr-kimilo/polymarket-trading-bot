"""
测试反弹趋势记录功能 (任务56)

验证每15秒记录反弹百分比的功能是否正常工作
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from strategies.rebound import ReboundStrategy, ReboundConfig
from src.bot import TradingBot
from src.database import get_database


def test_rebound_trend_recording():
    """测试反弹趋势记录功能"""
    
    print("="*60)
    print("反弹趋势记录功能测试 (任务56)")
    print("="*60)
    
    # 创建配置
    print("\n1. 创建策略配置...")
    config = ReboundConfig(
        coin="BTC",
        size=3.0,
        strategy_type="3",
        simulation_mode=True,  # 模拟模式
        profit_and_loss_enabled=True,
        take_profit_base=0.8,
        take_profit_reduce_loss=0.1,
        stop_loss_stage_bc=0.2
    )
    print(f"   ✓ 策略类型: {config.strategy_type}")
    print(f"   ✓ P&L enabled: {config.profit_and_loss_enabled}")
    
    # 创建Bot (模拟模式不需要真实初始化)
    print("\n2. 创建TradingBot...")
    bot = TradingBot(
        config=None,  # 模拟模式
        private_key="0x" + "0"*64,  # 假私钥
        safe_address="0x" + "0"*40  # 假地址
    )
    print("   ✓ Bot创建成功 (模拟模式)")
    
    # 创建策略
    print("\n3. 创建Rebound策略...")
    strategy = ReboundStrategy(bot=bot, config=config)
    print("   ✓ 策略创建成功")
    
    # 测试反弹趋势记录数据结构
    print("\n4. 检查反弹趋势记录数据结构...")
    assert hasattr(strategy, '_rebound_trend_records'), "缺少 _rebound_trend_records 属性"
    assert hasattr(strategy, '_last_trend_record_time'), "缺少 _last_trend_record_time 属性"
    assert hasattr(strategy, '_trend_record_interval'), "缺少 _trend_record_interval 属性"
    
    print(f"   ✓ _rebound_trend_records: {strategy._rebound_trend_records}")
    print(f"   ✓ _last_trend_record_time: {strategy._last_trend_record_time}")
    print(f"   ✓ _trend_record_interval: {strategy._trend_record_interval}秒")
    
    # 测试方法存在
    print("\n5. 检查反弹趋势记录方法...")
    assert hasattr(strategy, '_record_rebound_trend'), "缺少 _record_rebound_trend 方法"
    assert hasattr(strategy, '_get_rebound_trend_summary'), "缺少 _get_rebound_trend_summary 方法"
    print("   ✓ _record_rebound_trend 方法存在")
    print("   ✓ _get_rebound_trend_summary 方法存在")
    
    # 模拟持仓并测试记录
    print("\n6. 模拟持仓并测试趋势记录...")
    
    # 添加一个模拟持仓
    strategy._active_positions["up"] = {
        "entry_price": 0.20,
        "size": 15.0,
        "token_id": "test_token",
        "db_id": 1
    }
    
    # 模拟价格变化和记录
    test_prices = [0.22, 0.25, 0.28, 0.30, 0.32, 0.30, 0.28]
    
    for i, price in enumerate(test_prices):
        # 设置当前价格
        strategy.prices.record("up", price)
        
        # 强制设置时间以触发记录
        strategy._last_trend_record_time = time.time() - strategy._trend_record_interval - 1
        
        # 执行记录
        strategy._record_rebound_trend()
        
        print(f"   记录 #{i+1}: 价格={price:.4f}, 反弹={((price - 0.20) / 0.20):.2%}")
    
    # 检查记录结果
    print("\n7. 检查记录结果...")
    records = strategy._rebound_trend_records["up"]
    print(f"   ✓ 记录数量: {len(records)}")
    print(f"   ✓ 记录内容: {[f'{r:.2%}' for r in records]}")
    
    # 获取趋势摘要
    trend_summary = strategy._get_rebound_trend_summary("up")
    print(f"   ✓ 趋势摘要: {trend_summary}")
    
    # 验证格式
    assert len(records) == len(test_prices), f"记录数量不匹配: {len(records)} != {len(test_prices)}"
    assert trend_summary, "趋势摘要为空"
    assert "," in trend_summary, "趋势摘要格式不正确（应该是逗号分隔）"
    
    print("\n8. 测试数据库字段...")
    try:
        db = get_database()
        print("   ✓ 数据库连接成功")
        
        # 检查表结构（通过查询元数据）
        with db._conn.cursor() as cur:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rebound_orders' 
                AND column_name = 'rebound_trend';
            """)
            result = cur.fetchone()
            
            if result:
                print("   ✓ rebound_trend 字段已存在")
            else:
                print("   ⚠️  rebound_trend 字段不存在，需要更新数据库表结构")
                print("   提示: 删除旧表后重新运行程序将自动创建新表")
    except Exception as e:
        print(f"   ⚠️  数据库检查失败: {e}")
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    
    print("\n测试结果:")
    print("✓ 反弹趋势记录数据结构正常")
    print("✓ 反弹趋势记录方法存在")
    print("✓ 趋势记录功能正常工作")
    print("✓ 趋势摘要格式正确")
    
    print("\n下一步:")
    print("1. 如果 rebound_trend 字段不存在:")
    print("   - 方法1: DROP TABLE rebound_orders CASCADE; (删除旧表)")
    print("   - 方法2: ALTER TABLE rebound_orders ADD COLUMN rebound_trend TEXT;")
    print("2. 运行策略3进行实际测试:")
    print("   python apps/run_rebound.py --coin BTC --strategy-type 3")
    print("3. 查看数据库中的 rebound_trend 字段，分析反弹趋势")
    
    return True


if __name__ == "__main__":
    try:
        success = test_rebound_trend_recording()
        if success:
            print("\n✅ 所有测试通过!")
            sys.exit(0)
        else:
            print("\n❌ 测试失败")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
