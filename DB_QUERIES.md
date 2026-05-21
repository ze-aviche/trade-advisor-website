# DB Query Reference

Paste any query into the **Admin → SQLite Query Utility**. Only `SELECT` and `PRAGMA` are permitted.

---

## Schema / Housekeeping

```sql
-- All tables
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name
```

```sql
-- Row count for every table
SELECT 'users'                  AS tbl, COUNT(*) AS rows FROM users UNION ALL
SELECT 'sessions',                       COUNT(*) FROM sessions UNION ALL
SELECT 'trades',                         COUNT(*) FROM trades UNION ALL
SELECT 'daily_positions',                COUNT(*) FROM daily_positions UNION ALL
SELECT 'brown_positions',                COUNT(*) FROM brown_positions UNION ALL
SELECT 'gap_up_snapshots',               COUNT(*) FROM gap_up_snapshots UNION ALL
SELECT 'swing_daily_picks',              COUNT(*) FROM swing_daily_picks UNION ALL
SELECT 'swing_screener_history',         COUNT(*) FROM swing_screener_history UNION ALL
SELECT 'swing_daily_bars',               COUNT(*) FROM swing_daily_bars UNION ALL
SELECT 'brown_bot_config',               COUNT(*) FROM brown_bot_config UNION ALL
SELECT 'brown_watchlist',                COUNT(*) FROM brown_watchlist UNION ALL
SELECT 'brown_orders',                   COUNT(*) FROM brown_orders UNION ALL
SELECT 'email_leads',                    COUNT(*) FROM email_leads
```

```sql
-- Database file size (MB)
SELECT ROUND(page_count * page_size / 1024.0 / 1024.0, 2) AS size_mb
FROM pragma_page_count(), pragma_page_size()
```

```sql
-- Column names for any table (replace 'trades')
PRAGMA table_info(trades)
```

---

## Users & Subscriptions

```sql
-- All users
SELECT id, username, email, system_role, subscription_tier, subscription_status,
       is_active, created_at, last_login
FROM users ORDER BY id
```

```sql
-- Count by subscription tier
SELECT subscription_tier, COUNT(*) AS count FROM users GROUP BY subscription_tier
```

```sql
-- Trial users and days remaining
SELECT id, username, email, trial_expires_at, trial_reminder_sent,
       ROUND(JULIANDAY(trial_expires_at) - JULIANDAY('now'), 1) AS days_left
FROM users
WHERE trial_expires_at IS NOT NULL
ORDER BY trial_expires_at
```

```sql
-- Staff accounts
SELECT id, username, email, system_role, last_login
FROM users WHERE system_role IS NOT NULL ORDER BY system_role
```

```sql
-- Users active in the last 7 days
SELECT id, username, email, subscription_tier, last_login
FROM users WHERE last_login >= DATE('now', '-7 days') ORDER BY last_login DESC
```

```sql
-- Active sessions (not yet expired)
SELECT username, created_at, expires_at,
       ROUND((JULIANDAY(expires_at) - JULIANDAY('now')) * 24, 1) AS hours_left
FROM sessions ORDER BY expires_at DESC LIMIT 50
```

```sql
-- Landing page email leads
SELECT email, source, created_at, welcome_sent FROM email_leads ORDER BY created_at DESC
```

---

## P&L Diagnostics

```sql
-- Orphan buys: BrownBot entries with no matching sell (position exited but trade not recorded)
SELECT t.symbol, t.trade_date, t.quantity, t.price, t.order_id, t.position_type
FROM trades t
WHERE t.side = 'B' AND t.source = 'brownbot'
  AND NOT EXISTS (
    SELECT 1 FROM trades s
    WHERE s.symbol = t.symbol
      AND s.side IN ('S','SS')
      AND s.source = 'brownbot'
      AND s.trade_date >= t.trade_date
  )
ORDER BY t.trade_date DESC, t.symbol
```

```sql
-- Full round-trips for a symbol — edit RGTI
SELECT symbol, side, trade_date, quantity, price, pnl, source, order_id, trade_time
FROM trades
WHERE symbol = 'RGTI'
ORDER BY trade_date, trade_time
```

```sql
-- Symbols with buys but zero realized P&L (possible missing exit trades)
SELECT b.symbol,
       b.trade_date,
       b.quantity                         AS buy_qty,
       b.price                            AS buy_price,
       COALESCE(SUM(s.pnl), 0)           AS recorded_pnl,
       COUNT(s.id)                        AS sell_count
FROM trades b
LEFT JOIN trades s ON s.symbol = b.symbol
                   AND s.side IN ('S','SS')
                   AND s.source = 'brownbot'
                   AND s.trade_date >= b.trade_date
WHERE b.side = 'B' AND b.source = 'brownbot'
GROUP BY b.symbol, b.trade_date, b.quantity, b.price
ORDER BY b.trade_date DESC
```

---

## Trades & P&L

```sql
-- All trades today
SELECT id, symbol, side, quantity, price, pnl, position_type, trade_time
FROM trades WHERE trade_date = DATE('now') ORDER BY trade_time DESC
```

```sql
-- Daily P&L — last 30 days
SELECT trade_date,
       COUNT(*)                                                       AS fills,
       ROUND(SUM(pnl), 2)                                            AS total_pnl,
       ROUND(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 2)         AS gross_profit,
       ROUND(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 2)         AS gross_loss
FROM trades
WHERE trade_date >= DATE('now', '-30 days')
GROUP BY trade_date ORDER BY trade_date DESC
```

```sql
-- Running cumulative P&L by day
SELECT trade_date,
       ROUND(SUM(pnl), 2)                                          AS daily_pnl,
       ROUND(SUM(SUM(pnl)) OVER (ORDER BY trade_date), 2)          AS cumulative_pnl
FROM trades GROUP BY trade_date ORDER BY trade_date
```

```sql
-- P&L by symbol (all time)
SELECT symbol,
       COUNT(*)                                              AS fills,
       ROUND(SUM(pnl), 2)                                   AS total_pnl,
       ROUND(AVG(pnl), 2)                                   AS avg_pnl,
       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)             AS wins,
       SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END)             AS losses
FROM trades GROUP BY symbol ORDER BY total_pnl DESC
```

```sql
-- P&L split: day trades vs swing trades
SELECT position_type,
       COUNT(*)                                              AS fills,
       ROUND(SUM(pnl), 2)                                   AS total_pnl,
       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)             AS wins,
       SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END)             AS losses
FROM trades GROUP BY position_type
```

```sql
-- Top 10 best trades
SELECT symbol, trade_date, side, quantity, price, pnl, position_type
FROM trades ORDER BY pnl DESC LIMIT 10
```

```sql
-- Top 10 worst trades
SELECT symbol, trade_date, side, quantity, price, pnl, position_type
FROM trades ORDER BY pnl ASC LIMIT 10
```

```sql
-- Trades for a specific symbol (edit NVDA)
SELECT id, trade_date, side, quantity, price, pnl, trade_time, position_type
FROM trades WHERE symbol = 'NVDA' ORDER BY trade_time DESC LIMIT 100
```

```sql
-- Trades in a custom date range (edit dates)
SELECT trade_date, symbol, side, quantity, price, pnl, position_type
FROM trades
WHERE trade_date BETWEEN '2026-01-01' AND '2026-05-20'
ORDER BY trade_date DESC, trade_time DESC LIMIT 200
```

---

## BrownBot

```sql
-- Active BrownBot positions (open only)
SELECT position_id, symbol, position_type, avg_entry_price, entry_price, quantity,
       profit_target, stop_loss, unrealized_pnl, unrealized_pnl_pct,
       current_price, entry_time, trade_date
FROM brown_positions WHERE status IS NULL OR status = 'open'
ORDER BY entry_time DESC
```

```sql
-- Today's closed positions with realized P&L
SELECT symbol, position_type, avg_entry_price, exit_price, quantity,
       realized_pnl, realized_pnl_pct, exit_reason, entry_time, exit_time
FROM brown_positions
WHERE status = 'closed' AND trade_date = DATE('now','localtime')
ORDER BY exit_time DESC
```

```sql
-- P&L summary by ticker for today (realized + unrealized)
SELECT symbol,
       ROUND(SUM(realized_pnl), 2)                                        AS realized_pnl,
       ROUND(SUM(CASE WHEN status = 'open' THEN unrealized_pnl ELSE 0 END), 2) AS unrealized_pnl,
       COUNT(*)                                                             AS positions
FROM brown_positions WHERE trade_date = DATE('now','localtime')
GROUP BY symbol ORDER BY realized_pnl DESC
```

```sql
-- All BrownBot orders today (immutable order log)
SELECT order_id, position_id, symbol, side, order_type, position_type,
       submitted_qty, submitted_price, filled_qty, filled_price,
       status, exit_reason, submitted_at, filled_at
FROM brown_orders WHERE trade_date = DATE('now','localtime')
ORDER BY submitted_at DESC
```

```sql
-- Pending (unfilled) orders
SELECT order_id, symbol, side, order_type, submitted_qty, submitted_price,
       submitted_at
FROM brown_orders WHERE status = 'pending'
ORDER BY submitted_at DESC
```

```sql
-- Full BrownBot config
SELECT * FROM brown_bot_config LIMIT 1
```

```sql
-- BrownBot watchlist
SELECT symbol, trade_type, note, added_at FROM brown_watchlist ORDER BY added_at DESC
```

---

## Gap-Up Snapshots

```sql
-- Today's gap-up scan
SELECT ticker, company_name, price, gap_percent, volume, sector, data_source, created_at
FROM gap_up_snapshots WHERE date = DATE('now') ORDER BY gap_percent DESC
```

```sql
-- Most frequently appearing tickers (all time)
SELECT ticker,
       COUNT(*)                          AS appearances,
       ROUND(AVG(gap_percent), 1)        AS avg_gap_pct,
       MAX(date)                         AS last_seen
FROM gap_up_snapshots GROUP BY ticker ORDER BY appearances DESC LIMIT 50
```

```sql
-- Daily gap-up summary
SELECT date,
       COUNT(*)                          AS tickers,
       ROUND(AVG(gap_percent), 1)        AS avg_gap,
       ROUND(MAX(gap_percent), 1)        AS max_gap
FROM gap_up_snapshots GROUP BY date ORDER BY date DESC LIMIT 30
```

```sql
-- Large gap-ups (>20%) in last 30 days
SELECT date, ticker, price, gap_percent, volume, sector
FROM gap_up_snapshots
WHERE gap_percent >= 20 AND date >= DATE('now', '-30 days')
ORDER BY gap_percent DESC LIMIT 100
```

---

## Swing AI Picks

```sql
-- Swing picks history — all dates
SELECT date, candidates_scanned, created_at FROM swing_daily_picks ORDER BY date DESC
```

```sql
-- Screener history with grades — last 30 days
SELECT date, ticker, ai_grade, ai_bias, price, rsi14, above_sma20, was_entered, entry_price
FROM swing_screener_history
WHERE date >= DATE('now', '-30 days')
ORDER BY date DESC, ai_grade ASC LIMIT 200
```

```sql
-- Grade A picks that BrownBot actually entered
SELECT date, ticker, price, entry_price, ai_grade, ai_bias, ai_summary
FROM swing_screener_history
WHERE ai_grade = 'A' AND was_entered = 1
ORDER BY date DESC LIMIT 100
```

```sql
-- Grade breakdown across all screener history
SELECT ai_grade, ai_bias, COUNT(*) AS count
FROM swing_screener_history
GROUP BY ai_grade, ai_bias ORDER BY ai_grade, ai_bias
```

```sql
-- OHLCV bar cache coverage
SELECT COUNT(DISTINCT ticker) AS tickers_cached,
       COUNT(*)               AS total_bars,
       MIN(date)              AS oldest_bar,
       MAX(date)              AS newest_bar
FROM swing_daily_bars
```

---

## Daily Position Snapshots

```sql
-- Most recent snapshot
SELECT symbol, quantity, avg_cost, realized, unrealized, snapshot_date
FROM daily_positions ORDER BY snapshot_date DESC LIMIT 50
```

```sql
-- History for a specific symbol (edit TSLA)
SELECT snapshot_date, quantity, avg_cost, realized, unrealized
FROM daily_positions WHERE symbol = 'TSLA' ORDER BY snapshot_date DESC LIMIT 30
```
