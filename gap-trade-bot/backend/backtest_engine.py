"""
Backtest engine for gap-up strategy — Day Trade and Swing Trade modes.

Day backtest
  Candidates : gap_data filtered by min_gap, price, volume
  Entry      : first 1-min bar at-or-after entry_start_time that passes all
               configured signals (VWAP, candle, extension, volume surge)
  Exit       : stop / target / EOD cutoff on subsequent 1-min bars
  Fallback   : daily OHLC from gap_data when no 1-min bars exist

Swing backtest
  Candidates : gap_data cross-filtered by market cap (Polygon reference API,
               cached in ticker_metadata table with 7-day TTL)
  Entry      : today_close of gap day (confirming the move before buying)
  Exit       : walk daily bars from Polygon — stop / target / max hold days
  Data       : Polygon /v2/aggs/1/day fetched on demand, cached per ticker

Timestamp handling (UTC vs naive ET):
  Bars stored with '+00:00' → UTC.  ET cutoffs are converted to UTC before
  comparison so the hot inner loop does only string comparison.
  Bars stored without tz suffix → assumed ET (Polygon naive format).
"""
from __future__ import annotations

import os
import math
import time
import sqlite3
from datetime import datetime, date, timedelta
from typing import Any, Optional

import pytz
import requests

ET = pytz.timezone('US/Eastern')

DB_PATH = os.getenv('DATABASE_PATH') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'trading_advisor.db'
)
OHLCV_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'ohlcv_1m.db'
)

POLYGON_KEY = os.getenv('POLYGON_API_KEY', '')


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ohlcv_conn() -> sqlite3.Connection:
    c = sqlite3.connect(OHLCV_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


# ── Market cap cache ───────────────────────────────────────────────────────────

TICKER_META_REFRESH_DAYS = 7


def _ensure_ticker_metadata_table():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticker_metadata (
                ticker       TEXT PRIMARY KEY,
                market_cap_m REAL,
                fetched_at   TEXT NOT NULL
            )
        """)
        conn.commit()


def _fetch_polygon_market_cap(ticker: str) -> Optional[float]:
    """Return market cap in millions from Polygon reference API, or None."""
    url = (
        f"https://api.polygon.io/v3/reference/tickers/{ticker.upper()}"
        f"?apiKey={POLYGON_KEY}"
    )
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            cap = resp.json().get('results', {}).get('market_cap')
            if cap:
                return round(cap / 1e6, 2)
    except Exception:
        pass
    return None


def _load_cached_market_caps(tickers: list[str]) -> dict[str, Optional[float]]:
    """Load market caps from ticker_metadata that are still within TTL."""
    if not tickers:
        return {}
    cutoff = (date.today() - timedelta(days=TICKER_META_REFRESH_DAYS)).isoformat()
    upper = [t.upper() for t in tickers]
    placeholders = ','.join('?' * len(upper))
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT ticker, market_cap_m FROM ticker_metadata "
            f"WHERE ticker IN ({placeholders}) AND fetched_at >= ?",
            upper + [cutoff]
        ).fetchall()
    return {r['ticker']: r['market_cap_m'] for r in rows}


def _upsert_market_cap(ticker: str, cap_m: Optional[float]):
    today = date.today().isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ticker_metadata (ticker, market_cap_m, fetched_at) "
            "VALUES (?, ?, ?)",
            (ticker.upper(), cap_m, today)
        )
        conn.commit()


def fetch_and_cache_market_caps(
    tickers: list[str],
    progress_cb=None,
) -> dict[str, Optional[float]]:
    """
    Return {TICKER: market_cap_m} for every ticker in the list.
    Reads from the ticker_metadata cache first; fetches missing/stale entries
    from Polygon one at a time (≈150 ms apart to respect rate limits).
    progress_cb(fetched, total) is called after each Polygon fetch if provided.
    """
    _ensure_ticker_metadata_table()
    upper_tickers = [t.upper() for t in tickers]

    result = _load_cached_market_caps(upper_tickers)

    to_fetch = [t for t in upper_tickers if t not in result]

    for i, ticker in enumerate(to_fetch):
        cap_m = _fetch_polygon_market_cap(ticker)
        _upsert_market_cap(ticker, cap_m)
        result[ticker] = cap_m
        if progress_cb:
            progress_cb(i + 1, len(to_fetch))
        time.sleep(0.15)

    return result


# ── Timestamp helpers ──────────────────────────────────────────────────────────

_cutoff_cache: dict[tuple, str] = {}


def _et_hhmm_to_comparable(hhmm_et: str, day_str: str, is_utc: bool) -> str:
    """Convert ET 'HH:MM' to the storage format for bar timestamps."""
    if not is_utc:
        return hhmm_et
    key = (day_str, hhmm_et)
    if key in _cutoff_cache:
        return _cutoff_cache[key]
    h, m = map(int, hhmm_et.split(':'))
    naive = datetime.strptime(day_str, '%Y-%m-%d').replace(hour=h, minute=m)
    utc_hhmm = ET.localize(naive).astimezone(pytz.UTC).strftime('%H:%M')
    _cutoff_cache[key] = utc_hhmm
    return utc_hhmm


def _ts_is_utc(ts_str: str) -> bool:
    return '+' in ts_str or ts_str.endswith('Z')


# ── Info endpoint ──────────────────────────────────────────────────────────────

def get_backtest_info() -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as total "
            "FROM gap_data"
        ).fetchone()
        distinct_days = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM gap_data"
        ).fetchone()[0]
        distinct_tickers = conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM gap_data"
        ).fetchone()[0]

    ohlcv_rows = ohlcv_days = 0
    if os.path.exists(OHLCV_DB_PATH):
        try:
            with _ohlcv_conn() as oc:
                ohlcv_rows = oc.execute("SELECT COUNT(*) FROM ohlcv_1m").fetchone()[0]
                ohlcv_days = oc.execute("SELECT COUNT(DISTINCT day) FROM ohlcv_1m").fetchone()[0]
        except Exception:
            pass

    return {
        'min_date':          row['min_date'],
        'max_date':          row['max_date'],
        'total_candidates':  row['total'],
        'distinct_days':     distinct_days,
        'distinct_tickers':  distinct_tickers,
        'ohlcv_1m_rows':     ohlcv_rows,
        'ohlcv_1m_days':     ohlcv_days,
    }


# ── Public router ──────────────────────────────────────────────────────────────

def run_backtest(cfg: dict) -> dict:
    if cfg.get('trade_type') == 'swing':
        return run_swing_backtest(cfg)
    return run_day_backtest(cfg)


# ══════════════════════════════════════════════════════════════════════════════
# DAY TRADE BACKTEST
# ══════════════════════════════════════════════════════════════════════════════

def run_day_backtest(cfg: dict) -> dict:
    """
    cfg keys:
      start_date, end_date, initial_capital
      position_size_pct    % of capital per trade
      stop_loss_pct        % below entry
      profit_target_pct    % above entry
      min_gap_pct, min_price, max_price, min_volume_m, max_float_m
      entry_start_time     HH:MM ET — earliest bar to consider (default '09:35')
      entry_end_time       HH:MM ET — latest bar to enter; skip if not entered by then (default '10:30')
      eod_exit_time        HH:MM ET — flatten at or after this time (default '15:55')
      day_check_vwap       bool — bar close must be above session VWAP
      day_check_candle     bool — bar must be bullish (close >= open)
      day_max_extension_pct float — bar close must be <= this % above today_open (0 = disabled)
      day_check_volume_surge bool — bar volume >= 1.5x recent average
    """
    start       = cfg.get('start_date')
    end         = cfg.get('end_date')
    capital     = float(cfg.get('initial_capital', 100_000))
    pos_pct     = float(cfg.get('position_size_pct', 10))
    sl_pct      = float(cfg.get('stop_loss_pct', 2))
    tgt_pct     = float(cfg.get('profit_target_pct', 4))
    min_gap     = float(cfg.get('min_gap_pct', 5))
    min_price   = float(cfg.get('min_price', 1))
    max_price   = float(cfg.get('max_price', 9999))
    min_vol     = float(cfg.get('min_volume_m', 0))
    max_float   = float(cfg.get('max_float_m', 0))
    entry_start = cfg.get('entry_start_time', '09:35')
    entry_end   = cfg.get('entry_end_time',   '10:30')
    eod_et      = cfg.get('eod_exit_time',    '15:55')
    chk_vwap    = bool(cfg.get('day_check_vwap', False))
    chk_candle  = bool(cfg.get('day_check_candle', False))
    max_ext     = float(cfg.get('day_max_extension_pct', 0))
    chk_surge   = bool(cfg.get('day_check_volume_surge', False))

    candidates = _fetch_candidates(start, end, min_gap, min_price, max_price, min_vol, max_float)

    use_1m  = os.path.exists(OHLCV_DB_PATH)
    ohlcv_c = _ohlcv_conn() if use_1m else None

    trades        = []
    equity        = capital
    equity_curve  = [{'date': start, 'equity': round(equity, 2)}]
    peak_equity   = capital
    max_dd        = 0.0
    daily_returns: list[float] = []
    fallback_count = 0
    no_entry_count = 0

    for row in candidates:
        ticker     = row['ticker']
        trade_date = row['date']
        gap_open   = float(row['today_open']  or 0)
        ohlc_high  = float(row['today_high']  or 0)
        ohlc_low   = float(row['today_low']   or 0)
        ohlc_close = float(row['today_close'] or 0)

        if gap_open <= 0:
            continue

        result_1m = None
        if ohlcv_c:
            sim = _simulate_day_trade_1m(
                ohlcv_c, ticker, trade_date,
                sl_pct, tgt_pct,
                entry_start, entry_end, eod_et,
                chk_vwap, chk_candle, max_ext, chk_surge,
                gap_open,
            )
            if sim is False:
                # No 1-min bars for this ticker/day — fall through to OHLC fallback
                result_1m = None
            elif sim is None:
                # Had 1-min bars but no qualifying entry in window — skip trade
                no_entry_count += 1
                continue
            else:
                result_1m = sim

        if result_1m:
            entry, exit_price, exit_reason = result_1m
        else:
            # OHLC fallback (no 1-min data at all)
            fallback_count += 1
            entry     = gap_open
            stop_fb   = round(entry * (1 - sl_pct  / 100), 4)
            target_fb = round(entry * (1 + tgt_pct / 100), 4)
            if ohlc_low <= stop_fb:
                exit_price, exit_reason = stop_fb,    'Stop Loss'
            elif ohlc_high >= target_fb:
                exit_price, exit_reason = target_fb,  'Target Hit'
            else:
                exit_price, exit_reason = ohlc_close, 'EOD Close'

        if entry <= 0:
            continue

        stop   = round(entry * (1 - sl_pct  / 100), 4)
        target = round(entry * (1 + tgt_pct / 100), 4)

        trade_value = equity * (pos_pct / 100)
        shares      = math.floor(trade_value / entry)
        if shares < 1:
            continue

        pnl     = round((exit_price - entry) * shares, 2)
        pnl_pct = round((exit_price - entry) / entry * 100, 3)
        equity += pnl

        if equity > peak_equity:
            peak_equity = equity
        dd = (peak_equity - equity) / peak_equity * 100
        if dd > max_dd:
            max_dd = dd

        daily_returns.append(pnl / (entry * shares) if entry * shares else 0)

        trades.append({
            'date':         trade_date,
            'ticker':       ticker,
            'gap_pct':      round(float(row['gap_percentage'] or 0), 2),
            'entry':        round(entry, 4),
            'exit':         round(exit_price, 4),
            'shares':       shares,
            'stop':         round(stop, 4),
            'target':       round(target, 4),
            'pnl':          pnl,
            'pnl_pct':      pnl_pct,
            'exit_reason':  exit_reason,
            'equity_after': round(equity, 2),
        })
        equity_curve.append({'date': trade_date, 'equity': round(equity, 2)})

    if ohlcv_c:
        ohlcv_c.close()

    equity_curve.append({'date': end, 'equity': round(equity, 2)})

    summary = _calc_summary(trades, capital, equity, max_dd, daily_returns)
    summary['used_1m_bars']       = len(trades) - fallback_count
    summary['used_ohlc_fallback'] = fallback_count
    summary['no_entry_in_window'] = no_entry_count

    return {'summary': summary, 'trades': trades, 'equity_curve': equity_curve}


def _simulate_day_trade_1m(
    conn: sqlite3.Connection,
    ticker: str,
    day: str,
    sl_pct: float,
    tgt_pct: float,
    entry_start_et: str,
    entry_end_et: str,
    eod_et: str,
    check_vwap: bool,
    check_candle: bool,
    max_extension_pct: float,
    check_volume_surge: bool,
    gap_open: float,
) -> 'Optional[tuple[float, float, str]] | bool':
    """
    Find the first qualifying bar in [entry_start, entry_end], enter at
    that bar's open, then simulate exit.

    Returns:
      (entry, exit, reason) — trade completed.
      None  — had 1-min bars, but no qualifying entry found in window;
               caller should skip this trade entirely (not fall back to OHLC).
      False — no 1-min bars at all for this ticker/day;
               caller should use OHLC fallback.
    """
    bars = conn.execute(
        "SELECT ts, open, high, low, close, volume FROM ohlcv_1m "
        "WHERE ticker=? AND day=? ORDER BY ts ASC",
        (ticker, day)
    ).fetchall()

    if not bars:
        return False  # sentinel: no 1-min data → caller should use OHLC fallback

    first_ts = bars[0]['ts']
    is_utc   = _ts_is_utc(first_ts)

    entry_start_cmp = _et_hhmm_to_comparable(entry_start_et, day, is_utc)
    entry_end_cmp   = _et_hhmm_to_comparable(entry_end_et,   day, is_utc)
    eod_cmp         = _et_hhmm_to_comparable(eod_et,          day, is_utc)

    entry       = None
    stop        = target = 0.0
    in_position = False

    # Running session VWAP: computed from all bars, even pre-entry, so the
    # VWAP at the entry bar accurately reflects full session context.
    vwap_num  = 0.0
    vwap_den  = 0.0
    recent_vols: list[float] = []

    for bar in bars:
        hhmm  = bar['ts'][11:16]
        open_ = float(bar['open']   or 0)
        high  = float(bar['high']   or 0)
        low   = float(bar['low']    or 0)
        close = float(bar['close']  or 0)
        vol   = float(bar['volume'] or 0)

        # Update VWAP regardless of position state
        tp = (high + low + close) / 3
        if vol > 0:
            vwap_num += tp * vol
            vwap_den += vol
        session_vwap = vwap_num / vwap_den if vwap_den else 0

        if not in_position:
            if hhmm < entry_start_cmp:
                recent_vols.append(vol)
                continue

            if hhmm > entry_end_cmp:
                # Entry window closed without a qualifying bar — skip stock
                return None

            # Inside entry window — evaluate signals
            ok = True
            if check_vwap and session_vwap > 0 and close < session_vwap:
                ok = False
            if ok and check_candle and close < open_:
                ok = False
            if ok and max_extension_pct > 0 and gap_open > 0:
                if (close - gap_open) / gap_open * 100 > max_extension_pct:
                    ok = False
            if ok and check_volume_surge and len(recent_vols) >= 3:
                avg = sum(recent_vols[-5:]) / min(len(recent_vols), 5)
                if avg > 0 and vol < avg * 1.5:
                    ok = False

            if not ok:
                recent_vols.append(vol)
                continue

            # Qualifies — enter at this bar's open
            entry = open_ if open_ > 0 else close
            if entry <= 0:
                recent_vols.append(vol)
                continue

            stop        = round(entry * (1 - sl_pct  / 100), 4)
            target      = round(entry * (1 + tgt_pct / 100), 4)
            in_position = True
            # Fall through to check exit on entry bar

        # In position
        if hhmm >= eod_cmp:
            return (entry, close, 'EOD Close')
        if low <= stop:
            return (entry, stop, 'Stop Loss')
        if high >= target:
            return (entry, target, 'Target Hit')

        recent_vols.append(vol)

    if in_position and bars:
        return (entry, float(bars[-1]['close'] or 0), 'EOD Close')

    return None  # never entered


# ══════════════════════════════════════════════════════════════════════════════
# SWING TRADE BACKTEST
# ══════════════════════════════════════════════════════════════════════════════

def run_swing_backtest(cfg: dict) -> dict:
    """
    cfg keys:
      start_date, end_date, initial_capital
      swing_position_pct      % of capital per trade (default 3)
      swing_stop_loss_pct     % below entry (default 7)
      swing_profit_target_pct % above entry (default 15)
      swing_max_hold_days     calendar days to hold before force-close (default 20)
      min_market_cap_m        min market cap in $M — 0 = disabled (default 500)
      min_gap_pct, min_price, max_price, min_volume_m, max_float_m

    Candidate source: gap_data cross-filtered by market cap (>= min_market_cap_m).
    Market cap is fetched from Polygon and cached in ticker_metadata (7-day TTL).
    Entry: today_close of gap day — simulating "confirmed gap, buy at close".
    Exit: walk Polygon daily bars (stop → target → max hold days).
    """
    start         = cfg.get('start_date')
    end           = cfg.get('end_date')
    capital       = float(cfg.get('initial_capital', 100_000))
    pos_pct       = float(cfg.get('swing_position_pct', 3))
    sl_pct        = float(cfg.get('swing_stop_loss_pct', 7))
    tgt_pct       = float(cfg.get('swing_profit_target_pct', 15))
    max_hold      = int(cfg.get('swing_max_hold_days', 20))
    min_cap_m     = float(cfg.get('min_market_cap_m', 500))
    min_gap       = float(cfg.get('min_gap_pct', 5))
    min_price     = float(cfg.get('min_price', 1))
    max_price     = float(cfg.get('max_price', 9999))
    min_vol       = float(cfg.get('min_volume_m', 0))
    max_float     = float(cfg.get('max_float_m', 0))

    if not POLYGON_KEY:
        raise ValueError('POLYGON_API_KEY is required for swing backtest (daily bar fetch)')

    candidates = _fetch_candidates(start, end, min_gap, min_price, max_price, min_vol, max_float)
    total_before_cap_filter = len(candidates)

    # ── Market cap filter ──────────────────────────────────────────────────────
    market_cap_filtered = 0
    if min_cap_m > 0 and candidates:
        unique_tickers = list({row['ticker'].upper() for row in candidates})
        market_caps = fetch_and_cache_market_caps(unique_tickers)
        filtered = []
        for row in candidates:
            cap = market_caps.get(row['ticker'].upper())
            if cap is not None and cap >= min_cap_m:
                filtered.append(row)
            else:
                market_cap_filtered += 1
        candidates = filtered

    # Pre-fetch daily bars per unique ticker (one API call each, cached).
    # Extend the fetch window by max_hold days so stocks near the end of the
    # backtest range still get enough bars to reach stop/target/max-hold.
    fetch_end = (datetime.strptime(end, '%Y-%m-%d') + timedelta(days=max_hold + 10)).strftime('%Y-%m-%d')

    unique_tickers = list({row['ticker'] for row in candidates})
    daily_bars_cache: dict[str, dict[str, dict]] = {}
    for ticker in unique_tickers:
        bars = _fetch_polygon_daily_bars(ticker, start, fetch_end)
        daily_bars_cache[ticker] = {b['date']: b for b in bars}
        time.sleep(0.13)   # ~7 req/s within Polygon limits

    trades        = []
    equity        = capital
    equity_curve  = [{'date': start, 'equity': round(equity, 2)}]
    peak_equity   = capital
    max_dd        = 0.0
    daily_returns: list[float] = []
    no_data_count = 0

    for row in candidates:
        ticker     = row['ticker']
        trade_date = row['date']
        entry      = float(row['today_close'] or 0)  # enter at gap-day close

        if entry <= 0:
            continue

        trade_value = equity * (pos_pct / 100)
        shares = math.floor(trade_value / entry)
        if shares < 1:
            continue

        # Daily bars after entry date, capped at max_hold_days
        ticker_bars = daily_bars_cache.get(ticker, {})
        hold_dates  = sorted(d for d in ticker_bars if d > trade_date)[:max_hold]

        if not hold_dates:
            no_data_count += 1
            continue

        hold_bars = [ticker_bars[d] for d in hold_dates]
        exit_price, exit_reason, days_held = _simulate_swing_trade(entry, sl_pct, tgt_pct, hold_bars)

        stop   = round(entry * (1 - sl_pct  / 100), 4)
        target = round(entry * (1 + tgt_pct / 100), 4)

        pnl     = round((exit_price - entry) * shares, 2)
        pnl_pct = round((exit_price - entry) / entry * 100, 3)
        equity += pnl

        if equity > peak_equity:
            peak_equity = equity
        dd = (peak_equity - equity) / peak_equity * 100
        if dd > max_dd:
            max_dd = dd

        daily_returns.append(pnl / (entry * shares) if entry * shares else 0)

        trades.append({
            'date':         trade_date,
            'ticker':       ticker,
            'gap_pct':      round(float(row['gap_percentage'] or 0), 2),
            'entry':        round(entry, 4),
            'exit':         round(exit_price, 4),
            'shares':       shares,
            'stop':         round(stop, 4),
            'target':       round(target, 4),
            'pnl':          pnl,
            'pnl_pct':      pnl_pct,
            'exit_reason':  exit_reason,
            'days_held':    days_held,
            'equity_after': round(equity, 2),
        })
        equity_curve.append({'date': trade_date, 'equity': round(equity, 2)})

    equity_curve.append({'date': end, 'equity': round(equity, 2)})

    summary = _calc_summary(trades, capital, equity, max_dd, daily_returns)
    summary['no_data_count']          = no_data_count
    summary['max_hold_exits']         = sum(1 for t in trades if t['exit_reason'] == 'Max Hold Days')
    summary['market_cap_filtered']    = market_cap_filtered
    summary['total_before_cap_filter'] = total_before_cap_filter

    return {'summary': summary, 'trades': trades, 'equity_curve': equity_curve}


def _fetch_polygon_daily_bars(ticker: str, start: str, end: str) -> list[dict]:
    """Fetch daily OHLCV from Polygon. Returns [] on error or missing key."""
    if not POLYGON_KEY:
        return []
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/1/day/"
        f"{start}/{end}?adjusted=true&sort=asc&limit=5000&apiKey={POLYGON_KEY}"
    )
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return [
                {
                    'date':   datetime.utcfromtimestamp(r['t'] / 1000).strftime('%Y-%m-%d'),
                    'open':   r.get('o'),
                    'high':   r.get('h'),
                    'low':    r.get('l'),
                    'close':  r.get('c'),
                    'volume': r.get('v'),
                }
                for r in resp.json().get('results', [])
                if r.get('t')
            ]
    except Exception:
        pass
    return []


def _simulate_swing_trade(
    entry_price: float,
    sl_pct: float,
    tgt_pct: float,
    daily_bars: list[dict],
) -> tuple[float, str, int]:
    """
    Walk daily bars. Conservative same-day ordering: stop fires before target.
    Returns (exit_price, exit_reason, days_held).
    """
    stop   = entry_price * (1 - sl_pct  / 100)
    target = entry_price * (1 + tgt_pct / 100)

    for i, bar in enumerate(daily_bars):
        low   = float(bar['low']   or 0)
        high  = float(bar['high']  or 0)
        close = float(bar['close'] or 0)

        if low <= stop:
            return (round(stop,   4), 'Stop Loss',     i + 1)
        if high >= target:
            return (round(target, 4), 'Target Hit',    i + 1)

    return (round(float(daily_bars[-1]['close'] or 0), 4), 'Max Hold Days', len(daily_bars))


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _fetch_candidates(start, end, min_gap, min_price, max_price, min_vol, max_float) -> list:
    query = """
        SELECT date, ticker, gap_percentage, today_open, today_high, today_low,
               today_close, volume_m, yesterday_close
        FROM gap_data
        WHERE date BETWEEN ? AND ?
          AND gap_percentage >= ?
          AND today_open >= ?
          AND today_open <= ?
          AND volume_m >= ?
    """
    params: list[Any] = [start, end, min_gap, min_price, max_price, min_vol]

    with _conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(gap_data)").fetchall()}
        if 'float_shares' in cols and max_float > 0:
            query += " AND (float_shares IS NULL OR float_shares / 1e6 <= ?)"
            params.append(max_float)
        query += " ORDER BY date ASC, gap_percentage DESC"
        return conn.execute(query, params).fetchall()


def _calc_summary(trades, initial_capital, final_equity, max_dd, daily_returns) -> dict:
    if not trades:
        return {
            'total_trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
            'total_pnl': 0, 'total_return_pct': 0,
            'initial_capital': initial_capital, 'final_capital': final_equity,
            'avg_win': 0, 'avg_loss': 0, 'largest_win': 0, 'largest_loss': 0,
            'profit_factor': 0, 'max_drawdown_pct': 0, 'sharpe_ratio': 0,
            'stop_exits': 0, 'target_exits': 0, 'eod_exits': 0,
        }

    wins         = [t for t in trades if t['pnl'] > 0]
    losses       = [t for t in trades if t['pnl'] <= 0]
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss   = abs(sum(t['pnl'] for t in losses))

    import statistics
    sharpe = 0.0
    if len(daily_returns) > 1:
        mu = statistics.mean(daily_returns)
        sd = statistics.stdev(daily_returns)
        sharpe = round((mu / sd) * (252 ** 0.5), 2) if sd else 0.0

    return {
        'total_trades':     len(trades),
        'wins':             len(wins),
        'losses':           len(losses),
        'win_rate':         round(len(wins) / len(trades) * 100, 1),
        'total_pnl':        round(sum(t['pnl'] for t in trades), 2),
        'total_return_pct': round((final_equity - initial_capital) / initial_capital * 100, 2),
        'initial_capital':  round(initial_capital, 2),
        'final_capital':    round(final_equity, 2),
        'avg_win':          round(gross_profit / len(wins), 2)  if wins   else 0,
        'avg_loss':         round(-gross_loss  / len(losses), 2) if losses else 0,
        'largest_win':      round(max(t['pnl'] for t in wins), 2)  if wins   else 0,
        'largest_loss':     round(min(t['pnl'] for t in losses), 2) if losses else 0,
        'profit_factor':    round(gross_profit / gross_loss, 2) if gross_loss else 0,
        'max_drawdown_pct': round(max_dd, 2),
        'sharpe_ratio':     sharpe,
        'stop_exits':       sum(1 for t in trades if t['exit_reason'] == 'Stop Loss'),
        'target_exits':     sum(1 for t in trades if t['exit_reason'] == 'Target Hit'),
        'eod_exits':        sum(1 for t in trades if t['exit_reason'] == 'EOD Close'),
    }
