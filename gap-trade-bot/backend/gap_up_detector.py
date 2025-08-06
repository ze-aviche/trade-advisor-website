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

# Load environment variables
load_dotenv()

# Setup logger
logger = get_logger(__name__)

# Import gap tracker
try:
    from gap_tracker import gap_tracker
    GAP_TRACKER_AVAILABLE = True
    logger.info("✅ Gap tracker loaded successfully")
except ImportError:
    GAP_TRACKER_AVAILABLE = False
    logger.warning("⚠️ Gap tracker not available, using basic detection")

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

def get_real_time_quote(ticker, polygon_client):
    """
    Get real-time quote for a ticker during pre-market/after-hours
    """
    try:
        # Get real-time quote
        quote = polygon_client.get_last_quote(ticker)
        if quote:
            if hasattr(quote, 'bid_price') and hasattr(quote, 'ask_price'):
                mid_price = (quote.bid_price + quote.ask_price) / 2
                logger.info(f"✅ Real-time quote for {ticker}: Bid=${quote.bid_price}, Ask=${quote.ask_price}, Mid=${mid_price:.2f}")
                return mid_price
            elif hasattr(quote, 'price'):
                logger.info(f"✅ Real-time quote for {ticker}: Price=${quote.price}")
                return quote.price
            else:
                logger.warning(f"❌ Quote object has unexpected structure")
                return None
        else:
            logger.warning(f"❌ No real-time quote available for {ticker}")
            return None
    except Exception as e:
        logger.error(f"❌ Error getting real-time quote for {ticker}: {e}")
        return None

def get_current_price(ticker, polygon_client):
    """
    Get current price for a ticker using Polygon aggregates endpoint for today
    """
    try:
        today = dt.now().date()
        date_str = today.strftime("%Y-%m-%d")
        
        logger.info(f"🔍 Getting current price for {ticker} on {date_str}")
        
        # Check current time to determine market status
        current_time = dt.now()
        market_status = check_market_timing()
        
        logger.info(f"🕐 Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if market_status == "pre_market":
            logger.info(f"📈 Pre-market hours - limited data availability")
            # Try real-time quote first
            real_time_price = get_real_time_quote(ticker, polygon_client)
            if real_time_price:
                return real_time_price
            
            # Fallback to aggregates if real-time quote fails
            logger.info(f"📈 Market is pre_market, trying real-time quote...")
            return get_real_time_quote(ticker, polygon_client)
            
        elif market_status == "open":
            logger.info(f"📈 Market is open - using regular aggregates")
            # Use regular aggregates for market hours
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
                logger.info(f"✅ Current price for {ticker}: ${current_price}")
                return current_price
            else:
                logger.warning(f"❌ No current price data for {ticker}")
                return None
                
        elif market_status == "after_hours":
            logger.info(f"📈 After-hours - using real-time quotes")
            return get_real_time_quote(ticker, polygon_client)
            
        else:
            logger.warning(f"❌ Unknown market status: {market_status}")
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
        new_peaks_detected = []
        drop_candidates = []
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
                    
                    # Only process stocks with significant gap-up (2% or more)
                    if gap_percent >= 2.0:
                        # Use gap tracker if available
                        if GAP_TRACKER_AVAILABLE:
                            # Update gap tracker
                            is_new_peak, peak_data = gap_tracker.update_gap(ticker, gap_percent, current_price)
                            
                            # Check for significant drop from peak (for shorting)
                            is_significant_drop = gap_tracker.is_significant_drop(ticker, gap_percent, drop_threshold=10.0)
                            
                            if is_new_peak:
                                # New peak detected - add to gap-up stocks for breakout strategy
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
                                    'is_new_peak': True,
                                    'peak_data': peak_data
                                }
                                gap_up_stocks.append(stock_info)
                                new_peaks_detected.append(ticker)
                                logger.info(f"🚀 NEW PEAK GAP-UP: {ticker} - {gap_percent:.2f}% gap")
                            elif is_significant_drop:
                                # Significant drop detected - add to drop candidates for shorting
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
                                    'is_significant_drop': True,
                                    'peak_data': peak_data
                                }
                                drop_candidates.append(stock_info)
                                logger.info(f"📉 DROP CANDIDATE: {ticker} - {gap_percent:.2f}% (peak: {peak_data['peak_gap']:.2f}%)")
                            else:
                                # Not a new peak and not a significant drop - skip
                                logger.debug(f"⏭️ {ticker}: {gap_percent:.2f}% (not new peak, not significant drop)")
                        else:
                            # Basic detection without peak tracking
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
                        logger.warning(f"❌ {ticker}: Gap {gap_percent:.2f}% < 2.0% threshold")
                        
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
        logger.info(f"📊 Tickers with gap < 2%: {gap_too_small}")
        if GAP_TRACKER_AVAILABLE:
            logger.info(f"🚀 New peaks detected: {len(new_peaks_detected)}")
            logger.info(f"📉 Drop candidates: {len(drop_candidates)}")
        logger.info(f"✅ Final gap-up stocks found: {len(gap_up_stocks)}")
        
        # Store gap-up stocks in database
        if gap_up_stocks:
            logger.info("💾 Storing gap-up stocks in database...")
            store_daily_gap_ups(gap_up_stocks)
        
        return gap_up_stocks
        
    except Exception as e:
        logger.error(f"❌ Error in get_gap_up_stocks: {e}")
        return []

def get_drop_candidates_for_shorting():
    """
    Get stocks that have dropped significantly from their peak for shorting opportunities
    """
    if not GAP_TRACKER_AVAILABLE:
        logger.warning("⚠️ Gap tracker not available for drop candidates")
        return []
    
    try:
        # Get all peak data
        all_peaks = gap_tracker.get_all_peaks()
        drop_candidates = []
        
        for ticker, peak_data in all_peaks.items():
            # Get current gap for this ticker
            polygon_client = get_polygon_client()
            previous_close = get_previous_close_price(ticker, polygon_client)
            current_price = get_current_price(ticker, polygon_client)
            
            if previous_close and current_price:
                current_gap = ((current_price - previous_close) / previous_close) * 100
                
                # Check if it's a significant drop from peak
                if gap_tracker.is_significant_drop(ticker, current_gap, drop_threshold=10.0):
                    drop_candidates.append({
                        'ticker': ticker,
                        'current_gap': current_gap,
                        'peak_gap': peak_data['peak_gap'],
                        'drop_percentage': peak_data['peak_gap'] - current_gap,
                        'peak_data': peak_data
                    })
        
        logger.info(f"📉 Found {len(drop_candidates)} drop candidates for shorting")
        return drop_candidates
        
    except Exception as e:
        logger.error(f"❌ Error getting drop candidates: {e}")
        return []

def store_daily_gap_ups(gap_up_stocks):
    """
    Store daily gap-up stocks in the database
    """
    try:
        # Connect to database in strategies folder
        db_path = os.path.join(os.path.dirname(__file__), 'bot', 'strategies', 'gap_up_history.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get today's date
        today = dt.now().strftime('%Y-%m-%d')
        
        # First, check if we already have data for today
        cursor.execute("SELECT COUNT(*) FROM DAILY_GAP_UPS WHERE date = ?", (today,))
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            logger.warning(f"⚠️ Already have {existing_count} gap-up records for {today}, skipping...")
            conn.close()
            return
        
        # Insert new gap-up stocks
        inserted_count = 0
        for stock in gap_up_stocks:
            try:
                cursor.execute("""
                    INSERT INTO DAILY_GAP_UPS 
                    (date, ticker, prev_close, open_price, gap_percent, volume, market_cap, sector)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    today,
                    stock['ticker'],
                    stock.get('previous_close', 0),
                    stock.get('price', 0),
                    stock.get('gap_percent', 0),
                    stock.get('volume', 0),
                    stock.get('market_cap', 0),
                    stock.get('sector', '')
                ))
                inserted_count += 1
                logger.info(f"✅ Stored {stock['ticker']} in database")
                
            except Exception as e:
                logger.error(f"❌ Error storing {stock['ticker']}: {e}")
                continue
        
        # Commit changes
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Successfully stored {inserted_count} gap-up stocks for {today}")
        
    except Exception as e:
        logger.error(f"❌ Error storing daily gap-ups: {e}")

def get_daily_gap_ups_from_db(date=None):
    """
    Retrieve daily gap-up stocks from database
    """
    try:
        # Connect to database in strategies folder
        db_path = os.path.join(os.path.dirname(__file__), 'bot', 'strategies', 'gap_up_history.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get today's date if not specified
        if date is None:
            date = dt.now().strftime('%Y-%m-%d')
        
        # Query gap-up stocks for the specified date
        cursor.execute("""
            SELECT ticker, prev_close, open_price, gap_percent, volume, market_cap, sector
            FROM DAILY_GAP_UPS 
            WHERE date = ?
            ORDER BY gap_percent DESC
        """, (date,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        gap_ups = []
        for row in results:
            gap_ups.append({
                'ticker': row[0],
                'previous_close': row[1],
                'price': row[2],
                'gap_percent': row[3],
                'volume': row[4],
                'market_cap': row[5],
                'sector': row[6]
            })
        
        logger.info(f"📊 Retrieved {len(gap_ups)} gap-up stocks for {date}")
        return gap_ups
        
    except Exception as e:
        logger.error(f"❌ Error retrieving daily gap-ups: {e}")
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
        try:
            quote = get_real_time_quote(ticker, polygon_client)
            logger.info(f"✅ Real-time quote available: ${quote}")
        except Exception as e:
            logger.error(f"❌ Real-time quote failed: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error testing {ticker}: {e}")

if __name__ == "__main__":
    # Test the gap-up detection
    gap_ups = get_gap_up_stocks()
    print(f"Found {len(gap_ups)} gap-up stocks")
    for stock in gap_ups[:5]:  # Show first 5
        print(f"  {stock['ticker']}: {stock['gap_percent']}% gap") 