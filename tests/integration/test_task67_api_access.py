"""
Task 67 - 验证 Order Schedule API 接口可访问性

测试服务启动后，所有 Order Schedule API 端点是否可以正常访问
"""

import requests
import sys
from datetime import date, timedelta


def test_api_endpoints(base_url: str = "http://localhost:5000"):
    """测试所有 Order Schedule API 端点"""
    
    print("\n" + "=" * 60)
    print("  任务67 - API接口访问性测试")
    print("=" * 60 + "\n")
    
    # 检查服务是否运行
    print("1. 检查API服务器是否运行...")
    try:
        response = requests.get(f"{base_url}/", timeout=2)
        print(f"   ✅ API服务器正在运行 (状态码: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 无法连接到 {base_url}")
        print("   请先启动服务:")
        print("   - python apps/run_rebound.py --simulation")
        print("   或")
        print("   - python scripts/strategy_api.py server")
        return False
    except requests.exceptions.Timeout:
        print("   ❌ 连接超时")
        return False
    
    all_passed = True
    
    # 测试 1: POST /orderSchedule/create
    print("\n2. 测试 POST /orderSchedule/create")
    try:
        url = f"{base_url}/orderSchedule/create"
        payload = {
            "env": "sim",
            "strategy_type": "1",
            "schedule_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "09:00",
            "end_time": "17:00"
        }
        response = requests.post(url, json=payload, timeout=5)
        result = response.json()
        
        if response.status_code == 200 and result.get('success'):
            schedule_id = result.get('schedule_id')
            print(f"   ✅ 创建调度计划成功 (ID: {schedule_id})")
            print(f"   URL: {url}")
        else:
            print(f"   ❌ 创建失败: {result.get('message')}")
            all_passed = False
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        all_passed = False
    
    # 测试 2: GET /orderSchedule/query
    print("\n3. 测试 GET /orderSchedule/query")
    try:
        url = f"{base_url}/orderSchedule/query"
        params = {"env": "sim", "strategy_type": "1"}
        response = requests.get(url, params=params, timeout=5)
        result = response.json()
        
        if response.status_code == 200 and result.get('success'):
            count = result.get('count', 0)
            print(f"   ✅ 查询调度计划成功 (找到 {count} 个)")
            print(f"   URL: {url}?env=sim&strategy_type=1")
        else:
            print(f"   ❌ 查询失败: {result.get('message')}")
            all_passed = False
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        all_passed = False
    
    # 测试 3: GET /orderSchedule/check
    print("\n4. 测试 GET /orderSchedule/check")
    try:
        url = f"{base_url}/orderSchedule/check"
        params = {"env": "sim", "strategy_type": "1"}
        response = requests.get(url, params=params, timeout=5)
        result = response.json()
        
        if response.status_code == 200 and result.get('success') is not None:
            should_trade = result.get('should_trade')
            message = result.get('message')
            status = "应该交易 ✅" if should_trade else "不应该交易 ⏸️"
            print(f"   ✅ 检查交易时间成功 ({status})")
            print(f"   原因: {message}")
            print(f"   URL: {url}?env=sim&strategy_type=1")
        else:
            print(f"   ❌ 检查失败: {result.get('message')}")
            all_passed = False
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        all_passed = False
    
    # 测试 4: POST /orderSchedule/cancel
    print("\n5. 测试 POST /orderSchedule/cancel")
    try:
        url = f"{base_url}/orderSchedule/cancel"
        payload = {"schedule_id": 999999}  # 测试用的不存在ID
        response = requests.post(url, json=payload, timeout=5)
        result = response.json()
        
        # 即使ID不存在，接口也应该正常响应
        if response.status_code == 200 and 'success' in result:
            print("   ✅ 取消调度接口正常 (响应正确)")
            print(f"   消息: {result.get('message')}")
            print(f"   URL: {url}")
        else:
            print("   ❌ 接口异常")
            all_passed = False
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        all_passed = False
    
    # 总结
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有 Order Schedule API 端点测试通过！")
        print("任务67验证成功：服务启动后接口可以正常访问")
    else:
        print("❌ 部分接口测试失败")
    print("=" * 60 + "\n")
    
    return all_passed


def main():
    """主函数"""
    # 测试默认端口
    success = test_api_endpoints("http://localhost:5000")
    
    if success:
        print("✅ 任务67完成：live或sim模式启动时，Order Schedule API可以正确访问")
        print("📖 完整API文档: docs/api/order-schedule-api.md")
        sys.exit(0)
    else:
        print("\n提示:")
        print("1. 请确保服务已启动:")
        print("   python apps/run_rebound.py --simulation")
        print("2. 或单独启动API服务器:")
        print("   python scripts/strategy_api.py server")
        sys.exit(1)


if __name__ == "__main__":
    main()
