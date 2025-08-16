#!/usr/bin/env python3
"""Test bot status functionality"""

import requests
import time
import json

def main():
    print("🔄 Testing bot status functionality...")
    
    # Test 1: Check initial bot status
    print("\n=== Test 1: Initial Bot Status ===")
    response1 = requests.get("http://localhost:5000/api/bot/status")
    data1 = response1.json()
    print(f"Initial positions: {len(data1.get('positions', []))}")
    
    # Test 2: Check after a few seconds
    print("\n=== Test 2: After Delay ===")
    time.sleep(2)  # Wait a few seconds
    response2 = requests.get("http://localhost:5000/api/bot/status")
    data2 = response2.json()
    print(f"Positions after delay: {len(data2.get('positions', []))}")
    
    # Test 3: Final check
    print("\n=== Test 3: Final Bot Status ===")
    response3 = requests.get("http://localhost:5000/api/bot/status")
    data3 = response3.json()
    print(f"Final positions: {len(data3.get('positions', []))}")
    
    print("\n✅ Bot status test completed!")

if __name__ == "__main__":
    main() 