#!/usr/bin/env python3
"""
Trading Database Manager
Handles real-time trading data: positions, orders, trades, performance metrics
Separate from historical cache for optimal performance
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, List, Optional, Any

# Add parent directory to path
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger

logger = get_logger(__name__)

class TradingDatabase:
    """Manages trading-specific database operations"""
    
    def __init__(self, db_file=None):
        # Use absolute path to ensure consistency
        if db_file is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_file = os.path.join(script_dir, 'trading_positions.db')
        
        self.db_file = db_file
        self.init_trading_tables()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_trading_tables(self):
        """Initialize trading-specific tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Drop and recreate performance_metrics table to fix schema
            cursor.execute('DROP TABLE IF EXISTS performance_metrics')
            
            # Create positions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    exit_price REAL,
                    exit_time TIMESTAMP,
                    status TEXT DEFAULT 'open',
                    pnl REAL DEFAULT 0.0,
                    broker TEXT DEFAULT 'alpaca',
                    order_id TEXT,
                    UNIQUE(ticker, side, status)
                )
            ''')
            
            # Create orders table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE NOT NULL,
                    ticker TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    price REAL,
                    limit_price REAL,
                    stop_price REAL,
                    filled_qty INTEGER DEFAULT 0,
                    avg_fill_price REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    filled_at TIMESTAMP,
                    cancelled_at TIMESTAMP,
                    broker TEXT NOT NULL,
                    strategy TEXT,
                    notes TEXT
                )
            ''')
            
            # Create trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    ticker TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    pnl REAL DEFAULT 0.0,
                    commission REAL DEFAULT 0.0,
                    strategy TEXT,
                    broker TEXT NOT NULL,
                    notes TEXT
                )
            ''')
            
            # Create performance_metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0.0,
                    total_commission REAL DEFAULT 0.0,
                    win_rate REAL DEFAULT 0.0,
                    avg_win REAL DEFAULT 0.0,
                    avg_loss REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    strategy TEXT,
                    broker TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, strategy, broker)
                )
            ''')
            
            # Create risk_limits table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS risk_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    limit_type TEXT NOT NULL,
                    limit_value REAL NOT NULL,
                    current_value REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(limit_type)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_ticker ON orders(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(entry_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_date ON performance_metrics(date)')
            
            conn.commit()
            logger.info("✅ Trading database tables initialized")
    
    # Position Management
    def open_position(self, ticker: str, quantity: int, side: str, entry_price: float, 
                     broker: str = 'alpaca', order_id: str = None) -> bool:
        """Open a new position"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO positions 
                    (ticker, quantity, side, entry_price, status, broker, order_id, entry_time)
                    VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
                ''', (ticker, quantity, side, entry_price, broker, order_id, datetime.now().isoformat()))
                
                conn.commit()
                logger.info(f"📈 Position opened: {ticker} {quantity} shares {side} @ ${entry_price}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error opening position: {e}")
            return False
    
    def close_position(self, ticker: str, side: str, exit_price: float, 
                      exit_time: str = None) -> bool:
        """Close an existing position"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get current position
                cursor.execute('''
                    SELECT * FROM positions 
                    WHERE ticker = ? AND side = ? AND status = 'open'
                ''', (ticker, side))
                
                position = cursor.fetchone()
                if not position:
                    logger.warning(f"⚠️ No open position found for {ticker} {side}")
                    return False
                
                # Calculate P&L
                entry_price = position['entry_price']
                quantity = position['quantity']
                pnl = (exit_price - entry_price) * quantity if side == 'buy' else (entry_price - exit_price) * quantity
                
                # Update position
                cursor.execute('''
                    UPDATE positions 
                    SET exit_price = ?, exit_time = ?, status = 'closed', pnl = ?
                    WHERE ticker = ? AND side = ? AND status = 'open'
                ''', (exit_price, exit_time or datetime.now().isoformat(), pnl, ticker, side))
                
                conn.commit()
                logger.info(f"📉 Position closed: {ticker} {side} @ ${exit_price} P&L: ${pnl:.2f}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            return False
    
    def get_position(self, ticker: str, side: str = None) -> Optional[Dict[str, Any]]:
        """Get current position for a ticker"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if side:
                    cursor.execute('''
                        SELECT * FROM positions 
                        WHERE ticker = ? AND side = ? AND status = 'open'
                    ''', (ticker, side))
                else:
                    cursor.execute('''
                        SELECT * FROM positions 
                        WHERE ticker = ? AND status = 'open'
                    ''', (ticker,))
                
                position = cursor.fetchone()
                return dict(position) if position else None
                
        except Exception as e:
            logger.error(f"❌ Error getting position: {e}")
            return None
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM positions WHERE status = 'open'
                    ORDER BY entry_time DESC
                ''')
                
                positions = []
                for row in cursor.fetchall():
                    positions.append(dict(row))
                
                return positions
                
        except Exception as e:
            logger.error(f"❌ Error getting all positions: {e}")
            return []
    
    def update_position_price(self, ticker: str, current_price: float) -> bool:
        """Update position with current price for P&L calculation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM positions 
                    WHERE ticker = ? AND status = 'open'
                ''', (ticker,))
                
                position = cursor.fetchone()
                if not position:
                    return False
                
                # Calculate unrealized P&L
                entry_price = position['entry_price']
                quantity = position['quantity']
                side = position['side']
                
                if side == 'buy':
                    pnl = (current_price - entry_price) * quantity
                else:
                    pnl = (entry_price - current_price) * quantity
                
                # Update P&L
                cursor.execute('''
                    UPDATE positions 
                    SET pnl = ? 
                    WHERE ticker = ? AND status = 'open'
                ''', (pnl, ticker))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating position price: {e}")
            return False
    
    # Order Management
    def store_order(self, order_data: Dict[str, Any]) -> bool:
        """Store order information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO orders 
                    (order_id, ticker, quantity, side, order_type, status, price, 
                     limit_price, stop_price, broker, strategy, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order_data.get('order_id'),
                    order_data.get('ticker'),
                    order_data.get('quantity'),
                    order_data.get('side'),
                    order_data.get('order_type'),
                    order_data.get('status', 'submitted'),
                    order_data.get('price'),
                    order_data.get('limit_price'),
                    order_data.get('stop_price'),
                    order_data.get('broker', 'alpaca'),
                    order_data.get('strategy'),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                logger.info(f"📋 Order stored: {order_data.get('ticker')} {order_data.get('side')}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error storing order: {e}")
            return False
    
    def update_order_status(self, order_id: str, status: str, 
                          filled_qty: int = None, avg_fill_price: float = None) -> bool:
        """Update order status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if status == 'filled':
                    cursor.execute('''
                        UPDATE orders 
                        SET status = ?, filled_qty = ?, avg_fill_price = ?, filled_at = ?
                        WHERE order_id = ?
                    ''', (status, filled_qty, avg_fill_price, datetime.now().isoformat(), order_id))
                elif status == 'cancelled':
                    cursor.execute('''
                        UPDATE orders 
                        SET status = ?, cancelled_at = ?
                        WHERE order_id = ?
                    ''', (status, datetime.now().isoformat(), order_id))
                else:
                    cursor.execute('''
                        UPDATE orders 
                        SET status = ?
                        WHERE order_id = ?
                    ''', (status, order_id))
                
                conn.commit()
                logger.info(f"📊 Order status updated: {order_id} -> {status}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating order status: {e}")
            return False
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
                order = cursor.fetchone()
                
                return dict(order) if order else None
                
        except Exception as e:
            logger.error(f"❌ Error getting order: {e}")
            return None
    
    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM orders 
                    WHERE status IN ('submitted', 'pending', 'partial')
                    ORDER BY created_at DESC
                ''')
                
                orders = []
                for row in cursor.fetchall():
                    orders.append(dict(row))
                
                return orders
                
        except Exception as e:
            logger.error(f"❌ Error getting pending orders: {e}")
            return []
    
    # Trade Management
    def record_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Record a completed trade"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO trades 
                    (trade_id, ticker, quantity, side, entry_price, exit_price, 
                     entry_time, exit_time, pnl, commission, strategy, broker, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_data.get('trade_id'),
                    trade_data.get('ticker'),
                    trade_data.get('quantity'),
                    trade_data.get('side'),
                    trade_data.get('entry_price'),
                    trade_data.get('exit_price'),
                    trade_data.get('entry_time'),
                    trade_data.get('exit_time'),
                    trade_data.get('pnl', 0.0),
                    trade_data.get('commission', 0.0),
                    trade_data.get('strategy'),
                    trade_data.get('broker', 'alpaca'),
                    trade_data.get('notes')
                ))
                
                conn.commit()
                logger.info(f"💰 Trade recorded: {trade_data.get('ticker')} P&L: ${trade_data.get('pnl', 0):.2f}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error recording trade: {e}")
            return False
    
    def get_trade_history(self, ticker: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trade history"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if ticker:
                    cursor.execute('''
                        SELECT * FROM trades 
                        WHERE ticker = ?
                        ORDER BY entry_time DESC
                        LIMIT ?
                    ''', (ticker, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM trades 
                        ORDER BY entry_time DESC
                        LIMIT ?
                    ''', (limit,))
                
                trades = []
                for row in cursor.fetchall():
                    trades.append(dict(row))
                
                return trades
                
        except Exception as e:
            logger.error(f"❌ Error getting trade history: {e}")
            return []
    
    # Performance Metrics
    def update_performance_metrics(self, date: str, metrics: Dict[str, Any]) -> bool:
        """Update daily performance metrics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO performance_metrics 
                    (date, total_trades, winning_trades, losing_trades, total_pnl, 
                     total_commission, win_rate, avg_win, avg_loss, max_drawdown, 
                     strategy, broker, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    date,
                    metrics.get('total_trades', 0),
                    metrics.get('winning_trades', 0),
                    metrics.get('losing_trades', 0),
                    metrics.get('total_pnl', 0.0),
                    metrics.get('total_commission', 0.0),
                    metrics.get('win_rate', 0.0),
                    metrics.get('avg_win', 0.0),
                    metrics.get('avg_loss', 0.0),
                    metrics.get('max_drawdown', 0.0),
                    metrics.get('strategy'),
                    metrics.get('broker', 'alpaca'),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                logger.info(f"📊 Performance metrics updated for {date}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating performance metrics: {e}")
            return False
    
    def get_performance_summary(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get performance summary"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if start_date and end_date:
                    cursor.execute('''
                        SELECT 
                            SUM(total_trades) as total_trades,
                            SUM(winning_trades) as winning_trades,
                            SUM(losing_trades) as losing_trades,
                            SUM(total_pnl) as total_pnl,
                            SUM(total_commission) as total_commission,
                            AVG(win_rate) as avg_win_rate,
                            AVG(avg_win) as avg_win,
                            AVG(avg_loss) as avg_loss,
                            MIN(max_drawdown) as max_drawdown
                        FROM performance_metrics 
                        WHERE date BETWEEN ? AND ?
                    ''', (start_date, end_date))
                else:
                    cursor.execute('''
                        SELECT 
                            SUM(total_trades) as total_trades,
                            SUM(winning_trades) as winning_trades,
                            SUM(losing_trades) as losing_trades,
                            SUM(total_pnl) as total_pnl,
                            SUM(total_commission) as total_commission,
                            AVG(win_rate) as avg_win_rate,
                            AVG(avg_win) as avg_win,
                            AVG(avg_loss) as avg_loss,
                            MIN(max_drawdown) as max_drawdown
                        FROM performance_metrics
                    ''')
                
                result = cursor.fetchone()
                if result:
                    return dict(result)
                else:
                    return {}
                
        except Exception as e:
            logger.error(f"❌ Error getting performance summary: {e}")
            return {}
    
    # Database Maintenance
    def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up old data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                
                # Clean up old orders
                cursor.execute('DELETE FROM orders WHERE created_at < ?', (cutoff_date,))
                
                # Clean up old performance metrics
                cursor.execute('DELETE FROM performance_metrics WHERE date < ?', (cutoff_date,))
                
                conn.commit()
                logger.info(f"🧹 Cleaned up data older than {days} days")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up old data: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Count positions
                cursor.execute('SELECT COUNT(*) as count FROM positions WHERE status = "open"')
                stats['open_positions'] = cursor.fetchone()['count']
                
                # Count orders
                cursor.execute('SELECT COUNT(*) as count FROM orders WHERE status IN ("submitted", "pending", "partial")')
                stats['pending_orders'] = cursor.fetchone()['count']
                
                # Count trades
                cursor.execute('SELECT COUNT(*) as count FROM trades')
                stats['total_trades'] = cursor.fetchone()['count']
                
                # Database size
                cursor.execute('PRAGMA page_count')
                page_count = cursor.fetchone()[0]
                cursor.execute('PRAGMA page_size')
                page_size = cursor.fetchone()[0]
                stats['database_size_mb'] = (page_count * page_size) / (1024 * 1024)
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {e}")
            return {}

# Global trading database instance
trading_db = TradingDatabase() 