#!/usr/bin/env python3
"""
Real-time Gap-up Detector
Monitors stocks for real-time gap-up opportunities
"""

import os
import time
import threading
from datetime import datetime, timedelta
from polygon import RESTClient
from dotenv import load_dotenv
from logging_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

class RealTimeGapDetector:
    """Real-time gap-up detection using Polygon API"""
    
    def __init__(self):
        self.polygon_client = self._get_polygon_client()
        self.gap_threshold = 5.0  # Minimum gap percentage
        self.running = False
        self.callback = None
        logger.info("✅ Real-time gap-up detector initialized")
    
    def _get_polygon_client(self):
        """Get Polygon API client"""
        try:
            api_key = os.getenv('POLYGON_API_KEY')
            if not api_key:
                logger.error("❌ POLYGON_API_KEY not found in environment")
                return None
            
            return RESTClient(api_key)
        except Exception as e:
            logger.error(f"❌ Error creating Polygon client: {e}")
            return None
    
    def get_previous_close_price(self, ticker):
        """Get previous close price for a ticker"""
        try:
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
            logger.error(f"❌ Error getting previous close for {ticker}: {e}")
            return None
    
    def get_current_price(self, ticker):
        """Get current price for a ticker"""
        try:
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
            logger.error(f"❌ Error getting current price for {ticker}: {e}")
            return None
    
    def check_gap_up(self, ticker):
        """Check if a stock has a significant gap-up"""
        try:
            current_price = self.get_current_price(ticker)
            previous_close = self.get_previous_close_price(ticker)
            
            if current_price is None or previous_close is None:
                return None
            
            # Calculate gap percentage
            gap_percent = ((current_price - previous_close) / previous_close) * 100
            
            # Check if it meets our threshold
            if gap_percent >= self.gap_threshold:
                # Get stock details
                details = self.polygon_client.get_ticker_details(ticker)
                
                return {
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
                    'detected_at': datetime.now().isoformat()
                }
            
            return None
        except Exception as e:
            logger.error(f"❌ Error checking gap-up for {ticker}: {e}")
            return None
    
    def scan_for_gap_ups(self):
        """Scan all stocks for gap-ups"""
        try:
            logger.info("🔍 Scanning for real-time gap-ups...")
            
            # Get all gainers from Polygon
            tickers = self.polygon_client.get_snapshot_direction(
                "stocks",
                direction="gainers",
            )
            
            if not tickers:
                logger.warning("❌ No tickers returned from Polygon API")
                return []
            
            gap_ups_found = []
            
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
                    logger.warning(f"🚨 REAL-TIME GAP-UP DETECTED: {ticker} - {gap_up_data['gap_percent']}%")
                    
                    # Call callback if set
                    if self.callback:
                        self.callback(gap_up_data)
            
            return gap_ups_found
            
        except Exception as e:
            logger.error(f"❌ Error scanning for gap-ups: {e}")
            return []
    
    def start_monitoring(self, callback=None):
        """Start real-time monitoring"""
        self.callback = callback
        self.running = True
        
        def monitor_worker():
            while self.running:
                try:
                    self.scan_for_gap_ups()
                    # Wait 30 seconds before next scan
                    time.sleep(30)
                except Exception as e:
                    logger.error(f"❌ Error in monitoring worker: {e}")
                    time.sleep(60)  # Wait longer on error
        
        # Start monitoring thread
        thread = threading.Thread(target=monitor_worker, daemon=True)
        thread.start()
        logger.info("✅ Real-time gap-up monitoring started")
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.running = False
        logger.info("⏹️ Real-time gap-up monitoring stopped")

# Global instance
real_time_detector = RealTimeGapDetector() 