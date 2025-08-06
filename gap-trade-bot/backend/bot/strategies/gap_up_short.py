#!/usr/bin/env python3
"""
Gap Up Short Strategy
Short stocks that gap up above 40% with specific volume and price conditions

STRATEGY CRITERIA:
==================

ENTRY CONDITIONS:
1. Gap up above 40%
2. Volume between 2x and 10x of 2*avg_volume (4x-20x avg_volume)
3. Time > 10AM 
4. Below premarket high
5. 10% below day high

RISK MANAGEMENT:
- 15% profit target (short position)
- 15% stop loss (short position)
- 70% minimum confidence threshold

VOLUME CALCULATION:
- Volume min threshold = avg_volume * 4 (2x of 2*avg_volume)
- Volume max threshold = avg_volume * 20 (10x of 2*avg_volume)

CONFIDENCE SCORING:
- Gap percentage (0-30 points)
- Volume ratio (0-25 points) 
- Time factor (0-15 points)
- Distance from day high (0-15 points)
- Distance from premarket high (0-15 points)
- Total: 0-100 points
"""

import sys
import os
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from logging_config import get_logger

logger = get_logger(__name__)

class GapUpShortStrategy:
    """Gap Up Short Strategy Implementation"""
    
    def __init__(self):
        self.name = "gap_up_short"
        self.description = "Short stocks with gap up above 40% with volume and price conditions"
        
        # Strategy configuration
        # Load configuration from unified config
        try:
            import sys
            import os
            # Add the backend directory to the path
            # Strategy file is at: backend/bot/strategies/gap_up_short.py
            # Need to go up 2 levels to reach backend directory
            backend_dir = os.path.join(os.path.dirname(__file__), '..', '..')
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            
            from config.strategy_manager import strategy_manager
            backend_config = strategy_manager.get_backend_config('gapUpShort')
            if backend_config:
                # Convert string time to time object
                if 'min_time' in backend_config and isinstance(backend_config['min_time'], str):
                    from datetime import datetime
                    time_obj = datetime.strptime(backend_config['min_time'], '%H:%M').time()
                    backend_config['min_time'] = time_obj
                
                self.config = backend_config
                logger.info(f"✅ Loaded unified config for {self.name}: {self.config}")
            else:
                # Fallback to default config
                self.config = {
                    'min_gap_percentage': 40,  # Minimum gap percentage
                    'volume_min_multiplier': 2.0,  # Minimum volume multiplier
                    'volume_max_multiplier': 10.0,  # Maximum volume multiplier
                    'min_time': time(10, 0),  # Minimum time (10:00 AM)
                    'max_distance_from_day_high': 10.0,  # Maximum 10% below day high
                    'target_multiplier': 0.85,  # 15% profit target (short)
                    'stop_loss_multiplier': 1.15,  # 15% stop loss (short)
                    'confidence_threshold': 70  # Minimum confidence
                }
                logger.warning(f"⚠️ Using fallback config for {self.name}")
        except Exception as e:
            logger.error(f"❌ Error loading unified config for {self.name}: {e}")
            # Fallback to default config
            self.config = {
                'min_gap_percentage': 40,  # Minimum gap percentage
                'volume_min_multiplier': 2.0,  # Minimum volume multiplier
                'volume_max_multiplier': 10.0,  # Maximum volume multiplier
                'min_time': time(10, 0),  # Minimum time (10:00 AM)
                'max_distance_from_day_high': 10.0,  # Maximum 10% below day high
                'target_multiplier': 0.85,  # 15% profit target (short)
                'stop_loss_multiplier': 1.15,  # 15% stop loss (short)
                'confidence_threshold': 70  # Minimum confidence
            }
        
        # Strategy state
        self.entry_price = None
        self.entry_time = None
        self.day_high_at_entry = None
        self.premarket_high_at_entry = None
        self.target_price = None
        self.stop_loss_price = None
        self.position_size = 1000  # Default position size
        
    def analyze_entry_conditions(self, ticker: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if entry conditions are met for gap up short strategy"""
        try:
            current_price = current_data.get('current_price', 0)
            day_high = current_data.get('day_high', 0)
            day_low = current_data.get('day_low', 0)
            gap_percent = current_data.get('gap_percent', 0)
            current_volume = current_data.get('current_volume', 0)
            avg_volume = current_data.get('avg_volume', 1000000)
            current_time = current_data.get('current_time', time(9, 30))
            premarket_high = current_data.get('premarket_high', 0)
            market_status = current_data.get('market_status', 'closed')
            
            # Calculate volume thresholds (2x and 10x of 2*avg_volume)
            volume_min_threshold = avg_volume * 4  # 2x of 2*avg_volume
            volume_max_threshold = avg_volume * 20  # 10x of 2*avg_volume
            
            # Entry conditions
            is_gap_up_above_40 = gap_percent >= self.config['min_gap_percentage']
            is_volume_in_range = volume_min_threshold <= current_volume <= volume_max_threshold
            is_after_10am = current_time >= self.config['min_time']
            is_below_premarket_high = current_price < premarket_high if premarket_high > 0 else True
            is_below_day_high_by_10_percent = ((day_high - current_price) / day_high * 100) >= self.config['max_distance_from_day_high'] if day_high > 0 else False
            is_market_open = market_status == 'open'
            
            # Calculate distances and ratios
            distance_from_day_high = round(((day_high - current_price) / day_high) * 100, 2) if day_high > 0 else 0
            volume_ratio = round(current_volume / avg_volume, 2) if avg_volume > 0 else 0
            distance_from_premarket_high = round(((premarket_high - current_price) / premarket_high) * 100, 2) if premarket_high > 0 else 0
            
            # Log detailed condition analysis
            logger.info(f"🔍 {ticker} - Gap Up Short Strategy Analysis:")
            logger.info(f"   📊 Current Price: ${current_price:.2f}")
            logger.info(f"   📈 Day High: ${day_high:.2f}")
            logger.info(f"   📊 Gap %: {gap_percent:.2f}% (Min: {self.config['min_gap_percentage']}%)")
            logger.info(f"   📊 Volume: {current_volume:,} (Avg: {avg_volume:,}, Ratio: {volume_ratio:.2f}x)")
            logger.info(f"   📊 Volume Range: {volume_min_threshold:,} - {volume_max_threshold:,}")
            logger.info(f"   🕐 Current Time: {current_time.strftime('%H:%M')} (Min: {self.config['min_time'].strftime('%H:%M')})")
            logger.info(f"   📊 Premarket High: ${premarket_high:.2f}")
            logger.info(f"   📊 Distance from Day High: {distance_from_day_high:.2f}%")
            logger.info(f"   📊 Distance from Premarket High: {distance_from_premarket_high:.2f}%")
            
            # Log condition results
            conditions_met = []
            conditions_failed = []
            
            if is_gap_up_above_40:
                conditions_met.append(f"Gap Up Above 40% ({gap_percent:.2f}% >= {self.config['min_gap_percentage']}%)")
            else:
                conditions_failed.append(f"Gap Up Above 40% ({gap_percent:.2f}% < {self.config['min_gap_percentage']}%)")
            
            if is_volume_in_range:
                conditions_met.append(f"Volume in Range ({current_volume:,} between {volume_min_threshold:,} - {volume_max_threshold:,})")
            else:
                conditions_failed.append(f"Volume in Range ({current_volume:,} not between {volume_min_threshold:,} - {volume_max_threshold:,})")
            
            if is_after_10am:
                conditions_met.append(f"After 10AM ({current_time.strftime('%H:%M')} >= {self.config['min_time'].strftime('%H:%M')})")
            else:
                conditions_failed.append(f"After 10AM ({current_time.strftime('%H:%M')} < {self.config['min_time'].strftime('%H:%M')})")
            
            if is_below_premarket_high:
                conditions_met.append(f"Below Premarket High (${current_price:.2f} < ${premarket_high:.2f})")
            else:
                conditions_failed.append(f"Below Premarket High (${current_price:.2f} >= ${premarket_high:.2f})")
            
            if is_below_day_high_by_10_percent:
                conditions_failed.append(f"Below Day High by 10% ({distance_from_day_high:.2f}% >= {self.config['max_distance_from_day_high']}%)")
            else:
                conditions_met.append(f"Below Day High by 10% ({distance_from_day_high:.2f}% < {self.config['max_distance_from_day_high']}%)")
            
            if is_market_open:
                conditions_met.append("Market Open")
            else:
                conditions_failed.append("Market Closed")
            
            # Calculate confidence score
            confidence = self._calculate_confidence(
                gap_percent, current_volume, avg_volume, distance_from_day_high, 
                distance_from_premarket_high, current_time
            )
            
            # Determine if all conditions are met
            all_conditions_met = (
                is_gap_up_above_40 and 
                is_volume_in_range and 
                is_after_10am and 
                is_below_premarket_high and 
                is_below_day_high_by_10_percent and 
                is_market_open
            )
            
            # Log results
            if conditions_met:
                logger.info(f"   ✅ Conditions Met: {', '.join(conditions_met)}")
            if conditions_failed:
                logger.info(f"   ❌ Conditions Failed: {', '.join(conditions_failed)}")
            
            analysis = {
                'ticker': ticker,
                'strategy': self.name,
                'conditions_met': {
                    'gap_up_above_40': is_gap_up_above_40,
                    'volume_in_range': is_volume_in_range,
                    'after_10am': is_after_10am,
                    'below_premarket_high': is_below_premarket_high,
                    'below_day_high_by_10_percent': is_below_day_high_by_10_percent,
                    'market_open': is_market_open,
                    'all_conditions_met': all_conditions_met
                },
                'metrics': {
                    'gap_percent': gap_percent,
                    'volume_ratio': volume_ratio,
                    'distance_from_day_high': distance_from_day_high,
                    'distance_from_premarket_high': distance_from_premarket_high,
                    'current_time': current_time.strftime('%H:%M'),
                    'current_price': current_price,
                    'day_high': day_high,
                    'premarket_high': premarket_high,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume
                },
                'confidence': confidence,
                'conditions_met_list': conditions_met,
                'conditions_failed_list': conditions_failed
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry conditions for {ticker}: {e}")
            return {'error': str(e)}
    
    def _calculate_confidence(self, gap_percent: float, current_volume: int, avg_volume: int, 
                            distance_from_day_high: float, distance_from_premarket_high: float, 
                            current_time: time) -> float:
        """Calculate confidence score for the strategy"""
        try:
            confidence = 0
            
            # Gap percentage contribution (0-30 points)
            if gap_percent >= 50:
                confidence += 30
            elif gap_percent >= 45:
                confidence += 25
            elif gap_percent >= 40:
                confidence += 20
            
            # Volume contribution (0-25 points)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            if 8 <= volume_ratio <= 15:
                confidence += 25
            elif 6 <= volume_ratio <= 18:
                confidence += 20
            elif 4 <= volume_ratio <= 20:
                confidence += 15
            
            # Time contribution (0-15 points)
            if current_time >= time(10, 30):
                confidence += 15
            elif current_time >= time(10, 15):
                confidence += 10
            elif current_time >= time(10, 0):
                confidence += 5
            
            # Distance from day high contribution (0-15 points)
            if 5 <= distance_from_day_high <= 8:
                confidence += 15
            elif 3 <= distance_from_day_high <= 10:
                confidence += 10
            elif 1 <= distance_from_day_high <= 12:
                confidence += 5
            
            # Distance from premarket high contribution (0-15 points)
            if distance_from_premarket_high >= 2:
                confidence += 15
            elif distance_from_premarket_high >= 1:
                confidence += 10
            elif distance_from_premarket_high >= 0.5:
                confidence += 5
            
            return min(confidence, 100)  # Cap at 100
            
        except Exception as e:
            logger.error(f"❌ Error calculating confidence: {e}")
            return 0
    
    def should_enter_position(self, analysis: Dict[str, Any]) -> bool:
        """Determine if we should enter a short position"""
        try:
            conditions_met = analysis.get('conditions_met', {})
            confidence = analysis.get('confidence', 0)
            
            # Check all required conditions individually
            is_gap_up_above_40 = conditions_met.get('gap_up_above_40', False)
            is_volume_in_range = conditions_met.get('volume_in_range', False)
            is_after_10am = conditions_met.get('after_10am', False)
            is_below_premarket_high = conditions_met.get('below_premarket_high', False)
            is_below_day_high_by_10_percent = conditions_met.get('below_day_high_by_10_percent', False)
            is_market_open = conditions_met.get('market_open', False)
            
            # All conditions must be met and confidence above threshold
            all_conditions_met = (
                is_gap_up_above_40 and 
                is_volume_in_range and 
                is_after_10am and 
                is_below_premarket_high and 
                is_below_day_high_by_10_percent and 
                is_market_open
            )
            
            min_confidence = self.config.get('confidence_threshold', 60)  # Get from config or default to 60%
            
            should_enter = all_conditions_met and confidence >= min_confidence
            
            logger.info(f"📊 Gap Up Short Entry Decision: {'YES' if should_enter else 'NO'} (Confidence: {confidence:.1f}% >= {min_confidence}%)")
            
            return should_enter
            
        except Exception as e:
            logger.error(f"❌ Error determining entry: {e}")
            return False
    
    def should_exit_position(self, current_price: float, entry_price: float, 
                           target_price: float, stop_loss_price: float) -> Tuple[bool, str]:
        """Determine if we should exit the short position"""
        try:
            # For short positions, profit when price goes down
            if current_price <= target_price:
                return True, "profit_target"
            if current_price >= stop_loss_price:
                return True, "stop_loss"
            
            return False, "hold"
            
        except Exception as e:
            logger.error(f"❌ Error determining exit: {e}")
            return False, "error"
    
    def calculate_entry_price(self, current_price: float, day_high: float) -> float:
        """Calculate optimal entry price for short position"""
        # Enter at current market price for short and round to nearest cent
        entry_price = round(current_price, 2)
        return entry_price
    
    def calculate_target_price(self, entry_price: float) -> float:
        """Calculate target price for profit taking (short)"""
        target_price = entry_price * self.config['target_multiplier']
        return round(target_price, 2)
    
    def calculate_stop_loss_price(self, entry_price: float) -> float:
        """Calculate stop loss price (short)"""
        stop_loss_price = entry_price * self.config['stop_loss_multiplier']
        return round(stop_loss_price, 2)
    
    def execute_entry(self, ticker: str, current_price: float, day_high: float) -> Dict[str, Any]:
        """Execute short position entry"""
        try:
            self.entry_price = self.calculate_entry_price(current_price, day_high)
            self.entry_time = datetime.now()
            self.day_high_at_entry = day_high
            self.target_price = self.calculate_target_price(self.entry_price)
            self.stop_loss_price = self.calculate_stop_loss_price(self.entry_price)
            
            logger.info(f"📉 SHORT ENTRY - {ticker}:")
            logger.info(f"   Entry Price: ${self.entry_price:.2f}")
            logger.info(f"   Target Price: ${self.target_price:.2f} (15% profit)")
            logger.info(f"   Stop Loss: ${self.stop_loss_price:.2f} (15% loss)")
            logger.info(f"   Position Size: {self.position_size} shares")
            
            return {
                'ticker': ticker,
                'action': 'SHORT_ENTRY',
                'entry_price': self.entry_price,
                'entry_time': self.entry_time,
                'target_price': self.target_price,
                'stop_loss_price': self.stop_loss_price,
                'position_size': self.position_size,
                'day_high_at_entry': self.day_high_at_entry
            }
            
        except Exception as e:
            logger.error(f"❌ Error executing short entry for {ticker}: {e}")
            return {'error': str(e)}
    
    def execute_exit(self, ticker: str, current_price: float, exit_reason: str) -> Dict[str, Any]:
        """Execute short position exit"""
        try:
            if not self.entry_price:
                logger.error("❌ No entry price found for exit")
                return {'error': 'No entry price found'}
            
            # Calculate P&L for short position
            pnl_percent = ((self.entry_price - current_price) / self.entry_price) * 100
            pnl_dollars = (self.entry_price - current_price) * self.position_size
            
            logger.info(f"📉 SHORT EXIT - {ticker}:")
            logger.info(f"   Entry Price: ${self.entry_price:.2f}")
            logger.info(f"   Exit Price: ${current_price:.2f}")
            logger.info(f"   P&L: ${pnl_dollars:.2f} ({pnl_percent:.2f}%)")
            logger.info(f"   Exit Reason: {exit_reason}")
            
            result = {
                'ticker': ticker,
                'action': 'SHORT_EXIT',
                'entry_price': self.entry_price,
                'exit_price': current_price,
                'pnl_percent': pnl_percent,
                'pnl_dollars': pnl_dollars,
                'exit_reason': exit_reason,
                'position_size': self.position_size,
                'entry_time': self.entry_time,
                'exit_time': datetime.now()
            }
            
            # Reset state
            self._reset_state()
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error executing short exit for {ticker}: {e}")
            return {'error': str(e)}
    
    def _reset_state(self):
        """Reset strategy state"""
        self.entry_price = None
        self.entry_time = None
        self.day_high_at_entry = None
        self.premarket_high_at_entry = None
        self.target_price = None
        self.stop_loss_price = None
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get current strategy status"""
        return {
            'name': self.name,
            'description': self.description,
            'config': self.config,
            'has_position': self.entry_price is not None,
            'entry_price': self.entry_price,
            'target_price': self.target_price,
            'stop_loss_price': self.stop_loss_price,
            'entry_time': self.entry_time
        }

def main():
    """Test the strategy"""
    strategy = GapUpShortStrategy()
    
    # Test data
    test_data = {
        'current_price': 15.50,
        'day_high': 18.00,
        'day_low': 14.00,
        'gap_percent': 45.0,
        'current_volume': 8000000,
        'avg_volume': 1000000,
        'current_time': time(10, 30),
        'premarket_high': 16.50,
        'market_status': 'open'
    }
    
    # Test analysis
    analysis = strategy.analyze_entry_conditions('TEST', test_data)
    logger.info(f"Strategy Analysis: {analysis}")
    
    # Test entry decision
    should_enter = strategy.should_enter_position(analysis)
    logger.info(f"Should Enter: {should_enter}")

if __name__ == "__main__":
    main() 