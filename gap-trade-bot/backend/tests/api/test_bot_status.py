#!/usr/bin/env python3
"""
Test Bot Status API
Test bot status API endpoint
"""

import requests
import sys
import os

# Add parent directories to path to reach the bot module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_bot_status():
    """Test bot status API endpoint"""
    try:
        print("🤖 Testing Bot Status API")
        
        # Test bot status endpoint
        response = requests.get('http://localhost:5000/api/bot/status')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Bot status API responding")
            print(f"📊 Bot status: {data}")
        else:
            print(f"❌ Bot status API error: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to bot status API - backend may not be running")
    except Exception as e:
        print(f"❌ Error testing bot status: {e}")

if __name__ == "__main__":
    test_bot_status()
