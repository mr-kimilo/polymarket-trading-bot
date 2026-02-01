"""
检查策略3的配置和设置情况

任务56: 验证策略3是否正确配置，并检查所有相关参数
"""

import os
import sys
import yaml
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from strategies.rebound import ReboundConfig


def load_config():
    """加载 config.yaml 配置文件"""
    config_path = parent_dir / "config.yaml"
    if not config_path.exists():
        print(f"❌ 错误: config.yaml 不存在于 {config_path}")
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def check_strategy_type(config):
    """检查策略类型配置"""
    print("\n" + "="*60)
    print("策略类型检查")
    print("="*60)
    
    strategy_type = config.get("strategy", {}).get("type", "")
    print(f"✓ strategy.type: {strategy_type}")
    
    if strategy_type == "3":
        print("✓ 策略3已启用 (Take Profit and Stop Loss)")
    elif strategy_type == "1":
        print("⚠️  当前使用策略1 (30% BTC 50 rebound in A)")
    elif strategy_type == "2":
        print("⚠️  当前使用策略2 (15% BTC 30 rebound in C)")
    else:
        print(f"❌ 未知策略类型: {strategy_type}")
    
    return strategy_type


def check_profit_and_loss_config(config):
    """检查止盈止损配置"""
    print("\n" + "="*60)
    print("止盈止损配置检查")
    print("="*60)
    
    pnl = config.get("profit_and_loss", {})
    
    enabled = pnl.get("enabled")
    take_profit_base = pnl.get("take_profit_base")
    take_profit_reduce_loss = pnl.get("take_profit_reduce_loss")
    stop_loss_stage_bc = pnl.get("stop_loss_stage_bc")
    
    print(f"✓ profit_and_loss.enabled: {enabled}")
    print(f"✓ take_profit_base: {take_profit_base} ({take_profit_base*100:.0f}%)")
    print(f"  → 订单盈利达到 {take_profit_base*100:.0f}% 时，进入止盈监控状态")
    
    print(f"✓ take_profit_reduce_loss: {take_profit_reduce_loss} ({take_profit_reduce_loss*100:.0f}%)")
    print(f"  → 从峰值回落 {take_profit_reduce_loss*100:.0f}% 时，执行止盈卖出")
    
    print(f"✓ stop_loss_stage_bc: {stop_loss_stage_bc} ({stop_loss_stage_bc*100:.0f}%)")
    print(f"  → 在B和C阶段，损失超过 {stop_loss_stage_bc*100:.0f}% 时止损")
    
    # Validate values
    if not enabled:
        print("⚠️  警告: profit_and_loss.enabled 未启用!")
    
    if take_profit_base <= 0 or take_profit_base >= 1:
        print(f"❌ 错误: take_profit_base={take_profit_base} 超出合理范围 (0, 1)")
    
    if take_profit_reduce_loss <= 0 or take_profit_reduce_loss >= 1:
        print(f"❌ 错误: take_profit_reduce_loss={take_profit_reduce_loss} 超出合理范围 (0, 1)")
    
    if stop_loss_stage_bc <= 0 or stop_loss_stage_bc >= 1:
        print(f"❌ 错误: stop_loss_stage_bc={stop_loss_stage_bc} 超出合理范围 (0, 1)")
    
    return pnl


def check_auto_claim_config(config):
    """检查自动claim配置"""
    print("\n" + "="*60)
    print("自动Claim配置检查")
    print("="*60)
    
    auto_claim = config.get("auto_claim", {})
    
    enabled = auto_claim.get("enabled", False)
    min_balance = auto_claim.get("min_balance", 10.0)
    check_interval = auto_claim.get("check_interval", 60)
    
    print(f"✓ auto_claim.enabled: {enabled}")
    print(f"✓ min_balance: ${min_balance:.2f}")
    print(f"  → 当余额低于 ${min_balance:.2f} 时自动claim")
    print(f"✓ check_interval: {check_interval} 分钟 ({check_interval*60} 秒)")
    
    if not enabled:
        print("⚠️  警告: 自动claim未启用，需要手动claim")
    
    return auto_claim


def check_direct_sell_config(config):
    """检查直接卖出配置"""
    print("\n" + "="*60)
    print("直接卖出配置检查")
    print("="*60)
    
    direct_sell = config.get("direct_sell", {})
    enabled = direct_sell.get("enabled", False)
    
    print(f"✓ direct_sell.enabled: {enabled}")
    if enabled:
        print("  → 直接卖出功能已启用，可使用 direct_sell.bat")
    else:
        print("  → 直接卖出功能未启用")
    
    return direct_sell


def check_env_variables():
    """检查环境变量"""
    print("\n" + "="*60)
    print("环境变量检查")
    print("="*60)
    
    required_vars = [
        "POLY_PRIVATE_KEY",
        "POLY_SAFE_ADDRESS",
        "DATABASE_HOST",
        "DATABASE_NAME",
        "DATABASE_USER",
        "DATABASE_PASSWORD"
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Only show first/last few chars for security
            if "KEY" in var or "PASSWORD" in var:
                display = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
            else:
                display = value
            print(f"✓ {var}: {display}")
        else:
            print(f"❌ {var}: 未设置")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  缺失的环境变量: {', '.join(missing)}")
        print("请在 .env 文件中配置这些变量")
    
    return len(missing) == 0


def simulate_rebound_config(config, strategy_type):
    """模拟创建 ReboundConfig 实例"""
    print("\n" + "="*60)
    print("ReboundConfig 实例化检查")
    print("="*60)
    
    try:
        pnl = config.get("profit_and_loss", {})
        auto_claim = config.get("auto_claim", {})
        direct_sell = config.get("direct_sell", {})
        
        # Create config instance
        rebound_config = ReboundConfig(
            coin="BTC",
            size=3.0,
            strategy_type=strategy_type,
            simulation_mode=True,  # For safety
            profit_and_loss_enabled=pnl.get("enabled", False),
            take_profit_base=pnl.get("take_profit_base", 0.8),
            take_profit_reduce_loss=pnl.get("take_profit_reduce_loss", 0.1),
            stop_loss_stage_bc=pnl.get("stop_loss_stage_bc", 0.2),
            auto_claim_enabled=auto_claim.get("enabled", True),
            auto_claim_min_balance=auto_claim.get("min_balance", 5.0),
            auto_claim_check_interval=auto_claim.get("check_interval", 60) * 60,  # minutes to seconds
            direct_sell_enabled=direct_sell.get("enabled", False)
        )
        
        print("✓ ReboundConfig 创建成功")
        print(f"  - strategy_type: {rebound_config.strategy_type}")
        print(f"  - profit_and_loss_enabled: {rebound_config.profit_and_loss_enabled}")
        print(f"  - take_profit_base: {rebound_config.take_profit_base} ({rebound_config.take_profit_base*100:.0f}%)")
        print(f"  - take_profit_reduce_loss: {rebound_config.take_profit_reduce_loss} ({rebound_config.take_profit_reduce_loss*100:.0f}%)")
        print(f"  - stop_loss_stage_bc: {rebound_config.stop_loss_stage_bc} ({rebound_config.stop_loss_stage_bc*100:.0f}%)")
        print(f"  - active_segments: {rebound_config.active_segments}")
        print(f"  - order_segments: {rebound_config.order_segments}")
        
        return True
    except Exception as e:
        print(f"❌ ReboundConfig 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_strategy3_explanation():
    """打印策略3的说明"""
    print("\n" + "="*60)
    print("策略3 工作原理")
    print("="*60)
    
    print("""
策略3 (Take Profit and Stop Loss) 是一个短期波动交易策略：

1. 下单时机:
   - 与策略1相同，在A段(15-10分钟)下单
   - 检测UP/DOWN快速下跌到30%以下
   - BTC价格下跌在$50以内

2. 止盈逻辑:
   - 当订单盈利达到 take_profit_base (如80%) 时，进入止盈监控
   - 持续追踪峰值价格 (peak price)
   - 当价格从峰值回落 take_profit_reduce_loss (如10%) 时，执行卖出
   - 例如: 入场0.20 → 涨到0.36(+80%) → 回落到0.32(-11%) → 触发止盈

3. 止损逻辑:
   - 在B段和C段(10-0分钟)，如果还没有止盈
   - 检查亏损是否超过 stop_loss_stage_bc (如20%)
   - 超过则立即止损卖出，减少损失
   - 例如: 入场0.20 → 跌到0.16(-20%) → 触发止损

4. 优势:
   - 不等到15分钟结束，根据趋势及时止盈
   - 避免盈利回吐，锁定利润
   - 在下跌趋势中及时止损，控制风险

5. 反弹趋势记录 (任务56新增):
   - 每15秒记录一次反弹百分比
   - 记录格式: "0.15, 0.25, 0.35, 0.30, 0.28, ..."
   - 用于分析反弹趋势，优化止盈参数
    """)


def main():
    print("="*60)
    print("策略3配置检查脚本")
    print("任务56: 生成脚本检查strategy=3的配置和设置情况")
    print("="*60)
    
    # Load config
    config = load_config()
    if not config:
        return
    
    # Check strategy type
    strategy_type = check_strategy_type(config)
    
    # Check P&L config
    check_profit_and_loss_config(config)
    
    # Check auto claim
    check_auto_claim_config(config)
    
    # Check direct sell
    check_direct_sell_config(config)
    
    # Check environment variables
    env_ok = check_env_variables()
    
    # Simulate ReboundConfig creation
    config_ok = simulate_rebound_config(config, strategy_type)
    
    # Print strategy explanation
    print_strategy3_explanation()
    
    # Summary
    print("\n" + "="*60)
    print("检查结果汇总")
    print("="*60)
    
    all_ok = True
    
    if strategy_type == "3":
        print("✓ 策略类型: 策略3已正确配置")
    else:
        print(f"⚠️  策略类型: 当前使用策略{strategy_type}，不是策略3")
        all_ok = False
    
    if env_ok:
        print("✓ 环境变量: 所有必需的环境变量已配置")
    else:
        print("❌ 环境变量: 部分环境变量缺失")
        all_ok = False
    
    if config_ok:
        print("✓ ReboundConfig: 配置实例化成功")
    else:
        print("❌ ReboundConfig: 配置实例化失败")
        all_ok = False
    
    if all_ok:
        print("\n✅ 所有检查通过！策略3已就绪")
    else:
        print("\n⚠️  部分检查未通过，请修复上述问题")
    
    print("\n提示:")
    print("- 模拟模式测试: python apps/run_rebound.py --coin BTC --strategy-type 3")
    print("- 真实交易: python apps/run_rebound.py --coin BTC --strategy-type 3 --live --size 3")
    print("- 批处理启动: run_rebound_live.bat (需修改为 --strategy-type 3)")


if __name__ == "__main__":
    main()
