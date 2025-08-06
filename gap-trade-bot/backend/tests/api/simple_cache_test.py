#!/usr/bin/env python3
"""
Simple test for the caching system
"""
import time
from historical_data import get_historical_gap_up_data, get_cache_stats, clear_cache

def simple_test():
    """Simple test of the caching system"""
    print("🧪 Simple Cache Test")
    print("=" * 30)
    
    # Clear cache first
    clear_cache()
    
    # Test with a small dataset
    ticker = "AAPL"
    days = 5
    
    print(f"🔄 First request for {ticker} ({days} days)...")
    start_time = time.time()
    result1 = get_historical_gap_up_data(ticker, days, use_cache=True)
    first_time = time.time() - start_time
    
    if result1:
        print(f"✅ First request: {len(result1)} records in {first_time:.2f}s")
        
        # Second request - should be faster
        print(f"🔄 Second request for {ticker} ({days} days)...")
        start_time = time.time()
        result2 = get_historical_gap_up_data(ticker, days, use_cache=True)
        second_time = time.time() - start_time
        
        if result2:
            print(f"✅ Second request: {len(result2)} records in {second_time:.2f}s")
            
            # Calculate improvement
            if first_time > 0:
                improvement = ((first_time - second_time) / first_time) * 100
                print(f"🚀 Performance improvement: {improvement:.1f}%")
        
        # Show cache stats
        stats = get_cache_stats()
        print(f"📊 Cache stats: {stats}")
        
        # Test cache status
        from historical_cache import historical_cache
        status = historical_cache.get_cache_status(ticker)
        print(f"📋 Cache status for {ticker}:")
        print(f"   Cached: {status.get('cached', False)}")
        print(f"   Records: {status.get('total_records', 0)}")
        print(f"   Last Updated: {status.get('last_updated', 'N/A')}")
        
    else:
        print("❌ Test failed - no data retrieved")

if __name__ == "__main__":
    simple_test() 