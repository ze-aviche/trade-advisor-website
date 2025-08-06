#!/usr/bin/env python3
"""Test automatic sync functionality"""

import requests
import time
import json

def main():
    print("🔄 Testing automatic sync functionality...")
    
    # Test 1: Check initial bot status
    print("\n=== Test 1: Initial Bot Status ===")
    response1 = requests.get("http://localhost:5000/api/bot/status")
    data1 = response1.json()
    print(f"Initial positions: {len(data1.get('positions', []))}")
    
    # Test 2: Check after a few seconds (should auto-sync)
    print("\n=== Test 2: After Auto-Sync ===")
    time.sleep(2)  # Wait for potential auto-sync
    response2 = requests.get("http://localhost:5000/api/bot/status")
    data2 = response2.json()
    print(f"Positions after auto-sync: {len(data2.get('positions', []))}")
    
    # Test 3: Manual sync
    print("\n=== Test 3: Manual Sync ===")
    response3 = requests.post("http://localhost:5000/api/bot/sync-trades")
    data3 = response3.json()
    print(f"Manual sync result: {data3.get('success')}")
    print(f"Synced count: {data3.get('data', {}).get('synced_count', 0)}")
    
    # Test 4: Final check
    print("\n=== Test 4: Final Bot Status ===")
    response4 = requests.get("http://localhost:5000/api/bot/status")
    data4 = response4.json()
    print(f"Final positions: {len(data4.get('positions', []))}")
    
    print("\n✅ Automatic sync test completed!")

if __name__ == "__main__":
    main() 