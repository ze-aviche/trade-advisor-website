# BrownBot Configuration Reference

## Config Hot-Reload Behaviour

BrownBot reads config from the DB on every loop iteration — **no restart needed** for any setting change.

| Loop | DB read? | Interval | Change takes effect |
|---|---|---|---|
| Scanner (`_brown_bot_scan_and_enter`) | Yes | 30 s | Next scan cycle |
| Exit loop (`_brown_bot_check_exits`) | Yes | 2 s | Within 2 s |
| RiskManager (slot caps, loss limit) | Rebuilt from scanner read | 30 s | Next scan cycle |
| Monitor thread (`day_max_reentry`) | Via `sess.config` snapshot, refreshed by scanner | ≤ 30 s | Next scan cycle |

**The only thing that does NOT hot-reload is the broker.** `sess.broker` is set at bot-start. If you change broker credentials, stop and restart BrownBot.

---

## Config Fields Reference

### Day Trade — Risk & Sizing

| Field | Default | Description |
|---|---|---|
| `day_position_pct` | 5.0 | Position size as % of account equity |
| `max_concurrent_day` | 5 | Max open day positions at one time |
| `day_max_reentry` | 2 | Max times BrownBot may enter the **same symbol** per session. After N exits, the symbol is locked out for the rest of the day regardless of scanner hits. |
| `max_daily_loss` | -500.0 | Circuit breaker — halts all new entries when `realized_pnl + unrealized_pnl ≤ this value`. Positive input is normalised to negative automatically. |

### Day Trade — Entry Filters (Scanner)

| Field | Default | Description |
|---|---|---|
| `min_gap_pct` | 25.0 | Minimum gap-up % vs prior close |
| `min_price` | 1.0 | Minimum stock price |
| `max_price` | 50.0 | Maximum stock price |
| `min_volume_m` | 10.0 | Minimum pre-market volume (millions of shares) |
| `float_operator` | `>=` | Float filter operator — `>=` (large float) or `<=` (low float) |
| `max_float_m` | 5.0 | Float threshold in millions (used with `float_operator`) |

### Day Trade — Time Gate

| Field | Default | Description |
|---|---|---|
| `day_time_gate_enabled` | True | Whether to restrict entries to a time window |
| `day_time_gate_start` | `09:35` | Earliest entry time (ET) |
| `day_time_gate_end` | `10:30` | Latest entry time (ET) — gap momentum strongest in first hour |

### Day Trade — Intraday Trend Signals (optional filters)

All disabled by default. Each enabled signal must pass before an entry is placed.

| Field | Default | Description |
|---|---|---|
| `day_check_vwap` | False | Skip if price is below session VWAP |
| `day_check_candle` | False | Skip if last 1-min bar is bearish (close < open) |
| `day_max_extension_pct` | 0.0 | Skip if price is more than N% above gap-open price (0 = disabled) |
| `day_check_volume_surge` | False | Skip if current bar volume < 1.5× recent average |
| `day_ai_playbook` | False | Run Claude AI on each candidate before entry. Defers entry one scan cycle. Skips if AI returns `bias=Short / confidence=High`. Overrides stop/target % when confidence is high. |

### Day Trade — Exit Conditions

| Field | Default | Description |
|---|---|---|
| `day_profit_target_pct` | 5.0 | Exit when price rises N% above entry |
| `day_stop_loss_pct` | 2.5 | Exit when price falls N% below entry |
| `day_eod_exit_time` | `15:55` | Flatten all day positions at this time ET (to avoid overnight risk) |
| `day_breakeven_trigger_pct` | 50.0 | Once price reaches N% of the way from entry to target, move stop to entry price (breakeven stop, shown as "BE" badge) |
| `day_trailing_stop_enabled` | False | Activate trailing stop |
| `day_trailing_stop_pct` | 1.5 | Trail distance in % below highest price seen |

### Swing Trade — Sizing & Risk

| Field | Default | Description |
|---|---|---|
| `swing_position_pct` | 3.0 | Position size as % of equity |
| `max_concurrent_swing` | 3 | Max open swing positions at one time |

### Swing Trade — Entry Signals

| Field | Default | Description |
|---|---|---|
| `swing_check_above_sma20` | True | Skip if price is below 20-day SMA |
| `swing_check_ma_cross` | True | Skip if short-term MA is below long-term MA (bearish cross) |
| `swing_check_rsi_range` | False | Require RSI in [`swing_rsi_min`, `swing_rsi_max`] |
| `swing_check_rel_vol` | False | Require relative volume ≥ `swing_rel_vol_min` |

### Swing Trade — Exit Conditions

| Field | Default | Description |
|---|---|---|
| `swing_profit_target_pct` | 15.0 | Profit target % |
| `swing_stop_loss_pct` | 7.0 | Stop loss % |
| `swing_max_hold_days` | 20 | Force-exit after N calendar days |
| `swing_earnings_protection_enabled` | True | Exit before scheduled earnings |
| `swing_earnings_exit_days` | 2 | Exit N days before earnings date |
| `swing_breakeven_trigger_pct` | 50.0 | Move stop to breakeven once N% of the way to target |
| `swing_trailing_stop_enabled` | False | Activate trailing stop |
| `swing_trailing_stop_pct` | 5.0 | Trail distance in % |

---

## Entry Pipeline (Day Trades) — Decision Waterfall

Every 30 s the scanner evaluates gap-up candidates in this order. First failure = skip.

```
1. Symbol in attempted_symbols?          → SKIP (already traded this session)
2. Symbol in eod_flattened_symbols?      → SKIP (EOD-exited, no re-entry today)
3. Outside day_time_gate window?         → SKIP
4. Gap % < min_gap_pct?                  → SKIP
5. Price outside min_price/max_price?    → SKIP
6. Volume < min_volume_m?                → SKIP
7. Float fails float_operator/max_float? → SKIP
8. entry_counts[symbol] ≥ day_max_reentry? → SKIP + permanently lock symbol
9. Intraday signals (VWAP/candle etc)?   → SKIP if any enabled signal fails
10. AI Playbook (if enabled)?            → DEFER one cycle on first encounter
                                         → SKIP if bias=Short/High confidence
11. RiskManager.can_enter()?             → SKIP if circuit breaker open or slots full
12. Buying power ≥ equity × position_pct? → SKIP if insufficient
13. ✅ Place MARKET order via Alpaca
```

---

## Exit Priority Order

The exit loop checks every 2 s per position. First match wins.

```
1. Profit target hit     → SELL (both day and swing)
2. Stop loss hit         → SELL (both; stop moves to entry after breakeven trigger)
3. EOD flatten           → SELL (day only, at day_eod_exit_time ET)
4. Max hold days         → SELL (swing only)
5. Earnings protection   → SELL (swing only, N days before earnings)
```

---

## Re-entry Cap Detail

**Purpose:** Prevents the bot from repeatedly re-entering a stock that is clearly not working that day (e.g., QTEX entered 16 times in one session).

**Mechanics:**
- `entry_counts[symbol]` increments after each successful order placement.
- After each exit the monitor thread checks: if `entry_counts < day_max_reentry`, it removes the symbol from `attempted_symbols` (unlocks for re-entry). Otherwise it stays locked.
- The scanner also enforces the cap independently: if `entry_counts ≥ day_max_reentry` it adds the symbol to `attempted_symbols` permanently for the session.
- The activity log shows: `SKIP QTEX: re-entry cap reached (2/2 entries this session) — locked out`

**Recommended values:**
- `1` — very conservative, one attempt per stock per day
- `2` — default, allows one re-entry after first stop-out
- `3+` — only use if you have a strategy that deliberately scales into a position

**Session P&L tracking per symbol** (`symbol_session_pnl`) is also accumulated in memory on every exit. Visible in the activity log alongside the re-entry unlock/block message.

---

## Sync Behaviour: `sess.config` Snapshot

`sess.config` is a dict that holds the last-read config for the monitor thread (which runs outside the scanner/exit loops and cannot do its own DB read cheaply). It is refreshed by the scanner on every 30 s cycle (`sess.config = config` at the top of `_brown_bot_scan_and_enter`). Fields read from `sess.config` (currently `day_max_reentry`) are therefore at most 30 s stale.

---

## What Requires a Bot Restart

| Change | Restart needed? |
|---|---|
| Any config field | No — picked up within 30 s |
| Broker credentials | **Yes** — `sess.broker` is set once at start |
| Risk manager thresholds | No — RiskManager rebuilt every 30 s |
| Stop/target/EOD time | No — exit loop reads fresh config every 2 s |
| Re-entry cap | No — refreshed via `sess.config` within 30 s |
