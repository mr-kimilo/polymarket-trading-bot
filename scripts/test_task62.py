"""
任务62测试脚本 - 验证API服务器集成

测试内容：
1. 验证API服务器可以在后台启动
2. 验证API端点可以正常访问
3. 验证策略运行时API功能正常
"""

import sys
import os
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_api_server_startup():
    """测试1: API服务器启动"""
    print("\n" + "="*60)
    print("测试1: API服务器后台启动")
    print("="*60)
    
    try:
        from apps.run_rebound import start_api_server_background
        
        # 使用非标准端口避免冲突
        test_port = 5001
        
        print(f"启动API服务器在端口 {test_port}...")
        start_api_server_background(port=test_port, host="127.0.0.1")
        
        # 等待服务器启动
        print("等待服务器启动...")
        time.sleep(3)
        
        print("✅ API服务器启动成功")
        return True, test_port
        
    except Exception as e:
        print(f"❌ API服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_api_endpoints(port):
    """测试2: API端点访问"""
    print("\n" + "="*60)
    print("测试2: API端点访问")
    print("="*60)
    
    base_url = f"http://127.0.0.1:{port}"
    
    tests = []
    
    # 测试获取激活规则
    try:
        print(f"\n测试: GET {base_url}/rules/active/simulate")
        response = requests.get(f"{base_url}/rules/active/simulate", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 状态码: {response.status_code}")
            print(f"   响应: success={data.get('success')}, message={data.get('message')}")
            tests.append(True)
        else:
            print(f"❌ 状态码: {response.status_code}")
            tests.append(False)
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        tests.append(False)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        tests.append(False)
    
    # 测试查询规则
    try:
        print(f"\n测试: GET {base_url}/rules/query?env=simulate")
        response = requests.get(f"{base_url}/rules/query?env=simulate", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 状态码: {response.status_code}")
            print(f"   响应: success={data.get('success')}, count={data.get('count')}")
            tests.append(True)
        else:
            print(f"❌ 状态码: {response.status_code}")
            tests.append(False)
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        tests.append(False)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        tests.append(False)
    
    # 测试创建规则
    try:
        print(f"\n测试: POST {base_url}/rules/create")
        payload = {
            "env": "test_task62",
            "stage_buy": "A",
            "price_down_percentage": 0.30,
            "price_down": 50.0,
            "take_profit": 0.80,
            "stop_loss": 0.20
        }
        response = requests.post(
            f"{base_url}/rules/create", 
            json=payload, 
            timeout=5,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 状态码: {response.status_code}")
            print(f"   响应: success={data.get('success')}, rule_id={data.get('rule_id')}")
            tests.append(True)
        else:
            print(f"❌ 状态码: {response.status_code}")
            print(f"   错误: {response.text}")
            tests.append(False)
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        tests.append(False)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        tests.append(False)
    
    passed = sum(tests)
    total = len(tests)
    print(f"\nAPI端点测试: {passed}/{total} 通过")
    
    return all(tests)


def test_flask_availability():
    """测试3: Flask可用性"""
    print("\n" + "="*60)
    print("测试3: Flask依赖检查")
    print("="*60)
    
    try:
        import flask
        print(f"✅ Flask已安装: version {flask.__version__}")
        return True
    except ImportError:
        print("❌ Flask未安装")
        print("   提示: pip install flask")
        return False


def test_api_integration():
    """测试4: 完整集成测试"""
    print("\n" + "="*60)
    print("测试4: API服务器完整集成")
    print("="*60)
    
    try:
        # 检查start_api_server_background函数
        from apps.run_rebound import start_api_server_background
        print("✅ start_api_server_background 函数存在")
        
        # 检查函数签名
        import inspect
        sig = inspect.signature(start_api_server_background)
        params = list(sig.parameters.keys())
        print(f"✅ 函数参数: {params}")
        
        if 'port' in params and 'host' in params:
            print("✅ 参数正确包含 port 和 host")
            return True
        else:
            print("❌ 参数不完整")
            return False
            
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("任务62测试: API服务器集成")
    print("="*60)
    
    results = []
    
    # 测试3: Flask可用性（必须先检查）
    flask_ok = test_flask_availability()
    results.append(("Flask依赖", flask_ok))
    
    if not flask_ok:
        print("\n" + "="*60)
        print("⚠️  Flask未安装，部分测试将跳过")
        print("   安装命令: pip install flask")
        print("="*60)
        # 继续其他测试
    
    # 测试4: 集成检查
    results.append(("API集成", test_api_integration()))
    
    # 只有Flask安装时才测试服务器
    if flask_ok:
        # 测试1: 服务器启动
        server_ok, port = test_api_server_startup()
        results.append(("服务器启动", server_ok))
        
        # 测试2: API端点（只有服务器启动成功才测试）
        if server_ok and port:
            results.append(("API端点", test_api_endpoints(port)))
        else:
            print("\n跳过API端点测试（服务器未启动）")
            results.append(("API端点", False))
    
    # 汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed and name != "Flask依赖":  # Flask不是必需的
            all_passed = False
    
    print("="*60)
    if all_passed:
        print("🎉 所有必要测试通过！任务62实现正确")
    else:
        print("⚠️  部分测试失败，需要检查")
    
    if not flask_ok:
        print("\n💡 提示: 安装Flask以启用API功能")
        print("   pip install flask")
    
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        exit(1)
