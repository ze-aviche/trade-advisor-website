#!/usr/bin/env python3
"""
Historical Data Analysis Module for Gap-Trade-Bot
Provides comprehensive historical data analysis for stocks with intelligent caching
"""
import os
import time
import datetime
from datetime import datetime as dt, timedelta
import pytz
import requests
from polygon import RESTClient
from dotenv import load_dotenv
from historical_cache import historical_cache
import logging
import concurrent.futures
import threading
from logging_config import get_logger, log_performance, log_cache_operation, log_error

# Get logger for this module
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

_ET_TZ = pytz.timezone('America/New_York')

def _alpaca_bars_raw(ticker, start_iso, end_iso, timeframe='1Min'):
    """Fetch bars from Alpaca Data API with pagination, returning list of raw dicts.

    Tries feed=sip first (full market data); falls back to feed=iex on 403
    so free-tier Alpaca accounts still work.
    """
    key    = os.environ.get('ALPACA_API_KEY', '')
    secret = os.environ.get('ALPACA_API_SECRET', '')
    if not key or not secret:
        logger.warning('_alpaca_bars_raw: ALPACA_API_KEY / ALPACA_API_SECRET not set')
        return []
    url     = f'https://data.alpaca.markets/v2/stocks/{ticker.upper()}/bars'
    headers = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}

    feeds_to_try = ['sip', 'iex']
    for feed in feeds_to_try:
        params = {'timeframe': timeframe, 'start': start_iso, 'end': end_iso,
                  'limit': 10000, 'adjustment': 'raw', 'feed': feed}
        all_bars  = []
        http_code = None   # last HTTP status seen on this feed attempt
        failed    = False
        while True:
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                http_code = resp.status_code
                if http_code != 200:
                    body = resp.text[:300]
                    if http_code == 403 and feed == 'sip':
                        logger.warning(
                            f'_alpaca_bars_raw {ticker}: SIP feed returned 403 '
                            f'(subscription limit) — retrying with IEX feed. body={body}')
                    else:
                        logger.warning(
                            f'_alpaca_bars_raw {ticker}: HTTP {http_code} '
                            f'feed={feed} body={body}')
                    failed = True
                    break
                data = resp.json()
                all_bars.extend(data.get('bars') or [])
                token = data.get('next_page_token')
                if not token:
                    break
                params['page_token'] = token
            except Exception as e:
                logger.warning(f'_alpaca_bars_raw {ticker} feed={feed}: {e}')
                failed = True
                break
        if not failed:
            return all_bars
        # 403 on SIP → try IEX next; any other failure → give up
        if not (http_code == 403 and feed == 'sip'):
            break
    return []

def _et_to_iso(date_str, time_str):
    """Convert 'YYYY-MM-DD' + 'HH:MM' ET to a UTC ISO string (handles DST via pytz)."""
    naive = dt.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
    return _ET_TZ.localize(naive).astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

class _BarData:
    """Wraps an Alpaca bar dict with attributes for backward compat with process_batch_data_to_gap_ups."""
    __slots__ = ('timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap')
    def __init__(self, bar_dict):
        t = bar_dict.get('t', '')
        try:
            ts_dt = dt.fromisoformat(t.replace('Z', '+00:00'))
            self.timestamp = int(ts_dt.timestamp() * 1000)
        except Exception:
            self.timestamp = 0
        self.open   = float(bar_dict.get('o') or 0)
        self.high   = float(bar_dict.get('h') or 0)
        self.low    = float(bar_dict.get('l') or 0)
        self.close  = float(bar_dict.get('c') or 0)
        self.volume = int(bar_dict.get('v') or 0)
        self.vwap   = bar_dict.get('vw')

def get_polygon_client():
    """Get Polygon API client with API key and timeout configuration"""
    api_key = os.environ.get('POLYGON_API_KEY')
    if not api_key:
        api_key = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
        print("Using default Polygon API key")
    
    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable is required")
    
    # Create client with timeout configuration
    client = RESTClient(api_key)
    
    # Set timeout for requests (if supported by the client)
    try:
        # Some REST clients support timeout configuration
        if hasattr(client, 'timeout'):
            client.timeout = 15  # 15 seconds timeout
    except:
        pass  # If timeout is not supported, continue without it
    
    return client

def count_vwap_crosses(polygon_client, ticker, date):
    """
    Fetches 2-minute bar data for a given ticker and date and counts VWAP crosses.
    Uses Alpaca Data API (2-min bars included in Algo Trader Plus plan).
    polygon_client parameter is kept for backward compatibility but is not used.
    """
    import requests as _req
    alpaca_key    = os.environ.get('ALPACA_API_KEY', '')
    alpaca_secret = os.environ.get('ALPACA_API_SECRET', '')
    if not alpaca_key or not alpaca_secret:
        logger.debug(f'count_vwap_crosses: Alpaca keys not configured — skipping for {ticker} {date}')
        return None

    # date may be a datetime.date or a string 'YYYY-MM-DD'
    date_str = date.isoformat() if hasattr(date, 'isoformat') else str(date)
    url = f'https://data.alpaca.markets/v2/stocks/{ticker.upper()}/bars'
    params = {
        'timeframe': '2Min',
        'start':     f'{date_str}T00:00:00Z',
        'end':       f'{date_str}T23:59:59Z',
        'limit':     10000,
        'adjustment': 'raw',
        'feed':      'sip',
    }
    headers = {
        'APCA-API-KEY-ID':     alpaca_key,
        'APCA-API-SECRET-KEY': alpaca_secret,
    }
    try:
        resp = _req.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            logger.debug(f'count_vwap_crosses: Alpaca HTTP {resp.status_code} for {ticker} {date_str}')
            return None
        bars = resp.json().get('bars') or []
    except Exception as e:
        logger.debug(f'count_vwap_crosses: fetch error for {ticker} {date_str}: {e}')
        return None

    if not bars:
        return 0

    # Alpaca returns vw (bar VWAP) directly — use it the same way the original
    # Polygon code did: compare each bar's close vs its own bar VWAP.
    cross_count = 0
    prev_close = bars[0].get('c')
    prev_vwap  = bars[0].get('vw')

    for b in bars[1:]:
        curr_close = b.get('c')
        curr_vwap  = b.get('vw')
        if None in (prev_close, prev_vwap, curr_close, curr_vwap):
            prev_close, prev_vwap = curr_close, curr_vwap
            continue
        if (prev_close < prev_vwap and curr_close > curr_vwap) or \
           (prev_close > prev_vwap and curr_close < curr_vwap):
            cross_count += 1
        prev_close, prev_vwap = curr_close, curr_vwap

    return cross_count

def get_premarket_high_low_data(ticker, polygon_client, date_str):
    """
    Fetches premarket high/low data for a given ticker and date (4:00 AM to 9:30 AM EST).
    polygon_client is kept for backward compatibility but is not used.
    """
    try:
        logger.debug(f"🔍 Fetching premarket data for {ticker} on {date_str} (4:00-9:30 AM EST)")

        start_iso = _et_to_iso(date_str, '04:00')
        end_iso   = _et_to_iso(date_str, '09:30')
        bars = _alpaca_bars_raw(ticker, start_iso, end_iso, timeframe='1Min')

        if not bars:
            logger.debug(f"⚠️ No premarket data found for {ticker} on {date_str}")
            return None, None, None, None, None

        logger.debug(f"📊 Found {len(bars)} premarket bars for {ticker} on {date_str}")

        # bars are in chronological order; first bar's open = premarket open price
        first_bar_open = float(bars[0].get('o') or 0)

        max_high = -1
        high_bar_t = None
        min_low = float('inf')
        low_bar_t = None

        for bar in bars:
            h = float(bar.get('h') or 0)
            l = float(bar.get('l') or 0)
            if h > max_high:
                max_high = h
                high_bar_t = bar.get('t', '')
            if l < min_low:
                min_low = l
                low_bar_t = bar.get('t', '')

        high_timestamp_est = None
        if high_bar_t:
            high_timestamp_est = dt.fromisoformat(high_bar_t.replace('Z', '+00:00')).astimezone(_ET_TZ).strftime('%H:%M')

        low_timestamp_est = None
        if low_bar_t:
            low_timestamp_est = dt.fromisoformat(low_bar_t.replace('Z', '+00:00')).astimezone(_ET_TZ).strftime('%H:%M')

        logger.debug(f"✅ Premarket data for {ticker} on {date_str}: High={max_high}@{high_timestamp_est}, Low={min_low}@{low_timestamp_est}, FirstOpen={first_bar_open}")
        return max_high, high_timestamp_est, min_low, low_timestamp_est, first_bar_open

    except Exception as e:
        logger.error(f"❌ Error fetching premarket data for {ticker} on {date_str}: {e}")
        return None, None, None, None, None

def get_daily_high_low_data(ticker, polygon_client, date_str):
    """
    Fetches daily high/low data for a given ticker and date (9:30 AM to 4:00 PM EST).
    polygon_client is kept for backward compatibility but is not used.
    """
    try:
        start_iso = _et_to_iso(date_str, '09:30')
        end_iso   = _et_to_iso(date_str, '16:00')
        bars = _alpaca_bars_raw(ticker, start_iso, end_iso, timeframe='1Min')

        if not bars:
            return None, None, None, None

        max_high = -1
        high_bar_t = None
        min_low = float('inf')
        low_bar_t = None

        for bar in bars:
            h = float(bar.get('h') or 0)
            l = float(bar.get('l') or 0)
            if h > max_high:
                max_high = h
                high_bar_t = bar.get('t', '')
            if l < min_low:
                min_low = l
                low_bar_t = bar.get('t', '')

        high_timestamp_est = None
        if high_bar_t:
            high_timestamp_est = dt.fromisoformat(high_bar_t.replace('Z', '+00:00')).astimezone(_ET_TZ).strftime('%H:%M')

        low_timestamp_est = None
        if low_bar_t:
            low_timestamp_est = dt.fromisoformat(low_bar_t.replace('Z', '+00:00')).astimezone(_ET_TZ).strftime('%H:%M')

        return max_high, high_timestamp_est, min_low, low_timestamp_est

    except Exception as e:
        logger.error(f"Error fetching daily data for {ticker} on {date_str}: {e}")
        return None, None, None, None

def get_premarket_volume(polygon_client, ticker, date_str):
    """
    Fetches premarket volume for a given ticker and date (4:00 AM to 9:30 AM EST).
    Returns volume in millions.
    polygon_client is kept for backward compatibility but is not used.
    """
    try:
        start_iso = _et_to_iso(date_str, '04:00')
        end_iso   = _et_to_iso(date_str, '09:30')
        bars = _alpaca_bars_raw(ticker, start_iso, end_iso, timeframe='1Min')

        if not bars:
            logger.debug(f"⚠️ No premarket volume data found for {ticker} on {date_str}")
            return 0.0

        premarket_total_volume_millions = sum(int(bar.get('v') or 0) for bar in bars) / 1_000_000
        logger.debug(f"📊 Premarket volume (millions) for {ticker} on {date_str}: {premarket_total_volume_millions}")
        return round(premarket_total_volume_millions, 2)

    except Exception as e:
        logger.error(f"❌ Error fetching premarket volume for {ticker} on {date_str}: {e}")
        return 0.0

def fetch_single_day_data(ticker, polygon_client, date_str):
    """
    Fetch comprehensive data for a single day from Alpaca Data API.
    Returns a single data point dictionary.
    polygon_client is kept for backward compatibility but is not used.
    """
    try:
        # Get daily bar for this specific date
        day_bars = _alpaca_bars_raw(ticker, f'{date_str}T00:00:00Z', f'{date_str}T23:59:59Z', timeframe='1Day')

        if not day_bars:
            return None

        bar = day_bars[0]
        agg_open   = float(bar.get('o') or 0)
        agg_high   = float(bar.get('h') or 0)
        agg_low    = float(bar.get('l') or 0)
        agg_close  = float(bar.get('c') or 0)
        agg_volume = int(bar.get('v') or 0)

        # Get previous day close for gap calculation (look back up to 7 days for weekends/holidays)
        previous_day_close = None
        for days_back in range(1, 8):
            prev_date = (dt.strptime(date_str, '%Y-%m-%d') - timedelta(days=days_back)).strftime('%Y-%m-%d')
            prev_bars = _alpaca_bars_raw(ticker, f'{prev_date}T00:00:00Z', f'{prev_date}T23:59:59Z', timeframe='1Day')
            if prev_bars:
                previous_day_close = float(prev_bars[-1].get('c') or 0) or None
                if previous_day_close:
                    break

        # Calculate gap percentage
        gap_percent = None
        if previous_day_close and agg_open:
            gap_percent = round(((agg_open - previous_day_close) / previous_day_close) * 100, 2)

        # Get premarket data (polygon_client=None is fine — it's ignored inside)
        premarket_high, premarket_high_time, _, _, premarket_bar_open = get_premarket_high_low_data(ticker, None, date_str)
        premarket_volume = get_premarket_volume(None, ticker, date_str)

        # Get daily high/low data
        daily_high, daily_high_time, _, _ = get_daily_high_low_data(ticker, None, date_str)

        # Calculate percentages
        percent_gap_high = None
        closing_percent = None
        if previous_day_close:
            if daily_high:
                percent_gap_high = round(((daily_high - previous_day_close) / previous_day_close) * 100, 2)
            closing_percent = round(((agg_close - previous_day_close) / previous_day_close) * 100, 2)

        # premarket open: use first premarket bar open
        premarket_open = premarket_bar_open

        # afterhours close: fetch 16:00–20:00 ET bars, take last bar's close
        afterhours_close = None
        try:
            ah_start = _et_to_iso(date_str, '16:00')
            ah_end   = _et_to_iso(date_str, '20:00')
            ah_bars  = _alpaca_bars_raw(ticker, ah_start, ah_end, timeframe='1Min')
            if ah_bars:
                afterhours_close = float(ah_bars[-1].get('c') or 0) or None
        except Exception as e:
            logger.debug(f"afterhours fetch error for {ticker} on {date_str}: {e}")

        # Determine Runner/Fader
        runner_fader = "Runner" if agg_close > agg_open else (
            "Fader" if agg_close < agg_open else "Neutral")

        # VWAP crosses removed for performance optimization
        vwap_crosses = None

        data_point = {
            'date': date_str,
            'pd close': round(previous_day_close, 2) if previous_day_close else None,
            'premarket open': round(premarket_open, 2) if premarket_open else None,
            'premarket high': round(premarket_high, 2) if premarket_high else None,
            'premarket high time': premarket_high_time,
            'premarket volume': premarket_volume,
            'open': round(agg_open, 2),
            'gap up % at open': gap_percent,
            'day high': round(daily_high, 2) if daily_high else round(agg_high, 2),
            'day high time': daily_high_time,
            'day high %': percent_gap_high,
            'close price': round(agg_close, 2),
            'closing percent': closing_percent,
            'afterhours close': round(afterhours_close, 2) if afterhours_close else None,
            'total volume': agg_volume,
            'VWAP Crosses': None,  # Removed for performance
            'Runner/Fader': runner_fader,
            'high': round(agg_high, 2),
            'low': round(agg_low, 2),
            'volume_millions': round(agg_volume / 1000000, 2),
            'dollar_volume_millions': round((agg_volume * agg_high) / 1000000, 2)
        }

        return data_point

    except Exception as e:
        logger.error(f"Error fetching single day data for {ticker} on {date_str}: {e}")
        return None

def get_batch_daily_data(ticker, start_date, end_date):
    """
    Fetch all daily data for a ticker in a single batch API call using Alpaca.
    Returns a list of _BarData objects for backward compat with process_batch_data_to_gap_ups.
    """
    start_time = time.time()
    try:
        raw_bars = _alpaca_bars_raw(
            ticker,
            f'{start_date}T00:00:00Z',
            f'{end_date}T23:59:59Z',
            timeframe='1Day'
        )

        if not raw_bars:
            return []

        # Wrap in _BarData objects (provides .timestamp, .open, .high, .low, .close, .volume, .vwap)
        daily_data = [_BarData(b) for b in raw_bars]
        daily_data.sort(key=lambda x: x.timestamp)

        duration = time.time() - start_time
        log_performance('batch_daily_data', duration, {
            'ticker': ticker,
            'start_date': start_date,
            'end_date': end_date,
            'data_points': len(daily_data)
        })

        logger.info(f"📊 Retrieved {len(daily_data)} days of batch data for {ticker}")
        return daily_data

    except Exception as e:
        logger.error(f"❌ Error fetching batch daily data for {ticker}: {e}")
        return []

def process_batch_data_to_gap_ups(ticker, daily_data, min_gap_percent=5):
    """
    Process batch daily data to extract gap-up information.
    Returns days where the gap-up percentage meets min_gap_percent.
    """
    try:
        major_gap_up_data = []
        
        # Create a dictionary for quick lookup of previous trading days
        daily_data_dict = {}
        for agg in daily_data:
            date_str = dt.utcfromtimestamp(agg.timestamp / 1000).strftime('%Y-%m-%d')
            daily_data_dict[date_str] = agg

        for i, agg in enumerate(daily_data):
            date_str = dt.utcfromtimestamp(agg.timestamp / 1000).strftime('%Y-%m-%d')
            
            # Get previous trading day close for gap calculation
            previous_day_close = None
            
            # Find the actual previous trading day by looking back through the data
            current_date = dt.strptime(date_str, '%Y-%m-%d').date()
            for days_back in range(1, 10):  # Look back up to 10 days to find previous trading day
                prev_date = current_date - timedelta(days=days_back)
                prev_date_str = prev_date.strftime('%Y-%m-%d')
                
                if prev_date_str in daily_data_dict:
                    previous_day_close = daily_data_dict[prev_date_str].close
                    logger.debug(f"📊 Found previous trading day for {date_str}: {prev_date_str} (close: {previous_day_close})")
                    break
            
            # Calculate gap percentage
            gap_percent = None
            if previous_day_close and agg.open:
                gap_percent = round(((agg.open - previous_day_close) / previous_day_close) * 100, 2)
                logger.debug(f"📈 Gap calculation for {date_str}: Open={agg.open}, PrevClose={previous_day_close}, Gap={gap_percent}%")
            
            # Only process if the gap meets the minimum threshold
            if gap_percent and gap_percent >= min_gap_percent:
                logger.info(f"🚀 Found gap-up for {ticker} on {date_str}: {gap_percent}% (min: {min_gap_percent}%)")
                
                # Calculate percentages
                percent_gap_high = None
                closing_percent = None
                if previous_day_close:
                    percent_gap_high = round(((agg.high - previous_day_close) / previous_day_close) * 100, 2)
                    closing_percent = round(((agg.close - previous_day_close) / previous_day_close) * 100, 2)
                
                # Determine Runner/Fader
                runner_fader = "Runner" if agg.close > agg.open else (
                    "Fader" if agg.close < agg.open else "Neutral")
                
                # Get premarket data for gap-up days only (efficient approach)
                premarket_high, premarket_high_time, _, _, premarket_bar_open = get_premarket_high_low_data(ticker, None, date_str)
                premarket_volume = get_premarket_volume(None, ticker, date_str)

                # Get daily high/low data for gap-up days
                daily_high, daily_high_time, _, _ = get_daily_high_low_data(ticker, None, date_str)

                # Get VWAP crosses for gap-up days
                vwap_crosses = count_vwap_crosses(None, ticker, date_str)

                # premarket open from first premarket bar; afterhours close from 16:00–20:00 ET bars
                premarket_open = premarket_bar_open
                afterhours_close = None
                try:
                    ah_start = _et_to_iso(date_str, '16:00')
                    ah_end   = _et_to_iso(date_str, '20:00')
                    ah_bars  = _alpaca_bars_raw(ticker, ah_start, ah_end, timeframe='1Min')
                    if ah_bars:
                        afterhours_close = float(ah_bars[-1].get('c') or 0) or None
                except Exception as e:
                    logger.debug(f"afterhours fetch error for {ticker} on {date_str}: {e}")
                
                data_point = {
                    'date': date_str,
                    'pd close': round(previous_day_close, 2) if previous_day_close else None,
                    'premarket open': round(premarket_open, 2) if premarket_open else None,
                    'premarket high': round(premarket_high, 2) if premarket_high else None,
                    'premarket high time': premarket_high_time,
                    'premarket volume': premarket_volume,
                    'open': round(agg.open, 2),
                    'gap up % at open': gap_percent,
                    'day high': round(daily_high if daily_high else agg.high, 2),
                    'day high time': daily_high_time,
                    'day high %': percent_gap_high,
                    'close price': round(agg.close, 2),
                    'closing percent': closing_percent,
                    'afterhours close': round(afterhours_close, 2) if afterhours_close else None,
                    'total volume': agg.volume,
                    'VWAP Crosses': vwap_crosses,
                    'Runner/Fader': runner_fader,
                    'high': round(agg.high, 2),
                    'low': round(agg.low, 2),
                    'volume_millions': round(agg.volume / 1000000, 2),
                    'dollar_volume_millions': round((agg.volume * agg.high) / 1000000, 2)
                }
                
                major_gap_up_data.append(data_point)
        
        logger.info(f"📈 Found {len(major_gap_up_data)} gap-up days (>={min_gap_percent}%) for {ticker}")
        return major_gap_up_data

    except Exception as e:
        logger.error(f"❌ Error processing batch data for {ticker}: {e}")
        return []

def get_historical_gap_up_data(ticker, days=30, use_cache=True, min_gap_percent=25):
    """
    Get comprehensive historical gap-up data for a stock using intelligent caching.
    Cache stores days with gap >= 5% (low threshold for broad reuse).
    Results are filtered to min_gap_percent before returning.
    """
    start_time = time.time()
    # Helper applied to every return path so callers always get the filtered view
    def _filter(data):
        return [d for d in (data or []) if (d.get('gap up % at open') or 0) >= min_gap_percent]

    try:
        # days=0 means "All Time" — use a far-back date so the full cache is covered
        if days == 0:
            days = 5475  # 15 years; well beyond any data we'll ever cache

        # Calculate date range based on requested days
        end_date = dt.now().date()
        start_date = end_date - timedelta(days=days)

        # Format dates for API and cache
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")

        logger.info(f"📊 Fetching historical gap-up data for {ticker} from {from_date} to {to_date} ({days} days)")
        
        cached_data = []  # Initialize cached_data in outer scope
        
        if use_cache:
            # Check cache status and freshness
            cache_status = historical_cache.get_cache_status(ticker)
            logger.info(f"Cache status for {ticker}: {cache_status}")
            
            # Check if cache is fresh (within 24 hours for recent data)
            is_fresh = historical_cache.is_data_fresh(ticker, max_age_hours=24)
            logger.info(f"Cache freshness for {ticker}: {'Fresh' if is_fresh else 'Stale'}")
            
            # Get cached data for the requested range
            cached_data = historical_cache.get_cached_data(ticker, from_date, to_date)
            logger.info(f"DEBUG: Retrieved {len(cached_data)} cached records for {ticker}")
            
            if cached_data:
                logger.info(f"✅ Found {len(cached_data)} cached gap-up records for {ticker}")
                
                # Check if we have enough gap-up days in the requested date range
                requested_start = (end_date - timedelta(days=days)).strftime("%Y-%m-%d")
                requested_end = to_date
                
                # Filter cached data to only include gap-up days within the requested date range
                requested_cached_data = [data for data in cached_data 
                                      if requested_start <= data['date'] <= requested_end]
                
                logger.info(f"📊 Requested range: {requested_start} to {requested_end}")
                logger.info(f"📊 Found {len(requested_cached_data)} gap-up days in requested range")
                
                # If cache is fresh and we have data, only return early if the cache
                # metadata range fully covers the requested date range.  Without this
                # check a 1-yr cache would satisfy a 3-yr request prematurely.
                if is_fresh and requested_cached_data:
                    cache_range_meta = cache_status.get('data_range', {})
                    cache_start_meta = cache_range_meta.get('start') if cache_range_meta else None
                    cache_end_meta   = cache_range_meta.get('end')   if cache_range_meta else None
                    full_coverage = (
                        cache_start_meta and cache_end_meta
                        and cache_start_meta <= from_date
                        and cache_end_meta   >= to_date
                    )
                    if full_coverage:
                        requested_cached_data.sort(key=lambda x: x['date'], reverse=True)
                        logger.info(f"✅ Returning {len(requested_cached_data)} fresh cached gap-up days for {ticker} (full range covered)")
                        return _filter(requested_cached_data)
                    logger.info(
                        f"🔄 Cache is fresh but does not cover full requested range "
                        f"({from_date}→{to_date}); cache covers ({cache_start_meta}→{cache_end_meta}). "
                        f"Falling through to delta fetch."
                    )
                
                # Check if requested range extends beyond cached range
                cache_range = cache_status.get('data_range', {})
                cache_start = cache_range.get('start') if cache_range else None
                cache_end = cache_range.get('end') if cache_range else None
                
                if cache_start and cache_end:
                    # Check if requested range extends beyond cached range
                    cache_start_date = dt.strptime(cache_start, "%Y-%m-%d").date()
                    cache_end_date = dt.strptime(cache_end, "%Y-%m-%d").date()
                    requested_start_date = dt.strptime(requested_start, "%Y-%m-%d").date()
                    requested_end_date = dt.strptime(requested_end, "%Y-%m-%d").date()
                    
                    # Check if requested range extends beyond cached range
                    extends_before = requested_start_date < cache_start_date
                    extends_after = requested_end_date > cache_end_date
                    
                    if extends_before or extends_after:
                        # Requested range extends beyond cached range, fetch delta
                        logger.info(f"🔄 Requested range extends beyond cache (before: {extends_before}, after: {extends_after})")
                        
                        # Calculate the actual missing date ranges
                        missing_dates = []
                        if extends_before:
                            # Get missing dates from requested_start to cache_start_date - 1 day
                            missing_before = historical_cache.get_cache_gaps(ticker, requested_start, (cache_start_date - timedelta(days=1)).strftime('%Y-%m-%d'))
                            missing_dates.extend(missing_before)
                            logger.info(f"DEBUG: Found {len(missing_before)} missing dates before cache")
                        
                        if extends_after:
                            # Get missing dates from cache_end_date + 1 day to requested_end
                            missing_after = historical_cache.get_cache_gaps(ticker, (cache_end_date + timedelta(days=1)).strftime('%Y-%m-%d'), requested_end)
                            missing_dates.extend(missing_after)
                            logger.info(f"DEBUG: Found {len(missing_after)} missing dates after cache")
                        
                        logger.info(f"DEBUG: Found {len(missing_dates)} total missing dates for requested range")
                        
                        if missing_dates:
                            # Use optimized batch delta processing instead of individual day fetching
                            delta_data = get_batch_delta_data(ticker, missing_dates)
                            
                            # Store new delta data in cache (even if empty)
                            if delta_data:
                                historical_cache.store_historical_data(ticker, delta_data, requested_start, requested_end)
                                logger.info(f"💾 Cached {len(delta_data)} new gap-up days from delta for {ticker}")
                            else:
                                # Cache empty delta result to avoid re-searching this period
                                historical_cache.store_historical_data(ticker, [], requested_start, requested_end)
                                logger.info(f"💾 Cached empty delta result (no gap-ups) for {ticker} in period {requested_start} to {requested_end}")
                            
                            # Combine cached data with delta data
                            all_data = requested_cached_data + delta_data
                            all_data.sort(key=lambda x: x['date'], reverse=True)
                            logger.info(f"✅ Returning {len(all_data)} gap-up days (cached: {len(requested_cached_data)}, delta: {len(delta_data)})")
                            return _filter(all_data)
                        else:
                            logger.info(f"✅ No missing dates to fetch for requested range")
                            return _filter(requested_cached_data)
                    else:
                        # Requested range is within cached range
                        if requested_cached_data:
                            requested_cached_data.sort(key=lambda x: x['date'], reverse=True)
                            logger.info(f"✅ Returning {len(requested_cached_data)} gap-up days from cache for requested range")
                            return _filter(requested_cached_data)
                        else:
                            logger.info(f"✅ No gap-up days found in requested range (within cache)")
                            return []
                else:
                    # No cache range info, return cached data if any
                    if requested_cached_data:
                        requested_cached_data.sort(key=lambda x: x['date'], reverse=True)
                        logger.info(f"✅ Returning {len(requested_cached_data)} gap-up days from cache for requested range")
                        return _filter(requested_cached_data)
                    else:
                        logger.info(f"🔄 No gap-up days found in requested range, checking for delta")
                    
                    # Only fetch delta if the requested range extends beyond our cached data range
                    cache_range = cache_status.get('data_range', {})
                    cache_start = cache_range.get('start') if cache_range else None
                    cache_end = cache_range.get('end') if cache_range else None
                    
                    if cache_start and cache_end:
                        # Check if requested range extends beyond cached range
                        cache_start_date = dt.strptime(cache_start, "%Y-%m-%d").date()
                        cache_end_date = dt.strptime(cache_end, "%Y-%m-%d").date()
                        requested_start_date = dt.strptime(requested_start, "%Y-%m-%d").date()
                        requested_end_date = dt.strptime(requested_end, "%Y-%m-%d").date()
                        
                        # Check if requested range extends beyond cached range
                        extends_before = requested_start_date < cache_start_date
                        extends_after = requested_end_date > cache_end_date
                        
                        if extends_before or extends_after:
                            # Requested range extends beyond cached range, fetch delta
                            logger.info(f"🔄 Requested range extends beyond cache (before: {extends_before}, after: {extends_after})")
                            
                            # Calculate the actual missing date ranges
                            missing_dates = []
                            if extends_before:
                                # Get missing dates from requested_start to cache_start_date - 1 day
                                missing_before = historical_cache.get_cache_gaps(ticker, requested_start, (cache_start_date - timedelta(days=1)).strftime('%Y-%m-%d'))
                                missing_dates.extend(missing_before)
                                logger.info(f"DEBUG: Found {len(missing_before)} missing dates before cache")
                            
                            if extends_after:
                                # Get missing dates from cache_end_date + 1 day to requested_end
                                missing_after = historical_cache.get_cache_gaps(ticker, (cache_end_date + timedelta(days=1)).strftime('%Y-%m-%d'), requested_end)
                                missing_dates.extend(missing_after)
                                logger.info(f"DEBUG: Found {len(missing_after)} missing dates after cache")
                            
                            logger.info(f"DEBUG: Found {len(missing_dates)} total missing dates for requested range")
                            
                            if missing_dates:
                                # Use optimized batch delta processing instead of individual day fetching
                                delta_data = get_batch_delta_data(ticker, missing_dates)
                                
                                # Store new delta data in cache (even if empty)
                                if delta_data:
                                    historical_cache.store_historical_data(ticker, delta_data, requested_start, requested_end)
                                    logger.info(f"💾 Cached {len(delta_data)} new gap-up days from delta for {ticker}")
                                else:
                                    # Cache empty delta result to avoid re-searching this period
                                    historical_cache.store_historical_data(ticker, [], requested_start, requested_end)
                                    logger.info(f"💾 Cached empty delta result (no gap-ups) for {ticker} in period {requested_start} to {requested_end}")
                                
                                # Return delta data (these are the only gap-up days in the requested range)
                                delta_data.sort(key=lambda x: x['date'], reverse=True)
                                logger.info(f"✅ Returning {len(delta_data)} gap-up days from delta for requested range")
                                return _filter(delta_data)
                            else:
                                logger.info(f"✅ No missing dates to fetch for requested range")
                                return []
                        else:
                            # Requested range is completely within cached range, but no gap-ups found
                            logger.info(f"✅ Requested range is within cache, but no gap-up days found in this period")
                            return []
                    else:
                        # No cache range info, fetch delta for the entire requested range
                        logger.info(f"🔄 No cache range info, fetching delta for entire requested range")
                        missing_dates = historical_cache.get_cache_gaps(ticker, requested_start, requested_end)
                        logger.info(f"DEBUG: Found {len(missing_dates)} missing dates for requested range")

                        if missing_dates:
                            logger.info(f"🔄 Fetching delta data for {ticker}: {len(missing_dates)} missing dates")

                            delta_data = []
                            for missing_date in missing_dates:
                                data_point = fetch_single_day_data(ticker, None, missing_date)
                                gap_percent = data_point.get('gap up % at open') if data_point else None
                                if data_point and gap_percent is not None and gap_percent >= 5:
                                    delta_data.append(data_point)

                            # Store new delta data in cache (even if empty)
                            if delta_data:
                                historical_cache.store_historical_data(ticker, delta_data, requested_start, requested_end)
                                logger.info(f"💾 Cached {len(delta_data)} new gap-up days from delta for {ticker}")
                            else:
                                # Cache empty delta result to avoid re-searching this period
                                historical_cache.store_historical_data(ticker, [], requested_start, requested_end)
                                logger.info(f"💾 Cached empty delta result (no gap-ups) for {ticker} in period {requested_start} to {requested_end}")

                            # Return delta data (these are the only gap-up days in the requested range)
                            delta_data.sort(key=lambda x: x['date'], reverse=True)
                            logger.info(f"✅ Returning {len(delta_data)} gap-up days from delta for requested range")
                            return _filter(delta_data)
                        else:
                            logger.info(f"✅ No missing dates to fetch for requested range")
                            return []
            else:
                logger.info(f"DEBUG: No cached data found for {ticker}, will fetch from Alpaca")

        # If no cache or insufficient cached data, fetch from Alpaca using batch processing
        logger.info(f"🔄 Fetching batch data from Alpaca for {ticker}")
        
        # Add timeout protection for API calls
        try:
            # Use batch processing for much faster data retrieval
            daily_data = get_batch_daily_data(ticker, from_date, to_date)
        except Exception as e:
            logger.error(f"❌ Error fetching batch data for {ticker}: {e}")
            # Return empty list instead of None to avoid breaking the API
            return []
        
        if not daily_data:
            logger.error(
                f"❌ No daily bar data returned for {ticker} from Alpaca "
                f"(both SIP and IEX feeds tried). Check ALPACA_API_KEY / "
                f"ALPACA_API_SECRET and subscription plan.")
            return None
        
        # Process batch data to extract gap-up information (cache at 5% threshold)
        major_gap_up_data = process_batch_data_to_gap_ups(ticker, daily_data, min_gap_percent=5)

        # Sort by date (most recent first)
        major_gap_up_data.sort(key=lambda x: x['date'], reverse=True)

        # Store cache result (even if no gap-ups found) if caching is enabled
        if use_cache:
            if major_gap_up_data:
                historical_cache.store_historical_data(ticker, major_gap_up_data, from_date, to_date)
                logger.info(f"💾 Cached {len(major_gap_up_data)} gap-up days (>=5%) for {ticker}")
            else:
                # Cache empty result to avoid re-searching this period
                historical_cache.store_historical_data(ticker, [], from_date, to_date)
                logger.info(f"💾 Cached empty result (no gap-ups) for {ticker} in period {from_date} to {to_date}")

        duration = time.time() - start_time
        log_performance('historical_gap_up_data', duration, {
            'ticker': ticker,
            'days': days,
            'use_cache': use_cache,
            'total_days': len(daily_data),
            'gap_up_days': len(major_gap_up_data)
        })

        logger.info(f"✅ Retrieved {len(daily_data)} days of historical data for {ticker}")
        logger.info(f"📈 Found {len(major_gap_up_data)} gap-up days (>=5%) for {ticker}, returning filtered to >={min_gap_percent}%")

        # Apply user's min_gap_percent filter before returning
        return _filter(major_gap_up_data)[:days]
        
    except Exception as e:
        duration = time.time() - start_time
        log_error(e, {
            'ticker': ticker,
            'days': days,
            'use_cache': use_cache,
            'function': 'get_historical_gap_up_data'
        })
        logger.error(f"❌ Error getting historical gap-up data for {ticker}: {e}")
        return None

def fetch_multiple_stocks_parallel(tickers, days=365, use_cache=True):
    """
    Fetch historical gap-up data for multiple stocks in parallel.
    This significantly improves performance when processing multiple tickers.
    """
    try:
        logger.info(f"🚀 Starting parallel processing for {len(tickers)} tickers")
        
        # Use ThreadPoolExecutor for I/O-bound operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(get_historical_gap_up_data, ticker, days, use_cache): ticker 
                for ticker in tickers
            }
            
            # Collect results as they complete
            results = {}
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    results[ticker] = data
                    logger.info(f"✅ Completed processing for {ticker}")
                except Exception as e:
                    logger.error(f"❌ Error processing {ticker}: {e}")
                    results[ticker] = None
        
        logger.info(f"🎉 Parallel processing completed for {len(tickers)} tickers")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error in parallel processing: {e}")
        return {}

def get_batch_delta_data(ticker, missing_dates, min_gap_percent=5):
    """
    Fetch delta data for missing dates using batch processing.
    This is much faster than fetching day by day.
    """
    try:
        if not missing_dates:
            return []
        
        logger.info(f"🔄 Fetching batch delta data for {ticker}: {len(missing_dates)} missing dates")
        
        # Sort dates for efficient processing
        missing_dates.sort()
        start_date = missing_dates[0]
        end_date = missing_dates[-1]
        
        # Get batch data for the entire missing range
        daily_data = get_batch_daily_data(ticker, start_date, end_date)

        if not daily_data:
            return []

        # Process only the missing dates from the batch data
        delta_data = []
        daily_data_dict = {}

        # Create lookup dictionary for quick access
        for agg in daily_data:
            date_str = dt.utcfromtimestamp(agg.timestamp / 1000).strftime('%Y-%m-%d')
            daily_data_dict[date_str] = agg
        
        # Process only the missing dates
        for missing_date in missing_dates:
            if missing_date in daily_data_dict:
                agg = daily_data_dict[missing_date]
                
                # Get previous trading day close for gap calculation
                previous_day_close = None
                
                # Find the actual previous trading day by looking back through the data
                current_date = dt.strptime(missing_date, '%Y-%m-%d').date()
                for days_back in range(1, 10):  # Look back up to 10 days to find previous trading day
                    prev_date = current_date - timedelta(days=days_back)
                    prev_date_str = prev_date.strftime('%Y-%m-%d')
                    
                    if prev_date_str in daily_data_dict:
                        previous_day_close = daily_data_dict[prev_date_str].close
                        logger.debug(f"📊 Found previous trading day for {missing_date}: {prev_date_str} (close: {previous_day_close})")
                        break
                
                # Fallback: if not found in batch data, fetch individually via Alpaca.
                # Walk back up to 10 days to correctly skip weekends/holidays.
                if previous_day_close is None:
                    for fb in range(1, 10):
                        prev_date_str = (current_date - timedelta(days=fb)).strftime('%Y-%m-%d')
                        try:
                            prev_bars = _alpaca_bars_raw(
                                ticker,
                                f'{prev_date_str}T00:00:00Z',
                                f'{prev_date_str}T23:59:59Z',
                                timeframe='1Day'
                            )
                            if prev_bars:
                                previous_day_close = float(prev_bars[-1].get('c') or 0) or None
                                if previous_day_close:
                                    logger.debug(f"📊 Fetched previous day individually for {missing_date}: {prev_date_str} (close: {previous_day_close})")
                                    break
                        except Exception as e:
                            logger.warning(f"Could not fetch previous day data for {ticker} on {prev_date_str}: {e}")
                
                # Calculate gap percentage
                gap_percent = None
                if previous_day_close and agg.open:
                    gap_percent = round(((agg.open - previous_day_close) / previous_day_close) * 100, 2)
                
                # Only process if the gap meets the minimum threshold
                if gap_percent and gap_percent >= min_gap_percent:
                    # Get premarket data for gap-up days only
                    premarket_high, premarket_high_time, _, _, premarket_bar_open = get_premarket_high_low_data(ticker, None, missing_date)
                    premarket_volume = get_premarket_volume(None, ticker, missing_date)

                    # Get daily high/low data for gap-up days
                    daily_high, daily_high_time, _, _ = get_daily_high_low_data(ticker, None, missing_date)

                    # Get VWAP crosses for gap-up days
                    vwap_crosses = count_vwap_crosses(None, ticker, missing_date)

                    # premarket open from first premarket bar; afterhours close from 16:00–20:00 ET bars
                    premarket_open = premarket_bar_open
                    afterhours_close = None
                    try:
                        ah_start = _et_to_iso(missing_date, '16:00')
                        ah_end   = _et_to_iso(missing_date, '20:00')
                        ah_bars  = _alpaca_bars_raw(ticker, ah_start, ah_end, timeframe='1Min')
                        if ah_bars:
                            afterhours_close = float(ah_bars[-1].get('c') or 0) or None
                    except Exception as e:
                        logger.debug(f"afterhours fetch error for {ticker} on {missing_date}: {e}")
                    
                    # Calculate percentages
                    percent_gap_high = None
                    closing_percent = None
                    if previous_day_close:
                        percent_gap_high = round(((agg.high - previous_day_close) / previous_day_close) * 100, 2)
                        closing_percent = round(((agg.close - previous_day_close) / previous_day_close) * 100, 2)
                    
                    # Determine Runner/Fader
                    runner_fader = "Runner" if agg.close > agg.open else (
                        "Fader" if agg.close < agg.open else "Neutral")
                    
                    data_point = {
                        'date': missing_date,
                        'pd close': round(previous_day_close, 2) if previous_day_close else None,
                        'premarket open': round(premarket_open, 2) if premarket_open else None,
                        'premarket high': round(premarket_high, 2) if premarket_high else None,
                        'premarket high time': premarket_high_time,
                        'premarket volume': premarket_volume,
                        'open': round(agg.open, 2),
                        'gap up % at open': gap_percent,
                        'day high': round(daily_high if daily_high else agg.high, 2),
                        'day high time': daily_high_time,
                        'day high %': percent_gap_high,
                        'close price': round(agg.close, 2),
                        'closing percent': closing_percent,
                        'afterhours close': round(afterhours_close, 2) if afterhours_close else None,
                        'total volume': agg.volume,
                        'VWAP Crosses': vwap_crosses,
                        'Runner/Fader': runner_fader,
                        'high': round(agg.high, 2),
                        'low': round(agg.low, 2),
                        'volume_millions': round(agg.volume / 1000000, 2),
                        'dollar_volume_millions': round((agg.volume * agg.high) / 1000000, 2)
                    }
                    
                    delta_data.append(data_point)
        
        logger.info(f"✅ Batch delta processing completed for {ticker}: {len(delta_data)} gap-up days found")
        return delta_data
        
    except Exception as e:
        logger.error(f"❌ Error in batch delta processing for {ticker}: {e}")
        return []

def cache_gap_up_day_for_tickers(date_str, gap_up_stocks, delay_seconds=0.5):
    """
    Populate historical_data_cache for each ticker in the nightly gap-up snapshot.
    Called from update_real_time_gap_ups() in a background thread after the snapshot is saved.
    """
    try:
        cached_count = 0
        skipped_count = 0

        for stock in gap_up_stocks:
            ticker = stock.get('ticker') or stock.get('symbol')
            if not ticker:
                continue

            # Skip if this date is already in the historical cache for this ticker
            existing = historical_cache.get_cached_data(ticker, date_str, date_str)
            if existing:
                skipped_count += 1
                continue

            try:
                data_point = fetch_single_day_data(ticker, None, date_str)
                if data_point:
                    historical_cache.store_historical_data(ticker, [data_point], date_str, date_str)
                    cached_count += 1
                    logger.info(f"💾 Snapshot→cache: stored {date_str} data for {ticker}")
            except Exception as e:
                logger.error(f"❌ Snapshot→cache error for {ticker} on {date_str}: {e}")

            if delay_seconds > 0:
                time.sleep(delay_seconds)

        logger.info(
            f"✅ Nightly historical cache update for {date_str}: "
            f"{cached_count} stored, {skipped_count} already cached"
        )
    except Exception as e:
        logger.error(f"❌ cache_gap_up_day_for_tickers failed for {date_str}: {e}")


def get_cache_stats():
    """Get cache statistics"""
    return historical_cache.get_cache_stats()

def clear_cache(ticker=None):
    """Clear cache for a specific ticker or all tickers"""
    return historical_cache.clear_cache(ticker)

if __name__ == "__main__":
    # Test the functions
    print("🧪 Testing historical data functions with caching...")
    
    # Test cache stats
    stats = get_cache_stats()
    print(f"📊 Cache stats: {stats}")
    
    # Test historical data retrieval
    result = get_historical_gap_up_data("AAPL", 30)
    if result:
        print(f"✅ Successfully retrieved data for AAPL")
        print(f"📊 Data points: {len(result)}")
        
        # Test cache stats after retrieval
        stats_after = get_cache_stats()
        print(f"📊 Cache stats after retrieval: {stats_after}")
    else:
        print("❌ Failed to retrieve data")
