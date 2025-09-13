#!/usr/bin/env python3
"""
TimescaleDB Historical Data Analysis Module for Gap-Trade-Bot
Provides comprehensive historical data analysis for stocks using TimescaleDB as data source
"""
import os
import time
import datetime
from datetime import datetime as dt, timedelta
import pytz
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
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

def get_timescaledb_connection():
    """Get TimescaleDB connection with proper configuration"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("TIMESCALEDB_HOST", "localhost"),
            port=int(os.getenv("TIMESCALEDB_PORT", "5432")),
            database=os.getenv("TIMESCALEDB_NAME", "marketdata"),
            user=os.getenv("TIMESCALEDB_USER", "ts_user"),
            password=os.getenv("TIMESCALEDB_PASSWORD", "ts_pass")
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to TimescaleDB: {e}")
        return None

def extract_time_from_timestamp(timestamp):
    """
    Extract time (HH:MM) from TimescaleDB timestamp.
    Timestamps are in Central Time format: '2023-05-02 17:52:00.000 -0500'
    """
    if not timestamp:
        return None
    
    try:
        # Handle different timestamp formats
        if hasattr(timestamp, 'strftime'):
            # Already a datetime object
            return timestamp.strftime('%H:%M')
        else:
            # String timestamp like '2023-05-02 17:52:00.000 -0500'
            timestamp_str = str(timestamp)
            # Extract time part (17:52:00) and take only HH:MM
            time_part = timestamp_str.split(' ')[1]  # Get '17:52:00.000'
            return time_part.split(':')[0] + ':' + time_part.split(':')[1]  # Get '17:52'
    except Exception as e:
        logger.warning(f"Error extracting time from timestamp {timestamp}: {e}")
        return None

def try_premarket_time_ranges(conn, ticker, date_obj):
    """
    Try multiple premarket time ranges to handle data gaps.
    Returns (max_high, high_timestamp, min_low, low_timestamp, range_used) or None if no data found.
    """
    # Try multiple time ranges to handle data gaps
    time_ranges = [
        (f"{date_obj} 03:00:00-05:00", f"{date_obj} 08:30:00-05:00", "3:00-8:30 AM CST"),  # Full premarket
        (f"{date_obj} 04:00:00-05:00", f"{date_obj} 08:30:00-05:00", "4:00-8:30 AM CST"),  # Skip early hours
        (f"{date_obj} 05:00:00-05:00", f"{date_obj} 08:30:00-05:00", "5:00-8:30 AM CST"),  # Skip more early hours
        (f"{date_obj} 06:00:00-05:00", f"{date_obj} 08:30:00-05:00", "6:00-8:30 AM CST"),  # Late premarket only
    ]
    
    query = """
    SELECT 
        max(high) as max_high,
        min(low) as min_low,
        ts as timestamp
    FROM ohlcv_1m 
    WHERE ticker = %s 
    AND day = %s
    AND ts >= %s::timestamp 
    AND ts <= %s::timestamp
    GROUP BY ts
    ORDER BY ts
    """
    
    for start_ts, end_ts, range_desc in time_ranges:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (ticker, date_obj, start_ts, end_ts))
                results = cursor.fetchall()
            
            if results:
                # Find max high and min low with their timestamps
                max_high = -1
                high_timestamp = None
                min_low = float('inf')
                low_timestamp = None
                data_points = len(results)
                
                for row in results:
                    if row['max_high'] and row['max_high'] > max_high:
                        max_high = row['max_high']
                        high_timestamp = row['timestamp']
                    if row['min_low'] and row['min_low'] < min_low:
                        min_low = row['min_low']
                        low_timestamp = row['timestamp']
                
                # Check if we found valid data
                if max_high != -1 and min_low != float('inf'):
                    logger.debug(f"✅ Found premarket data for {ticker} in range {range_desc} ({data_points} data points)")
                    return max_high, high_timestamp, min_low, low_timestamp, range_desc
                else:
                    logger.debug(f"⚠️ Found {data_points} data points in {range_desc} but no valid OHLC values")
            else:
                logger.debug(f"⚠️ No data found in range {range_desc}")
                
        except Exception as e:
            logger.warning(f"Error querying range {range_desc}: {e}")
            continue
    
    logger.warning(f"❌ No premarket data found for {ticker} in any time range")
    return None

def count_vwap_crosses_ts(ticker, date):
    """
    Count VWAP crosses for a given ticker and date using TimescaleDB.
    Fetches 2-minute aggregated data and counts VWAP crosses.
    """
    try:
        conn = get_timescaledb_connection()
        if not conn:
            return None
        
        # Convert date to proper format
        date_obj = pd.to_datetime(date).date()
        
        # Query for 2-minute aggregated data with VWAP
        query = """
        SELECT 
            time_bucket('2 minutes', ts) as timestamp,
            first(open, ts) as open,
            max(high) as high,
            min(low) as low,
            last(close, ts) as close,
            sum(volume) as volume,
            avg(vwap) as vwap
        FROM ohlcv_1m 
        WHERE ticker = %s 
        AND day = %s
        AND ts >= %s::timestamp 
        AND ts <= %s::timestamp
        GROUP BY time_bucket('2 minutes', ts)
        ORDER BY timestamp
        """
        
        # Create session bounds for the query (8:30 AM to 3:00 PM CST)
        start_ts = f"{date_obj} 08:30:00-05:00"  # 8:30 AM CST
        end_ts = f"{date_obj} 15:00:00-05:00"    # 3:00 PM CST
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (ticker, date_obj, start_ts, end_ts))
            results = cursor.fetchall()
        
        conn.close()
        
        if not results:
            return 0
        
        cross_count = 0
        previous_close = results[0]['close']
        previous_vwap = results[0]['vwap']
        
        for i in range(1, len(results)):
            current_bar = results[i]
            current_close = current_bar['close']
            current_vwap = current_bar['vwap']
            
            if (previous_close is not None and current_close is not None and 
                previous_vwap is not None and current_vwap is not None):
                if ((previous_close < previous_vwap and current_close > current_vwap) or 
                    (previous_close > previous_vwap and current_close < previous_vwap)):
                    cross_count += 1
            
            previous_close = current_close
            previous_vwap = current_vwap
        
        return cross_count
        
    except Exception as e:
        logger.error(f"Error counting VWAP crosses for {ticker} on {date}: {e}")
        return None

def get_premarket_high_low_data_ts(ticker, date_str):
    """
    Fetches premarket high/low data for a given ticker and date (3:00 AM to 8:30 AM CST) from TimescaleDB.
    Handles data gaps by trying multiple time ranges if no data is found in early hours.
    """
    try:
        conn = get_timescaledb_connection()
        if not conn:
            return None, None, None, None
        
        date_obj = pd.to_datetime(date_str).date()
        
        # Try multiple time ranges to handle data gaps
        result = try_premarket_time_ranges(conn, ticker, date_obj)
        
        conn.close()
        
        if not result:
            logger.debug(f"⚠️ No premarket data found for {ticker} on {date_str} in any time range")
            return None, None, None, None
        
        max_high, high_timestamp, min_low, low_timestamp, range_used = result
        
        # Extract time from timestamps (already in CST format)
        high_timestamp_est = extract_time_from_timestamp(high_timestamp)
        low_timestamp_est = extract_time_from_timestamp(low_timestamp)
        
        logger.debug(f"✅ Premarket data for {ticker} on {date_str}: High={max_high}@{high_timestamp_est}, Low={min_low}@{low_timestamp_est} (range: {range_used})")
        return max_high, high_timestamp_est, min_low, low_timestamp_est
        
    except Exception as e:
        logger.error(f"❌ Error fetching premarket data for {ticker} on {date_str}: {e}")
        return None, None, None, None

def get_daily_high_low_data_ts(ticker, date_str):
    """
    Fetches daily high/low data for a given ticker and date (9:30 AM to 4:00 PM EST) from TimescaleDB.
    """
    try:
        conn = get_timescaledb_connection()
        if not conn:
            return None, None, None, None
        
        date_obj = pd.to_datetime(date_str).date()
        
        # Query for daily data (8:30 AM to 3:00 PM CST)
        query = """
        SELECT 
            max(high) as max_high,
            min(low) as min_low,
            ts as timestamp
        FROM ohlcv_1m 
        WHERE ticker = %s 
        AND day = %s
        AND ts >= %s::timestamp 
        AND ts <= %s::timestamp
        GROUP BY ts
        ORDER BY ts
        """
        
        start_ts = f"{date_obj} 08:30:00-05:00"  # 8:30 AM CST
        end_ts = f"{date_obj} 15:00:00-05:00"    # 3:00 PM CST
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (ticker, date_obj, start_ts, end_ts))
            results = cursor.fetchall()
        
        conn.close()
        
        if not results:
            return None, None, None, None
        
        # Find max high and min low with their timestamps
        max_high = -1
        high_timestamp = None
        min_low = float('inf')
        low_timestamp = None
        
        for row in results:
            if row['max_high'] > max_high:
                max_high = row['max_high']
                high_timestamp = row['timestamp']
            if row['min_low'] < min_low:
                min_low = row['min_low']
                low_timestamp = row['timestamp']
        
        # Extract time from timestamps (already in EST format)
        high_timestamp_est = extract_time_from_timestamp(high_timestamp)
        low_timestamp_est = extract_time_from_timestamp(low_timestamp)
        
        return max_high, high_timestamp_est, min_low, low_timestamp_est
        
    except Exception as e:
        logger.error(f"❌ Error fetching daily data for {ticker} on {date_str}: {e}")
        return None, None, None, None

def get_premarket_volume_ts(ticker, date_str):
    """
    Fetches premarket volume for a given ticker and date (4:00 AM to 9:30 AM EST) from TimescaleDB.
    """
    try:
        conn = get_timescaledb_connection()
        if not conn:
            return 0.0
        
        date_obj = pd.to_datetime(date_str).date()
        
        # Try multiple time ranges to handle data gaps
        time_ranges = [
            (f"{date_obj} 03:00:00-05:00", f"{date_obj} 08:30:00-05:00", "3:00-8:30 AM CST"),  # Full premarket
            (f"{date_obj} 04:00:00-05:00", f"{date_obj} 08:30:00-05:00", "4:00-8:30 AM CST"),  # Skip early hours
            (f"{date_obj} 05:00:00-05:00", f"{date_obj} 08:30:00-05:00", "5:00-8:30 AM CST"),  # Skip more early hours
            (f"{date_obj} 06:00:00-05:00", f"{date_obj} 08:30:00-05:00", "6:00-8:30 AM CST"),  # Late premarket only
        ]
        
        query = """
        SELECT sum(volume) as total_volume
        FROM ohlcv_1m 
        WHERE ticker = %s 
        AND day = %s
        AND ts >= %s::timestamp 
        AND ts <= %s::timestamp
        """
        
        for start_ts, end_ts, range_desc in time_ranges:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (ticker, date_obj, start_ts, end_ts))
                    result = cursor.fetchone()
                
                if result and result['total_volume'] is not None:
                    premarket_total_volume = float(result['total_volume'])
                    logger.debug(f"📊 Premarket volume for {ticker} on {date_str}: {premarket_total_volume:,.0f} (range: {range_desc})")
                    conn.close()
                    return premarket_total_volume
                else:
                    logger.debug(f"⚠️ No volume data found in range {range_desc}")
                    
            except Exception as e:
                logger.warning(f"Error querying volume range {range_desc}: {e}")
                continue
        
        conn.close()
        logger.debug(f"⚠️ No premarket volume data found for {ticker} on {date_str} in any time range")
        return 0.0
        
    except Exception as e:
        logger.error(f"❌ Error fetching premarket volume for {ticker} on {date_str}: {e}")
        return 0.0

def fetch_single_day_data_ts(ticker, date_str):
    """
    Fetch comprehensive data for a single day from TimescaleDB.
    Returns a single data point dictionary.
    """
    try:
        conn = get_timescaledb_connection()
        if not conn:
            return None
        
        date_obj = pd.to_datetime(date_str).date()
        
        # Get daily aggregates for this specific date
        daily_query = """
        SELECT 
            first(open, ts) as open,
            max(high) as high,
            min(low) as low,
            last(close, ts) as close,
            sum(volume) as volume,
            avg(vwap) as vwap
        FROM ohlcv_1m 
        WHERE ticker = %s 
        AND day = %s
        AND ts >= %s::timestamp 
        AND ts <= %s::timestamp
        """
        
        # Trading hours: 8:30 AM to 3:00 PM CST
        start_ts = f"{date_obj} 08:30:00-05:00"
        end_ts = f"{date_obj} 15:00:00-05:00"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(daily_query, (ticker, date_obj, start_ts, end_ts))
            daily_result = cursor.fetchone()
        
        if not daily_result or daily_result['open'] is None:
            conn.close()
            return None
        
        # Get previous day data for gap calculation
        prev_date = date_obj - timedelta(days=1)
        prev_daily_query = """
        SELECT 
            last(close, ts) as close
        FROM ohlcv_1m 
        WHERE ticker = %s 
        AND day = %s
        AND ts >= %s::timestamp 
        AND ts <= %s::timestamp
        """
        
        prev_start_ts = f"{prev_date} 08:30:00-05:00"
        prev_end_ts = f"{prev_date} 15:00:00-05:00"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(prev_daily_query, (ticker, prev_date, prev_start_ts, prev_end_ts))
            prev_result = cursor.fetchone()
        
        conn.close()
        
        previous_day_close = prev_result['close'] if prev_result else None
        
        # Calculate gap percentage
        gap_percent = None
        if previous_day_close and daily_result['open']:
            gap_percent = round(((daily_result['open'] - previous_day_close) / previous_day_close) * 100, 2)
        
        # Get premarket data
        premarket_high, premarket_high_time, _, _ = get_premarket_high_low_data_ts(ticker, date_str)
        premarket_volume = get_premarket_volume_ts(ticker, date_str)
        
        # Get daily high/low data
        daily_high, daily_high_time, _, _ = get_daily_high_low_data_ts(ticker, date_str)
        
        # Calculate percentages
        percent_gap_high = None
        closing_percent = None
        if previous_day_close:
            if daily_high:
                percent_gap_high = round(((daily_high - previous_day_close) / previous_day_close) * 100, 2)
            closing_percent = round(((daily_result['close'] - previous_day_close) / previous_day_close) * 100, 2)
        
        # Get premarket open and afterhours close from TimescaleDB
        premarket_open = None
        afterhours_close = None
        
        # Get premarket open (first trade of the day)
        conn = get_timescaledb_connection()
        if conn:
            premarket_open_query = """
            SELECT open
            FROM ohlcv_1m 
            WHERE ticker = %s 
            AND day = %s
            ORDER BY ts ASC
            LIMIT 1
            """
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(premarket_open_query, (ticker, date_obj))
                premarket_open_result = cursor.fetchone()
                if premarket_open_result:
                    premarket_open = premarket_open_result['open']
            
            # Get afterhours close (last trade of the day)
            afterhours_close_query = """
            SELECT close
            FROM ohlcv_1m 
            WHERE ticker = %s 
            AND day = %s
            ORDER BY ts DESC
            LIMIT 1
            """
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(afterhours_close_query, (ticker, date_obj))
                afterhours_close_result = cursor.fetchone()
                if afterhours_close_result:
                    afterhours_close = afterhours_close_result['close']
            
            conn.close()
        
        # Determine Runner/Fader
        runner_fader = "Runner" if daily_result['close'] > daily_result['open'] else (
            "Fader" if daily_result['close'] < daily_result['open'] else "Neutral")
        
        # VWAP crosses
        vwap_crosses = count_vwap_crosses_ts(ticker, date_str)
        
        data_point = {
            'date': date_str,
            'pd close': round(previous_day_close, 2) if previous_day_close else None,
            'premarket open': round(premarket_open, 2) if premarket_open else None,
            'premarket high': round(premarket_high, 2) if premarket_high else None,
            'premarket high time': premarket_high_time,
            'premarket volume': premarket_volume,
            'open': round(daily_result['open'], 2),
            'gap up % at open': gap_percent,
            'day high': round(daily_high, 2) if daily_high else round(daily_result['high'], 2),
            'day high time': daily_high_time,
            'day high %': percent_gap_high,
            'close price': round(daily_result['close'], 2),
            'closing percent': closing_percent,
            'afterhours close': round(afterhours_close, 2) if afterhours_close else None,
            'total volume': daily_result['volume'],
            'VWAP Crosses': vwap_crosses,
            'Runner/Fader': runner_fader,
            'high': round(daily_result['high'], 2),
            'low': round(daily_result['low'], 2),
            'volume_millions': round(daily_result['volume'] / 1000000, 2),
            'dollar_volume_millions': round((daily_result['volume'] * daily_result['high']) / 1000000, 2)
        }
        
        return data_point
        
    except Exception as e:
        logger.error(f"Error fetching single day data for {ticker} on {date_str}: {e}")
        return None

def get_batch_daily_data_ts(ticker, start_date, end_date):
    """
    Fetch all daily data for a ticker in a single batch query from TimescaleDB.
    This is much faster than fetching day by day.
    """
    start_time = time.time()
    try:
        conn = get_timescaledb_connection()
        if not conn:
            return []
        
        start_date_obj = pd.to_datetime(start_date).date()
        end_date_obj = pd.to_datetime(end_date).date()
        
        # Single batch query for all daily data
        query = """
        SELECT 
            day as date,
            first(open, ts) as open,
            max(high) as high,
            min(low) as low,
            last(close, ts) as close,
            sum(volume) as volume,
            avg(vwap) as vwap
        FROM ohlcv_1m 
        WHERE ticker = %s 
        AND day >= %s 
        AND day <= %s
        AND ts >= %s::timestamp 
        AND ts <= %s::timestamp
        GROUP BY day
        ORDER BY day
        """
        
        # Trading hours: 8:30 AM to 3:00 PM CST
        start_ts = f"{start_date_obj} 08:30:00-05:00"
        end_ts = f"{end_date_obj} 15:00:00-05:00"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (ticker, start_date_obj, end_date_obj, start_ts, end_ts))
            results = cursor.fetchall()
        
        conn.close()
        
        # Convert to list of dictionaries
        daily_data = []
        for row in results:
            daily_data.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'vwap': row['vwap']
            })
        
        duration = time.time() - start_time
        log_performance('batch_daily_data_ts', duration, {
            'ticker': ticker,
            'start_date': start_date,
            'end_date': end_date,
            'data_points': len(daily_data)
        })
        
        logger.info(f"📊 Retrieved {len(daily_data)} days of batch data for {ticker} from TimescaleDB")
        return daily_data
        
    except Exception as e:
        logger.error(f"❌ Error fetching batch daily data for {ticker}: {e}")
        return []

def process_batch_data_to_gap_ups_ts(ticker, daily_data):
    """
    Process batch daily data to extract gap-up information from TimescaleDB.
    Returns only days with 25%+ gap-ups.
    """
    try:
        major_gap_up_data = []
        
        # Create a dictionary for quick lookup of previous trading days
        daily_data_dict = {}
        for data in daily_data:
            daily_data_dict[data['date']] = data
        
        for i, data in enumerate(daily_data):
            date_str = data['date']
            
            # Get previous trading day close for gap calculation
            previous_day_close = None
            
            # Find the actual previous trading day by looking back through the data
            current_date = dt.strptime(date_str, '%Y-%m-%d').date()
            for days_back in range(1, 10):  # Look back up to 10 days to find previous trading day
                prev_date = current_date - timedelta(days=days_back)
                prev_date_str = prev_date.strftime('%Y-%m-%d')
                
                if prev_date_str in daily_data_dict:
                    previous_day_close = daily_data_dict[prev_date_str]['close']
                    logger.debug(f"📊 Found previous trading day for {date_str}: {prev_date_str} (close: {previous_day_close})")
                    break
            
            # Calculate gap percentage
            gap_percent = None
            if previous_day_close and data['open']:
                gap_percent = round(((data['open'] - previous_day_close) / previous_day_close) * 100, 2)
                logger.debug(f"📈 Gap calculation for {date_str}: Open={data['open']}, PrevClose={previous_day_close}, Gap={gap_percent}%")
            
            # Only process if it's a major gap-up (25%+)
            if gap_percent and gap_percent >= 25:
                logger.info(f"🚀 Found major gap-up for {ticker} on {date_str}: {gap_percent}%")
                
                # Calculate percentages
                percent_gap_high = None
                closing_percent = None
                if previous_day_close:
                    percent_gap_high = round(((data['high'] - previous_day_close) / previous_day_close) * 100, 2)
                    closing_percent = round(((data['close'] - previous_day_close) / previous_day_close) * 100, 2)
                
                # Determine Runner/Fader
                runner_fader = "Runner" if data['close'] > data['open'] else (
                    "Fader" if data['close'] < data['open'] else "Neutral")
                
                # Get premarket data for gap-up days only (efficient approach)
                premarket_high, premarket_high_time, _, _ = get_premarket_high_low_data_ts(ticker, date_str)
                premarket_volume = get_premarket_volume_ts(ticker, date_str)
                
                # Get daily high/low data for gap-up days
                daily_high, daily_high_time, _, _ = get_daily_high_low_data_ts(ticker, date_str)
                
                # Get VWAP crosses for gap-up days
                vwap_crosses = count_vwap_crosses_ts(ticker, date_str)
                
                # Get premarket open and afterhours close from TimescaleDB
                premarket_open = None
                afterhours_close = None
                
                conn = get_timescaledb_connection()
                if conn:
                    date_obj = pd.to_datetime(date_str).date()
                    
                    # Get premarket open (first trade of the day)
                    premarket_open_query = """
                    SELECT open
                    FROM ohlcv_1m 
                    WHERE ticker = %s 
                    AND day = %s
                    ORDER BY ts ASC
                    LIMIT 1
                    """
                    
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(premarket_open_query, (ticker, date_obj))
                        premarket_open_result = cursor.fetchone()
                        if premarket_open_result:
                            premarket_open = premarket_open_result['open']
                    
                    # Get afterhours close (last trade of the day)
                    afterhours_close_query = """
                    SELECT close
                    FROM ohlcv_1m 
                    WHERE ticker = %s 
                    AND day = %s
                    ORDER BY ts DESC
                    LIMIT 1
                    """
                    
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(afterhours_close_query, (ticker, date_obj))
                        afterhours_close_result = cursor.fetchone()
                        if afterhours_close_result:
                            afterhours_close = afterhours_close_result['close']
                    
                    conn.close()
                
                data_point = {
                    'date': date_str,
                    'pd close': round(previous_day_close, 2) if previous_day_close else None,
                    'premarket open': round(premarket_open, 2) if premarket_open else None,
                    'premarket high': round(premarket_high, 2) if premarket_high else None,
                    'premarket high time': premarket_high_time,
                    'premarket volume': premarket_volume,
                    'open': round(data['open'], 2),
                    'gap up % at open': gap_percent,
                    'day high': round(daily_high if daily_high else data['high'], 2),
                    'day high time': daily_high_time,
                    'day high %': percent_gap_high,
                    'close price': round(data['close'], 2),
                    'closing percent': closing_percent,
                    'afterhours close': round(afterhours_close, 2) if afterhours_close else None,
                    'total volume': data['volume'],
                    'VWAP Crosses': vwap_crosses,
                    'Runner/Fader': runner_fader,
                    'high': round(data['high'], 2),
                    'low': round(data['low'], 2),
                    'volume_millions': round(data['volume'] / 1000000, 2),
                    'dollar_volume_millions': round((data['volume'] * data['high']) / 1000000, 2)
                }
                
                major_gap_up_data.append(data_point)
        
        logger.info(f"📈 Found {len(major_gap_up_data)} major gap-up days (25%+) for {ticker}")
        return major_gap_up_data
        
    except Exception as e:
        logger.error(f"❌ Error processing batch data for {ticker}: {e}")
        return []

def get_historical_gap_up_data_ts(ticker, days=30, use_cache=True):
    """
    Get comprehensive historical gap-up data for a stock using TimescaleDB and intelligent caching.
    Returns detailed gap-up analysis for the specified number of days.
    Only caches days when stocks actually gap up by 25% or more (gap_percent >= 25).
    """
    start_time = time.time()
    try:
        # Calculate date range based on requested days
        end_date = dt.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Format dates for API and cache
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")
        
        logger.info(f"📊 Fetching historical gap-up data for {ticker} from TimescaleDB: {from_date} to {to_date} ({days} days)")
        
        # Check cache first (same logic as original)
        cached_data = []
        if use_cache:
            cache_status = historical_cache.get_cache_status(ticker)
            logger.info(f"Cache status for {ticker}: {cache_status}")
            
            is_fresh = historical_cache.is_data_fresh(ticker, max_age_hours=24)
            logger.info(f"Cache freshness for {ticker}: {'Fresh' if is_fresh else 'Stale'}")
            
            cached_data = historical_cache.get_cached_data(ticker, from_date, to_date)
            logger.info(f"DEBUG: Retrieved {len(cached_data)} cached records for {ticker}")
            
            if cached_data and is_fresh:
                requested_cached_data = [data for data in cached_data 
                                      if from_date <= data['date'] <= to_date]
                if requested_cached_data:
                    requested_cached_data.sort(key=lambda x: x['date'], reverse=True)
                    logger.info(f"✅ Returning {len(requested_cached_data)} fresh cached gap-up days for {ticker}")
                    return requested_cached_data
        
        # If no cache or insufficient cached data, fetch from TimescaleDB
        logger.info(f"🔄 Fetching fresh batch data from TimescaleDB for {ticker}")
        
        try:
            # Use batch processing for much faster data retrieval
            daily_data = get_batch_daily_data_ts(ticker, from_date, to_date)
        except Exception as e:
            logger.error(f"❌ Error fetching batch data for {ticker}: {e}")
            return []
        
        if not daily_data:
            logger.error(f"❌ No historical data found for {ticker}")
            return []
        
        # Process batch data to extract gap-up information
        major_gap_up_data = process_batch_data_to_gap_ups_ts(ticker, daily_data)
        
        # Sort by date (most recent first)
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
        
        duration = time.time() - start_time
        log_performance('historical_gap_up_data_ts', duration, {
            'ticker': ticker,
            'days': days,
            'use_cache': use_cache,
            'total_days': len(daily_data),
            'gap_up_days': len(major_gap_up_data)
        })
        
        logger.info(f"✅ Retrieved {len(daily_data)} days of historical data for {ticker} from TimescaleDB")
        logger.info(f"📈 Found {len(major_gap_up_data)} major gap-up days (25%+) for {ticker}")
        
        # Return only gap-up data
        return major_gap_up_data[:days]
        
    except Exception as e:
        duration = time.time() - start_time
        log_error(e, {
            'ticker': ticker,
            'days': days,
            'use_cache': use_cache,
            'function': 'get_historical_gap_up_data_ts'
        })
        logger.error(f"❌ Error getting historical gap-up data for {ticker}: {e}")
        return []

def fetch_multiple_stocks_parallel_ts(tickers, days=365, use_cache=True, max_workers=5):
    """
    Fetch historical gap-up data for multiple stocks in parallel using TimescaleDB.
    This significantly improves performance when processing multiple tickers.
    
    Args:
        tickers: List of ticker symbols
        days: Number of days to fetch data for
        use_cache: Whether to use caching
        max_workers: Maximum number of parallel workers (default: 5)
    """
    try:
        logger.info(f"🚀 Starting parallel processing for {len(tickers)} tickers using TimescaleDB (max_workers={max_workers})")
        
        # Use ThreadPoolExecutor for I/O-bound operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(get_historical_gap_up_data_ts, ticker, days, use_cache): ticker 
                for ticker in tickers
            }
            
            # Collect results as they complete
            results = {}
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    results[ticker] = data
                    completed_count += 1
                    logger.info(f"✅ Completed processing for {ticker} ({completed_count}/{len(tickers)})")
                except Exception as e:
                    logger.error(f"❌ Error processing {ticker}: {e}")
                    results[ticker] = None
                    completed_count += 1
        
        logger.info(f"🎉 Parallel processing completed for {len(tickers)} tickers using TimescaleDB")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error in parallel processing: {e}")
        return {}

def fetch_single_day_data_parallel_ts(tickers, date_str, max_workers=10):
    """
    Fetch single day data for multiple tickers in parallel.
    Useful for analyzing a specific date across multiple stocks.
    
    Args:
        tickers: List of ticker symbols
        date_str: Date string in YYYY-MM-DD format
        max_workers: Maximum number of parallel workers
    """
    try:
        logger.info(f"🚀 Starting parallel single day data fetch for {len(tickers)} tickers on {date_str}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(fetch_single_day_data_ts, ticker, date_str): ticker 
                for ticker in tickers
            }
            
            # Collect results as they complete
            results = {}
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    results[ticker] = data
                    completed_count += 1
                    if data:
                        logger.info(f"✅ Completed {ticker} ({completed_count}/{len(tickers)}) - Gap: {data.get('gap up % at open', 'N/A')}%")
                    else:
                        logger.info(f"⚠️ No data for {ticker} ({completed_count}/{len(tickers)})")
                except Exception as e:
                    logger.error(f"❌ Error processing {ticker}: {e}")
                    results[ticker] = None
                    completed_count += 1
        
        logger.info(f"🎉 Parallel single day processing completed for {len(tickers)} tickers")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error in parallel single day processing: {e}")
        return {}

def fetch_batch_data_parallel_ts(tickers, start_date, end_date, max_workers=5):
    """
    Fetch batch daily data for multiple tickers in parallel.
    More efficient than individual ticker processing for large date ranges.
    
    Args:
        tickers: List of ticker symbols
        start_date: Start date string in YYYY-MM-DD format
        end_date: End date string in YYYY-MM-DD format
        max_workers: Maximum number of parallel workers
    """
    try:
        logger.info(f"🚀 Starting parallel batch data fetch for {len(tickers)} tickers from {start_date} to {end_date}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(get_batch_daily_data_ts, ticker, start_date, end_date): ticker 
                for ticker in tickers
            }
            
            # Collect results as they complete
            results = {}
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    results[ticker] = data
                    completed_count += 1
                    logger.info(f"✅ Completed batch data for {ticker} ({completed_count}/{len(tickers)}) - {len(data)} days")
                except Exception as e:
                    logger.error(f"❌ Error processing batch data for {ticker}: {e}")
                    results[ticker] = None
                    completed_count += 1
        
        logger.info(f"🎉 Parallel batch processing completed for {len(tickers)} tickers")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error in parallel batch processing: {e}")
        return {}

def process_gap_ups_parallel_ts(ticker_batch_data, max_workers=5):
    """
    Process gap-up data for multiple tickers in parallel.
    Takes pre-fetched batch data and processes it for gap-ups.
    
    Args:
        ticker_batch_data: Dictionary with ticker as key and batch data as value
        max_workers: Maximum number of parallel workers
    """
    try:
        logger.info(f"🚀 Starting parallel gap-up processing for {len(ticker_batch_data)} tickers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(process_batch_data_to_gap_ups_ts, ticker, batch_data): ticker 
                for ticker, batch_data in ticker_batch_data.items()
                if batch_data  # Only process tickers with data
            }
            
            # Collect results as they complete
            results = {}
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    gap_ups = future.result()
                    results[ticker] = gap_ups
                    completed_count += 1
                    logger.info(f"✅ Completed gap-up processing for {ticker} ({completed_count}/{len(ticker_batch_data)}) - {len(gap_ups)} gap-ups")
                except Exception as e:
                    logger.error(f"❌ Error processing gap-ups for {ticker}: {e}")
                    results[ticker] = None
                    completed_count += 1
        
        logger.info(f"🎉 Parallel gap-up processing completed for {len(ticker_batch_data)} tickers")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error in parallel gap-up processing: {e}")
        return {}

def fetch_comprehensive_parallel_ts(tickers, days=30, max_workers=5, use_cache=True):
    """
    Comprehensive parallel processing that fetches batch data and processes gap-ups.
    This is the most efficient way to process multiple tickers.
    
    Args:
        tickers: List of ticker symbols
        days: Number of days to fetch data for
        max_workers: Maximum number of parallel workers
        use_cache: Whether to use caching
    """
    try:
        logger.info(f"🚀 Starting comprehensive parallel processing for {len(tickers)} tickers ({days} days)")
        
        # Calculate date range
        end_date = dt.now().date()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Step 1: Fetch batch data in parallel
        logger.info("📦 Step 1: Fetching batch data in parallel...")
        batch_results = fetch_batch_data_parallel_ts(tickers, start_date_str, end_date_str, max_workers)
        
        # Step 2: Process gap-ups in parallel
        logger.info("🚀 Step 2: Processing gap-ups in parallel...")
        gap_up_results = process_gap_ups_parallel_ts(batch_results, max_workers)
        
        # Step 3: Cache results if enabled
        if use_cache:
            logger.info("💾 Step 3: Caching results...")
            for ticker, gap_ups in gap_up_results.items():
                if gap_ups:
                    historical_cache.store_historical_data(ticker, gap_ups, start_date_str, end_date_str)
        
        # Summary
        total_gap_ups = sum(len(gap_ups) for gap_ups in gap_up_results.values() if gap_ups)
        logger.info(f"🎉 Comprehensive parallel processing completed!")
        logger.info(f"📊 Processed {len(tickers)} tickers, found {total_gap_ups} total gap-ups")
        
        return gap_up_results
        
    except Exception as e:
        logger.error(f"❌ Error in comprehensive parallel processing: {e}")
        return {}

def get_cache_stats():
    """Get cache statistics"""
    return historical_cache.get_cache_stats()

def clear_cache(ticker=None):
    """Clear cache for a specific ticker or all tickers"""
    return historical_cache.clear_cache(ticker)

if __name__ == "__main__":
    # Test the functions
    print("🧪 Testing TimescaleDB historical data functions with caching...")
    
    # Test cache stats
    stats = get_cache_stats()
    print(f"📊 Cache stats: {stats}")
    
    # Test historical data retrieval
    result = get_historical_gap_up_data_ts("AAPL", 30)
    if result:
        print(f"✅ Successfully retrieved data for AAPL from TimescaleDB")
        print(f"📊 Data points: {len(result)}")
        
        # Test cache stats after retrieval
        stats_after = get_cache_stats()
        print(f"📊 Cache stats after retrieval: {stats_after}")
    else:
        print("❌ Failed to retrieve data from TimescaleDB")
