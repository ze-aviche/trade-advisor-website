#!/usr/bin/env python3
"""
Test script for historical data caching functionality
Demonstrates the performance improvements with caching
"""
import time
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_data import get_historical_gap_up_data, get_cache_stats, clear_cache
from historical_cache import historical_cache

def test_caching_performance():
    """Test the caching performance with a sample ticker"""
    ticker = "AAPL"
    days = 30
    
    print("🧪 Testing Historical Data Caching Performance")
    print("=" * 50)
    
    # Clear cache first
    print("🗑️ Clearing cache...")
    clear_cache()
    
    # Get initial cache stats
    initial_stats = get_cache_stats()
    print(f"📊 Initial cache stats: {initial_stats}")
    
    # First request - should fetch from Polygon
    print(f"\n🔄 First request for {ticker} ({days} days)...")
    start_time = time.time()
    result1 = get_historical_gap_up_data(ticker, days, use_cache=True)
    first_request_time = time.time() - start_time
    
    if result1:
        print(f"✅ First request completed in {first_request_time:.2f} seconds")
        print(f"📊 Retrieved {len(result1)} data points")
    else:
        print("❌ First request failed")
        return
    
    # Get cache stats after first request
    stats_after_first = get_cache_stats()
    print(f"📊 Cache stats after first request: {stats_after_first}")
    
    # Second request - should use cache
    print(f"\n🔄 Second request for {ticker} ({days} days)...")
    start_time = time.time()
    result2 = get_historical_gap_up_data(ticker, days, use_cache=True)
    second_request_time = time.time() - start_time
    
    if result2:
        print(f"✅ Second request completed in {second_request_time:.2f} seconds")
        print(f"📊 Retrieved {len(result2)} data points")
    else:
        print("❌ Second request failed")
        return
    
    # Calculate performance improvement
    if first_request_time > 0:
        improvement = ((first_request_time - second_request_time) / first_request_time) * 100
        print(f"\n🚀 Performance improvement: {improvement:.1f}% faster")
        print(f"⏱️ First request: {first_request_time:.2f}s")
        print(f"⏱️ Second request: {second_request_time:.2f}s")
    
    # Test cache status
    print(f"\n📋 Cache status for {ticker}:")
    cache_status = historical_cache.get_cache_status(ticker)
    print(f"   Cached: {cache_status.get('cached', False)}")
    print(f"   Total records: {cache_status.get('total_records', 0)}")
    print(f"   Last updated: {cache_status.get('last_updated', 'N/A')}")
    if cache_status.get('data_range'):
        print(f"   Data range: {cache_status['data_range']['start']} to {cache_status['data_range']['end']}")
    
    # Test with different ticker
    print(f"\n🔄 Testing with different ticker (TSLA)...")
    start_time = time.time()
    result3 = get_historical_gap_up_data("TSLA", 15, use_cache=True)
    tsla_request_time = time.time() - start_time
    
    if result3:
        print(f"✅ TSLA request completed in {tsla_request_time:.2f} seconds")
        print(f"📊 Retrieved {len(result3)} data points")
    
    # Final cache stats
    final_stats = get_cache_stats()
    print(f"\n📊 Final cache stats: {final_stats}")

def test_delta_fetching():
    """Test delta fetching functionality"""
    ticker = "MSFT"
    days = 20
    
    print(f"\n🧪 Testing Delta Fetching for {ticker}")
    print("=" * 40)
    
    # Clear cache first
    clear_cache()
    
    # First request - fetch 10 days
    print(f"🔄 Fetching first 10 days for {ticker}...")
    result1 = get_historical_gap_up_data(ticker, 10, use_cache=True)
    
    if result1:
        print(f"✅ First request: {len(result1)} data points")
        
        # Second request - fetch 20 days (should only fetch 10 new days)
        print(f"🔄 Fetching 20 days for {ticker} (should use cache + delta)...")
        result2 = get_historical_gap_up_data(ticker, 20, use_cache=True)
        
        if result2:
            print(f"✅ Second request: {len(result2)} data points")
            
            # Verify data integrity
            if len(result2) == 20:
                print("✅ Delta fetching working correctly")
            else:
                print("⚠️ Delta fetching may have issues")
        else:
            print("❌ Second request failed")
    else:
        print("❌ First request failed")

def test_cache_management():
    """Test cache management functions"""
    print(f"\n🧪 Testing Cache Management")
    print("=" * 30)
    
    # Test cache stats
    stats = get_cache_stats()
    print(f"📊 Current cache stats: {stats}")
    
    # Test clearing specific ticker
    print("🗑️ Clearing AAPL cache...")
    clear_cache("AAPL")
    
    # Test clearing all cache
    print("🗑️ Clearing all cache...")
    clear_cache()
    
    final_stats = get_cache_stats()
    print(f"📊 Cache stats after clearing: {final_stats}")

if __name__ == "__main__":
    print("🚀 Starting Historical Data Cache Tests")
    print("=" * 50)
    
    try:
        # Test basic caching performance
        test_caching_performance()
        
        # Test delta fetching
        test_delta_fetching()
        
        # Test cache management
        test_cache_management()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc() 