#!/usr/bin/env python3
"""
日志错误分析工具
分析logs目录中的所有日志文件，统计错误类型和修复状态
"""
import os
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def analyze_log_file(log_path):
    """分析单个日志文件"""
    errors = defaultdict(list)
    
    if not os.path.exists(log_path):
        return errors
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            # 查找错误关键词
            if any(keyword in line.lower() for keyword in ['error', 'failed', 'rejected', 'invalid', 'exception']):
                # 提取时间戳（如果有）
                timestamp_match = re.search(r'\[(\d{2}:\d{2}:\d{2})', line)
                timestamp = timestamp_match.group(1) if timestamp_match else f"Line {i+1}"
                
                # 分类错误类型
                if 'invalid expiration' in line.lower():
                    errors['expiration_error'].append((timestamp, line.strip()))
                elif 'invalid signature' in line.lower():
                    errors['signature_error'].append((timestamp, line.strip()))
                elif 'invalid' in line.lower():
                    errors['other_invalid_error'].append((timestamp, line.strip()))
                elif 'rejected' in line.lower():
                    errors['rejected_order'].append((timestamp, line.strip()))
                elif 'failed' in line.lower():
                    errors['failed_operation'].append((timestamp, line.strip()))
                else:
                    errors['other_error'].append((timestamp, line.strip()))
                    
    except Exception as e:
        print(f"❌ 读取日志文件失败 {log_path}: {e}")
        
    return errors

def format_error_summary(error_type, error_list):
    """格式化错误摘要"""
    if not error_list:
        return None
        
    # 只显示前3个和最后1个
    sample_errors = error_list[:3]
    if len(error_list) > 3:
        sample_errors.append(error_list[-1])
        
    return {
        'count': len(error_list),
        'samples': sample_errors
    }

def main():
    print("=" * 80)
    print("日志错误分析报告")
    print("=" * 80)
    print()
    
    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("❌ logs 目录不存在")
        return
        
    all_errors = defaultdict(lambda: defaultdict(list))
    
    # 分析所有日志文件
    for log_file in logs_dir.glob("*.log"):
        print(f"📄 分析日志文件: {log_file.name}")
        print(f"   文件大小: {log_file.stat().st_size} bytes")
        print(f"   最后修改: {datetime.fromtimestamp(log_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        
        errors = analyze_log_file(log_file)
        
        if not any(errors.values()):
            print(f"   ✅ 未发现错误")
        else:
            for error_type, error_list in errors.items():
                all_errors[log_file.name][error_type].extend(error_list)
                print(f"   ⚠️  {error_type}: {len(error_list)} 个")
        
        print()
    
    # 总结报告
    print("=" * 80)
    print("总结报告")
    print("=" * 80)
    print()
    
    # 1. Expiration 错误检查
    expiration_total = sum(len(errors.get('expiration_error', [])) for errors in all_errors.values())
    print(f"1️⃣  Expiration 错误检查:")
    if expiration_total == 0:
        print(f"   ✅ 未发现 'invalid expiration' 错误")
        print(f"   ✅ expiration bug 已修复！")
    else:
        print(f"   ❌ 发现 {expiration_total} 个 expiration 错误")
        for log_name, errors in all_errors.items():
            if 'expiration_error' in errors:
                print(f"      {log_name}: {len(errors['expiration_error'])} 个")
                for timestamp, line in errors['expiration_error'][:2]:
                    print(f"        [{timestamp}] {line[:100]}...")
    print()
    
    # 2. Signature 错误检查
    signature_total = sum(len(errors.get('signature_error', [])) for errors in all_errors.values())
    print(f"2️⃣  Signature 错误检查:")
    if signature_total == 0:
        print(f"   ✅ 未发现 'invalid signature' 错误")
    else:
        print(f"   ⚠️  发现 {signature_total} 个 signature 错误（需要进一步调查）")
        for log_name, errors in all_errors.items():
            if 'signature_error' in errors:
                print(f"      {log_name}: {len(errors['signature_error'])} 个")
                for timestamp, line in errors['signature_error'][:2]:
                    print(f"        [{timestamp}] {line[:100]}...")
    print()
    
    # 3. 其他错误统计
    other_errors_count = 0
    for errors in all_errors.values():
        for error_type, error_list in errors.items():
            if error_type not in ['expiration_error', 'signature_error']:
                other_errors_count += len(error_list)
    
    print(f"3️⃣  其他错误:")
    if other_errors_count == 0:
        print(f"   ✅ 未发现其他错误")
    else:
        print(f"   ℹ️  发现 {other_errors_count} 个其他类型错误")
        for log_name, errors in all_errors.items():
            for error_type, error_list in errors.items():
                if error_type not in ['expiration_error', 'signature_error'] and error_list:
                    print(f"      {log_name} - {error_type}: {len(error_list)} 个")
    print()
    
    # 4. 最终结论
    print("=" * 80)
    print("✨ 修复状态总结:")
    print("=" * 80)
    if expiration_total == 0:
        print("✅ expiration bug 已成功修复 - 日志中无相关错误")
    else:
        print("❌ expiration bug 仍需修复")
        
    if signature_total > 0:
        print(f"⚠️  发现新问题: {signature_total} 个 signature 错误需要调查")
        print("   可能原因:")
        print("   1. 私钥/Safe地址配置问题")
        print("   2. 签名算法实现问题")
        print("   3. API认证问题")
        
    print()

if __name__ == "__main__":
    main()
