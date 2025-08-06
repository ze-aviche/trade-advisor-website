#!/usr/bin/env python3
"""
Test script to verify period dropdown functionality
"""
from historical_data import get_historical_gap_up_data, clear_cache

def test_period_dropdown():
    """Test different time periods for historical data"""
    print("🧪 Testing Period Dropdown Functionality")
    print("=" * 50)
    
    # Clear cache first
    clear_cache()
    
    ticker = "AAPL"
    periods = [
        (180, "6 Months"),
        (365, "1 Year"),
        (730, "2 Years"),
        (1095, "3 Years")
    ]
    
    for days, period_name in periods:
        print(f"\n🔄 Testing {period_name} ({days} days)...")
        
        try:
            data = get_historical_gap_up_data(ticker, days, use_cache=True)
            
            if data:
                print(f"✅ {period_name}: Retrieved {len(data)} records")
                
                # Show date range
                if len(data) > 0:
                    first_date = data[0]['date']
                    last_date = data[-1]['date']
                    print(f"   📅 Date range: {first_date} to {last_date}")
                    
                    # Count gap-up days (25%+)
                    gap_up_days = [day for day in data if day.get('gap up % at open') and day['gap up % at open'] >= 25]
                    print(f"   📊 25%+ gap-up days: {len(gap_up_days)}")
                    
                    # Show sample data
                    if len(data) > 0:
                        sample = data[0]
                        print(f"   📋 Sample: {sample['date']} - Gap: {sample.get('gap up % at open', 'N/A')}% - Pattern: {sample.get('Runner/Fader', 'N/A')}")
                
            else:
                print(f"❌ {period_name}: No data retrieved")
                
        except Exception as e:
            print(f"❌ {period_name}: Error - {e}")
    
    print(f"\n✅ Period dropdown test completed!")

if __name__ == "__main__":
    test_period_dropdown() 