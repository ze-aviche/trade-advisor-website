"""
OHLCV 1-minute bar fetcher for gap-up stocks.

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
POLYGON_KEY   = os.getenv('POLYGON_API_KEY', '')
SLEEP_BETWEEN = 0.5          # seconds between Polygon calls (Starter = unlimited)
MAX_RETRIES   = 3
EOD_HOUR_ET   = 16           # 4 PM ET — bars are complete after market close
EOD_MIN_ET    = 30           # fire at 4:30 PM ET
ET            = pytz.timezone('US/Eastern')

POLYGON_URL = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/"
    "{date}/{date}?adjusted=true&sort=asc&limit=50000&apiKey={key}"
)

_lock = threading.Lock()

# All 1-min bar data lives in a dedicated file to avoid locking the main DB.
# The migration script (backtest/migrate_timescaledb_to_sqlite.py) writes here too.
OHLCV_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ohlcv_1m.db')


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


# ── Polygon fetch ─────────────────────────────────────────────────────────────

def fetch_bars(ticker: str, day: str) -> Optional[list[dict]]:
    """
    Fetch 1-min bars for one (ticker, day) from Polygon.
    Returns list of bar dicts, or None on unrecoverable error.
    day must be 'YYYY-MM-DD'.
    """
    if not POLYGON_KEY:
        logger.warning('POLYGON_API_KEY not set — cannot fetch bars')
        return None

    url = POLYGON_URL.format(ticker=ticker.upper(), date=day, key=POLYGON_KEY)

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                results = resp.json().get('results', [])
                if not results:
                    return []   # market closed / no data for that day
                bars = []
                for r in results:
                    ts_ms = r.get('t')
                    if ts_ms is None:
                        continue
                    ts_str = datetime.utcfromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S+00:00')
                    bars.append({
                        'ticker': ticker.upper(),
                        'ts':     ts_str,
                        'day':    day,
                        'open':   r.get('o'),
                        'high':   r.get('h'),
                        'low':    r.get('l'),
                        'close':  r.get('c'),
                        'volume': int(r.get('v', 0)),
                        'vwap':   r.get('vw'),
                        'source': 'polygon',
                    })
                return bars
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', 60))
                logger.warning(f'[OHLCV] Rate limited — sleeping {retry_after}s')
                time.sleep(retry_after + 1)
            elif resp.status_code == 403:
                logger.error(f'[OHLCV] API key rejected for {ticker} {day}')
                return None
            else:
                logger.warning(f'[OHLCV] HTTP {resp.status_code} for {ticker} {day} — retry {attempt+1}')
                time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f'[OHLCV] Exception fetching {ticker} {day}: {e} — retry {attempt+1}')
            time.sleep(2 ** attempt)

    return None


# ── Backfill ──────────────────────────────────────────────────────────────────

def _get_pending_pairs() -> list[tuple[str, str]]:
    """
    Return all (ticker, date) from gap_data that are not yet in ohlcv_1m.
    Ordered oldest-first so the most historical data is filled first.
    """
    with _main_conn() as main:
        gap_rows = main.execute(
            "SELECT DISTINCT ticker, date FROM gap_data ORDER BY date, ticker"
        ).fetchall()

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


# ── Daemon thread ─────────────────────────────────────────────────────────────

def ohlcv_daemon():
    """
    Main daemon function.

    Phase 1 (runs once at startup):  backfill all historical missing bars.
    Phase 2 (runs every trading day): fetch today's bars after 4:30 PM ET.
    """
    _ensure_table()

    # Phase 1 — backfill in background (may take a while for large gap_data)
    try:
        run_backfill()
    except Exception as e:
        logger.error(f'[OHLCV] Backfill crashed: {e}', exc_info=True)

    # Phase 2 — daily EOD fetch
    last_eod_date: Optional[date] = None

    while True:
        try:
            now_et = datetime.now(ET)
            today  = now_et.date()

            if _is_eod_window(now_et) and last_eod_date != today:
                fetch_today_bars()
                last_eod_date = today

        except Exception as e:
            logger.error(f'[OHLCV] EOD loop error: {e}', exc_info=True)

        time.sleep(300)   # check every 5 minutes
