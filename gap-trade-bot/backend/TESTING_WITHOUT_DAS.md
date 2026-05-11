# Testing Without DAS Pro

End-to-end test of position entry, tracking, P&L, and logging using a mock DAS server — no DAS Trader subscription required.

## Important: Docker vs local testing are mutually exclusive

**Stop Docker before starting a mock test session.**

```bash
docker-compose down
```

Why:
- Docker maps port `5000` on the host. Running `python app.py` locally also uses port `5000`. They will conflict.
- The mock DAS server binds `127.0.0.1:9800` on the **host machine**. A bot running inside Docker resolves `127.0.0.1` to the container's loopback — it can never reach the mock server. Mock testing only works when Flask is run directly on the host.

**To return to Docker after testing:**
1. Kill the local Flask process and mock server (`Ctrl+C` in both terminals).
2. Confirm port 5000 is free: `netstat -ano | findstr :5000`
3. `docker-compose up --build -d`

---

## How the end-to-end mock flow works

The mock server speaks the same raw DAS TCP protocol as the real server. Both the Entry Bot and Exit Bot connect to it on `127.0.0.1:9800`.

| Bot | What it does |
|---|---|
| **Entry Bot** | Submits a symbol. Polls Level 1 data every second. Enters when conditions are met. |
| **Exit Bot** | Reads `GET POSITIONS` from mock. Monitors prices. Exits when profit target or stop is hit. |

After the Entry Bot places a buy order, the mock server **adds the position** to its state — so the Exit Bot immediately sees it in `GET POSITIONS` and begins managing its exit.

---

## Step 1 — Start the mock DAS server (Terminal 1)

```bash
cd gap-trade-bot/backend
python mock_das_server.py --scenario entry --ramp 15
```

**Scenarios:**

| Scenario | Starting positions |
|---|---|
| `entry` | None — entry bot opens them via order placement ← **use this for E2E testing** |
| `mixed` | NVDA day (LONG) + AAPL swing (LONG) — pre-existing, for exit bot testing |
| `day` | TSLA long + AMD short |
| `swing` | MSFT long + META long |
| `eod` | SPY day position — test EOD force-exit |

**`--ramp SECONDS`** (default 15) — how long before volume rises from 100 K → 3 M shares.
Set lower during development: `--ramp 5`.

**Drift flag — controls price movement after positions are open:**

```bash
python mock_das_server.py --scenario entry --drift target   # prices move toward profit targets
python mock_das_server.py --scenario entry --drift stop     # prices move toward stop losses
```

**Interactive keys while running:**

| Key | Effect |
|---|---|
| `t` | Drift toward profit targets |
| `s` | Drift toward stop losses |
| `n` | Neutral oscillation |
| `v` | Manually trigger volume ramp now (skip the wait) |
| `p` | Print current bid/ask/last for all symbols |
| `c` | Show open and closed positions |
| `q` | Quit |

---

## Step 2 — Start the Flask backend (Terminal 2)

```bash
cd gap-trade-bot/backend
python app.py
```

---

## Step 3 — Start the Exit Bot

1. Open the dashboard in a browser.
2. Go to the **Bot tab** (Exit Bot).
3. Click **Start Bot** — the bot connects to the mock server on port 9800.

---

## Step 4 — Submit a Day Trade entry

1. Go to the **Entry Bot** tab.
2. Make sure **Day** is selected (default).
3. Fill in:
   - **Symbol**: `NVDA`
   - **Volume threshold**: `1` (M shares)
   - **Dollar volume threshold**: `200` (M dollars) — NVDA @ $480 × 1M shares = $480M, so this is met as soon as volume ramps
   - **Entry time**: a time in the past (e.g. `09:30`) so the time gate is already open
   - **Quantity**: `100`
4. Click **Submit**.

**What happens:**
- The Tracking Status panel shows NVDA with three condition indicators (volume, dollar vol, time).
- For the first ~15 seconds, volume is 100 K shares — below the 1 M threshold. All conditions show as pending.
- After ~15 seconds the mock volume ramps to 3 M. All conditions turn green.
- The bot places a `NEWORDER B NVDA SMAT 100 MKT` against the mock server.
- **Entry Bot Active Positions** shows NVDA immediately.
- **Exit Bot Active Positions** also shows NVDA (mock server added it to `GET POSITIONS`).
- The Exit Bot starts monitoring NVDA's price for its profit target and stop loss.

> Press `t` in the mock server terminal to drift prices toward target. Press `s` to drift toward stop.

---

## Step 5 — Submit a Swing Trade entry

1. Stay on the **Entry Bot** tab.
2. Toggle to **Swing**.
3. Fill in:
   - **Symbol**: `AAPL`
   - **Quantity**: `50`
   - **Entry reason** (optional): `bull_flag_breakout`
   - **Max hold days** (optional): `20`
4. Click **Submit**.

**What happens:**
- Swing trades have **no volume or time conditions** — the bot enters immediately at the current price.
- The order is placed within 1–2 seconds.
- AAPL appears in both Entry Bot and Exit Bot active positions.

---

## What each panel shows

| Panel | Source |
|---|---|
| **Entry Bot → Tracking Status** | `tracking_symbols` dict — symbols waiting for conditions |
| **Entry Bot → Active Positions** | `active_positions` dict — positions placed by entry bot |
| **Entry Bot → Debug Logs** | `entry_bot_logs` list — timestamped log of every action |
| **Exit Bot → Active Positions** | `trading_bot.active_positions` — read from DAS `GET POSITIONS` |

Entry Bot and Exit Bot active positions are separate in-memory stores but share the same underlying mock DAS position state.

---

## Testing the Positions History and Trades tabs

These tabs read from the **database**, not from live bot state. To populate them:

```bash
python seed_test_positions.py --clear
```

This seeds historical position data into `positions` and `daily_positions` tables so you can test date-range filtering, position type display, and P&L history without needing the live bot flow.

> The seed script does NOT affect what the Entry Bot or Exit Bot show as "active" — those come from the mock server.

---

## Notes

- The mock server handles **multiple simultaneous TCP connections** — Entry Bot and Exit Bot each open their own connection and operate independently.
- `NEWORDER B {symbol}` from the Entry Bot **opens** a position in the mock. `NEWORDER S {symbol}` from the Exit Bot **closes** it.
- Price drift fires every 5 seconds. With `--drift target` and a 5% profit target, expect an exit after roughly 17 ticks (~85 seconds).
- Swing positions with a 15% target take ~50 ticks (~4 minutes) to reach.
