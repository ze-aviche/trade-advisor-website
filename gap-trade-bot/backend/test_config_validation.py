#!/usr/bin/env python3
"""
Test Bot Configuration Validation
Test that bot configuration updates work correctly
"""

import requests
import json
import time

def test_config_validation():
    """Test bot configuration validation"""
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Bot Configuration Validation")
    print("="*50)
    
    try:
        # Test 1: Get current config
        print("\n1️⃣ Getting current configuration...")
        response = requests.get(f"{base_url}/api/bot/validate-config")
        if response.status_code == 200:
            current_config = response.json()['data']
            print(f"✅ Current config: {current_config}")
        else:
            print(f"❌ Failed to get current config: {response.status_code}")
            return False
        
        # Test 2: Update configuration
        print("\n2️⃣ Updating configuration...")
        new_config = {
            'profit_target_pct': 8.0,
            'stop_loss_pct': 4.0,
            'monitor_interval': 15
        }
        
        response = requests.post(f"{base_url}/api/bot/config", json=new_config)
        if response.status_code == 200:
            print(f"✅ Config updated successfully: {response.json()}")
        else:
            print(f"❌ Failed to update config: {response.status_code}")
            return False
        
        # Test 3: Validate the update
        print("\n3️⃣ Validating the update...")
        time.sleep(1)  # Small delay to ensure update is processed
        
        response = requests.get(f"{base_url}/api/bot/validate-config")
        if response.status_code == 200:
            updated_config = response.json()['data']
            print(f"✅ Updated config: {updated_config}")
            
            # Check if values match
            if (updated_config['profit_target_pct'] == new_config['profit_target_pct'] and
                updated_config['stop_loss_pct'] == new_config['stop_loss_pct'] and
                updated_config['monitor_interval'] == new_config['monitor_interval']):
                print("✅ Configuration validation successful!")
                return True
            else:
                print("❌ Configuration values don't match expected values")
                return False
        else:
            print(f"❌ Failed to validate config: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API - backend may not be running")
        return False
    except Exception as e:
        print(f"❌ Error testing config validation: {e}")
        return False

if __name__ == "__main__":
    success = test_config_validation()
    if success:
        print("\n🎉 All configuration validation tests passed!")
    else:
        print("\n⚠️ Configuration validation tests failed!")
