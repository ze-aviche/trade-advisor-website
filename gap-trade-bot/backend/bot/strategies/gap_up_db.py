#!/usr/bin/env python3
"""
Gap-Up Database Query Utility
Provides functions to query the gap_up_history.db for backtesting
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from logging_config import get_logger

logger = get_logger(__name__)

class GapUpDB:
    """Database interface for gap-up history"""
    
    def __init__(self, db_path: str = "gap_up_history.db"):
        self.db_path = db_path
    
    def get_gap_up_stocks_for_date(self, date: datetime, min_gap_percent: float = 25.0) -> List[str]:
        """Get list of tickers that had gap-ups on a specific date"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT ticker, gap_percent 
                    FROM DAILY_GAP_UPS 
                    WHERE date = ? AND gap_percent >= ?
                    ORDER BY gap_percent DESC
                ''', (date_str, min_gap_percent))
                
                results = cursor.fetchall()
                tickers = [row[0] for row in results]
                
                logger.info(f"📊 Found {len(tickers)} gap-up stocks for {date_str} (≥{min_gap_percent}%)")
                for ticker, gap_percent in results:
                    logger.debug(f"📈 {ticker}: +{gap_percent:.1f}%")
                
                return tickers
                
        except Exception as e:
            logger.error(f"❌ Error querying gap-up database for {date}: {e}")
            return []
    
    def get_gap_up_data_for_stock(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        """Get detailed gap-up data for a specific stock on a specific date"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT date, ticker, prev_close, open_price, gap_percent, 
                           volume, market_cap, sector
                    FROM DAILY_GAP_UPS 
                    WHERE date = ? AND ticker = ?
                ''', (date_str, ticker))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'date': row[0],
                        'ticker': row[1],
                        'prev_close': row[2],
                        'open_price': row[3],
                        'gap_percent': row[4],
                        'volume': row[5],
                        'market_cap': row[6],
                        'sector': row[7]
                    }
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting gap-up data for {ticker} on {date}: {e}")
            return None
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about the gap-up database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total gap-up records
                cursor.execute('SELECT COUNT(*) FROM DAILY_GAP_UPS')
                total_gap_ups = cursor.fetchone()[0]
                
                # Total tickers
                cursor.execute('SELECT COUNT(*) FROM ALL_TICKERS')
                total_tickers = cursor.fetchone()[0]
                
                # Date range
                cursor.execute('SELECT MIN(date), MAX(date) FROM DAILY_GAP_UPS')
                date_range = cursor.fetchone()
                min_date = date_range[0] if date_range[0] else 'N/A'
                max_date = date_range[1] if date_range[1] else 'N/A'
                
                # Unique dates
                cursor.execute('SELECT COUNT(DISTINCT date) FROM DAILY_GAP_UPS')
                unique_dates = cursor.fetchone()[0]
                
                # Unique tickers with gap-ups
                cursor.execute('SELECT COUNT(DISTINCT ticker) FROM DAILY_GAP_UPS')
                unique_gap_up_tickers = cursor.fetchone()[0]
                
                # Average gap percentage
                cursor.execute('SELECT AVG(gap_percent) FROM DAILY_GAP_UPS')
                avg_gap = cursor.fetchone()[0]
                
                return {
                    'total_gap_ups': total_gap_ups,
                    'total_tickers': total_tickers,
                    'date_range': {'min': min_date, 'max': max_date},
                    'unique_dates': unique_dates,
                    'unique_gap_up_tickers': unique_gap_up_tickers,
                    'average_gap_percent': avg_gap
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {e}")
            return {}
    
    def check_database_exists(self) -> bool:
        """Check if the gap-up database exists and has data"""
        try:
            if not os.path.exists(self.db_path):
                logger.warning(f"⚠️ Database file not found: {self.db_path}")
                return False
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='DAILY_GAP_UPS'")
                if not cursor.fetchone():
                    logger.warning(f"⚠️ DAILY_GAP_UPS table not found in {self.db_path}")
                    return False
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ALL_TICKERS'")
                if not cursor.fetchone():
                    logger.warning(f"⚠️ ALL_TICKERS table not found in {self.db_path}")
                    return False
                
                # Check if we have data
                cursor.execute('SELECT COUNT(*) FROM DAILY_GAP_UPS')
                gap_ups_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM ALL_TICKERS')
                tickers_count = cursor.fetchone()[0]
                
                if gap_ups_count == 0:
                    logger.warning(f"⚠️ Database exists but DAILY_GAP_UPS is empty: {self.db_path}")
                    return False
                
                if tickers_count == 0:
                    logger.warning(f"⚠️ Database exists but ALL_TICKERS is empty: {self.db_path}")
                    return False
                
                logger.info(f"✅ Database found with {gap_ups_count} gap-ups and {tickers_count} tickers: {self.db_path}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error checking database: {e}")
            return False

def main():
    """Test the gap-up database functionality"""
    db = GapUpDB()
    
    if not db.check_database_exists():
        print("❌ Gap-up database not found or empty!")
        print("Run fetch_gap_up_history.py first to populate the database.")
        return
    
    # Get database stats
    stats = db.get_database_stats()
    print("\n📊 Database Statistics:")
    print(f"Total Records: {stats.get('total_records', 0)}")
    print(f"Date Range: {stats.get('date_range', {}).get('min', 'N/A')} to {stats.get('date_range', {}).get('max', 'N/A')}")
    print(f"Unique Dates: {stats.get('unique_dates', 0)}")
    print(f"Unique Tickers: {stats.get('unique_tickers', 0)}")
    print(f"Average Gap %: {stats.get('average_gap_percent', 0):.1f}%")
    
    # Test getting gap-ups for a recent date
    test_date = datetime.now() - timedelta(days=7)
    gap_ups = db.get_gap_up_stocks_for_date(test_date)
    print(f"\n📈 Gap-ups for {test_date.strftime('%Y-%m-%d')}: {len(gap_ups)} stocks")

if __name__ == "__main__":
    main() 