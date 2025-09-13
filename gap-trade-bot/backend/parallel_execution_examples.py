#!/usr/bin/env python3
"""
Examples of how to use parallel execution functions in historical_ts_data.py
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_ts_data import (
    fetch_multiple_stocks_parallel_ts,
    fetch_single_day_data_parallel_ts,
    fetch_batch_data_parallel_ts,
    process_gap_ups_parallel_ts,
    fetch_comprehensive_parallel_ts
)

# Load environment variables
load_dotenv()

def example_1_basic_parallel_processing():
    """Example 1: Basic parallel processing for multiple tickers"""
    print("📊 Example 1: Basic Parallel Processing")
    print("-" * 40)
    
    # List of tickers to process
    tickers = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
    
    # Fetch historical gap-up data for all tickers in parallel
    results = fetch_multiple_stocks_parallel_ts(
        tickers=tickers,
        days=30,           # Last 30 days
        use_cache=True,    # Use caching
        max_workers=5      # Use 5 parallel workers
    )
    
    # Process results
    for ticker, gap_ups in results.items():
        if gap_ups:
            print(f"✅ {ticker}: Found {len(gap_ups)} gap-up days")
            # Show the most recent gap-up
            if gap_ups:
                latest = gap_ups[0]
                print(f"   Latest: {latest['date']} - {latest['gap up % at open']}% gap")
        else:
            print(f"⚠️ {ticker}: No gap-up data found")

def example_2_single_day_analysis():
    """Example 2: Analyze a specific date across multiple tickers"""
    print("\n📅 Example 2: Single Day Analysis")
    print("-" * 35)
    
    # List of tickers to analyze
    tickers = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
    
    # Specific date to analyze (yesterday)
    target_date = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Fetch single day data for all tickers in parallel
    results = fetch_single_day_data_parallel_ts(
        tickers=tickers,
        date_str=target_date,
        max_workers=10  # Can use more workers for single day data
    )
    
    # Process results
    print(f"📊 Analysis for {target_date}:")
    for ticker, data in results.items():
        if data:
            gap = data.get('gap up % at open', 0)
            if gap and gap > 0:
                print(f"🚀 {ticker}: {gap}% gap up - {data['Runner/Fader']}")
            else:
                print(f"📉 {ticker}: {gap}% gap - {data['Runner/Fader']}")
        else:
            print(f"❌ {ticker}: No data available")

def example_3_batch_data_processing():
    """Example 3: Batch data processing for large date ranges"""
    print("\n📦 Example 3: Batch Data Processing")
    print("-" * 40)
    
    # List of tickers
    tickers = ["AAPL", "TSLA", "MSFT"]
    
    # Date range (last 90 days)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)
    
    # Fetch batch data in parallel
    batch_results = fetch_batch_data_parallel_ts(
        tickers=tickers,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        max_workers=3
    )
    
    # Process batch data for gap-ups
    gap_up_results = process_gap_ups_parallel_ts(
        ticker_batch_data=batch_results,
        max_workers=3
    )
    
    # Show results
    print(f"📊 Gap-up analysis for {start_date} to {end_date}:")
    for ticker, gap_ups in gap_up_results.items():
        if gap_ups:
            print(f"🚀 {ticker}: {len(gap_ups)} gap-up days")
            # Show top 3 gap-ups
            for i, gap_up in enumerate(gap_ups[:3]):
                print(f"   {i+1}. {gap_up['date']}: {gap_up['gap up % at open']}% gap")
        else:
            print(f"📉 {ticker}: No gap-ups found")

def example_4_comprehensive_processing():
    """Example 4: Comprehensive parallel processing (most efficient)"""
    print("\n🎯 Example 4: Comprehensive Parallel Processing")
    print("-" * 50)
    
    # List of tickers
    tickers = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX"]
    
    # Comprehensive processing (fetches batch data + processes gap-ups)
    results = fetch_comprehensive_parallel_ts(
        tickers=tickers,
        days=60,           # Last 60 days
        max_workers=5,     # 5 parallel workers
        use_cache=True     # Use caching
    )
    
    # Analyze results
    total_gap_ups = 0
    top_gappers = []
    
    for ticker, gap_ups in results.items():
        if gap_ups:
            count = len(gap_ups)
            total_gap_ups += count
            
            # Find the biggest gap-up for this ticker
            biggest_gap = max(gap_ups, key=lambda x: x['gap up % at open'] or 0)
            top_gappers.append((ticker, biggest_gap))
    
    # Sort by gap percentage
    top_gappers.sort(key=lambda x: x[1]['gap up % at open'] or 0, reverse=True)
    
    print(f"📊 Summary: {total_gap_ups} total gap-ups found across {len(tickers)} tickers")
    print(f"🏆 Top 5 biggest gap-ups:")
    for i, (ticker, gap_up) in enumerate(top_gappers[:5]):
        print(f"   {i+1}. {ticker} on {gap_up['date']}: {gap_up['gap up % at open']}% gap")

def example_5_memory_efficient_processing():
    """Example 5: Memory-efficient processing for large datasets"""
    print("\n💾 Example 5: Memory-Efficient Processing")
    print("-" * 45)
    
    # Large list of tickers
    tickers = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX", "AMD", "INTC"]
    
    # Use fewer workers to reduce memory usage
    results = fetch_multiple_stocks_parallel_ts(
        tickers=tickers,
        days=30,
        use_cache=True,
        max_workers=2  # Reduced workers for memory efficiency
    )
    
    # Process results efficiently
    gap_up_summary = {}
    for ticker, gap_ups in results.items():
        if gap_ups:
            gap_up_summary[ticker] = len(gap_ups)
        else:
            gap_up_summary[ticker] = 0
    
    # Show summary
    print(f"📊 Gap-up summary for {len(tickers)} tickers:")
    for ticker, count in sorted(gap_up_summary.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"🚀 {ticker}: {count} gap-ups")
        else:
            print(f"📉 {ticker}: No gap-ups")

def example_6_custom_worker_configuration():
    """Example 6: Custom worker configuration based on system resources"""
    print("\n⚙️ Example 6: Custom Worker Configuration")
    print("-" * 45)
    
    import os
    
    # Determine optimal worker count based on system
    cpu_count = os.cpu_count() or 4
    optimal_workers = min(cpu_count, 8)  # Cap at 8 workers
    
    print(f"🖥️ System CPU count: {cpu_count}")
    print(f"⚙️ Optimal workers: {optimal_workers}")
    
    tickers = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
    
    # Use system-optimized worker count
    results = fetch_multiple_stocks_parallel_ts(
        tickers=tickers,
        days=30,
        use_cache=True,
        max_workers=optimal_workers
    )
    
    print(f"📊 Processed {len(tickers)} tickers with {optimal_workers} workers")
    for ticker, gap_ups in results.items():
        if gap_ups:
            print(f"✅ {ticker}: {len(gap_ups)} gap-ups")
        else:
            print(f"⚠️ {ticker}: No gap-ups")

def main():
    """Run all examples"""
    print("🚀 Parallel Execution Examples for historical_ts_data.py")
    print("=" * 60)
    
    try:
        example_1_basic_parallel_processing()
        example_2_single_day_analysis()
        example_3_batch_data_processing()
        example_4_comprehensive_processing()
        example_5_memory_efficient_processing()
        example_6_custom_worker_configuration()
        
        print("\n" + "=" * 60)
        print("🎉 All examples completed!")
        print("💡 Use these patterns in your own code for efficient parallel processing.")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        print("💡 Make sure your database is running and accessible.")

if __name__ == "__main__":
    main()
