#!/usr/bin/env python3
"""
Historical Data Caching Module for Gap-Trade-Bot
Provides intelligent caching of historical gap-up data to reduce API calls
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import List, Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HistoricalDataCache:
    def __init__(self, db_file=None):
        # Use absolute path to ensure consistency
        if db_file is None:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_file = os.path.join(script_dir, 'trading_advisor.db')
        
        self.db_file = db_file
        self.init_cache_tables()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_cache_tables(self):
        """Initialize cache tables for historical data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create historical_data_cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historical_data_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, date)
                )
            ''')
            
            # Create cache_metadata table for tracking cache status
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    ticker TEXT PRIMARY KEY,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_start_date TEXT,
                    data_end_date TEXT,
                    total_records INTEGER DEFAULT 0
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ticker_date 
                ON historical_data_cache(ticker, date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ticker_updated 
                ON historical_data_cache(ticker, updated_at)
            ''')
            
            conn.commit()
            logger.info("✅ Historical data cache tables initialized")
    
    def get_cached_data(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """Get cached historical data for a ticker within date range"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT data_json, date, updated_at
                    FROM historical_data_cache 
                    WHERE ticker = ? AND date BETWEEN ? AND ?
                    ORDER BY date ASC
                ''', (ticker, start_date, end_date))
                
                cached_data = []
                for row in cursor.fetchall():
                    data = json.loads(row['data_json'])
                    cached_data.append(data)
                
                logger.info(f"📊 Retrieved {len(cached_data)} cached records for {ticker}")
                return cached_data
                
        except Exception as e:
            logger.error(f"❌ Error retrieving cached data for {ticker}: {e}")
            return []
    
    def get_cache_gaps(self, ticker: str, start_date: str, end_date: str) -> List[str]:
        """Find dates that are missing from cache within the requested range"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all dates in the range
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                all_dates = []
                current_dt = start_dt
                while current_dt <= end_dt:
                    all_dates.append(current_dt.strftime('%Y-%m-%d'))
                    current_dt += timedelta(days=1)
                
                # Get cached dates
                cursor.execute('''
                    SELECT date FROM historical_data_cache 
                    WHERE ticker = ? AND date BETWEEN ? AND ?
                ''', (ticker, start_date, end_date))
                
                cached_dates = {row['date'] for row in cursor.fetchall()}
                
                # Find missing dates
                missing_dates = [date for date in all_dates if date not in cached_dates]
                
                logger.info(f"🔍 Found {len(missing_dates)} missing dates for {ticker}")
                return missing_dates
                
        except Exception as e:
            logger.error(f"❌ Error finding cache gaps for {ticker}: {e}")
            return []
    
    def store_historical_data(self, ticker: str, data_list: List[Dict], query_start_date: str = None, query_end_date: str = None) -> bool:
        """Store historical data in cache with actual query range"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stored_count = 0
                for data_point in data_list:
                    date = data_point.get('date')
                    if not date:
                        continue
                    
                    # Store or update the data
                    cursor.execute('''
                        INSERT OR REPLACE INTO historical_data_cache 
                        (ticker, date, data_json, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (ticker, date, json.dumps(data_point)))
                    stored_count += 1
                
                # Update cache metadata with actual query range
                if data_list:
                    # Use actual query range if provided, otherwise use data range
                    if query_start_date and query_end_date:
                        start_date = query_start_date
                        end_date = query_end_date
                    else:
                        # Fallback to data range (for backward compatibility)
                        start_date = min(data['date'] for data in data_list if data.get('date'))
                        end_date = max(data['date'] for data in data_list if data.get('date'))
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO cache_metadata 
                        (ticker, last_updated, data_start_date, data_end_date, total_records)
                        VALUES (?, CURRENT_TIMESTAMP, ?, ?, 
                                (SELECT COUNT(*) FROM historical_data_cache WHERE ticker = ?))
                    ''', (ticker, start_date, end_date, ticker))
                
                conn.commit()
                logger.info(f"💾 Stored {stored_count} records for {ticker} in cache (query range: {query_start_date} to {query_end_date})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error storing historical data for {ticker}: {e}")
            return False
    
    def get_cache_status(self, ticker: str) -> Dict:
        """Get cache status for a ticker"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get metadata
                cursor.execute('''
                    SELECT last_updated, data_start_date, data_end_date, total_records
                    FROM cache_metadata WHERE ticker = ?
                ''', (ticker,))
                
                metadata_row = cursor.fetchone()
                if not metadata_row:
                    return {
                        'ticker': ticker,
                        'cached': False,
                        'total_records': 0,
                        'last_updated': None,
                        'data_range': None
                    }
                
                # Get most recent data
                cursor.execute('''
                    SELECT updated_at FROM historical_data_cache 
                    WHERE ticker = ? ORDER BY updated_at DESC LIMIT 1
                ''', (ticker,))
                
                recent_row = cursor.fetchone()
                last_updated = recent_row['updated_at'] if recent_row else metadata_row['last_updated']
                
                return {
                    'ticker': ticker,
                    'cached': True,
                    'total_records': metadata_row['total_records'],
                    'last_updated': last_updated,
                    'data_range': {
                        'start': metadata_row['data_start_date'],
                        'end': metadata_row['data_end_date']
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting cache status for {ticker}: {e}")
            return {'ticker': ticker, 'cached': False, 'error': str(e)}
    
    def clear_cache(self, ticker: str = None) -> bool:
        """Clear cache for a specific ticker or all tickers"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if ticker:
                    cursor.execute('DELETE FROM historical_data_cache WHERE ticker = ?', (ticker,))
                    cursor.execute('DELETE FROM cache_metadata WHERE ticker = ?', (ticker,))
                    logger.info(f"🗑️ Cleared cache for {ticker}")
                else:
                    cursor.execute('DELETE FROM historical_data_cache')
                    cursor.execute('DELETE FROM cache_metadata')
                    logger.info("🗑️ Cleared all historical data cache")
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict:
        """Get overall cache statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get total records
                cursor.execute('SELECT COUNT(*) as total FROM historical_data_cache')
                total_records = cursor.fetchone()['total']
                
                # Get unique tickers
                cursor.execute('SELECT COUNT(DISTINCT ticker) as tickers FROM historical_data_cache')
                unique_tickers = cursor.fetchone()['tickers']
                
                # Get cache size
                cursor.execute('SELECT COALESCE(SUM(LENGTH(data_json)), 0) as size FROM historical_data_cache')
                size_bytes = cursor.fetchone()['size'] or 0
                size_mb = round(size_bytes / (1024 * 1024), 2)
                
                # Get most recent updates
                cursor.execute('''
                    SELECT ticker, updated_at FROM historical_data_cache 
                    ORDER BY updated_at DESC LIMIT 5
                ''')
                recent_updates = [dict(row) for row in cursor.fetchall()]
                
                return {
                    'total_records': total_records,
                    'unique_tickers': unique_tickers,
                    'cache_size_mb': size_mb,
                    'recent_updates': recent_updates
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {'error': str(e)}
    
    def is_data_fresh(self, ticker: str, max_age_hours: int = 24) -> bool:
        """Check if cached data is fresh enough"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT updated_at FROM historical_data_cache 
                    WHERE ticker = ? ORDER BY updated_at DESC LIMIT 1
                ''', (ticker,))
                
                row = cursor.fetchone()
                if not row:
                    return False
                
                # Safely convert string date to datetime object
                if row['updated_at'] and isinstance(row['updated_at'], str):
                    last_updated = datetime.fromisoformat(row['updated_at'])
                else:
                    # If it's already a datetime object or None, handle appropriately
                    last_updated = row['updated_at'] if row['updated_at'] else datetime.now()
                
                age_hours = (datetime.now() - last_updated).total_seconds() / 3600
                
                return age_hours <= max_age_hours
                
        except Exception as e:
            logger.error(f"❌ Error checking data freshness for {ticker}: {e}")
            return False

# Global cache instance
historical_cache = HistoricalDataCache() 