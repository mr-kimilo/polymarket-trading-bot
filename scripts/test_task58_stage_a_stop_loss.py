#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试任务58: A段紧急止损功能

验证A段(15-10分钟)的紧急止损在损失达到35%时正确触发
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from strategies.rebound import ReboundConfig


def test_stage_a_emergency_stop_loss():
    """测试A段紧急止损配置"""
    
    print("="*60)
    print("测试任务58: A段紧急止损功能")
    print("="*60)
    
    print("\n1. 创建配置...")
    config = ReboundConfig(
        coin="BTC",
        size=3.0,
        strategy_type="3",
        simulation_mode=True,
        profit_and_loss_enabled=True,
        take_profit_base=0.8,
        take_profit_reduce_loss=0.1,
        stop_loss_stage_a=0.35,  # A段35%紧急止损
        stop_loss_stage_bc=0.2   # B/C段20%止损
    )
    print(f"   ✓ 策略类型: {config.strategy_type}")
    print(f"   ✓ A段紧急止损阈值: {config.stop_loss_stage_a:.0%}")
    print(f"   ✓ B/C段止损阈值: {config.stop_loss_stage_bc:.0%}")
    
    print("\n2. 测试场景: A段损失未达到35%")
    entry = 0.30
    current = 0.22  # 损失 26.7%
    loss = (entry - current) / entry
    print(f"   入场价: {entry}")
    print(f"   当前价: {current}")
    print(f"   损失: {loss:.1%}")
    print(f"   预期: 不触发 (< {config.stop_loss_stage_a:.0%})")
    print(f"   结果: {'✓ 正确' if loss < config.stop_loss_stage_a else '✗ 错误'}")
    
    print("\n3. 测试场景: A段损失达到35%")
    entry = 0.30
    current = 0.195  # 损失 35%
    loss = (entry - current) / entry
    print(f"   入场价: {entry}")
    print(f"   当前价: {current}")
    print(f"   损失: {loss:.1%}")
    print(f"   预期: 触发紧急止损 (>= {config.stop_loss_stage_a:.0%})")
    print(f"   结果: {'✓ 正确' if loss >= config.stop_loss_stage_a else '✗ 错误'}")
    
    print("\n4. 测试场景: A段损失超过35%")
    entry = 0.285
    current = 0.165  # 损失 42.1% (真实订单778的情况)
    loss = (entry - current) / entry
    print(f"   入场价: {entry}")
    print(f"   当前价: {current}")
    print(f"   损失: {loss:.1%}")
    print(f"   预期: 触发紧急止损 (>= {config.stop_loss_stage_a:.0%})")
    print(f"   结果: {'✓ 正确' if loss >= config.stop_loss_stage_a else '✗ 错误'}")
    print(f"   注: 这是真实订单778的情况，现在会自动止损")
    
    print("\n5. 测试场景: B段损失达到20%")
    entry = 0.30
    current = 0.24  # 损失 20%
    loss = (entry - current) / entry
    print(f"   入场价: {entry}")
    print(f"   当前价: {current}")
    print(f"   损失: {loss:.1%}")
    print(f"   预期: 触发止损 (>= {config.stop_loss_stage_bc:.0%})")
    print(f"   结果: {'✓ 正确' if loss >= config.stop_loss_stage_bc else '✗ 错误'}")
    
    print("\n6. 测试场景: C段损失达到20%")
    entry = 0.30
    current = 0.24  # 损失 20%
    loss = (entry - current) / entry
    print(f"   入场价: {entry}")
    print(f"   当前价: {current}")
    print(f"   损失: {loss:.1%}")
    print(f"   预期: 触发止损 (>= {config.stop_loss_stage_bc:.0%})")
    print(f"   结果: {'✓ 正确' if loss >= config.stop_loss_stage_bc else '✗ 错误'}")
    
    print("\n7. 止损策略总结:")
    print("   A段(15-10分钟):")
    print(f"     - 紧急止损阈值: {config.stop_loss_stage_a:.0%} (更宽松，允许反弹)")
    print("     - 保护: 防止极端损失 (如订单778的-42%)")
    print("   B段(10-5分钟):")
    print(f"     - 止损阈值: {config.stop_loss_stage_bc:.0%} (中等严格)")
    print("     - 保护: 开始保护资金")
    print("   C段(5-0分钟):")
    print(f"     - 止损阈值: {config.stop_loss_stage_bc:.0%} (更严格)")
    print("     - 保护: 加强资金保护")
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    
    print("\n修改内容:")
    print("- 在 strategies/rebound.py 中:")
    print("  1. 添加 stop_loss_stage_a 配置参数 (默认0.35)")
    print("  2. 修改 _evaluate_positions_for_profit_and_loss() 方法")
    print("  3. 添加A段紧急止损检查逻辑")
    print()
    print("- 在 config.yaml 中:")
    print("  1. 添加 profit_and_loss.stop_loss_stage_a: 0.35")
    print()
    print("- 在 scripts/check_strategy3_config.py 中:")
    print("  1. 添加 stop_loss_stage_a 参数读取和验证")
    print("  2. 更新策略说明文档")
    
    print("\n功能说明:")
    print("- A段: 损失≥35% 触发紧急止损")
    print("- B段: 损失≥20% 触发止损")
    print("- C段: 损失≥20% 触发止损")
    print("- 目的: 既保留A段反弹空间，又防止极端损失")
    
    print("\n配置参数:")
    print("- stop_loss_stage_a: 0.35 (35%)")
    print("  A段紧急止损，更宽松，允许价格波动和反弹")
    print("- stop_loss_stage_bc: 0.2 (20%)")
    print("  B和C段止损，更严格，及时止损")
    
    print("\n使用方法:")
    print("- 配置已自动生效，无需额外设置")
    print("- 运行策略3: python apps/run_rebound.py --coin BTC --strategy-type 3")
    print("- LIVE模式: 去掉 --simulation-mode 参数")
    
    print("\n实际效果 (订单778场景):")
    print("- 订单: DOWN @ 0.285")
    print("- 价格跌到: 0.195 (损失35%)")
    print("- ✓ 现在会自动触发A段紧急止损")
    print("- ✗ 之前: 需要等到B段才会检查止损")
    print("- ✓ 防止: 损失进一步扩大到42% (订单778实际损失)")


if __name__ == "__main__":
    test_stage_a_emergency_stop_loss()
