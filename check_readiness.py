#!/usr/bin/env python3
"""
项目完备性检查脚本
检查所有启动准备项是否完成

Usage:
    python check_readiness.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("Polymarket Trading Bot - 启动准备检查")
print("=" * 70)
print()

# 存储检查结果
results = []

# ============================================================================
# 1. ✅ 安装 Python 依赖
# ============================================================================
print("[检查 1/5] Python 依赖安装")
print("-" * 70)

missing_deps = []
core_deps = [
    ('web3', 'web3'),
    ('eth_account', 'eth-account'),
    ('cryptography', 'cryptography'),
    ('yaml', 'pyyaml'),
    ('requests', 'requests'),
    ('websockets', 'websockets'),
    ('pytest', 'pytest'),
    ('dotenv', 'python-dotenv'),
]

for module_name, package_name in core_deps:
    try:
        __import__(module_name)
        print(f"  ✓ {package_name}")
    except ImportError:
        print(f"  ✗ {package_name} - 未安装")
        missing_deps.append(package_name)

if missing_deps:
    print(f"\n❌ 缺少依赖: {', '.join(missing_deps)}")
    print(f"   运行: python -m pip install {' '.join(missing_deps)}")
    results.append(("Python依赖", False, f"缺少: {', '.join(missing_deps)}"))
else:
    print("\n✅ 所有核心依赖已安装")
    results.append(("Python依赖", True, "所有依赖已安装"))

print()

# ============================================================================
# 2. ✅ 获取 Polymarket 钱包凭证（私钥 + Safe 地址）
# ============================================================================
print("[检查 2/5] Polymarket 钱包凭证")
print("-" * 70)

import os
from dotenv import load_dotenv
load_dotenv()

# 检查环境变量
env_private_key = os.environ.get("POLY_PRIVATE_KEY")
env_safe_address = os.environ.get("POLY_SAFE_ADDRESS")

# 检查配置文件
config_safe_address = None
config_has_builder = False
if Path("config.yaml").exists():
    try:
        from src.config import Config
        config = Config.load("config.yaml")
        config_safe_address = config.safe_address
        config_has_builder = config.builder.is_configured()
    except Exception as e:
        print(f"  ⚠ 配置文件读取失败: {e}")

# 检查加密私钥
encrypted_key_exists = Path("credentials/key.enc").exists()

# 凭证来源分析
has_private_key = False
has_safe_address = False
credential_sources = []

if env_private_key:
    print(f"  ✓ 环境变量私钥: POLY_PRIVATE_KEY")
    has_private_key = True
    credential_sources.append("环境变量私钥")
elif encrypted_key_exists:
    print(f"  ✓ 加密私钥文件: credentials/key.enc")
    has_private_key = True
    credential_sources.append("加密私钥文件")
else:
    print(f"  ✗ 私钥未配置")
    print(f"     - 环境变量 POLY_PRIVATE_KEY 未设置")
    print(f"     - credentials/key.enc 文件不存在")

if env_safe_address:
    print(f"  ✓ Safe地址 (环境变量): {env_safe_address[:10]}...")
    has_safe_address = True
    credential_sources.append("环境变量Safe地址")
elif config_safe_address:
    print(f"  ✓ Safe地址 (config.yaml): {config_safe_address[:10]}...")
    has_safe_address = True
    credential_sources.append("配置文件Safe地址")
else:
    print(f"  ✗ Safe地址未配置")

# Builder凭证（可选）
if config_has_builder:
    print(f"  ✓ Builder Program凭证已配置（免Gas模式）")
    credential_sources.append("Builder凭证")
else:
    print(f"  ⚠ Builder Program凭证未配置（将使用标准模式，需要Gas费）")

if has_private_key and has_safe_address:
    print(f"\n✅ 钱包凭证完整")
    results.append(("钱包凭证", True, f"来源: {', '.join(credential_sources)}"))
else:
    missing = []
    if not has_private_key:
        missing.append("私钥")
    if not has_safe_address:
        missing.append("Safe地址")
    print(f"\n❌ 钱包凭证不完整，缺少: {', '.join(missing)}")
    print(f"   设置方法:")
    print(f"   1. 环境变量: export POLY_PRIVATE_KEY=你的私钥")
    print(f"   2. 或运行: python scripts/setup.py")
    results.append(("钱包凭证", False, f"缺少: {', '.join(missing)}"))

print()

# ============================================================================
# 3. ✅ 配置环境变量或 config.yaml
# ============================================================================
print("[检查 3/5] 配置文件完备性")
print("-" * 70)

has_env = Path(".env").exists()
has_config = Path("config.yaml").exists()

if has_env:
    print(f"  ✓ .env 文件存在")
if has_config:
    print(f"  ✓ config.yaml 文件存在")
    if config_safe_address:
        print(f"    - Safe地址: {config_safe_address[:10]}...")
        print(f"    - 免Gas模式: {'启用' if config_has_builder else '禁用'}")

if not has_env and not has_config:
    print(f"  ✗ 无配置文件")
    print(f"    创建方法:")
    print(f"    1. 复制配置模板: cp config.example.yaml config.yaml")
    print(f"    2. 或创建 .env 文件")

if has_env or has_config:
    print(f"\n✅ 配置文件已就绪")
    config_type = []
    if has_env:
        config_type.append(".env")
    if has_config:
        config_type.append("config.yaml")
    results.append(("配置文件", True, f"类型: {', '.join(config_type)}"))
else:
    print(f"\n❌ 配置文件缺失")
    results.append(("配置文件", False, "未找到配置文件"))

print()

# ============================================================================
# 4. ✅ 运行快速入门示例验证配置
# ============================================================================
print("[检查 4/5] 快速入门示例可用性")
print("-" * 70)

quickstart_path = Path("examples/quickstart.py")
if quickstart_path.exists():
    print(f"  ✓ quickstart.py 存在")
    
    # 检查是否可以导入核心模块
    try:
        from src.bot import TradingBot
        from src.config import Config
        print(f"  ✓ 核心模块可导入")
        
        if has_private_key and has_safe_address:
            print(f"  ✓ 凭证齐全，可以运行 quickstart")
            print(f"    运行命令: python examples/quickstart.py")
            print(f"\n✅ 快速入门示例已就绪")
            results.append(("快速入门", True, "可以运行"))
        else:
            print(f"  ⚠ 凭证不完整，需要配置后才能运行")
            print(f"\n⚠ 快速入门示例需要完整凭证")
            results.append(("快速入门", False, "凭证不完整"))
    except ImportError as e:
        print(f"  ✗ 模块导入失败: {e}")
        print(f"\n❌ 快速入门示例不可用")
        results.append(("快速入门", False, f"导入失败: {e}"))
else:
    print(f"  ✗ quickstart.py 不存在")
    print(f"\n❌ 快速入门示例缺失")
    results.append(("快速入门", False, "文件不存在"))

print()

# ============================================================================
# 5. ✅ 从小额开始测试策略
# ============================================================================
print("[检查 5/5] 测试策略准备")
print("-" * 70)

flash_crash_path = Path("apps/run_flash_crash.py")
strategy_path = Path("strategies/flash_crash.py")

if flash_crash_path.exists() and strategy_path.exists():
    print(f"  ✓ Flash Crash 策略文件存在")
    
    try:
        from strategies.flash_crash import FlashCrashStrategy
        print(f"  ✓ 策略模块可导入")
        
        # 检查市场可用性
        try:
            from src.gamma_client import GammaClient
            gamma = GammaClient()
            market = gamma.get_current_15m_market("ETH")
            if market and market.get("acceptingOrders"):
                print(f"  ✓ 当前有活跃的15分钟市场")
                print(f"    市场: {market.get('slug', 'Unknown')}")
            else:
                print(f"  ⚠ 当前无活跃的15分钟市场（这是正常的）")
        except Exception as e:
            print(f"  ⚠ 市场检查失败: {e}")
        
        print(f"\n  推荐测试参数:")
        print(f"    python apps/run_flash_crash.py --coin ETH --size 1.0")
        print(f"    (从 1 USDC 小额开始测试)")
        
        if has_private_key and has_safe_address:
            print(f"\n✅ 策略测试已准备就绪")
            results.append(("策略测试", True, "所有组件就绪"))
        else:
            print(f"\n⚠ 需要配置凭证后才能运行策略")
            results.append(("策略测试", False, "凭证不完整"))
    except ImportError as e:
        print(f"  ✗ 策略模块导入失败: {e}")
        print(f"\n❌ 策略不可用")
        results.append(("策略测试", False, f"导入失败: {e}"))
else:
    print(f"  ✗ 策略文件不存在")
    print(f"\n❌ 策略缺失")
    results.append(("策略测试", False, "文件不存在"))

print()

# ============================================================================
# 总结
# ============================================================================
print("=" * 70)
print("检查结果总结")
print("=" * 70)
print()

all_passed = all(result[1] for result in results)
passed_count = sum(1 for result in results if result[1])
total_count = len(results)

for i, (name, passed, detail) in enumerate(results, 1):
    status = "✅" if passed else "❌"
    print(f"{status} [{i}/{total_count}] {name}: {detail}")

print()
print("=" * 70)

if all_passed:
    print("🎉 恭喜！所有检查通过，项目已完全准备就绪！")
    print()
    print("下一步操作:")
    print("  1. 运行快速入门: python examples/quickstart.py")
    print("  2. 测试策略: python apps/run_flash_crash.py --coin ETH --size 1.0")
    print("  3. 查看实时订单簿: python apps/orderbook_tui.py --coin BTC")
    print()
else:
    print(f"⚠ 完成度: {passed_count}/{total_count} 项通过")
    print()
    print("需要完成的项目:")
    for name, passed, detail in results:
        if not passed:
            print(f"  - {name}: {detail}")
    print()
    print("请参考上面的说明完成缺失的配置")
    print()

print("=" * 70)
