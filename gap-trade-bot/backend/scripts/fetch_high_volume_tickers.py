#!/usr/bin/env python3
"""
Fetch High Volume Tickers Script
Fetches tickers with daily volume > 85M for a date range and stores them in DAILY_GAP_UP_BY_VOL table.
"""

import os
import sys
import sqlite3
import argparse
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import warnings
import urllib3

# Suppress connection pool warnings
warnings.filterwarnings('ignore', message='Connection pool is full')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from polygon import RESTClient
from logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

class HighVolumeTickersFetcher:
    """Fetches tickers with daily volume > 85M for a date range"""
    
    def __init__(self, db_path: str = "gap_ups_history.db"):
        self.db_path = db_path
        self.polygon_client = self._get_polygon_client()
        self.init_database()
    
    def _get_polygon_client(self):
        """Get Polygon API client"""
        print("🔑 Initializing Polygon API client...")
        api_key = os.environ.get('POLYGON_API_KEY')
        if not api_key:
            api_key = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
            print("⚠️ Using default Polygon API key")
            logger.warning("Using default Polygon API key")
        
        if not api_key:
            print("❌ POLYGON_API_KEY environment variable is required")
            raise ValueError("POLYGON_API_KEY environment variable is required")
        
        # Create client with connection pooling configuration
        client = RESTClient(api_key)
        
        # Configure connection pooling to handle concurrent requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Increase connection pool size for better concurrent performance
        import requests
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,  # Number of connection pools
            pool_maxsize=50,      # Maximum connections per pool
            max_retries=3         # Retry failed requests
        )
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        
        # Set the session for the client (if supported)
        if hasattr(client, '_session'):
            client._session = session
        
        print("✅ Polygon API client initialized with connection pooling")
        return client
    
    def init_database(self):
        """Initialize the database with DAILY_GAP_UP_BY_VOL table"""
        try:
            print(f"🗄️ Initializing database: {self.db_path}")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create DAILY_GAP_UP_BY_VOL table
                print("📋 Creating DAILY_GAP_UP_BY_VOL table...")
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS DAILY_GAP_UP_BY_VOL (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        tickers TEXT NOT NULL,  -- JSON array of tickers
                        volume_threshold INTEGER DEFAULT 85000000,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date)
                    )
                ''')
                
                # Create index for faster queries
                print("🔍 Creating database indexes...")
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_gap_up_by_vol_date ON DAILY_GAP_UP_BY_VOL(date)')
                
                conn.commit()
                print(f"✅ Database initialized: {self.db_path}")
                logger.info(f"✅ Database initialized: {self.db_path}")
                
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            logger.error(f"❌ Error initializing database: {e}")
            raise
    
    def get_all_tickers_from_db(self) -> List[str]:
        """Get all tickers from ALL_TICKERS table"""
        try:
            print("📊 Fetching all tickers from database...")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT ticker FROM ALL_TICKERS ORDER BY ticker')
                results = cursor.fetchall()
                tickers = [row[0] for row in results]
                print(f"📊 Found {len(tickers)} tickers in database")
                return tickers
        except Exception as e:
            print(f"❌ Error fetching tickers from database: {e}")
            logger.error(f"❌ Error fetching tickers from database: {e}")
            return []
    
    def check_ticker_volume_for_date(self, ticker: str, date: datetime) -> bool:
        """Check if a ticker has volume > 85M for a specific date"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # Get daily aggregates for the ticker
            daily_data = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=date_str,
                to=date_str,
                adjusted="true"
            )
            
            if not daily_data or len(daily_data) == 0:
                return False
            
            daily = daily_data[0]
            volume = daily.volume if hasattr(daily, 'volume') else 0
            
            return volume > 85_000_000  # 85M threshold
                
        except Exception as e:
            logger.warning(f"⚠️ Error checking volume for {ticker}: {e}")
            return False
    
    def check_ticker_volume_parallel(self, args: tuple) -> tuple:
        """Check ticker volume in parallel (for ThreadPoolExecutor)"""
        ticker, date = args
        
        # Create a thread-local session for better connection handling
        import threading
        import requests
        
        if not hasattr(threading.current_thread(), '_local_session'):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=5,
                pool_maxsize=10,
                max_retries=2
            )
            session.mount('https://', adapter)
            session.mount('http://', adapter)
            threading.current_thread()._local_session = session
        
        result = self.check_ticker_volume_for_date(ticker, date)
        return (ticker, result)
    
    def process_ticker_batch_parallel(self, tickers: List[str], date: datetime, batch_size: int = 50, max_workers: int = 10) -> List[str]:
        """Process a batch of tickers in parallel"""
        qualifying_tickers = []
        total_tickers = len(tickers)
        
        print(f"📊 Processing {total_tickers} tickers in batches of {batch_size} with {max_workers} workers...")
        
        # Process tickers in batches
        for i in range(0, total_tickers, batch_size):
            batch = tickers[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_tickers + batch_size - 1) // batch_size
            
            print(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} tickers)...")
            
            # Create arguments for parallel processing
            args_list = [(ticker, date) for ticker in batch]
            
            # Process batch in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_ticker = {executor.submit(self.check_ticker_volume_parallel, args): args[0] for args in args_list}
                
                # Collect results as they complete
                completed_count = 0
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        ticker, is_qualified = future.result()
                        if is_qualified:
                            qualifying_tickers.append(ticker)
                        
                        completed_count += 1
                        if completed_count % 10 == 0:
                            print(f"    📊 Batch {batch_num}: {completed_count}/{len(batch)} completed...")
                            
                    except Exception as e:
                        print(f"    ⚠️ Error processing {ticker}: {e}")
            
            print(f"    ✅ Batch {batch_num} completed. Found {len(qualifying_tickers)} qualifying tickers so far...")
            
            # Small delay between batches to avoid rate limiting and connection pool issues
            time.sleep(1.0)
        
        return qualifying_tickers
    
    def process_date(self, date: datetime, tickers: List[str], batch_size: int = 50, max_workers: int = 10) -> List[str]:
        """Process a single date and return tickers with volume > 85M using parallel processing"""
        date_str = date.strftime('%Y-%m-%d')
        print(f"📅 Processing date: {date_str}")
        print(f"📊 Checking {len(tickers)} tickers for volume > 85M using parallel processing...")
        
        start_time = time.time()
        qualifying_tickers = self.process_ticker_batch_parallel(tickers, date, batch_size, max_workers)
        end_time = time.time()
        
        print(f"📊 Date {date_str}: Found {len(qualifying_tickers)} tickers with volume > 85M")
        print(f"⏱️ Processing time: {end_time - start_time:.2f} seconds")
        return qualifying_tickers
    
    def store_daily_results(self, date: datetime, tickers: List[str]):
        """Store daily results in DAILY_GAP_UP_BY_VOL table"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            print(f"💾 Storing results for {date_str}...")
            
            # Convert tickers list to JSON string
            tickers_json = json.dumps(tickers)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or replace the record for this date
                cursor.execute('''
                    INSERT OR REPLACE INTO DAILY_GAP_UP_BY_VOL (date, tickers, volume_threshold)
                    VALUES (?, ?, ?)
                ''', (date_str, tickers_json, 85_000_000))
                
                conn.commit()
                print(f"✅ Stored {len(tickers)} tickers for {date_str}")
                
        except Exception as e:
            print(f"❌ Error storing results for {date_str}: {e}")
            logger.error(f"❌ Error storing results for {date_str}: {e}")
            raise
    
    def run_date_range(self, start_date: datetime, end_date: datetime, batch_size: int = 50, max_workers: int = 10):
        """Run the process for a date range with parallel processing"""
        try:
            print(f"🚀 Starting high volume ticker fetch for date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            print(f"⚙️ Configuration: Batch size={batch_size}, Max workers={max_workers}")
            logger.info(f"🚀 Starting high volume ticker fetch for date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Get all tickers from database
            print("📊 Step 1: Fetching all tickers from database...")
            tickers = self.get_all_tickers_from_db()
            
            if not tickers:
                print("⚠️ No tickers found in database")
                logger.warning("⚠️ No tickers found in database")
                return
            
            # Process each date in the range
            current_date = start_date
            total_dates = (end_date - start_date).days + 1
            processed_dates = 0
            total_start_time = time.time()
            
            while current_date <= end_date:
                processed_dates += 1
                print(f"\n📅 Processing date {processed_dates}/{total_dates}: {current_date.strftime('%Y-%m-%d')}")
                
                # Check if it's a weekend (skip weekends)
                if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    print(f"⏭️ Skipping weekend: {current_date.strftime('%Y-%m-%d')}")
                    current_date += timedelta(days=1)
                    continue
                
                # Process the date with parallel processing
                qualifying_tickers = self.process_date(current_date, tickers, batch_size, max_workers)
                
                # Store results
                self.store_daily_results(current_date, qualifying_tickers)
                
                # Move to next date
                current_date += timedelta(days=1)
                
                # Add delay between dates to avoid rate limiting
                time.sleep(1)
            
            total_end_time = time.time()
            print(f"\n✅ Process completed successfully!")
            print(f"📊 Processed {processed_dates} dates")
            print(f"⏱️ Total processing time: {total_end_time - total_start_time:.2f} seconds")
            
        except Exception as e:
            print(f"❌ Error in run_date_range: {e}")
            logger.error(f"❌ Error in run_date_range: {e}")
            raise

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Fetch tickers with daily volume > 85M for a date range')
    parser.add_argument('--start-date', type=str, required=True,
                       help='Start date (YYYY-MM-DD format)')
    parser.add_argument('--end-date', type=str, required=True,
                       help='End date (YYYY-MM-DD format)')
    parser.add_argument('--db-path', type=str, default='gap_ups_history.db',
                       help='Database path (default: gap_ups_history.db)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Batch size for parallel processing (default: 50)')
    parser.add_argument('--max-workers', type=int, default=10,
                       help='Maximum number of parallel workers (default: 10)')
    
    args = parser.parse_args()
    
    print("🎯 Starting High Volume Tickers Fetcher Script")
    print("=" * 60)
    
    # Parse dates
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        print(f"📅 Start date: {args.start_date}")
        print(f"📅 End date: {args.end_date}")
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD")
        logger.error("❌ Invalid date format. Use YYYY-MM-DD")
        return
    
    if start_date > end_date:
        print("❌ Start date must be before end date")
        logger.error("❌ Start date must be before end date")
        return
    
    print(f"💾 Database path: {args.db_path}")
    print(f"⚙️ Batch size: {args.batch_size}")
    print(f"⚙️ Max workers: {args.max_workers}")
    logger.info(f"🎯 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Create fetcher and run
    try:
        print("🔧 Initializing fetcher...")
        fetcher = HighVolumeTickersFetcher(args.db_path)
        print("✅ Fetcher initialized successfully")
        
        print("🚀 Starting main process...")
        fetcher.run_date_range(start_date, end_date, args.batch_size, args.max_workers)
        
        print("=" * 60)
        print("🎉 Script completed successfully!")
        
    except Exception as e:
        print(f"❌ Script failed: {e}")
        logger.error(f"❌ Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 