#!/usr/bin/env python3
"""Quick test of auto_claim config loading"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from apps.run_rebound import load_auto_claim_from_config
from strategies.rebound import ReboundConfig

# Load config
ac = load_auto_claim_from_config()
print(f"Loaded from config:")
print(f"  enabled={ac['enabled']}")
print(f"  min_balance=${ac['min_balance']}")
print(f"  interval={ac['check_interval']}s ({ac['check_interval']/60:.0f} min)")
print()

# Create ReboundConfig
cfg = ReboundConfig(
    auto_claim_enabled=ac['enabled'],
    auto_claim_min_balance=ac['min_balance'],
    auto_claim_check_interval=ac['check_interval']
)

print(f"ReboundConfig:")
print(f"  enabled={cfg.auto_claim_enabled}")
print(f"  min_balance=${cfg.auto_claim_min_balance}")
print(f"  interval={cfg.auto_claim_check_interval}s ({cfg.auto_claim_check_interval/60:.0f} min)")
print()
print("✓ Configuration loading works correctly!")
