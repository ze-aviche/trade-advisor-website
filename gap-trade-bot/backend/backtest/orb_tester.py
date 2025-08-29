"""
Opening-Range Breakout (ORB) Backtester
---------------------------------------
- Consumes your daily gappers table (DataFrame or SQL query)
- Fetches 1‑minute intraday bars from Polygon.io for each (ticker, date)
- Simulates a long ORB breakout with configurable rules
- Outputs trades + daily/overall stats

Notes
-----
• Educational example; validate before using with real money.
• Requires a Polygon API key (Starter/Developer+ for full historical intraday)
• Caches downloaded minute bars as Parquet under ./intraday_cache to avoid refetching

How the strategy works (defaults)
---------------------------------
1) Build a 5‑minute opening range from 09:30:00–09:34:59 (US/Eastern).
2) Once the range is set (>= 09:35), go LONG when a 1‑min bar CLOSES > opening‑range high (ORH).
3) Entry price = breakout candle close + slippage.
4) Stop = opening‑range low (ORL) – stop_buffer_pct.
5) Position size = risk_per_trade_usd / (entry – stop).
6) Exit rules (first event wins):
   a) Take‑profit at take_profit_R × initial_risk (e.g., 2R)
   b) Time stop at time_exit (default 11:00:00)
   c) End‑of‑day liquidation at 15:59

You can switch to a trailing stop or different exits by tweaking `manage_position`.
"""
from __future__ import annotations

import os
import math
import time
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

# Ensure parquet support is available
try:
    import pyarrow
except ImportError:
    print("Warning: pyarrow not found. Parquet caching will not work.")
    print("Install with: pip install pyarrow")

# ------------------------
# Configuration
# ------------------------
@dataclass
class Config:
    polygon_api_key: str = os.getenv("POLYGON_API_KEY", "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT")
    # Cache folder for 1-min bars
    cache_dir: Path = Path("intraday_cache")
    # Rate-limit safety
    sleep_between_calls_sec: float = 0.25
    max_retries: int = 3

    # Trading session
    session_start: str = "09:30:00"  # regular hours start
    session_end: str = "16:00:00"    # regular hours end

    # Opening range window (minutes from 09:30)
    orb_minutes: int = 5

    # Strategy params
    slippage_cents: float = 0.01            # add to entry price to simulate fills
    fees_per_share: float = 0.0005          # simplistic fee model
    stop_buffer_pct: float = 0.0            # e.g., 0.001 = 0.1% below ORL
    risk_per_trade_usd: float = 100.0       # fixed $ risk per trade
    take_profit_R: float = 2.0              # exit at 2R
    time_exit: str = "11:00:00"             # time-based exit if still open

    # Filters
    min_price: float = 1.0
    min_dollar_volume_m: float = 1.0        # use your gappers column if available

    # Dataframe column names expected from gappers table
    col_date: str = "date"
    col_ticker: str = "ticker"
    col_open: str = "today_open"
    col_close: str = "today_close"
    col_high: str = "today_high"
    col_low: str = "today_low"
    col_dollar_vol_m: str = "highest_dollar_volume_m"  # optional

CFG = Config()
CFG.cache_dir.mkdir(exist_ok=True)

# ------------------------
# Utilities
# ------------------------

def _session_bounds(date_str: str, start: str, end: str) -> Tuple[str, str]:
    return f"{date_str}T{start}", f"{date_str}T{end}"


def fetch_polygon_1min(ticker: str, date_str: str, cfg: Config = CFG) -> pd.DataFrame:
    """Fetch 1‑minute bars for a single ticker/date from Polygon, with basic caching.
    Returns DataFrame with columns: timestamp, open, high, low, close, volume
    """
    cache_path = cfg.cache_dir / f"{ticker}_{date_str}.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    start_iso, end_iso = _session_bounds(date_str, cfg.session_start, cfg.session_end)
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/min/"
        f"{start_iso}/{end_iso}?adjusted=true&sort=asc&limit=50000&apiKey={cfg.polygon_api_key}"
    )

    for attempt in range(cfg.max_retries):
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if "results" not in data:
                return pd.DataFrame(columns=["timestamp","open","high","low","close","volume"])  # empty

            df = pd.DataFrame(data["results"]).rename(columns={
                "t":"timestamp_ms", "o":"open", "h":"high", "l":"low", "c":"close", "v":"volume"
            })
            df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms")
            df = df[["timestamp","open","high","low","close","volume"]]
            df.to_parquet(cache_path, index=False)
            time.sleep(cfg.sleep_between_calls_sec)
            return df
        else:
            time.sleep(1.0 + attempt)

    # give up
    return pd.DataFrame(columns=["timestamp","open","high","low","close","volume"])  # empty


def build_opening_range(df_1m: pd.DataFrame, date_str: str, cfg: Config = CFG) -> Tuple[float, float, pd.Timestamp]:
    """Compute ORH/ORL from first cfg.orb_minutes minutes after 09:30."""
    if df_1m.empty:
        return np.nan, np.nan, pd.NaT

    date = pd.to_datetime(date_str).date()
    start_ts = pd.Timestamp(f"{date} {cfg.session_start}")
    end_ts = start_ts + pd.Timedelta(minutes=cfg.orb_minutes)

    mask = (df_1m["timestamp"] >= start_ts) & (df_1m["timestamp"] < end_ts)
    or_bars = df_1m.loc[mask]
    if or_bars.empty:
        return np.nan, np.nan, pd.NaT

    orh = float(or_bars["high"].max())
    orl = float(or_bars["low"].min())
    or_ready_ts = end_ts  # earliest time a breakout is allowed
    return orh, orl, or_ready_ts


@dataclass
class Trade:
    date: str
    ticker: str
    entry_time: Optional[pd.Timestamp]
    exit_time: Optional[pd.Timestamp]
    entry: Optional[float]
    stop: Optional[float]
    shares: int
    exit_price: Optional[float]
    pnl: float
    R: float
    reason: str
    orh: float
    orl: float
    notes: str = ""


def simulate_orb_long(df_1m: pd.DataFrame, date_str: str, ticker: str, cfg: Config = CFG) -> Optional[Trade]:
    """Simulate a single ORB long trade for one ticker/day. Returns a Trade or None if no setup."""
    if df_1m.empty:
        return None

    # Basic filters on first bar price (optional)
    first_bar = df_1m.iloc[0]
    if first_bar["open"] < cfg.min_price:
        return None

    # Opening range
    orh, orl, or_ready_ts = build_opening_range(df_1m, date_str, cfg)
    if not np.isfinite(orh) or not np.isfinite(orl):
        return None

    # Find breakout: first 1‑min bar CLOSE > ORH after or_ready_ts
    trade = None
    for idx, row in df_1m.iterrows():
        ts = row["timestamp"]
        if ts < or_ready_ts:
            continue
        if row["close"] > orh:
            # Entry at close + slippage
            entry = float(row["close"]) + cfg.slippage_cents
            stop = max(1e-4, orl * (1 - cfg.stop_buffer_pct))
            risk_per_share = max(1e-4, entry - stop)
            shares = max(0, int(math.floor(cfg.risk_per_trade_usd / risk_per_share)))
            if shares <= 0:
                return None

            entry_time = ts
            target = entry + cfg.take_profit_R * risk_per_share

            # Manage position forward in time, including current bar (since we entered on close)
            exit_price = None
            exit_time = None
            reason = ""

            # Iterate subsequent bars for exits
            for j in range(idx + 1, len(df_1m)):
                b = df_1m.iloc[j]
                bh, bl, bc = float(b["high"]), float(b["low"]), float(b["close"])
                ts2 = b["timestamp"]

                # 1) Hard stop (if low touches/breaks stop)
                if bl <= stop:
                    exit_price = stop - cfg.slippage_cents  # assume slight adverse slip
                    exit_time = ts2
                    reason = "stop"
                    break

                # 2) Take profit target
                if bh >= target:
                    exit_price = target  # filled at target
                    exit_time = ts2
                    reason = "target"
                    break

                # 3) Time exit
                time_exit_ts = pd.Timestamp(f"{pd.to_datetime(date_str).date()} {cfg.time_exit}")
                if ts2 >= time_exit_ts:
                    exit_price = bc - cfg.slippage_cents
                    exit_time = ts2
                    reason = "time_exit"
                    break

            # If still open by end of day, liquidate
            if exit_price is None:
                last = df_1m.iloc[-1]
                exit_price = float(last["close"]) - cfg.slippage_cents
                exit_time = last["timestamp"]
                reason = "eod"

            fees = cfg.fees_per_share * shares
            pnl = (exit_price - entry) * shares - fees
            R = pnl / cfg.risk_per_trade_usd if cfg.risk_per_trade_usd > 0 else np.nan

            trade = Trade(
                date=date_str,
                ticker=ticker,
                entry_time=entry_time,
                exit_time=exit_time,
                entry=entry,
                stop=stop,
                shares=shares,
                exit_price=exit_price,
                pnl=pnl,
                R=R,
                reason=reason,
                orh=orh,
                orl=orl,
                notes="ORB long"
            )
            break

    return trade


# ------------------------
# Backtest runner
# ------------------------

def run_backtest(gappers_df: pd.DataFrame, cfg: Config = CFG) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run the ORB backtest across a gappers universe.
    gappers_df must have at least [date, ticker]. Additional filters are optional.
    Returns (trades_df, summary_df)
    """
    required = {cfg.col_date, cfg.col_ticker}
    if not required.issubset(gappers_df.columns):
        raise ValueError(f"gappers_df must contain columns: {required}")

    trades: List[Trade] = []
    # Sort by date to make debugging deterministic
    gappers_df = gappers_df.sort_values([cfg.col_date, cfg.col_ticker]).reset_index(drop=True)

    for _, row in gappers_df.iterrows():
        date_str = str(row[cfg.col_date])
        ticker = str(row[cfg.col_ticker])

        # Optional universe filters
        if cfg.col_open in gappers_df.columns and row.get(cfg.col_open, np.nan) is not np.nan:
            if row[cfg.col_open] < cfg.min_price:
                continue
        if cfg.col_dollar_vol_m in gappers_df.columns and row.get(cfg.col_dollar_vol_m, np.nan) is not np.nan:
            if row[cfg.col_dollar_vol_m] < cfg.min_dollar_volume_m:
                continue

        df_1m = fetch_polygon_1min(ticker, date_str, cfg)
        if df_1m.empty:
            continue

        trade = simulate_orb_long(df_1m, date_str, ticker, cfg)
        if trade:
            trades.append(trade)

    if not trades:
        return pd.DataFrame(), pd.DataFrame()

    trades_df = pd.DataFrame([asdict(t) for t in trades])

    # Daily and overall stats
    daily = trades_df.groupby("date").agg(
        n_trades=("ticker", "count"),
        pnl=("pnl", "sum"),
        R=("R", "sum"),
        winrate=("pnl", lambda x: (x > 0).mean() if len(x) else np.nan),
        avg_R=("R", "mean")
    ).reset_index()

    overall = pd.DataFrame({
        "metric": [
            "trades", "winrate", "total_PnL", "total_R", "avg_R", "median_R", "avg_$per_trade"
        ],
        "value": [
            len(trades_df),
            float((trades_df["pnl"] > 0).mean()),
            float(trades_df["pnl"].sum()),
            float(trades_df["R"].sum()),
            float(trades_df["R"].mean()),
            float(trades_df["R"].median()),
            float(trades_df["pnl"].mean()),
        ]
    })

    return trades_df, overall


# ------------------------
# Example usage (uncomment and adapt)
# ------------------------
if __name__ == "__main__":
    # Example: build a tiny gappers DataFrame from your sample
    data = [
        {"date":"2025-03-25", "ticker":"ALMS", "today_open":5.77, "highest_dollar_volume_m":75.99},
        {"date":"2025-03-25", "ticker":"DM", "today_open":3.71, "highest_dollar_volume_m":851.65},
        {"date":"2025-03-25", "ticker":"DATS", "today_open":3.86, "highest_dollar_volume_m":244.13},
    ]
    gappers_df = pd.DataFrame(data)

    # IMPORTANT: set your Polygon API key
    if CFG.polygon_api_key in (None, "", "YOUR_POLYGON_API_KEY"):
        raise SystemExit("Please set POLYGON_API_KEY environment variable or edit Config.polygon_api_key")

    trades_df, overall = run_backtest(gappers_df, CFG)

    out_dir = Path("./backtest_output")
    out_dir.mkdir(exist_ok=True)
    trades_path = out_dir / "orb_trades.csv"
    overall_path = out_dir / "orb_overall.csv"

    trades_df.to_csv(trades_path, index=False)
    overall.to_csv(overall_path, index=False)

    print(f"Saved trades to {trades_path}")
    print(f"Saved summary to {overall_path}")
