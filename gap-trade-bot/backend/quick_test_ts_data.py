#!/usr/bin/env python3
"""
Quick test script for historical_ts_data.py module
Focused on testing specific functions with a known ticker and date
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_ts_data import (
    get_timescaledb_connection,
    get_premarket_high_low_data_ts,
    get_daily_high_low_data_ts,
    get_premarket_volume_ts,
    count_vwap_crosses_ts,
    fetch_single_day_data_ts,
    get_historical_gap_up_data_ts
)

# Load environment variables
load_dotenv()

def quick_test():
    """Quick test with a specific ticker and date"""
    
    # You can modify these values for your test
    TEST_TICKER = "AAPL"  # Change this to a ticker you have data for
    TEST_DATE = "2023-05-02"  # Change this to a date you have data for
    
    print(f"🧪 Quick test for {TEST_TICKER} on {TEST_DATE}")
    print("=" * 50)
    
    # Test 1: Database connection
    print("1. Testing database connection...")
    conn = get_timescaledb_connection()
    if conn:
        print("   ✅ Connection successful")
        conn.close()
    else:
        print("   ❌ Connection failed")
        return
    
    # Test 2: Premarket data
    print(f"2. Testing premarket data for {TEST_TICKER}...")
    high, high_time, low, low_time = get_premarket_high_low_data_ts(TEST_TICKER, TEST_DATE)
    if high is not None:
        print(f"   ✅ Premarket High: ${high} at {high_time}")
        print(f"   ✅ Premarket Low: ${low} at {low_time}")
    else:
        print("   ⚠️ No premarket data found")
    
    # Test 3: Daily data
    print(f"3. Testing daily data for {TEST_TICKER}...")
    high, high_time, low, low_time = get_daily_high_low_data_ts(TEST_TICKER, TEST_DATE)
    if high is not None:
        print(f"   ✅ Daily High: ${high} at {high_time}")
        print(f"   ✅ Daily Low: ${low} at {low_time}")
    else:
        print("   ⚠️ No daily data found")
    
    # Test 4: Premarket volume
    print(f"4. Testing premarket volume for {TEST_TICKER}...")
    volume = get_premarket_volume_ts(TEST_TICKER, TEST_DATE)
    if volume > 0:
        print(f"   ✅ Premarket Volume: {volume:,.0f} shares")
    else:
        print("   ⚠️ No premarket volume found")
    
    # Test 5: VWAP crosses
    print(f"5. Testing VWAP crosses for {TEST_TICKER}...")
    crosses = count_vwap_crosses_ts(TEST_TICKER, TEST_DATE)
    if crosses is not None:
        print(f"   ✅ VWAP Crosses: {crosses}")
    else:
        print("   ⚠️ No VWAP data found")
    
    # Test 6: Single day comprehensive data
    print(f"6. Testing comprehensive single day data for {TEST_TICKER}...")
    data = fetch_single_day_data_ts(TEST_TICKER, TEST_DATE)
    if data:
        print("   ✅ Single day data retrieved:")
        print(f"      Gap %: {data.get('gap up % at open', 'N/A')}%")
        print(f"      Open: ${data.get('open', 'N/A')}")
        print(f"      High: ${data.get('day high', 'N/A')}")
        print(f"      Close: ${data.get('close price', 'N/A')}")
        print(f"      Volume: {data.get('total volume', 'N/A'):,}")
        print(f"      Runner/Fader: {data.get('Runner/Fader', 'N/A')}")
    else:
        print("   ⚠️ No single day data found")
    
    # Test 7: Historical gap-up data (last 30 days)
    print(f"7. Testing historical gap-up data for {TEST_TICKER} (last 30 days)...")
    historical_data = get_historical_gap_up_data_ts(TEST_TICKER, 30)
    if historical_data:
        print(f"   ✅ Found {len(historical_data)} gap-up days")
        if historical_data:
            latest_gap = historical_data[0]
            print(f"      Latest gap-up: {latest_gap['date']} - {latest_gap.get('gap up % at open', 'N/A')}%")
    else:
        print("   ⚠️ No historical gap-up data found")
    
    print("\n" + "=" * 50)
    print("🎉 Quick test completed!")

def find_available_data():
    """Find available tickers and dates in the database"""
    print("🔍 Finding available test data...")
    
    conn = get_timescaledb_connection()
    if not conn:
        print("❌ Cannot connect to database")
        return
    
    try:
        with conn.cursor() as cursor:
            # Find tickers with recent data
            cursor.execute("""
                SELECT ticker, MAX(day) as latest_date, COUNT(*) as record_count
                FROM ohlcv_1m 
                WHERE day >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY ticker 
                ORDER BY record_count DESC 
                LIMIT 5
            """)
            results = cursor.fetchall()
            
            if results:
                print("📊 Available tickers with recent data:")
                for ticker, latest_date, count in results:
                    print(f"   {ticker}: {latest_date} ({count:,} records)")
            else:
                print("⚠️ No recent data found")
                
    except Exception as e:
        print(f"❌ Error finding data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("Choose test option:")
    print("1. Quick test with specific ticker/date")
    print("2. Find available data")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        quick_test()
    elif choice == "2":
        find_available_data()
    else:
        print("Invalid choice. Running quick test...")
        quick_test()
