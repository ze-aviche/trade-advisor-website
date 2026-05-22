# BrownBot — Architecture & Pipeline

BrownBot is a fully autonomous trading bot. It finds its own candidates, gates entries through a risk manager, and exits positions without manual intervention. It operates independently of the Entry Bot and Exit Bot — never modify those when working on BrownBot.

Gated to the **Yogi** subscription tier.

---

## Runtime

Three daemon threads are started together on `POST /api/brown-bot/start` and stopped on `POST /api/brown-bot/stop`:

| Thread | Function | Interval |
|--------|----------|----------|
| `BrownBotScanner` | `_brown_bot_scanner_loop()` → `_brown_bot_scan_and_enter()` | 30 s |
| `BrownBotExits` | `_brown_bot_exit_loop()` → `_brown_bot_check_exits()` | 2 s (swing-specific every 60 s) |
| `BrownBotOrderMonitor` | `_brown_order_monitor_loop()` | 2 s |

`_brown_bot_running` is the only shutdown signal — all three loops poll it and exit cleanly.

On `start_brown_bot()` the bot restores any `status='open'` positions from `brown_positions` (DB), cross-references with the broker, and only keeps positions the broker actually holds. See **Restart & Recovery** for the full reconciliation flow.

---

## Order Management Flow

This is the core lifecycle that separates "order submitted" from "fill confirmed". No DB writes happen until the broker confirms a fill.

Log channels:
- **UI log** — visible in the BrownBot Logs panel (WARNING/INFO via `_add_brown_log`)
- **Server log** — server stdout only (DEBUG via `app_logger.debug`; filter with `grep '\[BrownBot'`)
 

 On Render (production): the logs/ folder is inside the container filesystem — it exists but is wiped on each deploy. If you want to read it live, SSH into the Render shell and run:


tail -f logs/gap_trade_backend_all.log | grep '\[BrownBot'
Locally (Docker): same path inside the container. To stream it from the host:


docker exec -it <container> tail -f logs/gap_trade_backend_all.log | grep '\[BrownBot'

docker exec -it gap-trade-bot-web-1 tail -f logs/gap_trade_backend_all.log in local


Important caveat: the file handler is at DEBUG level, so all app_logger.debug(...) lines (the [BrownBot ...] order management lines) are written to the file. The console/Render web log only shows INFO and above — so the file is the only place you'll see the per-poll monitor details.



```
1. Scanner identifies candidate
         │
         ▼
2. _brown_enter_position()
   · pre-flight buying power check
   · broker.place_order(BUY, MARKET)

   SERVER  [BrownBot:Alpaca] BUY {qty} {SYM} → order_id={id} status={status}
   UI      {SYM}: entry started — approx ${price}, type={day|swing}
   (on immediate rejection)
   UI  ⚠   {SYM} order {id…} rejected immediately — not entering

   · immediate fill check via broker.get_order()
   SERVER  [BrownBot entry] immediate status check {SYM} order={id…}
             status={status} filled_avg_price={x} filled_qty={n}

         ├─ Fast path — fill confirmed right away:
         │   SERVER  [BrownBot entry] {SYM} position_id=… entry_confirmed=True
         │             avg_entry_price={x} target={t} stop={s}
         │   SERVER  [BrownBot entry] {SYM} position saved to DB (status=open)
         │   SERVER  [BrownBot entry] {SYM} brown_orders row written … status=filled
         │   (fill price differs from scanner approx)
         │   UI      {SYM} fill confirmed ${fill} (scanner approx was ${approx})
         │   UI      ENTERED {DAY|SWING} {SYM} ~${price} | target ${t} (+x%) | stop ${s} (-x%)
         │
         └─ Async path — still pending:
             SERVER  [BrownBot entry] {SYM} order {id…} not yet filled — deferring to monitor loop
             SERVER  [BrownBot entry] {SYM} position saved to DB (status=open)
             SERVER  [BrownBot entry] {SYM} brown_orders row written … status=pending
             UI      {SYM} BUY pending broker confirmation — DB write deferred
             UI      ENTERED {DAY|SWING} {SYM} ~${price} | target ${t} | stop ${s}
                      │
                      ▼
3. _brown_order_monitor_loop() polls every 2 s
   SERVER  [BrownBot monitor] polling {N} pending order(s): [{SYM}/entry …]
   SERVER  [BrownBot monitor] {SYM} entry order={id…} status={status} age={n}s
             filled_avg_price={x} filled_qty={n}
         │
         ├─ FILLED → _brown_monitor_finalize_entry()
         │   SERVER  [BrownBot monitor] {SYM} FILLED → calling finalize_entry
         │   SERVER  [BrownBot finalize_entry] {SYM} order={id…} fill_price={x} fill_qty={n}
         │   SERVER  [BrownBot finalize_entry] {SYM} memory updated —
         │             avg_entry={x} target={t} stop={s}
         │   SERVER  [BrownBot finalize_entry] {SYM} brown_orders updated … status=filled
         │   SERVER  [BrownBot finalize_entry] {SYM} brown_positions.avg_entry_price updated → {x}
         │   SERVER  [BrownBot finalize_entry] {SYM} save_brown_position done
         │   UI      {SYM} BUY confirmed by broker: {n} @ ${fill}
         │
         ├─ PARTIAL → no action, re-polls next cycle (market orders fill quickly)
         │
         ├─ CANCELLED / REJECTED
         │   UI  ⚠   {SYM} entry/exit order {id…} CANCELLED/REJECTED — no DB write
         │   UI  ⚠   {SYM}: phantom entry removed — order was not filled
         │
         └─ Timeout (>60 s, still not FILLED)
               UI  ⚠  {SYM} entry order {id…} stuck {n}s — checking fill before cancel
               │
               ├─ fill_qty > 0 (partial fill at timeout)
               │   UI  ⚠  {SYM}: entry order partially filled ({x}/{n} shares) at
               │             timeout — cancelling remainder, accepting partial
               │   → _brown_monitor_finalize_entry() at actual fill_qty  (logs as above)
               │
               └─ fill_qty == 0 (no fill)
                   UI  ⚠  {SYM}: entry timed out and not filled — position removed

4. Exit condition met (profit target / stop / EOD / max hold / earnings)
         │
         ▼
5. _brown_close_position()
   SERVER  [BrownBot close_position] {SYM} position_id=… reason=… qty=…
             current_price=… avg_entry_price=…
   (broker position check)
   SERVER  [BrownBot close_position] {SYM} broker confirms position:
             qty=… avg_entry=… unrealized=…
   (if broker has no position — aborts without selling)
   UI  ⚠   No open position for {SYM} in broker — removing from tracking (no sell placed)

   · broker.close_position(symbol) → market SELL
   SERVER  [BrownBot:Alpaca] SELL {SYM} → order_id={id}
   SERVER  [BrownBot close_position] {SYM} queued to pending_orders
             order={id…} avg_entry_in_meta={x} approx_exit={price}
   SERVER  [BrownBot close_position] {SYM} removed from active_positions,
             monitor will call finalize_exit

6. _brown_order_monitor_loop() polls the SELL order every 2 s
   SERVER  [BrownBot monitor] polling {N} pending order(s): [{SYM}/exit …]
   SERVER  [BrownBot monitor] {SYM} exit order={id…} status={status} age={n}s
         │
         ├─ PARTIAL → wait; polls again next cycle
         │
         ├─ FILLED → _brown_monitor_finalize_exit()
         │   SERVER  [BrownBot monitor] {SYM} FILLED → calling finalize_exit
         │   SERVER  [BrownBot finalize_exit] {SYM} order={id…} fill_price={x}
         │             fill_qty={n} reason={r} avg_entry={e} entry_price_in_meta={m}
         │   SERVER  [BrownBot finalize_exit] {SYM} P&L calc:
         │             ({fill} - {avg_entry}) × {qty} = {pnl} ({pct}%)
         │   SERVER  [BrownBot finalize_exit] {SYM} brown_orders updated … status=filled
         │   SERVER  [BrownBot finalize_exit] {SYM} brown_positions status → closed
         │             realized_pnl={pnl} realized_pnl_pct={pct}
         │   SERVER  [BrownBot finalize_exit] {SYM} trades row written pnl={pnl}
         │   UI      EXITED {DAY|SWING} {SYM} [{reason}]
         │             entry ${avg} → exit ${fill} × {qty} | P&L +/-${pnl}
         │
         ├─ CANCELLED / REJECTED
         │   UI  ⚠   {SYM} exit {id…} CANCELLED/REJECTED — no DB write
         │   UI  ⚠   {SYM}: exit order rejected — position restored for retry
         │
         └─ Timeout (>60 s)
               ├─ fill_qty > 0 (partial exit at timeout)
               │   UI  ⚠  {SYM}: exit order partially filled ({x}/{n} shares) at
               │             timeout — cancelling remainder, accepting partial
               │   → _brown_monitor_finalize_exit() at fill_qty  (logs as above)
               │   UI  ⚠  {SYM}: {remaining} shares restored to active tracking
               │             after partial exit — exit loop will retry
               │
               └─ fill_qty == 0 (no fill)
                   UI  ⚠  {SYM}: exit order timed out — position restored,
                             exit loop will retry

7. P&L is now in brown_positions.realized_pnl (permanent record)
   and in trades.pnl (feed for the Positions / P&L tabs)
```

### In-memory state during a trade

| Dict / Set | Purpose |
|------------|---------|
| `_brown_bot_active_positions` | All open positions (removed when sell submitted) |
| `_brown_pending_orders` | All orders waiting for broker fill confirmation |
| `_brown_closing_positions` | Set of position_ids currently being sent to the broker; prevents double-exit |
| `_brown_entry_counts` | Fill-confirmed entry count per symbol (survives restart via DB) |
| `_brown_attempted_symbols` | Every symbol attempted this session — no retries for fills OR rejections |

### Source of truth per field

| Field | Authoritative source |
|-------|---------------------|
| `avg_entry_price` | `brown_positions.avg_entry_price` column (written by `update_brown_position_entry` on fill confirm) |
| `realized_pnl` | `brown_positions.realized_pnl` (written by `close_brown_position` on exit fill) |
| `unrealized_pnl` | `brown_positions.unrealized_pnl` (persisted every 2 s by exit loop) |
| Daily realized P&L | `get_brown_daily_realized_pnl()` → `SUM(realized_pnl) FROM brown_positions WHERE status='closed' AND trade_date=today` |
| Order log | `brown_orders` table — immutable per-order row, updated once on fill |

---

## Entry Pipeline

### Day Trades — Gap-Up Scanner

Runs every 30 seconds inside `_brown_bot_scan_and_enter()`.

```
real_time_gap_ups  (in-memory, refreshed by gap-up monitor thread)
      │
      ▼
Config filters
· min_gap_pct, min_price, max_price, min_volume_m
      │
      ▼
Time gate check  (09:35–10:30 ET by default, toggleable in config)
      │
      ▼
Skip if symbol in _brown_attempted_symbols
(locks out any symbol that was attempted this session — fills AND rejections)
      │
      ▼
_check_day_entry_signal(symbol)
· Fetches 1-min bars from 09:30 ET  →  Alpaca StockBarsRequest
                                    →  Polygon /v2/aggs fallback
· Computes VWAP from session open
· Checks (each independently toggled in Day Filters config):
    VWAP     — close ≥ session VWAP
    CANDLE   — last 1-min candle bullish (close > open)
    EXT      — price not extended beyond max_extension_pct from gap price
    VOL      — entry bar volume ≥ 1.5× 10-bar average
· Returns (enter: bool, checks: list, reason: str)
· Pass/fail badges shown live in Candidates UI
      │
      ▼
RiskManager.can_enter(symbol, 'day')
· max_concurrent_day slot check
· max_daily_loss circuit breaker
      │
      ▼
_brown_enter_position(symbol, 'day')
· Pre-flight buying power check  →  skips (no order sent) if account BP < price × qty
· Marks symbol in _brown_attempted_symbols BEFORE the order
· Places market BUY via broker.place_order()
· Saves position to brown_positions (DB) immediately
· Writes entry row to brown_orders (DB)
· Defers trade record to monitor thread (written only after fill confirmed)
```

---

### Swing Trades — Daily AI Hot Picks

Runs every 30 seconds inside the same `_brown_bot_scan_and_enter()` call, after the day trade block.

The swing candidate source is the **Swing tab's daily AI ranking** — the same picks the user sees in the Hot Swing Picks panel. BrownBot reads Grade A/B Bullish picks directly; it does not run its own separate swing signal check.

#### How the swing hot picks are built

This pipeline runs on-demand (when the Swing tab is opened) and automatically at **8 PM ET every trading day** via the `SwingPicksEOD` scheduler thread:

```
Polygon gainers snapshot  ──┐
Polygon losers snapshot   ──┤  (parallel fetch)
real_time_gap_ups (memory)──┤
Full Polygon all-tickers    ┘  volume-surge scan
      │
      ▼
Ticker quality filter  (always on, zero API cost)
· Pure alpha 1–5 chars only  (rejects dots, slashes, digits)
· Preferred stock regex  →  blocks USBPR, WFCPR, KBSPRA, JPMPRA etc.
      │
      ▼
Liquidity floor
· Price ≥ $10
· Daily dollar volume ≥ $3M  (price × volume)
      │
      ▼
Intraday price structure filter  (snapshot fields, zero API cost)
· Close position in range ≥ 40%  →  close not near day low (sell-off candle rejected)
· Close ≥ VWAP × 0.985           →  price held above session average
· Change ≥ −3%  (vol-surge path)  →  distribution volume rejected
      │
      ▼
Market cap filter  (1 Polygon reference batch call)
· Drops stocks with confirmed market cap < $300M  (micro-caps)
· Fail-open: tickers with no reference data are kept
      │
      ▼
SMA-10 trend filter  (parallel Polygon daily bars, ~15 bars per ticker)
· Computes 10-day SMA for every candidate
· Drops stocks whose close is > 3% below SMA-10  →  broken pattern
      │
      ▼
Claude Haiku ranking
· Sees: ticker, price, change%, volume, day range, close position,
        SMA-10, vol-surge ratio, market cap, source tag
· Returns 6–8 best picks, each with:
    grade       A | B | C
    bias        Bullish | Bearish
    reason      one sentence
    entry_zone  price or range
    watch_for   key confirmation condition
    risk        stop / invalidation level
      │
      ▼
Persisted to DB  →  swing_daily_picks table  (date PRIMARY KEY)
Warmed into      →  _daily_picks_cache[session_date]

EOD scheduler re-runs at 8 PM ET daily with final market data.
Startup catch-up: if server restarts after 4 PM ET and today's row
is missing from DB, runs immediately on boot.
```

#### BrownBot reading the picks

Every 30-second scan:

```
_daily_picks_cache[session_date]   (memory, fastest)
      │  miss
      ▼
db_manager.get_swing_picks(session_date)   (DB, survives restarts)
      │  warms memory cache on hit
      ▼
Filter: grade in (A, B)  AND  bias == Bullish
      │
      ▼
Skip if: symbol already in open position
         symbol in _brown_attempted_symbols  (fills + rejected/skipped — no retry)
      │
      ▼
RiskManager.can_enter(symbol, 'swing')
· max_concurrent_swing slot check
· max_daily_loss circuit breaker
      │
      ▼
_brown_get_current_price(symbol)   →  live broker quote
      │
      ▼
_brown_enter_position(symbol, 'swing')
· Pre-flight buying power check  →  skips if BP insufficient
· Places market BUY
· Sets profit_target and stop_loss from live price + config pct
· Saves position to brown_positions (DB) immediately
· Writes entry row to brown_orders (DB)
· Defers trade record to monitor thread
```

#### Swing Candidates UI

The Swing Trade Candidates panel in the UI shows all Grade A/B Bullish picks with a status badge derived from runtime state:

| Status | Meaning |
|--------|---------|
| **Active** | Position currently open in `_brown_bot_active_positions` |
| **Entered Today** | Fill confirmed (`_brown_entry_counts` has the symbol) |
| **Skipped** | Attempted but rejected/BP-insufficient — will not be retried this session |
| **Eligible** | No attempt yet; bot may enter on the next scan |

---

## Exit Pipeline

Runs every 2 seconds. Swing-specific checks (hold days, earnings) run every 60 seconds.

```
For each position in _brown_bot_active_positions:
      │
      ▼
_brown_get_current_price(symbol)
→  broker.get_current_price()  →  live last-trade price
      │
      ▼
Update unrealized_pnl in memory (shown live in UI)
update_brown_position_unrealized() persists to DB every 2 s:
  · brown_positions.current_price
  · brown_positions.unrealized_pnl
  · brown_positions.unrealized_pnl_pct
      │
      ▼
Breakeven stop check
· Once price reaches breakeven_trigger_pct% of entry→target range,
  move stop to entry price
· Sets _at_breakeven flag  →  shown as "BE" badge in UI
      │
      ▼
Exit conditions (checked in order):

  1. Profit target    current_price ≥ profit_target
  2. Stop loss        current_price ≤ stop_loss  (or breakeven stop)
  3. EOD flatten      day trades only — at day_eod_exit_time ET
  4. Max hold days    swing trades only — entry_date + swing_max_hold_days
  5. Earnings         swing trades only — queries Nasdaq earnings calendar
                      exits N days before confirmed earnings date
      │
      ▼
_brown_close_position(position_id, exit_reason)
· _brown_closing_positions guard  →  prevents double-exit if two loop ticks overlap
· broker.get_position(symbol)     →  confirms broker holds position before selling
· broker.close_position(symbol)   →  market SELL (cannot accidentally short)
· writes exit row to brown_orders (status='pending')
· adds to _brown_pending_orders   →  monitor takes over
· removes from _brown_bot_active_positions (memory only — DB row stays 'open')
      │
      ▼
_brown_order_monitor_loop() confirms fill (see Order Management Flow above)
      │
      ▼
_brown_monitor_finalize_exit() closes the books:
· close_brown_position()  →  brown_positions status='closed', realized_pnl stored
· add_trade(BROWN_EXIT_*) →  trades table, pnl = realized P&L
```

---

## Risk Manager

`bot/risk_manager.py → RiskManager`. Instantiated from `brown_bot_config` when the bot starts.

| Guard | What it checks |
|-------|---------------|
| `max_daily_loss` | `get_brown_daily_realized_pnl(today)` → `SUM(realized_pnl) FROM brown_positions WHERE status='closed' AND trade_date=today`. If total ≤ threshold, circuit breaker halts all new entries. |
| `max_concurrent_day` | Count of open day positions in `_brown_bot_active_positions` (excludes `_exit_pending`) |
| `max_concurrent_swing` | Count of open swing positions (same) |

The risk manager reads from `brown_positions` — not `trades`. This means P&L from `close_all` and from normally-exited positions are all counted correctly via a single consistent source.

`GET /api/brown-bot/risk-status` returns a live snapshot even when the bot is stopped (reads config + today's P&L from DB directly).

---

## State & Persistence

| Data | Storage | Notes |
|------|---------|-------|
| Active positions | `_brown_bot_active_positions` (memory dict) | Seeded from `brown_positions WHERE status='open'` on start |
| Position ledger | `brown_positions` table (SQLite) | **Permanent** — rows transition `status='open'` → `'closed'`, never deleted on normal exit |
| Order log | `brown_orders` table (SQLite) | **Immutable** — one row per BUY or SELL, `status='pending'` → `'filled'`/`'cancelled'` |
| Entry counts | `_brown_entry_counts` (memory dict) | Fill-confirmed only; resets on start; restored from DB on restart |
| Attempted symbols | `_brown_attempted_symbols` (memory set) | All attempts (fills + rejections); resets on start; restored on restart |
| Pending fills | `_brown_pending_orders` (memory dict) | order_id → metadata; cleared on restart (recovered via broker on next start) |
| Trade history | `trades` table (SQLite) | `BROWN_ENTRY_*` / `BROWN_EXIT_*` — written only after broker fill confirmation |
| Daily stats | `get_brown_daily_realized_pnl()` | Reads from `brown_positions` — always accurate after restart |
| Swing picks | `swing_daily_picks` table (SQLite) | Keyed by trading date; updated at 8 PM ET daily |
| Swing picks cache | `_daily_picks_cache` (memory dict) | Seeded from DB on cold start |
| Activity log | `_brown_bot_logs` (memory, last 100) | Served via `GET /api/brown-bot/logs` |

BrownBot positions are **never** written to the `positions` table (owned by the DAS sync / Exit Bot). The Exit Bot ignores them entirely.

The `brown_orders` table is append-only — `INSERT OR IGNORE` on submission means duplicate order_ids are silently dropped if the same order is submitted twice (e.g. race between monitor and direct path).

---

## Restart & Recovery

`start_brown_bot()` runs a four-step reconciliation before launching threads:

### Step 1 — Restore from DB

Load all rows from `brown_positions WHERE status='open'` (or status IS NULL for legacy rows). Day positions from a previous trading date are deleted immediately. All others are added to `_brown_bot_active_positions`.

### Step 2 — Patch unconfirmed avg_entry_price

For positions that survived step 1: if `avg_entry_price` is NULL in the DB (entry fill was never confirmed before the last restart), fetch the broker's `avg_entry_price` for that symbol and write it to both memory and DB. Also recalculates `profit_target` and `stop_loss` based on the actual fill.

This closes the narrow crash window between `_brown_enter_position` saving the position row and `_brown_monitor_finalize_entry` writing the confirmed fill price.

### Step 3 — Drop stale positions (in DB, not in broker)

For each restored position whose symbol the broker no longer holds:

1. **Check DB for a sell trade** — if a `BROWN_EXIT_*` row already exists for this symbol on or after the entry date, nothing to recover; the exit completed normally before the restart.

2. **Check broker order history for a filled sell** — if a fill is found: write `close_brown_position()` (marks the DB row `status='closed'` with P&L), write `add_trade(BROWN_EXIT_*)`. This recovers P&L from the scenario where the server crashed after placing the sell but before the monitor confirmed it.

3. **Cancel the pending entry order at broker** — if no sell was found anywhere (phantom entry: position saved to DB but order never filled), call `broker.cancel_order(entry_oid)` to prevent a delayed fill from creating an untracked broker position, then `delete_brown_position()` and `update_brown_order_fill(status='cancelled')`.

### Step 4 — Adopt orphans (in broker, not in DB)

For each broker position that isn't tracked in BrownBot's DB: create a new position dict using the broker's `avg_entry_price`, derive targets/stops from current config pcts, save to `brown_positions`, and add to `_brown_bot_active_positions`. A warning is logged if this pushes the count above the configured slot cap.

---

## Debug Logging

All order-management debug lines are prefixed `[BrownBot ...]` and written to `app_logger` at `DEBUG` level — they appear in the server log when `LOG_LEVEL=DEBUG` and are **not** shown in the UI activity log.

Filter your logs with: `grep '\[BrownBot'`

### Entry submission (`_brown_enter_position`)

| Log prefix | What it tells you |
|------------|------------------|
| `[BrownBot entry] immediate status check` | Broker's response to `get_order()` right after `place_order()` — shows `status`, `filled_avg_price`, `filled_qty` |
| `[BrownBot entry] not yet filled — deferring to monitor` | Fast-path check found no fill yet; order goes into `_brown_pending_orders` |
| `[BrownBot entry] position_id=… entry_confirmed=…` | Summary of the position dict before it's saved — key fields: `avg_entry_price`, `target`, `stop` |
| `[BrownBot entry] position saved to DB` | `save_brown_position()` succeeded |
| `[BrownBot entry] brown_orders row written … status=pending/filled` | `add_brown_order()` succeeded |
| `[BrownBot entry] fast-path: update_brown_order_fill + update_brown_position_entry done` | Confirmed fill written to DB on the fast path |

UI log also emits: `"BUY submitted order=… waiting for broker fill confirmation"` when taking the async path.

### Order monitor loop (`_brown_order_monitor_loop`)

| Log prefix | What it tells you |
|------------|------------------|
| `[BrownBot monitor] polling N pending order(s): [SYM/type …]` | Every cycle that has pending orders — confirms the loop is running and what it's watching |
| `[BrownBot monitor] SYM entry/exit order=… status=… age=Xs` | Per-order status from broker each poll — the key line to check if an order is stuck |
| `[BrownBot monitor] SYM FILLED → calling finalize_entry/exit` | Fill confirmed — about to write to DB |
| `[BrownBot monitor] SYM exit CANCELLED — position restored` | Exit rejected; position put back in `_brown_bot_active_positions` for retry |
| `[BrownBot monitor] SYM exit CANCELLED — no saved_pos, cannot restore` | Exit rejected but the `position` snapshot was missing from meta — position may be orphaned |

UI activity log also emits these on partial-fill timeout (visible in the BrownBot Logs panel):

| UI log message | What happened |
|----------------|--------------|
| `SYM: entry order partially filled (X/N shares) at timeout — cancelling remainder, accepting partial` | Partial BUY at timeout — position tracked at `X` shares, not `N` |
| `SYM: exit order partially filled (X/N shares) at timeout — cancelling remainder, accepting partial` | Partial SELL at timeout — exit recorded for `X` shares |
| `SYM: Y shares restored to active tracking after partial exit — exit loop will retry` | `(N − X)` remaining shares put back in tracking for the next exit attempt |

### Finalize entry (`_brown_monitor_finalize_entry`)

| Log prefix | What it tells you |
|------------|------------------|
| `[BrownBot finalize_entry] SYM order=… fill_price=… fill_qty=…` | Entry point — confirms which order is being finalized |
| `[BrownBot finalize_entry] SYM memory updated — avg_entry=… target=… stop=…` | In-memory position updated with actual fill; these are the numbers the exit loop will use |
| `[BrownBot finalize_entry] SYM NOT found in active_positions` | Position was already removed from memory before the fill arrived (unusual) |
| `[BrownBot finalize_entry] SYM brown_orders updated … status=filled` | `update_brown_order_fill()` success |
| `[BrownBot finalize_entry] SYM brown_positions.avg_entry_price updated → X` | `update_brown_position_entry()` success |
| `[BrownBot finalize_entry] SYM save_brown_position done` | Full position blob refreshed in DB |

### Finalize exit (`_brown_monitor_finalize_exit`)

| Log prefix | What it tells you |
|------------|------------------|
| `[BrownBot finalize_exit] SYM order=… fill_price=… fill_qty=… reason=… avg_entry=… entry_price_in_meta=…` | Entry point — `avg_entry` and `entry_price_in_meta` should match; a discrepancy means the meta carried the wrong entry price |
| `[BrownBot finalize_exit] SYM P&L calc: (fill - avg_entry) × qty = pnl (pct%)` | Full P&L arithmetic — paste this line to verify the math |
| `[BrownBot finalize_exit] SYM brown_orders updated … status=filled` | Exit order row updated |
| `[BrownBot finalize_exit] SYM brown_positions status → closed realized_pnl=…` | `close_brown_position()` succeeded |
| `[BrownBot finalize_exit] SYM trades row written pnl=…` | `add_trade()` succeeded |

### Exit submission (`_brown_close_position`)

| Log prefix | What it tells you |
|------------|------------------|
| `[BrownBot close_position] SYM position_id=… reason=… qty=… current_price=… avg_entry_price=…` | Entry point — confirm the position the exit loop is acting on |
| `[BrownBot close_position] SYM broker confirms position: qty=… avg_entry=… unrealized=…` | Broker position check passed; these are the broker's live numbers |
| `[BrownBot close_position] SYM exit brown_orders row written … status=pending reason=…` | Exit order logged to `brown_orders` |
| `[BrownBot close_position] SYM queued to pending_orders … avg_entry_in_meta=… approx_exit=…` | The two numbers that will determine P&L once the fill comes in |
| `[BrownBot close_position] SYM removed from active_positions, monitor will call finalize_exit` | Position handed off to monitor — no longer in the exit loop's next tick |

---

## Config Reference

All settings live in `brown_bot_config` (DB) and are editable in the Configuration panel.

### Day Trade Config
| Field | Default | Description |
|-------|---------|-------------|
| `day_profit_target_pct` | 5.0 | Exit when unrealized gain reaches this % |
| `day_stop_loss_pct` | 2.5 | Exit when unrealized loss reaches this % |
| `day_eod_exit_time` | 15:45 | Flatten all day positions at this time (ET) |
| `day_trailing_stop_enabled` | false | Enable trailing stop |
| `day_trailing_stop_pct` | 1.5 | Trail distance % |
| `day_time_gate_enabled` | true | Restrict entries to a time window |
| `day_time_gate_start` | 09:35 | Entry window open (ET) |
| `day_time_gate_end` | 10:30 | Entry window close (ET) |
| `day_breakeven_trigger_pct` | 50.0 | Move stop to entry when this % of target reached |

### Day Trade Entry Filters
| Field | Default | Description |
|-------|---------|-------------|
| `day_check_vwap` | false | Require close ≥ session VWAP |
| `day_check_candle` | false | Require last 1-min candle bullish |
| `day_check_volume_surge` | false | Require entry bar ≥ 1.5× avg volume |
| `day_max_extension_pct` | 0 | Max % above gap price allowed (0 = off) |

### Day Trade Scanner Filters
| Field | Default | Description |
|-------|---------|-------------|
| `min_gap_pct` | 10.0 | Minimum gap % for scanner candidates |
| `min_price` | 5.0 | Minimum price filter |
| `max_price` | 500.0 | Maximum price filter |
| `min_volume_m` | 0.5 | Minimum volume in millions |
| `max_float_m` | 0 | Float filter in millions (0 = off) |
| `float_operator` | ≤ | Direction of float filter |

### Swing Trade Config
| Field | Default | Description |
|-------|---------|-------------|
| `swing_profit_target_pct` | 15.0 | Exit when unrealized gain reaches this % |
| `swing_stop_loss_pct` | 7.0 | Exit when unrealized loss reaches this % |
| `swing_max_hold_days` | 20 | Force exit after this many calendar days |
| `swing_earnings_protection_enabled` | true | Exit before upcoming earnings |
| `swing_breakeven_trigger_pct` | 50.0 | Move stop to entry when this % of target reached |

### Portfolio Risk
| Field | Default | Description |
|-------|---------|-------------|
| `max_daily_loss` | −500.0 | Circuit breaker — halt entries below this P&L ($) |
| `max_concurrent_day` | 3 | Max simultaneous open day positions |
| `max_concurrent_swing` | 5 | Max simultaneous open swing positions |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/brown-bot/status` | — | Running state, stats, active positions |
| POST | `/api/brown-bot/start` | ✓ | Instantiate RiskManager, recover positions, launch threads |
| POST | `/api/brown-bot/stop` | ✓ | Clear flag, join threads |
| GET/POST | `/api/brown-bot/config` | ✓ | Read / write config |
| GET | `/api/brown-bot/logs` | ✓ | Last 100 activity log entries |
| GET | `/api/brown-bot/risk-status` | ✓ | Live risk snapshot (daily P&L, slots, circuit breaker) |
| GET | `/api/brown-bot/candidates` | ✓ | Filtered gap-ups (scanner candidates) |
| GET | `/api/brown-bot/candidate-signals` | ✓ | Intraday signal check results per symbol |
| POST | `/api/session/ping` | ✓ | Extend session + return new `expires_at` (used by keepalive) |

---

## Session Management

BrownBot runs as a server-side daemon — it continues executing regardless of whether the user has a browser open or their session is active. The UI is a control panel only.

### Session keepalive (frontend)

When the bot is **running**, the frontend automatically pings `POST /api/session/ping` every 4 minutes to extend the 24-hour session window. This fires even if the user has navigated away from the BrownBot tab. The keepalive starts on `toggleBrownBot()` (start) and stops on `toggleBrownBot()` (stop).

### Session expiry warning

When the session has fewer than 30 minutes remaining, an amber dismissible banner appears at the top of the page with a "Stay logged in" button. Clicking it calls the ping endpoint to reset the timer. The banner also notes that BrownBot will keep running even if the session lapses.

### Global bot status chip

A green animated "BrownBot LIVE" chip is displayed in the top nav bar whenever the bot is running, regardless of which tab is active. Clicking it navigates to the BrownBot tab.

---

## Key Constraints

- **No manual input** — BrownBot is fully autonomous. Day candidates come from the gap-up scanner; swing candidates come from the daily AI hot picks.
- **Long only** — all entries are market BUY. `broker.close_position()` is used for exits to prevent accidental short selling.
- **Single process** — runs inside the same Flask/eventlet process as the rest of the app. All three threads share `_brown_bot_active_positions` via `_brown_bot_lock`.
- **No `positions` table writes** — BrownBot positions live in memory, `brown_positions`, and `trades` only. Never write to the `positions` table.
- **Broker-confirmed writes** — trade records in `trades` and realized P&L in `brown_positions` are written only after the broker confirms a fill. `_brown_pending_orders` bridges the gap between order submission and fill confirmation.
- **Permanent position ledger** — `brown_positions` rows are never deleted on a normal exit. They transition `status='open'` → `'closed'`. Only phantom entries (buy order never filled) are deleted.
- **Retry guard** — `_brown_attempted_symbols` is marked before every order attempt. The scan loop skips any symbol already in this set, so a rejected or BP-failed order is never retried in the same session.
- **Buying power pre-flight** — `_brown_enter_position()` checks `broker.get_account().buying_power` before placing the order. If insufficient, the symbol is logged, marked as attempted, and no order is sent. Fails open if the account API call errors.
- **Swing picks are session-scoped** — `_brown_entry_counts` prevents re-entering the same swing pick multiple times in a day, even if the position closes and re-qualifies.
- **Bot/session decoupling** — BrownBot runs independently of the user's login session. The session keepalive is a convenience, not a dependency; if the session lapses the bot continues running.
- **Double-exit guard** — `_brown_closing_positions` is a set of position_ids currently being sent to the broker. The exit loop skips any position already in this set, preventing duplicate sell orders if two loop ticks overlap.
- **Partial fill safety** — `PARTIAL` status during normal polling is treated as "still waiting" and re-polled next cycle. At the 60-second timeout, if `filled_qty > 0` the remaining unfilled shares are cancelled at the broker and the partial fill is accepted: entry positions are tracked at the actual filled share count; exit positions record the filled portion and restore the remaining shares to active tracking so the exit loop can retry. If `filled_qty == 0` at timeout, the order is cancelled and cleaned up as if it was never filled.
