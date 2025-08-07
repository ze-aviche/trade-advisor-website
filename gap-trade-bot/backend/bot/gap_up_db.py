"""
Gap-Up Database for Trading Bot
Stores gap-up detection results to avoid repeated API calls
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class GapUpDatabase:
    """Database for storing gap-up detection results"""
    
    def __init__(self, db_file: str = "bot/data/gap_up_cache.db"):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Create gap_up_results table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS gap_up_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        gap_percent REAL NOT NULL,
                        current_price REAL NOT NULL,
                        previous_close REAL NOT NULL,
                        volume INTEGER,
                        market_cap REAL,
                        peak_gap_percent REAL,
                        is_new_peak BOOLEAN DEFAULT 0,
                        is_significant_drop BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date, ticker)
                    )
                ''')
                
                # Create gap_up_sessions table to track detection runs
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS gap_up_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_date TEXT NOT NULL,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        total_tickers INTEGER DEFAULT 0,
                        gap_up_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'running'
                    )
                ''')
                
                conn.commit()
                logger.info("✅ Gap-up database initialized")
                
        except Exception as e:
            logger.error(f"❌ Error initializing gap-up database: {e}")
    
    def start_detection_session(self, session_date: str = None) -> int:
        """Start a new gap-up detection session"""
        try:
            if not session_date:
                session_date = date.today().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO gap_up_sessions (session_date, status)
                    VALUES (?, 'running')
                ''', (session_date,))
                conn.commit()
                session_id = cursor.lastrowid
                logger.info(f"🔍 Started gap-up detection session {session_id} for {session_date}")
                return session_id
                
        except Exception as e:
            logger.error(f"❌ Error starting detection session: {e}")
            return None
    
    def end_detection_session(self, session_id: int, total_tickers: int, gap_up_count: int):
        """End a gap-up detection session"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE gap_up_sessions 
                    SET end_time = CURRENT_TIMESTAMP, 
                        total_tickers = ?, 
                        gap_up_count = ?, 
                        status = 'completed'
                    WHERE id = ?
                ''', (total_tickers, gap_up_count, session_id))
                conn.commit()
                logger.info(f"✅ Completed gap-up detection session {session_id}: {gap_up_count} gap-ups found")
                
        except Exception as e:
            logger.error(f"❌ Error ending detection session: {e}")
    
    def store_gap_up_results(self, session_id: int, gap_up_data: List[Dict[str, Any]]):
        """Store gap-up detection results"""
        try:
            session_date = date.today().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                for stock in gap_up_data:
                    ticker = stock.get('ticker')
                    gap_percent = stock.get('gap_percent', 0)
                    current_price = stock.get('current_price', 0)
                    previous_close = stock.get('previous_close', 0)
                    volume = stock.get('volume', 0)
                    market_cap = stock.get('market_cap', 0)
                    peak_gap_percent = stock.get('peak_gap_percent', 0)
                    is_new_peak = stock.get('is_new_peak', False)
                    is_significant_drop = stock.get('is_significant_drop', False)
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO gap_up_results 
                        (date, ticker, gap_percent, current_price, previous_close, 
                         volume, market_cap, peak_gap_percent, is_new_peak, is_significant_drop)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (session_date, ticker, gap_percent, current_price, previous_close,
                          volume, market_cap, peak_gap_percent, is_new_peak, is_significant_drop))
                
                conn.commit()
                logger.info(f"💾 Stored {len(gap_up_data)} gap-up results for session {session_id}")
                
        except Exception as e:
            logger.error(f"❌ Error storing gap-up results: {e}")
    
    def get_gap_up_stocks(self, min_gap_percent: float = 25.0, 
                          include_new_peaks: bool = True,
                          include_significant_drops: bool = False) -> List[str]:
        """Get gap-up stocks from database"""
        try:
            session_date = date.today().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Build query based on criteria
                query = '''
                    SELECT ticker, gap_percent, is_new_peak, is_significant_drop
                    FROM gap_up_results 
                    WHERE date = ? AND gap_percent >= ?
                '''
                params = [session_date, min_gap_percent]
                
                if include_new_peaks and not include_significant_drops:
                    query += ' AND is_new_peak = 1'
                elif include_significant_drops and not include_new_peaks:
                    query += ' AND is_significant_drop = 1'
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                tickers = [row[0] for row in results]
                logger.info(f"📊 Retrieved {len(tickers)} gap-up stocks from database (min gap: {min_gap_percent}%)")
                return tickers
                
        except Exception as e:
            logger.error(f"❌ Error getting gap-up stocks from database: {e}")
            return []
    
    def get_gap_up_data(self, min_gap_percent: float = 25.0) -> List[Dict[str, Any]]:
        """Get full gap-up data from database"""
        try:
            session_date = date.today().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ticker, gap_percent, current_price, previous_close, 
                           volume, market_cap, peak_gap_percent, is_new_peak, is_significant_drop
                    FROM gap_up_results 
                    WHERE date = ? AND gap_percent >= ?
                    ORDER BY gap_percent DESC
                ''', (session_date, min_gap_percent))
                
                results = cursor.fetchall()
                gap_up_data = []
                
                for row in results:
                    gap_up_data.append({
                        'ticker': row[0],
                        'gap_percent': row[1],
                        'current_price': row[2],
                        'previous_close': row[3],
                        'volume': row[4],
                        'market_cap': row[5],
                        'peak_gap_percent': row[6],
                        'is_new_peak': bool(row[7]),
                        'is_significant_drop': bool(row[8])
                    })
                
                logger.info(f"📊 Retrieved {len(gap_up_data)} gap-up records from database")
                return gap_up_data
                
        except Exception as e:
            logger.error(f"❌ Error getting gap-up data from database: {e}")
            return []
    
    def is_data_fresh(self, max_age_minutes: int = 30) -> bool:
        """Check if the gap-up data is fresh (less than max_age_minutes old)"""
        try:
            session_date = date.today().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT MAX(created_at) as last_update
                    FROM gap_up_results 
                    WHERE date = ?
                ''', (session_date,))
                
                result = cursor.fetchone()
                if not result or not result[0]:
                    return False
                
                last_update = datetime.fromisoformat(result[0].replace('Z', '+00:00'))
                age_minutes = (datetime.now() - last_update).total_seconds() / 60
                
                is_fresh = age_minutes < max_age_minutes
                logger.info(f"📊 Gap-up data age: {age_minutes:.1f} minutes (fresh: {is_fresh})")
                return is_fresh
                
        except Exception as e:
            logger.error(f"❌ Error checking data freshness: {e}")
            return False
    
    def clear_old_data(self, days: int = 7):
        """Clear old gap-up data"""
        try:
            cutoff_date = (date.today() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM gap_up_results WHERE date < ?', (cutoff_date,))
                cursor.execute('DELETE FROM gap_up_sessions WHERE session_date < ?', (cutoff_date,))
                conn.commit()
                
                logger.info(f"🧹 Cleared gap-up data older than {days} days")
                
        except Exception as e:
            logger.error(f"❌ Error clearing old data: {e}")

# Global instance
gap_up_db = GapUpDatabase() 