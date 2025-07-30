#!/usr/bin/env python3
"""
Real Gap-Up Stock Detection using Polygon API
Based on the trading-advisor project implementation
"""
import os
import datetime
from datetime import datetime as dt, timedelta
import pytz
from polygon import RESTClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_polygon_client():
    """Get Polygon API client with API key"""
    # Try to get API key from environment variable first
    api_key = os.environ.get('POLYGON_API_KEY')
    
    # If not found, use the one from trading-advisor project
    if not api_key:
        api_key = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
        print("Using default Polygon API key from trading-advisor project")
    
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
    print(f"Using last trading day: {date_str} for {ticker}")
    
    try:
        aggs = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=date_str,
            to=date_str
        )
        if aggs and len(aggs) > 0:
            return aggs[0].close
        else:
            print(f"No previous close found for {ticker}")
            return None
    except Exception as e:
        print(f"Error fetching previous close for {ticker}: {e}")
        return None

def get_current_price(ticker, polygon_client):
    """
    Get current price for a ticker using Polygon aggregates endpoint for today
    """
    try:
        today = dt.now().date()
        date_str = today.strftime("%Y-%m-%d")
        
        # Get today's data
        aggs = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=date_str,
            to=date_str
        )
        
        if aggs and len(aggs) > 0:
            return aggs[0].close
        else:
            # If no data for today, try to get the latest available data
            aggs = polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=(today - timedelta(days=5)).strftime("%Y-%m-%d"),
                to=date_str
            )
            if aggs and len(aggs) > 0:
                return aggs[-1].close
        return None
    except Exception as e:
        print(f"Error fetching current price for {ticker}: {e}")
        return None

def get_gap_up_stocks():
    """
    Get real gap-up stocks using Polygon API
    Returns a list of dictionaries with stock information
    """
    try:
        polygon_client = get_polygon_client()
        print("✅ Polygon API client initialized successfully")
        
        # Get gainers from Polygon
        print("Fetching gainers from Polygon API...")
        tickers = polygon_client.get_snapshot_direction(
            "stocks",
            direction="gainers",
        )
        
        gap_up_stocks = []
        total_tickers = 0
        below_1_count = 0
        cs_type_count = 0
        
        if not tickers or not isinstance(tickers, list):
            print("❌ No tickers returned from Polygon API")
            return []
            
        print(f"✅ Processing {len(tickers)} gainers from Polygon API")
        
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
            try:
                # Get ticker details
                details = polygon_client.get_ticker_details(ticker)
                issue_type = details.type
                
                if issue_type == "CS":  # Common Stock
                    cs_type_count += 1
                    previous_close = get_previous_close_price(ticker, polygon_client)
                    current_price = get_current_price(ticker, polygon_client)
                    
                    if previous_close is not None and previous_close >= 1 and current_price is not None:
                        # Calculate gap percentage
                        gap_percent = ((current_price - previous_close) / previous_close) * 100
                        
                        # Only include stocks with significant gap-up (2% or more)
                        if gap_percent >= 2.0:
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
                            print(f"✅ Gap-up found: {ticker} - {gap_percent:.2f}% gap")
                    else:
                        below_1_count += 1
                        
            except Exception as e:
                print(f"❌ Error processing {ticker}: {e}")
                continue
                
        print(f"📊 Total tickers processed: {total_tickers}")
        print(f"📊 Common stock tickers: {cs_type_count}")
        print(f"📊 Tickers with price < $1: {below_1_count}")
        print(f"✅ Final gap-up stocks found: {len(gap_up_stocks)}")
        
        return gap_up_stocks
        
    except Exception as e:
        print(f"❌ Error in get_gap_up_stocks: {e}")
        return []

def get_stock_analysis(ticker):
    """
    Get detailed analysis for a specific stock
    """
    try:
        polygon_client = get_polygon_client()
        
        # Get current price and previous close
        current_price = get_current_price(ticker, polygon_client)
        previous_close = get_previous_close_price(ticker, polygon_client)
        
        if current_price is None or previous_close is None:
            return None
            
        # Calculate basic metrics
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100
        
        # Get ticker details
        details = polygon_client.get_ticker_details(ticker)
        
        analysis = {
            'ticker': ticker,
            'company_name': details.name,
            'current_price': round(current_price, 2),
            'previous_close': round(previous_close, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'market_cap': getattr(details, 'market_cap', 0),
            'volume': getattr(details, 'share_class_shares_outstanding', 0),
            'sector': getattr(details, 'sic_description', 'Unknown'),
            'list_date': getattr(details, 'list_date', None),
            'analysis': {
                'gap_up': change_percent > 2.0,
                'gap_percent': round(change_percent, 2),
                'strength': 'Strong' if change_percent > 5.0 else 'Moderate' if change_percent > 2.0 else 'Weak'
            }
        }
        
        return analysis
        
    except Exception as e:
        print(f"❌ Error analyzing {ticker}: {e}")
        return None

def get_market_data(ticker):
    """
    Get real-time market data for a ticker
    """
    try:
        polygon_client = get_polygon_client()
        
        # Get current price using aggregates
        current_price = get_current_price(ticker, polygon_client)
        previous_close = get_previous_close_price(ticker, polygon_client)
        
        if current_price is None or previous_close is None:
            return None
            
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100
        
        return {
            'ticker': ticker,
            'price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': 0,  # We don't have volume from aggregates
            'timestamp': dt.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error getting market data for {ticker}: {e}")
        return None

if __name__ == "__main__":
    # Test the functions
    print("🧪 Testing gap-up detection...")
    gap_ups = get_gap_up_stocks()
    print(f"Found {len(gap_ups)} gap-up stocks")
    for stock in gap_ups[:5]:  # Show first 5
        print(f"{stock['ticker']}: {stock['gap_percent']}% gap") 