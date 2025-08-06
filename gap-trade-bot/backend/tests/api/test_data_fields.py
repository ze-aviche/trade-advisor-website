#!/usr/bin/env python3
"""
Test script to verify all data fields are being returned correctly
"""
from historical_data import get_historical_gap_up_data, clear_cache

def test_data_fields():
    """Test that all required data fields are present"""
    print("🧪 Testing Data Fields")
    print("=" * 30)
    
    # Clear cache first
    clear_cache()
    
    # Get data for a ticker with more days to get complete data
    ticker = "AAPL"
    days = 30  # More days to get better data
    
    print(f"🔄 Fetching data for {ticker} ({days} days)...")
    data = get_historical_gap_up_data(ticker, days, use_cache=True)
    
    if data and len(data) > 0:
        print(f"✅ Retrieved {len(data)} records")
        
        # Find a record with more complete data
        best_record = None
        max_fields = 0
        
        for record in data:
            non_none_fields = sum(1 for value in record.values() if value is not None)
            if non_none_fields > max_fields:
                max_fields = non_none_fields
                best_record = record
        
        if best_record:
            print(f"\n📊 Best record date: {best_record.get('date', 'N/A')} ({max_fields} non-null fields)")
            
            # Define all required fields
            required_fields = [
                'date',
                'pd close',
                'premarket open',
                'premarket high',
                'premarket high time',
                'premarket volume',
                'open',
                'gap up % at open',
                'day high',
                'day high time',
                'day high %',
                'close price',
                'closing percent',
                'afterhours close',
                'total volume',
                'VWAP Crosses',
                'Runner/Fader',
                'high',
                'low',
                'volume_millions',
                'dollar_volume_millions'
            ]
            
            print(f"\n🔍 Checking {len(required_fields)} required fields:")
            missing_fields = []
            present_fields = []
            
            for field in required_fields:
                value = best_record.get(field)
                status = "✅" if value is not None else "❌"
                print(f"   {status} {field}: {value}")
                
                if value is None:
                    missing_fields.append(field)
                else:
                    present_fields.append(field)
            
            print(f"\n📊 Summary:")
            print(f"   ✅ Present fields: {len(present_fields)}")
            print(f"   ❌ Missing fields: {len(missing_fields)}")
            
            if missing_fields:
                print(f"   ⚠️ Missing fields: {missing_fields}")
            else:
                print(f"   ✅ All {len(required_fields)} fields are present!")
            
            # Show sample data
            print(f"\n📋 Sample data for {best_record['date']}:")
            print(f"   Previous Close: ${best_record.get('pd close', 'N/A')}")
            print(f"   Premarket Open: ${best_record.get('premarket open', 'N/A')}")
            print(f"   Premarket High: ${best_record.get('premarket high', 'N/A')}")
            print(f"   Premarket High Time: {best_record.get('premarket high time', 'N/A')}")
            print(f"   Premarket Volume: {best_record.get('premarket volume', 'N/A')}")
            print(f"   Open: ${best_record.get('open', 'N/A')}")
            print(f"   Gap %: {best_record.get('gap up % at open', 'N/A')}%")
            print(f"   Day High: ${best_record.get('day high', 'N/A')}")
            print(f"   Day High Time: {best_record.get('day high time', 'N/A')}")
            print(f"   Day High %: {best_record.get('day high %', 'N/A')}%")
            print(f"   Close: ${best_record.get('close price', 'N/A')}")
            print(f"   Closing %: {best_record.get('closing percent', 'N/A')}%")
            print(f"   After Hours: ${best_record.get('afterhours close', 'N/A')}")
            print(f"   Volume: {best_record.get('total volume', 'N/A')}")
            print(f"   VWAP Crosses: {best_record.get('VWAP Crosses', 'N/A')}")
            print(f"   Pattern: {best_record.get('Runner/Fader', 'N/A')}")
            print(f"   High: ${best_record.get('high', 'N/A')}")
            print(f"   Low: ${best_record.get('low', 'N/A')}")
            print(f"   Volume (M): {best_record.get('volume_millions', 'N/A')}M")
            print(f"   Dollar Volume (M): ${best_record.get('dollar_volume_millions', 'N/A')}M")
            
        else:
            print("❌ No suitable record found")
        
    else:
        print("❌ No data retrieved")

if __name__ == "__main__":
    test_data_fields() 