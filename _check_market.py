"""查询当前BTC市场和手动买入的持仓"""
from dotenv import load_dotenv
load_dotenv()

from src.gamma_client import GammaClient
from src.database import Database

# 1. 获取当前BTC 15分钟市场
print("=== 当前BTC 15分钟市场 ===")
gc = GammaClient()
m = gc.get_current_15m_market('BTC')
current_tokens = set()
if m:
    tokens = gc.parse_token_ids(m)
    prices = gc.parse_prices(m)
    print(f"  问题: {m.get('question', '')[:80]}")
    print(f"  UP   token: {tokens.get('up', '')}")
    print(f"  DOWN token: {tokens.get('down', '')}")
    print(f"  UP   价格: {prices.get('up', 0):.4f}")
    print(f"  DOWN 价格: {prices.get('down', 0):.4f}")
    current_tokens.add(tokens.get('up', ''))
    current_tokens.add(tokens.get('down', ''))
else:
    print("  未找到当前市场")

# 2. 对比DB中的open订单
print("\n=== DB未平仓订单 vs 当前市场 ===")
db = Database()
rows = db.get_open_rebound_orders(coin='BTC')
current = [r for r in rows if r.token_id in current_tokens]
old = [r for r in rows if r.token_id not in current_tokens]

print(f"当前市场持仓 ({len(current)} 笔):")
for r in current:
    print(f"  ID={r.id} | {r.side} | entry={r.entry_price} | size={r.size}")

print(f"\n过去市场残留 ({len(old)} 笔，已过期):")
for r in old[:5]:
    print(f"  ID={r.id} | {r.side} | entry={r.entry_price} | token=...{r.token_id[-20:]}")
if len(old) > 5:
    print(f"  ... 另 {len(old)-5} 笔")

# 3. 如果用户手动买了，需要手动插入DB记录
print("\n=== 说明 ===")
print("如果手动购买的是 UP 或 DOWN 仓，需要手动插入DB让机器人接管止盈止损。")
print("请告知：买的是 UP 还是 DOWN？买入价格是多少？金额是多少USDC？")
