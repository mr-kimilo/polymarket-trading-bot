# Copilot Instructions

A beginner-friendly Python trading bot for Polymarket. Uses gasless transactions via Builder Program, EIP-712 signing, and WebSocket for real-time data.

## Architecture

```
src/           # Core library (bot, client, signer, config, websocket_client, database)
strategies/    # Trading strategies (base.py defines BaseStrategy pattern)
lib/           # Support components (MarketManager, PriceTracker, PositionManager)
apps/          # Entry points for running strategies (run_rebound.py, run_flash_crash.py)
tests/         # Unit tests (tests/) and integration tests (tests/integration/)
scripts/       # Utility scripts and API server
```

### Key Module Responsibilities

| Module | Purpose |
|--------|---------|
| `src/bot.py` | `TradingBot` - main async trading interface |
| `src/client.py` | `ClobClient`, `RelayerClient` - API communication with HMAC auth |
| `src/signer.py` | EIP-712 order signing (signature_type=2 for Gnosis Safe) |
| `src/websocket_client.py` | Real-time orderbook via WebSocket |
| `src/database.py` | PostgreSQL operations with `ReboundOrder` dataclass |
| `lib/market_manager.py` | 15-minute market discovery via GammaClient |
| `strategies/base.py` | `BaseStrategy` - inherit this for new strategies |

### Data Flow

1. `TradingBot.place_order()` creates an `Order` dataclass
2. `OrderSigner.sign_order()` produces EIP-712 signature
3. `ClobClient.post_order()` submits with Builder HMAC headers
4. `RelayerClient` handles gasless Safe deployment if needed

## Development Workflow

1. **Consult instructions**: List which `./instructions/*.instructions.md` files guide your implementation
2. **TDD**: Write tests first - see `./instructions/unit-and-integration-tests.instructions.md`
3. **Run tests**: `pytest` or `pytest --cov` before committing
4. **Lint**: Fix ruff/black/mypy warnings

```bash
pytest tests/ -v                  # Run all tests
pytest tests/test_bot.py -v       # Single test file
python scripts/full_test.py       # Full integration test
```

## Key Patterns

### Async Trading Methods

All bot methods are async. Use `asyncio.run()` at entry points:

```python
from src import create_bot_from_env

async def main():
    bot = create_bot_from_env()
    result = await bot.place_order(token_id="...", price=0.65, size=10.0, side="BUY")

asyncio.run(main())
```

### Strategy Development

Inherit from `BaseStrategy` in `strategies/base.py`. Provides MarketManager, PriceTracker, PositionManager:

```python
from strategies.base import BaseStrategy, StrategyConfig

class MyStrategy(BaseStrategy):
    async def on_book_update(self, snapshot: OrderbookSnapshot):
        if snapshot.mid_price < 0.30:
            await self.buy(side="up", size=self.config.size)
```

### Configuration Precedence

Environment vars > `config.yaml` > defaults. Load via:

```python
config = Config.from_env()   # From POLY_* env vars
config = Config.load("config.yaml")  # From YAML file
```

### Dataclasses for Data Structures

Use `@dataclass` throughout (not Pydantic). See `src/config.py`, `src/signer.py`, `src/database.py`.

### WebSocket Orderbook

Use callbacks with `@manager.on_book_update` decorator:

```python
manager = MarketManager(coin="BTC")

@manager.on_book_update
async def handle_book(snapshot: OrderbookSnapshot):
    print(f"Mid: {snapshot.mid_price}, Bid: {snapshot.best_bid}")
```

## External Integrations

- **CLOB API**: `https://clob.polymarket.com` - Order submission
- **Relayer API**: `https://relayer-v2.polymarket.com` - Gasless transactions
- **GammaClient**: 15-minute market discovery (BTC/ETH/SOL/XRP Up/Down markets)
- **PostgreSQL**: Order tracking via `src/database.py`

## Python Guidelines

- Type hints required for all function signatures
- PEP 8 enforced by black/ruff
- Use dataclasses for data structures
- Prefer composition over inheritance
- Context managers for resources
- English for all documentation and code comments
