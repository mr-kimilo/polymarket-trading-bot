"""检查当前持仓和活跃市场"""
import asyncio
import json
from dotenv import load_dotenv
load_dotenv()

from src.bot import TradingBot
from src.config import Config
from src.database import Database


async def main():
    config = Config.load_with_env('config.yaml')
    bot = TradingBot(config=config)

    # 1. 查询CLOB API当前挂单
    print("=== Polymarket 账户当前挂单 (CLOB API) ===")
    try:
        bot._init_clients()
        orders = bot.clob_client.get_open_orders()
        if not orders:
            print("  (无挂单)")
        else:
            for o in orders:
                print(json.dumps(o, indent=2))
    except Exception as e:
        print(f"  API查询失败: {e}")

    # 2. 查当前BTC市场的token IDs (通过数据库最新记录探测)
    print("\n=== 当前BTC 15分钟市场 Token IDs ===")
    try:
        import aiohttp
        # 用CLOB的market endpoint直接搜索
        url = "https://clob.polymarket.com/markets?next_cursor=&limit=100"
        # 改用 gamma-api 但走 btc 关键字过滤
        gamma_url = "https://gamma-api.polymarket.com/markets?tag_slug=crypto&active=true&closed=false&limit=20&keyword=BTC+15+minutes"
        active_tokens = set()
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(gamma_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
            for m in data:
                q = m.get('question', '')
                for t in m.get('tokens', []):
                    tid = t.get('token_id', '')
                    outcome = t.get('outcome', '')
                    print(f"  {outcome:5s} | {tid}")
                    active_tokens.add(tid)
        print(f"\n  共 {len(active_tokens)} 个活跃token")
    except Exception as e:
        print(f"  市场查询失败: {e}")
        # 回退：用DB中最新的token推断
        active_tokens = set()
        print("  回退到DB最新记录...")

    # 3. 对比DB中的open订单，找出当前市场的持仓
    print("\n=== DB未平仓订单 vs 当前市场 ===")
    db = Database()
    rows = db.get_open_rebound_orders(coin='BTC')
    current = [r for r in rows if r.token_id in active_tokens]
    old = [r for r in rows if r.token_id not in active_tokens]
    print(f"  当前市场持仓: {len(current)} 笔")
    for r in current:
        print(f"    ID={r.id} | {r.side} | entry={r.entry_price} | size={r.size}")
    print(f"  过期市场残留: {len(old)} 笔 (已过期)")


asyncio.run(main())
