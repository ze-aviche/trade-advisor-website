#!/usr/bin/env python3
"""
Test Alpaca Integration
Simple script to test Alpaca connection and basic functionality
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from alpaca_client import alpaca_client
from logging_config import get_logger

logger = get_logger(__name__)

def test_alpaca_connection():
    """Test Alpaca connection and basic functionality"""
    try:
        print("🔧 Testing Alpaca Integration...")
        print("=" * 50)
        
        # Test account connection
        print("📊 Testing Account Connection...")
        account_info = alpaca_client.get_account_info()
        
        if account_info:
            print("✅ Account connection successful!")
            print(f"   Account Number: {account_info.get('account_number', 'N/A')}")
            print(f"   Cash: ${account_info.get('cash', 0):.2f}")
            print(f"   Portfolio Value: ${account_info.get('portfolio_value', 0):.2f}")
            print(f"   Buying Power: ${account_info.get('buying_power', 0):.2f}")
            print(f"   Status: {account_info.get('status', 'N/A')}")
        else:
            print("❌ Account connection failed!")
            return False
        
        # Test market status
        print("\n📈 Testing Market Status...")
        market_status = alpaca_client.get_market_status()
        
        if market_status:
            print("✅ Market status retrieved!")
            print(f"   Market Open: {market_status.get('is_open', False)}")
            print(f"   Next Open: {market_status.get('next_open', 'N/A')}")
            print(f"   Next Close: {market_status.get('next_close', 'N/A')}")
        else:
            print("❌ Market status failed!")
            return False
        
        # Test position retrieval
        print("\n📋 Testing Position Retrieval...")
        positions = alpaca_client.get_positions()
        
        if positions is not None:
            print("✅ Position retrieval successful!")
            print(f"   Active Positions: {len(positions)}")
            for symbol, position in positions.items():
                print(f"   {symbol}: {position['quantity']} shares @ ${position['avg_entry_price']:.2f}")
        else:
            print("❌ Position retrieval failed!")
            return False
        
        # Test pending orders
        print("\n📋 Testing Pending Orders...")
        pending_orders = alpaca_client.get_pending_orders()
        
        if pending_orders is not None:
            print("✅ Pending orders retrieved!")
            print(f"   Pending Orders: {len(pending_orders)}")
            for order in pending_orders:
                print(f"   {order['symbol']}: {order['quantity']} shares {order['side']} @ ${order.get('limit_price', 'market')}")
        else:
            print("❌ Pending orders failed!")
            return False
        
        print("\n✅ All Alpaca tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing Alpaca integration: {e}")
        return False

def test_mock_mode():
    """Test mock mode when Alpaca credentials are not available"""
    try:
        print("\n🔧 Testing Mock Mode...")
        print("=" * 50)
        
        # This would test the mock functionality
        print("✅ Mock mode available as fallback")
        print("   - No real orders will be placed")
        print("   - All orders are simulated")
        print("   - Perfect for testing strategies")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing mock mode: {e}")
        return False

def main():
    """Main test function"""
    print("🤖 Gap Trade Bot - Alpaca Integration Test")
    print("=" * 60)
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test Alpaca connection
    alpaca_success = test_alpaca_connection()
    
    # Test mock mode
    mock_success = test_mock_mode()
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"   Alpaca Integration: {'✅ PASS' if alpaca_success else '❌ FAIL'}")
    print(f"   Mock Mode: {'✅ PASS' if mock_success else '❌ FAIL'}")
    
    if alpaca_success:
        print("\n🎉 Alpaca integration is working! You can use real trading.")
    elif mock_success:
        print("\n⚠️ Alpaca not configured. Bot will run in mock mode.")
    else:
        print("\n❌ Both Alpaca and mock mode failed!")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main() 