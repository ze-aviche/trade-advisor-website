#!/usr/bin/env python3
"""
Test script for parallel execution capabilities in historical_ts_data.py
Tests all parallel processing functions with different configurations
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
    fetch_multiple_stocks_parallel_ts,
    fetch_single_day_data_parallel_ts,
    fetch_batch_data_parallel_ts,
    process_gap_ups_parallel_ts,
    fetch_comprehensive_parallel_ts,
    get_historical_gap_up_data_ts,
    get_batch_daily_data_ts,
    process_batch_data_to_gap_ups_ts,
    clear_cache
)

# Load environment variables
load_dotenv()

def get_test_tickers():
    """Get a list of test tickers from the database"""
    print("🔍 Finding test tickers...")
    
    conn = get_timescaledb_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as cursor:
            # Get tickers with recent data
            cursor.execute("""
                SELECT ticker 
                FROM ohlcv_1m 
                WHERE day >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY ticker
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """)
            tickers = [row[0] for row in cursor.fetchall()]
            print(f"📈 Found {len(tickers)} test tickers: {tickers}")
            return tickers
    except Exception as e:
        print(f"❌ Error finding test tickers: {e}")
        return []
    finally:
        conn.close()

def test_parallel_vs_sequential():
    """Compare parallel vs sequential execution performance"""
    print("\n⚡ Testing Parallel vs Sequential Performance")
    print("=" * 50)
    
    tickers = get_test_tickers()
    if len(tickers) < 2:
        print("⚠️ Need at least 2 tickers for comparison test")
        return
    
    # Test with 3 tickers for fair comparison
    test_tickers = tickers[:3]
    days = 7
    
    print(f"📊 Testing with {len(test_tickers)} tickers: {test_tickers}")
    
    # Sequential execution
    print("\n🐌 Sequential execution...")
    start_time = time.time()
    sequential_results = {}
    for ticker in test_tickers:
        try:
            data = get_historical_gap_up_data_ts(ticker, days, use_cache=False)
            sequential_results[ticker] = data
            print(f"  ✅ {ticker}: {len(data) if data else 0} gap-ups")
        except Exception as e:
            print(f"  ❌ {ticker}: Error - {e}")
            sequential_results[ticker] = None
    sequential_time = time.time() - start_time
    
    # Parallel execution
    print(f"\n🚀 Parallel execution (max_workers=3)...")
    start_time = time.time()
    parallel_results = fetch_multiple_stocks_parallel_ts(test_tickers, days, use_cache=False, max_workers=3)
    parallel_time = time.time() - start_time
    
    # Results comparison
    print(f"\n📊 Performance Comparison:")
    print(f"  Sequential time: {sequential_time:.2f} seconds")
    print(f"  Parallel time: {parallel_time:.2f} seconds")
    print(f"  Speedup: {sequential_time/parallel_time:.2f}x faster")
    
    # Data comparison
    print(f"\n📈 Data Comparison:")
    for ticker in test_tickers:
        seq_count = len(sequential_results.get(ticker, [])) if sequential_results.get(ticker) else 0
        par_count = len(parallel_results.get(ticker, [])) if parallel_results.get(ticker) else 0
        print(f"  {ticker}: Sequential={seq_count}, Parallel={par_count}")

def test_different_worker_counts():
    """Test performance with different worker counts"""
    print("\n👥 Testing Different Worker Counts")
    print("=" * 40)
    
    tickers = get_test_tickers()
    if len(tickers) < 4:
        print("⚠️ Need at least 4 tickers for worker count test")
        return
    
    test_tickers = tickers[:4]
    days = 7
    worker_counts = [1, 2, 4, 8]
    
    print(f"📊 Testing with {len(test_tickers)} tickers: {test_tickers}")
    
    results = {}
    for workers in worker_counts:
        print(f"\n🔧 Testing with {workers} workers...")
        start_time = time.time()
        try:
            data = fetch_multiple_stocks_parallel_ts(test_tickers, days, use_cache=False, max_workers=workers)
            duration = time.time() - start_time
            results[workers] = duration
            print(f"  ✅ Completed in {duration:.2f} seconds")
        except Exception as e:
            print(f"  ❌ Error with {workers} workers: {e}")
            results[workers] = None
    
    # Show results
    print(f"\n📊 Worker Count Performance:")
    for workers, duration in results.items():
        if duration:
            print(f"  {workers} workers: {duration:.2f} seconds")
        else:
            print(f"  {workers} workers: Failed")

def test_single_day_parallel():
    """Test parallel single day data fetching"""
    print("\n📅 Testing Parallel Single Day Data Fetch")
    print("=" * 45)
    
    tickers = get_test_tickers()
    if len(tickers) < 3:
        print("⚠️ Need at least 3 tickers for single day test")
        return
    
    test_tickers = tickers[:3]
    test_date = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"📊 Testing single day data for {len(test_tickers)} tickers on {test_date}")
    
    start_time = time.time()
    results = fetch_single_day_data_parallel_ts(test_tickers, test_date, max_workers=3)
    duration = time.time() - start_time
    
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📈 Results:")
    for ticker, data in results.items():
        if data:
            gap = data.get('gap up % at open', 'N/A')
            print(f"  {ticker}: Gap {gap}%, Open ${data.get('open', 'N/A')}")
        else:
            print(f"  {ticker}: No data")

def test_batch_data_parallel():
    """Test parallel batch data fetching"""
    print("\n📦 Testing Parallel Batch Data Fetch")
    print("=" * 40)
    
    tickers = get_test_tickers()
    if len(tickers) < 3:
        print("⚠️ Need at least 3 tickers for batch test")
        return
    
    test_tickers = tickers[:3]
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)
    
    print(f"📊 Testing batch data for {len(test_tickers)} tickers from {start_date} to {end_date}")
    
    start_time = time.time()
    results = fetch_batch_data_parallel_ts(test_tickers, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), max_workers=3)
    duration = time.time() - start_time
    
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📈 Results:")
    for ticker, data in results.items():
        if data:
            print(f"  {ticker}: {len(data)} days of data")
        else:
            print(f"  {ticker}: No data")

def test_comprehensive_parallel():
    """Test comprehensive parallel processing"""
    print("\n🎯 Testing Comprehensive Parallel Processing")
    print("=" * 50)
    
    tickers = get_test_tickers()
    if len(tickers) < 3:
        print("⚠️ Need at least 3 tickers for comprehensive test")
        return
    
    test_tickers = tickers[:3]
    days = 7
    
    print(f"📊 Testing comprehensive processing for {len(test_tickers)} tickers ({days} days)")
    
    start_time = time.time()
    results = fetch_comprehensive_parallel_ts(test_tickers, days, max_workers=3, use_cache=False)
    duration = time.time() - start_time
    
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📈 Results:")
    total_gap_ups = 0
    for ticker, gap_ups in results.items():
        if gap_ups:
            count = len(gap_ups)
            total_gap_ups += count
            print(f"  {ticker}: {count} gap-ups")
        else:
            print(f"  {ticker}: No gap-ups")
    
    print(f"📊 Total gap-ups found: {total_gap_ups}")

def test_memory_efficient_parallel():
    """Test memory-efficient parallel processing with limited workers"""
    print("\n💾 Testing Memory-Efficient Parallel Processing")
    print("=" * 55)
    
    tickers = get_test_tickers()
    if len(tickers) < 2:
        print("⚠️ Need at least 2 tickers for memory test")
        return
    
    test_tickers = tickers[:2]  # Use fewer tickers
    days = 7
    
    print(f"📊 Testing memory-efficient processing with {len(test_tickers)} tickers")
    print("💡 Using max_workers=1 to minimize memory usage")
    
    start_time = time.time()
    results = fetch_multiple_stocks_parallel_ts(test_tickers, days, use_cache=False, max_workers=1)
    duration = time.time() - start_time
    
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📈 Results:")
    for ticker, data in results.items():
        if data:
            print(f"  {ticker}: {len(data)} gap-ups")
        else:
            print(f"  {ticker}: No data")

def main():
    """Main test function"""
    print("🧪 Testing Parallel Execution Capabilities")
    print("=" * 50)
    
    # Clear cache before testing
    print("🗑️ Clearing cache before testing...")
    clear_cache()
    
    # Run all tests
    test_parallel_vs_sequential()
    test_different_worker_counts()
    test_single_day_parallel()
    test_batch_data_parallel()
    test_comprehensive_parallel()
    test_memory_efficient_parallel()
    
    print("\n" + "=" * 50)
    print("🎉 All parallel execution tests completed!")
    print("💡 Check the results above to see performance improvements.")
    print("💡 Use max_workers=1-2 if you encounter memory issues.")

if __name__ == "__main__":
    main()
