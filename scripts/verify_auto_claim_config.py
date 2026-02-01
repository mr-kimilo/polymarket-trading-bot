#!/usr/bin/env python3
"""
Verify Auto Claim Configuration - 验证auto_claim配置是否正确加载
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml


def verify_config():
    """验证配置"""
    print("=" * 60)
    print("Auto Claim Configuration Verification")
    print("=" * 60)
    print()
    
    # 1. 检查 config.yaml
    print("1. Checking config.yaml...")
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    if not config_path.exists():
        print("   ❌ config.yaml not found!")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    auto_claim = config.get("auto_claim", {})
    print(f"   ✓ auto_claim.enabled: {auto_claim.get('enabled')}")
    print(f"   ✓ auto_claim.min_balance: ${auto_claim.get('min_balance')}")
    print(f"   ✓ auto_claim.check_interval: {auto_claim.get('check_interval')} minutes")
    print()
    
    # 2. 检查环境变量
    print("2. Checking environment variables...")
    safe_address = os.environ.get("POLY_SAFE_ADDRESS", "")
    private_key = os.environ.get("POLY_PRIVATE_KEY", "")
    builder_key = os.environ.get("POLY_BUILDER_API_KEY", "")
    
    print(f"   {'✓' if safe_address else '❌'} POLY_SAFE_ADDRESS: {'SET' if safe_address else 'NOT SET'}")
    print(f"   {'✓' if private_key else '❌'} POLY_PRIVATE_KEY: {'SET' if private_key else 'NOT SET'}")
    print(f"   {'✓' if builder_key else '❌'} POLY_BUILDER_API_KEY: {'SET' if builder_key else 'NOT SET'}")
    print()
    
    # 3. 测试加载函数
    print("3. Testing load_auto_claim_from_config()...")
    sys.path.insert(0, str(Path(__file__).parent.parent / "apps"))
    from run_rebound import load_auto_claim_from_config
    
    auto_claim_config = load_auto_claim_from_config()
    print(f"   ✓ enabled: {auto_claim_config['enabled']}")
    print(f"   ✓ min_balance: ${auto_claim_config['min_balance']}")
    print(f"   ✓ check_interval: {auto_claim_config['check_interval']} seconds")
    print()
    
    # 4. 验证转换
    print("4. Verifying conversions...")
    expected_interval_seconds = auto_claim.get('check_interval', 5) * 60
    actual_interval_seconds = auto_claim_config['check_interval']
    
    if expected_interval_seconds == actual_interval_seconds:
        print(f"   ✓ check_interval correctly converted: {auto_claim.get('check_interval')} min -> {actual_interval_seconds} sec")
    else:
        print(f"   ❌ check_interval conversion mismatch!")
        print(f"      Expected: {expected_interval_seconds} sec")
        print(f"      Got: {actual_interval_seconds} sec")
        return False
    print()
    
    # 5. 测试 ReboundConfig
    print("5. Testing ReboundConfig initialization...")
    from strategies.rebound import ReboundConfig
    
    config = ReboundConfig(
        auto_claim_enabled=auto_claim_config["enabled"],
        auto_claim_min_balance=auto_claim_config["min_balance"],
        auto_claim_check_interval=auto_claim_config["check_interval"]
    )
    
    print(f"   ✓ ReboundConfig.auto_claim_enabled: {config.auto_claim_enabled}")
    print(f"   ✓ ReboundConfig.auto_claim_min_balance: ${config.auto_claim_min_balance}")
    print(f"   ✓ ReboundConfig.auto_claim_check_interval: {config.auto_claim_check_interval} sec")
    print()
    
    # 6. 检查依赖
    print("6. Checking dependencies...")
    try:
        from py_builder_relayer_client.client import RelayClient
        print("   ✓ py-builder-relayer-client installed")
    except ImportError:
        print("   ❌ py-builder-relayer-client NOT installed")
        print("      Run: pip install py-builder-relayer-client")
        return False
    
    try:
        from py_builder_signing_sdk.config import BuilderApiKeyCreds
        print("   ✓ py-builder-signing-sdk installed")
    except ImportError:
        print("   ❌ py-builder-signing-sdk NOT installed")
        print("      Run: pip install py-builder-signing-sdk")
        return False
    print()
    
    print("=" * 60)
    print("✓ All checks passed!")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"- Auto-claim is {'ENABLED' if auto_claim_config['enabled'] else 'DISABLED'}")
    print(f"- Will trigger when balance < ${auto_claim_config['min_balance']}")
    print(f"- Checks every {auto_claim_config['check_interval'] / 60:.0f} minutes")
    print()
    
    return True


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    success = verify_config()
    sys.exit(0 if success else 1)
