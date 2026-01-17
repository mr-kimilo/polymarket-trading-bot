"""Test order signing using both official SDK and our implementation."""
import os
import json
from dotenv import load_dotenv
load_dotenv()

# Our implementation
from src.bot import TradingBot
from src.config import Config
from src.signer import Order

private_key = os.environ.get('POLY_PRIVATE_KEY')
safe_address = os.environ.get('POLY_SAFE_ADDRESS')

# Use a valid token_id from active market
token_id = "101676997363687199724245607342877036148401850938023978421879460310389391082353"
price = 0.01  # Very low price so order won't be filled
size = 5.0  # Use size >= 5 to pass validation

print("=" * 60)
print("Testing Order Placement with Our Implementation")
print("=" * 60)

# Our implementation
config = Config.load("config.yaml") if os.path.exists("config.yaml") else Config()
config.safe_address = safe_address

bot = TradingBot(config=config, private_key=private_key)

try:
    # Check if market is neg_risk
    neg_risk = bot.clob_client.get_neg_risk(token_id)
    print(f"Market neg_risk: {neg_risk}")
    
    # Create order
    order = Order(
        token_id=token_id,
        price=price,
        size=size,
        side="BUY",
        maker=safe_address,
        fee_rate_bps=0,
    )
    
    # Sign order with neg_risk parameter
    signed = bot.signer.sign_order(order, neg_risk=neg_risk)
    print("Our signed order:")
    print(json.dumps(signed, indent=2, default=str))
    
    # Try to post using our clob_client
    print("\nTrying to post order with our implementation...")
    result = bot.clob_client.post_order(signed, "GTC")
    print(f"SUCCESS! Result: {result}")
except Exception as e:
    print(f"Our implementation Error: {e}")
    import traceback
    traceback.print_exc()
