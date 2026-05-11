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

## Architecture overview

### Single-process Flask + SocketIO backend
`app.py` (~5 100 lines) is the entire backend. It runs as one process with eventlet green threads. There is no task queue, no separate worker process. Background loops (DAS monitor, trial reminders) run as daemon threads started at app boot.

### DAS Trader integration
DAS Trader Pro is the broker execution layer. The bot communicates via a **raw TCP socket** to `127.0.0.1:9800`. All commands are ASCII strings terminated with `\r\n` (e.g. `GET POSITIONS\r\n`, `SB NVDA Lv1\r\n`, `NEWORDER <id> B NVDA SMAT 100 MKT\r\n`).

`DAS_ENABLED` in `app.py` is the global feature flag (currently `False`). When `False`, the Exit Bot and scheduled DAS sync are also disabled regardless of their own state.

The shared DAS socket is in `bot/trading_bot.py → Connection`. The entry bot (`app.py`) and exit bot (`TradingBot`) each open **separate TCP connections** to DAS. Thread safety is enforced by `Connection._lock` (a `threading.Lock`).

`_send_das_script()` in `app.py` routes through the exit bot's connection first (preferred), then falls back to a direct socket (`_das_direct`). Never use the `cmdapi/CMDAPI_PYTHON.py` class for new code — it is not thread-safe.

### Three-bot design
| Bot | Where | Trigger | Loop interval |
|-----|-------|---------|---------------|
| **Entry Bot** | `app.py` (`submit_entry_parameters`, `_tracking_loop`) | User submits symbol + params via UI | 1 s (day), immediate (swing) |
| **Exit Bot** | `bot/trading_bot.py → TradingBot` | User clicks "Start Bot" in UI | 5 s (day), 60 s (swing) |
| **BrownBot** | `app.py` (`_brown_bot_scanner_loop`, `_brown_bot_exit_loop`) | User clicks "Start" in BrownBot tab | Scanner: 30 s · Exits: 2 s |

Entry bot state (`tracking_symbols`, `active_positions`, `entry_bot_logs`) is in-memory global dicts in `app.py`. Exit bot state is in `TradingBot` instance attributes. Both persist positions to the SQLite DB via `database.py → db_manager`.

BrownBot state (`_brown_bot_active_positions`, `_brown_bot_stats`, `_brown_bot_logs`) lives in module-level globals in `app.py`. BrownBot positions are **not** in the `positions` table — they live in memory and are written to `trades` on exit only.

### Position lifecycle
1. Entry bot checks `check_entry_conditions()` — volume, dollar-volume, time gates (day) or immediate (swing)
2. `enter_position()` sends `NEWORDER B` and writes to `active_positions` + DB
3. Exit bot reads `GET POSITIONS`, subscribes to Level 1, calls `ExitConditionChecker.check_exit_conditions()` every loop
4. `OrderManager.close_position()` sends `NEWORDER S` (or `B` for shorts) and writes the closed trade to DB

### Database (`database.py`)
Single SQLite file. Location is `DATABASE_PATH` env var (Render persistent disk) or `backend/trading_advisor.db` locally.

Schema is managed by `init_database()` + `_migrate_schema()` (additive `ALTER TABLE` migrations — safe to run repeatedly). Key tables:
- `users`, `sessions` — auth
- `positions` — current live positions (upserted on every DAS sync)
- `daily_positions` — daily snapshots of positions (append-only, one row per symbol per day)
- `trades` — individual fills from DAS; BrownBot writes a closing record here on exit
- `gap_up_snapshots` — daily gap-up scan results
- `swing_bot_config` — per-user swing exit settings
- `brown_bot_config` — BrownBot day/swing targets, risk limits, scanner thresholds (one row per user)
- `brown_watchlist` — manual symbols added by the user for BrownBot to trade

`db_manager` is a module-level singleton imported everywhere.

### Authentication
Session-token based (not JWT). Tokens are in `Authorization: Bearer <token>` header or `session_token` cookie. `require_auth` decorator in `auth.py` sets `request.user` for the current request. `require_role(*roles)` checks `system_role` from the `users` table.

System roles: `super_admin`, `dev_master`, `bot_admin`. First registered user is auto-promoted to `super_admin`.

### Frontend
Vanilla JS + Vue 3 (CDN, no build step) + Tailwind CSS (CDN). All logic is in `frontend/app.js`. Tabs are driven by `currentTab` Vue data property. Socket.IO is used for real-time push from the backend. No npm, no bundler — just open `index.html` or let Flask serve it.

### Gap-up detection
`gap_up_detector.py` uses the Polygon REST API. Results are cached in memory (`gap_up_cache.py`) with a TTL and also persisted to `gap_up_snapshots` table. `yfinance` is the fallback when the Polygon plan doesn't include the gainers endpoint.

### External services
| Service | Purpose | Feature flag / env var |
|---------|---------|----------------------|
| Polygon API | Market data, gap-up scan | `POLYGON_API_KEY` |
| Anthropic Claude | AI trade analysis (`ai_agent.py`) | `ANTHROPIC_API_KEY` |
| Stripe | Subscription billing | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*` |
| Gmail SMTP | Email notifications, trial reminders | `CONTACT_EMAIL_FROM`, `GMAIL_APP_PASSWORD` |
| Sentry | Error monitoring | `SENTRY_DSN` (optional — disabled if unset) |

### Deployment
Render.com. The persistent disk mounts at `/data`; set `DATABASE_PATH=/data/trading_advisor.db`. The Dockerfile is in `gap-trade-bot/` (not the repo root). `docker-compose.yml` is for local use only.

### BrownBot

BrownBot is a fully autonomous bot that finds its own candidates, gates entries through a portfolio risk manager, and exits positions without manual intervention. It is gated to the **Yogi** subscription tier and operates independently of the Entry Bot and Exit Bot — never modify those bots when working on BrownBot.

#### Runtime threads
Two daemon threads are started together on `POST /api/brown-bot/start` and stopped on `POST /api/brown-bot/stop`:

| Thread | Function | Interval |
|--------|----------|----------|
| `BrownBotScanner` | `_brown_bot_scanner_loop()` → `_brown_bot_scan_and_enter()` | 30 s |
| `BrownBotExits` | `_brown_bot_exit_loop()` → `_brown_bot_check_exits()` | 2 s (swing-specific checks every 60 s) |

The running flag `_brown_bot_running` is the only shutdown signal — both loops poll it and exit cleanly.

#### Entry pipeline (`_brown_bot_scan_and_enter`)
1. Fetch gap-up candidates from `get_gap_up_stocks_for_frontend()`, filter by config thresholds (`min_gap_pct`, `min_price`, `max_price`, `min_volume_m`).
2. Merge with `brown_watchlist` from DB.
3. **Day trades** (scanner hits + watchlist `trade_type='day'`): time-gated to 09:35–10:30 ET.
4. **Swing trades** (watchlist `trade_type='swing'`): run `_check_swing_signal()` first.
5. All candidates: `RiskManager.can_enter()` check before any order.
6. `_brown_enter_position()` → `place_das_order()` → store in `_brown_bot_active_positions`.

#### Swing signal check (`_check_swing_signal`)
Two-stage gate to balance quality vs. API cost:
- **Stage 1** (cheap, always): `close > SMA20` + optional volume surge (1.5× 10-bar avg). Score 0.60–0.75. Uses `_ai_agent._get_technical_analysis()` (Polygon bars).
- **Stage 2** (expensive, only when score < 0.8): `_ai_agent.process_message()` asks Claude for BUY/HOLD. BUY → score 0.85, HOLD → score 0.45.
- Enter if final score ≥ 0.70.

#### Risk manager (`bot/risk_manager.py → RiskManager`)
Instantiated from `brown_bot_config` when the bot starts. `can_enter(symbol, position_type, active_positions)` returns `(allowed, reason)` and enforces:
- `max_daily_loss`: circuit breaker — halts all new entries if today's realized P&L ≤ threshold.
- `max_concurrent_day` / `max_concurrent_swing`: slot caps.

The `GET /api/brown-bot/risk-status` endpoint returns a live snapshot even before the bot is started (reads config + today's P&L from DB directly).

#### Exit pipeline (`_brown_bot_check_exits`)
For each position in `_brown_bot_active_positions`:
1. Fetch current price via `_brown_get_current_price()` → `get_real_stock_data()` → `SB {sym} Lv1`.
2. Update `unrealized_pnl` in the shared dict.
3. **Breakeven stop**: once price reaches `{type}_breakeven_trigger_pct`% of the way from entry to target, move stop to entry price (sets `_at_breakeven` flag; shown as "BE" badge in UI).
4. Exit conditions checked in order: profit target → stop loss → EOD flatten (day, at `day_eod_exit_time` ET) → max hold days (swing) → earnings protection (swing, queries Nasdaq calendar via `_ai_agent._get_earnings_calendar()`).
5. `_brown_close_position()` → `place_das_order(S)` → `db_manager.add_trade()` → remove from dict.

#### Position discriminator
`position_type` field in `_brown_bot_active_positions` is `'day'` or `'swing'`. BrownBot positions are **never** written to the `positions` table (which is owned by the DAS sync / Exit Bot). The Exit Bot ignores them; BrownBot's exit loop manages them exclusively.

#### API endpoints (`/api/brown-bot/*`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/status` | — | Running state, stats, active positions list |
| POST | `/start` | ✓ | Instantiate RiskManager, launch threads |
| POST | `/stop` | ✓ | Clear flag, join threads |
| GET/POST | `/config` | ✓ | Read / write `brown_bot_config` |
| GET | `/logs` | ✓ | Last 100 activity log entries (reversed) |
| GET | `/risk-status` | ✓ | Live risk snapshot (daily P&L, slots, circuit breaker) |
| GET | `/candidates` | ✓ | Filtered gap-ups + watchlist merged |
| GET/POST | `/watchlist` | ✓ | List / add watchlist symbols |
| DELETE | `/watchlist/<symbol>` | ✓ | Remove watchlist symbol |

## Key constraints

- **Eventlet + single worker**: Do not add CPU-bound blocking work to request handlers. Use daemon threads for background polling (pattern already established in `app.py`).
- **SQLite WAL mode is not set**: Concurrent writes from multiple threads must go through `db_manager` (which opens a new connection per operation via `get_connection()` context manager). Never cache a connection across threads.
- **DAS is a paid desktop app**: Real DAS testing requires the app running on Windows. All automated testing uses `mock_das_server.py`.
- **`DAS_ENABLED = False`** is the default in `app.py`. Changing it to `True` enables live order placement. Never enable it in production without verifying the DAS credentials in `.env`.
- **Schema migrations are additive only.** Never drop or rename columns — the `_migrate_schema()` pattern uses `ALTER TABLE ADD COLUMN` with `except sqlite3.OperationalError: pass`.
