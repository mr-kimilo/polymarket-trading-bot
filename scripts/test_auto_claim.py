#!/usr/bin/env python3
"""
测试Auto-Claim功能

检查:
1. USDC余额获取
2. 可redeem仓位获取
3. Redeem功能 (使用官方py-builder-relayer-client)
"""

import os
import sys
import asyncio
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from src.auto_claim import AutoClaimer

# 设置logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

async def main():
    safe_address = os.environ.get("POLY_SAFE_ADDRESS", "")
    private_key = os.environ.get("POLY_PRIVATE_KEY", "")
    
    # Builder credentials
    builder_key = os.environ.get("POLY_BUILDER_API_KEY", "")
    builder_secret = os.environ.get("POLY_BUILDER_API_SECRET", "")
    builder_passphrase = os.environ.get("POLY_BUILDER_API_PASSPHRASE", "")
    
    if not safe_address:
        print("Error: POLY_SAFE_ADDRESS not set")
        return
    
    print(f"Safe Address: {safe_address}")
    print(f"Private Key: {'SET' if private_key else 'NOT SET'}")
    print(f"Builder Key: {'SET' if builder_key else 'NOT SET'}")
    print(f"Builder Secret: {'SET' if builder_secret else 'NOT SET'}")
    print(f"Builder Passphrase: {'SET' if builder_passphrase else 'NOT SET'}")
    print("-" * 60)
    
    # 创建AutoClaimer
    claimer = AutoClaimer(
        safe_address=safe_address,
        private_key=private_key,
        min_balance=10.0,  # 测试用，设为10 USDC
        builder_api_key=builder_key,
        builder_api_secret=builder_secret,
        builder_api_passphrase=builder_passphrase
    )
    
    # 检查RelayClient是否初始化
    print(f"\nRelayClient initialized: {claimer.relay_client is not None}")
    
    # 1. 检查USDC余额
    print("\n1. Checking USDC balance...")
    balance = claimer.get_usdc_balance()
    print(f"   USDC Balance: ${balance:.2f}")
    
    # 2. 获取可redeem的仓位
    print("\n2. Checking redeemable positions...")
    
    # 先获取所有可redeem仓位（包括value=0的）
    all_positions = []
    try:
        import requests
        url = f"https://data-api.polymarket.com/positions"
        params = {"user": safe_address, "redeemable": "true", "sizeThreshold": 0}
        response = requests.get(url, params=params, timeout=30)
        all_positions = response.json() if response.status_code == 200 else []
    except Exception:
        pass
    
    # 只获取有价值的仓位
    positions = claimer.get_redeemable_positions(min_value=0.01)
    
    print(f"   All redeemable positions: {len(all_positions)}")
    print(f"   Positions with value > $0.01: {len(positions)}")
    
    if positions:
        print(f"   Found {len(positions)} redeemable positions:")
        total_value = 0
        for i, pos in enumerate(positions, 1):
            print(f"   {i}. {pos.title}")
            print(f"      Outcome: {pos.outcome}")
            print(f"      Size: {pos.size:.2f}")
            print(f"      Value: ${pos.current_value:.2f}")
            print(f"      NegRisk: {pos.neg_risk}")
            print(f"      ConditionID: {pos.condition_id[:20]}...")
            print()
            total_value += pos.current_value
        print(f"   Total redeemable value: ${total_value:.2f}")
    else:
        print("   No redeemable positions found")
    
    # 3. 询问是否执行redeem
    if positions and claimer.relay_client:
        print("\n3. Would you like to redeem these positions?")
        print("   Options:")
        print("   - 'batch' : Redeem all in one transaction")
        print("   - 'single': Redeem first position only")
        print("   - 'no'    : Skip redeem")
        user_input = input("   Enter choice: ").strip().lower()
        
        if user_input == 'batch':
            print("\n   Batch redeeming all positions...")
            result = await claimer.redeem_all_positions(positions)
            if result.get("success"):
                print(f"   ✓ Success! TX: {result.get('transaction_hash')}")
            else:
                print(f"   ✗ Failed: {result.get('error')}")
                
        elif user_input == 'single':
            pos = positions[0]
            print(f"\n   Redeeming: {pos.title} ({pos.outcome})")
            success = await claimer.redeem_position(pos)
            if success:
                print("   ✓ Success!")
            else:
                print("   ✗ Failed")
        else:
            print("   Skipped redeem")
        
        # 检查新余额
        if user_input in ['batch', 'single']:
            print("\n   Checking new balance...")
            new_balance = claimer.get_usdc_balance()
            print(f"   New USDC Balance: ${new_balance:.2f}")
            print(f"   Gained: ${new_balance - balance:.2f}")
    elif not claimer.relay_client:
        print("\n3. RelayClient not initialized - cannot execute redeem")
        print("   Make sure POLY_PRIVATE_KEY and Builder credentials are set")
    
    print("\n" + "=" * 60)
    print("Auto-Claim test complete!")


if __name__ == "__main__":
    asyncio.run(main())
