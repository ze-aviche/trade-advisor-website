#!/usr/bin/env python3
"""
Test script for historical_ts_data.py module
Tests all functions with TimescaleDB data to ensure proper functionality
"""
import os
import sys
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the backend directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_ts_data import (
    get_timescaledb_connection,
    extract_time_from_timestamp,
    try_premarket_time_ranges,
    count_vwap_crosses_ts,
    get_premarket_high_low_data_ts,
    get_daily_high_low_data_ts,
    get_premarket_volume_ts,
    fetch_single_day_data_ts,
    get_batch_daily_data_ts,
    process_batch_data_to_gap_ups_ts,
    get_historical_gap_up_data_ts,
    fetch_multiple_stocks_parallel_ts,
    get_cache_stats,
    clear_cache
)

# Load environment variables
load_dotenv()

def test_database_connection():
    """Test TimescaleDB connection"""
    print("🔌 Testing TimescaleDB connection...")
    
    conn = get_timescaledb_connection()
    if conn:
        print("✅ TimescaleDB connection successful")
        
        # Test a simple query to verify data exists
        try:
            with conn.cursor() as cursor:
                # Use a simpler query to avoid memory issues
                cursor.execute("SELECT COUNT(*) FROM ohlcv_1m")
                count = cursor.fetchone()[0]
                print(f"📊 Total records in ohlcv_1m: {count:,}")
                
                # Get sample tickers with a more efficient query
                cursor.execute("SELECT ticker FROM ohlcv_1m GROUP BY ticker LIMIT 5")
                tickers = [row[0] for row in cursor.fetchall()]
                print(f"📈 Sample tickers: {tickers}")
                
                # Get date range with a more efficient query
                cursor.execute("SELECT MIN(day), MAX(day) FROM ohlcv_1m")
                min_date, max_date = cursor.fetchone()
                print(f"📅 Date range: {min_date} to {max_date}")
                
        except Exception as e:
            print(f"❌ Error testing database: {e}")
            print("💡 This might be due to shared memory limits. Try:")
            print("   1. Restart PostgreSQL/TimescaleDB")
            print("   2. Increase max_locks_per_transaction in postgresql.conf")
            print("   3. Reduce concurrent connections")
        finally:
            conn.close()
    else:
        print("❌ TimescaleDB connection failed")
        return False
    
    return True

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

def test_premarket_data(test_ticker, test_date):
    """Test premarket data functions"""
    print(f"\n🌅 Testing premarket data for {test_ticker} on {test_date}...")
    
    # Test premarket high/low
    print("  Testing premarket high/low data...")
    start_time = time.time()
    high, high_time, low, low_time = get_premarket_high_low_data_ts(test_ticker, test_date)
    duration = time.time() - start_time
    
    if high is not None:
        print(f"  ✅ Premarket High: ${high} at {high_time} (took {duration:.2f}s)")
        print(f"  ✅ Premarket Low: ${low} at {low_time}")
    else:
        print(f"  ⚠️ No premarket high/low data found (took {duration:.2f}s)")
    
    # Test premarket volume
    print("  Testing premarket volume...")
    start_time = time.time()
    volume = get_premarket_volume_ts(test_ticker, test_date)
    duration = time.time() - start_time
    
    if volume > 0:
        print(f"  ✅ Premarket Volume: {volume:,.0f} shares (took {duration:.2f}s)")
    else:
        print(f"  ⚠️ No premarket volume data found (took {duration:.2f}s)")

def test_daily_data(test_ticker, test_date):
    """Test daily data functions"""
    print(f"\n📊 Testing daily data for {test_ticker} on {test_date}...")
    
    # Test daily high/low
    print("  Testing daily high/low data...")
    start_time = time.time()
    high, high_time, low, low_time = get_daily_high_low_data_ts(test_ticker, test_date)
    duration = time.time() - start_time
    
    if high is not None:
        print(f"  ✅ Daily High: ${high} at {high_time} (took {duration:.2f}s)")
        print(f"  ✅ Daily Low: ${low} at {low_time}")
    else:
        print(f"  ⚠️ No daily high/low data found (took {duration:.2f}s)")
    
    # Test VWAP crosses
    print("  Testing VWAP crosses...")
    start_time = time.time()
    crosses = count_vwap_crosses_ts(test_ticker, test_date)
    duration = time.time() - start_time
    
    if crosses is not None:
        print(f"  ✅ VWAP Crosses: {crosses} (took {duration:.2f}s)")
    else:
        print(f"  ⚠️ No VWAP data found (took {duration:.2f}s)")

def test_single_day_data(test_ticker, test_date):
    """Test comprehensive single day data"""
    print(f"\n📈 Testing comprehensive single day data for {test_ticker} on {test_date}...")
    
    start_time = time.time()
    data = fetch_single_day_data_ts(test_ticker, test_date)
    duration = time.time() - start_time
    
    if data:
        print(f"  ✅ Single day data retrieved (took {duration:.2f}s)")
        print(f"  📊 Data points:")
        for key, value in data.items():
            if value is not None:
                print(f"    {key}: {value}")
            else:
                print(f"    {key}: None")
    else:
        print(f"  ⚠️ No single day data found (took {duration:.2f}s)")

def test_batch_data(test_ticker, days=7):
    """Test batch data retrieval"""
    print(f"\n📦 Testing batch data for {test_ticker} (last {days} days)...")
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    start_time = time.time()
    batch_data = get_batch_daily_data_ts(test_ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    duration = time.time() - start_time
    
    if batch_data:
        print(f"  ✅ Batch data retrieved: {len(batch_data)} days (took {duration:.2f}s)")
        print(f"  📊 Sample data points:")
        for i, data in enumerate(batch_data[:3]):  # Show first 3 days
            print(f"    Day {i+1}: {data['date']} - O:{data['open']} H:{data['high']} L:{data['low']} C:{data['close']} V:{data['volume']:,}")
    else:
        print(f"  ⚠️ No batch data found (took {duration:.2f}s)")

def test_gap_up_processing(test_ticker, days=30):
    """Test gap-up processing"""
    print(f"\n🚀 Testing gap-up processing for {test_ticker} (last {days} days)...")
    
    # First get batch data
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    batch_data = get_batch_daily_data_ts(test_ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    
    if batch_data:
        print(f"  📦 Retrieved {len(batch_data)} days of batch data")
        
        # Process for gap-ups
        start_time = time.time()
        gap_ups = process_batch_data_to_gap_ups_ts(test_ticker, batch_data)
        duration = time.time() - start_time
        
        if gap_ups:
            print(f"  ✅ Found {len(gap_ups)} gap-up days (25%+) (took {duration:.2f}s)")
            for gap_up in gap_ups[:3]:  # Show first 3 gap-ups
                print(f"    📈 {gap_up['date']}: Gap {gap_up['gap up % at open']}% - {gap_up['Runner/Fader']}")
        else:
            print(f"  ⚠️ No gap-up days found (took {duration:.2f}s)")
    else:
        print(f"  ❌ No batch data available for gap-up processing")

def test_historical_gap_up_data(test_ticker, days=30):
    """Test main historical gap-up data function"""
    print(f"\n📊 Testing historical gap-up data for {test_ticker} (last {days} days)...")
    
    start_time = time.time()
    historical_data = get_historical_gap_up_data_ts(test_ticker, days, use_cache=True)
    duration = time.time() - start_time
    
    if historical_data:
        print(f"  ✅ Retrieved {len(historical_data)} gap-up days (took {duration:.2f}s)")
        print(f"  📊 Sample gap-up data:")
        for i, data in enumerate(historical_data[:2]):  # Show first 2 gap-ups
            print(f"    Gap-up {i+1}:")
            print(f"      Date: {data['date']}")
            print(f"      Gap: {data['gap up % at open']}%")
            print(f"      Premarket High: ${data['premarket high']} at {data['premarket high time']}")
            print(f"      Daily High: ${data['day high']} at {data['day high time']}")
            print(f"      VWAP Crosses: {data['VWAP Crosses']}")
            print(f"      Runner/Fader: {data['Runner/Fader']}")
    else:
        print(f"  ⚠️ No historical gap-up data found (took {duration:.2f}s)")

def test_parallel_processing(test_tickers, days=7):
    """Test parallel processing for multiple tickers"""
    print(f"\n🚀 Testing parallel processing for {len(test_tickers)} tickers...")
    
    start_time = time.time()
    results = fetch_multiple_stocks_parallel_ts(test_tickers, days, use_cache=True)
    duration = time.time() - start_time
    
    print(f"  ✅ Parallel processing completed (took {duration:.2f}s)")
    
    for ticker, data in results.items():
        if data:
            print(f"    {ticker}: {len(data)} gap-up days")
        else:
            print(f"    {ticker}: No data")

def test_cache_functionality():
    """Test cache functionality"""
    print(f"\n💾 Testing cache functionality...")
    
    # Get initial cache stats
    stats = get_cache_stats()
    print(f"  📊 Initial cache stats: {stats}")
    
    # Test cache clearing
    clear_cache()
    print("  🗑️ Cache cleared")
    
    # Get cache stats after clearing
    stats_after = get_cache_stats()
    print(f"  📊 Cache stats after clearing: {stats_after}")

def get_test_data():
    """Get test data from database"""
    print("🔍 Finding test data...")
    
    conn = get_timescaledb_connection()
    if not conn:
        return None, None
    
    try:
        with conn.cursor() as cursor:
            # Use a simpler query to avoid memory issues
            cursor.execute("""
                SELECT ticker, day
                FROM ohlcv_1m 
                WHERE day >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY day DESC, ticker
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                ticker, latest_date = result
                print(f"  📈 Test ticker: {ticker}")
                print(f"  📅 Latest date: {latest_date}")
                return ticker, latest_date.strftime("%Y-%m-%d")
            else:
                print("  ⚠️ No recent data found")
                return None, None
                
    except Exception as e:
        print(f"  ❌ Error finding test data: {e}")
        return None, None
    finally:
        conn.close()

def main():
    """Main test function"""
    print("🧪 Starting comprehensive test of historical_ts_data.py")
    print("=" * 60)
    
    # Test database connection first
    if not test_database_connection():
        print("❌ Database connection failed. Exiting tests.")
        return
    
    # Get test data
    test_ticker, test_date = get_test_data()
    if not test_ticker or not test_date:
        print("❌ No test data available. Exiting tests.")
        return
    
    # Run all tests
    test_timestamp_extraction()
    test_premarket_data(test_ticker, test_date)
    test_daily_data(test_ticker, test_date)
    test_single_day_data(test_ticker, test_date)
    test_batch_data(test_ticker, days=7)
    test_gap_up_processing(test_ticker, days=30)
    test_historical_gap_up_data(test_ticker, days=30)
    
    # Test with multiple tickers if we can find them (skip if memory issues)
    try:
        conn = get_timescaledb_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT ticker 
                        FROM ohlcv_1m 
                        WHERE day >= CURRENT_DATE - INTERVAL '7 days'
                        GROUP BY ticker
                        LIMIT 2
                    """)
                    test_tickers = [row[0] for row in cursor.fetchall()]
                    if len(test_tickers) > 1:
                        test_parallel_processing(test_tickers, days=7)
                    else:
                        print("⚠️ Not enough tickers for parallel processing test")
            except Exception as e:
                print(f"⚠️ Could not test parallel processing: {e}")
            finally:
                conn.close()
    except Exception as e:
        print(f"⚠️ Skipping parallel processing test due to connection issues: {e}")
    
    test_cache_functionality()
    
    print("\n" + "=" * 60)
    print("🎉 All tests completed!")
    print("📊 Check the output above for any errors or warnings.")
    print("💡 If you see ⚠️ warnings, they may indicate data gaps or missing data for certain time periods.")

if __name__ == "__main__":
    main()
