"""
OHLCV 1-minute bar fetcher for gap-up stocks.

Data source: Alpaca Data API v2 (replaces Polygon — same data, already included
in the Algo Trader Plus subscription).

Two jobs in one daemon thread:
  1. Backfill  — on startup, fetch bars for every (ticker, date) in gap_data
                 that isn't already in ohlcv_1m.
  2. Daily EOD — after 4:30 PM ET each trading day, fetch today's bars for
                 all tickers in gap_up_snapshots.

Both jobs skip any (ticker, date) already present in ohlcv_1m (idempotent).
"""
from __future__ import annotations

import os
import time
import sqlite3
import threading
from datetime import datetime, date, timedelta
from typing import Optional

import requests
import pytz

from logging_config import get_logger

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ALPACA_KEY    = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET = os.getenv('ALPACA_API_SECRET', '')
SLEEP_BETWEEN = 0.5          # seconds between API calls
MAX_RETRIES   = 3
EOD_HOUR_ET   = 16           # 4 PM ET — bars are complete after market close
EOD_MIN_ET    = 30           # fire at 4:30 PM ET
ET            = pytz.timezone('US/Eastern')

ALPACA_BARS_URL = 'https://data.alpaca.markets/v2/stocks/{ticker}/bars'

_lock = threading.Lock()

# All 1-min bar data lives in a dedicated file to avoid locking the main DB.
# The migration script (backtest/migrate_timescaledb_to_sqlite.py) writes here too.
OHLCV_DB_PATH = os.getenv('OHLCV_DB_PATH') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ohlcv_1m.db')


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_main_db_path() -> str:
    db_path = os.getenv('DATABASE_PATH')
    if not db_path:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading_advisor.db')
    return db_path


def _conn() -> sqlite3.Connection:
    """Connection to ohlcv_1m.db (dedicated 1-min bar store)."""
    c = sqlite3.connect(OHLCV_DB_PATH, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def _main_conn() -> sqlite3.Connection:
    """Connection to trading_advisor.db (for reading gap_up_snapshots etc.)."""
    c = sqlite3.connect(_get_main_db_path(), timeout=30)
    return c


def _ensure_table():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_1m (
                ticker  TEXT    NOT NULL,
                ts      TEXT    NOT NULL,
                day     TEXT    NOT NULL,
                open    REAL,
                high    REAL,
                low     REAL,
                close   REAL,
                volume  INTEGER,
                vwap    REAL,
                source  TEXT,
                PRIMARY KEY (ticker, ts)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_day ON ohlcv_1m (ticker, day)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_day ON ohlcv_1m (day)")
        conn.commit()


def _already_fetched(ticker: str, day: str) -> bool:
    """Return True if ohlcv_1m.db already has any rows for this ticker+day."""
    with _conn() as ohlcv:
        row = ohlcv.execute(
            "SELECT 1 FROM ohlcv_1m WHERE ticker = ? AND day = ? LIMIT 1",
            (ticker.upper(), day)
        ).fetchone()
    return row is not None


def _insert_bars(bars: list[dict]):
    if not bars:
        return
    with _conn() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO ohlcv_1m
               (ticker, ts, day, open, high, low, close, volume, vwap, source)
               VALUES (:ticker, :ts, :day, :open, :high, :low, :close, :volume, :vwap, :source)""",
            bars,
        )
        conn.commit()


# ── Alpaca fetch ──────────────────────────────────────────────────────────────

def fetch_bars(ticker: str, day: str) -> Optional[list[dict]]:
    """
    Fetch 1-min bars for one (ticker, day) from Alpaca Data API v2.
    Returns list of bar dicts, or None on unrecoverable error.
    day must be 'YYYY-MM-DD'.
    Handles Alpaca pagination automatically via next_page_token.
    """
    if not ALPACA_KEY or not ALPACA_SECRET:
        logger.warning('ALPACA_API_KEY / ALPACA_API_SECRET not set — cannot fetch bars')
        return None

    sym = ticker.upper()
    url = ALPACA_BARS_URL.format(ticker=sym)
    headers = {
        'APCA-API-KEY-ID':     ALPACA_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET,
    }
    base_params = {
        'timeframe':  '1Min',
        'start':      f'{day}T00:00:00Z',
        'end':        f'{day}T23:59:59Z',
        'limit':      1000,
        'adjustment': 'raw',
        'feed':       'sip',
    }

    all_bars: list[dict] = []
    page_token: Optional[str] = None

    while True:
        params = dict(base_params)
        if page_token:
            params['page_token'] = page_token

        page_fetched = False
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    for r in (data.get('bars') or []):
                        # Convert "2024-01-01T14:30:00Z" → "2024-01-01 14:30:00+00:00"
                        ts_raw = r['t'].replace('T', ' ')
                        ts = ts_raw[:-1] + '+00:00' if ts_raw.endswith('Z') else ts_raw
                        all_bars.append({
                            'ticker': sym,
                            'ts':     ts,
                            'day':    day,
                            'open':   r.get('o'),
                            'high':   r.get('h'),
                            'low':    r.get('l'),
                            'close':  r.get('c'),
                            'volume': int(r.get('v', 0)),
                            'vwap':   r.get('vw'),
                            'source': 'alpaca',
                        })
                    page_token = data.get('next_page_token')
                    page_fetched = True
                    break
                elif resp.status_code == 429:
                    wait = int(resp.headers.get('Retry-After', 60))
                    logger.warning(f'[OHLCV] Rate limited — sleeping {wait}s')
                    time.sleep(wait + 1)
                elif resp.status_code == 403:
                    logger.error(f'[OHLCV] API key rejected for {ticker} {day}')
                    return None
                else:
                    logger.warning(
                        f'[OHLCV] HTTP {resp.status_code} for {ticker} {day} — retry {attempt+1}')
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.warning(
                    f'[OHLCV] Exception fetching {ticker} {day}: {e} — retry {attempt+1}')
                time.sleep(2 ** attempt)

        if not page_fetched:
            # All retries exhausted — return whatever we have (or None if nothing)
            return None if not all_bars else all_bars

        if not page_token:
            break  # no more pages
        time.sleep(SLEEP_BETWEEN)

    return all_bars if all_bars else []  # [] = market closed / no data that day


# ── Backfill ──────────────────────────────────────────────────────────────────

def _get_pending_pairs() -> list[tuple[str, str]]:
    """
    Return all (ticker, date) from gap_data that are not yet in ohlcv_1m.
    Ordered oldest-first so the most historical data is filled first.
    Returns [] if gap_data table doesn't exist yet.
    """
    try:
        with _main_conn() as main:
            gap_rows = main.execute(
                "SELECT DISTINCT ticker, date FROM gap_data ORDER BY date, ticker"
            ).fetchall()
    except Exception as e:
        logger.warning(f'[OHLCV] _get_pending_pairs: {e} — gap_data not yet populated')
        return []

    if not gap_rows:
        return []

    with _conn() as ohlcv:
        done = set(
            ohlcv.execute("SELECT ticker, day FROM ohlcv_1m GROUP BY ticker, day").fetchall()
        )

    return [(t.upper(), d) for t, d in gap_rows if (t.upper(), d) not in done]


def run_backfill():
    """Fetch missing bars for all historical gap_data entries. Runs once at startup."""
    pending = _get_pending_pairs()
    if not pending:
        logger.info('[OHLCV] Backfill: nothing to fetch — ohlcv_1m is up to date')
        return

    logger.info(f'[OHLCV] Backfill: {len(pending)} (ticker, date) pairs to fetch')
    ok = skipped = errors = 0

    for ticker, day in pending:
        # Re-check in case another process already inserted it
        if _already_fetched(ticker, day):
            skipped += 1
            continue

        bars = fetch_bars(ticker, day)
        if bars is None:
            errors += 1
        elif bars:
            _insert_bars(bars)
            ok += 1
            logger.debug(f'[OHLCV] {ticker} {day}: stored {len(bars)} bars')
        else:
            skipped += 1  # no data (holiday / halted)

        time.sleep(SLEEP_BETWEEN)

    logger.info(f'[OHLCV] Backfill complete — fetched={ok}, skipped={skipped}, errors={errors}')


# ── EOD daily fetch ───────────────────────────────────────────────────────────

def _today_et() -> date:
    return datetime.now(ET).date()


def _is_eod_window(now: datetime) -> bool:
    """True between 4:30 PM and 11:59 PM ET on weekdays."""
    if now.weekday() >= 5:   # Saturday / Sunday
        return False
    return now.hour > EOD_HOUR_ET or (now.hour == EOD_HOUR_ET and now.minute >= EOD_MIN_ET)


def fetch_today_bars():
    """Fetch 1-min bars for all of today's gap-up stocks."""
    day_str = _today_et().isoformat()

    with _main_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM gap_up_snapshots WHERE date = ?",
            (day_str,)
        ).fetchall()

    tickers = [r[0].upper() for r in rows]
    if not tickers:
        logger.info(f'[OHLCV] EOD: no gap-up snapshots for {day_str}')
        return

    logger.info(f'[OHLCV] EOD: fetching bars for {len(tickers)} tickers on {day_str}')
    ok = skipped = errors = 0

    for ticker in tickers:
        if _already_fetched(ticker, day_str):
            skipped += 1
            continue
        bars = fetch_bars(ticker, day_str)
        if bars is None:
            errors += 1
        elif bars:
            _insert_bars(bars)
            ok += 1
        else:
            skipped += 1
        time.sleep(SLEEP_BETWEEN)

    logger.info(f'[OHLCV] EOD {day_str}: fetched={ok}, skipped={skipped}, errors={errors}')


# ── Snapshot → gap_data sync (close the loop for daily forward-testing) ────────

def _ensure_gap_data_float_col():
    """Add gap_data.float_shares if missing so the backtest float filter works."""
    try:
        with _main_conn() as conn:
            tbls = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if 'gap_data' not in tbls:
                return
            cols = {r[1] for r in conn.execute("PRAGMA table_info(gap_data)").fetchall()}
            if 'float_shares' not in cols:
                conn.execute("ALTER TABLE gap_data ADD COLUMN float_shares REAL")
                conn.commit()
    except Exception as e:
        logger.debug(f'[OHLCV] float col ensure: {e}')


def _regular_session_ohlc(ticker: str, day: str):
    """Aggregate ohlcv_1m 09:30–16:00 ET bars → (open, high, low, close, vol, peak_$vol)."""
    with _conn() as oc:
        bars = oc.execute(
            "SELECT ts, open, high, low, close, volume FROM ohlcv_1m "
            "WHERE ticker=? AND day=? ORDER BY ts ASC", (ticker, day)).fetchall()
    reg = []
    for b in bars:
        try:
            dt = datetime.fromisoformat(str(b[0]).replace('Z', '+00:00')).astimezone(ET)
        except Exception:
            continue
        if (dt.hour, dt.minute) >= (9, 30) and dt.hour < 16:
            reg.append(b)
    if not reg:
        return None
    o  = float(reg[0][1] or 0)
    hi = max(float(b[2] or 0) for b in reg)
    lo = min(float(b[3] or 0) for b in reg if (b[3] or 0) > 0)
    cl = float(reg[-1][4] or 0)
    vol = sum(float(b[5] or 0) for b in reg)
    peak_dv = max((float(b[4] or 0) * float(b[5] or 0)) for b in reg)
    return o, hi, lo, cl, vol, peak_dv


def sync_gap_data_from_snapshots(fetch_missing: bool = True) -> int:
    """
    Append daily gap_up_snapshots into gap_data (the backtest CANDIDATE table),
    deriving OHLC/volume from the 1-min bars in ohlcv_1m. This closes the loop so
    recent days become backtestable ("go one day back and test"). Idempotent.
    If fetch_missing, pulls any snapshot ticker-day whose bars aren't cached yet.
    """
    _ensure_gap_data_float_col()
    try:
        with _main_conn() as conn:
            tbls = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if 'gap_up_snapshots' not in tbls or 'gap_data' not in tbls:
                return 0
            snaps = conn.execute(
                "SELECT date, ticker, gap_percent, previous_close, float_shares "
                "FROM gap_up_snapshots").fetchall()
            existing = {(r[0], (r[1] or '').upper())
                        for r in conn.execute("SELECT date, ticker FROM gap_data").fetchall()}
    except Exception as e:
        logger.warning(f'[OHLCV] gap_data sync: tables not ready — {e}')
        return 0

    # De-dup snapshots (a ticker may appear multiple sessions per day) & skip existing.
    seen = set()
    pending = []
    for date_s, ticker, gap_pct, prev_close, float_sh in snaps:
        t = (ticker or '').upper()
        key = (date_s, t)
        if not t or key in seen or key in existing:
            continue
        seen.add(key)
        pending.append((date_s, t, gap_pct, prev_close, float_sh))

    if not pending:
        return 0
    logger.info(f'[OHLCV] gap_data sync: {len(pending)} snapshot rows to evaluate')

    inserted = 0
    for date_s, t, gap_pct, prev_close, float_sh in pending:
        if fetch_missing and not _already_fetched(t, date_s):
            bars = fetch_bars(t, date_s)
            if bars:
                _insert_bars(bars)
            time.sleep(SLEEP_BETWEEN)
        agg = _regular_session_ohlc(t, date_s)
        if not agg:
            continue
        o, hi, lo, cl, vol, peak_dv = agg
        pc = float(prev_close) if prev_close not in (None, 0) else 0
        if o <= 0 or pc <= 0:
            continue
        gp = round((o - pc) / pc * 100, 2)   # open-based gap, matching historical gap_data
        try:
            with _main_conn() as conn:
                conn.execute(
                    "INSERT INTO gap_data (date, ticker, yesterday_close, today_open, "
                    "gap_percentage, today_close, today_high, today_low, volume_m, "
                    "highest_dollar_volume_m, float_shares) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (date_s, t, round(pc, 4), round(o, 4), gp, round(cl, 4),
                     round(hi, 4), round(lo, 4), round(vol / 1e6, 3),
                     round(peak_dv / 1e6, 3), float_sh))
                conn.commit()
            inserted += 1
        except Exception as e:
            logger.debug(f'[OHLCV] gap_data insert {t} {date_s}: {e}')

    logger.info(f'[OHLCV] gap_data sync: +{inserted} new candidate rows from snapshots')
    return inserted


# ── Daemon thread ─────────────────────────────────────────────────────────────

def ohlcv_daemon():
    """
    Main daemon function.

    Phase 1 (runs once at startup):  backfill all historical missing bars.
    Phase 2 (runs every trading day): fetch today's bars after 4:30 PM ET.
    """
    _ensure_table()

    # Phase 1 — backfill; retry every 10 min if gap_data isn't seeded yet
    backfill_done = False
    while not backfill_done:
        try:
            run_backfill()
            backfill_done = True
        except Exception as e:
            logger.error(f'[OHLCV] Backfill failed: {e} — retrying in 10 min', exc_info=True)
            time.sleep(600)

    # One-time catch-up: fold any snapshot days not yet in gap_data (2025-09 →
    # today) into the candidate table so recent days become backtestable.
    try:
        sync_gap_data_from_snapshots()
    except Exception as e:
        logger.error(f'[OHLCV] gap_data catch-up sync failed: {e}', exc_info=True)

    # Phase 2 — daily EOD fetch
    last_eod_date: Optional[date] = None

    while True:
        try:
            now_et = datetime.now(ET)
            today  = now_et.date()

            if _is_eod_window(now_et) and last_eod_date != today:
                fetch_today_bars()
                # Fold today's gappers into gap_data so tomorrow you can backtest today.
                try:
                    sync_gap_data_from_snapshots()
                except Exception as _se:
                    logger.error(f'[OHLCV] EOD gap_data sync failed: {_se}')
                last_eod_date = today

        except Exception as e:
            logger.error(f'[OHLCV] EOD loop error: {e}', exc_info=True)

        time.sleep(300)   # check every 5 minutes
