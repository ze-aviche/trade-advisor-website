#!/usr/bin/env python3
"""
Real Gap-Up Stock Detection using Alpaca Data API v2.
Alpaca Algo Trader Plus provides real-time data (replaces Polygon).
"""

import os
import time
import requests
from datetime import datetime as dt
import pytz
from dotenv import load_dotenv
from logging_config import get_logger
from gap_up_cache import gap_up_cache

# Load environment variables before reading them so .env is honoured locally
load_dotenv()

ALPACA_KEY    = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET = os.getenv('ALPACA_API_SECRET', '')

# Setup logger
logger = get_logger(__name__)

# Gap tracker removed - using simple gap-up detection
GAP_TRACKER_AVAILABLE = False

# Session tracker: remembers which market session each ticker was FIRST detected in today.
# Maps ticker -> {'session': 'premarket'|'intraday'|'afterhours', 'date': 'YYYY-MM-DD'}
# Backed by gap_up_snapshots DB so session tags survive server restarts mid-day.
_session_tracker: dict = {}

_SESSION_MAP = {
    'pre_market':  'premarket',
    'open':        'intraday',
    'after_hours': 'afterhours',
    'closed':      'premarket',  # overnight (midnight–4 AM) → next day's pre-market
}

def _load_session_tracker():
    """
    Restore today's session tags from gap_up_snapshots DB on startup.
    This means a server restart mid-day won't re-classify pre-market gappers
    as intraday — their original session is preserved in the DB.
    """
    global _session_tracker
    try:
        from database import db_manager
        et_tz = pytz.timezone('US/Eastern')
        now_et = dt.now(et_tz)
        today = now_et.date().isoformat()
        rows = db_manager.get_gap_up_snapshot(today)

        # Before market open (9:30 AM ET), no stock can legitimately have been
        # first seen during intraday. Any 'intraday' tag in the DB before 9:30 AM
        # is a stale artifact (e.g. from an old overnight-scan bug). Correct it.
        pre_open = (now_et.hour + now_et.minute / 60.0) < 9.5

        corrected = 0
        _session_tracker = {}
        for row in rows:
            if not row.get('session'):
                continue
            session = row['session']
            if pre_open and session == 'intraday':
                session = 'premarket'
                corrected += 1
            _session_tracker[row['ticker']] = {'session': session, 'date': today}

        if _session_tracker:
            msg = f"Restored {len(_session_tracker)} session tracker entries from DB"
            if corrected:
                msg += f" ({corrected} stale 'intraday' corrected to 'premarket')"
            logger.info(msg)
    except Exception as e:
        logger.warning(f"Could not restore session tracker from DB: {e}")


# Restore today's session tags at module import
_load_session_tracker()


def _tag_with_session(stocks: list) -> list:
    """
    Stamp each stock dict with a 'session' key reflecting when it was
    FIRST detected as a gapper today. Subsequent polls keep the original tag.
    Session tags are backed by the DB so server restarts don't re-classify
    pre-market gappers as intraday.
    """
    et_tz   = pytz.timezone('US/Eastern')
    today   = dt.now(et_tz).date().isoformat()
    session = _SESSION_MAP.get(check_market_timing(), 'intraday')

    for stock in stocks:
        ticker = stock.get('ticker')
        if not ticker:
            continue
        entry = _session_tracker.get(ticker)
        if entry and entry['date'] == today:
            stock['session'] = entry['session']   # keep original session
        else:
            _session_tracker[ticker] = {'session': session, 'date': today}
            stock['session'] = session

    # Purge stale entries from previous trading days
    stale = [t for t, v in _session_tracker.items() if v['date'] != today]
    for t in stale:
        del _session_tracker[t]

    return stocks

def check_market_timing():
    """Check current market session using US/Eastern time."""
    et_tz = pytz.timezone('US/Eastern')
    now = dt.now(et_tz)
    current_time = now.time()

    if now.weekday() >= 5:
        return "closed"

    pre_market_start = dt.strptime("04:00", "%H:%M").time()
    market_open     = dt.strptime("09:30", "%H:%M").time()
    market_close    = dt.strptime("16:00", "%H:%M").time()
    after_hours_end = dt.strptime("20:00", "%H:%M").time()

    if pre_market_start <= current_time < market_open:
        return "pre_market"
    elif market_open <= current_time <= market_close:
        return "open"
    elif market_close < current_time <= after_hours_end:
        return "after_hours"
    else:
        return "closed"

# Ticker suffixes that reliably indicate non-common-stock instruments
_NON_CS_SUFFIXES = ('W', 'WS', 'R', 'U', 'Z')

def _ticker_looks_non_cs(ticker):
    t = ticker.upper().replace('.', '')
    return any(t.endswith(s) for s in _NON_CS_SUFFIXES)


# ── Full universe cache ────────────────────────────────────────────────────────
# Populated once per day by _get_alpaca_equity_universe().
_UNIVERSE_CACHE: dict = {'symbols': [], 'ts': 0.0}
_UNIVERSE_TTL = 86_400   # 24 h

# ── Fundamentals cache ─────────────────────────────────────────────────────────
# ticker → {market_cap, float_shares, company_name, sector}
# Cached indefinitely within the process — fundamentals change slowly and
# yfinance is rate-limited, so we never re-fetch a ticker we already have.
_fundamentals_cache: dict = {}


def _get_alpaca_equity_universe() -> list:
    """
    Return all active tradable US equity symbols from the Alpaca broker API.
    Tries live API first, then paper API.  Cached for 24 h in memory so the
    expensive assets call only runs once per server start.
    """
    global _UNIVERSE_CACHE
    if time.time() - _UNIVERSE_CACHE['ts'] < _UNIVERSE_TTL and _UNIVERSE_CACHE['symbols']:
        return _UNIVERSE_CACHE['symbols']

    if not ALPACA_KEY or not ALPACA_SECRET:
        return []

    headers = {
        'APCA-API-KEY-ID':     ALPACA_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET,
    }
    for base_url in ('https://api.alpaca.markets', 'https://paper-api.alpaca.markets'):
        try:
            resp = requests.get(
                f'{base_url}/v2/assets',
                headers=headers,
                params={'asset_class': 'us_equity', 'status': 'active'},
                timeout=30,
            )
            if resp.status_code == 200:
                symbols = [
                    a['symbol'] for a in resp.json()
                    if a.get('tradable') and not _ticker_looks_non_cs(a.get('symbol', ''))
                ]
                _UNIVERSE_CACHE = {'symbols': symbols, 'ts': time.time()}
                logger.info(f'Universe cache: loaded {len(symbols)} US equity symbols from {base_url}')
                return symbols
            logger.debug(f'Alpaca assets {base_url}: HTTP {resp.status_code}')
        except Exception as e:
            logger.debug(f'Alpaca assets {base_url}: {e}')

    return _UNIVERSE_CACHE['symbols']   # return stale on complete failure


def _fetch_from_alpaca_universe_scan(min_price: float, min_gap_pct: float = 2.0) -> list:
    """
    Comprehensive gap scanner: snapshot the FULL Alpaca US equity universe and
    filter by gap% vs previous close.  This catches any mover (including micro-cap
    runners like AMST/INM) that Alpaca's movers or yfinance screeners exclude due
    to their implicit liquidity/market-cap filters.

    Runs batches of 500 symbols concurrently — typically 10–20 s for 10 k symbols.
    Results are merged as a supplemental source (duplicates deduped by the caller).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    symbols = _get_alpaca_equity_universe()
    if not symbols:
        logger.warning('Universe scan: symbol cache empty — skipping')
        return []

    headers = {
        'APCA-API-KEY-ID':     ALPACA_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET,
    }
    batch_size = 500
    batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]

    def _snap_batch(batch):
        try:
            resp = requests.get(
                'https://data.alpaca.markets/v2/stocks/snapshots',
                headers=headers,
                params={'symbols': ','.join(batch), 'feed': 'sip'},
                timeout=20,
            )
            if resp.status_code != 200:
                return []
            hits = []
            for ticker, snap in resp.json().items():
                try:
                    if _ticker_looks_non_cs(ticker):
                        continue
                    daily = snap.get('dailyBar') or {}
                    prev  = snap.get('prevDailyBar') or {}
                    trade = snap.get('latestTrade') or {}

                    price      = float(trade.get('p') or daily.get('c') or 0)
                    prev_close = float(prev.get('c') or 0)
                    if price <= 0 or prev_close <= 0 or price < min_price:
                        continue

                    gap_pct = ((price - prev_close) / prev_close) * 100
                    if gap_pct < min_gap_pct:
                        continue

                    hits.append({
                        'ticker':         ticker,
                        'company_name':   ticker,
                        'price':          round(price, 2),
                        'previous_close': round(prev_close, 2),
                        'change':         round(price - prev_close, 2),
                        'change_percent': round(gap_pct, 2),
                        'gap_percent':    round(gap_pct, 2),
                        'volume':         int(daily.get('v') or 0),
                        'market_cap':     0,
                        'float_shares':   0,
                        'sector':         'Unknown',
                        'list_date':      None,
                        'data_source':    'alpaca_universe',
                    })
                except Exception:
                    pass
            return hits
        except Exception as e:
            logger.debug(f'Universe scan batch error: {e}')
            return []

    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(_snap_batch, b) for b in batches]
        for f in as_completed(futures):
            results.extend(f.result())

    results.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(
        f'Universe scan: {len(results)} gainers ≥{min_gap_pct}% '
        f'from {len(symbols)} symbols ({len(batches)} batches)'
    )
    return results


def _fetch_from_alpaca(min_price):
    """
    Fetch gap-up stocks using Alpaca's stock screener movers endpoint.
    Alpaca Algo Trader Plus provides real-time data — no Polygon needed.
    Raises on any API or credential error.
    """
    if not ALPACA_KEY or not ALPACA_SECRET:
        raise ValueError("ALPACA_API_KEY / ALPACA_API_SECRET not set")

    market_status = check_market_timing()
    logger.info(f"Fetching market gainers via Alpaca movers (status: {market_status})")

    headers = {
        'APCA-API-KEY-ID':     ALPACA_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET,
    }
    resp = requests.get(
        'https://data.alpaca.markets/v1beta1/screener/stocks/movers',
        headers=headers,
        params={'top': 500},
        timeout=15,
    )
    resp.raise_for_status()
    gainers = resp.json().get('gainers') or []
    logger.info(f"Processing {len(gainers)} gainers from Alpaca movers")

    gap_up_stocks = []
    skipped_non_cs = 0
    skipped_price  = 0

    for item in gainers:
        ticker = item.get('symbol')
        if not ticker:
            continue

        if _ticker_looks_non_cs(ticker):
            skipped_non_cs += 1
            continue

        try:
            price      = float(item.get('price') or 0)
            change     = float(item.get('change') or 0)
            change_pct = float(item.get('change_percent') or 0)
            volume     = int(item.get('volume') or 0)

            if price <= 0 or price < min_price:
                skipped_price += 1
                continue

            prev_close = price - change
            if prev_close <= 0:
                continue

            gap_up_stocks.append({
                'ticker':         ticker,
                'company_name':   ticker,   # enriched with yfinance metadata in caller
                'price':          round(price, 2),
                'previous_close': round(prev_close, 2),
                'change':         round(change, 2),
                'change_percent': round(change_pct, 2),
                'gap_percent':    round(change_pct, 2),
                'volume':         volume,
                'market_cap':     0,
                'float_shares':   0,
                'sector':         'Unknown',
                'list_date':      None,
                'data_source':    'alpaca',
            })
        except Exception as e:
            logger.error(f"Error processing Alpaca gainer {ticker}: {e}")
            continue

    gap_up_stocks.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(
        f"Alpaca done — {len(gap_up_stocks)} gap-ups "
        f"(skipped: {skipped_non_cs} non-CS, {skipped_price} below ${min_price})"
    )
    return gap_up_stocks


def _fetch_from_alpaca_most_actives(min_price: float) -> list:
    """
    Supplemental scan: pull top 100 most-active stocks by share volume from Alpaca,
    then fetch their snapshots to compute the actual gap-% vs prev close.
    Micro-cap runners like AMST/INM always show up here even if they're absent from
    the movers endpoint's liquidity-filtered universe.
    Returns only stocks with a positive gap (gainers).
    """
    if not ALPACA_KEY or not ALPACA_SECRET:
        return []
    headers = {
        'APCA-API-KEY-ID': ALPACA_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET,
    }
    # Step 1: most-active stocks by share volume
    try:
        resp = requests.get(
            'https://data.alpaca.markets/v1beta1/screener/stocks/most-actives',
            headers=headers,
            params={'top': 100, 'by': 'volume'},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f'Alpaca most-actives HTTP {resp.status_code}: {resp.text[:200]}')
            return []
        actives = resp.json().get('most_actives') or []
    except Exception as e:
        logger.warning(f'Alpaca most-actives error: {e}')
        return []

    if not actives:
        return []

    symbols = [item['symbol'] for item in actives if item.get('symbol')]

    # Step 2: snapshots to compute gap% (prev close → current price)
    try:
        snap_resp = requests.get(
            'https://data.alpaca.markets/v2/stocks/snapshots',
            headers=headers,
            params={'symbols': ','.join(symbols), 'feed': 'sip'},
            timeout=15,
        )
        snapshots = snap_resp.json() if snap_resp.status_code == 200 else {}
    except Exception as e:
        logger.warning(f'Alpaca most-actives snapshots error: {e}')
        snapshots = {}

    results = []
    for item in actives:
        ticker = item.get('symbol')
        if not ticker or _ticker_looks_non_cs(ticker):
            continue
        try:
            snap      = snapshots.get(ticker, {})
            trade     = snap.get('latestTrade') or {}
            daily_bar = snap.get('dailyBar') or {}
            prev_bar  = snap.get('prevDailyBar') or {}

            price      = float(trade.get('p') or daily_bar.get('c') or item.get('price') or 0)
            prev_close = float(prev_bar.get('c') or 0)

            if price <= 0 or prev_close <= 0 or price < min_price:
                continue

            gap_pct = ((price - prev_close) / prev_close) * 100
            if gap_pct <= 0:
                continue  # only gainers

            volume = int(daily_bar.get('v') or item.get('volume') or 0)

            results.append({
                'ticker':         ticker,
                'company_name':   ticker,
                'price':          round(price, 2),
                'previous_close': round(prev_close, 2),
                'change':         round(price - prev_close, 2),
                'change_percent': round(gap_pct, 2),
                'gap_percent':    round(gap_pct, 2),
                'volume':         volume,
                'market_cap':     0,
                'float_shares':   0,
                'sector':         'Unknown',
                'list_date':      None,
                'data_source':    'alpaca_actives',
            })
        except Exception as e:
            logger.debug(f'Alpaca most-actives item error {ticker}: {e}')

    results.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(f'Alpaca most-actives: {len(results)} gainers from top-100 active stocks')
    return results


def _fetch_from_yfinance(min_price):
    """
    Fallback: fetch gap-up stocks using yfinance day_gainers screener.
    Returns data in the same shape as _fetch_from_alpaca.
    """
    import yfinance as yf

    logger.info("Fetching market gainers via yfinance screener")
    result = yf.screen('day_gainers')
    quotes = result.get('quotes', [])
    logger.info(f"yfinance returned {len(quotes)} gainers")

    gap_up_stocks = []
    for q in quotes:
        try:
            ticker        = q.get('symbol')
            quote_type    = q.get('quoteType', '')
            current_price = q.get('regularMarketPrice')
            prev_close    = q.get('regularMarketPreviousClose')

            if not ticker or quote_type != 'EQUITY':
                continue
            if current_price is None or prev_close is None or prev_close == 0:
                continue
            if current_price < min_price:
                continue

            gap_percent = ((current_price - prev_close) / prev_close) * 100

            gap_up_stocks.append({
                'ticker':         ticker,
                'company_name':   q.get('longName') or q.get('shortName') or ticker,
                'price':          round(current_price, 2),
                'previous_close': round(prev_close, 2),
                'change':         round(current_price - prev_close, 2),
                'change_percent': round(gap_percent, 2),
                'gap_percent':    round(gap_percent, 2),
                'volume':         int(q.get('regularMarketVolume') or 0),
                'market_cap':     int(q.get('marketCap') or 0),
                'float_shares':   int(q.get('floatShares') or q.get('sharesOutstanding') or 0),
                'sector':         q.get('sector') or 'Unknown',
                'list_date':      None,
                'data_source':    'yfinance',
            })
        except Exception as e:
            logger.error(f"Error processing yfinance quote {q.get('symbol')}: {e}")
            continue

    gap_up_stocks.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(f"yfinance done — {len(gap_up_stocks)} equity gap-ups found")
    return gap_up_stocks


def _fetch_from_yfinance_extra(min_price):
    """
    Supplemental small-cap gainer scan using additional yfinance screeners.
    Catches stocks that don't appear in the top-N of the standard day_gainers
    snapshot — notably micro/small caps like DRTS, CRCA.
    Returns data in the same shape as _fetch_from_alpaca/_fetch_from_yfinance.
    """
    import yfinance as yf

    extra_screeners = ['small_cap_gainers', 'aggressive_small_caps', 'most_actives']
    seen = set()
    stocks = []

    for screener_name in extra_screeners:
        try:
            result = yf.screen(screener_name)
            quotes = result.get('quotes', [])
            logger.info(f"yfinance {screener_name} returned {len(quotes)} results")
            for q in quotes:
                try:
                    ticker     = q.get('symbol')
                    quote_type = q.get('quoteType', '')
                    if not ticker or ticker in seen or quote_type != 'EQUITY':
                        continue
                    current_price = q.get('regularMarketPrice')
                    prev_close    = q.get('regularMarketPreviousClose')
                    if current_price is None or prev_close is None or prev_close == 0:
                        continue
                    if current_price < min_price:
                        continue
                    gap_percent = ((current_price - prev_close) / prev_close) * 100
                    seen.add(ticker)
                    stocks.append({
                        'ticker':         ticker,
                        'company_name':   q.get('longName') or q.get('shortName') or ticker,
                        'price':          round(current_price, 2),
                        'previous_close': round(prev_close, 2),
                        'change':         round(current_price - prev_close, 2),
                        'change_percent': round(gap_percent, 2),
                        'gap_percent':    round(gap_percent, 2),
                        'volume':         int(q.get('regularMarketVolume') or 0),
                        'market_cap':     int(q.get('marketCap') or 0),
                        'float_shares':   int(q.get('floatShares') or q.get('sharesOutstanding') or 0),
                        'sector':         q.get('sector') or 'Unknown',
                        'list_date':      None,
                        'data_source':    'yfinance',
                    })
                except Exception as e:
                    logger.error(f"Error processing {screener_name} quote {q.get('symbol')}: {e}")
        except Exception as e:
            logger.warning(f"yfinance {screener_name} screener unavailable: {e}")

    stocks.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(f"yfinance extra screeners — {len(stocks)} unique small-cap gap-ups found")
    return stocks


def _fetch_premarket_from_yfinance(min_price):
    """
    Pre-market gap scanner.  yfinance standard screeners use regularMarketPrice
    (yesterday's close until 9:30 AM), so we read preMarketPrice instead to surface
    stocks with overnight/pre-market catalysts.

    Gap% = preMarketPrice vs regularMarketPreviousClose (yesterday's close).
    Minimum move: 2% — same threshold as the AH scanner.
    """
    import yfinance as yf

    PM_MIN_MOVE_PCT = 2.0
    seen   = set()
    stocks = []

    for screener_name in ('most_actives', 'day_gainers', 'small_cap_gainers'):
        try:
            result = yf.screen(screener_name)
            quotes = result.get('quotes', [])
            logger.info(f"yfinance PM scan ({screener_name}): {len(quotes)} stocks to check")
            for q in quotes:
                ticker = q.get('symbol')
                if not ticker or ticker in seen:
                    continue
                if q.get('quoteType', '') != 'EQUITY':
                    continue

                pm_price   = q.get('preMarketPrice')
                prev_close = q.get('regularMarketPreviousClose')

                if not pm_price or not prev_close or prev_close == 0:
                    continue
                if pm_price < min_price:
                    continue

                pm_gap_pct = ((pm_price - prev_close) / prev_close) * 100
                if pm_gap_pct < PM_MIN_MOVE_PCT:
                    continue

                seen.add(ticker)
                stocks.append({
                    'ticker':         ticker,
                    'company_name':   q.get('longName') or q.get('shortName') or ticker,
                    'price':          round(pm_price, 2),
                    'previous_close': round(prev_close, 2),
                    'change':         round(pm_price - prev_close, 2),
                    'change_percent': round(pm_gap_pct, 2),
                    'gap_percent':    round(pm_gap_pct, 2),
                    'volume':         int(q.get('preMarketVolume') or q.get('regularMarketVolume') or 0),
                    'market_cap':     int(q.get('marketCap') or 0),
                    'float_shares':   int(q.get('floatShares') or q.get('sharesOutstanding') or 0),
                    'sector':         q.get('sector') or 'Unknown',
                    'list_date':      None,
                    'data_source':    'yfinance_pm',
                })
        except Exception as e:
            logger.warning(f"yfinance PM {screener_name} unavailable: {e}")

    stocks.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(f"yfinance PM scan — {len(stocks)} pre-market movers found")
    return stocks


def _fetch_afterhours_from_yfinance(min_price):
    """
    After-hours specific scanner.  yfinance's standard screeners (day_gainers,
    small_cap_gainers) only expose regularMarketPrice, so they miss stocks whose
    only catalyst arrived after 4 PM ET.  This function reads postMarketPrice and
    postMarketChangePercent from the most_actives screener to surface them.

    Gap% here is AH price vs today's regular close (not yesterday's close),
    because that is the meaningful move for an AH catalyst.
    """
    import yfinance as yf

    AH_MIN_MOVE_PCT = 2.0  # ignore trivial AH ticks
    seen   = set()
    stocks = []

    for screener_name in ('most_actives', 'day_gainers', 'small_cap_gainers'):
        try:
            result = yf.screen(screener_name)
            quotes = result.get('quotes', [])
            logger.info(f"yfinance AH scan ({screener_name}): {len(quotes)} stocks to check")
            for q in quotes:
                ticker = q.get('symbol')
                if not ticker or ticker in seen:
                    continue
                if q.get('quoteType', '') != 'EQUITY':
                    continue

                post_price    = q.get('postMarketPrice')
                regular_close = q.get('regularMarketPrice')  # today's close as AH baseline
                if not post_price or not regular_close or regular_close == 0:
                    continue
                if post_price < min_price:
                    continue

                ah_gap_pct = ((post_price - regular_close) / regular_close) * 100
                if ah_gap_pct < AH_MIN_MOVE_PCT:
                    continue

                seen.add(ticker)
                stocks.append({
                    'ticker':         ticker,
                    'company_name':   q.get('longName') or q.get('shortName') or ticker,
                    'price':          round(post_price, 2),
                    'previous_close': round(regular_close, 2),
                    'change':         round(post_price - regular_close, 2),
                    'change_percent': round(ah_gap_pct, 2),
                    'gap_percent':    round(ah_gap_pct, 2),
                    'volume':         int(q.get('regularMarketVolume') or 0),
                    'market_cap':     int(q.get('marketCap') or 0),
                    'float_shares':   int(q.get('floatShares') or q.get('sharesOutstanding') or 0),
                    'sector':         q.get('sector') or 'Unknown',
                    'list_date':      None,
                    'data_source':    'yfinance_ah',
                })
        except Exception as e:
            logger.warning(f"yfinance AH {screener_name} unavailable: {e}")

    stocks.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(f"yfinance AH scan — {len(stocks)} after-hours movers found")
    return stocks


def _enrich_missing_fundamentals(stocks: list) -> None:
    """
    Fill market_cap, float_shares, company_name, and sector for Alpaca-sourced
    stocks that are missing any of these fields.

    Cache strategy
    ─────────────
    _fundamentals_cache (module-level dict) maps ticker → data dict.
    Every ticker is cached after the first fetch attempt — including tickers
    where yfinance returned all-zero/Unknown — so we never hammer Yahoo Finance
    with repeated calls for the same symbol in the same process lifetime.

    A cached entry with all-zero values just means "Yahoo Finance has no useful
    data for this ticker"; _apply_fundamentals will be a no-op for it.
    Network failures (exception / empty info) are NOT cached so they retry
    on the next scan cycle.
    """
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _needs_enrichment(s: dict) -> bool:
        return (
            not s.get('market_cap') or
            not s.get('float_shares') or
            s.get('sector') in (None, 'Unknown', '')
        )

    def _apply(stock: dict, data: dict) -> None:
        """Write fetched/cached fundamentals into a stock dict in-place."""
        if data.get('market_cap'):
            stock['market_cap'] = data['market_cap']
        if data.get('float_shares'):
            stock['float_shares'] = data['float_shares']
        if data.get('sector') and data['sector'] != 'Unknown':
            stock['sector'] = data['sector']
        # Only overwrite company_name when it's still the raw ticker symbol
        if data.get('company_name') and data['company_name'] != stock.get('ticker'):
            stock['company_name'] = data['company_name']

    missing = [s for s in stocks if _needs_enrichment(s)]
    if not missing:
        return

    cache_hits = [s for s in missing if s['ticker'] in _fundamentals_cache]
    need_fetch  = [s for s in missing if s['ticker'] not in _fundamentals_cache]

    for s in cache_hits:
        _apply(s, _fundamentals_cache[s['ticker']])

    if not need_fetch:
        logger.info(f'Fundamentals: {len(cache_hits)} cache hits, nothing to fetch')
        return

    def _fetch(ticker: str):
        try:
            info = yf.Ticker(ticker).info
            if not info or not isinstance(info, dict):
                return ticker, None          # network/parse failure — don't cache
            return ticker, {
                'market_cap':   int(info.get('marketCap') or 0),
                'float_shares': int(info.get('floatShares') or
                                    info.get('sharesOutstanding') or 0),
                'company_name': (info.get('longName') or
                                 info.get('shortName') or ticker),
                'sector':       info.get('sector') or 'Unknown',
            }
        except Exception:
            return ticker, None              # network/parse failure — don't cache

    info_map: dict = {}
    try:
        with ThreadPoolExecutor(max_workers=15) as ex:
            futures = {ex.submit(_fetch, s['ticker']) for s in need_fetch}
            for future in as_completed(futures, timeout=25):
                try:
                    ticker, data = future.result()
                    info_map[ticker] = data
                except Exception:
                    pass
    except Exception as _te:
        logger.warning(f'Fundamentals fetch pool error: {_te}')

    fetched = enriched = 0
    for s in need_fetch:
        ticker = s['ticker']
        data = info_map.get(ticker)      # None = network failure
        if data is None:
            continue                     # not cached — will retry next scan

        # Always cache so we never call yfinance twice for the same ticker.
        # Even all-zero results get cached: _apply is a no-op for those.
        _fundamentals_cache[ticker] = data
        fetched += 1
        if data.get('market_cap') or data.get('float_shares'):
            enriched += 1
        _apply(s, data)

    logger.info(
        f'Fundamentals: {len(cache_hits)} cache hits, '
        f'{fetched}/{len(need_fetch)} fetched, {enriched} with useful data'
    )


def get_gap_up_stocks_for_frontend():
    """
    Session-routed gap-up scanner. Primary source changes by market session:
      pre_market / closed  → yfinance preMarketPrice  (Alpaca movers is stale before open)
      open                 → Alpaca movers             (real-time SIP, most accurate intraday)
      after_hours          → yfinance postMarketPrice  (Alpaca movers shows today's close %, not AH)
    yfinance day_gainers always runs as supplemental for metadata enrichment + missed tickers.
    Raises only if all sources fail.
    """
    GAP_UP_MIN_PRICE = 0.0

    cache_key = "gap_up_frontend_all"

    cached_result = gap_up_cache.get(cache_key, "real_time")
    if cached_result is not None:
        logger.info(f"Cache HIT: returning {len(cached_result)} gap-up stocks")
        return cached_result

    market_status = check_market_timing()

    # ── Session-specific primary source ──────────────────────────────────────
    primary_stocks = []
    primary_error  = None
    primary_label  = 'none'

    if market_status in ('pre_market', 'closed'):
        # Alpaca movers resets at market open and shows yesterday's data until then.
        # yfinance preMarketPrice is the only reliable source for today's gap-ups.
        primary_label = 'yfinance_pm'
        try:
            primary_stocks = _fetch_premarket_from_yfinance(GAP_UP_MIN_PRICE)
        except Exception as e:
            primary_error = e
            logger.warning(f"yfinance pre-market scan unavailable: {e}")

    elif market_status == 'open':
        # Alpaca movers uses real-time SIP data during market hours — best available source.
        primary_label = 'alpaca'
        try:
            primary_stocks = _fetch_from_alpaca(GAP_UP_MIN_PRICE)
        except Exception as e:
            primary_error = e
            logger.warning(f"Alpaca movers unavailable: {e}")

        # Supplemental: most-actives by share volume catches micro-cap runners
        # (e.g. 100%+ movers) that Alpaca's movers liquidity filter may exclude.
        try:
            actives_stocks = _fetch_from_alpaca_most_actives(GAP_UP_MIN_PRICE)
            seen_primary = {s['ticker'] for s in primary_stocks}
            added = 0
            for s in actives_stocks:
                if s['ticker'] not in seen_primary:
                    primary_stocks.append(s)
                    seen_primary.add(s['ticker'])
                    added += 1
            if added:
                logger.info(f'Alpaca most-actives supplemental: added {added} tickers not in movers')
        except Exception as e:
            logger.warning(f"Alpaca most-actives supplemental failed: {e}")

        # Full-universe scan: snapshot every active US equity and filter by gap%.
        # This is the only source that guarantees catching any mover regardless of
        # market cap or liquidity.  Runs every 5 min (own cache key) so it doesn't
        # add latency to the fast 30-60 s refresh cycle.
        try:
            universe_cached = gap_up_cache.get('gap_up_universe_scan', 'default')
            if universe_cached is None:
                universe_stocks = _fetch_from_alpaca_universe_scan(GAP_UP_MIN_PRICE, min_gap_pct=2.0)
                gap_up_cache.set('gap_up_universe_scan', universe_stocks, 'default')  # 5-min TTL
            else:
                universe_stocks = universe_cached
            seen_primary = {s['ticker'] for s in primary_stocks}
            added_u = 0
            for s in universe_stocks:
                if s['ticker'] not in seen_primary:
                    primary_stocks.append(s)
                    seen_primary.add(s['ticker'])
                    added_u += 1
            if added_u:
                logger.info(f'Universe scan supplemental: added {added_u} tickers')
        except Exception as e:
            logger.warning(f"Universe scan supplemental failed: {e}")

    # after_hours: Alpaca still shows today's closing movers (not AH catalysts);
    # the dedicated AH scan below handles that session — primary_stocks stays empty.

    # ── Day gainers: metadata enrichment + missed tickers ────────────────────
    yf_stocks = []
    try:
        yf_stocks = _fetch_from_yfinance(GAP_UP_MIN_PRICE)
    except Exception as e:
        logger.warning(f"yfinance screener unavailable: {e}")

    if not primary_stocks and not yf_stocks:
        if primary_error:
            raise primary_error
        raise RuntimeError("No gap-up data available from any source")

    # Enrich primary stocks with yfinance metadata where available.
    # Primary price/change_pct data always takes priority.
    yf_meta = {s['ticker']: s for s in yf_stocks}
    for s in primary_stocks:
        if s['ticker'] in yf_meta:
            yf = yf_meta[s['ticker']]
            s['company_name'] = yf.get('company_name') or s['ticker']
            s['market_cap']   = yf.get('market_cap', 0)
            s['float_shares'] = yf.get('float_shares', 0)
            s['sector']       = yf.get('sector', 'Unknown')

    # Primary first; day_gainers adds tickers not covered by primary
    seen   = {s['ticker'] for s in primary_stocks}
    merged = list(primary_stocks)
    for s in yf_stocks:
        if s['ticker'] not in seen:
            merged.append(s)
            seen.add(s['ticker'])

    # Supplemental small-cap scan
    yf_extra = []
    try:
        yf_extra = _fetch_from_yfinance_extra(GAP_UP_MIN_PRICE)
    except Exception as e:
        logger.warning(f"yfinance extra screeners unavailable: {e}")
    for s in yf_extra:
        if s['ticker'] not in seen:
            merged.append(s)
            seen.add(s['ticker'])

    # After-hours specific scan
    yf_ah = []
    if market_status == 'after_hours':
        try:
            yf_ah = _fetch_afterhours_from_yfinance(GAP_UP_MIN_PRICE)
        except Exception as e:
            logger.warning(f"yfinance AH scan unavailable: {e}")
        for s in yf_ah:
            if s['ticker'] not in seen:
                merged.append(s)
                seen.add(s['ticker'])

    merged.sort(key=lambda x: x['gap_percent'], reverse=True)

    # Enrich stocks that still have market_cap=0 (Alpaca-sourced) with yfinance fundamentals.
    # Cache means subsequent scans are instant; only new tickers hit the network.
    _enrich_missing_fundamentals(merged)

    _tag_with_session(merged)

    # Persist tagged stocks to DB — session column is never overwritten on conflict
    # so pre-market tags survive subsequent intraday re-fetches.
    try:
        from database import db_manager
        et_tz = pytz.timezone('US/Eastern')
        today = dt.now(et_tz).date().isoformat()
        db_manager.upsert_gap_up_stocks(today, merged)
    except Exception as e:
        logger.warning(f"Could not persist gap-up stocks to DB: {e}")

    yf_added = sum(1 for s in yf_stocks if s['ticker'] not in {p['ticker'] for p in primary_stocks})
    logger.info(
        f"[{market_status}] Merged {len(merged)} gap-up stocks "
        f"({len(primary_stocks)} {primary_label}, {yf_added} yfinance day_gainers, "
        f"{len(yf_extra)} small-cap extra, {len(yf_ah)} AH)"
    )

    gap_up_cache.set(cache_key, merged, "real_time")
    return merged







if __name__ == "__main__":
    gap_ups = get_gap_up_stocks_for_frontend()
    print(f"Found {len(gap_ups)} gap-up stocks")
    for stock in gap_ups[:5]:
        print(f"  {stock['ticker']}: {stock['gap_percent']}% gap") 