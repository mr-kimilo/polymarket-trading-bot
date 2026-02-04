"""
Order Schedule API 测试脚本 (任务66)

测试所有 API 端点以验证文档的准确性
"""

import requests
import json
from datetime import date, timedelta
import sys

BASE_URL = "http://localhost:5000"


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def test_create_schedule():
    """测试创建订单计划"""
    print_section("测试 1: 创建订单计划 (POST /orderSchedule/create)")
    
    url = f"{BASE_URL}/orderSchedule/create"
    payload = {
        "env": "sim",
        "strategy_type": "1",
        "schedule_date": (date.today() + timedelta(days=1)).isoformat(),
        "start_time": "09:00",
        "end_time": "17:00"
    }
    
    print(f"请求 URL: {url}")
    print(f"请求体:\n{json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload)
        print(f"\n响应状态码: {response.status_code}")
        result = response.json()
        print(f"响应体:\n{json.dumps(result, indent=2)}")
        
        if result.get('success'):
            print(f"\n✅ 成功: 创建了计划 ID={result.get('schedule_id')}")
            return result.get('schedule_id')
        else:
            print(f"\n❌ 失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        return None


def test_query_schedules():
    """测试查询订单计划"""
    print_section("测试 2: 查询订单计划 (GET /orderSchedule/query)")
    
    url = f"{BASE_URL}/orderSchedule/query"
    params = {"env": "sim", "strategy_type": "1"}
    
    print(f"请求 URL: {url}")
    print(f"查询参数: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"\n响应状态码: {response.status_code}")
        result = response.json()
        print(f"响应体:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if result.get('success'):
            print(f"\n✅ 成功: 找到 {result.get('count')} 个计划")
        else:
            print(f"\n❌ 失败: {result.get('message')}")
        
        return result
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        return None


def test_check_should_trade():
    """测试检查是否应该交易"""
    print_section("测试 3: 检查是否应该交易 (GET /orderSchedule/check)")
    
    url = f"{BASE_URL}/orderSchedule/check"
    params = {"env": "sim", "strategy_type": "1"}
    
    print(f"请求 URL: {url}")
    print(f"查询参数: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"\n响应状态码: {response.status_code}")
        result = response.json()
        print(f"响应体:\n{json.dumps(result, indent=2)}")
        
        if result.get('success'):
            should_trade = result.get('should_trade')
            status = "应该交易 ✅" if should_trade else "不应该交易 ⏸️"
            print(f"\n✅ 成功: {status}")
            print(f"原因: {result.get('message')}")
            return should_trade
        else:
            print(f"\n❌ 失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        return False


def test_cancel_schedule(schedule_id: int):
    """测试取消订单计划"""
    print_section("测试 4: 取消订单计划 (POST /orderSchedule/cancel)")
    
    if not schedule_id:
        print("⚠️  跳过: 没有可取消的计划 ID")
        return
    
    url = f"{BASE_URL}/orderSchedule/cancel"
    payload = {"schedule_id": schedule_id}
    
    print(f"请求 URL: {url}")
    print(f"请求体:\n{json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload)
        print(f"\n响应状态码: {response.status_code}")
        result = response.json()
        print(f"响应体:\n{json.dumps(result, indent=2)}")
        
        if result.get('success'):
            print(f"\n✅ 成功: 已取消计划 ID={schedule_id}")
        else:
            print(f"\n❌ 失败: {result.get('message')}")
        
        return result
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        return None


def test_error_handling():
    """测试错误处理"""
    print_section("测试 5: 错误处理")
    
    test_cases = [
        {
            "name": "缺少必填参数",
            "method": "POST",
            "url": f"{BASE_URL}/orderSchedule/create",
            "data": {"env": "sim"},  # 缺少其他必填参数
        },
        {
            "name": "日期格式错误",
            "method": "POST",
            "url": f"{BASE_URL}/orderSchedule/create",
            "data": {
                "env": "sim",
                "strategy_type": "1",
                "schedule_date": "2026-2-5",  # 错误格式
                "start_time": "09:00",
                "end_time": "17:00"
            },
        },
        {
            "name": "时间格式错误",
            "method": "POST",
            "url": f"{BASE_URL}/orderSchedule/create",
            "data": {
                "env": "sim",
                "strategy_type": "1",
                "schedule_date": "2026-02-05",
                "start_time": "9:00",  # 错误格式
                "end_time": "17:00"
            },
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n--- 错误测试 {i}: {test['name']} ---")
        try:
            if test['method'] == 'POST':
                response = requests.post(test['url'], json=test['data'])
            else:
                response = requests.get(test['url'], params=test['data'])
            
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2)}")
            
            if not result.get('success'):
                print(f"✅ 正确捕获错误: {result.get('message')}")
            else:
                print("❌ 应该返回错误但成功了")
        except Exception as e:
            print(f"❌ 异常: {e}")


def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("  Order Schedule API 测试")
    print("  文档: docs/api/order-schedule-api.md")
    print("=" * 60)
    
    # 检查服务是否运行
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"\n✅ API 服务正在运行 (状态码: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 错误: 无法连接到 {BASE_URL}")
        print("请先启动 API 服务器:")
        print("  python scripts/strategy_api.py server")
        sys.exit(1)
    
    # 执行测试
    schedule_id = test_create_schedule()
    test_query_schedules()
    test_check_should_trade()
    test_cancel_schedule(schedule_id)
    test_error_handling()
    
    # 总结
    print_section("测试完成")
    print("所有 API 端点已测试完毕")
    print("详细文档请查看: docs/api/order-schedule-api.md")
    print()


if __name__ == "__main__":
    main()
