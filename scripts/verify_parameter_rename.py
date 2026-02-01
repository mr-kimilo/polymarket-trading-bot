#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证参数重命名完成情况
Verify that parameter rename from stop_loss_stage_c to stop_loss_stage_bc is complete
"""

import os
from dataclasses import fields
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_config_yaml():
    """检查 config.yaml 是否有正确的参数"""
    print("\n=== Checking config.yaml ===")
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'stop_loss_stage_bc:' in content:
            print("✓ config.yaml has 'stop_loss_stage_bc' parameter")
            return True
        elif 'stop_loss_stage_c:' in content:
            print("✗ config.yaml still has old 'stop_loss_stage_c' parameter")
            return False
    except Exception as e:
        print(f"Error reading config.yaml: {e}")
        return False

def check_rebound_config():
    """检查 ReboundConfig 是否有正确的字段"""
    print("\n=== Checking ReboundConfig dataclass ===")
    try:
        from strategies.rebound import ReboundConfig
        
        # Check if field exists
        field_names = [f.name for f in fields(ReboundConfig)]
        
        if 'stop_loss_stage_bc' in field_names:
            print("✓ ReboundConfig has 'stop_loss_stage_bc' field")
            return True
        elif 'stop_loss_stage_c' in field_names:
            print("✗ ReboundConfig still has old 'stop_loss_stage_c' field")
            return False
        else:
            print("✗ ReboundConfig missing stop_loss field")
            return False
    except Exception as e:
        print(f"Error checking ReboundConfig: {e}")
        return False

def check_strategy_code():
    """检查策略代码中的使用"""
    print("\n=== Checking strategy code ===")
    try:
        with open('strategies/rebound.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        old_count = content.count('stop_loss_stage_c')
        # Exclude the field initialization and comparison lines which should use new name
        has_new = 'self.config.stop_loss_stage_bc' in content
        
        if has_new and old_count == 0:
            print("✓ strategies/rebound.py uses 'stop_loss_stage_bc' correctly")
            return True
        else:
            print(f"✗ Old parameter found in strategy code: {old_count} occurrences")
            return False
    except Exception as e:
        print(f"Error checking strategy code: {e}")
        return False

def check_test_scripts():
    """检查测试脚本"""
    print("\n=== Checking test scripts ===")
    test_files = [
        'scripts/test_task57_stop_loss_bc.py',
        'scripts/test_rebound_trend.py',
        'scripts/check_strategy3_config.py'
    ]
    
    all_ok = True
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"! {test_file} not found")
            continue
        
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'stop_loss_stage_c' not in content:
                print(f"✓ {test_file} uses updated parameter name")
            else:
                # Check if it's only in comments or examples
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'stop_loss_stage_c' in line and not (line.strip().startswith('#') or '"""' in line or "'''" in line):
                        print(f"✗ {test_file} line {i+1} has old parameter: {line.strip()}")
                        all_ok = False
        except Exception as e:
            print(f"Error checking {test_file}: {e}")
            all_ok = False
    
    return all_ok

def main():
    print("=" * 60)
    print("Parameter Rename Verification")
    print("stop_loss_stage_c → stop_loss_stage_bc")
    print("=" * 60)
    
    results = {
        'config.yaml': check_config_yaml(),
        'ReboundConfig': check_rebound_config(),
        'strategy code': check_strategy_code(),
        'test scripts': check_test_scripts(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for check_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{check_name:20} {status}")
    
    all_pass = all(results.values())
    
    print("=" * 60)
    if all_pass:
        print("✓ All checks passed - parameter rename is complete!")
    else:
        print("✗ Some checks failed - please review the changes")
    print("=" * 60)
    
    return 0 if all_pass else 1

if __name__ == '__main__':
    sys.exit(main())
