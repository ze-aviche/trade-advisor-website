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

def get_polygon_client():
    """Get Polygon API client with API key"""
    # Try to get API key from environment variable first
    api_key = os.environ.get('POLYGON_API_KEY')
    
    # If not found, use the one from trading-advisor project
    if not api_key:
        api_key = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
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

def get_gap_up_stocks_for_frontend():
    """
    Fetch all market gainers and return Common Stock gap-ups with no percentage threshold.
    Uses snapshot data (prev_day + day) for price/volume — no extra API calls per ticker.
    """
    GAP_UP_MIN_PRICE = 0.75

    from gap_up_cache import gap_up_cache
    cache_key = "gap_up_frontend_all"

    cached_result = gap_up_cache.get(cache_key, "real_time")
    if cached_result is not None:
        logger.info(f"Cache HIT: returning {len(cached_result)} gap-up stocks")
        return cached_result

    try:
        polygon_client = get_polygon_client()
        market_status = check_market_timing()
        logger.info(f"Fetching market gainers (status: {market_status})")

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
                # Pull price and volume directly from snapshot — no extra API calls
                prev_day = getattr(item, 'prev_day', None)
                day      = getattr(item, 'day', None)

                previous_close = getattr(prev_day, 'close', None) if prev_day else None
                current_price  = getattr(day, 'close', None)  if day  else None
                volume         = getattr(day, 'volume', 0)     if day  else 0

                if previous_close is None or current_price is None or previous_close == 0:
                    skipped_no_data += 1
                    continue

                if current_price < GAP_UP_MIN_PRICE:
                    skipped_price += 1
                    continue

                # Still need ticker_details for the Common Stock type check
                details = polygon_client.get_ticker_details(ticker)
                if getattr(details, 'type', None) != "CS":
                    skipped_non_cs += 1
                    continue

                gap_percent = ((current_price - previous_close) / previous_close) * 100

                gap_up_stocks.append({
                    'ticker':        ticker,
                    'company_name':  details.name,
                    'price':         round(current_price, 2),
                    'previous_close': round(previous_close, 2),
                    'change':        round(current_price - previous_close, 2),
                    'change_percent': round(gap_percent, 2),
                    'gap_percent':   round(gap_percent, 2),
                    'volume':        int(volume or 0),
                    'market_cap':    getattr(details, 'market_cap', 0),
                    'sector':        getattr(details, 'sic_description', 'Unknown'),
                    'list_date':     getattr(details, 'list_date', None),
                })

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                continue

        # Return sorted by gap % descending so the biggest movers are first by default
        gap_up_stocks.sort(key=lambda x: x['gap_percent'], reverse=True)

        logger.info(
            f"Done — {len(gap_up_stocks)} CS gap-ups found "
            f"(skipped: {skipped_non_cs} non-CS, {skipped_price} below ${GAP_UP_MIN_PRICE}, "
            f"{skipped_no_data} missing data)"
        )

        gap_up_cache.set(cache_key, gap_up_stocks, "real_time")
        return gap_up_stocks

    except Exception as e:
        logger.error(f"Error in get_gap_up_stocks_for_frontend: {e}")
        return []







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