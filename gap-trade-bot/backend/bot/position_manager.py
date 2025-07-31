"""
Position Manager for Trading Bot
Tracks and manages trading positions, P&L, and risk
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from config import config

logger = get_logger(__name__)

class PositionManager:
    """Manages trading positions and P&L tracking"""
    
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self.active_positions = {}  # Current open positions
        self.closed_positions = []  # Recently closed positions
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.max_positions = config.MAX_POSITIONS
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize position tracking database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create positions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trading_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    target_price REAL,
                    stop_loss_price REAL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    pnl REAL,
                    pnl_percent REAL,
                    exit_reason TEXT,
                    status TEXT DEFAULT 'open',
                    holding_time TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create daily P&L table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    total_pnl REAL DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ Position database initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing position database: {e}")
    
    def open_position(self, order: Dict[str, Any]) -> bool:
        """Open a new trading position"""
        try:
            ticker = order.get('ticker')
            
            # Check if we already have a position in this ticker
            if ticker in self.active_positions:
                logger.warning(f"⚠️ Already have position in {ticker}")
                return False
            
            # Check maximum positions limit
            if len(self.active_positions) >= self.max_positions:
                logger.warning(f"⚠️ Maximum positions ({self.max_positions}) reached")
                return False
            
            # Store position
            position = {
                'ticker': ticker,
                'strategy': order.get('strategy'),
                'action': order.get('action'),
                'quantity': order.get('quantity'),
                'entry_price': order.get('entry_price'),
                'target_price': order.get('target_price'),
                'stop_loss_price': order.get('stop_loss_price'),
                'entry_time': order.get('entry_time'),
                'position_value': order.get('position_value'),
                'day_high_at_entry': order.get('day_high_at_entry'),
                'risk_reward_ratio': order.get('risk_reward_ratio')
            }
            
            self.active_positions[ticker] = position
            
            # Store in database
            self._store_position_db(position)
            
            logger.info(f"📈 Opened position: {ticker} @ ${position['entry_price']:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error opening position: {e}")
            return False
    
    def close_position(self, ticker: str, exit_order: Dict[str, Any]) -> bool:
        """Close an existing position"""
        try:
            if ticker not in self.active_positions:
                logger.warning(f"⚠️ No active position found for {ticker}")
                return False
            
            position = self.active_positions[ticker]
            
            # Calculate final P&L
            entry_price = position['entry_price']
            exit_price = exit_order.get('exit_price')
            quantity = position['quantity']
            
            pnl = (exit_price - entry_price) * quantity
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            
            # Update position with exit details
            position.update({
                'exit_price': exit_price,
                'exit_time': exit_order.get('exit_time'),
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'exit_reason': exit_order.get('exit_reason'),
                'holding_time': exit_order.get('holding_time'),
                'status': 'closed'
            })
            
            # Move to closed positions
            self.closed_positions.append(position)
            del self.active_positions[ticker]
            
            # Update P&L tracking
            self.daily_pnl += pnl
            self.total_pnl += pnl
            
            # Update database
            self._update_position_db(ticker, position)
            self._update_daily_pnl(pnl)
            
            # Log result
            pnl_color = "🟢" if pnl > 0 else "🔴"
            logger.info(f"{pnl_color} Closed position: {ticker} | P&L: ${pnl:.2f} ({pnl_percent:.2f}%)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            return False
    
    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get current position for a ticker"""
        return self.active_positions.get(ticker)
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active positions"""
        return self.active_positions.copy()
    
    def get_position_count(self) -> int:
        """Get number of active positions"""
        return len(self.active_positions)
    
    def can_open_position(self, ticker: str) -> bool:
        """Check if we can open a new position"""
        # Check if already have position in this ticker
        if ticker in self.active_positions:
            return False
        
        # Check maximum positions limit
        if len(self.active_positions) >= self.max_positions:
            return False
        
        return True
    
    def update_position_prices(self, ticker: str, current_price: float) -> Optional[Dict[str, Any]]:
        """Update position with current price and check exit conditions"""
        try:
            if ticker not in self.active_positions:
                return None
            
            position = self.active_positions[ticker]
            entry_price = position['entry_price']
            target_price = position['target_price']
            stop_loss_price = position['stop_loss_price']
            
            # Calculate current P&L
            current_pnl = (current_price - entry_price) * position['quantity']
            current_pnl_percent = ((current_price - entry_price) / entry_price) * 100
            
            # Update position with current metrics
            position.update({
                'current_price': current_price,
                'current_pnl': current_pnl,
                'current_pnl_percent': current_pnl_percent,
                'last_updated': datetime.now().isoformat()
            })
            
            # Check exit conditions
            exit_signal = False
            exit_reason = None
            
            if current_price >= target_price:
                exit_signal = True
                exit_reason = "profit_target"
            elif current_price <= stop_loss_price:
                exit_signal = True
                exit_reason = "stop_loss"
            
            if exit_signal:
                return {
                    'ticker': ticker,
                    'exit_signal': True,
                    'exit_reason': exit_reason,
                    'current_price': current_price,
                    'current_pnl': current_pnl,
                    'current_pnl_percent': current_pnl_percent
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error updating position prices: {e}")
            return None
    
    def get_daily_pnl(self) -> float:
        """Get today's P&L"""
        return self.daily_pnl
    
    def get_total_pnl(self) -> float:
        """Get total P&L"""
        return self.total_pnl
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of all positions"""
        try:
            total_positions = len(self.active_positions)
            total_value = sum(pos.get('position_value', 0) for pos in self.active_positions.values())
            
            # Calculate average P&L for active positions
            active_pnl = 0
            if self.active_positions:
                active_pnl = sum(pos.get('current_pnl', 0) for pos in self.active_positions.values())
            
            return {
                'active_positions': total_positions,
                'total_position_value': total_value,
                'daily_pnl': self.daily_pnl,
                'total_pnl': self.total_pnl,
                'active_pnl': active_pnl,
                'max_positions': self.max_positions,
                'available_slots': self.max_positions - total_positions
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting position summary: {e}")
            return {}
    
    def _store_position_db(self, position: Dict[str, Any]):
        """Store position in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trading_positions 
                (ticker, strategy, action, quantity, entry_price, target_price, stop_loss_price, entry_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                position['ticker'],
                position['strategy'],
                position['action'],
                position['quantity'],
                position['entry_price'],
                position['target_price'],
                position['stop_loss_price'],
                position['entry_time']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error storing position in database: {e}")
    
    def _update_position_db(self, ticker: str, position: Dict[str, Any]):
        """Update position in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE trading_positions 
                SET exit_price = ?, exit_time = ?, pnl = ?, pnl_percent = ?, 
                    exit_reason = ?, status = ?, holding_time = ?
                WHERE ticker = ? AND status = 'open'
            ''', (
                position['exit_price'],
                position['exit_time'],
                position['pnl'],
                position['pnl_percent'],
                position['exit_reason'],
                'closed',
                position['holding_time'],
                ticker
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error updating position in database: {e}")
    
    def _update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert or update daily P&L
            cursor.execute('''
                INSERT OR REPLACE INTO daily_pnl (date, total_pnl, total_trades)
                VALUES (?, ?, 1)
            ''', (today, pnl))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error updating daily P&L: {e}")

# Global position manager instance
position_manager = PositionManager() 