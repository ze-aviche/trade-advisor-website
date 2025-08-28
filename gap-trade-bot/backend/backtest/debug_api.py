#!/usr/bin/env python3
"""
Debug script to test Polygon API directly
"""

import requests
import json
from datetime import datetime

def test_polygon_api():
    """Test the Polygon API call directly"""
    
    # Test dates
    test_dates = ["2025-08-26", "2025-08-25", "2025-08-22"]
    
    for date in test_dates:
        print(f"\n🔍 Testing date: {date}")
        
        # Check if it's a weekend
        dt_obj = datetime.strptime(date, "%Y-%m-%d")
        if dt_obj.weekday() >= 5:
            print(f"❌ {date} is a weekend - no market data")
            continue
        
        # Test the API call
        url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true&apiKey=5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
        
        try:
            print(f"📡 Making API call to: {url}")
            response = requests.get(url)
            
            print(f"📊 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API call successful")
                
                # Check for errors in response
                if "error" in data:
                    print(f"❌ API Error: {data['error']}")
                    continue
                
                # Check for results
                results = data.get("results", [])
                print(f"📊 Number of stocks returned: {len(results)}")
                
                if len(results) > 0:
                    print(f"📋 First 3 stocks:")
                    for i, stock in enumerate(results[:3]):
                        ticker = stock["T"]
                        open_price = stock["o"]
                        close_price = stock["c"]
                        volume = stock["v"]
                        print(f"   {i+1}. {ticker}: Open=${open_price}, Close=${close_price}, Volume={volume}")
                    
                    # Look for INHD
                    inhd_found = False
                    for stock in results:
                        if stock["T"] == "INHD":
                            inhd_found = True
                            print(f"\n🎯 INHD found:")
                            print(f"   Ticker: {stock['T']}")
                            print(f"   Open: ${stock['o']}")
                            print(f"   Close: ${stock['c']}")
                            print(f"   Volume: {stock['v']}")
                            break
                    
                    if not inhd_found:
                        print(f"\n❌ INHD not found in results")
                else:
                    print(f"❌ No results returned for {date}")
                    
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

def test_api_key():
    """Test if the API key is valid"""
    print(f"\n🔑 Testing API key validity...")
    
    # Test with a simple endpoint
    url = "https://api.polygon.io/v3/reference/tickers?market=stocks&active=true&limit=5&apiKey=5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
    
    try:
        response = requests.get(url)
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API key is valid")
            print(f"📊 Response: {json.dumps(data, indent=2)[:500]}...")
        else:
            print(f"❌ API key might be invalid")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    print("🧪 Debugging Polygon API")
    print("=" * 50)
    
    # Test API key first
    test_api_key()
    
    # Test specific dates
    test_polygon_api()
    
    print("\n" + "=" * 50)
    print("✅ Debug complete")
