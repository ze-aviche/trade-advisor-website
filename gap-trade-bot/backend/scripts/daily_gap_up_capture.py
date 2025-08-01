#!/usr/bin/env python3
"""
Daily Gap-Up Capture Script
Runs at market open to capture and store daily gap-up stocks
"""

import sys
import os
import time
from datetime import datetime, timedelta
import pytz

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gap_up_detector import get_gap_up_stocks, store_daily_gap_ups, get_daily_gap_ups_from_db

def is_market_open():
    """Check if market is currently open"""
    try:
        # Get current time in ET
        et_tz = pytz.timezone('US/Eastern')
        now = datetime.now(et_tz)
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check market hours (9:30 AM - 4:00 PM ET)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
        
    except Exception as e:
        print(f"❌ Error checking market status: {e}")
        return False

def wait_for_market_open():
    """Wait until market opens"""
    print("⏰ Waiting for market to open...")
    
    while not is_market_open():
        et_tz = pytz.timezone('US/Eastern')
        now = datetime.now(et_tz)
        
        # Calculate time until market open
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        if now.time() < market_open.time():
            time_until_open = market_open - now
            print(f"⏰ Market opens in {time_until_open}")
        else:
            print("⏰ Market should be open, checking...")
        
        time.sleep(60)  # Check every minute
    
    print("✅ Market is now open!")

def capture_daily_gap_ups():
    """Capture daily gap-up stocks and store in database"""
    try:
        print("🚀 Starting daily gap-up capture...")
        
        # Check if we already have data for today
        today = datetime.now().strftime('%Y-%m-%d')
        existing_gap_ups = get_daily_gap_ups_from_db(today)
        
        if existing_gap_ups:
            print(f"⚠️ Already have {len(existing_gap_ups)} gap-up records for {today}")
            print("📊 Existing gap-ups:")
            for stock in existing_gap_ups[:5]:  # Show first 5
                print(f"   {stock['ticker']}: {stock['gap_percent']}% gap")
            return existing_gap_ups
        
        # Get fresh gap-up stocks
        print("🔍 Fetching current gap-up stocks...")
        gap_ups = get_gap_up_stocks()
        
        if not gap_ups:
            print("⚠️ No gap-up stocks found")
            return []
        
        print(f"✅ Captured {len(gap_ups)} gap-up stocks for {today}")
        print("📊 Top gap-ups:")
        for stock in gap_ups[:5]:  # Show first 5
            print(f"   {stock['ticker']}: {stock['gap_percent']}% gap")
        
        return gap_ups
        
    except Exception as e:
        print(f"❌ Error capturing daily gap-ups: {e}")
        return []

def main():
    """Main function"""
    print("🎯 Daily Gap-Up Capture Script")
    print("=" * 50)
    
    # Check if market is open
    if not is_market_open():
        print("⏰ Market is not open yet")
        wait_for_market_open()
    
    # Capture gap-ups
    gap_ups = capture_daily_gap_ups()
    
    if gap_ups:
        print(f"✅ Successfully captured {len(gap_ups)} gap-up stocks")
    else:
        print("⚠️ No gap-up stocks captured")
    
    print("=" * 50)
    print("✅ Daily gap-up capture complete!")

if __name__ == "__main__":
    main() 