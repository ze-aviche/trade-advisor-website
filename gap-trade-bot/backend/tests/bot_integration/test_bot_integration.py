#!/usr/bin/env python3
"""
Test Bot Integration
Basic tests for bot functionality
"""

import sys
import os

# Add parent directories to path to reach the bot module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from bot.trading_bot import TradingBot
    print("✅ Successfully imported TradingBot")
except Exception as e:
    print(f"❌ Failed to import TradingBot: {e}")

def test_bot_integration():
    """Test complete bot integration workflow"""
    try:
        print("🤖 Testing Bot Integration Workflow")
        
        # Create bot instance
        bot = TradingBot()
        print("✅ Bot instance created")
        
        # Test bot status
        status = bot.get_status()
        print(f"✅ Bot status: {status}")
        
        # Test bot start
        success = bot.start()
        print(f"✅ Bot start: {success}")
        
        # Test bot status after start
        status = bot.get_status()
        print(f"✅ Bot status after start: {status}")
        
        # Test subscribe to stock
        success = bot.subscribe_stock("AAPL")
        print(f"✅ Subscribe to AAPL: {success}")
        
        # Test bot status after subscribe
        status = bot.get_status()
        print(f"✅ Bot status after subscribe: {status}")
        
        # Test bot stop
        success = bot.stop()
        print(f"✅ Bot stop: {success}")
        
        # Test bot status after stop
        status = bot.get_status()
        print(f"✅ Bot status after stop: {status}")
        
        print("\n✅ Bot integration test completed!")
        
    except Exception as e:
        print(f"❌ Error testing bot integration: {e}")

if __name__ == "__main__":
    test_bot_integration()
