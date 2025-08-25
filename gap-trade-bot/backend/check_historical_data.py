#!/usr/bin/env python3
"""
Check historical daily_positions data
"""
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_historical_data():
    """Check if historical daily_positions data is preserved"""
    try:
        from database import db_manager
        
        print("🔍 Checking historical daily_positions data...")
        
        # Get current positions
        current_positions = db_manager.get_positions()
        print(f"📋 Current positions: {len(current_positions)} records")
        for pos in current_positions:
            print(f"  - {pos['symbol']}: {pos['quantity']} @ ${pos['avg_cost']:.2f}")
        
        # Get historical daily positions
        daily_positions = db_manager.get_daily_positions(limit=10)
        print(f"\n📊 Historical daily_positions: {len(daily_positions)} records")
        
        if daily_positions:
            print("📅 Recent historical snapshots:")
            for pos in daily_positions[:5]:
                print(f"  - {pos['symbol']} on {pos['snapshot_date']}: {pos['quantity']} @ ${pos['avg_cost']:.2f}")
        else:
            print("⚠️ No historical daily_positions data found")
        
        # Get summary
        summary = db_manager.get_daily_position_summary()
        print(f"\n📈 Historical Summary:")
        print(f"  - Total snapshots: {summary['total_snapshots']}")
        print(f"  - Unique symbols: {summary['unique_symbols']}")
        print(f"  - Unique dates: {summary['unique_dates']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking historical data: {e}")
        return False

if __name__ == "__main__":
    check_historical_data()
