#!/usr/bin/env python3
"""
Test script to validate get_gappers.py with date 2025-08-26
"""

import sys
import os
sys.path.append('.')

from get_gappers import get_grouped_bars, build_gap_dataset
from datetime import datetime, timedelta

def test_single_date():
    """Test get_grouped_bars for a single date"""
    date = "2025-08-26"
    print(f"🔍 Testing get_grouped_bars for date: {date}")
    
    try:
        # Test the API call
        daily_data = get_grouped_bars(date)
        print(f"✅ API call successful")
        print(f"📊 Retrieved {len(daily_data)} stocks for {date}")
        
        if len(daily_data) > 0:
            # Show first few stocks
            print(f"\n📋 First 5 stocks from {date}:")
            for i, stock in enumerate(daily_data[:5]):
                ticker = stock["T"]
                open_price = stock["o"]
                close_price = stock["c"]
                volume = stock["v"]
                print(f"   {i+1}. {ticker}: Open=${open_price}, Close=${close_price}, Volume={volume}")
            
            # Look for INHD specifically
            inhd_found = False
            for stock in daily_data:
                if stock["T"] == "INHD":
                    inhd_found = True
                    print(f"\n🎯 INHD found in data:")
                    print(f"   Ticker: {stock['T']}")
                    print(f"   Open: ${stock['o']}")
                    print(f"   Close: ${stock['c']}")
                    print(f"   Volume: {stock['v']}")
                    break
            
            if not inhd_found:
                print(f"\n❌ INHD not found in the data for {date}")
        else:
            print(f"❌ No data returned for {date}")
            
    except Exception as e:
        print(f"❌ Error testing single date: {e}")

def test_gap_detection():
    """Test gap detection for a few days around 2025-08-26"""
    print(f"\n🔍 Testing gap detection...")
    
    try:
        # Test a 3-day period around 2025-08-26
        start_date = "2025-08-27"
        end_date = "2025-08-28"
        
        print(f"📅 Testing gap detection from {start_date} to {end_date}")
        
        # Build gap dataset
        gappers_df = build_gap_dataset(start_date, end_date, gap_threshold=0.10)
        
        print(f"✅ Gap detection completed")
        print(f"📊 Found {len(gappers_df)} gap events")
        
        if len(gappers_df) > 0:
            print(f"\n📋 First 10 gap events:")
            for i, row in gappers_df.head(10).iterrows():
                print(f"   {i+1}. {row['date']} - {row['ticker']}: {row['gap_pct']:.2%} gap")
            
            # Look for INHD specifically
            inhd_gaps = gappers_df[gappers_df['ticker'] == 'INHD']
            if len(inhd_gaps) > 0:
                print(f"\n🎯 INHD gap events found:")
                for i, row in inhd_gaps.iterrows():
                    print(f"   {row['date']}: {row['gap_pct']:.2%} gap (Open: ${row['today_open']}, Prev Close: ${row['yesterday_close']})")
            else:
                print(f"\n❌ No INHD gap events found in the dataset")
        else:
            print(f"❌ No gap events found in the date range")
            
    except Exception as e:
        print(f"❌ Error testing gap detection: {e}")

def test_api_key():
    """Test if the API key is working"""
    print(f"\n🔑 Testing API key...")
    
    try:
        # Test with a known date that should have data
        test_date = "2025-08-26"
        daily_data = get_grouped_bars(test_date)
        
        if len(daily_data) > 0:
            print(f"✅ API key is working - retrieved {len(daily_data)} stocks")
        else:
            print(f"⚠️ API key might be working but no data for {test_date}")
            
    except Exception as e:
        print(f"❌ API key error: {e}")

if __name__ == "__main__":
    print("🧪 Validating get_gappers.py with date 2025-08-26")
    print("=" * 60)
    
    # Test API key first
    test_api_key()
    
    # Test single date
    test_single_date()
    
    # Test gap detection
    test_gap_detection()
    
    print("\n" + "=" * 60)
    print("✅ Validation complete")
