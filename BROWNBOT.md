# BrownBot — Architecture & Pipeline

BrownBot is a fully autonomous trading bot. It finds its own candidates, gates entries through a risk manager, and exits positions without manual intervention. It operates independently of the Entry Bot and Exit Bot — never modify those when working on BrownBot.

Gated to the **Yogi** subscription tier.

---

## Runtime

Two daemon threads are started together on `POST /api/brown-bot/start` and stopped on `POST /api/brown-bot/stop`:

| Thread | Function | Interval |
|--------|----------|----------|
| `BrownBotScanner` | `_brown_bot_scan_and_enter()` | 30 s |
| `BrownBotExits` | `_brown_bot_check_exits()` | 2 s (swing-specific every 60 s) |

The running flag `_brown_bot_running` is the only shutdown signal — both loops poll it and exit cleanly.

On `start_brown_bot()` the bot also restores any positions that were persisted to `brown_positions` (DB) before the last server restart, so active positions survive process restarts without manual reconciliation.

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
· max_daily_loss circuit breaker  (today's realized P&L from trades table)
      │
      ▼
_brown_enter_position(symbol, 'day')
· Pre-flight buying power check  →  skips (no order sent) if account BP < price × qty
· Marks symbol in _brown_attempted_symbols BEFORE the order
· Places market BUY via broker.place_order()
· Stores position in _brown_bot_active_positions
· Persists position to brown_positions table (DB)
· Writes BROWN_ENTRY_* record to trades table
· Increments _brown_entry_counts[symbol] only on a confirmed fill
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
· Logs each dropped ticker with close vs SMA-10 to app_logger.debug
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
· Stores in _brown_bot_active_positions
· Persists position to brown_positions table (DB)
· Writes BROWN_ENTRY_* record to trades table
```

#### Swing Candidates UI

The Swing Trade Candidates panel in the UI shows all Grade A/B Bullish picks with a status badge derived from runtime state:

| Status | Meaning |
|--------|---------|
| **Active** | Position currently open in `_brown_bot_active_positions` |
| **Entered Today** | Fill confirmed (`_brown_entry_counts` has the symbol) |
| **Skipped** | Attempted but rejected/BP-insufficient (`_brown_attempted_symbols` has it, `_brown_entry_counts` does not) — will not be retried this session |
| **Eligible** | No attempt yet; bot may enter on the next scan |

---

## Exit Pipeline

Runs every 2 seconds. Swing-specific checks (hold days, earnings) run every 60 seconds.

```
For each position in _brown_bot_active_positions:
      │
      ▼
_brown_get_current_price(symbol)
→  broker.get_quote()  →  Alpaca StockLatestTradeRequest (real last-trade price)
→  DAS Level 1 fallback
      │
      ▼
Update unrealized_pnl in position dict  (shown live in UI)
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
                      via _ai_agent._get_earnings_calendar()
                      exits N days before confirmed earnings date
      │
      ▼
_brown_close_position(position_id, exit_reason)
· broker.get_position(symbol)   →  confirms position exists
                                    (prevents accidental short if already flat)
· broker.close_position(symbol) →  market SELL via broker abstraction layer
· Polls broker.get_order() up to 3× for actual fill price (filled_avg_price)
· Deletes position from brown_positions table (DB)
· Writes BROWN_EXIT_* record to trades table
· Removes from _brown_bot_active_positions
```

---

## Risk Manager

Instantiated from `brown_bot_config` when the bot starts. Re-reads today's realized P&L from the `trades` table on each `can_enter()` call.

| Guard | What it checks |
|-------|---------------|
| `max_daily_loss` | Sum of today's BROWN_EXIT P&L ≤ threshold → circuit breaker halts all new entries |
| `max_concurrent_day` | Count of open day positions < limit |
| `max_concurrent_swing` | Count of open swing positions < limit |

`GET /api/brown-bot/risk-status` returns a live snapshot even when the bot is stopped.

---

## State & Persistence

| Data | Storage | Notes |
|------|---------|-------|
| Active positions | `_brown_bot_active_positions` (memory dict) | Seeded from `brown_positions` DB on `start_brown_bot()` |
| Active positions (backup) | `brown_positions` table (SQLite) | Written on entry, deleted on exit — survives server restarts |
| Entry counts | `_brown_entry_counts` (memory dict) | Filled-only entries; resets on start; restored from DB on restart |
| Attempted symbols | `_brown_attempted_symbols` (memory set) | All attempts this session (fills + rejections); resets on start; restored on restart |
| Trade history | `trades` table (SQLite) | `trade_id` prefixed `BROWN_ENTRY_*` / `BROWN_EXIT_*` |
| Daily stats | Queried live from `trades` table | Never in-memory; always accurate after restart |
| Swing picks | `swing_daily_picks` table (SQLite) | Keyed by trading date; updated at 8 PM ET daily |
| Swing picks cache | `_daily_picks_cache` (memory dict) | Seeded from DB on cold start |
| Activity log | `_brown_bot_logs` (memory, last 100) | Served via `GET /api/brown-bot/logs` |

BrownBot positions are **never** written to the `positions` table (owned by the DAS sync / Exit Bot). The Exit Bot ignores them entirely.

---

## Session Management

BrownBot runs as a server-side daemon — it continues executing regardless of whether the user has a browser open or their session is active. The UI is a control panel only.

### Session keepalive (frontend)

When the bot is **running**, the frontend automatically pings `POST /api/session/ping` every 4 minutes to extend the 24-hour session window. This fires even if the user has navigated away from the BrownBot tab. The keepalive starts on `toggleBrownBot()` (start) and stops on `toggleBrownBot()` (stop).

`POST /api/session/ping` is an authenticated endpoint that extends the session and returns the new `expires_at` timestamp.

### Session expiry warning

When the session has fewer than 30 minutes remaining, an amber dismissible banner appears at the top of the page with a "Stay logged in" button. Clicking it calls the ping endpoint to reset the timer. The banner also notes that BrownBot will keep running even if the session lapses.

### Global bot status chip

A green animated "BrownBot LIVE" chip is displayed in the top nav bar whenever the bot is running, regardless of which tab is active. Clicking it navigates to the BrownBot tab.

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
| POST | `/api/brown-bot/start` | ✓ | Instantiate RiskManager, restore positions, launch threads |
| POST | `/api/brown-bot/stop` | ✓ | Clear flag, join threads |
| GET/POST | `/api/brown-bot/config` | ✓ | Read / write config |
| GET | `/api/brown-bot/logs` | ✓ | Last 100 activity log entries |
| GET | `/api/brown-bot/risk-status` | ✓ | Live risk snapshot |
| GET | `/api/brown-bot/candidates` | ✓ | Filtered gap-ups (scanner candidates) |
| GET | `/api/brown-bot/candidate-signals` | ✓ | Intraday signal check results per symbol |
| POST | `/api/session/ping` | ✓ | Extend session + return new `expires_at` (used by keepalive) |

---

## Key Constraints

- **No manual input** — BrownBot is fully autonomous. Day candidates come from the gap-up scanner; swing candidates come from the daily AI hot picks.
- **Long only** — all entries are market BUY. `broker.close_position()` is used for exits to prevent accidental short selling.
- **Single process** — runs inside the same Flask/eventlet process as the rest of the app. Both loops are daemon threads; they share `_brown_bot_active_positions` via `_brown_bot_lock`.
- **No position table writes** — BrownBot positions live in memory, `brown_positions`, and `trades` only. Never write to the `positions` table.
- **Retry guard** — `_brown_attempted_symbols` (a set) is marked before every order attempt. The scan loop skips any symbol already in this set, so a rejected or BP-failed order is never retried in the same session.
- **Buying power pre-flight** — `_brown_enter_position()` checks `broker.get_account().buying_power` before placing the order. If insufficient, the symbol is logged, marked as attempted (skipped), and no order is sent. Fails open if the account API call errors.
- **Swing picks are session-scoped** — `_brown_entry_counts` prevents re-entering the same swing pick multiple times in a day, even if the position closes and re-qualifies.
- **Bot/session decoupling** — BrownBot runs independently of the user's login session. The session keepalive is a convenience, not a dependency; if the session lapses the bot continues running.
