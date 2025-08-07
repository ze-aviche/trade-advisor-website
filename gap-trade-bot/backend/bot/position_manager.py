"""
Position Manager for Trading Bot
Manages open and closed trading positions using dedicated trading database
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config
from bot.trading_database import trading_db

logger = get_logger(__name__)

class PositionManager:
    """Manages trading positions using dedicated database"""
    
    def __init__(self):
        self.positions = {}  # In-memory cache for quick access
        self.load_positions()
        logger.info("✅ Position manager initialized with database backend")
    
    def load_positions(self):
        """Load all open positions from database into memory"""
        try:
            positions = trading_db.get_all_positions()
            self.positions = {}
            
            for position in positions:
                ticker = position['ticker']
                side = position['side']
                key = f"{ticker}_{side}"
                self.positions[key] = position
            
            logger.info(f"📊 Loaded {len(self.positions)} open positions from database")
            
        except Exception as e:
            logger.error(f"❌ Error loading positions: {e}")
    
    def open_position(self, ticker: str, quantity: int, side: str, entry_price: float, 
                     broker: str = 'alpaca', order_id: str = None) -> bool:
        """Open a new position"""
        try:
            # Store in database
            success = trading_db.open_position(ticker, quantity, side, entry_price, broker, order_id)
            
            if success:
                # Update in-memory cache
                key = f"{ticker}_{side}"
                self.positions[key] = {
                    'ticker': ticker,
                    'quantity': quantity,
                    'side': side,
                    'entry_price': entry_price,
                    'entry_time': datetime.now().isoformat(),
                    'status': 'open',
                    'broker': broker,
                    'order_id': order_id,
                    'pnl': 0.0
                }
                
                logger.info(f"📈 Position opened: {ticker} {quantity} shares {side} @ ${entry_price}")
                return True
            else:
                logger.error(f"❌ Failed to open position: {ticker}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error opening position: {e}")
            return False
    
    def close_position(self, ticker: str, side: str, exit_price: float, 
                      exit_time: str = None) -> bool:
        """Close an existing position"""
        try:
            # Close in database
            success = trading_db.close_position(ticker, side, exit_price, exit_time)
            
            if success:
                # Remove from in-memory cache
                key = f"{ticker}_{side}"
                if key in self.positions:
                    position = self.positions[key]
                    entry_price = position['entry_price']
                    quantity = position['quantity']
                    
                    # Calculate P&L
                    if side == 'buy':
                        pnl = (exit_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - exit_price) * quantity
                    
                    # Record trade
                    trade_data = {
                        'trade_id': f"TRADE_{ticker}_{int(datetime.now().timestamp())}",
                        'ticker': ticker,
                        'quantity': quantity,
                        'side': side,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'entry_time': position['entry_time'],
                        'exit_time': exit_time or datetime.now().isoformat(),
                        'pnl': pnl,
                        'commission': 0.0,  # Will be updated from broker
                        'strategy': 'break_out',
                        'broker': position.get('broker', 'alpaca'),
                        'notes': f"Position closed at ${exit_price}"
                    }
                    
                    trading_db.record_trade(trade_data)
                    del self.positions[key]
                    
                    logger.info(f"📉 Position closed: {ticker} {side} @ ${exit_price} P&L: ${pnl:.2f}")
                    return True
                else:
                    logger.warning(f"⚠️ Position not found in memory: {ticker} {side}")
                    return False
            else:
                logger.error(f"❌ Failed to close position: {ticker}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            return False
    
    def get_position(self, ticker: str, side: str = None) -> Optional[Dict[str, Any]]:
        """Get current position for a ticker"""
        try:
            if side:
                key = f"{ticker}_{side}"
                return self.positions.get(key)
            else:
                # Return first position found for ticker
                for key, position in self.positions.items():
                    if position['ticker'] == ticker:
                        return position
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting position: {e}")
            return None
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        try:
            return list(self.positions.values())
        except Exception as e:
            logger.error(f"❌ Error getting all positions: {e}")
            return []
    
    def update_position_prices(self, current_prices: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Update position prices and check for exit conditions"""
        try:
            updated_count = 0
            
            for key, position in self.positions.items():
                ticker = position['ticker']
                current_price = current_prices.get(ticker)
                
                if current_price:
                    # Update in database
                    success = trading_db.update_position_price(ticker, current_price)
                    
                    if success:
                        # Update in-memory cache
                        entry_price = position['entry_price']
                        quantity = position['quantity']
                        side = position['side']
                        
                        if side == 'buy':
                            pnl = (current_price - entry_price) * quantity
                        else:
                            pnl = (entry_price - current_price) * quantity
                        
                        position['pnl'] = pnl
                        updated_count += 1
                        
                        # Check for exit conditions
                        exit_signal = self._check_exit_conditions(ticker, position, current_price)
                        if exit_signal:
                            return exit_signal
            
            if updated_count > 0:
                logger.info(f"📊 Updated prices for {updated_count} positions")
            
            return None  # No exit signal
            
        except Exception as e:
            logger.error(f"❌ Error updating position prices: {e}")
            return None
    
    def _check_exit_conditions(self, ticker: str, position: Dict[str, Any], current_price: float) -> Optional[Dict[str, Any]]:
        """Check if position should be exited based on stop loss or target"""
        try:
            entry_price = position['entry_price']
            quantity = position['quantity']
            side = position['side']
            
            # Get strategy configuration for exit conditions
            from config.strategy_manager import StrategyConfigManager
            strategy_manager = StrategyConfigManager()
            
            # Default to breakOut strategy
            strategy_config = strategy_manager.get_strategy_by_key('breakOut')
            if not strategy_config:
                logger.warning(f"⚠️ No strategy config found for {ticker}")
                return None
            
            backend_config = strategy_config.get('backend_config', {})
            target_multiplier = backend_config.get('target_multiplier', 1.25)
            stop_loss_multiplier = backend_config.get('stop_loss_multiplier', 0.85)
            
            # Calculate target and stop loss prices
            target_price = entry_price * target_multiplier
            stop_loss_price = entry_price * stop_loss_multiplier
            
            # Check exit conditions
            if side == 'buy':
                # Long position exit conditions
                if current_price <= stop_loss_price:
                    logger.warning(f"🚨 STOP LOSS TRIGGERED: {ticker} - Current: ${current_price:.2f} <= Stop: ${stop_loss_price:.2f}")
                    return {
                        'exit_signal': True,
                        'exit_reason': 'stop_loss',
                        'ticker': ticker,
                        'current_price': current_price,
                        'target_price': target_price,
                        'stop_loss_price': stop_loss_price
                    }
                elif current_price >= target_price:
                    logger.info(f"🎯 TARGET REACHED: {ticker} - Current: ${current_price:.2f} >= Target: ${target_price:.2f}")
                    return {
                        'exit_signal': True,
                        'exit_reason': 'target_reached',
                        'ticker': ticker,
                        'current_price': current_price,
                        'target_price': target_price,
                        'stop_loss_price': stop_loss_price
                    }
            else:
                # Short position exit conditions (reverse logic)
                if current_price >= stop_loss_price:
                    logger.warning(f"🚨 STOP LOSS TRIGGERED: {ticker} - Current: ${current_price:.2f} >= Stop: ${stop_loss_price:.2f}")
                    return {
                        'exit_signal': True,
                        'exit_reason': 'stop_loss',
                        'ticker': ticker,
                        'current_price': current_price,
                        'target_price': target_price,
                        'stop_loss_price': stop_loss_price
                    }
                elif current_price <= target_price:
                    logger.info(f"🎯 TARGET REACHED: {ticker} - Current: ${current_price:.2f} <= Target: ${target_price:.2f}")
                    return {
                        'exit_signal': True,
                        'exit_reason': 'target_reached',
                        'ticker': ticker,
                        'current_price': current_price,
                        'target_price': target_price,
                        'stop_loss_price': stop_loss_price
                    }
            
            return None  # No exit condition met
            
        except Exception as e:
            logger.error(f"❌ Error checking exit conditions for {ticker}: {e}")
            return None
    
    def can_open_position(self, ticker: str, side: str) -> bool:
        """Check if we can open a position for this ticker/side"""
        try:
            key = f"{ticker}_{side}"
            return key not in self.positions
        except Exception as e:
            logger.error(f"❌ Error checking position availability: {e}")
            return False
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of all positions"""
        try:
            total_positions = len(self.positions)
            total_value = 0.0
            total_pnl = 0.0
            
            for position in self.positions.values():
                quantity = position['quantity']
                entry_price = position['entry_price']
                pnl = position.get('pnl', 0.0)
                
                total_value += quantity * entry_price
                total_pnl += pnl
            
            return {
                'total_positions': total_positions,
                'total_value': total_value,
                'total_pnl': total_pnl,
                'positions': list(self.positions.values())
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting position summary: {e}")
            return {}
    
    def refresh_positions(self):
        """Refresh positions from database"""
        try:
            self.load_positions()
            logger.info("🔄 Positions refreshed from database")
        except Exception as e:
            logger.error(f"❌ Error refreshing positions: {e}")
    
    def get_positions_by_broker(self, broker: str) -> List[Dict[str, Any]]:
        """Get positions for a specific broker"""
        try:
            return [pos for pos in self.positions.values() if pos.get('broker') == broker]
        except Exception as e:
            logger.error(f"❌ Error getting positions by broker: {e}")
            return []
    
    def get_positions_by_strategy(self, strategy: str) -> List[Dict[str, Any]]:
        """Get positions for a specific strategy"""
        try:
            return [pos for pos in self.positions.values() if pos.get('strategy') == strategy]
        except Exception as e:
            logger.error(f"❌ Error getting positions by strategy: {e}")
            return []
    
    def get_largest_positions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get largest positions by value"""
        try:
            positions = list(self.positions.values())
            positions.sort(key=lambda x: x['quantity'] * x['entry_price'], reverse=True)
            return positions[:limit]
        except Exception as e:
            logger.error(f"❌ Error getting largest positions: {e}")
            return []
    
    def get_profitable_positions(self) -> List[Dict[str, Any]]:
        """Get positions with positive P&L"""
        try:
            return [pos for pos in self.positions.values() if pos.get('pnl', 0) > 0]
        except Exception as e:
            logger.error(f"❌ Error getting profitable positions: {e}")
            return []
    
    def get_losing_positions(self) -> List[Dict[str, Any]]:
        """Get positions with negative P&L"""
        try:
            return [pos for pos in self.positions.values() if pos.get('pnl', 0) < 0]
        except Exception as e:
            logger.error(f"❌ Error getting losing positions: {e}")
            return []

# Global position manager instance
position_manager = PositionManager() 