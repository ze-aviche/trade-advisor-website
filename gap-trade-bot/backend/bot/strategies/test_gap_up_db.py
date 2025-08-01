#!/usr/bin/env python3
"""
Test script for gap-up database functionality
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from gap_up_db import GapUpDB
from logging_config import get_logger

logger = get_logger(__name__)

def test_gap_up_database():
    """Test the gap-up database functionality"""
    print("🧪 Testing Gap-Up Database Functionality")
    print("=" * 50)
    
    # Initialize database
    db = GapUpDB()
    
    # Check if database exists
    if not db.check_database_exists():
        print("❌ Database not found or empty!")
        print("Please run fetch_gap_up_history.py first to populate the database.")
        return False
    
    # Get database stats
    stats = db.get_database_stats()
    print("\n📊 Database Statistics:")
    print(f"Total Records: {stats.get('total_records', 0)}")
    print(f"Date Range: {stats.get('date_range', {}).get('min', 'N/A')} to {stats.get('date_range', {}).get('max', 'N/A')}")
    print(f"Unique Dates: {stats.get('unique_dates', 0)}")
    print(f"Unique Tickers: {stats.get('unique_tickers', 0)}")
    print(f"Average Gap %: {stats.get('average_gap_percent', 0):.1f}%")
    
    # Test getting gap-ups for recent dates
    test_dates = [
        datetime.now() - timedelta(days=1),
        datetime.now() - timedelta(days=7),
        datetime.now() - timedelta(days=30)
    ]
    
    print("\n📈 Testing Gap-Up Retrieval:")
    for test_date in test_dates:
        gap_ups = db.get_gap_up_stocks_for_date(test_date)
        print(f"{test_date.strftime('%Y-%m-%d')}: {len(gap_ups)} gap-up stocks")
        
        # Show details for first few stocks
        for i, ticker in enumerate(gap_ups[:3]):
            gap_data = db.get_gap_up_data_for_stock(ticker, test_date)
            if gap_data:
                print(f"  - {ticker}: +{gap_data['gap_percent']:.1f}% (${gap_data['open_price']:.2f})")
    
    print("\n✅ Database test completed successfully!")
    return True

if __name__ == "__main__":
    test_gap_up_database() 