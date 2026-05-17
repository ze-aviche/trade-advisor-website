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
    """
    try:
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=2,
            timespan='minute',
            from_=date,
            to=date,
            limit=50000
        )
        aggs_list = list(aggs_data)
    except Exception as e:
        print(f"Error fetching 2-minute bar data for {ticker} on {date}: {e}")
        return None

    if not aggs_list:
        return 0

    cross_count = 0
    previous_close = aggs_list[0].close
    previous_vwap = aggs_list[0].vwap

    for i in range(1, len(aggs_list)):
        current_bar = aggs_list[i]
        current_close = current_bar.close
        current_vwap = current_bar.vwap

        if previous_close is not None and current_close is not None and previous_vwap is not None and current_vwap is not None:
            if (previous_close < previous_vwap and current_close > current_vwap) or \
                    (previous_close > previous_vwap and current_close < previous_vwap):
                cross_count += 1

        previous_close = current_close
        previous_vwap = current_vwap

    return cross_count

def get_premarket_high_low_data(ticker, polygon_client, date_str):
    """
    Fetches premarket high/low data for a given ticker and date (4:00 AM to 9:30 AM EST).
    """
    try:
        est_timezone = pytz.timezone('America/New_York')
        start_datetime_est = est_timezone.localize(dt.strptime(f"{date_str} 04:00", '%Y-%m-%d %H:%M'))
        end_datetime_est = est_timezone.localize(dt.strptime(f"{date_str} 9:30", '%Y-%m-%d %H:%M'))
        
        start_timestamp_utc_ms = int(start_datetime_est.timestamp() * 1000)
        end_timestamp_utc_ms = int(end_datetime_est.timestamp() * 1000)
        
        logger.debug(f"🔍 Fetching premarket data for {ticker} on {date_str} (4:00-9:30 AM EST)")
        
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='minute',
            from_=start_timestamp_utc_ms,
            to=end_timestamp_utc_ms,
            limit=50000
        )
        aggs_list = list(aggs_data)
        
        if not aggs_list:
            logger.debug(f"⚠️ No premarket data found for {ticker} on {date_str}")
            return None, None, None, None, None

        logger.debug(f"📊 Found {len(aggs_list)} premarket bars for {ticker} on {date_str}")

        # aggs_list is already in chronological order; first bar's open = premarket open price
        first_bar_open = aggs_list[0].open

        max_high = -1
        high_timestamp = None
        min_low = float('inf')
        low_timestamp = None

        for bar in aggs_list:
            if bar.high > max_high:
                max_high = bar.high
                high_timestamp = bar.timestamp
            if bar.low < min_low:
                min_low = bar.low
                low_timestamp = bar.timestamp

        high_timestamp_est = None
        if high_timestamp:
            high_datetime_utc = dt.fromtimestamp(high_timestamp / 1000, tz=pytz.utc)
            high_datetime_est = high_datetime_utc.astimezone(est_timezone)
            high_timestamp_est = high_datetime_est.strftime('%H:%M')

        low_timestamp_est = None
        if low_timestamp:
            low_datetime_utc = dt.fromtimestamp(low_timestamp / 1000, tz=pytz.utc)
            low_datetime_est = low_datetime_utc.astimezone(est_timezone)
            low_timestamp_est = low_datetime_est.strftime('%H:%M')

        logger.debug(f"✅ Premarket data for {ticker} on {date_str}: High={max_high}@{high_timestamp_est}, Low={min_low}@{low_timestamp_est}, FirstOpen={first_bar_open}")
        return max_high, high_timestamp_est, min_low, low_timestamp_est, first_bar_open

    except Exception as e:
        logger.error(f"❌ Error fetching premarket data for {ticker} on {date_str}: {e}")
        return None, None, None, None, None

def get_daily_high_low_data(ticker, polygon_client, date_str):
    """
    Fetches daily high/low data for a given ticker and date (9:30 AM to 4:00 PM EST).
    """
    try:
        est_timezone = pytz.timezone('America/New_York')
        start_datetime_est = est_timezone.localize(dt.strptime(f"{date_str} 09:30", '%Y-%m-%d %H:%M'))
        end_datetime_est = est_timezone.localize(dt.strptime(f"{date_str} 16:00", '%Y-%m-%d %H:%M'))
        
        start_timestamp_utc_ms = int(start_datetime_est.timestamp() * 1000)
        end_timestamp_utc_ms = int(end_datetime_est.timestamp() * 1000)
        
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='minute',
            from_=start_timestamp_utc_ms,
            to=end_timestamp_utc_ms,
            limit=50000
        )
        aggs_list = list(aggs_data)
        
        if not aggs_list:
            return None, None, None, None
        
        max_high = -1
        high_timestamp = None
        min_low = float('inf')
        low_timestamp = None
        
        for bar in aggs_list:
            if bar.high > max_high:
                max_high = bar.high
                high_timestamp = bar.timestamp
            if bar.low < min_low:
                min_low = bar.low
                low_timestamp = bar.timestamp
        
        high_timestamp_est = None
        if high_timestamp:
            high_datetime_utc = dt.fromtimestamp(high_timestamp / 1000, tz=pytz.utc)
            high_datetime_est = high_datetime_utc.astimezone(est_timezone)
            high_timestamp_est = high_datetime_est.strftime('%H:%M')
        
        low_timestamp_est = None
        if low_timestamp:
            low_datetime_utc = dt.fromtimestamp(low_timestamp / 1000, tz=pytz.utc)
            low_datetime_est = low_datetime_utc.astimezone(est_timezone)
            low_timestamp_est = low_datetime_est.strftime('%H:%M')
        
        return max_high, high_timestamp_est, min_low, low_timestamp_est
        
    except Exception as e:
        print(f"Error fetching daily data for {ticker} on {date_str}: {e}")
        return None, None, None, None

def get_premarket_volume(polygon_client, ticker, date_str):
    """
    Fetches premarket volume for a given ticker and date (4:00 AM to 9:30 AM EST).
    Returns volume in millions.
    """
    try:
        est_timezone = pytz.timezone('America/New_York')
        start_datetime_est = est_timezone.localize(dt.strptime(f"{date_str} 04:00", '%Y-%m-%d %H:%M'))
        end_datetime_est = est_timezone.localize(dt.strptime(f"{date_str} 09:30", '%Y-%m-%d %H:%M'))
        
        start_timestamp_utc_ms = int(start_datetime_est.timestamp() * 1000)
        end_timestamp_utc_ms = int(end_datetime_est.timestamp() * 1000)
        
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='minute',
            from_=start_timestamp_utc_ms,
            to=end_timestamp_utc_ms,
            limit=50000
        )
        aggs_list = list(aggs_data)
        
        if not aggs_list:
            logger.debug(f"⚠️ No premarket volume data found for {ticker} on {date_str}")
            return 0.0
        
        premarket_total_volume_millions = sum(bar.volume for bar in aggs_list) / 1_000_000
        logger.debug(f"📊 Premarket volume (millions) for {ticker} on {date_str}: {premarket_total_volume_millions}")
        return round(premarket_total_volume_millions, 2)
        
    except Exception as e:
        logger.error(f"❌ Error fetching premarket volume for {ticker} on {date_str}: {e}")
        return 0.0

def fetch_single_day_data(ticker, polygon_client, date_str):
    """
    Fetch comprehensive data for a single day from Polygon API.
    Returns a single data point dictionary.
    """
    try:
        # Get daily aggregates for this specific date
        aggs_data = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=date_str,
            to=date_str,
            adjusted="true"
        )
        
        if not aggs_data:
            return None
        
        # Get the single day data
        agg = aggs_data[0] if aggs_data else None
        if not agg:
            return None
        
        # Get previous day data for gap calculation
        prev_date = (dt.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        prev_aggs = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=prev_date,
            to=prev_date,
            adjusted="true"
        )
        
        previous_day_close = None
        if prev_aggs and len(prev_aggs) > 0:
            previous_day_close = prev_aggs[0].close
        
        # Calculate gap percentage
        gap_percent = None
        if previous_day_close and agg.open:
            gap_percent = round(((agg.open - previous_day_close) / previous_day_close) * 100, 2)
        
        # Get premarket data
        premarket_high, premarket_high_time, _, _, premarket_bar_open = get_premarket_high_low_data(ticker, polygon_client, date_str)
        premarket_volume = get_premarket_volume(polygon_client, ticker, date_str)

        # Get daily high/low data
        daily_high, daily_high_time, _, _ = get_daily_high_low_data(ticker, polygon_client, date_str)

        # Calculate percentages
        percent_gap_high = None
        closing_percent = None
        if previous_day_close:
            if daily_high:
                percent_gap_high = round(((daily_high - previous_day_close) / previous_day_close) * 100, 2)
            closing_percent = round(((agg.close - previous_day_close) / previous_day_close) * 100, 2)

        # Get daily summary for premarket open and afterhours close
        try:
            daily_summary = polygon_client.get_daily_open_close_agg(
                ticker=ticker,
                date=date_str,
                adjusted="true",
            )
            premarket_open = daily_summary.pre_market if daily_summary.pre_market else premarket_bar_open
            afterhours_close = daily_summary.after_hours if daily_summary.after_hours else None
        except Exception as e:
            print(f"Error fetching daily summary for {ticker} on {date_str}: {e}")
            premarket_open = premarket_bar_open
            afterhours_close = None
        
        # Determine Runner/Fader
        runner_fader = "Runner" if agg.close > agg.open else (
            "Fader" if agg.close < agg.open else "Neutral")
        
        # VWAP crosses removed for performance optimization
        vwap_crosses = None
        
        data_point = {
            'date': date_str,
            'pd close': round(previous_day_close, 2) if previous_day_close else None,
            'premarket open': round(premarket_open, 2) if premarket_open else None,
            'premarket high': round(premarket_high, 2) if premarket_high else None,
            'premarket high time': premarket_high_time,
            'premarket volume': premarket_volume,
            'open': round(agg.open, 2),
            'gap up % at open': gap_percent,
            'day high': round(daily_high, 2) if daily_high else round(agg.high, 2),
            'day high time': daily_high_time,
            'day high %': percent_gap_high,
            'close price': round(agg.close, 2),
            'closing percent': closing_percent,
            'afterhours close': round(afterhours_close, 2) if afterhours_close else None,
            'total volume': agg.volume,
            'VWAP Crosses': None,  # Removed for performance
            'Runner/Fader': runner_fader,
            'high': round(agg.high, 2),
            'low': round(agg.low, 2),
            'volume_millions': round(agg.volume / 1000000, 2),
            'dollar_volume_millions': round((agg.volume * agg.high) / 1000000, 2)
        }
        
        return data_point
        
    except Exception as e:
        logger.error(f"Error fetching single day data for {ticker} on {date_str}: {e}")
        return None

def get_batch_daily_data(ticker, start_date, end_date):
    """
    Fetch all daily data for a ticker in a single batch API call.
    This is much faster than fetching day by day.
    """
    start_time = time.time()
    try:
        polygon_client = get_polygon_client()
        
        # Single batch call for all daily data
        aggs_data = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=start_date,
            to=end_date,
            adjusted="true"
        )
        
        if not aggs_data:
            return []
        
        # Convert to list and sort by date
        daily_data = list(aggs_data)
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
            # Fix Polygon API date offset by adding 1 day to get correct trading date
            date_str = (dt.fromtimestamp(agg.timestamp / 1000) + timedelta(days=1)).strftime('%Y-%m-%d')
            daily_data_dict[date_str] = agg
        
        for i, agg in enumerate(daily_data):
            # Fix Polygon API date offset by adding 1 day to get correct trading date
            date_str = (dt.fromtimestamp(agg.timestamp / 1000) + timedelta(days=1)).strftime('%Y-%m-%d')
            
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
                polygon_client = get_polygon_client()
                premarket_high, premarket_high_time, _, _, premarket_bar_open = get_premarket_high_low_data(ticker, polygon_client, date_str)
                premarket_volume = get_premarket_volume(polygon_client, ticker, date_str)

                # Get daily high/low data for gap-up days
                daily_high, daily_high_time, _, _ = get_daily_high_low_data(ticker, polygon_client, date_str)

                # Get VWAP crosses for gap-up days
                vwap_crosses = count_vwap_crosses(polygon_client, ticker, date_str)

                # Get daily summary for premarket open and afterhours close
                try:
                    logger.debug(f"🔍 Fetching daily summary for {ticker} on {date_str}")
                    daily_summary = polygon_client.get_daily_open_close_agg(
                        ticker=ticker,
                        date=date_str,
                        adjusted="true",
                    )
                    premarket_open = daily_summary.pre_market if daily_summary.pre_market else premarket_bar_open
                    afterhours_close = daily_summary.after_hours if daily_summary.after_hours else None
                    logger.debug(f"📊 Daily summary for {ticker} on {date_str}: Pre-market={premarket_open}, After-hours={afterhours_close}")
                except Exception as e:
                    logger.warning(f"❌ Error fetching daily summary for {ticker} on {date_str}: {e}")
                    premarket_open = premarket_bar_open
                    afterhours_close = None
                
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
                            polygon_client = get_polygon_client()

                            delta_data = []
                            for missing_date in missing_dates:
                                data_point = fetch_single_day_data(ticker, polygon_client, missing_date)
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
                logger.info(f"DEBUG: No cached data found for {ticker}, will fetch from Polygon")
        
        # If no cache or insufficient cached data, fetch from Polygon using batch processing
        logger.info(f"🔄 Fetching fresh batch data from Polygon for {ticker}")
        
        # Add timeout protection for API calls
        try:
            # Use batch processing for much faster data retrieval
            daily_data = get_batch_daily_data(ticker, from_date, to_date)
        except Exception as e:
            logger.error(f"❌ Error fetching batch data for {ticker}: {e}")
            # Return empty list instead of None to avoid breaking the API
            return []
        
        if not daily_data:
            logger.error(f"❌ No historical data found for {ticker}")
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
        polygon_client = get_polygon_client()
        daily_data = get_batch_daily_data(ticker, start_date, end_date)
        
        if not daily_data:
            return []
        
        # Process only the missing dates from the batch data
        delta_data = []
        daily_data_dict = {}
        
        # Create lookup dictionary for quick access
        for agg in daily_data:
            date_str = (dt.fromtimestamp(agg.timestamp / 1000) + timedelta(days=1)).strftime('%Y-%m-%d')
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
                
                # Fallback: if not found in batch data, fetch individually.
                # Walk back up to 10 days to correctly skip weekends/holidays.
                if previous_day_close is None:
                    for fb in range(1, 10):
                        prev_date_str = (current_date - timedelta(days=fb)).strftime('%Y-%m-%d')
                        try:
                            prev_aggs = polygon_client.get_aggs(
                                ticker=ticker,
                                multiplier=1,
                                timespan="day",
                                from_=prev_date_str,
                                to=prev_date_str,
                                adjusted="true"
                            )
                            if prev_aggs and len(prev_aggs) > 0:
                                previous_day_close = prev_aggs[0].close
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
                    premarket_high, premarket_high_time, _, _, premarket_bar_open = get_premarket_high_low_data(ticker, polygon_client, missing_date)
                    premarket_volume = get_premarket_volume(polygon_client, ticker, missing_date)

                    # Get daily high/low data for gap-up days
                    daily_high, daily_high_time, _, _ = get_daily_high_low_data(ticker, polygon_client, missing_date)

                    # Get VWAP crosses for gap-up days
                    vwap_crosses = count_vwap_crosses(polygon_client, ticker, missing_date)

                    # Get daily summary for premarket open and afterhours close
                    try:
                        logger.debug(f"🔍 Fetching daily summary for {ticker} on {missing_date}")
                        daily_summary = polygon_client.get_daily_open_close_agg(
                            ticker=ticker,
                            date=missing_date,
                            adjusted="true",
                        )
                        premarket_open = daily_summary.pre_market if daily_summary.pre_market else premarket_bar_open
                        afterhours_close = daily_summary.after_hours if daily_summary.after_hours else None
                        logger.debug(f"📊 Daily summary for {ticker} on {missing_date}: Pre-market={premarket_open}, After-hours={afterhours_close}")
                    except Exception as e:
                        logger.warning(f"❌ Error fetching daily summary for {ticker} on {missing_date}: {e}")
                        premarket_open = premarket_bar_open
                        afterhours_close = None
                    
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
        polygon_client = get_polygon_client()
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
                data_point = fetch_single_day_data(ticker, polygon_client, date_str)
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
