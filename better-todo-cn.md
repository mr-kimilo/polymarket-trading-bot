# 更好的待办：Polymarket 机器人 — 高影响、低 Token 计划（2026-01-11）

本计划将原始 TODO 重构为简洁、面向代码的任务，包含明确的输入、输出、验收标准、命令与关键提醒，便于 AI 快速实现并减少 token 浪费。

## 指导原则
- 优先进行小而精确的修改，避免大规模重构。
- 明确指出要修改的确切文件和函数。
- 每次修改后进行短跑验证。
- 避免不必要的重启；验证 WebSocket 状态转换。

---

## 阶段 1 — 环境准备
- **目标：** 环境可运行；能快速启动但不进行交易。
- **输入：** `.env`、`config.yaml`、Python 虚拟环境、`requirements.txt`。
- **操作：**
  - 安装依赖。
  - 如需，确保 API 密钥配置妥当。
- **命令：**
  ```powershell
  cd D:\coin\polymarket-trading-bot
  python -m venv .venv; .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- **验收：** 能运行 `orderbook.py` 且无崩溃。

---

## 阶段 2 — TUI 数据与 BTC 价格
- **目标：** 稳定的界面，按分钟显示 UP/DOWN 与 BTC 起始/当前/变动。
- **文件：** `apps/orderbook_tui.py`
- **关键提醒：**
  - 使用 `rich.Live` 避免界面跳动；复用容器、原位更新。
  - BTC 价格：优先 CoinGecko，备选 CoinCap 与 Binance；刷新间隔约 5 秒。
- **验收：**
  - 显示：BTC 起始/当前价格、每分钟的 UP/DOWN 百分比、BTC Δ。
  - 布局稳定，不抖动；缓冲区有上限。

---

## 阶段 3 — 市场切换（15 分钟）
- **目标：** 周期切换时数据无缝衔接。
- **文件：** `lib/market_manager.py`、`src/websocket_client.py`
- **修改：**
  - 切换时：先 `await unsubscribe(old_tokens)` → 短延迟 → `subscribe(new_tokens, replace=True)`。
  - 订阅消息格式：
    - 初始连接：`{ "assets_ids": [...], "type": "market" }`
    - 随后切换：`{ "assets_ids": [...], "operation": "subscribe" }`
- **关键提醒：**
  - 不要仅依赖 `replace=True`；先显式取消订阅。
  - 维护 `initial_subscribe_done` 标志；断开连接时重置该标志。
- **验收：** 在 slug 变更后 10 秒内收到新盘口更新；空盘口不应持续超过 30 秒。

---

## 阶段 4 — 持久化（每 15 分钟一个 JSON）
- **目标：** 将每个 15 分钟周期保存为 `files/` 下的 `YYYY-MM-DD-HH-MM.json` 文件。
- **文件：** `apps/orderbook_tui.py`
- **数据结构：**
  - `coin`、`market_slug`、`period_start`、`btc_price_start`、`btc_price_end`
  - `up_start`、`down_start`
  - `minutes[]`：`minute_index`、`time`、`timestamp`、`up`、`up_pct`、`down`、`down_pct`、`btc_start`、`btc_end`、`btc_delta`
- **验收：** 周期结束时生成文件，包含最多 15 条分钟记录。

---

## 阶段 5 — 静默模式服务
- **目标：** 长期低资源运行的数据采集。
- **文件：** `apps/orderbook_tui.py`、`orderbook.py`、`start_silent_monitor.bat`、`start_background_monitors.bat`
- **修改：**
  - 添加 `--silent` 参数以抑制 UI，仅保存 JSON。
  - 静默模式下每分钟打印一行简短状态。
  - 提供启动用的 BAT 脚本。
- **命令：**
  ```powershell
  python orderbook.py --coin BTC --silent
  start_silent_monitor.bat
  start_background_monitors.bat
  ```
- **验收：** 打印状态行；JSON 文件持续增长；CPU 使用低。

---

## 阶段 6 — 清理
- **目标：** 删除过时测试脚本，保持仓库整洁。
- **操作：**
  - 验证无误后移除 `test_*` 脚本和多余工具。
- **验收：** 无遗留实验性文件。

---

## 快速代码提示
- WebSocket 订阅/取消订阅：
  - `src/websocket_client.py` → `subscribe()`、`subscribe_more()`、`unsubscribe()`
  - 维护 `self._initial_subscribe_done`；断开连接时设为 `False`。
- 市场切换循环：
  - `lib/market_manager.py` → `_market_check_loop()` 负责 slug 变更、取消订阅、重新订阅。
- TUI 分钟聚合与文件保存：
  - `apps/orderbook_tui.py` → `_record_minute_snapshot()`、`_save_period_data()`

---

## 风险点与关键检查
- **消息格式不匹配：** 初始订阅与后续订阅格式不同，格式错误会导致空盘口。
- **未显式取消订阅：** 可能导致旧订阅残留，新数据无法到达。
- **重连处理：** 断连后需重置 `initial_subscribe_done`。
- **速率限制：** BTC 价格 API 可能被限流；使用备用 API 并设短超时。
- **UI 抖动：** 避免每次刷新重建完整布局，应就地更新。

---

## 最小测试流程（Windows）
```powershell
# 1) 正常运行（UI）
python orderbook.py --coin BTC

# 2) 静默采集
python orderbook.py --coin BTC --silent

# 3) 验证文件保存
Get-ChildItem files\ *.json | Select-Object -First 5
```

---

## 验收矩阵（要点）
- **环境：** 无崩溃，依赖安装完成。
- **TUI：** 界面稳定，每分钟表含 BTC Δ。
- **切换：** 新 slug → ≤10s 收到数据，空盘不超过 30s。
- **持久化：** 每周期生成 JSON，含完整分钟记录。
- **静默：** 少量打印，持续运行且 CPU 低。
- **清理：** 无 `test_*` 残留。

---

## 向 AI 实现时的提示
- 提供确切的文件/函数目标和代码片段。
- 给出 1-2 条验收要点。
- 包含一条简短的验证命令。
- 若与切换相关：明确初始与后续的订阅负载格式。
- 若与价格相关：列出备用 API 与刷新间隔。
