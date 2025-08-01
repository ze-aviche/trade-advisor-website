#!/usr/bin/env python3
"""
Historical Gap-Up Data Fetcher
Fetches all gap-up stocks (25% or more) for each day in the last three years
by using Polygon's gainers API and scanning for actual gap-ups.
"""
import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import time
import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from polygon import RESTClient
from logging_config import get_logger

logger = get_logger(__name__)

class GapUpHistoryFetcher:
    """Fetches and stores historical gap-up data using real gap-up detection"""
    
    def __init__(self, db_path: str = "gap_up_history.db"):
        self.db_path = db_path
        self.polygon_client = self._get_polygon_client()
        self.init_database()
    
    def _get_polygon_client(self):
        """Get Polygon API client"""
        api_key = os.environ.get('POLYGON_API_KEY')
        if not api_key:
            api_key = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
            logger.warning("Using default Polygon API key")
        
        if not api_key:
            raise ValueError("POLYGON_API_KEY environment variable is required")
        
        return RESTClient(api_key)
    
    def init_database(self):
        """Initialize the database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create ALL_TICKERS table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ALL_TICKERS (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT UNIQUE NOT NULL,
                        market_cap REAL,
                        sector TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create DAILY_GAP_UPS table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS DAILY_GAP_UPS (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        prev_close REAL NOT NULL,
                        open_price REAL NOT NULL,
                        gap_percent REAL NOT NULL,
                        volume INTEGER,
                        market_cap REAL,
                        sector TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date, ticker)
                    )
                ''')
                
                # Create indexes for faster queries
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_tickers_ticker ON ALL_TICKERS(ticker)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_gap_ups_date ON DAILY_GAP_UPS(date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_gap_ups_ticker ON DAILY_GAP_UPS(ticker)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_gap_ups_gap ON DAILY_GAP_UPS(gap_percent)')
                
                conn.commit()
                logger.info(f"✅ Database initialized: {self.db_path}")
                
        except Exception as e:
            logger.error(f"❌ Error initializing database: {e}")
            raise
    
    def check_gap_up_for_ticker_parallel(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        """Check if a ticker had a gap-up on a specific date (for parallel processing)"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            prev_date = date - timedelta(days=1)
            prev_date_str = prev_date.strftime('%Y-%m-%d')
            
            # Get previous day's close
            try:
                prev_daily = self.polygon_client.get_daily_open_close_agg(
                    ticker=ticker, date=prev_date_str
                )
                prev_close = prev_daily.close
            except Exception as e:
                return None
            
            # Get current day's open
            try:
                daily_data = self.polygon_client.get_daily_open_close_agg(
                    ticker=ticker, date=date_str
                )
                open_price = daily_data.open
            except Exception as e:
                return None
            
            # Calculate gap percentage
            gap_percent = ((open_price - prev_close) / prev_close) * 100
            
            # Get additional data
            try:
                ticker_details = self.polygon_client.get_ticker_details(ticker)
                volume = getattr(ticker_details, 'share_class_shares_outstanding', 0)
                market_cap = getattr(ticker_details, 'market_cap', 0)
                sector = getattr(ticker_details, 'sic_description', 'Unknown')
            except Exception as e:
                volume = 0
                market_cap = 0
                sector = 'Unknown'
            
            return {
                'ticker': ticker,
                'date': date_str,
                'prev_close': prev_close,
                'open_price': open_price,
                'gap_percent': gap_percent,
                'volume': volume,
                'market_cap': market_cap,
                'sector': sector
            }
            
        except Exception as e:
            return None
    
    def get_tickers_for_date(self, date: datetime) -> List[str]:
        """Get all tickers that were traded on a specific date, filtered by market cap"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            print(f"📊 Fetching tickers for {date_str}...")
            
            try:
                print(f"🔍 Calling Polygon API for {date_str}...")
                grouped = self.polygon_client.get_grouped_daily_aggs(
                    date_str,
                    adjusted="true"
                )
                
                print(f"📊 API response received, processing results...")
                
                # Check if we already have filtered tickers in database
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) FROM ALL_TICKERS')
                    count = cursor.fetchone()[0]
                    
                    if count > 0:
                        print(f"📊 Found {count} existing tickers in database, using cached list...")
                        cursor.execute('SELECT ticker FROM ALL_TICKERS ORDER BY ticker')
                        results = cursor.fetchall()
                        tickers = [row[0] for row in results]
                        print(f"📊 Using {len(tickers)} cached tickers for {date_str}")
                        return tickers
                
                # Process all results and filter by market cap
                print(f"📊 Processing and filtering tickers by market cap...")
                filtered_tickers = []
                total_count = 0
                processed_count = 0
                
                for result in grouped:
                    total_count += 1
                    if hasattr(result, 'ticker'):
                        ticker = result.ticker
                        
                        # Get market cap for this ticker
                        try:
                            ticker_details = self.polygon_client.get_ticker_details(ticker)
                            market_cap = getattr(ticker_details, 'market_cap', 0)
                            
                            # Filter out stocks with market cap > $10B
                            if market_cap <= 10_000_000_000:  # $10B in dollars
                                filtered_tickers.append({
                                    'ticker': ticker,
                                    'market_cap': market_cap,
                                    'sector': getattr(ticker_details, 'sic_description', 'Unknown')
                                })
                            
                            processed_count += 1
                            if processed_count % 1000 == 0:
                                print(f"📊 Processed {processed_count}/{total_count} tickers...")
                            
                        except Exception as e:
                            # If we can't get market cap, include the ticker (safer approach)
                            filtered_tickers.append({
                                'ticker': ticker,
                                'market_cap': 0,
                                'sector': 'Unknown'
                            })
                
                # Store filtered tickers in database
                print(f"📊 Storing {len(filtered_tickers)} filtered tickers in database...")
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    for ticker_data in filtered_tickers:
                        cursor.execute('''
                            INSERT OR IGNORE INTO ALL_TICKERS (ticker, market_cap, sector)
                            VALUES (?, ?, ?)
                        ''', (ticker_data['ticker'], ticker_data['market_cap'], ticker_data['sector']))
                    
                    conn.commit()
                
                tickers = [t['ticker'] for t in filtered_tickers]
                print(f"📊 Found {len(tickers)} tickers (filtered from {total_count}) for {date_str}")
                return tickers
                
            except Exception as api_error:
                print(f"❌ API Error for {date_str}: {api_error}")
                return []
            
        except Exception as e:
            print(f"❌ Error getting tickers for {date_str}: {e}")
            return []
    
    def process_date_for_gap_ups_parallel(self, date: datetime, min_gap_percent: float = 25.0, max_workers: int = 20):
        """Process a specific date using parallel processing"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            logger.info(f"📅 Processing date: {date_str} with parallel processing...")
            print(f"📅 Processing date: {date_str} with parallel processing...")
            
            # Get all tickers that were traded on this specific date
            tickers = self.get_tickers_for_date(date)
            
            if not tickers:
                logger.warning(f"⚠️ No tickers found for {date_str}")
                return
            
            logger.info(f"📊 Processing {len(tickers)} tickers with {max_workers} workers...")
            
            # Process tickers in parallel
            gap_ups = []
            processed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_ticker = {
                    executor.submit(self.check_gap_up_for_ticker_parallel, ticker, date): ticker 
                    for ticker in tickers
                }
                
                # Process completed tasks
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    processed_count += 1
                    
                    if processed_count % 50 == 0:
                        logger.info(f"📊 Processed {processed_count}/{len(tickers)} tickers... (Current: {ticker})")
                    elif processed_count % 10 == 0:
                        logger.info(f"📊 Processed {processed_count}/{len(tickers)} tickers... (Current: {ticker})")
                    
                    try:
                        gap_data = future.result()
                        if gap_data and gap_data['gap_percent'] >= min_gap_percent:
                            gap_ups.append(gap_data)
                            logger.info(f"📈 Found gap-up: {ticker} (+{gap_data['gap_percent']:.1f}%) on {date_str}")
                    except Exception as e:
                        logger.debug(f"⚠️ Error processing {ticker}: {e}")
                        continue
            
            # Store gap-ups for this date
            if gap_ups:
                self.store_gap_ups(gap_ups)
                logger.info(f"💾 Stored {len(gap_ups)} gap-up records for {date_str}")
            else:
                logger.info(f"📊 No gap-ups found for {date_str}")
            
            logger.info(f"✅ Completed processing {date_str}: {len(gap_ups)} gap-ups found")
            
        except Exception as e:
            logger.error(f"❌ Error processing date {date}: {e}")
    
    def store_gap_ups(self, gap_ups: List[Dict[str, Any]]):
        """Store gap-up data in the DAILY_GAP_UPS table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for gap_up in gap_ups:
                    cursor.execute('''
                        INSERT OR REPLACE INTO DAILY_GAP_UPS 
                        (date, ticker, prev_close, open_price, gap_percent, volume, market_cap, sector)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        gap_up['date'],
                        gap_up['ticker'],
                        gap_up['prev_close'],
                        gap_up['open_price'],
                        gap_up['gap_percent'],
                        gap_up['volume'],
                        gap_up['market_cap'],
                        gap_up['sector']
                    ))
                
                conn.commit()
                logger.info(f"💾 Stored {len(gap_ups)} gap-up records")
                
        except Exception as e:
            logger.error(f"❌ Error storing gap-up data: {e}")
            raise
    
    def fetch_historical_gap_ups(self, start_date: datetime, end_date: datetime, min_gap_percent: float = 25.0):
        """Main method: Fetch gap-up data for a date range"""
        try:
            logger.info(f"🚀 Starting historical gap-up fetch from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Process each date
            current_date = start_date
            total_days = max(1, (end_date - start_date).days)  # Avoid division by zero
            processed_days = 0
            
            logger.info(f"📅 Total days to process: {total_days}")
            
            while current_date <= end_date:
                # Skip weekends
                if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    logger.info(f"⏭️ Skipping weekend: {current_date.strftime('%Y-%m-%d')}")
                    current_date += timedelta(days=1)
                    continue
                
                # Process this date with parallel processing
                self.process_date_for_gap_ups_parallel(current_date, min_gap_percent, max_workers=5)
                
                processed_days += 1
                if total_days > 0:
                    logger.info(f"✅ Processed {processed_days}/{total_days} days ({processed_days/total_days*100:.1f}%)")
                else:
                    logger.info(f"✅ Processed {processed_days} days")
                
                current_date += timedelta(days=1)
                
                # Rate limiting between days
                time.sleep(1)
            
            logger.info(f"🎉 Completed historical gap-up fetch! Processed {processed_days} days")
            
        except Exception as e:
            logger.error(f"❌ Error in fetch_historical_gap_ups: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Fetch historical gap-up data')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)', 
                       default=(datetime.now() - timedelta(days=1095)).strftime('%Y-%m-%d'))
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)', 
                       default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--min-gap', type=float, default=25.0, 
                       help='Minimum gap percentage (default: 25.0)')
    parser.add_argument('--db-path', type=str, default='gap_up_history.db',
                       help='Database path (default: gap_up_history.db)')
    
    args = parser.parse_args()
    
    try:
        print("🚀 Starting gap-up history fetcher...")
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        
        print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"📊 Min gap: {args.min_gap}%")
        print(f"💾 Database: {args.db_path}")
        
        print("🔧 Initializing fetcher...")
        fetcher = GapUpHistoryFetcher(args.db_path)
        
        print("🚀 Starting fetch process...")
        fetcher.fetch_historical_gap_ups(start_date, end_date, args.min_gap)
        
        print("✅ Gap-up history fetch completed!")
        
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 