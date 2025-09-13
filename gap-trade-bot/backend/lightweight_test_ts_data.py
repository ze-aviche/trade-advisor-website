#!/usr/bin/env python3
"""
Lightweight test script for historical_ts_data.py module
Avoids shared memory issues by using minimal database connections
"""
import os
import sys
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_ts_data import (
    get_timescaledb_connection,
    extract_time_from_timestamp,
    get_premarket_high_low_data_ts,
    get_daily_high_low_data_ts,
    get_premarket_volume_ts,
    count_vwap_crosses_ts,
    fetch_single_day_data_ts
)

# Load environment variables
load_dotenv()

def test_basic_connection():
    """Test basic database connection without complex queries"""
    print("🔌 Testing basic TimescaleDB connection...")
    
    conn = get_timescaledb_connection()
    if conn:
        print("✅ Connection successful")
        try:
            with conn.cursor() as cursor:
                # Simple query to test connection
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result:
                    print("✅ Basic query successful")
                else:
                    print("❌ Basic query failed")
        except Exception as e:
            print(f"❌ Query error: {e}")
        finally:
            conn.close()
        return True
    else:
        print("❌ Connection failed")
        return False

def test_timestamp_extraction():
    """Test timestamp extraction function"""
    print("\n🕐 Testing timestamp extraction...")
    
    test_timestamps = [
        "2023-05-02 17:52:00.000 -0500",
        "2023-05-02 03:00:00.000 -0500",
        "2023-05-02 08:30:00.000 -0500",
        "2023-05-02 15:00:00.000 -0500"
    ]
    
    for ts in test_timestamps:
        extracted = extract_time_from_timestamp(ts)
        print(f"  {ts} -> {extracted}")
    
    print("✅ Timestamp extraction test completed")

def find_simple_test_data():
    """Find test data with minimal database impact"""
    print("🔍 Finding test data...")
    
    conn = get_timescaledb_connection()
    if not conn:
        return None, None
    
    try:
        with conn.cursor() as cursor:
            # Very simple query to find any recent data
            cursor.execute("""
                SELECT ticker, day
                FROM ohlcv_1m 
                ORDER BY day DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                ticker, latest_date = result
                print(f"  📈 Test ticker: {ticker}")
                print(f"  📅 Test date: {latest_date}")
                return ticker, latest_date.strftime("%Y-%m-%d")
            else:
                print("  ⚠️ No data found")
                return None, None
                
    except Exception as e:
        print(f"  ❌ Error finding test data: {e}")
        return None, None
    finally:
        conn.close()

def test_core_functions(test_ticker, test_date):
    """Test core functions one by one"""
    print(f"\n🧪 Testing core functions for {test_ticker} on {test_date}...")
    
    # Test 1: Premarket high/low
    print("1. Testing premarket high/low...")
    try:
        high, high_time, low, low_time = get_premarket_high_low_data_ts(test_ticker, test_date)
        if high is not None:
            print(f"   ✅ Premarket High: ${high} at {high_time}")
            print(f"   ✅ Premarket Low: ${low} at {low_time}")
        else:
            print("   ⚠️ No premarket data found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Daily high/low
    print("2. Testing daily high/low...")
    try:
        high, high_time, low, low_time = get_daily_high_low_data_ts(test_ticker, test_date)
        if high is not None:
            print(f"   ✅ Daily High: ${high} at {high_time}")
            print(f"   ✅ Daily Low: ${low} at {low_time}")
        else:
            print("   ⚠️ No daily data found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Premarket volume
    print("3. Testing premarket volume...")
    try:
        volume = get_premarket_volume_ts(test_ticker, test_date)
        if volume > 0:
            print(f"   ✅ Premarket Volume: {volume:,.0f} shares")
        else:
            print("   ⚠️ No premarket volume found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: VWAP crosses
    print("4. Testing VWAP crosses...")
    try:
        crosses = count_vwap_crosses_ts(test_ticker, test_date)
        if crosses is not None:
            print(f"   ✅ VWAP Crosses: {crosses}")
        else:
            print("   ⚠️ No VWAP data found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 5: Single day comprehensive data
    print("5. Testing comprehensive single day data...")
    try:
        data = fetch_single_day_data_ts(test_ticker, test_date)
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
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    """Main test function"""
    print("🧪 Starting lightweight test of historical_ts_data.py")
    print("=" * 50)
    
    # Test basic connection first
    if not test_basic_connection():
        print("❌ Basic connection failed. Exiting tests.")
        return
    
    # Test timestamp extraction (no database needed)
    test_timestamp_extraction()
    
    # Find test data
    test_ticker, test_date = find_simple_test_data()
    if not test_ticker or not test_date:
        print("❌ No test data available. Exiting tests.")
        return
    
    # Test core functions
    test_core_functions(test_ticker, test_date)
    
    print("\n" + "=" * 50)
    print("🎉 Lightweight test completed!")
    print("💡 If you see ⚠️ warnings, they may indicate data gaps or missing data.")
    print("💡 If you see ❌ errors, check your database connection and data availability.")

if __name__ == "__main__":
    main()
