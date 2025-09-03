#!/usr/bin/env python3
"""
Script to check the actual structure of the ohlcv_1m table
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection settings - update these with your actual credentials
DB_CONFIG = {
    'host': os.getenv("TIMESCALEDB_HOST", "localhost"),
    'port': int(os.getenv("TIMESCALEDB_PORT", "5432")),
    'database': os.getenv("TIMESCALEDB_NAME", "marketdata"),
    'user': os.getenv("TIMESCALEDB_USER", "ts_user"),
    'password': os.getenv("TIMESCALEDB_PASSWORD", "ts_pass")
}

def check_table_structure():
    """Check the actual structure of the ohlcv_1m table"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Connected to TimescaleDB successfully!")
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'ohlcv_1m'
                );
            """)
            table_exists = cursor.fetchone()['exists']
            
            if not table_exists:
                print("❌ Table 'ohlcv_1m' does not exist!")
                return
            
            print("✅ Table 'ohlcv_1m' exists")
            
            # Get table structure
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'ohlcv_1m' 
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            print("\n📋 Table structure:")
            print(f"{'Column Name':<20} {'Data Type':<20} {'Nullable':<10}")
            print("-" * 50)
            for col in columns:
                print(f"{col['column_name']:<20} {col['data_type']:<20} {col['is_nullable']:<10}")
            
            # Check sample data
            cursor.execute("""
                SELECT * FROM ohlcv_1m 
                LIMIT 3;
            """)
            sample_data = cursor.fetchall()
            
            if sample_data:
                print(f"\n📊 Sample data (first 3 rows):")
                for i, row in enumerate(sample_data):
                    print(f"Row {i+1}: {dict(row)}")
            else:
                print("\n❌ No data found in table")
            
            # Check data statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_rows,
                    MIN(time) as earliest_time,
                    MAX(time) as latest_time,
                    COUNT(DISTINCT ticker) as unique_tickers
                FROM ohlcv_1m;
            """)
            stats = cursor.fetchone()
            
            print(f"\n📈 Data statistics:")
            print(f"Total rows: {stats['total_rows']:,}")
            print(f"Time range: {stats['earliest_time']} to {stats['latest_time']}")
            print(f"Unique tickers: {stats['unique_tickers']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🔍 Checking ohlcv_1m table structure...")
    check_table_structure()
