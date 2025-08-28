#!/usr/bin/env python3
"""
Debug why specific dates have no data
"""

import sys
import os
sys.path.append('.')

from get_gappers import get_grouped_bars
import requests

def debug_date(date_str):
    """Debug a specific date"""
    print(f"\n🔍 Debugging {date_str}...")
    
    # Check if it's a weekend
    from datetime import datetime
    dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt_obj.strftime("%A")
    is_weekend = dt_obj.weekday() >= 5
    
    print(f"📅 {date_str}: {day_name} {'(Weekend)' if is_weekend else '(Weekday)'}")
    
    # Test the API call directly
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date_str}?adjusted=true&apiKey=5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
    
    try:
        print(f"📡 Making API call...")
        response = requests.get(url)
        
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for errors
            if "error" in data:
                print(f"❌ API Error: {data['error']}")
                return
            
            # Check results
            results = data.get("results", [])
            print(f"📊 Number of stocks returned: {len(results)}")
            
            if len(results) > 0:
                print(f"✅ Data available for {date_str}")
                print(f"📋 First 3 stocks:")
                for i, stock in enumerate(results[:3]):
                    ticker = stock["T"]
                    open_price = stock["o"]
                    close_price = stock["c"]
                    volume = stock["v"]
                    print(f"   {i+1}. {ticker}: Open=${open_price}, Close=${close_price}, Volume={volume}")
            else:
                print(f"❌ No data returned for {date_str}")
                
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    # Debug the problematic dates
    debug_date("2025-08-25")
    debug_date("2025-08-28")
