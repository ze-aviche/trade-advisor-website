"""
Data Manager for Trading Bot
Handles real-time data, historical data comparison, and market data analysis
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
import sqlite3

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from config import config
from historical_data import get_historical_gap_up_data, get_polygon_client
from websocket_client import websocket_client

# Import the existing gap-up detector
from gap_up_detector import get_gap_up_stocks as get_real_gap_ups

logger = get_logger(__name__)

class DataManager:
    """Manages real-time and historical data for the trading bot"""
    
    def __init__(self):
        self.polygon_client = get_polygon_client()
        self.websocket_client = websocket_client
        self.real_time_cache = {}  # Cache for real-time data
        self.last_update = {}  # Track last update time for each ticker
        self.update_interval = 1  # Update interval in seconds
        logger.info("✅ Data manager initialized with WebSocket integration")
    
    def get_market_status(self) -> str:
        """Get current market status"""
        try:
            # Simple market hours check (9:30 AM - 4:00 PM ET)
            now = datetime.now()
            et_time = now.replace(tzinfo=timezone(timedelta(hours=-5)))
            
            # Check if it's a weekday
            if et_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return 'closed'
            
            # Check market hours (9:30 AM - 4:00 PM ET)
            market_open = et_time.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = et_time.replace(hour=16, minute=0, second=0, microsecond=0)
            
            if market_open <= et_time <= market_close:
                return 'open'
            else:
                return 'closed'
                
        except Exception as e:
            logger.error(f"❌ Error getting market status: {e}")
            return 'closed'
    
    def get_gap_up_stocks(self) -> List[str]:
        """Get stocks that actually gapped up today (real-time)"""
        try:
            logger.info("🔍 Scanning for real-time gap-ups using gap_up_detector...")
            
            # Use the existing gap-up detector
            gap_up_data = get_real_gap_ups()
            
            if not gap_up_data:
                logger.warning("⚠️ No gap-up stocks found")
                return []
            
            # Extract ticker symbols from the gap-up data
            gap_up_stocks = []
            for stock in gap_up_data:
                ticker = stock.get('ticker')
                gap_percent = stock.get('gap_percent', 0)
                
                if ticker and gap_percent >= config.MIN_GAP_PERCENTAGE:
                    gap_up_stocks.append(ticker)
                    logger.info(f"📈 Found gap-up: {ticker} (+{gap_percent:.1f}%)")
            
            logger.info(f"📊 Found {len(gap_up_stocks)} stocks with real-time gap-ups today")
            return gap_up_stocks
            
        except Exception as e:
            logger.error(f"❌ Error getting gap-up stocks: {e}")
            return []
    
    def get_real_time_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get real-time data for a ticker (WebSocket + REST fallback)"""
        try:
            current_time = time.time()
            last_update = self.last_update.get(ticker, 0)
            
            # Check if we have recent WebSocket data
            if (current_time - last_update) < self.update_interval:
                cached_data = self.real_time_cache.get(ticker)
                if cached_data:
                    logger.debug(f"📊 Using cached data for {ticker}")
                    return cached_data
            
            # Try to get data from WebSocket first
            websocket_data = self._get_websocket_data(ticker)
            if websocket_data:
                self.real_time_cache[ticker] = websocket_data
                self.last_update[ticker] = current_time
                return websocket_data
            
            # Fallback to REST API
            rest_data = self._get_rest_data(ticker)
            if rest_data:
                self.real_time_cache[ticker] = rest_data
                self.last_update[ticker] = current_time
                return rest_data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting real-time data for {ticker}: {e}")
            return None
    
    def _get_websocket_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get real-time data from WebSocket"""
        try:
            if not self.websocket_client.is_connected:
                return None
            
            # Get current price from WebSocket
            current_price = self.websocket_client.get_current_price(ticker)
            if not current_price:
                return None
            
            # Get VWAP from WebSocket
            vwap = self.websocket_client.get_current_vwap(ticker)
            
            # Get additional data from REST API (once per day)
            daily_data = self._get_daily_data_once(ticker)
            if not daily_data:
                return None
            
            # Calculate metrics
            current_volume = daily_data.get('volume', 0)
            day_high = daily_data.get('high', current_price)
            day_low = daily_data.get('low', current_price)
            day_open = daily_data.get('open', current_price)
            gap_percent = daily_data.get('gap_percent', 0)
            
            # Calculate average volume (cached)
            avg_volume = self._get_cached_average_volume(ticker)
            
            real_time_data = {
                'ticker': ticker,
                'current_price': current_price,
                'current_volume': current_volume,
                'day_high': day_high,
                'day_low': day_low,
                'day_open': day_open,
                'gap_percent': gap_percent,
                'vwap': vwap or 0,
                'avg_volume': avg_volume,
                'timestamp': datetime.now().isoformat(),
                'market_status': self.get_market_status(),
                'data_source': 'websocket'
            }
            
            logger.debug(f"📊 WebSocket data for {ticker}: ${current_price:.2f}")
            return real_time_data
            
        except Exception as e:
            logger.error(f"❌ Error getting WebSocket data for {ticker}: {e}")
            return None
    
    def _get_rest_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get real-time data from REST API (fallback)"""
        try:
            # Get current price and volume
            ticker_details = self.polygon_client.get_last_trade(ticker)
            
            if not ticker_details:
                return None
            
            # Get daily aggregates for today
            today = datetime.now().strftime('%Y-%m-%d')
            daily_data = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=today,
                to=today,
                adjusted="true"
            )
            
            if not daily_data:
                return None
            
            daily = daily_data[0]
            
            # Calculate current metrics
            current_price = ticker_details.price
            current_volume = daily.volume
            day_high = daily.high
            day_low = daily.low
            day_open = daily.open
            
            # Calculate VWAP (Volume Weighted Average Price)
            vwap = self._calculate_vwap(ticker, today)
            
            # Calculate average volume (20-day average)
            avg_volume = self._calculate_average_volume(ticker)
            
            # Calculate gap percentage
            gap_percent = None
            if day_open and daily.close:  # Use previous close as reference
                gap_percent = round(((day_open - daily.close) / daily.close) * 100, 2)
            
            real_time_data = {
                'ticker': ticker,
                'current_price': current_price,
                'current_volume': current_volume,
                'day_high': day_high,
                'day_low': day_low,
                'day_open': day_open,
                'gap_percent': gap_percent,
                'vwap': vwap,
                'avg_volume': avg_volume,
                'timestamp': datetime.now().isoformat(),
                'market_status': self.get_market_status(),
                'data_source': 'rest_api'
            }
            
            logger.debug(f"📊 REST API data for {ticker}: ${current_price:.2f}")
            return real_time_data
            
        except Exception as e:
            logger.error(f"❌ Error getting REST data for {ticker}: {e}")
            return None
    
    def _get_daily_data_once(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get daily data once per day (cached)"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{ticker}_{today}"
            
            # Check if we already have today's data
            if hasattr(self, '_daily_cache') and cache_key in self._daily_cache:
                return self._daily_cache[cache_key]
            
            # Get daily data from REST API
            daily_data = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=today,
                to=today,
                adjusted="true"
            )
            
            if not daily_data:
                return None
            
            daily = daily_data[0]
            
            # Calculate gap percentage
            gap_percent = None
            if daily.open and daily.close:
                gap_percent = round(((daily.open - daily.close) / daily.close) * 100, 2)
            
            data = {
                'volume': daily.volume,
                'high': daily.high,
                'low': daily.low,
                'open': daily.open,
                'gap_percent': gap_percent
            }
            
            # Cache the data
            if not hasattr(self, '_daily_cache'):
                self._daily_cache = {}
            self._daily_cache[cache_key] = data
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Error getting daily data for {ticker}: {e}")
            return None
    
    def _get_cached_average_volume(self, ticker: str) -> int:
        """Get cached average volume (calculated once per day)"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{ticker}_avg_vol_{today}"
            
            # Check if we already have today's average volume
            if hasattr(self, '_avg_volume_cache') and cache_key in self._avg_volume_cache:
                return self._avg_volume_cache[cache_key]
            
            # Calculate average volume
            avg_volume = self._calculate_average_volume(ticker)
            
            # Cache the result
            if not hasattr(self, '_avg_volume_cache'):
                self._avg_volume_cache = {}
            self._avg_volume_cache[cache_key] = avg_volume
            
            return avg_volume
            
        except Exception as e:
            logger.error(f"❌ Error getting cached average volume for {ticker}: {e}")
            return 1000000  # Default
    
    def _calculate_vwap(self, ticker: str, date: str) -> float:
        """Calculate VWAP for a given ticker and date"""
        try:
            # Get minute-by-minute data for the day
            minute_data = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="minute",
                from_=date,
                to=date,
                adjusted="true"
            )
            
            if not minute_data:
                return 0.0
            
            # Calculate VWAP: (Σ Price × Volume) / Σ Volume
            total_pv = 0.0  # Price × Volume
            total_volume = 0.0
            
            for bar in minute_data:
                price = (bar.high + bar.low + bar.close) / 3  # Typical price
                volume = bar.volume
                
                total_pv += price * volume
                total_volume += volume
            
            vwap = total_pv / total_volume if total_volume > 0 else 0.0
            return round(vwap, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating VWAP for {ticker}: {e}")
            return 0.0
    
    def _calculate_average_volume(self, ticker: str) -> int:
        """Calculate 20-day average volume for a ticker (industry standard)"""
        try:
            # Get daily data for the last 20 trading days (industry standard)
            end_date = datetime.now()
            
            # Calculate 20 trading days back (approximately 28 calendar days)
            # This accounts for weekends and holidays
            start_date = end_date - timedelta(days=28)  # Ensures we get 20+ trading days
            
            daily_data = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=start_date.strftime('%Y-%m-%d'),
                to=end_date.strftime('%Y-%m-%d'),
                adjusted="true"
            )
            
            if not daily_data:
                return 1000000  # Default average volume
            
            # Use only the last 20 trading days (industry standard)
            # If we have more than 20 days, take the most recent 20
            if len(daily_data) > 20:
                daily_data = daily_data[-20:]  # Last 20 trading days
            
            # Calculate average volume
            total_volume = sum(bar.volume for bar in daily_data)
            avg_volume = total_volume / len(daily_data)
            
            logger.info(f"📊 Average volume for {ticker}: {int(avg_volume):,} (based on {len(daily_data)} trading days)")
            
            return int(avg_volume)
            
        except Exception as e:
            logger.error(f"❌ Error calculating average volume for {ticker}: {e}")
            return 1000000  # Default average volume
    
    def get_historical_comparison(self, ticker: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current data with historical patterns"""
        try:
            # Get historical gap-up data for this ticker
            historical_data = get_historical_gap_up_data(ticker, days=730, use_cache=True)
            
            if not historical_data:
                return {'historical_patterns': [], 'similar_days': 0}
            
            # Get current time and forecast full-day volume
            current_time = datetime.now()
            current_volume = current_data.get('current_volume', 0)
            forecasted_volume = self._forecast_full_day_volume(current_volume, current_time)
            
            logger.info(f"📊 Volume Analysis for {ticker}:")
            logger.info(f"   Current Volume: {current_volume:,}")
            logger.info(f"   Forecasted Full-Day: {forecasted_volume:,}")
            logger.info(f"   Time: {current_time.strftime('%H:%M ET')}")
            
            # Find similar historical days
            similar_days = []
            current_gap = current_data.get('gap_percent', 0)
            
            for hist_day in historical_data:
                hist_gap = hist_day.get('gap up % at open', 0)
                hist_volume = hist_day.get('volume', 0)
                
                # Check if this historical day is similar
                gap_diff = abs(hist_gap - current_gap)
                volume_ratio = forecasted_volume / hist_volume if hist_volume > 0 else 0
                
                if gap_diff <= 10 and 0.5 <= volume_ratio <= 2.0:  # Similar gap and volume
                    similar_days.append({
                        'date': hist_day.get('date'),
                        'gap_percent': hist_gap,
                        'volume': hist_volume,
                        'day_high': hist_day.get('day high'),
                        'day_low': hist_day.get('day low'),
                        'close': hist_day.get('close'),
                        'similarity_score': 1 / (1 + gap_diff + abs(1 - volume_ratio))
                    })
            
            # Sort by similarity score
            similar_days.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return {
                'historical_patterns': similar_days[:5],  # Top 5 similar days
                'similar_days': len(similar_days),
                'total_historical_days': len(historical_data),
                'volume_analysis': {
                    'current_volume': current_volume,
                    'forecasted_volume': forecasted_volume,
                    'current_time': current_time.strftime('%H:%M ET'),
                    'trading_hours_remaining': self._get_trading_hours_remaining(current_time)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting historical comparison for {ticker}: {e}")
            return {'historical_patterns': [], 'similar_days': 0}
    
    def _forecast_full_day_volume(self, current_volume: int, current_time: datetime) -> int:
        """Forecast full-day volume based on current volume and time of day"""
        try:
            # Convert to ET if needed
            if current_time.tzinfo is None:
                # Assume ET if no timezone
                current_time = current_time.replace(tzinfo=timezone(timedelta(hours=-5)))
            
            # Get time components
            hour = current_time.hour
            minute = current_time.minute
            
            # Calculate minutes since market open (9:30 AM ET)
            market_open_minutes = 9 * 60 + 30  # 9:30 AM
            current_minutes = hour * 60 + minute
            minutes_since_open = current_minutes - market_open_minutes
            
            # Handle edge cases
            if minutes_since_open <= 0:
                # Before market open, use conservative estimate
                return int(current_volume * 6.5)  # Assume 6.5 hours of trading
            
            # Calculate trading hours elapsed and remaining
            hours_elapsed = minutes_since_open / 60.0
            total_trading_hours = 6.5  # 9:30 AM - 4:00 PM ET
            hours_remaining = max(0, total_trading_hours - hours_elapsed)
            
            # Volume forecasting based on time of day
            if hours_elapsed <= 0.5:  # First 30 minutes
                # High volume period, assume 25% of day's volume in first 30 min
                forecast_multiplier = 4.0
            elif hours_elapsed <= 1.0:  # First hour
                # Still high volume, assume 35% of day's volume in first hour
                forecast_multiplier = 2.86
            elif hours_elapsed <= 2.0:  # First 2 hours
                # Moderate volume, assume 50% of day's volume in first 2 hours
                forecast_multiplier = 2.0
            elif hours_elapsed <= 3.0:  # First 3 hours
                # Lower volume, assume 65% of day's volume in first 3 hours
                forecast_multiplier = 1.54
            else:  # After 3 hours
                # Use remaining time ratio with volume decay
                volume_decay_factor = max(0.3, hours_remaining / total_trading_hours)
                forecast_multiplier = 1 + (volume_decay_factor * 0.5)
            
            # Calculate forecasted volume
            forecasted_volume = int(current_volume * forecast_multiplier)
            
            # Apply sanity checks
            min_volume = current_volume  # Can't be less than current
            max_volume = current_volume * 10  # Can't be more than 10x current
            
            forecasted_volume = max(min_volume, min(forecasted_volume, max_volume))
            
            return forecasted_volume
            
        except Exception as e:
            logger.error(f"❌ Error forecasting volume: {e}")
            # Fallback: assume 3x current volume
            return int(current_volume * 3)
    
    def _get_trading_hours_remaining(self, current_time: datetime) -> float:
        """Calculate remaining trading hours"""
        try:
            # Convert to ET if needed
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone(timedelta(hours=-5)))
            
            # Get time components
            hour = current_time.hour
            minute = current_time.minute
            
            # Calculate minutes since market open
            market_open_minutes = 9 * 60 + 30  # 9:30 AM
            current_minutes = hour * 60 + minute
            minutes_since_open = current_minutes - market_open_minutes
            
            # Calculate remaining time
            total_trading_minutes = 6.5 * 60  # 6.5 hours
            minutes_remaining = max(0, total_trading_minutes - minutes_since_open)
            hours_remaining = minutes_remaining / 60.0
            
            return round(hours_remaining, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating trading hours: {e}")
            return 6.5  # Default to full trading day
    
    def analyze_buy_over_hod_pattern(self, ticker: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if current conditions match buy over HOD strategy"""
        try:
            current_price = current_data.get('current_price', 0)
            day_high = current_data.get('day_high', 0)
            day_open = current_data.get('day_open', 0)
            gap_percent = current_data.get('gap_percent', 0)
            
            # Strategy conditions
            is_gap_up = gap_percent >= config.MIN_GAP_PERCENTAGE
            is_above_hod = current_price > day_high
            is_market_open = self.get_market_status() == 'open'
            
            # Historical analysis
            historical_comparison = self.get_historical_comparison(ticker, current_data)
            similar_days = historical_comparison.get('similar_days', 0)
            
            # Calculate success probability based on historical patterns
            success_probability = 0.5  # Default 50%
            if historical_comparison['historical_patterns']:
                # Analyze historical patterns for success rate
                profitable_days = 0
                total_days = len(historical_comparison['historical_patterns'])
                
                for pattern in historical_comparison['historical_patterns']:
                    day_high = pattern.get('day_high', 0)
                    close = pattern.get('close', 0)
                    if close > day_high * 1.02:  # 2% above HOD
                        profitable_days += 1
                
                success_probability = profitable_days / total_days if total_days > 0 else 0.5
            
            analysis = {
                'ticker': ticker,
                'strategy': 'buy_over_hod',
                'conditions_met': {
                    'is_gap_up': is_gap_up,
                    'is_above_hod': is_above_hod,
                    'is_market_open': is_market_open,
                    'has_historical_data': similar_days > 0
                },
                'current_metrics': {
                    'current_price': current_price,
                    'day_high': day_high,
                    'gap_percent': gap_percent,
                    'distance_from_hod': round(((current_price - day_high) / day_high) * 100, 2) if day_high > 0 else 0
                },
                'historical_analysis': {
                    'similar_days': similar_days,
                    'success_probability': round(success_probability * 100, 2),
                    'patterns': historical_comparison['historical_patterns'][:3]  # Top 3 patterns
                },
                'recommendation': {
                    'should_trade': is_gap_up and is_above_hod and is_market_open and success_probability > 60,
                    'confidence': round(success_probability * 100, 2),
                    'reason': self._get_trade_reason(is_gap_up, is_above_hod, success_probability)
                }
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing buy over HOD pattern for {ticker}: {e}")
            return {'error': str(e)}
    
    def _get_trade_reason(self, is_gap_up: bool, is_above_hod: bool, success_probability: float) -> str:
        """Get reason for trade recommendation"""
        reasons = []
        
        if not is_gap_up:
            reasons.append("Not a significant gap-up")
        if not is_above_hod:
            reasons.append("Price not above day high")
        if success_probability < 60:
            reasons.append("Low historical success probability")
        
        if not reasons:
            return "All conditions met for buy over HOD strategy"
        else:
            return f"Conditions not met: {', '.join(reasons)}"
    
    def update_real_time_data(self, ticker: str):
        """Update real-time data for a ticker"""
        try:
            real_time_data = self.get_real_time_data(ticker)
            if real_time_data:
                self.real_time_data[ticker] = real_time_data
                logger.debug(f"📊 Updated real-time data for {ticker}: ${real_time_data['current_price']}")
        except Exception as e:
            logger.error(f"❌ Error updating real-time data for {ticker}: {e}")
    
    def get_all_real_time_data(self) -> Dict[str, Dict[str, Any]]:
        """Get real-time data for all tracked stocks"""
        return self.real_time_data.copy()

# Global data manager instance
data_manager = DataManager() 