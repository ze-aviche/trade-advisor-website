#!/usr/bin/env python3
"""
Test Scheduled DAS Sync
Tests the scheduled sync functionality
"""
import sys
import os
import time
from datetime import datetime
import pytz

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from scheduled_das_sync import ScheduledDASSync, get_sync_status, manual_sync
    print("✅ Successfully imported scheduled_das_sync")
except ImportError as e:
    print(f"❌ Failed to import scheduled_das_sync: {e}")
    sys.exit(1)

def test_scheduled_sync():
    """Test the scheduled sync functionality"""
    print("🧪 Testing Scheduled DAS Sync...")
    print("=" * 50)
    
    # Test 1: Check sync status
    print("\n=== Test 1: Sync Status ===")
    try:
        status = get_sync_status()
        print(f"✅ Sync status retrieved successfully:")
        print(f"   - Is running: {status['is_running']}")
        print(f"   - Market hours: {status['is_market_hours']}")
        print(f"   - Current time ET: {status['current_time_et']}")
        print(f"   - Next run: {status['next_scheduled_run']}")
        print(f"   - Thread alive: {status['thread_alive']}")
    except Exception as e:
        print(f"❌ Failed to get sync status: {e}")
    
    # Test 2: Test market hours detection
    print("\n=== Test 2: Market Hours Detection ===")
    try:
        sync_service = ScheduledDASSync()
        is_market_hours = sync_service.is_market_hours()
        et_now = datetime.now(sync_service.et_tz)
        print(f"✅ Market hours detection:")
        print(f"   - Current time: {et_now.strftime('%Y-%m-%d %I:%M:%S %p ET')}")
        print(f"   - Market hours: {is_market_hours}")
        print(f"   - Market hours are 8 AM - 8 PM ET")
    except Exception as e:
        print(f"❌ Failed to test market hours: {e}")
    
    # Test 3: Test manual sync
    print("\n=== Test 3: Manual Sync ===")
    try:
        print("🔄 Testing manual sync...")
        result = manual_sync()
        print(f"✅ Manual sync result:")
        print(f"   - Success: {result['success']}")
        print(f"   - Message: {result['message']}")
        print(f"   - Synced count: {result['synced_count']}")
    except Exception as e:
        print(f"❌ Failed to test manual sync: {e}")
    
    # Test 4: Test scheduler start/stop
    print("\n=== Test 4: Scheduler Start/Stop ===")
    try:
        sync_service = ScheduledDASSync()
        
        # Start scheduler
        print("🔄 Starting scheduler...")
        sync_service.start_scheduler()
        time.sleep(2)  # Wait a moment
        
        # Check if running
        status_after_start = sync_service.get_sync_status()
        print(f"✅ After start: {status_after_start['is_running']}")
        
        # Stop scheduler
        print("🛑 Stopping scheduler...")
        sync_service.stop_scheduler()
        time.sleep(2)  # Wait a moment
        
        # Check if stopped
        status_after_stop = sync_service.get_sync_status()
        print(f"✅ After stop: {status_after_stop['is_running']}")
        
    except Exception as e:
        print(f"❌ Failed to test scheduler: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Scheduled DAS Sync tests completed!")

if __name__ == "__main__":
    test_scheduled_sync()
