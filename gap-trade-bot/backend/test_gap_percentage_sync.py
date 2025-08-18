#!/usr/bin/env python3
"""
Test script to verify min_gap_percentage synchronization between frontend and backend
"""
import requests
import json
import sys
import os

def test_gap_percentage_sync():
    """Test that min_gap_percentage is synchronized"""
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Gap Percentage Synchronization")
    print("=" * 50)
    
    # Test 1: Get current configuration
    print("\n1. Getting current configuration...")
    try:
        response = requests.get(f"{base_url}/api/gap-ups/config")
        if response.status_code == 200:
            data = response.json()
            current_percentage = data['data']['min_percentage']
            print(f"   ✅ Current min_percentage: {current_percentage}%")
        else:
            print(f"   ❌ Failed to get config: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error getting config: {e}")
        return False
    
    # Test 2: Update configuration
    print("\n2. Updating configuration to 30%...")
    try:
        new_config = {"min_percentage": 30.0}
        response = requests.post(
            f"{base_url}/api/gap-ups/config",
            json=new_config,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Configuration updated: {data['message']}")
        else:
            print(f"   ❌ Failed to update config: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error updating config: {e}")
        return False
    
    # Test 3: Verify the update
    print("\n3. Verifying the update...")
    try:
        response = requests.get(f"{base_url}/api/gap-ups/config")
        if response.status_code == 200:
            data = response.json()
            updated_percentage = data['data']['min_percentage']
            print(f"   ✅ Updated min_percentage: {updated_percentage}%")
            
            if updated_percentage == 30.0:
                print("   ✅ Synchronization successful!")
            else:
                print(f"   ❌ Synchronization failed! Expected 30.0, got {updated_percentage}")
                return False
        else:
            print(f"   ❌ Failed to verify config: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error verifying config: {e}")
        return False
    
    # Test 4: Test gap-ups endpoint with new percentage
    print("\n4. Testing gap-ups endpoint with new percentage...")
    try:
        response = requests.get(f"{base_url}/api/gap-ups?min_percentage=30.0")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Gap-ups endpoint working with 30% threshold")
            print(f"   📊 Found {len(data['data'])} gap-up stocks")
        else:
            print(f"   ❌ Gap-ups endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error testing gap-ups endpoint: {e}")
        return False
    
    # Test 5: Reset to original value
    print("\n5. Resetting to original value...")
    try:
        reset_config = {"min_percentage": current_percentage}
        response = requests.post(
            f"{base_url}/api/gap-ups/config",
            json=reset_config,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            print(f"   ✅ Reset to original value: {current_percentage}%")
        else:
            print(f"   ❌ Failed to reset config: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error resetting config: {e}")
        return False
    
    print("\n✅ All synchronization tests passed!")
    return True

if __name__ == "__main__":
    success = test_gap_percentage_sync()
    sys.exit(0 if success else 1)
