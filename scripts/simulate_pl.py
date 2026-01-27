import time
from strategies.rebound import ReboundStrategy, ReboundConfig

# Create config for strategy 3 with P&L enabled
cfg = ReboundConfig(strategy_type="3", profit_and_loss_enabled=True, simulation_mode=True)
strategy = ReboundStrategy(bot=None, config=cfg)

# Monkeypatch prices.get_current_price to return dynamic value
current_prices = {"up": 1.0, "down": 1.0}
strategy.prices.get_current_price = lambda side: current_prices.get(side, 0)

# Insert an active 'up' position (entry 1.0, size 10)
strategy._active_positions['up'] = {
    'db_id': None,
    'entry_price': 1.0,
    'size': 10,
    'entry_time': time.time(),
    '_tp_eligible': False,
}
strategy._position_peak_price['up'] = 1.0

print('\n--- Start simulated P&L test ---')
print('Entry=1.0, take_profit_base=%.2f, take_profit_reduce_loss=%.2f' % (cfg.take_profit_base, cfg.take_profit_reduce_loss))

# Step 1: price rises above take_profit_base (e.g., to 1.6 -> +60%)
current_prices['up'] = 1.6
print('\n[Step 1] Price rises to', current_prices['up'])
strategy._evaluate_positions_for_profit_and_loss()
print('Position state after step1:', strategy._active_positions.get('up'))

# Step 2: price pulls back from peak by 10% (peak 1.6 -> pullback to 1.44)
current_prices['up'] = 1.44
print('\n[Step 2] Price pulls back to', current_prices['up'])
strategy._evaluate_positions_for_profit_and_loss()
print('Position state after step2:', strategy._active_positions.get('up'))

# Step 3: simulate stage C stop-loss scenario on a new position
strategy._active_positions.clear()
strategy._position_peak_price.clear()
strategy._active_positions['down'] = {
    'db_id': None,
    'entry_price': 1.0,
    'size': 10,
    'entry_time': time.time() - 1200,  # long-lived to simulate segment C timing (not strictly used)
    '_tp_eligible': False,
}
strategy._position_peak_price['down'] = 1.0

# Force get_current_segment to return 'C' temporarily
orig_get_segment = strategy.get_current_segment
strategy.get_current_segment = lambda: 'C'

# Price drops enough to trigger stop-loss stage C (e.g., to 0.75 => 25% loss)
current_prices['down'] = 0.75
print('\n[Step 3] Stage C loss scenario, price down to', current_prices['down'])
strategy._evaluate_positions_for_profit_and_loss()
print('Position state after step3:', strategy._active_positions.get('down'))

# restore
strategy.get_current_segment = orig_get_segment
print('\n--- End simulated P&L test ---')
