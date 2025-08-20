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
    """
    Check if we're in market hours and what data should be available
    """
    now = dt.now()
    current_time = now.time()
    
    # Check if it's a weekend (Saturday = 5, Sunday = 6)
    if now.weekday() >= 5:
        logger.info("📈 Weekend detected - market is closed")
        return "closed"
    
    # Market hours (EST/EDT)
    market_open = dt.strptime("09:30", "%H:%M").time()
    market_close = dt.strptime("16:00", "%H:%M").time()
    
    # Pre-market (4:00 AM - 9:30 AM)
    pre_market_start = dt.strptime("04:00", "%H:%M").time()
    
    # After hours (4:00 PM - 8:00 PM)
    after_hours_end = dt.strptime("20:00", "%H:%M").time()
    
    logger.info(f"🕐 Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if pre_market_start <= current_time < market_open:
        logger.info("📈 Pre-market hours - limited data availability")
        return "pre_market"
    elif market_open <= current_time <= market_close:
        logger.info("📈 Market hours - real-time data available")
        return "open"  # Changed from "market_hours" to "open" for consistency
    elif market_close < current_time <= after_hours_end:
        logger.info("📈 After hours - limited data availability")
        return "after_hours"
    else:
        logger.info("📈 Outside market hours - historical data only")
        return "closed"

@cached_gap_up_detection(cache_type="default")
def get_gap_up_stocks():
    """
    Get real gap-up stocks using Polygon API with peak tracking
    Returns a list of dictionaries with stock information
    """
    try:
        polygon_client = get_polygon_client()
        logger.info("✅ Polygon API client initialized successfully")
        
        # Check market timing
        market_status = check_market_timing()
        
        # Get gainers from Polygon
        logger.info("Fetching gainers from Polygon API...")
        tickers = polygon_client.get_snapshot_direction(
            "stocks",
            direction="gainers",
        )
        
        gap_up_stocks = []
        total_tickers = 0
        cs_type_count = 0
        no_previous_close = 0
        no_current_price = 0
        gap_too_small = 0
        below_075_count = 0
        
        if not tickers or not isinstance(tickers, list):
            logger.warning("❌ No tickers returned from Polygon API")
            return []
            
        logger.info(f"✅ Processing {len(tickers)} gainers from Polygon API")
        
        for item in tickers:
            ticker = None
            if isinstance(item, dict):
                ticker = item.get("ticker") or item.get("symbol")
            elif hasattr(item, "ticker"):
                ticker = getattr(item, "ticker", None)
            elif hasattr(item, "symbol"):
                ticker = getattr(item, "symbol", None)
                
            if not ticker:
                continue
                
            total_tickers += 1
            logger.info(f"\n🔍 Processing ticker {total_tickers}: {ticker}")
            
            try:
                # Get ticker details
                details = polygon_client.get_ticker_details(ticker)
                issue_type = details.type
                
                if issue_type == "CS":  # Common Stock
                    cs_type_count += 1
                    previous_close = get_previous_close_price(ticker, polygon_client)
                    current_price = get_current_price(ticker, polygon_client)
                    
                    # Debug information
                    if previous_close is None:
                        no_previous_close += 1
                        logger.warning(f"❌ {ticker}: No previous close available")
                        continue
                        
                    if current_price is None:
                        no_current_price += 1
                        logger.warning(f"❌ {ticker}: No current price available")
                        continue
                        
                    if current_price < 0.75:
                        below_075_count += 1
                        logger.warning(f"❌ {ticker}: Current price ${current_price} < $0.75")
                        continue
                    
                    # Calculate gap percentage
                    gap_percent = ((current_price - previous_close) / previous_close) * 100
                    logger.info(f"📊 {ticker}: Previous=${previous_close}, Current=${current_price}, Gap={gap_percent:.2f}%")
                    
                    # Only process stocks with significant gap-up (25% or more)
                    if gap_percent >= 25.0:
                        # Simple gap-up detection without strategy tracking
                        stock_info = {
                            'ticker': ticker,
                            'company_name': details.name,
                            'price': round(current_price, 2),
                            'previous_close': round(previous_close, 2),
                            'change': round(current_price - previous_close, 2),
                            'change_percent': round(gap_percent, 2),
                            'gap_percent': round(gap_percent, 2),
                            'volume': getattr(details, 'share_class_shares_outstanding', 0),
                            'market_cap': getattr(details, 'market_cap', 0),
                            'sector': getattr(details, 'sic_description', 'Unknown'),
                            'list_date': getattr(details, 'list_date', None)
                        }
                        gap_up_stocks.append(stock_info)
                        logger.info(f"✅ Gap-up found: {ticker} - {gap_percent:.2f}% gap")
                    else:
                        gap_too_small += 1
                        logger.warning(f"❌ {ticker}: Gap {gap_percent:.2f}% < 25.0% threshold")
                        
            except Exception as e:
                logger.error(f"❌ Error processing {ticker}: {e}")
                continue
                
        logger.info(f"\n📊 SUMMARY:")
        logger.info(f"📊 Market status: {market_status}")
        logger.info(f"📊 Total tickers processed: {total_tickers}")
        logger.info(f"📊 Common stock tickers: {cs_type_count}")
        logger.info(f"📊 Tickers with price < $0.75: {below_075_count}")
        logger.info(f"📊 Tickers with no previous close: {no_previous_close}")
        logger.info(f"📊 Tickers with no current price: {no_current_price}")
        logger.info(f"📊 Tickers with gap < 25%: {gap_too_small}")
        logger.info(f"✅ Final gap-up stocks found: {len(gap_up_stocks)}")
        

        
        return gap_up_stocks
        
    except Exception as e:
        logger.error(f"❌ Error in get_gap_up_stocks: {e}")
        return []

def get_gap_up_stocks_for_frontend():
    """
    Get gap-up stocks for frontend display by scanning the entire market
    Uses 15-minute delayed data to reduce API costs while still finding actual gap-up stocks
    Perfect for early morning gap-up detection (7 AM ET login with 15-min delayed data)
    """
    try:
        # Gap-up configuration (configurable via frontend)
        # Import from config to ensure synchronization
        import sys
        import config as config_module
        GAP_UP_MIN_PERCENTAGE = getattr(config_module, 'GAP_UP_MIN_PERCENTAGE', 15.0)
        GAP_UP_MIN_PRICE = 0.75
        USE_DELAYED_DATA = True
        DELAYED_DATA_DESCRIPTION = '15-minute delayed data for cost optimization'
        
        # Debug: Log the actual threshold being used
        logger.info(f"🔧 DEBUG: Using threshold from config: {GAP_UP_MIN_PERCENTAGE}%")
        logger.info(f"🔧 DEBUG: Config module path: {config_module.__file__}")
        logger.info(f"🔧 DEBUG: All config attributes: {[attr for attr in dir(config_module) if not attr.startswith('_')]}")
        
        # Use threshold-aware caching
        from gap_up_cache import gap_up_cache
        cache_key = f"gap_up_frontend_threshold_{GAP_UP_MIN_PERCENTAGE}"
        
        # Try to get from cache first
        cached_result = gap_up_cache.get(cache_key, "real_time")
        if cached_result is not None:
            logger.info(f"✅ Returning cached gap-up results for threshold {GAP_UP_MIN_PERCENTAGE}%")
            return cached_result
        
        polygon_client = get_polygon_client()
        logger.info("✅ Polygon API client initialized successfully")
        
        # Check market timing
        market_status = check_market_timing()
        
        # Scan the entire market for actual gap-up stocks using delayed data
        # This is perfect for 7 AM ET login when you want to see what gapped up > 25%
        logger.info(f"📊 Scanning entire market for gap-up stocks ({DELAYED_DATA_DESCRIPTION})")
        logger.info(f"📊 Looking for stocks with gap >= {GAP_UP_MIN_PERCENTAGE}% (threshold)")
        
        # Get gainers from Polygon API (this scans the entire market)
        # Using delayed data means we get the gainers as of 15 minutes ago
        # Perfect for early morning gap-up detection
        logger.info("🔍 Fetching market gainers from Polygon API (delayed data)...")
        tickers = polygon_client.get_snapshot_direction(
            "stocks",
            direction="gainers",
        )
        
        gap_up_stocks = []
        total_tickers = 0
        cs_type_count = 0
        no_previous_close = 0
        no_current_price = 0
        gap_too_small = 0
        below_075_count = 0
        
        if not tickers or not isinstance(tickers, list):
            logger.warning("❌ No tickers returned from Polygon API")
            return []
            
        logger.info(f"✅ Processing {len(tickers)} gainers from entire market")
        
        for item in tickers:
            ticker = None
            if isinstance(item, dict):
                ticker = item.get("ticker") or item.get("symbol")
            elif hasattr(item, "ticker"):
                ticker = getattr(item, "ticker", None)
            elif hasattr(item, "symbol"):
                ticker = getattr(item, "symbol", None)
                
            if not ticker:
                continue
                
            total_tickers += 1
            logger.info(f"\n🔍 Processing ticker {total_tickers}: {ticker}")
            
            try:
                # Get ticker details
                details = polygon_client.get_ticker_details(ticker)
                issue_type = details.type
                
                if issue_type == "CS":  # Common Stock
                    cs_type_count += 1
                    previous_close = get_previous_close_price(ticker, polygon_client)
                    current_price = get_current_price(ticker, polygon_client)
                    
                    # Debug information
                    if previous_close is None:
                        no_previous_close += 1
                        logger.warning(f"❌ {ticker}: No previous close available")
                        continue
                        
                    if current_price is None:
                        no_current_price += 1
                        logger.warning(f"❌ {ticker}: No current price available")
                        continue
                        
                    if current_price < GAP_UP_MIN_PRICE:
                        below_075_count += 1
                        logger.warning(f"❌ {ticker}: Current price ${current_price} < ${GAP_UP_MIN_PRICE}")
                        continue
                    
                    # Calculate gap percentage
                    gap_percent = ((current_price - previous_close) / previous_close) * 100
                    logger.info(f"📊 {ticker}: Previous=${previous_close}, Current=${current_price}, Gap={gap_percent:.2f}%")
                    
                    # Only process stocks with significant gap-up (25% or more as per user requirement)
                    if gap_percent >= GAP_UP_MIN_PERCENTAGE:
                        # Simple gap-up detection without strategy tracking
                        stock_info = {
                            'ticker': ticker,
                            'company_name': details.name,
                            'price': round(current_price, 2),
                            'previous_close': round(previous_close, 2),
                            'change': round(current_price - previous_close, 2),
                            'change_percent': round(gap_percent, 2),
                            'gap_percent': round(gap_percent, 2),
                            'volume': getattr(details, 'share_class_shares_outstanding', 0),
                            'market_cap': getattr(details, 'market_cap', 0),
                            'sector': getattr(details, 'sic_description', 'Unknown'),
                            'list_date': getattr(details, 'list_date', None),
                            'discovery_method': 'market_scan'
                        }
                        
                        gap_up_stocks.append(stock_info)
                        logger.info(f"🚀 MARKET GAP-UP FOUND: {ticker} - {gap_percent:.2f}% gap")
                    else:
                        gap_too_small += 1
                        logger.warning(f"❌ {ticker}: Gap {gap_percent:.2f}% < {GAP_UP_MIN_PERCENTAGE}% threshold")
                        
            except Exception as e:
                logger.error(f"❌ Error processing {ticker}: {e}")
                continue
                
        logger.info(f"\n📊 SUMMARY:")
        logger.info(f"📊 Market status: {market_status}")
        logger.info(f"📊 Data source: {DELAYED_DATA_DESCRIPTION}")
        logger.info(f"📊 Total tickers processed: {total_tickers}")
        logger.info(f"📊 Common stock tickers: {cs_type_count}")
        logger.info(f"📊 Tickers with price < ${GAP_UP_MIN_PRICE}: {below_075_count}")
        logger.info(f"📊 Tickers with no previous close: {no_previous_close}")
        logger.info(f"📊 Tickers with no current price: {no_current_price}")
        logger.info(f"📊 Tickers with gap < {GAP_UP_MIN_PERCENTAGE}%: {gap_too_small}")
        logger.info(f"✅ Final gap-up stocks found: {len(gap_up_stocks)}")
        
        # Cache the results with threshold-aware key
        try:
            gap_up_cache.set(cache_key, gap_up_stocks, "real_time")
            logger.info(f"💾 Cached gap-up results for threshold {GAP_UP_MIN_PERCENTAGE}%")
        except Exception as cache_error:
            logger.warning(f"⚠️ Could not cache results: {cache_error}")
        
        return gap_up_stocks
        
    except Exception as e:
        logger.error(f"❌ Error in get_gap_up_stocks_for_frontend: {e}")
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