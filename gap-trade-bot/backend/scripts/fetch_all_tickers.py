#!/usr/bin/env python3
"""
Fetch All Tickers Script
Fetches all stocks with market cap > 10B and stores them in ALL_tickers table
for a single day.
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from polygon import RESTClient
from logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

class AllTickersFetcher:
    """Fetches all stocks with market cap > 10B and stores them in database"""
    
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
        
        print("✅ Polygon API client initialized")
        return RESTClient(api_key)
    
    def init_database(self):
        """Initialize the database with ALL_TICKERS table"""
        try:
            print(f"🗄️ Initializing database: {self.db_path}")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create ALL_TICKERS table
                print("📋 Creating ALL_TICKERS table...")
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ALL_TICKERS (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT UNIQUE NOT NULL,
                        market_cap REAL,
                        sector TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create index for faster queries
                print("🔍 Creating database indexes...")
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_tickers_ticker ON ALL_TICKERS(ticker)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_tickers_market_cap ON ALL_TICKERS(market_cap)')
                
                conn.commit()
                print(f"✅ Database initialized: {self.db_path}")
                logger.info(f"✅ Database initialized: {self.db_path}")
                
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            logger.error(f"❌ Error initializing database: {e}")
            raise
    
    def fetch_and_filter_tickers(self, date: datetime) -> List[Dict[str, Any]]:
        """Fetch all tickers for a specific date and filter by market cap > 10B"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            print(f"📊 Fetching all tickers for {date_str}...")
            logger.info(f"📊 Fetching all tickers for {date_str}...")
            
            # Get grouped daily data for the date
            print(f"🔍 Calling Polygon API for {date_str}...")
            logger.info(f"🔍 Calling Polygon API for {date_str}...")
            grouped = self.polygon_client.get_grouped_daily_aggs(
                date_str,
                adjusted="true"
            )
            
            print(f"📊 API response received, processing {len(grouped)} results...")
            logger.info(f"📊 API response received, processing {len(grouped)} results...")
            
            # Process all results and filter by market cap
            print(f"📊 Processing and filtering tickers by market cap < 10B...")
            logger.info(f"📊 Processing and filtering tickers by market cap < 10B...")
            filtered_tickers = []
            total_count = 0
            processed_count = 0
            
            for result in grouped:
                total_count += 1
                if hasattr(result, 'ticker'):
                    ticker = result.ticker
                    print(f"🔍 Processing ticker {total_count}: {ticker}")
                    
                    # Get market cap for this ticker
                    try:
                        print(f"  📈 Getting market cap for {ticker}...")
                        ticker_details = self.polygon_client.get_ticker_details(ticker)
                        market_cap = getattr(ticker_details, 'market_cap', 0)
                        
                        # Handle None market cap values
                        if market_cap is None:
                            market_cap = 0
                            print(f"  💰 {ticker} market cap: None (set to 0)")
                        else:
                            print(f"  💰 {ticker} market cap: ${market_cap:,.0f}")
                        
                        # Filter for stocks with market cap < $10B
                        if market_cap < 10_000_000_000:  # $10B in dollars
                            sector = getattr(ticker_details, 'sic_description', 'Unknown')
                            print(f"  ✅ {ticker} QUALIFIED - Market Cap: ${market_cap:,.0f}, Sector: {sector}")
                            filtered_tickers.append({
                                'ticker': ticker,
                                'market_cap': market_cap,
                                'sector': sector
                            })
                        else:
                            print(f"  ❌ {ticker} REJECTED - Market Cap: ${market_cap:,.0f} (above 10B threshold)")
                        
                        processed_count += 1
                        if processed_count % 100 == 0:
                            print(f"📊 Progress: Processed {processed_count}/{total_count} tickers...")
                            logger.info(f"📊 Processed {processed_count}/{total_count} tickers...")
                        
                    except Exception as e:
                        print(f"  ⚠️ ERROR getting market cap for {ticker}: {e}")
                        logger.warning(f"⚠️ Could not get market cap for {ticker}: {e}")
                        # Skip tickers where we can't get market cap data
                        continue
            
            print(f"📊 Found {len(filtered_tickers)} tickers with market cap < 10B (from {total_count} total)")
            logger.info(f"📊 Found {len(filtered_tickers)} tickers with market cap < 10B (from {total_count} total)")
            return filtered_tickers
            
        except Exception as e:
            logger.error(f"❌ Error fetching tickers for {date_str}: {e}")
            return []
    
    def store_tickers(self, tickers: List[Dict[str, Any]]):
        """Store filtered tickers in the ALL_TICKERS table"""
        try:
            print(f"📊 Storing {len(tickers)} tickers in database...")
            logger.info(f"📊 Storing {len(tickers)} tickers in database...")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clear existing data first
                print("🗑️ Clearing existing ALL_TICKERS data...")
                cursor.execute('DELETE FROM ALL_TICKERS')
                print("🗑️ Cleared existing ALL_TICKERS data")
                logger.info("🗑️ Cleared existing ALL_TICKERS data")
                
                # Insert new data
                print("💾 Inserting tickers into database...")
                for i, ticker_data in enumerate(tickers, 1):
                    ticker = ticker_data['ticker']
                    market_cap = ticker_data['market_cap']
                    sector = ticker_data['sector']
                    
                    # Handle None market cap values for display
                    if market_cap is None:
                        market_cap_display = "None"
                    else:
                        market_cap_display = f"${market_cap:,.0f}"
                    
                    print(f"  💾 Storing {i}/{len(tickers)}: {ticker} - Market Cap: {market_cap_display} - Sector: {sector}")
                    
                    cursor.execute('''
                        INSERT INTO ALL_TICKERS (ticker, market_cap, sector)
                        VALUES (?, ?, ?)
                    ''', (ticker, market_cap, sector))
                    
                    # Commit every 50 records to avoid long transactions
                    if i % 50 == 0:
                        conn.commit()
                        print(f"  ✅ Committed {i} records to database...")
                
                # Final commit
                conn.commit()
                print(f"✅ Successfully stored {len(tickers)} tickers in ALL_TICKERS table")
                logger.info(f"✅ Successfully stored {len(tickers)} tickers in ALL_TICKERS table")
                
        except Exception as e:
            print(f"❌ Error storing tickers: {e}")
            logger.error(f"❌ Error storing tickers: {e}")
            raise
    
    def run_for_date(self, date: datetime):
        """Run the complete process for a specific date"""
        try:
            print(f"🚀 Starting ticker fetch for {date.strftime('%Y-%m-%d')}")
            logger.info(f"🚀 Starting ticker fetch for {date.strftime('%Y-%m-%d')}")
            
            # Fetch and filter tickers
            print("📊 Step 1: Fetching and filtering tickers...")
            tickers = self.fetch_and_filter_tickers(date)
            
            if not tickers:
                print("⚠️ No tickers found matching criteria")
                logger.warning("⚠️ No tickers found matching criteria")
                return
            
            # Store tickers in database
            print("📊 Step 2: Storing tickers in database...")
            self.store_tickers(tickers)
            
            # Display summary
            print(f"✅ Process completed successfully!")
            print(f"📊 Total tickers with market cap < 10B: {len(tickers)}")
            logger.info(f"✅ Process completed successfully!")
            logger.info(f"📊 Total tickers with market cap < 10B: {len(tickers)}")
            
            # Show some examples
            print("📋 Sample tickers:")
            logger.info("📋 Sample tickers:")
            for i, ticker in enumerate(tickers[:10]):
                market_cap = ticker['market_cap']
                if market_cap is None:
                    market_cap_display = "None"
                else:
                    market_cap_display = f"${market_cap:,.0f}"
                
                print(f"   {ticker['ticker']} - Market Cap: {market_cap_display} - Sector: {ticker['sector']}")
                logger.info(f"   {ticker['ticker']} - Market Cap: {market_cap_display} - Sector: {ticker['sector']}")
            
            if len(tickers) > 10:
                print(f"   ... and {len(tickers) - 10} more")
                logger.info(f"   ... and {len(tickers) - 10} more")
            
        except Exception as e:
            print(f"❌ Error in run_for_date: {e}")
            logger.error(f"❌ Error in run_for_date: {e}")
            raise

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Fetch all tickers with market cap < 10B')
    parser.add_argument('--date', type=str, default=None, 
                       help='Date to fetch (YYYY-MM-DD format, defaults to yesterday)')
    parser.add_argument('--db-path', type=str, default='gap_ups_history.db',
                       help='Database path (default: gap_ups_history.db)')
    
    args = parser.parse_args()
    
    print("🎯 Starting All Tickers Fetcher Script")
    print("=" * 50)
    
    # Determine date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
            print(f"📅 Using specified date: {args.date}")
        except ValueError:
            print("❌ Invalid date format. Use YYYY-MM-DD")
            logger.error("❌ Invalid date format. Use YYYY-MM-DD")
            return
    else:
        # Default to yesterday
        target_date = datetime.now() - timedelta(days=1)
        print(f"📅 Using default date (yesterday): {target_date.strftime('%Y-%m-%d')}")
    
    print(f"🎯 Target date: {target_date.strftime('%Y-%m-%d')}")
    print(f"💾 Database path: {args.db_path}")
    logger.info(f"🎯 Target date: {target_date.strftime('%Y-%m-%d')}")
    
    # Create fetcher and run
    try:
        print("🔧 Initializing fetcher...")
        fetcher = AllTickersFetcher(args.db_path)
        print("✅ Fetcher initialized successfully")
        
        print("🚀 Starting main process...")
        fetcher.run_for_date(target_date)
        
        print("=" * 50)
        print("🎉 Script completed successfully!")
        
    except Exception as e:
        print(f"❌ Script failed: {e}")
        logger.error(f"❌ Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 