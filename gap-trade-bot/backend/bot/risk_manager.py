"""
Risk Manager for Trading Bot
Handles stop-loss, position sizing, and risk management
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config

logger = get_logger(__name__)

class RiskManager:
    """Manages risk and position sizing for trading bot"""
    
    def __init__(self):
        self.max_daily_loss = bot_config.MAX_DAILY_LOSS
        self.max_portfolio_risk = bot_config.MAX_PORTFOLIO_RISK
        self.stop_loss_percentage = bot_config.STOP_LOSS_PERCENTAGE
        self.default_volume = bot_config.DEFAULT_VOLUME
        
        # Risk tracking
        self.daily_loss = 0.0
        self.total_portfolio_value = 0.0
        self.max_position_size = 0.0
        
        # Account-based limits
        self.max_position_value = 10000  # Maximum $10k per position
        self.max_portfolio_concentration = 0.05  # Maximum 5% in single position
        
    def calculate_position_size(self, entry_price: float, stop_loss_price: float, 
                              available_capital: float, ticker: str = None) -> int:
        """Calculate optimal position size based on risk with dynamic limits"""
        try:
            # Calculate risk per share
            risk_per_share = abs(entry_price - stop_loss_price)
            
            if risk_per_share <= 0:
                logger.warning("⚠️ Invalid stop loss price")
                return self.default_volume
            
            # Calculate maximum risk amount (2% of portfolio)
            max_risk_amount = available_capital * self.max_portfolio_risk
            
            # Calculate position size based on risk
            max_shares_by_risk = int(max_risk_amount / risk_per_share)
            
            # Calculate position size based on percentage of portfolio (2%)
            max_position_value = available_capital * 0.02  # 2% of portfolio
            max_shares_by_value = int(max_position_value / entry_price)
            
            # Apply price-based position limits
            max_shares_by_price = self._get_price_based_limit(entry_price)
            
            # For small accounts, use more conservative sizing
            if available_capital < 10000:  # Small account
                max_position_value = available_capital * 0.01  # 1% of portfolio
                max_shares_by_value = int(max_position_value / entry_price)
                max_shares_by_price = min(max_shares_by_price, 500)  # Lower limits for small accounts
            
            # Use the smallest of all limits (but don't limit by default_volume for small accounts)
            if available_capital < 10000:  # Small account
                position_size = min(max_shares_by_risk, max_shares_by_value, max_shares_by_price)
            else:
                position_size = min(max_shares_by_risk, max_shares_by_value, max_shares_by_price, self.default_volume)
            
            # Ensure minimum position size (lower for small accounts)
            if available_capital < 10000:  # Small account
                min_position_size = 10  # Lower minimum for small accounts
            else:
                min_position_size = 100  # Standard minimum
                
            if position_size < min_position_size:
                position_size = min_position_size
            
            # Ensure maximum position size and value limits
            if position_size > 1000:
                position_size = 1000
            
            # Additional check for very expensive stocks
            position_value = entry_price * position_size
            if position_value > self.max_position_value:  # Max $10k per position
                position_size = int(self.max_position_value / entry_price)
                if position_size < 1:
                    position_size = 1  # Minimum 1 share
            
            # For very expensive stocks (>$100), be more conservative
            if entry_price > 100 and position_value > (available_capital * 0.1):  # Max 10% of capital for expensive stocks
                max_shares_for_expensive = int((available_capital * 0.1) / entry_price)
                if max_shares_for_expensive < position_size:
                    position_size = max_shares_for_expensive
                    if position_size < 1:
                        position_size = 1
            
            logger.info(f"📊 Position size calculated for {ticker or 'Unknown'}: {position_size} shares")
            logger.info(f"📊 Entry Price: ${entry_price:.2f}")
            logger.info(f"📊 Risk per share: ${risk_per_share:.2f}")
            logger.info(f"📊 Max risk amount: ${max_risk_amount:.2f}")
            logger.info(f"📊 Max position value: ${max_position_value:.2f}")
            logger.info(f"📊 Price-based limit: {max_shares_by_price} shares")
            
            return position_size
            
        except Exception as e:
            logger.error(f"❌ Error calculating position size: {e}")
            return self.default_volume
    
    def _get_price_based_limit(self, entry_price: float) -> int:
        """Get position size limit based on stock price"""
        try:
            if entry_price < 1:
                return 1000  # Very low-priced stocks: max 1000 shares
            elif entry_price < 5:
                return 500   # Low-priced stocks: max 500 shares
            elif entry_price < 20:
                return 200   # Mid-priced stocks: max 200 shares
            elif entry_price < 100:
                return 100   # High-priced stocks: max 100 shares
            else:
                return 50    # Very expensive stocks: max 50 shares
        except Exception as e:
            logger.error(f"❌ Error calculating price-based limit: {e}")
            return 200
    
    def calculate_stop_loss_price(self, entry_price: float, direction: str = 'long') -> float:
        """Calculate stop loss price"""
        try:
            if direction == 'long':
                stop_loss_price = entry_price * (1 - self.stop_loss_percentage / 100)
            else:  # short
                stop_loss_price = entry_price * (1 + self.stop_loss_percentage / 100)
            
            return round(stop_loss_price, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating stop loss price: {e}")
            return entry_price * 0.85  # Default 15% stop loss
    
    def calculate_target_price(self, entry_price: float, risk_reward_ratio: float = 2.0) -> float:
        """Calculate target price based on risk-reward ratio"""
        try:
            # Calculate stop loss distance
            stop_loss_distance = entry_price * (self.stop_loss_percentage / 100)
            
            # Calculate target distance based on risk-reward ratio
            target_distance = stop_loss_distance * risk_reward_ratio
            
            # Calculate target price
            target_price = entry_price + target_distance
            
            return round(target_price, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating target price: {e}")
            return entry_price * 1.5  # Default 50% target
    
    def check_daily_loss_limit(self, new_loss: float) -> bool:
        """Check if new loss would exceed daily limit"""
        try:
            total_daily_loss = self.daily_loss + new_loss
            
            if total_daily_loss > self.max_daily_loss:
                logger.warning(f"⚠️ Daily loss limit would be exceeded: ${total_daily_loss:.2f}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking daily loss limit: {e}")
            return False
    
    def update_daily_loss(self, loss: float):
        """Update daily loss tracking"""
        try:
            self.daily_loss += loss
            logger.info(f"📊 Updated daily loss: ${self.daily_loss:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Error updating daily loss: {e}")
    
    def reset_daily_loss(self):
        """Reset daily loss at start of new day"""
        try:
            self.daily_loss = 0.0
            logger.info("🔄 Reset daily loss tracking")
            
        except Exception as e:
            logger.error(f"❌ Error resetting daily loss: {e}")
    
    def calculate_risk_metrics(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate risk metrics for a position"""
        try:
            entry_price = position.get('entry_price', 0)
            stop_loss_price = position.get('stop_loss_price', 0)
            quantity = position.get('quantity', 0)
            
            # Calculate risk metrics
            risk_per_share = abs(entry_price - stop_loss_price)
            total_risk = risk_per_share * quantity
            risk_percentage = (risk_per_share / entry_price) * 100
            
            # Calculate potential loss
            potential_loss = total_risk
            
            # Calculate potential profit (if target price is set)
            target_price = position.get('target_price', 0)
            potential_profit = 0
            if target_price > entry_price:
                profit_per_share = target_price - entry_price
                potential_profit = profit_per_share * quantity
            
            # Calculate risk-reward ratio
            risk_reward_ratio = potential_profit / total_risk if total_risk > 0 else 0
            
            metrics = {
                'risk_per_share': round(risk_per_share, 2),
                'total_risk': round(total_risk, 2),
                'risk_percentage': round(risk_percentage, 2),
                'potential_loss': round(potential_loss, 2),
                'potential_profit': round(potential_profit, 2),
                'risk_reward_ratio': round(risk_reward_ratio, 2),
                'position_value': round(entry_price * quantity, 2)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error calculating risk metrics: {e}")
            return {}
    
    def validate_trade_risk(self, ticker: str, entry_price: float, quantity: int, 
                           stop_loss_price: float) -> Tuple[bool, str]:
        """Validate if a trade meets risk requirements"""
        try:
            # Calculate position risk
            risk_per_share = abs(entry_price - stop_loss_price)
            total_risk = risk_per_share * quantity
            
            # Check if risk exceeds daily limit
            if not self.check_daily_loss_limit(total_risk):
                return False, "Daily loss limit exceeded"
            
            # Check if risk percentage is reasonable
            risk_percentage = (risk_per_share / entry_price) * 100
            if risk_percentage > 20:  # Max 20% risk per trade
                return False, f"Risk percentage too high: {risk_percentage:.1f}%"
            
            # Check if position size is reasonable
            position_value = entry_price * quantity
            if position_value > self.max_position_value:  # Max $10k per position
                return False, f"Position value too large: ${position_value:.0f}"
            
            # Check portfolio concentration
            if self.total_portfolio_value > 0:
                concentration = position_value / self.total_portfolio_value
                if concentration > self.max_portfolio_concentration:  # Max 5% concentration
                    return False, f"Portfolio concentration too high: {concentration:.1%}"
            
            # Check if we have enough buying power
            available_capital = self.get_available_capital()
            if position_value > available_capital * 0.5:  # Max 50% of buying power
                return False, f"Position too large for available capital: ${position_value:.0f}"
            
            return True, "Trade risk validated"
            
        except Exception as e:
            logger.error(f"❌ Error validating trade risk: {e}")
            return False, f"Risk validation error: {str(e)}"
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary"""
        try:
            return {
                'daily_loss': round(self.daily_loss, 2),
                'max_daily_loss': self.max_daily_loss,
                'max_portfolio_risk': self.max_portfolio_risk,
                'stop_loss_percentage': self.stop_loss_percentage,
                'default_volume': self.default_volume,
                'daily_loss_remaining': round(self.max_daily_loss - self.daily_loss, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting risk summary: {e}")
            return {}
    
    def should_stop_trading(self) -> bool:
        """Check if trading should be stopped due to risk"""
        try:
            # Stop if daily loss limit reached
            if self.daily_loss >= self.max_daily_loss:
                logger.warning("⚠️ Daily loss limit reached - stopping trading")
                return True
            
            # Stop if daily loss is close to limit (80% of limit)
            if self.daily_loss >= (self.max_daily_loss * 0.8):
                logger.warning("⚠️ Approaching daily loss limit - consider stopping")
                return False  # Warning but don't stop yet
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking if should stop trading: {e}")
            return False

    def get_available_capital(self) -> float:
        """Get real available capital from account"""
        try:
            from bot.alpaca_client import AlpacaClient
            client = AlpacaClient()
            account_info = client.get_account_info()
            
            # Use buying power as available capital
            available_capital = account_info.get('buying_power', 100000)
            portfolio_value = account_info.get('portfolio_value', 100000)
            
            # Update portfolio value for tracking
            self.total_portfolio_value = portfolio_value
            
            logger.info(f"📊 Available capital: ${available_capital:.2f}")
            logger.info(f"📊 Portfolio value: ${portfolio_value:.2f}")
            
            return available_capital
            
        except Exception as e:
            logger.error(f"❌ Error getting available capital: {e}")
            return 100000  # Fallback to $100k

# Global risk manager instance
risk_manager = RiskManager() 