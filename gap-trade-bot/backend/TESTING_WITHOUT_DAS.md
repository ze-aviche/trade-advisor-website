# Testing Swing Bot Without DAS Pro

Use the mock DAS server and DB seeder to test all swing trading features locally — no DAS Trader subscription required.

## Files

| File | Purpose |
|---|---|
| `mock_das_server.py` | Fake DAS Trader TCP server on `127.0.0.1:9800` |
| `seed_test_positions.py` | Seeds SQLite DB with test positions (1 day, 2 swing) |

---

## Step 1 — Start the mock DAS server (Terminal 1)

```bash
cd gap-trade-bot/backend
python mock_das_server.py --scenario mixed
```

**Available scenarios:**

| Scenario | Positions |
|---|---|
| `mixed` | 1 NVDA day (LONG) + 1 AAPL swing (LONG) — default |
| `day` | 2 day positions: TSLA long + AMD short |
| `swing` | 2 swing positions: MSFT long + META long |
| `eod` | Single SPY day position — use to test EOD force-exit |

**Optional drift flag** — controls which direction prices move:

```bash
python mock_das_server.py --scenario mixed --drift target   # prices move toward profit targets
python mock_das_server.py --scenario mixed --drift stop     # prices move toward stop losses
python mock_das_server.py --scenario mixed --drift neutral  # small random oscillation (default)
```

**Interactive keys while the server is running:**

| Key | Effect |
|---|---|
| `t` | Drift prices toward profit targets (triggers `PROFIT_TARGET` exit) |
| `s` | Drift prices toward stop losses (triggers `STOP_LOSS` exit) |
| `n` | Neutral price oscillation |
| `p` | Print current bid/ask/last for all positions |
| `c` | Show which positions have been closed by orders |
| `q` | Quit the server |

---

## Step 2 — Start the Flask backend (Terminal 2)

```bash
cd gap-trade-bot/backend
python app.py
```

---

## Step 3 — Seed the DB for UI display (Terminal 3, run once)

```bash
python seed_test_positions.py
```

Inserts three test positions directly into SQLite:

| Symbol | Style | Side | Entry | Entry Date |
|---|---|---|---|---|
| NVDA | Day | LONG 100 | $480.00 | Today |
| AAPL | Swing | LONG 50 | $175.00 | 5 days ago |
| MSFT | Swing | SHORT 30 | $415.00 | 2 days ago |

To wipe and re-seed:
```bash
python seed_test_positions.py --clear
```

---

## What to test

### Exit Bot tab

1. Click **Start Bot** — the bot connects to the mock server on port 9800.
2. Open **Active Positions** — verify:
   - NVDA shows a blue **DAY** badge, no Days column value
   - AAPL/MSFT show purple **SWING** badges with `5d` / `2d` in the Days column
3. In Terminal 1, press **`t`** — prices drift toward targets every 5 seconds. Watch:
   - NVDA gets closed (day position hits profit target)
   - AAPL/MSFT keep running (swing positions are unaffected)
4. Press **`s`** — prices drift toward stops. Swing stops can be hit.

### Testing EOD — day exits, swing stays

1. Run with the `eod` scenario.
2. In the **Bot Configuration** panel, set EOD exit time to a time ~2 minutes from now.
3. Watch the SPY position close at that time.
4. If you had a swing position open simultaneously, it would remain open.

### Swing Bot Configuration panel

1. On the **Exit Bot** tab, find the purple **Swing Bot Configuration** section.
2. Change profit target % or stop loss %, click **Save Swing Config**.
3. The running bot recalculates open swing position targets immediately.

### Entry Bot tab — Day vs Swing toggle

1. Open the **Entry Bot** tab.
2. Toggle between **Day** and **Swing** — the Volume, Dollar Volume, and Entry Time fields dim when Swing is selected.
3. Fill in a swing entry (symbol + optional setup reason + max hold days) and submit.

---

## Notes

- The mock server keeps the TCP connection alive across commands — the bot behaves identically to real DAS.
- Orders (`NEWORDER`) are accepted immediately and the position is removed from `GET POSITIONS` responses, so the bot cleans it from active tracking.
- Price drift fires every 5 seconds. With `--drift target` and default day-bot config (5% profit target), expect a LONG exit after roughly 17 ticks (~85 seconds).
- Swing positions with 15% targets take ~50 ticks (~4 minutes) to reach with `--drift target`.
