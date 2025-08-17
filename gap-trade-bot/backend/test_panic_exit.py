#!/usr/bin/env python3
"""
Test script for panic exit functionality
This script tests the panic exit API endpoint without actually executing trades
"""

import requests
import json
import time

def test_panic_exit_api():
    """Test the panic exit API endpoint"""
    
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Panic Exit API Endpoint")
    print("=" * 50)
    
    # Test 1: Check if server is running
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print("❌ Server health check failed")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        return False
    
    # Test 2: Check bot status
    try:
        response = requests.get(f"{base_url}/api/bot/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Bot status: {data.get('data', {}).get('running', 'Unknown')}")
        else:
            print("❌ Bot status check failed")
    except requests.exceptions.RequestException as e:
        print(f"❌ Bot status check error: {e}")
    
    # Test 3: Test panic exit endpoint
    print("\n🚨 Testing Panic Exit Endpoint...")
    try:
        response = requests.post(
            f"{base_url}/api/bot/panic-exit",
            headers={"Content-Type": "application/json"},
            json={},
            timeout=30  # Longer timeout for panic exit
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Panic exit API call successful")
            print(f"📋 Response: {json.dumps(data, indent=2)}")
            
            if data.get('success'):
                result = data.get('data', {})
                print(f"📊 Positions closed: {result.get('positions_closed', 0)}")
                print(f"📊 Positions failed: {result.get('positions_failed', 0)}")
                print(f"📊 Total positions: {result.get('total_positions', 0)}")
            else:
                print(f"❌ Panic exit failed: {data.get('error', 'Unknown error')}")
                
        elif response.status_code == 503:
            print("⚠️ Bot not available (expected if DAS not connected)")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"📋 Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Panic exit API error: {e}")
    
    print("\n🎉 Test completed!")

if __name__ == "__main__":
    test_panic_exit_api()
