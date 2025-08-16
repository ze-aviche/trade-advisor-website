#!/usr/bin/env python3
"""
Optimized Real-time Gap-up Detector with Hybrid Approach
Dual thresholds: 5% for alerts, 25% for trading opportunities
"""

import os
import time
import threading
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict, deque
from polygon import RESTClient
from dotenv import load_dotenv
from logging_config import get_logger
from gap_up_cache import cached_real_time_detection, get_cached_real_time_gap_ups, set_cached_real_time_gap_ups, set_cached_frontend_gap_ups

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

class OptimizedRealTimeGapDetector:
    """Optimized real-time gap-up detection with dual thresholds and smart deduplication"""
    
    def __init__(self):
        self.polygon_client = self._get_polygon_client()
        self.alert_threshold = 5.0      # Minimum gap for frontend alerts
        self.trading_threshold = 25.0    # Minimum gap for bot subscription
        self.running = False
        self.callback = None
        self.trading_callback = None  # New callback for trading opportunities
        
        # Smart deduplication
        self.detected_gaps = defaultdict(lambda: {'count': 0, 'last_detected': None})
        self.gap_history = deque(maxlen=1000)  # Keep last 1000 detections
        
        # Rate limiting
        self.api_calls = 0
        self.last_api_reset = time.time()
        self.max_api_calls_per_minute = 30  # Conservative limit
        
        # Smart scanning intervals
        self.base_scan_interval = 15  # 15 seconds base interval
        self.adaptive_interval = 15
        self.market_hours_active = False
        self.peak_hours_active = False
        
        # Performance tracking
        self.scan_count = 0
        self.gaps_found = 0
        self.trading_opportunities = 0
        self.last_performance_log = time.time()
        
        # Cache for frontend updates
        self.current_gap_ups = []
        
        logger.info("Optimized real-time gap-up detector initialized with hybrid approach")
        logger.info(f"📊 Alert threshold: {self.alert_threshold}%, Trading threshold: {self.trading_threshold}%")
    
    def _get_polygon_client(self):
        """Get Polygon API client"""
        try:
            api_key = os.getenv('POLYGON_API_KEY')
            if not api_key:
                logger.error("POLYGON_API_KEY not found in environment")
                return None
            
            return RESTClient(api_key)
        except Exception as e:
            logger.error(f"Error creating Polygon client: {e}")
            return None
    
    def _check_rate_limit(self):
        """Check and manage API rate limits"""
        current_time = time.time()
        
        # Reset counter every minute
        if current_time - self.last_api_reset >= 60:
            self.api_calls = 0
            self.last_api_reset = current_time
        
        # Check if we're over limit
        if self.api_calls >= self.max_api_calls_per_minute:
            wait_time = 60 - (current_time - self.last_api_reset)
            logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
            return False
        
        self.api_calls += 1
        return True
    
    def _is_market_hours(self):
        """Check if we're in market hours (9:30 AM - 4:00 PM ET)"""
        now = datetime.now()
        et_time = now - timedelta(hours=3)  # Convert to ET
        
        # Check if it's a weekday
        if et_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check market hours (9:30 AM - 4:00 PM ET)
        market_start = et_time.replace(hour=9, minute=30, second=0, microsecond=0)
        market_end = et_time.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_start <= et_time <= market_end
    
    def _is_peak_hours(self):
        """Check if we're in peak trading hours (9:30-11:30 AM ET or 3:00-5:00 PM ET)"""
        now = datetime.now()
        et_time = now - timedelta(hours=3)  # Convert to ET
        
        # Check if it's a weekday
        if et_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Morning peak: 9:30 AM - 11:30 AM ET
        morning_start = et_time.replace(hour=9, minute=30, second=0, microsecond=0)
        morning_end = et_time.replace(hour=11, minute=30, second=0, microsecond=0)
        
        # Afternoon peak: 3:00 PM - 5:00 PM ET
        afternoon_start = et_time.replace(hour=15, minute=0, second=0, microsecond=0)
        afternoon_end = et_time.replace(hour=17, minute=0, second=0, microsecond=0)
        
        # Check if we're in peak hours
        in_morning_peak = morning_start <= et_time <= morning_end
        in_afternoon_peak = afternoon_start <= et_time <= afternoon_end
        
        return in_morning_peak or in_afternoon_peak
    
    def _get_scan_mode_description(self):
        """Get current scan mode description"""
        if self._is_peak_hours():
            return "PEAK HOURS (2s intervals)"
        elif self._is_market_hours():
            return "MARKET HOURS (10s intervals)"
        else:
            return "OFF HOURS (60s intervals)"
    
    def _should_detect_gap(self, ticker, gap_percent):
        """Smart deduplication logic with dual thresholds"""
        current_time = time.time()
        ticker_data = self.detected_gaps[ticker]
        
        # If this is a new detection or significant change
        if ticker_data['last_detected'] is None:
            return True
        
        # If it's been more than 5 minutes since last detection
        if current_time - ticker_data['last_detected'] > 300:
            return True
        
        # If gap percentage changed significantly (>2% difference)
        last_gap = ticker_data.get('last_gap_percent', 0)
        if abs(gap_percent - last_gap) > 2.0:
            return True
        
        # If this is a very large gap (>20%), always report
        if gap_percent > 20.0:
            return True
        
        return False
    
    def _update_detection_history(self, ticker, gap_percent):
        """Update detection history for deduplication"""
        current_time = time.time()
        ticker_data = self.detected_gaps[ticker]
        
        ticker_data['count'] += 1
        ticker_data['last_detected'] = current_time
        ticker_data['last_gap_percent'] = gap_percent
        
        # Add to history
        detection_hash = hashlib.md5(f"{ticker}_{gap_percent:.1f}".encode()).hexdigest()
        self.gap_history.append({
            'ticker': ticker,
            'gap_percent': gap_percent,
            'timestamp': current_time,
            'hash': detection_hash
        })
    
    def get_previous_close_price(self, ticker):
        """Get previous close price for a ticker"""
        try:
            if not self._check_rate_limit():
                return None
                
            today = datetime.now().date()
            last_trading_day = today - timedelta(days=1)
            
            # Skip weekends
            while last_trading_day.weekday() >= 5:
                last_trading_day -= timedelta(days=1)
            
            date_str = last_trading_day.strftime("%Y-%m-%d")
            
            aggs = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=date_str,
                to=date_str
            )
            
            if aggs and len(aggs) > 0:
                return aggs[0].close
            return None
        except Exception as e:
            logger.error(f"Error getting previous close for {ticker}: {e}")
            return None
    
    def get_current_price(self, ticker):
        """Get current price for a ticker"""
        try:
            if not self._check_rate_limit():
                return None
                
            today = datetime.now().date()
            date_str = today.strftime("%Y-%m-%d")
            
            aggs = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=date_str,
                to=date_str
            )
            
            if aggs and len(aggs) > 0:
                return aggs[0].close
            
            # If no data for today, get latest available
            aggs = self.polygon_client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=(today - timedelta(days=5)).strftime("%Y-%m-%d"),
                to=date_str
            )
            
            if aggs and len(aggs) > 0:
                return aggs[-1].close
            
            return None
        except Exception as e:
            logger.error(f"Error getting current price for {ticker}: {e}")
            return None
    
    def check_gap_up(self, ticker):
        """Check for gap-up with hybrid threshold logic"""
        try:
            previous_close = self.get_previous_close_price(ticker)
            current_price = self.get_current_price(ticker)
            
            if not previous_close or not current_price:
                return None
            
            # Calculate gap percentage
            gap_percent = ((current_price - previous_close) / previous_close) * 100
            
            # Check if it meets our alert threshold
            if gap_percent >= self.alert_threshold:
                # Check if we should report this detection
                if not self._should_detect_gap(ticker, gap_percent):
                    return None
                
                # Get stock details
                if not self._check_rate_limit():
                    return None
                    
                details = self.polygon_client.get_ticker_details(ticker)
                
                gap_data = {
                    'ticker': ticker,
                    'company_name': details.name,
                    'price': round(current_price, 2),
                    'previous_close': round(previous_close, 2),
                    'change': round(current_price - previous_close, 2),
                    'change_percent': round(gap_percent, 2),
                    'gap_percent': round(gap_percent, 2),
                    'volume': getattr(details, 'share_class_shares_outstanding', 0),
                    'market_cap': getattr(details, 'market_cap', 0),
                    'sector': getattr(details, 'sic_description', 'Unknown'),
                    'list_date': getattr(details, 'list_date', None),
                    'detected_at': datetime.now().isoformat(),
                    'detection_count': self.detected_gaps[ticker]['count'] + 1,
                    'is_trading_opportunity': gap_percent >= self.trading_threshold
                }
                
                # Update detection history
                self._update_detection_history(ticker, gap_percent)
                
                return gap_data
            
            return None
        except Exception as e:
            logger.error(f"Error checking gap-up for {ticker}: {e}")
            return None
    
    def _adaptive_scan_interval(self):
        """Adapt scan interval based on market activity"""
        current_time = time.time()
        market_hours = self._is_market_hours()
        peak_hours = self._is_peak_hours()
        
        # During peak hours, scan very frequently
        if peak_hours:
            if not hasattr(self, 'peak_hours_active') or not self.peak_hours_active:
                logger.info("Peak hours detected (9:30-11:30 AM ET or 3:00-5:00 PM ET) - maximum scan frequency")
                self.peak_hours_active = True
                self.market_hours_active = True
            return 2  # 2 seconds during peak hours
        # During regular market hours, scan frequently
        elif market_hours:
            if not hasattr(self, 'market_hours_active') or not self.market_hours_active:
                logger.info("📈 Market hours detected - increasing scan frequency")
                self.market_hours_active = True
                self.peak_hours_active = False
            return 10  # 10 seconds during market hours
        else:
            if hasattr(self, 'market_hours_active') and self.market_hours_active:
                logger.info("📉 Outside market hours - reducing scan frequency")
                self.market_hours_active = False
                self.peak_hours_active = False
            return 60  # 60 seconds outside market hours
    
    def scan_for_gap_ups(self):
        """Smart scan for gap-ups with hybrid threshold handling"""
        try:
            self.scan_count += 1
            
            # Adaptive scan interval
            scan_interval = self._adaptive_scan_interval()
            
            logger.info(f"Scanning for real-time gap-ups (scan #{self.scan_count}, interval: {scan_interval}s)")
            
            # Get all gainers from Polygon
            if not self._check_rate_limit():
                return []
                
            tickers = self.polygon_client.get_snapshot_direction(
                "stocks",
                direction="gainers",
            )
            
            if not tickers:
                logger.warning("No tickers returned from Polygon API")
                return []
            
            gap_ups_found = []
            trading_opportunities = []
            
            for item in tickers:
                ticker = None
                if isinstance(item, dict):
                    ticker = item.get("ticker") or item.get("symbol")
                elif hasattr(item, "ticker"):
                    ticker = getattr(item, "ticker", None)
                elif hasattr(item, "symbol"):
                    ticker = getattr(item, "symbol", None)
                
                if not ticker:
                    continue
                
                # Check for gap-up
                gap_up_data = self.check_gap_up(ticker)
                if gap_up_data:
                    gap_ups_found.append(gap_up_data)
                    self.gaps_found += 1
                    
                    # Check if this is a trading opportunity
                    if gap_up_data['is_trading_opportunity']:
                        trading_opportunities.append(gap_up_data)
                        self.trading_opportunities += 1
                        logger.warning(f"🚨 TRADING OPPORTUNITY: {ticker} - {gap_up_data['gap_percent']}% (detection #{gap_up_data['detection_count']})")
                    else:
                        logger.info(f"📊 GAP-UP ALERT: {ticker} - {gap_up_data['gap_percent']}% (detection #{gap_up_data['detection_count']})")
                    
                    # Call callback if set
                    if self.callback:
                        self.callback(gap_up_data)
                    
                    # Call trading callback for 25%+ opportunities
                    if gap_up_data['is_trading_opportunity'] and self.trading_callback:
                        self.trading_callback(gap_up_data)
            
            # Update frontend cache with fresh gap-up data
            if gap_ups_found:
                self._update_frontend_cache(gap_ups_found)
            
            # Log performance every 10 scans
            if self.scan_count % 10 == 0:
                current_time = time.time()
                time_since_last = current_time - self.last_performance_log
                scans_per_minute = 10 / (time_since_last / 60)
                
                logger.info(f"📊 Performance: {scans_per_minute:.1f} scans/min, {self.gaps_found} gaps found, {self.trading_opportunities} trading opportunities, {len(self.detected_gaps)} unique tickers tracked")
                self.last_performance_log = current_time
            
            return gap_ups_found
            
        except Exception as e:
            logger.error(f"Error scanning for gap-ups: {e}")
            return []
    
    def start_monitoring(self, callback=None, trading_callback=None):
        """Start optimized real-time monitoring with dual callbacks"""
        self.callback = callback
        self.trading_callback = trading_callback
        self.running = True
        
        def monitor_worker():
            while self.running:
                try:
                    self.scan_for_gap_ups()
                    
                    # Adaptive sleep based on market hours
                    sleep_time = self._adaptive_scan_interval()
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring worker: {e}")
                    time.sleep(60)  # Wait longer on error
        
        # Start monitoring thread
        thread = threading.Thread(target=monitor_worker, daemon=True, name="GapUpMonitor")
        thread.start()
        logger.info("Optimized real-time gap-up monitoring started with hybrid approach")
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.running = False
        logger.info("⏹️ Optimized real-time gap-up monitoring stopped")
    
    def _update_frontend_cache(self, gap_ups_found):
        """Update the frontend cache with fresh gap-up data"""
        try:
            # Convert gap-up data to frontend format
            frontend_data = []
            for gap_up in gap_ups_found:
                frontend_item = {
                    'ticker': gap_up['ticker'],
                    'company_name': gap_up.get('company_name', 'Unknown'),
                    'price': gap_up['price'],  # Use 'price' from real-time detector
                    'previous_close': gap_up['previous_close'],
                    'change': gap_up['change'],  # Use 'change' from real-time detector
                    'change_percent': gap_up['change_percent'],  # Use 'change_percent' from real-time detector
                    'gap_percent': gap_up['gap_percent'],
                    'volume': gap_up.get('volume', 0),
                    'market_cap': gap_up.get('market_cap', 0),
                    'sector': gap_up.get('sector', 'Unknown'),
                    'peak_gap_percent': gap_up.get('peak_gap_percent', gap_up['gap_percent']),
                    'peak_time': gap_up.get('peak_time', ''),
                    'is_new_peak': gap_up.get('is_new_peak', False),
                    'is_significant_drop': gap_up.get('is_significant_drop', False)
                }
                frontend_data.append(frontend_item)
            
            # Update the cache
            set_cached_frontend_gap_ups(frontend_data)
            self.current_gap_ups = frontend_data
            
            logger.info(f"Updated frontend cache with {len(frontend_data)} gap-ups")
            
        except Exception as e:
            logger.error(f"Error updating frontend cache: {e}")
    
    def get_stats(self):
        """Get monitoring statistics"""
        return {
            'scans_performed': self.scan_count,
            'gaps_found': self.gaps_found,
            'trading_opportunities': self.trading_opportunities,
            'unique_tickers_tracked': len(self.detected_gaps),
            'api_calls_this_minute': self.api_calls,
            'market_hours_active': self.market_hours_active,
            'peak_hours_active': getattr(self, 'peak_hours_active', False),
            'adaptive_interval': self._adaptive_scan_interval(),
            'current_scan_mode': self._get_scan_mode_description(),
            'alert_threshold': self.alert_threshold,
            'trading_threshold': self.trading_threshold
        }

# Global instance
real_time_detector = OptimizedRealTimeGapDetector() 