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

def get_utc_datetime() -> str:
    """Get current UTC datetime in ISO format"""
    return datetime.now(timezone.utc).isoformat()

def convert_to_utc(dt: datetime) -> str:
    """Convert datetime to UTC ISO format"""
    if dt.tzinfo is None:
        # If no timezone info, assume it's UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

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
                    alpaca_id TEXT,
                    status TEXT,
                    notes TEXT
                )
            ''')
            
            # Add alpaca_id column if it doesn't exist
            try:
                cursor.execute('ALTER TABLE trades ADD COLUMN alpaca_id TEXT')
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
            # Add status column if it doesn't exist
            try:
                cursor.execute('ALTER TABLE trades ADD COLUMN status TEXT')
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
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
                
                entry_time = get_utc_datetime()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO positions 
                    (ticker, quantity, side, entry_price, status, broker, order_id, entry_time)
                    VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
                ''', (ticker, quantity, side, entry_price, broker, order_id, entry_time))
                
                # Create trade record for open position
                trade_data = {
                    'trade_id': f"{ticker}_{side}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    'ticker': ticker,
                    'quantity': quantity,
                    'side': side,
                    'entry_price': entry_price,
                    'exit_price': None,
                    'entry_time': entry_time,
                    'exit_time': None,
                    'pnl': 0.0,  # Will be updated with current price
                    'commission': 0.0,
                    'strategy': 'Active Position',
                    'broker': broker,
                    'alpaca_id': order_id,
                    'status': 'open',
                    'notes': f"Active position - {side} {quantity} shares"
                }
                
                # Record the trade
                self.record_trade(trade_data)
                
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
                ''', (exit_price, exit_time or get_utc_datetime(), pnl, ticker, side))
                
                if cursor.rowcount == 0:
                    logger.error(f"❌ No rows updated when closing position {ticker} {side}")
                    return False
                
                # Create trade record
                trade_data = {
                    'trade_id': f"{ticker}_{side}_{get_utc_datetime().replace(':', '').replace('-', '').replace('T', '_').split('.')[0]}",
                    'ticker': ticker,
                    'quantity': position['quantity'],
                    'side': side,
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'entry_time': position['entry_time'],
                    'exit_time': exit_time or get_utc_datetime(),
                    'pnl': pnl,
                    'commission': 0.0,
                    'strategy': position.get('strategy', 'Unknown'),
                    'broker': position.get('broker', 'alpaca'),
                    'alpaca_id': position.get('order_id'),
                    'status': 'closed',
                    'notes': f"Closed position - {side} {quantity} shares"
                }
                
                # Record the trade
                trade_success = self.record_trade(trade_data)
                if not trade_success:
                    logger.error(f"❌ Failed to record trade for closed position {ticker} {side}")
                    # Rollback the position update
                    conn.rollback()
                    return False
                
                conn.commit()
                logger.info(f"📉 Position closed: {ticker} {side} @ ${exit_price} P&L: ${pnl:.2f}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error closing position {ticker} {side}: {e}")
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
                     entry_time, exit_time, pnl, commission, strategy, broker, 
                     alpaca_id, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    trade_data.get('alpaca_id'),
                    trade_data.get('status'),
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
    
    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing trade record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Build dynamic UPDATE query
                set_clauses = []
                values = []
                
                for key, value in updates.items():
                    if key in ['pnl', 'exit_price', 'exit_time', 'status', 'notes']:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if not set_clauses:
                    logger.warning(f"⚠️ No valid fields to update for trade {trade_id}")
                    return False
                
                values.append(trade_id)
                query = f"UPDATE trades SET {', '.join(set_clauses)} WHERE trade_id = ?"
                
                cursor.execute(query, values)
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"✅ Updated trade: {trade_id}")
                    return True
                else:
                    logger.warning(f"⚠️ No trade found to update: {trade_id}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ Error updating trade {trade_id}: {e}")
            return False
    
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
    
    def sync_trades_from_alpaca(self, alpaca_client) -> Dict[str, Any]:
        """Sync trades and positions from Alpaca to local database"""
        try:
            logger.info("🔄 Syncing trades and positions from Alpaca...")
            
            synced_count = 0
            skipped_count = 0
            error_count = 0
            
            # First, sync current orders (trades)
            try:
                orders = alpaca_client.trading_client.get_orders()
                logger.info(f"📋 Found {len(orders)} current orders from Alpaca")
            except Exception as e:
                logger.error(f"❌ Error fetching orders from Alpaca: {e}")
                orders = []
            
            for order in orders:
                try:
                    # Check if trade already exists in database
                    existing_trade = self.get_trade_by_alpaca_id(order.id)
                    
                    if not existing_trade:
                        # Create trade record for filled orders
                        if order.status == 'filled':
                            trade_data = {
                                'trade_id': f"ALPACA_{order.id}",
                                'ticker': order.symbol,
                                'quantity': abs(int(order.qty)),
                                'side': 'buy' if order.side == 'buy' else 'sell',
                                'entry_price': float(order.filled_avg_price) if order.filled_avg_price else 0.0,
                                'exit_price': None,  # Will be set when position is closed
                                'entry_time': convert_to_utc(order.filled_at) if order.filled_at else convert_to_utc(order.created_at),
                                'exit_time': None,
                                'pnl': 0.0,  # Will be calculated when position is closed
                                'commission': float(order.commission) if order.commission else 0.0,
                                'strategy': 'alpaca_sync',
                                'broker': 'alpaca',
                                'alpaca_id': order.id,
                                'status': 'closed' if order.side == 'sell' else 'open',
                                'notes': f"Synced from Alpaca: {order.type} order - {order.status}"
                            }
                            
                            if self.record_trade(trade_data):
                                synced_count += 1
                                logger.info(f"✅ Synced filled order: {order.symbol} {order.qty} @ ${order.filled_avg_price or 'N/A'} (Status: {order.status})")
                            else:
                                error_count += 1
                                logger.error(f"❌ Failed to sync order: {order.symbol}")
                        else:
                            # For non-filled orders, just log them
                            logger.debug(f"⏭️ Skipping non-filled order: {order.symbol} (Status: {order.status})")
                            skipped_count += 1
                    else:
                        # If trade exists, update it with new data
                        updates = {
                            'exit_price': float(order.filled_avg_price) if order.filled_avg_price and order.status == 'filled' else None,
                            'exit_time': convert_to_utc(order.filled_at) if order.filled_at else None,
                            'status': order.status,
                            'notes': f"Synced from Alpaca: {order.type} order - {order.status}"
                        }
                        if self.update_trade(existing_trade['trade_id'], updates):
                            synced_count += 1
                            logger.info(f"✅ Updated existing order: {order.symbol} {order.qty} @ ${order.filled_avg_price or 'N/A'} (Status: {order.status})")
                        else:
                            error_count += 1
                            logger.error(f"❌ Failed to update existing order: {order.symbol}")
                        skipped_count += 1
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Error processing order {getattr(order, 'symbol', 'UNKNOWN')}: {e}")
            
            # Then, sync current positions (these represent filled orders)
            try:
                positions = alpaca_client.get_positions()
                logger.info(f"📈 Found {len(positions)} current positions")
            except Exception as e:
                logger.error(f"❌ Error fetching positions from Alpaca: {e}")
                positions = {}
            
            for ticker, position in positions.items():
                try:
                    quantity = abs(int(position.get('quantity', 0)))
                    side = 'buy' if position.get('quantity', 0) > 0 else 'sell'
                    entry_price = float(position.get('avg_entry_price', 0))
                    unrealized_pl = float(position.get('unrealized_pl', 0))
                    
                    # Check if position already exists in positions table
                    existing_position = self.get_position(ticker, side)
                    
                    if not existing_position:
                        # Create new position in positions table
                        position_success = self.open_position(
                            ticker=ticker,
                            quantity=quantity,
                            side=side,
                            entry_price=entry_price,
                            broker='alpaca',
                            order_id=f"ALPACA_SYNC_{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                        )
                        
                        if position_success:
                            # Update P&L for the position
                            self.update_position_price(ticker, entry_price)
                            synced_count += 1
                            logger.info(f"✅ Created new position: {ticker} {quantity} shares @ ${entry_price}")
                        else:
                            error_count += 1
                            logger.error(f"❌ Failed to create position: {ticker}")
                    else:
                        # Update existing position with latest data
                        self.update_position_price(ticker, entry_price)
                        synced_count += 1
                        logger.info(f"✅ Updated existing position: {ticker} {quantity} shares @ ${entry_price}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Error processing position {ticker}: {e}")
            
            # Clean up positions that no longer exist in Alpaca
            try:
                current_alpaca_tickers = set(positions.keys())
                local_positions = self.get_all_positions()
                cleaned_count = 0
                
                for local_pos in local_positions:
                    if local_pos['ticker'] not in current_alpaca_tickers:
                        # Position no longer exists in Alpaca, close it
                        logger.info(f"🔄 Position {local_pos['ticker']} no longer exists in Alpaca, closing position")
                        
                        try:
                            # Close the position (this will also create a trade record)
                            close_success = self.close_position(
                                ticker=local_pos['ticker'],
                                side=local_pos['side'],
                                exit_price=local_pos.get('entry_price', 0),  # Use entry price as exit price
                                exit_time=get_utc_datetime()
                            )
                            
                            if close_success:
                                cleaned_count += 1
                                logger.info(f"✅ Closed position: {local_pos['ticker']} (no longer in Alpaca)")
                            else:
                                error_count += 1
                                logger.error(f"❌ Failed to close position: {local_pos['ticker']} - close_position returned False")
                                
                                # Fallback: manually close the position using SQL
                                logger.info(f"🔄 Attempting manual SQL close for {local_pos['ticker']}")
                                manual_close_success = self._manual_close_position(
                                    ticker=local_pos['ticker'],
                                    side=local_pos['side'],
                                    exit_price=local_pos.get('entry_price', 0)
                                )
                                
                                if manual_close_success:
                                    cleaned_count += 1
                                    logger.info(f"✅ Manually closed position: {local_pos['ticker']}")
                                else:
                                    error_count += 1
                                    logger.error(f"❌ Manual close also failed for: {local_pos['ticker']}")
                                    
                        except Exception as e:
                            error_count += 1
                            logger.error(f"❌ Exception closing position {local_pos['ticker']}: {e}")
                            
                            # Fallback: manually close the position using SQL
                            try:
                                logger.info(f"🔄 Attempting manual SQL close for {local_pos['ticker']} after exception")
                                manual_close_success = self._manual_close_position(
                                    ticker=local_pos['ticker'],
                                    side=local_pos['side'],
                                    exit_price=local_pos.get('entry_price', 0)
                                )
                                
                                if manual_close_success:
                                    cleaned_count += 1
                                    logger.info(f"✅ Manually closed position after exception: {local_pos['ticker']}")
                                else:
                                    logger.error(f"❌ Manual close failed after exception for: {local_pos['ticker']}")
                            except Exception as manual_e:
                                logger.error(f"❌ Manual close exception for {local_pos['ticker']}: {manual_e}")
                
                if cleaned_count > 0:
                    logger.info(f"🧹 Cleaned up {cleaned_count} positions that no longer exist in Alpaca")
                    
            except Exception as e:
                logger.error(f"❌ Error cleaning up positions: {e}")
            
            logger.info(f"🔄 Sync complete: {synced_count} new trades/positions, {skipped_count} already exist, {error_count} errors, {cleaned_count} cleaned")
            return {
                'success': True,
                'synced_count': synced_count,
                'skipped_count': skipped_count,
                'error_count': error_count,
                'cleaned_count': cleaned_count,
                'total_orders': len(orders),
                'total_positions': len(positions)
            }
            
        except Exception as e:
            logger.error(f"❌ Error syncing trades from Alpaca: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_trade_by_alpaca_id(self, alpaca_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by Alpaca activity ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM trades WHERE alpaca_id = ?', (alpaca_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error getting trade by Alpaca ID: {e}")
            return None

    def cleanup_duplicate_trades(self) -> bool:
        """Clean up duplicate trade entries"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Find and remove duplicate trades based on ticker and side
                cursor.execute('''
                    DELETE FROM trades 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM trades 
                        GROUP BY ticker, side, status
                    )
                ''')
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"🧹 Cleaned up {deleted_count} duplicate trade entries")
                else:
                    logger.info("✅ No duplicate trades found")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up duplicate trades: {e}")
            return False
    
    def _manual_close_position(self, ticker: str, side: str, exit_price: float) -> bool:
        """Manually close a position using direct SQL (fallback method)"""
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
                    logger.warning(f"⚠️ No open position found for manual close: {ticker} {side}")
                    return False
                
                # Calculate P&L
                entry_price = position['entry_price']
                quantity = position['quantity']
                pnl = (exit_price - entry_price) * quantity if side == 'buy' else (entry_price - exit_price) * quantity
                
                # Update position using direct SQL
                cursor.execute('''
                    UPDATE positions 
                    SET exit_price = ?, exit_time = ?, status = 'closed', pnl = ?
                    WHERE ticker = ? AND side = ? AND status = 'open'
                ''', (exit_price, get_utc_datetime(), pnl, ticker, side))
                
                if cursor.rowcount == 0:
                    logger.error(f"❌ Manual close failed - no rows updated for {ticker} {side}")
                    return False
                
                # Create trade record manually
                trade_id = f"{ticker}_{side}_{get_utc_datetime().replace(':', '').replace('-', '').replace('T', '_').split('.')[0]}"
                
                cursor.execute('''
                    INSERT INTO trades (trade_id, ticker, quantity, side, entry_price, exit_price, 
                                     entry_time, exit_time, pnl, commission, strategy, broker, 
                                     alpaca_id, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_id, ticker, quantity, side, entry_price, exit_price,
                    position['entry_time'], get_utc_datetime(), pnl, 0.0,
                    position.get('strategy', 'Manual Close'), position.get('broker', 'alpaca'),
                    position.get('order_id'), 'closed',
                    f"Manually closed position - {side} {quantity} shares"
                ))
                
                conn.commit()
                logger.info(f"📉 Manually closed position: {ticker} {side} @ ${exit_price} P&L: ${pnl:.2f}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error in manual close position: {e}")
            return False

    def convert_closed_positions_to_trades(self) -> bool:
        """Convert any closed positions to trade records"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all closed positions
                cursor.execute('''
                    SELECT * FROM positions 
                    WHERE status = 'closed' AND exit_time IS NOT NULL
                ''')
                
                closed_positions = cursor.fetchall()
                converted_count = 0
                
                for position in closed_positions:
                    # Check if trade already exists
                    existing_trade = self.get_trade_by_alpaca_id(position['order_id'])
                    if existing_trade:
                        logger.debug(f"Trade already exists for {position['ticker']} order {position['order_id']}")
                        continue
                    
                    # Create trade record
                    trade_data = {
                        'trade_id': f"{position['ticker']}_{position['side']}_{get_utc_datetime().replace(':', '').replace('-', '').replace('T', '_').split('.')[0]}",
                        'ticker': position['ticker'],
                        'quantity': position['quantity'],
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': position['exit_price'],
                        'entry_time': position['entry_time'],
                        'exit_time': position['exit_time'],
                        'pnl': position['pnl'],
                        'commission': 0.0,
                        'strategy': position.get('strategy', 'Unknown'),
                        'broker': position.get('broker', 'alpaca'),
                        'alpaca_id': position.get('order_id'),
                        'status': 'closed',
                        'notes': f"Converted from closed position - {position['side']} {position['quantity']} shares"
                    }
                    
                    if self.record_trade(trade_data):
                        converted_count += 1
                        logger.info(f"✅ Converted closed position to trade: {position['ticker']} P&L: ${position['pnl']:.2f}")
                
                if converted_count > 0:
                    logger.info(f"🔄 Converted {converted_count} closed positions to trades")
                else:
                    logger.info("✅ No closed positions to convert")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Error converting closed positions to trades: {e}")
            return False

    def validate_database_consistency(self) -> Dict[str, Any]:
        """Validate database consistency and fix any issues"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check for open positions without corresponding trade records
                cursor.execute('''
                    SELECT p.ticker, p.side, p.quantity, p.entry_price, p.entry_time
                    FROM positions p
                    LEFT JOIN trades t ON p.ticker = t.ticker AND p.side = t.side AND t.status = 'open'
                    WHERE p.status = 'open' AND t.trade_id IS NULL
                ''')
                
                missing_trades = cursor.fetchall()
                fixed_count = 0
                
                for position in missing_trades:
                    logger.info(f"🔧 Creating missing trade record for open position: {position['ticker']}")
                    
                    trade_data = {
                        'trade_id': f"{position['ticker']}_{position['side']}_{get_utc_datetime().replace(':', '').replace('-', '').replace('T', '_').split('.')[0]}",
                        'ticker': position['ticker'],
                        'quantity': position['quantity'],
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': None,
                        'entry_time': position['entry_time'],
                        'exit_time': None,
                        'pnl': 0.0,
                        'commission': 0.0,
                        'strategy': 'Active Position',
                        'broker': 'alpaca',
                        'alpaca_id': f"VALIDATION_{position['ticker']}_{get_utc_datetime().replace(':', '').replace('-', '').replace('T', '_').split('.')[0]}",
                        'status': 'open',
                        'notes': f"Created during validation - {position['side']} {position['quantity']} shares"
                    }
                    
                    if self.record_trade(trade_data):
                        fixed_count += 1
                        logger.info(f"✅ Created missing trade record for {position['ticker']}")
                
                # Check for closed positions without corresponding trade records
                cursor.execute('''
                    SELECT p.ticker, p.side, p.quantity, p.entry_price, p.exit_price, p.entry_time, p.exit_time, p.pnl
                    FROM positions p
                    LEFT JOIN trades t ON p.ticker = t.ticker AND p.side = t.side AND t.status = 'closed'
                    WHERE p.status = 'closed' AND t.trade_id IS NULL
                ''')
                
                missing_closed_trades = cursor.fetchall()
                
                for position in missing_closed_trades:
                    logger.info(f"🔧 Creating missing trade record for closed position: {position['ticker']}")
                    
                    trade_data = {
                        'trade_id': f"{position['ticker']}_{position['side']}_{get_utc_datetime().replace(':', '').replace('-', '').replace('T', '_').split('.')[0]}",
                        'ticker': position['ticker'],
                        'quantity': position['quantity'],
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': position['exit_price'],
                        'entry_time': position['entry_time'],
                        'exit_time': position['exit_time'],
                        'pnl': position['pnl'],
                        'commission': 0.0,
                        'strategy': 'Validation Fix',
                        'broker': 'alpaca',
                        'alpaca_id': f"VALIDATION_CLOSED_{position['ticker']}_{get_utc_datetime().replace(':', '').replace('-', '').replace('T', '_').split('.')[0]}",
                        'status': 'closed',
                        'notes': f"Created during validation - closed {position['side']} {position['quantity']} shares"
                    }
                    
                    if self.record_trade(trade_data):
                        fixed_count += 1
                        logger.info(f"✅ Created missing closed trade record for {position['ticker']}")
                
                return {
                    'success': True,
                    'missing_open_trades': len(missing_trades),
                    'missing_closed_trades': len(missing_closed_trades),
                    'fixed_count': fixed_count
                }
                
        except Exception as e:
            logger.error(f"❌ Error validating database consistency: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Global trading database instance
trading_db = TradingDatabase() 