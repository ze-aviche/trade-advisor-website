#!/usr/bin/env python3
"""
Test script to verify trading bot WebSocket connections work with SSL fixes
"""

import asyncio
import sys
import os

# Add backend/bot to path
sys.path.append('backend/bot')

from websocket_client import WebSocketClient
from broker_websocket_client import BrokerWebSocketClient

async def test_polygon_websocket():
    """Test Polygon WebSocket connection in trading bot"""
    print("🔌 Testing Polygon WebSocket connection in trading bot...")
    
    try:
        # Create WebSocket client
        ws_client = WebSocketClient()
        
        # Test connection
        await ws_client.connect()
        
        if ws_client.is_connected:
            print("✅ Polygon WebSocket connection successful!")
            
            # Test subscription
            await ws_client.subscribe_to_symbols(['AAPL'])
            print("✅ Subscription to AAPL successful!")
            
            # Test data callback
            def test_callback(data):
                print(f"📊 Received data: {data}")
            
            ws_client.add_data_callback(test_callback)
            print("✅ Data callback added!")
            
            # Listen for a few seconds
            print("👂 Listening for data (5 seconds)...")
            await asyncio.sleep(5)
            
            # Cleanup
            await ws_client.disconnect()
            print("✅ Polygon WebSocket test completed successfully!")
            return True
        else:
            print("❌ Polygon WebSocket connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Polygon WebSocket test failed: {e}")
        return False

async def test_alpaca_websocket():
    """Test Alpaca WebSocket connection in trading bot"""
    print("🔌 Testing Alpaca WebSocket connection in trading bot...")
    
    try:
        # Create broker WebSocket client
        broker_ws = BrokerWebSocketClient('alpaca')
        
        # Test connection
        await broker_ws.connect()
        
        if broker_ws.is_connected:
            print("✅ Alpaca WebSocket connection successful!")
            
            # Test callbacks
            def test_order_callback(data):
                print(f"📊 Order update: {data}")
            
            def test_fill_callback(data):
                print(f"📊 Fill notification: {data}")
            
            broker_ws.add_order_callback(test_order_callback)
            broker_ws.add_fill_callback(test_fill_callback)
            print("✅ Callbacks added!")
            
            # Listen for a few seconds
            print("👂 Listening for broker updates (5 seconds)...")
            await asyncio.sleep(5)
            
            # Cleanup
            await broker_ws.disconnect()
            print("✅ Alpaca WebSocket test completed successfully!")
            return True
        else:
            print("❌ Alpaca WebSocket connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Alpaca WebSocket test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting trading bot WebSocket connection tests...")
    print("=" * 60)
    
    # Test Polygon WebSocket
    polygon_success = await test_polygon_websocket()
    
    print("\n" + "=" * 60)
    
    # Test Alpaca WebSocket
    alpaca_success = await test_alpaca_websocket()
    
    print("\n" + "=" * 60)
    
    if polygon_success and alpaca_success:
        print("✅ All WebSocket connections working properly!")
    else:
        print("❌ Some WebSocket connections failed")
    
    return polygon_success and alpaca_success

if __name__ == "__main__":
    asyncio.run(main()) 