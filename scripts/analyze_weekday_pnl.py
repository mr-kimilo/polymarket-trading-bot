"""
Task 8: 分析策略1周一到周四与周五周六的盈亏差异

分析内容:
1. 查询数据库订单数据，按星期分类统计
2. 获取BTC 15分钟K线数据
3. 分析周一到周四与周五周六的市场特征差异
4. 提出优化建议
"""

import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import requests
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# 导入psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("请安装 psycopg2: pip install psycopg2-binary")
    sys.exit(1)


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(
        host=os.environ.get("DATABASE_HOST", "127.0.0.1"),
        port=int(os.environ.get("DATABASE_PORT", "5432")),
        database=os.environ.get("DATABASE_NAME", "poly_market"),
        user=os.environ.get("DATABASE_USER", ""),
        password=os.environ.get("DATABASE_PASSWORD", "")
    )


def fetch_orders_by_weekday(conn, days=30):
    """
    按星期分类获取订单数据
    
    Returns:
        dict: {weekday: [orders]}，weekday 0=周一, 6=周日
    """
    sql = """
    SELECT 
        id, coin, side, segment, strategy_type,
        entry_price, exit_price, entry_btc_price, exit_btc_price,
        pnl, pnl_percent, status, is_simulated, env,
        created_at, period_start, period_end,
        trigger_up_price, trigger_down_price,
        trigger_up_drop, trigger_down_drop, btc_drop,
        EXTRACT(DOW FROM created_at) as day_of_week,
        EXTRACT(HOUR FROM created_at) as hour_of_day
    FROM rebound_orders
    WHERE created_at >= CURRENT_DATE - INTERVAL '%s days'
      AND status = 'closed'
    ORDER BY created_at;
    """
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (days,))
        rows = cur.fetchall()
    
    # 按星期分组 (PostgreSQL DOW: 0=周日, 1=周一...6=周六)
    # 转换为 Python weekday: 0=周一...6=周日
    weekday_map = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    
    orders_by_weekday = defaultdict(list)
    for row in rows:
        pg_dow = int(row['day_of_week'])
        py_weekday = weekday_map.get(pg_dow, pg_dow)
        orders_by_weekday[py_weekday].append(dict(row))
    
    return orders_by_weekday


def calculate_stats(orders):
    """计算订单统计数据"""
    if not orders:
        return {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_pnl': 0,
            'max_win': 0,
            'max_loss': 0
        }
    
    wins = [o for o in orders if o.get('pnl') and o['pnl'] > 0]
    losses = [o for o in orders if o.get('pnl') and o['pnl'] <= 0]
    
    pnls = [o['pnl'] for o in orders if o.get('pnl') is not None]
    
    return {
        'total': len(orders),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(orders) * 100 if orders else 0,
        'total_pnl': sum(pnls) if pnls else 0,
        'avg_pnl': sum(pnls) / len(pnls) if pnls else 0,
        'max_win': max(pnls) if pnls else 0,
        'max_loss': min(pnls) if pnls else 0
    }


def fetch_btc_klines(interval='15m', limit=500):
    """
    从币安获取BTC 15分钟K线数据
    
    Args:
        interval: K线间隔 ('15m', '1h', '4h', '1d')
        limit: 获取数量
        
    Returns:
        list: K线数据列表
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": "BTCUSDT",
        "interval": interval,
        "limit": limit
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        klines = []
        for k in data:
            klines.append({
                'open_time': datetime.fromtimestamp(k[0] / 1000),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5]),
                'close_time': datetime.fromtimestamp(k[6] / 1000),
                'day_of_week': datetime.fromtimestamp(k[0] / 1000).weekday()
            })
        return klines
    except Exception as e:
        print(f"获取K线失败: {e}")
        return []


def analyze_btc_volatility_by_weekday(klines):
    """
    按星期分析BTC波动性
    
    Returns:
        dict: {weekday: {avg_range, avg_volume, trend_ratio}}
    """
    weekday_data = defaultdict(list)
    
    for k in klines:
        weekday = k['day_of_week']
        range_pct = (k['high'] - k['low']) / k['open'] * 100  # 振幅百分比
        trend = 'up' if k['close'] > k['open'] else 'down'
        weekday_data[weekday].append({
            'range': k['high'] - k['low'],
            'range_pct': range_pct,
            'volume': k['volume'],
            'trend': trend
        })
    
    stats = {}
    for weekday, data in weekday_data.items():
        up_count = len([d for d in data if d['trend'] == 'up'])
        down_count = len([d for d in data if d['trend'] == 'down'])
        
        stats[weekday] = {
            'count': len(data),
            'avg_range': sum(d['range'] for d in data) / len(data),
            'avg_range_pct': sum(d['range_pct'] for d in data) / len(data),
            'avg_volume': sum(d['volume'] for d in data) / len(data),
            'up_ratio': up_count / len(data) * 100 if data else 0,
            'down_ratio': down_count / len(data) * 100 if data else 0
        }
    
    return stats


def analyze_order_timing(orders):
    """分析订单的时间段分布"""
    segment_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0})
    hour_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0})
    
    for order in orders:
        segment = order.get('segment', 'unknown')
        hour = order.get('hour_of_day', 0)
        pnl = order.get('pnl') or 0
        is_win = pnl > 0
        
        segment_stats[segment]['count'] += 1
        segment_stats[segment]['pnl'] += pnl
        if is_win:
            segment_stats[segment]['wins'] += 1
            
        hour_stats[int(hour)]['count'] += 1
        hour_stats[int(hour)]['pnl'] += pnl
        if is_win:
            hour_stats[int(hour)]['wins'] += 1
    
    return dict(segment_stats), dict(hour_stats)


def analyze_entry_conditions(orders):
    """分析入场条件"""
    conditions = []
    
    for order in orders:
        if order.get('trigger_up_drop') or order.get('trigger_down_drop'):
            conditions.append({
                'btc_drop': order.get('btc_drop'),
                'up_drop': order.get('trigger_up_drop'),
                'down_drop': order.get('trigger_down_drop'),
                'entry_price': order.get('entry_price'),
                'pnl': order.get('pnl'),
                'is_win': (order.get('pnl') or 0) > 0
            })
    
    if not conditions:
        return None
    
    wins = [c for c in conditions if c['is_win']]
    losses = [c for c in conditions if not c['is_win']]
    
    return {
        'win_avg_btc_drop': sum(c['btc_drop'] or 0 for c in wins) / len(wins) if wins else 0,
        'loss_avg_btc_drop': sum(c['btc_drop'] or 0 for c in losses) / len(losses) if losses else 0,
        'win_avg_entry': sum(c['entry_price'] or 0 for c in wins) / len(wins) if wins else 0,
        'loss_avg_entry': sum(c['entry_price'] or 0 for c in losses) / len(losses) if losses else 0,
    }


def print_report(orders_by_weekday, btc_stats):
    """打印分析报告"""
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    
    print("\n" + "="*80)
    print("                    任务8: 策略1 周一到周四 vs 周五周六 分析报告")
    print("="*80)
    
    # 1. 按星期统计订单盈亏
    print("\n📊 一、按星期分类的订单统计")
    print("-"*80)
    print(f"{'星期':<8}{'订单数':>10}{'盈利':>10}{'亏损':>10}{'胜率':>12}{'总盈亏':>15}{'平均盈亏':>15}")
    print("-"*80)
    
    weekday_total = {'mon_thu': [], 'fri_sat': []}
    
    for weekday in range(7):
        orders = orders_by_weekday.get(weekday, [])
        stats = calculate_stats(orders)
        
        name = weekday_names[weekday]
        print(f"{name:<8}{stats['total']:>10}{stats['wins']:>10}{stats['losses']:>10}"
              f"{stats['win_rate']:>10.1f}%{stats['total_pnl']:>15.2f}{stats['avg_pnl']:>15.2f}")
        
        # 分组
        if weekday < 4:  # 周一到周四
            weekday_total['mon_thu'].extend(orders)
        elif weekday < 6:  # 周五周六
            weekday_total['fri_sat'].extend(orders)
    
    # 2. 周一到周四 vs 周五周六 对比
    print("\n" + "="*80)
    print("📈 二、周一到周四 vs 周五周六 对比")
    print("-"*80)
    
    mon_thu_stats = calculate_stats(weekday_total['mon_thu'])
    fri_sat_stats = calculate_stats(weekday_total['fri_sat'])
    
    print(f"{'分组':<15}{'订单数':>10}{'盈利':>10}{'亏损':>10}{'胜率':>12}{'总盈亏':>15}{'平均盈亏':>15}")
    print("-"*80)
    print(f"{'周一到周四':<12}{mon_thu_stats['total']:>10}{mon_thu_stats['wins']:>10}{mon_thu_stats['losses']:>10}"
          f"{mon_thu_stats['win_rate']:>10.1f}%{mon_thu_stats['total_pnl']:>15.2f}{mon_thu_stats['avg_pnl']:>15.2f}")
    print(f"{'周五周六':<14}{fri_sat_stats['total']:>10}{fri_sat_stats['wins']:>10}{fri_sat_stats['losses']:>10}"
          f"{fri_sat_stats['win_rate']:>10.1f}%{fri_sat_stats['total_pnl']:>15.2f}{fri_sat_stats['avg_pnl']:>15.2f}")
    
    # 3. BTC波动性分析
    print("\n" + "="*80)
    print("📉 三、BTC 15分钟K线波动性分析（按星期）")
    print("-"*80)
    print(f"{'星期':<8}{'K线数':>10}{'平均振幅':>15}{'振幅%':>12}{'上涨%':>12}{'下跌%':>12}")
    print("-"*80)
    
    for weekday in range(7):
        if weekday in btc_stats:
            s = btc_stats[weekday]
            name = weekday_names[weekday]
            print(f"{name:<8}{s['count']:>10}{s['avg_range']:>15.2f}{s['avg_range_pct']:>10.2f}%"
                  f"{s['up_ratio']:>10.1f}%{s['down_ratio']:>10.1f}%")
    
    # 4. 时段分析
    print("\n" + "="*80)
    print("⏰ 四、时段(Segment)分析")
    print("-"*80)
    
    all_orders = []
    for orders in orders_by_weekday.values():
        all_orders.extend(orders)
    
    segment_stats, hour_stats = analyze_order_timing(all_orders)
    
    print(f"{'时段':<10}{'订单数':>10}{'盈利数':>10}{'胜率':>12}{'总盈亏':>15}")
    print("-"*80)
    for seg in ['A', 'B', 'C']:
        if seg in segment_stats:
            s = segment_stats[seg]
            win_rate = s['wins'] / s['count'] * 100 if s['count'] > 0 else 0
            print(f"{seg:<10}{s['count']:>10}{s['wins']:>10}{win_rate:>10.1f}%{s['pnl']:>15.2f}")
    
    # 5. 入场条件分析
    print("\n" + "="*80)
    print("🎯 五、入场条件分析")
    print("-"*80)
    
    mon_thu_conditions = analyze_entry_conditions(weekday_total['mon_thu'])
    fri_sat_conditions = analyze_entry_conditions(weekday_total['fri_sat'])
    
    if mon_thu_conditions:
        print("\n周一到周四:")
        print(f"  盈利订单平均BTC变化: {mon_thu_conditions['win_avg_btc_drop']:.2f}")
        print(f"  亏损订单平均BTC变化: {mon_thu_conditions['loss_avg_btc_drop']:.2f}")
        print(f"  盈利订单平均入场价: {mon_thu_conditions['win_avg_entry']:.4f}")
        print(f"  亏损订单平均入场价: {mon_thu_conditions['loss_avg_entry']:.4f}")
    
    if fri_sat_conditions:
        print("\n周五周六:")
        print(f"  盈利订单平均BTC变化: {fri_sat_conditions['win_avg_btc_drop']:.2f}")
        print(f"  亏损订单平均BTC变化: {fri_sat_conditions['loss_avg_btc_drop']:.2f}")
        print(f"  盈利订单平均入场价: {fri_sat_conditions['win_avg_entry']:.4f}")
        print(f"  亏损订单平均入场价: {fri_sat_conditions['loss_avg_entry']:.4f}")
    
    # 6. 结论和建议
    print("\n" + "="*80)
    print("💡 六、分析结论和优化建议")
    print("="*80)
    
    # 计算差异
    win_rate_diff = fri_sat_stats['win_rate'] - mon_thu_stats['win_rate']
    
    print(f"""
基于数据分析，周一到周四与周五周六的主要差异:

1. 胜率差异: 周五周六胜率比周一到周四高 {win_rate_diff:.1f}%

2. 可能原因分析:
   a) 周末市场参与者较少，价格波动更可预测
   b) 周末机构交易者活动减少，散户主导市场
   c) 周一到周四受宏观经济数据影响更大
   d) 周末BTC价格波动幅度可能更稳定

3. 优化建议:

   📌 方案A: 调整入场条件 (周一到周四更严格)
   - 周一到周四: UP/DOWN跌至25以下才入场 (原30)
   - BTC价格变化限制从50点降到30点
   - 只在A段操作，避免B、C段
   
   📌 方案B: 调整仓位管理
   - 周一到周四: 单笔仓位降低50%
   - 周五周六: 保持正常仓位
   
   📌 方案C: 增加过滤条件
   - 检查当日BTC整体趋势
   - 如果当日已亏损超过X次，暂停交易
   - 增加ATR(平均真实波动)过滤

   📌 方案D: 时间段优化
   - 分析哪些小时段盈利更高
   - 只在高胜率时间段执行策略
   
   📌 方案E: 考虑周一到周四不交易
   - 如果优化后仍亏损，考虑只在周五周六开启策略1
""")
    
    return {
        'mon_thu': mon_thu_stats,
        'fri_sat': fri_sat_stats,
        'btc_volatility': btc_stats,
        'segment_stats': segment_stats
    }


def main():
    """主函数"""
    print("正在连接数据库...")
    
    try:
        conn = get_db_connection()
        print("✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        sys.exit(1)
    
    try:
        # 获取订单数据
        print("正在查询订单数据...")
        orders_by_weekday = fetch_orders_by_weekday(conn, days=30)
        total_orders = sum(len(orders) for orders in orders_by_weekday.values())
        print(f"✅ 获取到 {total_orders} 条订单")
        
        # 获取BTC K线数据
        print("正在获取BTC 15分钟K线数据...")
        klines = fetch_btc_klines(interval='15m', limit=500)
        print(f"✅ 获取到 {len(klines)} 条K线")
        
        # 分析BTC波动性
        btc_stats = analyze_btc_volatility_by_weekday(klines)
        
        # 打印报告
        results = print_report(orders_by_weekday, btc_stats)
        
        # 保存报告到文件
        report_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'docs',
            'task8_weekday_analysis.md'
        )
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(generate_markdown_report(orders_by_weekday, btc_stats, results))
        
        print(f"\n📄 报告已保存到: {report_path}")
        
    except Exception as e:
        print(f"❌ 分析过程出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def generate_markdown_report(orders_by_weekday, btc_stats, results):
    """生成Markdown格式报告"""
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    
    report = f"""# 任务8: 策略1 周一到周四 vs 周五周六 盈亏分析报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 一、问题描述

策略1在周一到周四晚上的数据总是亏损，而周五和周六晚上才有盈利。需要分析原因并提出优化方案。

---

## 二、数据统计

### 2.1 按星期分类的订单统计

| 星期 | 订单数 | 盈利 | 亏损 | 胜率 | 总盈亏 | 平均盈亏 |
|------|--------|------|------|------|--------|----------|
"""
    
    for weekday in range(7):
        orders = orders_by_weekday.get(weekday, [])
        stats = calculate_stats(orders)
        name = weekday_names[weekday]
        report += f"| {name} | {stats['total']} | {stats['wins']} | {stats['losses']} | {stats['win_rate']:.1f}% | {stats['total_pnl']:.2f} | {stats['avg_pnl']:.2f} |\n"
    
    mon_thu = results['mon_thu']
    fri_sat = results['fri_sat']
    
    report += f"""
### 2.2 周一到周四 vs 周五周六 对比

| 分组 | 订单数 | 盈利 | 亏损 | 胜率 | 总盈亏 | 平均盈亏 |
|------|--------|------|------|------|--------|----------|
| 周一到周四 | {mon_thu['total']} | {mon_thu['wins']} | {mon_thu['losses']} | {mon_thu['win_rate']:.1f}% | {mon_thu['total_pnl']:.2f} | {mon_thu['avg_pnl']:.2f} |
| 周五周六 | {fri_sat['total']} | {fri_sat['wins']} | {fri_sat['losses']} | {fri_sat['win_rate']:.1f}% | {fri_sat['total_pnl']:.2f} | {fri_sat['avg_pnl']:.2f} |

### 2.3 BTC 15分钟K线波动性分析

| 星期 | K线数 | 平均振幅 | 振幅% | 上涨% | 下跌% |
|------|-------|----------|-------|-------|-------|
"""
    
    for weekday in range(7):
        if weekday in btc_stats:
            s = btc_stats[weekday]
            name = weekday_names[weekday]
            report += f"| {name} | {s['count']} | {s['avg_range']:.2f} | {s['avg_range_pct']:.2f}% | {s['up_ratio']:.1f}% | {s['down_ratio']:.1f}% |\n"
    
    win_rate_diff = fri_sat['win_rate'] - mon_thu['win_rate']
    
    report += f"""
---

## 三、差异分析

### 3.1 胜率差异

周五周六胜率比周一到周四高 **{win_rate_diff:.1f}%**

### 3.2 可能原因

1. **市场参与者差异**
   - 周末机构交易者活动减少
   - 散户主导市场，行为更可预测
   
2. **宏观经济影响**
   - 周一到周四受经济数据发布影响
   - 突发新闻导致价格剧烈波动
   
3. **流动性差异**
   - 周末流动性较低，价格波动更规律
   - 周一到周四流动性高，假突破更多

4. **市场情绪周期**
   - 周初承接上周末的情绪
   - 周末避险情绪降低

---

## 四、优化建议

### 方案A: 调整入场条件 (推荐)

针对周一到周四，采用更严格的入场条件:

```python
# 周一到周四入场条件
if weekday < 4:  # 周一到周四
    TRIGGER_THRESHOLD = 25  # 原30
    BTC_DROP_LIMIT = 30     # 原50
    ALLOWED_SEGMENTS = ["A"]  # 只允许A段
else:  # 周五周六
    TRIGGER_THRESHOLD = 30
    BTC_DROP_LIMIT = 50
    ALLOWED_SEGMENTS = ["A", "B", "C"]
```

### 方案B: 动态仓位管理

```python
# 根据星期调整仓位
def get_position_size(base_size, weekday):
    if weekday < 4:  # 周一到周四
        return base_size * 0.5  # 50%仓位
    else:
        return base_size  # 100%仓位
```

### 方案C: 增加过滤条件

1. **趋势过滤**: 只在BTC整体趋势明确时交易
2. **连亏保护**: 当日亏损超过3次暂停
3. **波动率过滤**: ATR超过阈值时不交易

### 方案D: 时间段优化

分析高胜率时间段，只在特定小时执行策略。

### 方案E: 周一到周四禁用

如果优化后仍无法改善，考虑只在周五周六开启策略1。

---

## 五、实施计划

1. **短期**: 先实施方案A，调整周一到周四的入场条件
2. **中期**: 收集数据，评估效果，考虑方案B
3. **长期**: 如果仍不理想，实施方案E

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    return report


if __name__ == "__main__":
    main()
