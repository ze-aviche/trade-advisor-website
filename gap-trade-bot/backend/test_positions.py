#!/usr/bin/env python3
"""
Test script for Positions History functionality
"""

import requests
import json
from datetime import datetime

def test_positions_api():
    """Test the positions API endpoints"""
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Positions History API...")
    
    # Test 1: Get positions
    print("\n1. Testing GET /api/positions")
    try:
        response = requests.get(f"{base_url}/api/positions")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('count', 0)} positions found")
            if data.get('data', {}).get('positions'):
                print(f"   Sample position: {data['data']['positions'][0]}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    # Test 2: Sync positions from DAS
    print("\n2. Testing POST /api/positions/sync-das")
    try:
        response = requests.post(f"{base_url}/api/positions/sync-das")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('message', 'Unknown')}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    # Test 3: Upsert a test position
    print("\n3. Testing POST /api/positions/upsert")
    test_position = {
        "symbol": "TEST",
        "quantity": 100,
        "avg_price": 50.0,
        "position_type": "LONG",
        "realized_pnl": 0.0,
        "unrealized_pnl": 500.0,
        "unrealized_pnl_pct": 10.0,
        "market_value": 5500.0,
        "cost_basis": 5000.0,
        "current_price": 55.0
    }
    
    try:
        response = requests.post(f"{base_url}/api/positions/upsert", json=test_position)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('message', 'Unknown')}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    # Test 4: Get positions with filter
    print("\n4. Testing GET /api/positions with filter")
    try:
        response = requests.get(f"{base_url}/api/positions?symbol=TEST&position_type=LONG")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('count', 0)} filtered positions found")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

def test_database_positions():
    """Test the database positions functionality"""
    print("\n🧪 Testing Database Positions Functionality...")
    
    try:
        from database import db_manager
        
        # Test upsert position
        test_position = {
            "symbol": "AAPL",
            "quantity": 50,
            "avg_price": 150.0,
            "position_type": "LONG",
            "realized_pnl": 100.0,
            "unrealized_pnl": 250.0,
            "unrealized_pnl_pct": 3.33,
            "market_value": 7750.0,
            "cost_basis": 7500.0,
            "current_price": 155.0
        }
        
        success, message = db_manager.upsert_position(test_position)
        print(f"✅ Upsert position: {message}")
        
        # Test get positions
        positions = db_manager.get_positions()
        print(f"✅ Get positions: {len(positions)} positions found")
        
        # Test get position summary
        summary = db_manager.get_position_summary()
        print(f"✅ Position summary: {summary}")
        
    except Exception as e:
        print(f"❌ Database test exception: {e}")

def test_das_integration():
    """Test the DAS integration for positions"""
    print("\n🧪 Testing DAS Integration for Positions...")
    
    try:
        from das_integration import das_trade_manager
        
        # Test position parsing
        test_response = """%POSITION AAPL 100 150.50 50.00 250.00
%POSITION MSFT -50 300.25 25.00 -125.00
%POSITION TSLA 200 250.75 0.00 500.00"""
        
        positions = das_trade_manager.parse_das_positions_response(test_response)
        print(f"✅ Parsed {len(positions)} positions from DAS response")
        
        for pos in positions:
            print(f"   {pos['symbol']}: {pos['position_type']} {pos['quantity']} @ ${pos['avg_price']:.2f}")
        
    except Exception as e:
        print(f"❌ DAS integration test exception: {e}")

if __name__ == "__main__":
    print("🚀 Starting Positions History Tests...")
    print(f"⏰ Test started at: {datetime.now()}")
    
    # Test database functionality
    test_database_positions()
    
    # Test DAS integration
    test_das_integration()
    
    # Test API endpoints (only if server is running)
    try:
        test_positions_api()
    except Exception as e:
        print(f"⚠️ API tests skipped (server may not be running): {e}")
    
    print(f"\n✅ All tests completed at: {datetime.now()}")
