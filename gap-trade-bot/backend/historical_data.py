#!/usr/bin/env python3
"""
Historical Data Analysis Module for Gap-Trade-Bot
Provides comprehensive historical data analysis for stocks with intelligent caching
"""
import os
import datetime
from datetime import datetime as dt, timedelta, time
import pytz
from polygon import RESTClient
from dotenv import load_dotenv
from historical_cache import historical_cache
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_polygon_client():
    """Get Polygon API client with API key"""
    api_key = os.environ.get('POLYGON_API_KEY')
    if not api_key:
        api_key = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
        print("Using default Polygon API key")
    
    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable is required")
    
    return RESTClient(api_key)

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
        print(f"Error fetching premarket data for {ticker} on {date_str}: {e}")
        return None, None, None, None

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
            return 0.0
        
        premarket_total_volume = sum(bar.volume for bar in aggs_list)
        return premarket_total_volume
        
    except Exception as e:
        print(f"Error fetching premarket volume for {ticker} on {date_str}: {e}")
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
        premarket_high, premarket_high_time, _, _ = get_premarket_high_low_data(ticker, polygon_client, date_str)
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
            premarket_open = daily_summary.pre_market if daily_summary.pre_market else None
            afterhours_close = daily_summary.after_hours if daily_summary.after_hours else None
        except Exception as e:
            print(f"Error fetching daily summary for {ticker} on {date_str}: {e}")
            premarket_open = None
            afterhours_close = None
        
        # Determine Runner/Fader
        runner_fader = "Runner" if agg.close > agg.open else (
            "Fader" if agg.close < agg.open else "Neutral")
        
        # Count VWAP crosses
        vwap_crosses = count_vwap_crosses(polygon_client, ticker, date_str)
        
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
            'VWAP Crosses': vwap_crosses,
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

def get_historical_gap_up_data(ticker, days=30, use_cache=True):
    """
    Get comprehensive historical gap-up data for a stock using intelligent caching.
    Returns detailed gap-up analysis for the specified number of days.
    Only caches days when stocks actually gap up by 25% or more (gap_percent >= 25).
    """
    try:
        # Calculate date range based on requested days (not always 3 years)
        end_date = dt.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Format dates for API and cache
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")
        
        logger.info(f"📊 Fetching historical gap-up data for {ticker} from {from_date} to {to_date} ({days} days)")
        
        cached_data = []  # Initialize cached_data in outer scope
        
        if use_cache:
            # Check cache status
            cache_status = historical_cache.get_cache_status(ticker)
            logger.info(f"Cache status for {ticker}: {cache_status}")
            
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
                            logger.info(f"🔄 Fetching delta data for {ticker}: {len(missing_dates)} missing dates")
                            polygon_client = get_polygon_client()
                            
                            delta_data = []
                            for missing_date in missing_dates:
                                data_point = fetch_single_day_data(ticker, polygon_client, missing_date)
                                gap_percent = data_point.get('gap up % at open') if data_point else None
                                if data_point and gap_percent is not None and gap_percent >= 25:  # Only cache major gap-up days (25%+)
                                    delta_data.append(data_point)
                            
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
                            return all_data
                        else:
                            logger.info(f"✅ No missing dates to fetch for requested range")
                            return requested_cached_data
                    else:
                        # Requested range is within cached range
                        if requested_cached_data:
                            requested_cached_data.sort(key=lambda x: x['date'], reverse=True)
                            logger.info(f"✅ Returning {len(requested_cached_data)} gap-up days from cache for requested range")
                            return requested_cached_data
                        else:
                            logger.info(f"✅ No gap-up days found in requested range (within cache)")
                            return []
                else:
                    # No cache range info, return cached data if any
                    if requested_cached_data:
                        requested_cached_data.sort(key=lambda x: x['date'], reverse=True)
                        logger.info(f"✅ Returning {len(requested_cached_data)} gap-up days from cache for requested range")
                        return requested_cached_data
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
                        else:
                            # Requested range is completely within cached range, but no gap-ups found
                            logger.info(f"✅ Requested range is within cache, but no gap-up days found in this period")
                            return []
                            logger.info(f"DEBUG: Found {len(missing_dates)} missing dates for requested range")
                            
                            if missing_dates:
                                logger.info(f"🔄 Fetching delta data for {ticker}: {len(missing_dates)} missing dates")
                                polygon_client = get_polygon_client()
                                
                                delta_data = []
                                for missing_date in missing_dates:
                                    data_point = fetch_single_day_data(ticker, polygon_client, missing_date)
                                    gap_percent = data_point.get('gap up % at open') if data_point else None
                                    if data_point and gap_percent is not None and gap_percent >= 25:  # Only cache major gap-up days (25%+)
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
                                return delta_data
                            else:
                                logger.info(f"✅ No missing dates to fetch for requested range")
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
                                if data_point and gap_percent is not None and gap_percent >= 25:  # Only cache major gap-up days (25%+)
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
                            return delta_data
                        else:
                            logger.info(f"✅ No missing dates to fetch for requested range")
                            return []
            else:
                logger.info(f"DEBUG: No cached data found for {ticker}, will fetch from Polygon")
        
        # If no cache or insufficient cached data, fetch from Polygon
        logger.info(f"🔄 Fetching fresh data from Polygon for {ticker}")
        polygon_client = get_polygon_client()
        
        # Get daily aggregates with adjusted prices
        aggs = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=from_date,
            to=to_date,
            adjusted="true"
        )
        
        if not aggs:
            logger.error(f"❌ No historical data found for {ticker}")
            return None
        
        # Convert to list of dictionaries with comprehensive analysis
        historical_data = []
        major_gap_up_data = []  # Separate list for major gap-up days only (25%+)
        
        for i, agg in enumerate(aggs):
            # Calculate gap percentage if we have previous day data
            gap_percent = None
            previous_day_close = None
            if i > 0:
                previous_day_close = aggs[i-1].close
                if previous_day_close and agg.open:
                    gap_percent = round(((agg.open - previous_day_close) / previous_day_close) * 100, 2)
            
            # Get date string
            date_str = dt.fromtimestamp(agg.timestamp / 1000).strftime('%Y-%m-%d')
            
            # Get premarket data
            premarket_high, premarket_high_time, _, _ = get_premarket_high_low_data(ticker, polygon_client, date_str)
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
                premarket_open = daily_summary.pre_market if daily_summary.pre_market else None
                afterhours_close = daily_summary.after_hours if daily_summary.after_hours else None
            except Exception as e:
                print(f"Error fetching daily summary for {ticker} on {date_str}: {e}")
                premarket_open = None
                afterhours_close = None
            
            # Determine Runner/Fader
            runner_fader = "Runner" if agg.close > agg.open else (
                "Fader" if agg.close < agg.open else "Neutral")
            
            # Count VWAP crosses
            vwap_crosses = count_vwap_crosses(polygon_client, ticker, date_str)
            
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
                'VWAP Crosses': vwap_crosses,
                'Runner/Fader': runner_fader,
                'high': round(agg.high, 2),
                'low': round(agg.low, 2),
                'volume_millions': round(agg.volume / 1000000, 2),
                'dollar_volume_millions': round((agg.volume * agg.high) / 1000000, 2)
            }
            historical_data.append(data_point)
            
            # Only add to major_gap_up_data if it's a major gap-up day (25%+)
            if gap_percent and gap_percent >= 25:
                major_gap_up_data.append(data_point)
        
        # Sort by date (most recent first)
        historical_data.sort(key=lambda x: x['date'], reverse=True)
        major_gap_up_data.sort(key=lambda x: x['date'], reverse=True)
        
        # Store cache result (even if no gap-ups found) if caching is enabled
        if use_cache:
            if major_gap_up_data:
                historical_cache.store_historical_data(ticker, major_gap_up_data, from_date, to_date)
                logger.info(f"💾 Cached {len(major_gap_up_data)} major gap-up days (25%+) for {ticker}")
            else:
                # Cache empty result to avoid re-searching this period
                historical_cache.store_historical_data(ticker, [], from_date, to_date)
                logger.info(f"💾 Cached empty result (no gap-ups) for {ticker} in period {from_date} to {to_date}")
        
        logger.info(f"✅ Retrieved {len(historical_data)} days of historical data for {ticker}")
        logger.info(f"📈 Found {len(major_gap_up_data)} major gap-up days (25%+) for {ticker}")
        
        # Return only gap-up data (never return all historical data)
        return major_gap_up_data[:days]  # Return gap-up data only
        
    except Exception as e:
        logger.error(f"❌ Error getting historical gap-up data for {ticker}: {e}")
        return None

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
