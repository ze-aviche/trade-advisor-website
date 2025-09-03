#!/usr/bin/env python3
"""
Test script to verify TimescaleDB connection and data access for orb_tester.py
"""
import os
import sys
from datetime import datetime, timedelta

# Add the current directory to Python path to import orb_tester
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orb_tester import CFG, get_db_connection, fetch_timescaledb_1min

def test_connection():
    """Test basic database connection"""
    print("Testing TimescaleDB connection...")
    
    conn = get_db_connection(CFG)
    if not conn:
        print("❌ Failed to connect to TimescaleDB")
        return False
    
    print("✅ Successfully connected to TimescaleDB")
    conn.close()
    return True

def test_data_access():
    """Test data access from ohlcv_1m table"""
    print("\nTesting data access from ohlcv_1m table...")
    
    # Test with a recent date and common ticker
    test_date = "2025-01-15"  # Adjust this to a date you have data for
    test_ticker = "AAPL"       # Adjust this to a ticker you have data for
    
    print(f"Fetching data for {test_ticker} on {test_date}...")
    
    df = fetch_timescaledb_1min(test_ticker, test_date, CFG)
    
    if df.empty:
        print(f"❌ No data found for {test_ticker} on {test_date}")
        print("   This might be normal if the ticker/date combination doesn't exist")
        return False
    
    print(f"✅ Successfully fetched {len(df)} rows of data")
    print(f"   Data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Sample data:")
    print(df.head(3).to_string())
    
    return True

def test_table_structure():
    """Test table structure and available data"""
    print("\nTesting table structure...")
    
    conn = get_db_connection(CFG)
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            # Check if ohlcv_1m table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'ohlcv_1m'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("❌ ohlcv_1m table does not exist")
                return False
            
            print("✅ ohlcv_1m table exists")
            
            # Check table structure
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'ohlcv_1m' 
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            print("   Table structure:")
            for col_name, col_type in columns:
                print(f"     {col_name}: {col_type}")
            
            # Check data availability
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_rows,
                    MIN(ts) as earliest_date,
                    MAX(ts) as latest_date,
                    COUNT(DISTINCT ticker) as unique_tickers
                FROM ohlcv_1m;
            """)
            stats = cursor.fetchone()
            
            print(f"   Data statistics:")
            print(f"     Total rows: {stats[0]:,}")
            print(f"     Date range: {stats[1]} to {stats[2]}")
            print(f"     Unique tickers: {stats[3]}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error checking table structure: {e}")
        return False
    finally:
        conn.close()

def main():
    """Run all tests"""
    print("=" * 50)
    print("TimescaleDB Connection Test for ORB Tester")
    print("=" * 50)
    
    # Test 1: Basic connection
    if not test_connection():
        print("\n❌ Connection test failed. Please check your TimescaleDB settings.")
        return
    
    # Test 2: Table structure
    if not test_table_structure():
        print("\n❌ Table structure test failed.")
        return
    
    # Test 3: Data access
    test_data_access()
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("=" * 50)

if __name__ == "__main__":
    main()
