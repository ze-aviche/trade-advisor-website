#!/usr/bin/env python3
"""
Test script to check Polygon WebSocket connection
"""

import asyncio
import json
import websockets
import os
import sys
import ssl
from datetime import datetime

# Add backend/bot to path
sys.path.append('backend/bot')

from config import TradingBotConfig

async def test_polygon_websocket():
    """Test Polygon WebSocket connection"""
    print("🔌 Testing Polygon WebSocket connection...")
    
    try:
        # Get API key
        config = TradingBotConfig()
        api_key = config.POLYGON_API_KEY
        if not api_key:
            print("❌ No Polygon API key found in config")
            return False
        
        print(f"✅ Found Polygon API key: {api_key[:10]}...")
        
        # Connect to Polygon WebSocket
        ws_url = "wss://delayed.polygon.io/stocks"
        print(f"🔗 Connecting to: {ws_url}")
        
        # Create SSL context that doesn't verify certificates (for testing)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        websocket = await websockets.connect(ws_url, ssl=ssl_context)
        print("✅ WebSocket connection established")
        
        # Send authentication
        auth_message = {
            "action": "auth",
            "params": api_key
        }
        await websocket.send(json.dumps(auth_message))
        print("🔐 Authentication sent")
        
        # Wait for auth response
        auth_response = await websocket.recv()
        auth_data = json.loads(auth_response)
        print(f"📡 Auth response: {auth_data}")
        
        # Check if it's a list and find the status message
        if isinstance(auth_data, list):
            status_msg = next((msg for msg in auth_data if msg.get('ev') == 'status'), None)
        else:
            status_msg = auth_data
        
        if status_msg and status_msg.get('status') == 'connected':
            print("✅ Authentication successful!")
            
            # Subscribe to a test symbol
            subscribe_message = {
                "action": "subscribe",
                "params": "T.AAPL,A.AAPL"  # Trade and Aggregate for AAPL
            }
            await websocket.send(json.dumps(subscribe_message))
            print("📡 Subscribed to AAPL")
            
            # Listen for a few messages
            print("👂 Listening for data (10 seconds)...")
            start_time = datetime.now()
            message_count = 0
            
            while (datetime.now() - start_time).seconds < 10:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    message_count += 1
                    print(f"📊 Message {message_count}: {data}")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
                    break
            
            print(f"📈 Received {message_count} messages in 10 seconds")
            
            # Unsubscribe
            unsubscribe_message = {
                "action": "unsubscribe",
                "params": "T.AAPL,A.AAPL"
            }
            await websocket.send(json.dumps(unsubscribe_message))
            print("📡 Unsubscribed from AAPL")
            
        else:
            print(f"❌ Authentication failed: {auth_data}")
            return False
        
        # Close connection
        await websocket.close()
        print("🔌 WebSocket connection closed")
        
        return True
        
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting Polygon WebSocket connection test...")
    print("=" * 50)
    
    success = await test_polygon_websocket()
    
    print("=" * 50)
    if success:
        print("✅ Polygon WebSocket connection test PASSED")
    else:
        print("❌ Polygon WebSocket connection test FAILED")
    
    return success

if __name__ == "__main__":
    asyncio.run(main()) 