#!/usr/bin/env python3
"""
Real Gap-Up Stock Detection using Polygon API
Based on the trading-advisor project implementation
"""

import os
import datetime
import sqlite3
from datetime import datetime as dt, timedelta
import pytz
from polygon import RESTClient
from dotenv import load_dotenv
from logging_config import get_logger
from gap_up_cache import cached_gap_up_detection, cached_real_time_detection, get_cached_gap_up_stocks, set_cached_gap_up_stocks, get_cached_frontend_gap_ups, set_cached_frontend_gap_ups, invalidate_gap_up_cache

# Load environment variables
load_dotenv()

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
    'closed':      'intraday',   # outside hours → bucket into intraday as fallback
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
        today = dt.now(et_tz).date().isoformat()
        rows = db_manager.get_gap_up_snapshot(today)
        _session_tracker = {
            row['ticker']: {'session': row['session'], 'date': today}
            for row in rows if row.get('session')
        }
        if _session_tracker:
            logger.info(f"Restored {len(_session_tracker)} session tracker entries from DB")
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

def get_polygon_client():
    """Get Polygon API client with API key"""
    # Try to get API key from environment variable first
    api_key = os.environ.get('POLYGON_API_KEY')
    
    # If not found, use the one from trading-advisor project
    if not api_key:
        api_key = "4CylhlrrwfJpekCA76ni_E9g1jibSTIw"
        logger.info("Using default Polygon API key from trading-advisor project")
    
    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable is required")
    
    return RESTClient(api_key)

def get_previous_close_price(ticker, polygon_client):
    """
    Fetches the last trading day's close price for the given ticker using Polygon aggregates endpoint.
    Returns the close price as a float, or None if not available.
    """
    # Get last trading day (skip weekends/holidays)
    today = dt.now().date()
    last_trading_day = today - timedelta(days=1)
    
    # Skip weekends (Saturday = 5, Sunday = 6)
    while last_trading_day.weekday() >= 5:
        last_trading_day -= timedelta(days=1)
    
    date_str = last_trading_day.strftime("%Y-%m-%d")
    logger.info(f"🔍 Using last trading day: {date_str} for {ticker}")
    
    try:
        aggs = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=date_str,
            to=date_str
        )
        if aggs and len(aggs) > 0:
            close_price = aggs[0].close
            logger.info(f"✅ Previous close for {ticker}: ${close_price}")
            return close_price
        else:
            logger.warning(f"❌ No previous close found for {ticker}")
            return None
    except Exception as e:
        logger.error(f"❌ Error fetching previous close for {ticker}: {e}")
        return None

# Note: get_real_time_quote function removed - using delayed data for cost optimization
# Real-time quotes are not needed for early morning gap-up detection

def get_current_price(ticker, polygon_client):
    """
    Get current price for a ticker using Polygon aggregates endpoint for today
    Uses delayed data (15-min delay) to reduce API costs - suitable for early morning gap-up detection
    """
    try:
        today = dt.now().date()
        date_str = today.strftime("%Y-%m-%d")
        
        logger.info(f"🔍 Getting current price for {ticker} on {date_str}")
        
        # Check current time to determine market status
        current_time = dt.now()
        market_status = check_market_timing()
        
        logger.info(f"🕐 Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Use delayed data for all market conditions to reduce API costs
        # This is suitable for early morning gap-up detection
        logger.info(f"📈 Using delayed data (15-min delay) for cost optimization")
        
        # Use aggregates with 15-minute delay
        aggs = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="minute",
            from_=date_str,
            to=date_str,
            limit=1
        )
        
        if aggs and len(aggs) > 0:
            current_price = aggs[0].close
            logger.info(f"✅ Current price for {ticker}: ${current_price} (delayed data)")
            return current_price
        else:
            logger.warning(f"❌ No current price data for {ticker}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error getting current price for {ticker}: {e}")
        return None

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

def get_gap_up_stocks():
    """Alias kept for backwards compatibility — delegates to get_gap_up_stocks_for_frontend."""
    return get_gap_up_stocks_for_frontend()

# Ticker suffixes that reliably indicate non-common-stock instruments
_NON_CS_SUFFIXES = ('W', 'WS', 'R', 'U', 'Z')

def _ticker_looks_non_cs(ticker):
    t = ticker.upper().replace('.', '')
    return any(t.endswith(s) for s in _NON_CS_SUFFIXES)


def _fetch_from_polygon(min_price):
    """
    Fetch gap-up stocks using Polygon's gainers snapshot endpoint.
    Raises on any API error (e.g. insufficient plan).
    When get_ticker_details returns NOT_FOUND, falls back to a ticker-suffix
    heuristic so valid stocks aren't silently dropped.
    """
    polygon_client = get_polygon_client()
    market_status = check_market_timing()
    logger.info(f"Fetching market gainers via Polygon (status: {market_status})")

    snapshots = polygon_client.get_snapshot_direction("stocks", direction="gainers")

    if not snapshots or not isinstance(snapshots, list):
        logger.warning("No gainers returned from Polygon API")
        return []

    logger.info(f"Processing {len(snapshots)} gainers from Polygon snapshot")

    gap_up_stocks = []
    skipped_non_cs = 0
    skipped_price = 0
    skipped_no_data = 0

    for item in snapshots:
        ticker = getattr(item, 'ticker', None)
        if not ticker:
            continue

        try:
            prev_day   = getattr(item, 'prev_day', None)
            day        = getattr(item, 'day', None)
            last_trade = getattr(item, 'last_trade', None)  # most recent trade (pre-market aware)

            previous_close = getattr(prev_day, 'close', None) if prev_day else None

            # Prefer last_trade price: it reflects pre-market activity during pre-market hours,
            # whereas day.close may still be yesterday's close before any trades execute today.
            last_trade_price = (getattr(last_trade, 'price', None)
                                or getattr(last_trade, 'p', None)) if last_trade else None
            current_price    = last_trade_price or (getattr(day, 'close', None) if day else None)
            volume           = getattr(day, 'volume', 0) if day else 0

            # todaysChangePerc is computed server-side by Polygon using the most recent price
            # vs prevDay.close — more accurate than recomputing from day.close.
            todays_change_perc = getattr(item, 'todays_change_perc', None)

            if previous_close is None or previous_close == 0:
                skipped_no_data += 1
                continue
            if current_price is None or current_price == 0:
                skipped_no_data += 1
                continue

            if current_price < min_price:
                skipped_price += 1
                continue

            # Try to get ticker details; if NOT_FOUND fall back to suffix heuristic
            company_name = ticker
            market_cap   = 0
            sector       = 'Unknown'
            list_date    = None
            float_shares = 0
            try:
                details      = polygon_client.get_ticker_details(ticker)
                ticker_type  = getattr(details, 'type', None)
                if ticker_type != "CS":
                    skipped_non_cs += 1
                    continue
                company_name = details.name
                market_cap   = getattr(details, 'market_cap', 0)
                sector       = getattr(details, 'sic_description', 'Unknown')
                list_date    = getattr(details, 'list_date', None)
                float_shares = int(
                    getattr(details, 'share_class_shares_outstanding', None) or
                    getattr(details, 'weighted_shares_outstanding', None) or 0
                )
            except Exception:
                # Details unavailable — use ticker suffix to exclude obvious non-CS
                if _ticker_looks_non_cs(ticker):
                    skipped_non_cs += 1
                    continue
                logger.warning(f"Ticker details not found for {ticker}; including based on suffix check")

            # Use server-side percent when available; fall back to local computation
            if todays_change_perc is not None:
                gap_percent = float(todays_change_perc)
            else:
                gap_percent = ((current_price - previous_close) / previous_close) * 100

            gap_up_stocks.append({
                'ticker':         ticker,
                'company_name':   company_name,
                'price':          round(current_price, 2),
                'previous_close': round(previous_close, 2),
                'change':         round(current_price - previous_close, 2),
                'change_percent': round(gap_percent, 2),
                'gap_percent':    round(gap_percent, 2),
                'volume':         int(volume or 0),
                'market_cap':     market_cap,
                'float_shares':   float_shares,
                'sector':         sector,
                'list_date':      list_date,
                'data_source':    'polygon',
            })

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            continue

    gap_up_stocks.sort(key=lambda x: x['gap_percent'], reverse=True)
    logger.info(
        f"Polygon done — {len(gap_up_stocks)} gap-ups "
        f"(skipped: {skipped_non_cs} non-CS, {skipped_price} below ${min_price}, "
        f"{skipped_no_data} missing data)"
    )
    return gap_up_stocks


def _fetch_from_yfinance(min_price):
    """
    Fallback: fetch gap-up stocks using yfinance day_gainers screener.
    Returns data in the same shape as _fetch_from_polygon.
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
                'float_shares':   int(q.get('sharesOutstanding') or q.get('floatShares') or 0),
                'sector':         'Unknown',
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
    Returns data in the same shape as _fetch_from_polygon/_fetch_from_yfinance.
    """
    import yfinance as yf

    extra_screeners = ['small_cap_gainers', 'aggressive_small_caps']
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
                        'float_shares':   int(q.get('sharesOutstanding') or q.get('floatShares') or 0),
                        'sector':         'Unknown',
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


def get_gap_up_stocks_for_frontend():
    """
    Fetch gap-up stocks from Polygon and yfinance, merge them, and return a
    deduplicated list sorted by gap% descending. Polygon data takes priority
    (richer metadata). Raises only if both sources fail.
    """
    GAP_UP_MIN_PRICE = 0.0

    from gap_up_cache import gap_up_cache
    cache_key = "gap_up_frontend_all"

    cached_result = gap_up_cache.get(cache_key, "real_time")
    if cached_result is not None:
        logger.info(f"Cache HIT: returning {len(cached_result)} gap-up stocks")
        return cached_result

    polygon_stocks = []
    polygon_error  = None
    try:
        polygon_stocks = _fetch_from_polygon(GAP_UP_MIN_PRICE)
    except Exception as e:
        polygon_error = e
        logger.warning(f"Polygon gainers unavailable: {e}")

    yf_stocks = []
    try:
        yf_stocks = _fetch_from_yfinance(GAP_UP_MIN_PRICE)
    except Exception as e:
        logger.warning(f"yfinance screener unavailable: {e}")

    if not polygon_stocks and not yf_stocks:
        if polygon_error:
            raise polygon_error
        raise RuntimeError("No gap-up data available from any source")

    # Merge: Polygon entries take priority; yfinance day_gainers fills in missing tickers
    seen   = {s['ticker'] for s in polygon_stocks}
    merged = list(polygon_stocks)
    for s in yf_stocks:
        if s['ticker'] not in seen:
            merged.append(s)
            seen.add(s['ticker'])

    # Supplemental small-cap scan: catches micro/small caps not in top-N of either source
    yf_extra = []
    try:
        yf_extra = _fetch_from_yfinance_extra(GAP_UP_MIN_PRICE)
    except Exception as e:
        logger.warning(f"yfinance extra screeners unavailable: {e}")
    for s in yf_extra:
        if s['ticker'] not in seen:
            merged.append(s)
            seen.add(s['ticker'])

    merged.sort(key=lambda x: x['gap_percent'], reverse=True)
    _tag_with_session(merged)

    # Persist tagged stocks to DB — session column is never overwritten on conflict
    # so pre-market tags survive subsequent intraday re-fetches.  This also makes
    # past-date viewing accurate throughout the day, not just after the 8 PM save.
    try:
        from database import db_manager
        et_tz = pytz.timezone('US/Eastern')
        today = dt.now(et_tz).date().isoformat()
        db_manager.upsert_gap_up_stocks(today, merged)
    except Exception as e:
        logger.warning(f"Could not persist gap-up stocks to DB: {e}")

    polygon_only = len(polygon_stocks)
    yf_day_only  = sum(1 for s in yf_stocks if s['ticker'] not in {p['ticker'] for p in polygon_stocks})
    logger.info(
        f"Merged result: {len(merged)} gap-up stocks "
        f"({polygon_only} polygon, {yf_day_only} yfinance day_gainers, {len(yf_extra)} small-cap extra)"
    )

    gap_up_cache.set(cache_key, merged, "real_time")
    return merged







def debug_ticker(ticker):
    """
    Debug function to test ticker data retrieval
    """
    try:
        polygon_client = get_polygon_client()
        
        logger.info(f"🔍 Debugging {ticker}...")
        
        # Get ticker details
        details = polygon_client.get_ticker_details(ticker)
        logger.info(f"📊 Ticker Details: {details.name} ({details.type})")
        
        # Get previous close
        previous_close = get_previous_close_price(ticker, polygon_client)
        logger.info(f"📊 Previous Close: ${previous_close}")
        
        # Get current price
        current_price = get_current_price(ticker, polygon_client)
        logger.info(f"📊 Current Price: ${current_price}")
        
        if previous_close and current_price:
            gap_percent = ((current_price - previous_close) / previous_close) * 100
            logger.info(f"📊 Gap Percentage: {gap_percent:.2f}%")
            
            if gap_percent >= 2.0:
                logger.info(f"✅ {ticker} is a gap-up stock!")
            else:
                logger.info(f"❌ {ticker} is not a gap-up stock")
        else:
            logger.warning(f"⚠️ Could not calculate gap for {ticker}")
            
    except Exception as e:
        logger.error(f"❌ Error debugging {ticker}: {e}")

def test_polygon_data_availability(ticker):
    """
    Test function to check Polygon data availability for a ticker
    """
    try:
        polygon_client = get_polygon_client()
        
        logger.info(f"🧪 Testing Polygon data availability for {ticker}...")
        
        # Test ticker details
        try:
            details = polygon_client.get_ticker_details(ticker)
            logger.info(f"✅ Ticker details available: {details.name}")
        except Exception as e:
            logger.error(f"❌ Ticker details failed: {e}")
        
        # Test previous close
        try:
            previous_close = get_previous_close_price(ticker, polygon_client)
            logger.info(f"✅ Previous close available: ${previous_close}")
        except Exception as e:
            logger.error(f"❌ Previous close failed: {e}")
        
        # Test current price
        try:
            current_price = get_current_price(ticker, polygon_client)
            logger.info(f"✅ Current price available: ${current_price}")
        except Exception as e:
            logger.error(f"❌ Current price failed: {e}")
        
        # Test real-time quote
        # try:
        #     quote = get_real_time_quote(ticker, polygon_client)
        #     logger.info(f"✅ Real-time quote available: ${quote}")
        # except Exception as e:
        #     logger.error(f"❌ Real-time quote failed: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error testing {ticker}: {e}")

if __name__ == "__main__":
    # Test the gap-up detection
    gap_ups = get_gap_up_stocks()
    print(f"Found {len(gap_ups)} gap-up stocks")
    for stock in gap_ups[:5]:  # Show first 5
        print(f"  {stock['ticker']}: {stock['gap_percent']}% gap") 