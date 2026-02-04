"""
Strategy Rules API - 策略规则管理接口 (任务60)

提供REST API供其他系统调用：
- POST /rules/active - 激活规则
- GET /rules/query - 查询规则
- POST /orderSchedule/create - 创建订单计划 (任务65)
- POST /orderSchedule/cancel - 取消订单计划 (任务65)
- GET /orderSchedule/query - 查询订单计划 (任务65)

使用方法：
    python -m scripts.strategy_api
    
    或者在其他系统中直接调用函数：
    from scripts.strategy_api import activate_rule, query_rules
"""

import os
import sys
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.database import get_database


@dataclass
class RuleActivateRequest:
    """激活规则请求"""
    rule_id: int


@dataclass
class RuleQueryRequest:
    """查询规则请求"""
    rule_ids: Optional[List[int]] = None
    create_date: Optional[str] = None  # ISO format: YYYY-MM-DD
    env: Optional[str] = None


def activate_rule(rule_id: int) -> dict:
    """
    激活指定的策略规则
    
    Args:
        rule_id: 规则ID
        
    Returns:
        {
            "success": bool,
            "message": str,
            "rule": dict or None
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "message": "Database not connected",
            "rule": None
        }
    
    # 激活规则
    success = db.activate_strategy3_rule(rule_id)
    if not success:
        return {
            "success": False,
            "message": f"Failed to activate rule {rule_id}",
            "rule": None
        }
    
    # 获取激活后的规则详情
    rules = db.query_strategy3_rules(rule_ids=[rule_id])
    rule = rules[0] if rules else None
    
    return {
        "success": True,
        "message": f"Rule {rule_id} activated successfully",
        "rule": rule
    }


def query_rules(
    rule_ids: Optional[List[int]] = None,
    create_date: Optional[str] = None,
    env: Optional[str] = None
) -> dict:
    """
    查询策略规则
    
    Args:
        rule_ids: 规则ID列表
        create_date: 创建日期起始 (YYYY-MM-DD格式)
        env: 环境筛选 ("production" 或 "simulate")
        
    Returns:
        {
            "success": bool,
            "message": str,
            "rules": list,
            "count": int
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "message": "Database not connected",
            "rules": [],
            "count": 0
        }
    
    # 解析日期
    date_from = None
    if create_date:
        try:
            date_from = datetime.strptime(create_date, "%Y-%m-%d")
        except ValueError:
            return {
                "success": False,
                "message": f"Invalid date format: {create_date}. Use YYYY-MM-DD",
                "rules": [],
                "count": 0
            }
    
    rules = db.query_strategy3_rules(
        rule_ids=rule_ids,
        create_date_from=date_from,
        env=env
    )
    
    return {
        "success": True,
        "message": f"Found {len(rules)} rules",
        "rules": rules,
        "count": len(rules)
    }


def create_rule(
    env: str = "simulate",
    stage_buy: str = "A",
    price_down_percentage: float = 0.25,
    price_down: float = 50.0,
    take_profit: float = 0.80,
    stop_loss: float = 0.20
) -> dict:
    """
    创建新的策略规则
    
    Args:
        env: 环境 ("production" 或 "simulate")
        stage_buy: 买入阶段 ("A", "B", "C")
        price_down_percentage: 价格下跌百分比阈值 (例如0.25表示25%)
        price_down: BTC价格下跌阈值 (美元)
        take_profit: 止盈比例 (例如0.80表示80%)
        stop_loss: 止损比例 (例如0.20表示20%)
        
    Returns:
        {
            "success": bool,
            "message": str,
            "rule_id": int or None
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "message": "Database not connected",
            "rule_id": None
        }
    
    rule_id = db.create_strategy3_rule(
        env=env,
        stage_buy=stage_buy,
        price_down_percentage=price_down_percentage,
        price_down=price_down,
        take_profit=take_profit,
        stop_loss=stop_loss
    )
    
    if rule_id:
        return {
            "success": True,
            "message": "Rule created successfully",
            "rule_id": rule_id
        }
    else:
        return {
            "success": False,
            "message": "Failed to create rule",
            "rule_id": None
        }


def get_active_rule(env: str = "simulate") -> dict:
    """
    获取当前激活的规则
    
    Args:
        env: 环境 ("production" 或 "simulate")
        
    Returns:
        {
            "success": bool,
            "message": str,
            "rule": dict or None
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "message": "Database not connected",
            "rule": None
        }
    
    rule = db.get_active_strategy3_rule(env=env)
    
    if rule:
        return {
            "success": True,
            "message": "Active rule found",
            "rule": rule
        }
    else:
        return {
            "success": True,
            "message": f"No active rule for env={env}",
            "rule": None
        }


# ==================== Order Schedule API (任务65) ====================

def create_order_schedule(
    env: str,
    strategy_type: str,
    schedule_date: str,
    start_time: str,
    end_time: str
) -> dict:
    """
    创建订单计划 (任务65, 补充任务)
    
    Args:
        env: 环境 ("prod" 或 "sim")
        strategy_type: 策略类型 ("1", "2", "3")
        schedule_date: 计划日期 (YYYY-MM-DD格式)
        start_time: 开始时间 (HH:MM格式)
        end_time: 结束时间 (HH:MM格式)
        
    Returns:
        {
            "success": bool,
            "message": str,
            "schedule_id": int or None
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "message": "Database not connected",
            "schedule_id": None
        }
    
    # 解析日期
    try:
        parsed_date = datetime.strptime(schedule_date, "%Y-%m-%d").date()
    except ValueError:
        return {
            "success": False,
            "message": f"Invalid date format: {schedule_date}. Use YYYY-MM-DD",
            "schedule_id": None
        }
    
    # 验证并解析时间
    try:
        start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        end_time_obj = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        return {
            "success": False,
            "message": "Invalid time format. Use HH:MM (e.g., '09:00')",
            "schedule_id": None
        }
    
    schedule_id = db.create_order_schedule(
        env=env,
        strategy_type=strategy_type,
        schedule_date=parsed_date,
        start_time=start_time_obj,
        end_time=end_time_obj,
        status=0  # plan
    )
    
    if schedule_id:
        return {
            "success": True,
            "message": "Order schedule created successfully",
            "schedule_id": schedule_id
        }
    else:
        return {
            "success": False,
            "message": "Failed to create order schedule",
            "schedule_id": None
        }


def cancel_order_schedule(schedule_id: int) -> dict:
    """
    取消订单计划 (任务65)
    
    Args:
        schedule_id: 计划ID
        
    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "message": "Database not connected"
        }
    
    success = db.cancel_order_schedule(schedule_id)
    
    if success:
        return {
            "success": True,
            "message": f"Order schedule {schedule_id} canceled successfully"
        }
    else:
        return {
            "success": False,
            "message": f"Failed to cancel order schedule {schedule_id}. It may not exist or already processed."
        }


def query_order_schedules(
    env: Optional[str] = None,
    strategy_type: Optional[str] = None,
    schedule_date: Optional[str] = None,
    status: Optional[int] = None
) -> dict:
    """
    查询订单计划 (任务65)
    
    Args:
        env: 环境筛选
        strategy_type: 策略类型筛选
        schedule_date: 日期筛选 (YYYY-MM-DD格式)
        status: 状态筛选 (0=plan, 1=running, 2=completed, 3=canceled)
        
    Returns:
        {
            "success": bool,
            "message": str,
            "schedules": list,
            "count": int
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "message": "Database not connected",
            "schedules": [],
            "count": 0
        }
    
    # 解析日期
    parsed_date = None
    if schedule_date:
        try:
            parsed_date = datetime.strptime(schedule_date, "%Y-%m-%d").date()
        except ValueError:
            return {
                "success": False,
                "message": f"Invalid date format: {schedule_date}. Use YYYY-MM-DD",
                "schedules": [],
                "count": 0
            }
    
    schedules = db.query_order_schedules(
        env=env,
        strategy_type=strategy_type,
        schedule_date=parsed_date,
        status=status
    )
    
    return {
        "success": True,
        "message": f"Found {len(schedules)} schedules",
        "schedules": schedules,
        "count": len(schedules)
    }


def check_should_trade(env: str, strategy_type: str) -> dict:
    """
    检查当前是否应该交易 (任务65)
    
    Args:
        env: 环境 ("prod" 或 "sim")
        strategy_type: 策略类型 ("1", "2", "3")
        
    Returns:
        {
            "success": bool,
            "should_trade": bool,
            "message": str
        }
    """
    db = get_database()
    if not db.is_connected:
        return {
            "success": False,
            "should_trade": False,
            "message": "Database not connected"
        }
    
    should_trade = db.check_should_trade(env=env, strategy_type=strategy_type)
    
    return {
        "success": True,
        "should_trade": should_trade,
        "message": "In scheduled trading time" if should_trade else "Not in scheduled trading time"
    }


# ==================== Flask API (可选) ====================

def create_flask_app():
    """创建Flask应用（如果安装了Flask）"""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        print("Flask not installed. Run: pip install flask")
        return None
    
    app = Flask(__name__)
    
    @app.route('/rules/active', methods=['POST'])
    def api_activate_rule():
        """激活规则 API"""
        data = request.get_json()
        if not data or 'rule_id' not in data:
            return jsonify({"success": False, "message": "rule_id is required"}), 400
        
        result = activate_rule(data['rule_id'])
        return jsonify(result)
    
    @app.route('/rules/query', methods=['GET'])
    def api_query_rules():
        """查询规则 API"""
        rule_ids = request.args.getlist('rule_id', type=int) or None
        create_date = request.args.get('create_date')
        env = request.args.get('env')
        
        result = query_rules(
            rule_ids=rule_ids,
            create_date=create_date,
            env=env
        )
        return jsonify(result)
    
    @app.route('/rules/create', methods=['POST'])
    def api_create_rule():
        """创建规则 API"""
        data = request.get_json() or {}
        result = create_rule(
            env=data.get('env', 'simulate'),
            stage_buy=data.get('stage_buy', 'A'),
            price_down_percentage=data.get('price_down_percentage', 0.25),
            price_down=data.get('price_down', 50.0),
            take_profit=data.get('take_profit', 0.80),
            stop_loss=data.get('stop_loss', 0.20)
        )
        return jsonify(result)
    
    @app.route('/rules/active/<env>', methods=['GET'])
    def api_get_active_rule(env):
        """获取激活规则 API"""
        result = get_active_rule(env=env)
        return jsonify(result)
    
    # ==================== Order Schedule API (任务65) ====================
    
    @app.route('/orderSchedule/create', methods=['POST'])
    def api_create_order_schedule():
        """创建订单计划 API (任务65, 补充任务)"""
        data = request.get_json() or {}
        
        required_fields = ['env', 'strategy_type', 'schedule_date', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"{field} is required"}), 400
        
        result = create_order_schedule(
            env=data['env'],
            strategy_type=data['strategy_type'],
            schedule_date=data['schedule_date'],
            start_time=data['start_time'],
            end_time=data['end_time']
        )
        return jsonify(result)
    
    @app.route('/orderSchedule/cancel', methods=['POST'])
    def api_cancel_order_schedule():
        """取消订单计划 API (任务65)"""
        data = request.get_json()
        if not data or 'schedule_id' not in data:
            return jsonify({"success": False, "message": "schedule_id is required"}), 400
        
        result = cancel_order_schedule(data['schedule_id'])
        return jsonify(result)
    
    @app.route('/orderSchedule/query', methods=['GET'])
    def api_query_order_schedules():
        """查询订单计划 API (任务65)"""
        env = request.args.get('env')
        strategy_type = request.args.get('strategy_type')
        schedule_date = request.args.get('schedule_date')
        status = request.args.get('status', type=int)
        
        result = query_order_schedules(
            env=env,
            strategy_type=strategy_type,
            schedule_date=schedule_date,
            status=status
        )
        return jsonify(result)
    
    @app.route('/orderSchedule/check', methods=['GET'])
    def api_check_should_trade():
        """检查是否应该交易 API (任务65)"""
        env = request.args.get('env')
        strategy_type = request.args.get('strategy_type')
        
        if not env or not strategy_type:
            return jsonify({"success": False, "message": "env and strategy_type are required"}), 400
        
        result = check_should_trade(env=env, strategy_type=strategy_type)
        return jsonify(result)
    
    return app


# ==================== CLI ====================

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Strategy Rules API")
    subparsers = parser.add_subparsers(dest='command')
    
    # 激活规则
    activate_parser = subparsers.add_parser('activate', help='Activate a rule')
    activate_parser.add_argument('rule_id', type=int, help='Rule ID to activate')
    
    # 查询规则
    query_parser = subparsers.add_parser('query', help='Query rules')
    query_parser.add_argument('--rule-ids', type=int, nargs='+', help='Rule IDs')
    query_parser.add_argument('--date', help='Create date (YYYY-MM-DD)')
    query_parser.add_argument('--env', help='Environment (production/simulate)')
    
    # 创建规则
    create_parser = subparsers.add_parser('create', help='Create a new rule')
    create_parser.add_argument('--env', default='simulate', help='Environment')
    create_parser.add_argument('--stage', default='A', help='Buy stage (A/B/C)')
    create_parser.add_argument('--price-down-pct', type=float, default=0.25, help='Price down percentage')
    create_parser.add_argument('--price-down', type=float, default=50.0, help='BTC price down threshold')
    create_parser.add_argument('--take-profit', type=float, default=0.80, help='Take profit ratio')
    create_parser.add_argument('--stop-loss', type=float, default=0.20, help='Stop loss ratio')
    
    # 获取激活规则
    active_parser = subparsers.add_parser('active', help='Get active rule')
    active_parser.add_argument('--env', default='simulate', help='Environment')
    
    # 启动API服务器
    server_parser = subparsers.add_parser('server', help='Start Flask API server')
    server_parser.add_argument('--host', default='0.0.0.0', help='Host')
    server_parser.add_argument('--port', type=int, default=5000, help='Port')
    
    # 任务65: 订单计划命令
    schedule_create_parser = subparsers.add_parser('schedule-create', help='Create order schedule (任务65补充)')
    schedule_create_parser.add_argument('--env', required=True, help='Environment (prod/sim)')
    schedule_create_parser.add_argument('--strategy-type', required=True, help='Strategy type (1/2/3)')
    schedule_create_parser.add_argument('--date', required=True, help='Schedule date (YYYY-MM-DD)')
    schedule_create_parser.add_argument('--start-time', required=True, help='Start time (HH:MM)')
    schedule_create_parser.add_argument('--end-time', required=True, help='End time (HH:MM)')
    
    schedule_cancel_parser = subparsers.add_parser('schedule-cancel', help='Cancel order schedule')
    schedule_cancel_parser.add_argument('schedule_id', type=int, help='Schedule ID to cancel')
    
    schedule_query_parser = subparsers.add_parser('schedule-query', help='Query order schedules')
    schedule_query_parser.add_argument('--env', help='Environment filter')
    schedule_query_parser.add_argument('--strategy-type', help='Strategy type filter')
    schedule_query_parser.add_argument('--date', help='Date filter (YYYY-MM-DD)')
    schedule_query_parser.add_argument('--status', type=int, help='Status filter (0=plan, 1=running, 2=completed, 3=canceled)')
    
    schedule_check_parser = subparsers.add_parser('schedule-check', help='Check if should trade now')
    schedule_check_parser.add_argument('--env', required=True, help='Environment (prod/sim)')
    schedule_check_parser.add_argument('--strategy-type', required=True, help='Strategy type (1/2/3)')
    
    args = parser.parse_args()
    
    if args.command == 'activate':
        result = activate_rule(args.rule_id)
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        if result['rule']:
            print(f"Rule: {result['rule']}")
    
    elif args.command == 'query':
        result = query_rules(
            rule_ids=args.rule_ids,
            create_date=args.date,
            env=args.env
        )
        print(f"Success: {result['success']}")
        print(f"Count: {result['count']}")
        for rule in result['rules']:
            print(f"  - ID={rule['id']} env={rule['env']} status={rule['status']} "
                  f"stage={rule['stage_buy']} tp={rule['take_profit']:.0%} sl={rule['stop_loss']:.0%}")
    
    elif args.command == 'create':
        result = create_rule(
            env=args.env,
            stage_buy=args.stage,
            price_down_percentage=args.price_down_pct,
            price_down=args.price_down,
            take_profit=args.take_profit,
            stop_loss=args.stop_loss
        )
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        if result['rule_id']:
            print(f"Rule ID: {result['rule_id']}")
    
    elif args.command == 'active':
        result = get_active_rule(env=args.env)
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        if result['rule']:
            print(f"Rule: {result['rule']}")
    
    elif args.command == 'server':
        app = create_flask_app()
        if app:
            print(f"Starting API server on {args.host}:{args.port}")
            app.run(host=args.host, port=args.port, debug=True)
    
    # 任务65: 订单计划命令处理
    elif args.command == 'schedule-create':
        result = create_order_schedule(
            env=args.env,
            strategy_type=args.strategy_type,
            schedule_date=args.date,
            start_time=args.start_time,
            end_time=args.end_time
        )
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        if result.get('schedule_id'):
            print(f"Schedule ID: {result['schedule_id']}")
    
    elif args.command == 'schedule-cancel':
        result = cancel_order_schedule(args.schedule_id)
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
    
    elif args.command == 'schedule-query':
        result = query_order_schedules(
            env=args.env,
            strategy_type=args.strategy_type,
            schedule_date=args.date,
            status=args.status
        )
        print(f"Success: {result['success']}")
        print(f"Count: {result['count']}")
        for schedule in result['schedules']:
            status_map = {0: 'plan', 1: 'running', 2: 'completed', 3: 'canceled'}
            status_str = status_map.get(schedule['status'], str(schedule['status']))
            print(f"  - ID={schedule['id']} env={schedule['env']} type={schedule['strategy_type']} "
                  f"date={schedule['schedule_date']} start={schedule['start_time']} "
                  f"end={schedule['end_time']} status={status_str}")
    
    elif args.command == 'schedule-check':
        result = check_should_trade(env=args.env, strategy_type=args.strategy_type)
        print(f"Should Trade: {result['should_trade']}")
        print(f"Message: {result['message']}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
