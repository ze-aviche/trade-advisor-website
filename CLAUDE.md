# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the application

All commands run from `gap-trade-bot/backend/` unless stated otherwise.

**Local development (host machine — required for mock DAS testing):**
```bash
pip install -r requirements.txt
python app.py
```
Flask serves both the API and the frontend at `http://localhost:5000`. The frontend is served as static files from `../frontend/`.

**Docker (production-like):**
```bash
# from gap-trade-bot/
docker-compose up --build
```
Uses gunicorn with eventlet worker (`-w 1` is intentional — eventlet is single-process).

**Important:** Docker and mock DAS testing are mutually exclusive. The mock server binds `127.0.0.1:9800` on the host; a container cannot reach it. See `TESTING_WITHOUT_DAS.md` for the full e2e mock flow.

**Mock DAS server (separate terminal, required for bot testing):**
```bash
python mock_das_server.py --scenario entry --ramp 15
# Interactive keys: t=drift to target, s=drift to stop, v=trigger volume ramp, q=quit
```

**Seed test data (positions/trades history without live bot):**
```bash
python seed_test_positions.py --clear
```

**Run tests:**
```bash
python3 -m pytest tests/ -v
```

## Architecture overview

### Single-process Flask + SocketIO backend
`app.py` (~9,600 lines) is the entire backend. It runs as one process with eventlet green threads. There is no task queue, no separate worker process. Background loops (DAS monitor, trial reminders, BrownBot scanner/exits) run as daemon threads started on demand.

### DAS Trader integration
DAS Trader Pro is the broker execution layer. The bot communicates via a **raw TCP socket** to `127.0.0.1:9800`. All commands are ASCII strings terminated with `\r\n` (e.g. `GET POSITIONS\r\n`, `SB NVDA Lv1\r\n`, `NEWORDER <id> B NVDA SMAT 100 MKT\r\n`).

`DAS_ENABLED` in `app.py` is the global feature flag (currently `False`). When `False`, the Exit Bot and scheduled DAS sync are also disabled regardless of their own state.

The shared DAS socket is in `bot/trading_bot.py → Connection`. The entry bot (`app.py`) and exit bot (`TradingBot`) each open **separate TCP connections** to DAS. Thread safety is enforced by `Connection._lock` (a `threading.Lock`).

`_send_das_script()` in `app.py` routes through the exit bot's connection first (preferred), then falls back to a direct socket (`_das_direct`). Never use the `cmdapi/CMDAPI_PYTHON.py` class for new code — it is not thread-safe.

### Broker abstraction (`bot/broker/`)
BrownBot uses a pluggable broker layer rather than DAS directly. `AlpacaBroker` in `bot/broker/alpaca.py` implements the `BaseBroker` interface. `_get_broker(user_id)` reads the active broker config from the `broker_configs` table and returns a connected broker instance. `_brown_broker` is the live instance while the bot is running. `place_das_order()` routes through the broker when DAS is disabled.

Supported brokers: **Alpaca** (live). Tastytrade, Tradier, DAS Trader Pro are shown in the UI with "Coming Soon" overlays.

### Three-bot design
| Bot | Where | Trigger | Loop interval |
|-----|-------|---------|---------------|
| **Entry Bot** | `app.py` (`submit_entry_parameters`, `_tracking_loop`) | User submits symbol + params via UI | 1 s (day), immediate (swing) |
| **Exit Bot** | `bot/trading_bot.py → TradingBot` | User clicks "Start Bot" in UI | 5 s (day), 60 s (swing) |
| **BrownBot** | `app.py` (`_brown_bot_scanner_loop`, `_brown_bot_exit_loop`) | User clicks "Start" in BrownBot tab | Scanner: 30 s · Exits: 2 s |

Entry bot state (`tracking_symbols`, `active_positions`, `entry_bot_logs`) is in-memory global dicts in `app.py`. Exit bot state is in `TradingBot` instance attributes. Both persist positions to the SQLite DB via `database.py → db_manager`.

BrownBot state is managed **per user** via `_get_brown_session(user_id)` which returns a `BrownBotSession` dataclass. Session fields include `active_positions`, `stats`, `logs`, `playbook_cache`, `playbook_pending`, `playbook_failed`. BrownBot positions are persisted to the `brown_positions` table (not the `positions` table owned by DAS sync).

### Position lifecycle
1. Entry bot checks `check_entry_conditions()` — volume, dollar-volume, time gates (day) or immediate (swing)
2. `enter_position()` sends `NEWORDER B` and writes to `active_positions` + DB
3. Exit bot reads `GET POSITIONS`, subscribes to Level 1, calls `ExitConditionChecker.check_exit_conditions()` every loop
4. `OrderManager.close_position()` sends `NEWORDER S` (or `B` for shorts) and writes the closed trade to DB

### Database (`database.py`)
Single SQLite file. Location is `DATABASE_PATH` env var (Render persistent disk) or `backend/trading_advisor.db` locally.

Schema is managed by `init_database()` + `_migrate_schema()` (additive `ALTER TABLE` migrations — safe to run repeatedly).

**Critical ordering rule**: In `_migrate_schema()`, `CREATE TABLE IF NOT EXISTS` for a table **must** come before any `ALTER TABLE ADD COLUMN` loop for that table. If ALTER TABLE runs first on a fresh DB the table won't exist, the error is swallowed silently, and the columns are permanently missing. This bug was fixed for `brown_positions` — do not reintroduce it.

Key tables:
- `users`, `sessions` — auth
- `positions` — current live positions (upserted on every DAS sync)
- `daily_positions` — daily snapshots of positions (append-only, one row per symbol per day)
- `trades` — individual fills from DAS
- `gap_up_snapshots` — daily gap-up scan results
- `swing_bot_config` — per-user swing exit settings
- `brown_bot_config` — BrownBot day/swing targets, risk limits, scanner thresholds (one row per user; seeded with platform defaults at registration)
- `brown_watchlist` — manual symbols added by the user for BrownBot to trade
- `brown_positions` — BrownBot active and closed positions with full P&L tracking (`status`, `trade_date`, `realized_pnl`, `unrealized_pnl`, `exit_reason`, etc.)
- `brown_orders` — immutable per-order log (one row per BUY or SELL placed by BrownBot)
- `broker_configs` — encrypted broker API keys per user
- `error_logs` — unhandled exception log (user_id, endpoint, traceback, request payload, IP)
- `swing_screener_history` — daily swing scanner snapshots
- `swing_daily_bars` — OHLCV cache for swing backtest

`db_manager` is a module-level singleton imported everywhere.

### Authentication
Session-token based (not JWT). Tokens are in `Authorization: Bearer <token>` header or `session_token` cookie. `require_auth` decorator in `auth.py` sets `request.user` for the current request. `require_role(*roles)` checks `system_role` from the `users` table.

System roles: `super_admin`, `dev_master`, `bot_admin`. First registered user is auto-promoted to `super_admin`.

Both `require_auth` and the `before_request` hook call `_tag_request_context(user)` which sets `g.current_user_id` (for log injection) and `sentry_sdk.set_user()` (for error attribution).

### Logging (`logging_config.py`)
**Structured JSON on stdout** (one object per line — greppable by `user_id` in Render log stream):
```json
{"time": "...", "level": "INFO", "logger": "app", "user_id": 7, "ip": "...", "endpoint": "...", "msg": "..."}
```

`UserContextFilter` injects `user_id`, `ip`, and `endpoint` into every log record from Flask `g`. Falls back to `-` in background threads (which have no request context).

**Per-user debug mode**: `set_debug_user(user_id, True/False)` in `logging_config.py` toggles a user into `_debug_user_ids`. Use `_brown_debug(user_id, msg)` in BrownBot code — it emits at INFO only when that user is in debug mode, avoiding global log level changes. Toggle via `POST /api/admin/debug-user`.

**High-frequency polling endpoints** (`/api/brown-bot/status`, `/api/brown-bot/logs`, `/api/brown-bot/risk-status`, `/api/bot/status`, `/api/entry-bot/status`, `/api/session/ping`, `/api/health`) are logged at DEBUG level to avoid flooding production logs. Errors on these paths still log at ERROR/WARNING.

### Error handling
`@app.errorhandler(Exception)` in `app.py` catches all unhandled exceptions, logs them via `app_logger.error()`, and writes a row to the `error_logs` table (includes user_id, traceback, request payload, IP). Returns `{"success": false, "error": "Internal server error"}` with 500.

Admin endpoints for error inspection:
- `GET /api/admin/error-logs?user_id=&since=&limit=` — query the error_logs table
- `POST /api/admin/debug-user` / `GET /api/admin/debug-user` — toggle/inspect per-user debug mode

### Frontend
Vanilla JS + Vue 3 (CDN, no build step) + Tailwind CSS (CDN). All logic is in `frontend/app.js`. Tabs are driven by `currentTab` Vue data property. Socket.IO is used for real-time push from the backend. No npm, no bundler — just open `index.html` or let Flask serve it.

Login page is `frontend/login.html` (separate file, its own Vue app). Includes password visibility toggle.

### Gap-up detection
`gap_up_detector.py` uses the Polygon REST API + Alpaca movers endpoint. Results are cached in memory (`gap_up_cache.py`) with a TTL and also persisted to `gap_up_snapshots` table. `yfinance` is the fallback/supplement for pre-market and metadata enrichment.

### External services
| Service | Purpose | Feature flag / env var |
|---------|---------|----------------------|
| Alpaca | Broker execution, market data (movers, bars) | `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `ALPACA_PAPER` |
| Polygon API | Gap-up scan supplemental | `POLYGON_API_KEY` |
| Anthropic Claude | AI trade analysis, swing picks, AI Playbook | `ANTHROPIC_API_KEY` |
| Stripe | Subscription billing | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*` |
| Gmail SMTP | Email notifications, trial reminders | `CONTACT_EMAIL_FROM`, `GMAIL_APP_PASSWORD` |
| Sentry | Error monitoring + per-request user tagging | `SENTRY_DSN` (optional — disabled if unset) |

### Deployment
Render.com. The persistent disk mounts at `/data`; set `DATABASE_PATH=/data/trading_advisor.db`. The Dockerfile is in `gap-trade-bot/` (not the repo root). `docker-compose.yml` is for local use only.

### Bruno API collection (`gap-trade-bot/bruno/`)
File-based API client collection covering all endpoints. Import into Bruno desktop app (File → Open Collection). Switch between `local` and `production` environments. Run the `auth/Login.bru` request first — the post-response script saves the session token to the environment automatically.

Folders: `auth/`, `admin/`, `gap-ups/`, `brown-bot/`, `broker/`, `positions/`, `trades/`, `entry-bot/`, `swing/`, `ai-agent/`, `cache/`, plus a root `Health Check.bru`.

---

### BrownBot

BrownBot is a fully autonomous bot that finds its own candidates, gates entries through a portfolio risk manager, and exits positions without manual intervention. It is gated to the **Yogi** subscription tier and operates independently of the Entry Bot and Exit Bot — never modify those bots when working on BrownBot.

#### Runtime threads
Two daemon threads are started together on `POST /api/brown-bot/start` and stopped on `POST /api/brown-bot/stop`:

| Thread | Function | Interval |
|--------|----------|----------|
| `BrownBotScanner` | `_brown_bot_scanner_loop()` → `_brown_bot_scan_and_enter()` | 30 s |
| `BrownBotExits` | `_brown_bot_exit_loop()` → `_brown_bot_check_exits()` | 2 s (swing-specific checks every 60 s) |

The running flag `_brown_bot_running` is the only shutdown signal — both loops poll it and exit cleanly.

The exit loop `verbose` flag is `True` every 30 ticks OR whenever the user is in debug mode (`is_debug_user(user_id)`), giving detailed per-position output in the logs without flooding them on every 2-second tick.

#### Per-user session (`BrownBotSession`)
`_get_brown_session(user_id)` returns (creating if needed) a `BrownBotSession` dataclass stored in `_brown_sessions[user_id]`. Fields:
- `active_positions` — dict of live positions keyed by symbol
- `stats` — day/swing entry/exit counts
- `logs` — last 100 activity log entries
- `playbook_cache` — symbol → AI playbook result
- `playbook_pending` — symbols currently being fetched in background
- `playbook_failed` — symbols whose playbook fetch failed (skip on retry)
- `lock` — `threading.Lock` for safe concurrent access

#### Entry pipeline (`_brown_bot_scan_and_enter`)

**Day trades** — sourced from auto-scanner gap-up hits (09:35–10:30 ET window):
1. **Scanner filter**: gap % ≥ `min_gap_pct`, price between `min_price`/`max_price`, volume ≥ `min_volume_m`M, optional float filter (`float_operator` is `>=` or `<=`, threshold is `max_float_m`).
2. **Intraday trend signals** via `_check_day_entry_signal()` — all optional, all off by default:
   - Above session VWAP (`day_check_vwap`)
   - Last 1-min candle is bullish/close ≥ open (`day_check_candle`)
   - Extension from gap price ≤ `day_max_extension_pct` (`day_max_extension_pct > 0`)
   - Volume surge ≥ 1.5× recent bar average (`day_check_volume_surge`)
3. **AI Playbook gate** (if `day_ai_playbook` is `True`): `_fetch_and_cache_playbook()` runs in a background thread on first encounter. Entry is deferred one scan cycle. On the next cycle the cached result is checked — if `bias=Short / confidence=High` the symbol is skipped. Otherwise the AI's stop/target percentages override the config defaults. Default is `False` (off) for new users.
4. **Risk manager**: `RiskManager.can_enter()` — slot cap (`max_concurrent_day`) + daily loss circuit breaker.
5. **Buying power**: `equity × day_position_pct%` must be ≤ available buying power.
6. `_brown_enter_position()` → `place_das_order()` → store in session `active_positions`.

**Swing trades** — sourced from today's Claude-ranked daily picks (Swing tab):
1. **Source**: `_daily_picks_cache[today]` / `db_manager.get_swing_picks(today)` — picks already graded by the Swing tab AI pipeline (SMA-10, intraday structure, market cap, Claude grade A/B/C + bullish/neutral/bearish bias). Only Grade A or B + Bullish picks are used.
2. No additional signal check — avoids double AI cost since picks are pre-vetted.
3. **Risk manager**: `RiskManager.can_enter()` — slot cap (`max_concurrent_swing`) + daily loss circuit breaker.
4. **Buying power**: `equity × swing_position_pct%` must be ≤ available buying power.
5. `_brown_enter_position()` → `place_das_order()` → store in session `active_positions`.

#### Risk manager (`bot/risk_manager.py → RiskManager`)
Instantiated from `brown_bot_config` when the bot starts. `can_enter(symbol, position_type, active_positions, unrealized_pnl)` returns `(allowed, reason)` and enforces:
- `max_daily_loss`: circuit breaker — halts all new entries if `realized_pnl + unrealized_pnl ≤ threshold`. Both components are included so open losing positions count against the limit in real time.
- `max_concurrent_day` / `max_concurrent_swing`: slot caps. Positions with `_exit_pending=True` are excluded from the count. `brown_day` counts toward day cap; `brown_swing` counts toward swing cap.
- User entering a positive number (e.g. `500`) is normalised to negative (`-500`) automatically.

The `GET /api/brown-bot/risk-status` endpoint returns a live snapshot even before the bot is started (reads config + today's P&L from DB directly).

#### Exit pipeline (`_brown_bot_check_exits`)
For each position in the session's `active_positions`:
1. Fetch current price via `_brown_get_current_price()` → `get_real_stock_data()` → `SB {sym} Lv1`.
2. Update `unrealized_pnl` in the shared dict.
3. **Breakeven stop**: once price reaches `{type}_breakeven_trigger_pct`% of the way from entry to target, move stop to entry price (sets `_at_breakeven` flag; shown as "BE" badge in UI).
4. Exit conditions checked in order: profit target → stop loss → EOD flatten (day, at `day_eod_exit_time` ET, default **15:55**) → max hold days (swing) → earnings protection (swing, queries Nasdaq calendar via `_ai_agent._get_earnings_calendar()`).
5. `_brown_close_position()` → `place_das_order(S)` → `db_manager.close_brown_position()` → remove from dict.

#### Position discriminator
`position_type` field in session `active_positions` is `'day'` or `'swing'`. BrownBot positions are **never** written to the `positions` table (which is owned by the DAS sync / Exit Bot). They live in `brown_positions`. The Exit Bot ignores them; BrownBot's exit loop manages them exclusively.

#### Debug logging in BrownBot
Use `_brown_debug(user_id, msg)` for verbose hot-path logging. It logs at INFO only when that user has debug mode enabled via `POST /api/admin/debug-user`. Key instrumentation points:
- `_brown_enter_position`: account fetch failure
- `_brown_bot_scan_and_enter`: per-stock filter-out reason
- `_brown_close_position`: duplicate exit guard, broker confirmation, DB write, pending-orders queue, active_positions removal

#### Default BrownBot config (applied to every new user at registration)
| Setting | Value |
|---|---|
| EOD exit time | 15:55 ET |
| AI Playbook | Off |
| Min gap % | 25% |
| Min volume | 10M |
| Min price | $1 |
| Max price | $50 |
| Float filter | ≥ 5M |
| Max concurrent day | 5 |
| Max concurrent swing | 3 |
| Swing scan source | Both |
| Swing SMA20 signal | On |
| Swing MA cross signal | On |

Defaults live in two places that must stay in sync: the Python `defaults` dict in `DatabaseManager.get_brown_bot_config()` and the SQL `DEFAULT` values in the `CREATE TABLE brown_bot_config` statement. After registration, `update_brown_bot_config(defaults, user_id)` seeds a DB row so the user always gets these values regardless of SQL schema defaults.

#### API endpoints (`/api/brown-bot/*`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/status` | — | Running state, stats, active positions list |
| POST | `/start` | ✓ | Instantiate RiskManager, launch threads |
| POST | `/stop` | ✓ | Clear flag, join threads |
| POST | `/close-all` | ✓ | Emergency exit all open positions |
| GET/POST | `/config` | ✓ | Read / write `brown_bot_config` |
| GET | `/logs` | ✓ | Last 100 activity log entries (reversed) |
| GET | `/risk-status` | ✓ | Live risk snapshot (daily P&L, slots, circuit breaker) |
| GET | `/broker-orders` | ✓ | Recent orders from the broker |
| GET | `/candidates` | ✓ | Filtered day gap-ups + watchlist merged |
| GET | `/swing-candidates` | ✓ | Swing picks eligible for entry |
| GET/POST | `/watchlist` | ✓ | List / add watchlist symbols |
| DELETE | `/watchlist/<symbol>` | ✓ | Remove watchlist symbol |
| POST | `/swing-backtest` | ✓ | Run backtest on swing config |

---

## Gap-up data pipeline

### Single source of truth
`gap_up_detector.py → get_gap_up_stocks_for_frontend()` is the **only** function that fetches gap-up data. Everything else reads from it — never add a second fetching path.

### Call chain
```
get_gap_up_stocks_for_frontend()
  │
  ├── GET /api/gap-ups ──────────────────────────────────────► Gap-Ups tab (frontend)
  │
  ├── POST /api/gap-ups/force-refresh ──┬────────────────────► Gap-Ups tab (cache-busted)
  │                                     └────────────────────► real_time_gap_ups global
  │
  └── gap_up_monitor_loop() (background thread, app.py)
        intervals: open=120s · pre_market=300s · after_hours=300s · closed=900s
        → real_time_gap_ups (module-level global, app.py line ~188)
                  │
                  └── _brown_bot_scan_and_enter() (every 30s)
                        reads real_time_gap_ups; falls back to DB snapshot if empty
```

### Session routing inside get_gap_up_stocks_for_frontend
| Effective session | Primary source | Trigger |
|---|---|---|
| `pre_market` / `closed` | `_fetch_premarket_from_yfinance()` | before 09:32 ET |
| `open` | `_fetch_from_alpaca()` (movers) + most-actives + universe scan | ≥ 09:32 ET |
| `after_hours` | Today's DB snapshot + universe scan | after 16:00 ET |

yfinance `day_gainers` always runs as a supplemental on every path for metadata enrichment.

### Stale-window guard (critical — do not remove)
Alpaca's movers endpoint resets ~60 s after market open. From 09:30:00 to 09:31:59 ET it still returns the **previous day's** top gainers. The guard in `get_gap_up_stocks_for_frontend()` overrides `market_status` to `pre_market` during this window, keeping yfinance as the source until 09:32 ET.

```python
if market_status == 'open' and now_et.hour == 9 and now_et.minute < 32:
    market_status = 'pre_market'  # stay on yfinance until Alpaca is definitely fresh
```

### Cache (gap_up_cache.py — GapUpCache)
Cache keys are **session-aware**: `gap_up_frontend_{session}` (e.g. `gap_up_frontend_open`). This forces a cache miss whenever the effective session changes, so stale pre-market data is never served after 09:32 ET.

| Session | Cache type | TTL |
|---|---|---|
| `open` (09:00–11:59 ET) | `real_time` | **30 s** |
| `open` (other hours) | `real_time` | 60 s |
| Outside market hours | `real_time` | 300 s |

Universe-scan results use a separate `gap_up_universe_scan` key with `default` type (120 s during peak hours).

**Universe scan is non-blocking on cache miss**: `_fetch_from_alpaca_universe_scan` takes 10–20 s for ~10 k symbols. On a cache miss, a background `UniversePrewarm` daemon thread is started and the current request continues without universe data. The next call (≥30 s later) gets a cache hit. Do not revert this to inline execution — it would block the API request and trip the 30 s frontend timeout.

`invalidate_gap_up_cache()` clears **all** `gap_up_frontend_*` and `gap_up_universe_*` keys — always call this before `get_gap_up_stocks_for_frontend()` when a forced refresh is needed.

### Force-refresh (POST /api/gap-ups/force-refresh)
1. Calls `invalidate_gap_up_cache()` — wipes all session + universe cache keys.
2. Calls `get_gap_up_stocks_for_frontend()` immediately — fetches from Alpaca/yfinance.
3. Assigns result to `real_time_gap_ups` global so BrownBot also sees fresh data without waiting for the next monitor cycle.
4. Response body contains the fresh stocks array — the frontend applies it directly to `this.gapUps` without a second API round-trip.

The Gap-Ups tab refresh button calls this endpoint (not the plain GET), so one click guarantees fresh data end-to-end.

### Real-time push (Socket.IO)
The backend monitor loop (`update_real_time_gap_ups`) broadcasts `gap_ups_update` via `socketio.emit()` every 2 min during market hours. The frontend establishes a `io()` connection on mount and listens for this event — when it fires, the gap-up table is updated in-place without any user interaction. The `websocket_connected` global must be `True` (set by the `connect` SocketIO handler) for broadcasts to fire.

### Adding new data sources
Any new gap-up data source must be added **inside** `get_gap_up_stocks_for_frontend()` as a supplemental — do not create parallel fetch paths in `app.py` or BrownBot. The monitor loop and BrownBot will pick it up automatically.

### Monitoring the gap-up pipeline in Render logs

**Important:** all log timestamps are **UTC**. Subtract 4 h (EDT) or 5 h (EST) to get ET. A log line at `23:28 UTC` is `19:28 ET` (7:28 PM) — still inside the after_hours window.

**GapUpMonitor thread** (`update_real_time_gap_ups` in `app.py`):
- Startup: `🔄 [GapUpMonitor] Thread started`
- Every cycle: `Gap-up monitor: N stocks (market=open, next refresh in 120s)`
- Sleeps 900 s during `closed` window (20:00–04:00 ET) — no log emitted during that window

**Alpaca movers fetch** (fires each monitor cycle when market is `open`):
- `[AlpacaMovers] Calling movers endpoint at HH:MM:SS ET`
- `[AlpacaMovers] N raw gainers received at HH:MM:SS ET (top ticker: XYZ)` — "top ticker" is Alpaca's raw #1 gainer before your non-CS filter runs; SPAC warrants/rights can appear here
- `[AlpacaMovers] HTTP 4xx from movers endpoint` — Alpaca key issue

**Universe scan** (supplemental, non-blocking, ~10 k symbols batched via Alpaca snapshots endpoint):
- Cache HIT: `[GapScanner] Universe scan cache HIT: 947 stocks` — served from 120 s cache, no API call
- Cache MISS: `[GapScanner] Universe scan cache MISS — scheduling background pre-warm (skipping for this request)` — `UniversePrewarm` daemon thread fires; current request gets no universe data; next request (≥ 30 s later) will hit the cache
- Pre-warm done: `[GapScanner] Universe pre-warm done: 947 stocks cached`
- Universe scan exists to catch micro-cap/low-float runners that Alpaca's curated top-50 movers list excludes

**After-hours behaviour** (16:00–20:00 ET):
- Monitor still runs every 300 s but skips live API calls
- `[GapScanner] [after_hours] Loading today's DB snapshot as primary...`
- `[GapScanner] AH DB snapshot: N stocks loaded` — N can be large (includes universe scan results merged earlier in the day)
- This is expected — no actionable intraday data in AH; DB snapshot is served to clients and BrownBot

**EOD snapshot save** (first after_hours cycle, ~16:05 ET):
- `📸 Gap-up snapshot saved for YYYY-MM-DD: N stocks` — written to `gap_up_snapshots` table once per day
- `📡 Background: caching N gappers in historical_data_cache for YYYY-MM-DD` — fires a thread to populate the Historical tab cache
- **Bug note (fixed 2026-05-28):** snapshot save was gated on `hour >= 20` which can never fire because the `closed` branch does `continue` before reaching that code. Fixed to `hour >= 16 and market_status == 'after_hours'`.

**Historical prefetch daemon** (`_historical_prefetch_daemon` in `app.py`, polls every 90 s):
- Startup: `📚 Historical prefetch daemon started`
- New tickers to fetch: `[HistoricalPrefetch] N new ticker(s) to pre-fetch: [...]`
- Per ticker done: `[HistoricalPrefetch] NVDA done — 48 gap-up days cached`
- Per ticker error: `[HistoricalPrefetch] Failed to pre-fetch TSLA: <reason>` — usually Polygon rate limit
- All cached (DEBUG level, not visible unless debug mode on): `[HistoricalPrefetch] All N gap-up ticker(s) already cached — sleeping 90s`
- Live status endpoint (no auth): `GET /api/historical-prefetch/status` → `{"prefetched": {"NVDA": {"records": 48, "fetched_at": "..."}}, "total": 12}`

**Force-refresh** (user clicks refresh button in Gap-Ups tab):
- `[ForceRefresh] Done — N stocks returned, real_time_gap_ups updated`

**Nightly historical cache thread** (`cache_gap_up_day_for_tickers` in `historical_data.py`, spawned by the EOD snapshot save):
- The thread only starts if `📸 Gap-up snapshot saved` fires first. If you see no cache logs, check for the snapshot log before investigating the thread.
- Kick-off (logged by `app.py`): `📡 Background: caching N gappers in historical_data_cache for YYYY-MM-DD`
- Per-ticker success: `💾 Snapshot→cache: stored YYYY-MM-DD data for NVDA`
- Per-ticker error (Alpaca rate limit, missing data, etc.): `❌ Snapshot→cache error for TSLA on YYYY-MM-DD: <reason>`
- Thread completion summary: `✅ Nightly historical cache update for YYYY-MM-DD: 31 stored, 4 already cached` — "already cached" = tickers the `HistoricalPrefetch` daemon fetched earlier in the day
- Thread crash: `❌ cache_gap_up_day_for_tickers failed for YYYY-MM-DD: <reason>`
- Thread sleeps 0.5 s between tickers so ~15 s for 30 gappers; most AH universe stocks are skipped by the existing-cache check
- Verify DB was populated: `GET /api/backtest/info` — if today's date appears with a non-zero ticker count, the thread succeeded
- **Missing logs for a past date = that date's data is not in the backtest DB** and will not self-heal; the nightly thread only processes the current day's snapshot

---

## Key constraints

- **Eventlet + single worker**: Do not add CPU-bound blocking work to request handlers. Use daemon threads for background polling (pattern already established in `app.py`).
- **SQLite WAL mode is not set**: Concurrent writes from multiple threads must go through `db_manager` (which opens a new connection per operation via `get_connection()` context manager). Never cache a connection across threads.
- **DAS is a paid desktop app**: Real DAS testing requires the app running on Windows. All automated testing uses `mock_das_server.py`.
- **`DAS_ENABLED = False`** is the default in `app.py`. Changing it to `True` enables live order placement. Never enable it in production without verifying the DAS credentials in `.env`.
- **Schema migrations are additive only.** Never drop or rename columns — the `_migrate_schema()` pattern uses `ALTER TABLE ADD COLUMN` with `except sqlite3.OperationalError: pass`. CREATE TABLE must precede ALTER TABLE within the same function.
- **BrownBot isolation**: Never modify Entry Bot or Exit Bot code when working on BrownBot. They share no state.
- **Polling endpoints**: Do not log `/api/brown-bot/status`, `/api/brown-bot/logs`, `/api/brown-bot/risk-status`, `/api/session/ping`, or `/api/health` at INFO — they are in `_POLLING_PATHS` and logged at DEBUG to prevent log flooding.
