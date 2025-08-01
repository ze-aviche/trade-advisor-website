"""
Break Out Strategy
Buy when price breaks above the day's high with volume confirmation

STRATEGY CRITERIA:
==================

ENTRY CONDITIONS:
1. Gap up above 25%
2. Price breaks above day high (HOD)
3. Market must be open
4. Price above VWAP (Volume Weighted Average Price)
5. Sufficient volume (minimum 500,000 shares)
6. Volume >= 2x average volume for breakout confirmation

RISK MANAGEMENT:
- 50% profit target (long position)
- 15% stop loss (long position)
- 60% minimum confidence threshold

VOLUME REQUIREMENTS:
- Minimum volume: 500,000 shares
- High volume threshold: 2,000,000 shares (for +20 confidence)
- Volume multiplier: 2.0x average volume for breakout
- Volume forecast analysis for confidence scoring

CONFIDENCE SCORING:
- Gap percentage (0-25 points)
- Volume ratio vs average (0-25 points)
- Distance from VWAP (0-20 points)
- Market conditions (0-15 points)
- Time of day factor (0-15 points)
- Total: 0-100 points

BREAKOUT LOGIC:
- Waits for price to break above the day's high
- Requires volume confirmation (2x average volume)
- Uses VWAP as additional support/resistance level
- Implements dynamic volume multipliers based on market conditions
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from logging_config import get_logger

logger = get_logger(__name__)

class BreakOutStrategy:
    """Break Out Strategy Implementation"""
    
    def __init__(self):
        self.name = "break_out"
        self.description = "Buy when price breaks above day high with volume confirmation"
        
        # Strategy configuration - self-contained
        self.config = {
            'target_multiplier': 1.5,  # 50% profit target
            'stop_loss_multiplier': 0.85,  # 15% stop loss
            'min_gap_percentage': 25,  # Minimum gap percentage
            'volume_threshold': 4000000,  # Minimum volume (4 million)
            'confidence_threshold': 60  # Minimum confidence
        }
        
        # Strategy state
        self.entry_price = None
        self.entry_time = None
        self.day_high_at_entry = None
        self.target_price = None
        self.stop_loss_price = None
        self.position_size = 1000  # Default position size
        
        # Volume thresholds
        self.min_volume = 4000000  # Minimum volume for consideration (4 million)
        self.high_volume_threshold = 2000000  # Volume threshold for +20 confidence
        self.volume_multiplier = 2.0  # Volume should be 2x average for breakout
        
    def analyze_entry_conditions(self, ticker: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if entry conditions are met"""
        try:
            current_price = current_data.get('current_price', 0)
            day_high = current_data.get('day_high', 0)
            gap_percent = current_data.get('gap_percent', 0)
            market_status = current_data.get('market_status', 'closed')
            current_volume = current_data.get('current_volume', 0)
            vwap = current_data.get('vwap', 0)
            avg_volume = current_data.get('avg_volume', 1000000)  # Default average volume
            
            # Get volume analysis from historical comparison
            volume_analysis = current_data.get('volume_analysis', {})
            forecasted_volume = volume_analysis.get('forecasted_volume', current_volume)
            current_time = volume_analysis.get('current_time', 'Unknown')
            hours_remaining = volume_analysis.get('trading_hours_remaining', 6.5)
            
            # Entry conditions
            is_gap_up = gap_percent >= self.config['min_gap_percentage']
            is_above_hod = current_price > day_high
            is_market_active = market_status in ['open', 'pre_market', 'after_hours']
            is_above_vwap = current_price > vwap if vwap > 0 else True
            has_sufficient_volume = forecasted_volume >= self.min_volume
            has_breakout_volume = forecasted_volume >= (avg_volume * self.volume_multiplier)
            
            # Calculate distances
            distance_from_hod = round(((current_price - day_high) / day_high) * 100, 2) if day_high > 0 else 0
            distance_from_vwap = round(((current_price - vwap) / vwap) * 100, 2) if vwap > 0 else 0
            volume_ratio = round(forecasted_volume / avg_volume, 2) if avg_volume > 0 else 0
            
            # Log detailed condition analysis
            logger.info(f"🔍 {ticker} - Break Out Strategy Analysis:")
            logger.info(f"   📊 Current Price: ${current_price:.2f}")
            logger.info(f"   📈 Day High: ${day_high:.2f}")
            logger.info(f"   📊 Gap %: {gap_percent:.2f}% (Min: {self.config['min_gap_percentage']}%)")
            logger.info(f"   📊 VWAP: ${vwap:.2f}")
            logger.info(f"   📊 Volume: {current_volume:,} (Forecasted: {forecasted_volume:,})")
            logger.info(f"   📊 Avg Volume: {avg_volume:,} (Ratio: {volume_ratio:.2f}x)")
            
            # Log condition results
            conditions_met = []
            conditions_failed = []
            
            if is_gap_up:
                conditions_met.append(f"Gap Up ({gap_percent:.2f}% >= {self.config['min_gap_percentage']}%)")
            else:
                conditions_failed.append(f"Gap Up ({gap_percent:.2f}% < {self.config['min_gap_percentage']}%)")
            
            if is_above_hod:
                conditions_met.append(f"Above HOD (${current_price:.2f} > ${day_high:.2f})")
            else:
                conditions_failed.append(f"Above HOD (${current_price:.2f} <= ${day_high:.2f})")
            
            if is_market_active:
                conditions_met.append(f"Market Active ({market_status})")
            else:
                conditions_failed.append(f"Market Closed ({market_status})")
            
            if is_above_vwap:
                conditions_met.append(f"Above VWAP (${current_price:.2f} > ${vwap:.2f})")
            else:
                conditions_failed.append(f"Below VWAP (${current_price:.2f} <= ${vwap:.2f})")
            
            if has_sufficient_volume:
                conditions_met.append(f"Sufficient Volume ({forecasted_volume:,} >= {self.min_volume:,})")
            else:
                conditions_failed.append(f"Insufficient Volume ({forecasted_volume:,} < {self.min_volume:,})")
            
            if has_breakout_volume:
                conditions_met.append(f"Breakout Volume ({volume_ratio:.2f}x avg)")
            else:
                conditions_failed.append(f"Weak Volume ({volume_ratio:.2f}x avg)")
            
            logger.info(f"   ✅ Conditions Met: {len(conditions_met)}/{6}")
            logger.info(f"   ❌ Conditions Failed: {len(conditions_failed)}/{6}")
            
            for condition in conditions_met:
                logger.info(f"      ✅ {condition}")
            for condition in conditions_failed:
                logger.info(f"      ❌ {condition}")
            
            analysis = {
                'ticker': ticker,
                'strategy': self.name,
                'conditions_met': {
                    'is_gap_up': is_gap_up,
                    'is_above_hod': is_above_hod,
                    'is_market_active': is_market_active,
                    'is_above_vwap': is_above_vwap,
                    'has_sufficient_volume': has_sufficient_volume,
                    'has_breakout_volume': has_breakout_volume,
                    'all_conditions_met': (
                        is_gap_up and 
                        is_above_hod and 
                        is_market_active and 
                        is_above_vwap and 
                        has_sufficient_volume and 
                        has_breakout_volume
                    )
                },
                'current_metrics': {
                    'current_price': current_price,
                    'day_high': day_high,
                    'gap_percent': gap_percent,
                    'distance_from_hod': distance_from_hod,
                    'distance_from_vwap': distance_from_vwap,
                    'market_status': market_status,
                    'current_volume': current_volume,
                    'forecasted_volume': forecasted_volume,
                    'avg_volume': avg_volume,
                    'volume_ratio': volume_ratio,
                    'vwap': vwap,
                    'current_time': current_time,
                    'hours_remaining': hours_remaining
                },
                'entry_signal': (
                    is_gap_up and 
                    is_above_hod and 
                    is_market_open and 
                    is_above_vwap and 
                    has_sufficient_volume and 
                    has_breakout_volume
                ),
                'confidence': self._calculate_confidence(current_data)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry conditions for {ticker}: {e}")
            return {'error': str(e)}
    
    def calculate_entry_price(self, current_price: float, day_high: float) -> float:
        """Calculate optimal entry price"""
        # Enter at current price when breaking above HOD
        return current_price
    
    def calculate_target_price(self, entry_price: float) -> float:
        """Calculate target price for profit taking"""
        target_multiplier = self.config.get('target_multiplier', 1.5)
        return entry_price * target_multiplier
    
    def calculate_stop_loss_price(self, entry_price: float) -> float:
        """Calculate stop loss price"""
        stop_loss_multiplier = self.config.get('stop_loss_multiplier', 0.85)
        return entry_price * stop_loss_multiplier
    
    def should_enter_position(self, analysis: Dict[str, Any]) -> bool:
        """Determine if we should enter a position"""
        try:
            conditions_met = analysis.get('conditions_met', {})
            confidence = analysis.get('confidence', 0)
            
            # All conditions must be met and confidence above threshold
            all_conditions = conditions_met.get('all_conditions_met', False)
            min_confidence = 60  # 60% confidence threshold
            
            return all_conditions and confidence >= min_confidence
            
        except Exception as e:
            logger.error(f"❌ Error determining entry: {e}")
            return False
    
    def should_exit_position(self, current_price: float, entry_price: float, 
                           target_price: float, stop_loss_price: float) -> Tuple[bool, str]:
        """Determine if we should exit the position"""
        try:
            # Check for profit target hit
            if current_price >= target_price:
                return True, "profit_target"
            
            # Check for stop loss hit
            if current_price <= stop_loss_price:
                return True, "stop_loss"
            
            # Check for trailing stop (if price drops significantly from entry)
            trailing_stop_percent = 10  # 10% trailing stop
            trailing_stop_price = entry_price * (1 - trailing_stop_percent / 100)
            
            if current_price <= trailing_stop_price:
                return True, "trailing_stop"
            
            return False, "hold"
            
        except Exception as e:
            logger.error(f"❌ Error determining exit: {e}")
            return False, "error"
    
    def execute_entry(self, ticker: str, current_price: float, day_high: float) -> Dict[str, Any]:
        """Execute entry order"""
        try:
            # Calculate prices
            entry_price = self.calculate_entry_price(current_price, day_high)
            target_price = self.calculate_target_price(entry_price)
            stop_loss_price = self.calculate_stop_loss_price(entry_price)
            
            # Store entry details
            self.entry_price = entry_price
            self.entry_time = datetime.now()
            self.day_high_at_entry = day_high
            self.target_price = target_price
            self.stop_loss_price = stop_loss_price
            
            # Calculate position value
            position_value = entry_price * self.position_size
            
            entry_order = {
                'ticker': ticker,
                'strategy': self.name,
                'action': 'buy',
                'quantity': self.position_size,
                'entry_price': entry_price,
                'target_price': target_price,
                'stop_loss_price': stop_loss_price,
                'entry_time': self.entry_time.isoformat(),
                'position_value': position_value,
                'day_high_at_entry': day_high,
                'risk_reward_ratio': (target_price - entry_price) / (entry_price - stop_loss_price)
            }
            
            logger.info(f"🚀 Executing BUY order for {ticker}: {self.position_size} shares @ ${entry_price:.2f}")
            logger.info(f"📊 Target: ${target_price:.2f} | Stop: ${stop_loss_price:.2f}")
            
            return entry_order
            
        except Exception as e:
            logger.error(f"❌ Error executing entry for {ticker}: {e}")
            return {'error': str(e)}
    
    def execute_exit(self, ticker: str, current_price: float, exit_reason: str) -> Dict[str, Any]:
        """Execute exit order"""
        try:
            if not self.entry_price:
                logger.warning(f"⚠️ No entry price found for {ticker}")
                return {'error': 'No entry price'}
            
            # Calculate P&L
            price_change = current_price - self.entry_price
            price_change_percent = (price_change / self.entry_price) * 100
            total_pnl = price_change * self.position_size
            
            # Calculate holding time
            holding_time = datetime.now() - self.entry_time if self.entry_time else timedelta(0)
            
            exit_order = {
                'ticker': ticker,
                'strategy': self.name,
                'action': 'sell',
                'quantity': self.position_size,
                'exit_price': current_price,
                'entry_price': self.entry_price,
                'price_change': price_change,
                'price_change_percent': price_change_percent,
                'total_pnl': total_pnl,
                'exit_reason': exit_reason,
                'exit_time': datetime.now().isoformat(),
                'holding_time': str(holding_time),
                'target_price': self.target_price,
                'stop_loss_price': self.stop_loss_price
            }
            
            # Log exit details
            pnl_color = "🟢" if total_pnl > 0 else "🔴"
            logger.info(f"{pnl_color} Executing SELL order for {ticker}: {self.position_size} shares @ ${current_price:.2f}")
            logger.info(f"📊 P&L: ${total_pnl:.2f} ({price_change_percent:.2f}%) | Reason: {exit_reason}")
            
            # Reset strategy state
            self._reset_state()
            
            return exit_order
            
        except Exception as e:
            logger.error(f"❌ Error executing exit for {ticker}: {e}")
            return {'error': str(e)}
    
    def _calculate_confidence(self, current_data: Dict[str, Any]) -> float:
        """Calculate confidence level for the trade"""
        try:
            confidence = 50.0  # Base confidence
            
            # Factors that increase confidence
            gap_percent = current_data.get('gap_percent', 0)
            if gap_percent > 50:
                confidence += 20
            elif gap_percent > 30:
                confidence += 10
            
            # Volume factor - use forecasted volume
            current_volume = current_data.get('current_volume', 0)
            forecasted_volume = current_data.get('forecasted_volume', current_volume)
            avg_volume = current_data.get('avg_volume', 1000000)
            
            if forecasted_volume >= self.high_volume_threshold:
                confidence += 20  # +20 for huge volume
                logger.info(f"📊 Huge volume forecasted: {forecasted_volume:,} vs avg {avg_volume:,} (+20 confidence)")
            elif forecasted_volume >= (avg_volume * self.volume_multiplier):
                confidence += 15  # +15 for breakout volume
                logger.info(f"📊 Breakout volume forecasted: {forecasted_volume:,} vs avg {avg_volume:,} (+15 confidence)")
            elif forecasted_volume >= self.min_volume:
                confidence += 10  # +10 for sufficient volume
                logger.info(f"📊 Sufficient volume forecasted: {forecasted_volume:,} (+10 confidence)")
            
            # VWAP factor
            current_price = current_data.get('current_price', 0)
            vwap = current_data.get('vwap', 0)
            
            if vwap > 0 and current_price > vwap:
                confidence += 10  # +10 for being above VWAP
                logger.info(f"📊 Price above VWAP: ${current_price:.2f} > ${vwap:.2f} (+10 confidence)")
            
            # Market status factor
            market_status = current_data.get('market_status', 'closed')
            if market_status in ['open', 'pre_market', 'after_hours']:
                confidence += 10
            
            # Time-based factor (more confidence earlier in the day)
            hours_remaining = current_data.get('hours_remaining', 6.5)
            if hours_remaining >= 5.0:  # Early in the day
                confidence += 5
                logger.info(f"📊 Early trading day: {hours_remaining:.1f} hours remaining (+5 confidence)")
            elif hours_remaining <= 1.0:  # Late in the day
                confidence -= 5
                logger.info(f"📊 Late trading day: {hours_remaining:.1f} hours remaining (-5 confidence)")
            
            # Cap confidence at 100%
            return min(confidence, 100.0)
            
        except Exception as e:
            logger.error(f"❌ Error calculating confidence: {e}")
            return 50.0
    
    def _reset_state(self):
        """Reset strategy state after exit"""
        self.entry_price = None
        self.entry_time = None
        self.day_high_at_entry = None
        self.target_price = None
        self.stop_loss_price = None
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get current strategy status"""
        return {
            'name': self.name,
            'description': self.description,
            'has_position': self.entry_price is not None,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'target_price': self.target_price,
            'stop_loss_price': self.stop_loss_price,
            'position_size': self.position_size,
            'volume_thresholds': {
                'min_volume': self.min_volume,
                'high_volume_threshold': self.high_volume_threshold,
                'volume_multiplier': self.volume_multiplier
            }
        } 

def get_dynamic_volume_multiplier(self, market_conditions: str) -> float:
    """Get volume multiplier based on market conditions"""
    if market_conditions == 'bull_market':
        return 1.5
    elif market_conditions == 'bear_market':
        return 2.5
    else:
        return 2.0  # Default 