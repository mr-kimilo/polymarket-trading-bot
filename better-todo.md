# Better TODO: Polymarket Bot — High-Impact, Low-Token Plan (2026-01-11)

This plan restructures the original TODO into concise, code-oriented tasks with clear inputs, outputs, acceptance criteria, commands, and key reminders to help AI implement quickly without wasting tokens.

## Guiding Principles
- Prefer small, surgical edits over broad refactors.
- Always cite exact files and functions to change.
- Validate after each change with a short run.
- Avoid redundant restarts; verify WebSocket state transitions.

---

## Phase 1 — Setup & Readiness
- **Goal:** Environment ready; quick run without trading.
- **Inputs:** `.env`, `config.yaml`, Python venv, `requirements.txt`.
- **Actions:**
  - Install dependencies.
  - Ensure API keys present if needed.
- **Commands:**
  ```powershell
  cd D:\coin\polymarket-trading-bot
  python -m venv .venv; .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- **Accept:** Can run `orderbook.py` without crashes.

---

## Phase 2 — TUI Data & BTC Price
- **Goal:** Stable screen, minute-by-minute UP/DOWN with BTC start/current/delta.
- **Files:** `apps/orderbook_tui.py`
- **Key Reminders:**
  - Use `rich.Live` to avoid screen jump; reuse containers, update in place.
  - BTC price: CoinGecko primary, fallbacks CoinCap & Binance; refresh ~5s.
- **Accept:**
  - Shows: start/current BTC, per-minute UP/DOWN %, BTC Δ.
  - No jittery layout; buffers capped.

---

## Phase 3 — Market Switching (15-min)
- **Goal:** Seamless data across period changes.
- **Files:** `lib/market_manager.py`, `src/websocket_client.py`
- **Changes:**
  - On switch: `await unsubscribe(old_tokens)` → small delay → `subscribe(new_tokens, replace=True)`.
  - Subscription message formats:
    - Initial connect: `{ "assets_ids": [...], "type": "market" }`
    - Subsequent switches: `{ "assets_ids": [...], "operation": "subscribe" }`
- **Key Reminders:**
  - Do not only rely on `replace=True`; explicitly unsubscribe first.
  - Track an `initial_subscribe_done` flag; reset on disconnect.
- **Accept:** Within 10s of slug change, new book updates arrive; no empty books persist >30s.

---

## Phase 4 — Persistence (JSON per 15 min)
- **Goal:** Save each 15-min period to `files/` as `YYYY-MM-DD-HH-MM.json`.
- **Files:** `apps/orderbook_tui.py`
- **Schema:**
  - `coin`, `market_slug`, `period_start`, `btc_price_start`, `btc_price_end`
  - `up_start`, `down_start`
  - `minutes[]`: `minute_index`, `time`, `timestamp`, `up`, `up_pct`, `down`, `down_pct`, `btc_start`, `btc_end`, `btc_delta`
- **Accept:** A file is created at period end with populated minutes (up to 15).

---

## Phase 5 — Silent Mode Service
- **Goal:** Long-run data capture with minimal resource usage.
- **Files:** `apps/orderbook_tui.py`, `orderbook.py`, `start_silent_monitor.bat`, `start_background_monitors.bat`
- **Changes:**
  - Add `--silent` argument that suppresses UI; only saves JSON.
  - In silent mode, print a tiny status line once per minute.
  - Provide BAT scripts for startup.
- **Commands:**
  ```powershell
  python orderbook.py --coin BTC --silent
  start_silent_monitor.bat
  start_background_monitors.bat
  ```
- **Accept:** Status lines print; JSON files accumulate; CPU stays low.

---

## Phase 6 — Cleanup
- **Goal:** Remove obsolete tests/scripts; keep repo tidy.
- **Actions:**
  - Remove `test_*` scripts and redundant tools once verified.
- **Accept:** No leftover experimental files.

---

## Quick Code Pointers
- WebSocket subscribe/unsubscribe:
  - `src/websocket_client.py` → `subscribe()`, `subscribe_more()`, `unsubscribe()`
  - Maintain `self._initial_subscribe_done`; set to `False` on disconnect.
- Market switch loop:
  - `lib/market_manager.py` → `_market_check_loop()` handles slug change, unsubscribe, subscribe.
- TUI minute aggregation & file save:
  - `apps/orderbook_tui.py` → `_record_minute_snapshot()`, `_save_period_data()`

---

## Pitfalls & Critical Checks
- **Message format mismatch:** Initial vs subsequent subscribe payloads; wrong format yields empty books.
- **No explicit unsubscribe:** Causes lingering old subscriptions; new data may not arrive.
- **Reconnect handling:** Reset `initial_subscribe_done` on disconnect.
- **Rate limits:** BTC price APIs may throttle; use fallbacks & short timeouts.
- **UI flicker:** Avoid rebuilding full layout every tick; update in place.

---

## Minimal Test Flow (Windows)
```powershell
# 1) Normal run (UI)
python orderbook.py --coin BTC

# 2) Silent collection
python orderbook.py --coin BTC --silent

# 3) Verify files saved
Get-ChildItem files\ *.json | Select-Object -First 5
```

---

## Acceptance Matrix (One-Liners)
- **Setup:** Runs without crash; dependencies installed.
- **TUI:** Stable screen; minute table with BTC deltas.
- **Switching:** New slug → data within ≤10s; no empties >30s.
- **Persistence:** One JSON per period with full minute records.
- **Silent:** Minimal prints; sustained runs; low CPU.
- **Cleanup:** No test_* clutter remains.

---

## When Asking AI to Implement
- Give exact file/function targets and snippets.
- Provide 1-2 acceptance bullets.
- Include one short command to validate.
- If switch-related: specify initial vs subsequent subscribe payload.
- If price-related: list API fallbacks and intervals.
