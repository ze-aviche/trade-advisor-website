#!/usr/bin/env python3
"""
Debug script for INHD gap calculation
"""

import os
import sys
from datetime import datetime as dt, timedelta
from polygon import RESTClient
from dotenv import load_dotenv

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

def get_previous_close_price(ticker, polygon_client):
    """Get previous close price"""
    today = dt.now().date()
    last_trading_day = today - timedelta(days=1)
    
    # Skip weekends
    while last_trading_day.weekday() >= 5:
        last_trading_day -= timedelta(days=1)
    
    date_str = last_trading_day.strftime("%Y-%m-%d")
    print(f"🔍 Using last trading day: {date_str} for {ticker}")
    
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
            print(f"✅ Previous close for {ticker}: ${close_price}")
            return close_price
        else:
            print(f"❌ No previous close found for {ticker}")
            return None
    except Exception as e:
        print(f"❌ Error fetching previous close for {ticker}: {e}")
        return None

def get_current_price(ticker, polygon_client):
    """Get current price"""
    try:
        today = dt.now().date()
        date_str = today.strftime("%Y-%m-%d")
        
        print(f"🔍 Getting current price for {ticker} on {date_str}")
        
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
            print(f"✅ Current price for {ticker}: ${current_price} (delayed data)")
            return current_price
        else:
            print(f"❌ No current price data for {ticker}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting current price for {ticker}: {e}")
        return None

def debug_inhd():
    """Debug INHD specifically"""
    print("🔍 Debugging INHD...")
    
    try:
        polygon_client = get_polygon_client()
        
        # Get ticker details
        details = polygon_client.get_ticker_details('INHD')
        print(f"📊 Ticker Details: {details.name} ({details.type})")
        
        # Get previous close
        previous_close = get_previous_close_price('INHD', polygon_client)
        print(f"📊 Previous Close: ${previous_close}")
        
        # Get current price
        current_price = get_current_price('INHD', polygon_client)
        print(f"📊 Current Price: ${current_price}")
        
        if previous_close and current_price:
            gap_percent = ((current_price - previous_close) / previous_close) * 100
            print(f"📊 Gap Percentage: {gap_percent:.2f}%")
            
            if gap_percent > 0:
                print(f"✅ INHD is gapping UP by {gap_percent:.2f}%")
            else:
                print(f"❌ INHD is gapping DOWN by {abs(gap_percent):.2f}%")
        else:
            print(f"⚠️ Could not calculate gap for INHD")
            
    except Exception as e:
        print(f"❌ Error debugging INHD: {e}")

if __name__ == "__main__":
    debug_inhd()
