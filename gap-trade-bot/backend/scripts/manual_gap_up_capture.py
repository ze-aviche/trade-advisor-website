#!/usr/bin/env python3
"""
Manual Gap-Up Capture Script
Run this to manually capture and store daily gap-up stocks
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gap_up_detector import get_gap_up_stocks, get_daily_gap_ups_from_db
from datetime import datetime

def main():
    """Manual gap-up capture"""
    print("🎯 Manual Gap-Up Capture")
    print("=" * 50)
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 Date: {today}")
    
    # Check if we already have data
    existing_gap_ups = get_daily_gap_ups_from_db(today)
    if existing_gap_ups:
        print(f"⚠️ Already have {len(existing_gap_ups)} gap-up records for {today}")
        print("📊 Existing gap-ups:")
        for stock in existing_gap_ups[:10]:  # Show first 10
            print(f"   {stock['ticker']}: {stock['gap_percent']}% gap")
        return
    
    # Get fresh gap-up stocks
    print("🔍 Fetching current gap-up stocks...")
    gap_ups = get_gap_up_stocks()
    
    if not gap_ups:
        print("⚠️ No gap-up stocks found")
        return
    
    print(f"✅ Captured {len(gap_ups)} gap-up stocks for {today}")
    print("📊 All gap-ups:")
    for stock in gap_ups:
        print(f"   {stock['ticker']}: {stock['gap_percent']}% gap (${stock['price']})")
    
    print("=" * 50)
    print("✅ Manual gap-up capture complete!")

if __name__ == "__main__":
    main() 