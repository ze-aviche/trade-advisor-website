#!/usr/bin/env python3

import sys
import os
import requests

# Add parent directories to path to reach the bot module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def test_bot_status():
    """Test bot status API endpoint"""
    
    print("🤖 Testing Bot Status API")
    print("=" * 30)
    
    try:
        # Test bot status endpoint
        response = requests.get('http://localhost:5000/api/bot/status')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Bot status API responding")
            print(f"   Is Running: {data.get('is_running', False)}")
            print(f"   Positions: {len(data.get('positions', []))}")
            print(f"   Subscribed Stocks: {len(data.get('subscribed_stocks', []))}")
        else:
            print(f"❌ Bot status API error: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to bot status API - backend may not be running")
    except Exception as e:
        print(f"❌ Error testing bot status: {e}")

if __name__ == "__main__":
    test_bot_status() 