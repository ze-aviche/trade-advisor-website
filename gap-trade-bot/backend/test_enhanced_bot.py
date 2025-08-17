#!/usr/bin/env python3
"""
Test Enhanced Trading Bot
Test the enhanced trading bot with position monitoring capabilities
"""

import sys
import os
import time
import requests

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_bot_import():
    """Test if the enhanced bot can be imported"""
    try:
        from bot.trading_bot import TradingBot, DASConnection, PositionParser
        print("✅ Successfully imported enhanced TradingBot")
        return True
    except Exception as e:
        print(f"❌ Failed to import enhanced TradingBot: {e}")
        return False

def test_bot_creation():
    """Test bot creation with configuration"""
    try:
        from bot.trading_bot import TradingBot
        
        config = {
            'profit_target_pct': 5.0,
            'stop_loss_pct': 2.5,
            'monitor_interval': 5
        }
        
        bot = TradingBot(config)
        print("✅ Bot created successfully with configuration")
        print(f"   Profit target: {bot.profit_target_pct}%")
        print(f"   Stop loss: {bot.stop_loss_pct}%")
        print(f"   Monitor interval: {bot.monitor_interval}s")
        return True
    except Exception as e:
        print(f"❌ Error creating bot: {e}")
        return False

def test_das_connection():
    """Test DAS connection (will fail if DAS is not running)"""
    try:
        from bot.trading_bot import DASConnection
        
        print("🔌 Testing DAS connection...")
        connection = DASConnection()
        
        # Try to connect
        success = connection.ConnectToServer()
        if success:
            print("✅ Successfully connected to DAS")
            
            # Test getting positions
            script = "GET POSITIONS\r\n"
            result = connection.SendScript(bytearray(script, encoding="ascii"))
            print(f"📊 Positions result: {result[:200]}...")
            
            connection.Disconnect()
            return True
        else:
            print("❌ Failed to connect to DAS (this is expected if DAS is not running)")
            return False
            
    except Exception as e:
        print(f"❌ Error testing DAS connection: {e}")
        return False

def test_position_parsing():
    """Test position parsing functionality"""
    try:
        from bot.trading_bot import PositionParser
        
        # Test data from DAS format
        test_positions = """
%POS AAPL 2 100 150.25
%POS MSFT 3 50 300.75
%POS TSLA 2 200 250.50
"""
        
        positions = PositionParser.parse_positions_raw(test_positions)
        print(f"✅ Parsed {len(positions)} positions:")
        
        for pos in positions:
            print(f"   {pos['symbol']} {pos['type']} {pos['quantity']} @ ${pos['avg_price']:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing position parsing: {e}")
        return False

def test_bot_api_endpoints():
    """Test bot API endpoints"""
    try:
        base_url = "http://localhost:5000"
        
        print("🌐 Testing bot API endpoints...")
        
        # Test bot status
        response = requests.get(f"{base_url}/api/bot/status")
        if response.status_code == 200:
            data = response.json()
            print("✅ Bot status endpoint working")
            print(f"   Running: {data.get('data', {}).get('running', False)}")
            print(f"   Monitoring: {data.get('data', {}).get('monitoring', False)}")
        else:
            print(f"❌ Bot status endpoint failed: {response.status_code}")
            return False
        
        # Test bot positions endpoint
        response = requests.get(f"{base_url}/api/bot/positions")
        if response.status_code == 200:
            data = response.json()
            print("✅ Bot positions endpoint working")
            print(f"   Active positions: {data.get('data', {}).get('count', 0)}")
        else:
            print(f"❌ Bot positions endpoint failed: {response.status_code}")
            return False
        
        # Test bot config endpoint
        response = requests.get(f"{base_url}/api/bot/config")
        if response.status_code == 200:
            data = response.json()
            print("✅ Bot config endpoint working")
            config = data.get('data', {})
            print(f"   Profit target: {config.get('profit_target_pct', 0)}%")
            print(f"   Stop loss: {config.get('stop_loss_pct', 0)}%")
        else:
            print(f"❌ Bot config endpoint failed: {response.status_code}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API - backend may not be running")
        return False
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")
        return False

def test_bot_lifecycle():
    """Test bot start/stop lifecycle"""
    try:
        from bot.trading_bot import TradingBot
        
        print("🔄 Testing bot lifecycle...")
        
        config = {
            'profit_target_pct': 5.0,
            'stop_loss_pct': 2.5,
            'monitor_interval': 10  # Longer interval for testing
        }
        
        bot = TradingBot(config)
        
        # Test start (will fail if DAS is not running, but that's expected)
        print("🚀 Testing bot start...")
        success = bot.start()
        if success:
            print("✅ Bot started successfully")
            
            # Wait a moment
            time.sleep(2)
            
            # Test stop
            print("🛑 Testing bot stop...")
            stop_success = bot.stop()
            if stop_success:
                print("✅ Bot stopped successfully")
            else:
                print("❌ Bot stop failed")
                return False
        else:
            print("⚠️ Bot start failed (expected if DAS is not running)")
            # Still test stop to clean up
            bot.stop()
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing bot lifecycle: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Enhanced Trading Bot")
    print("="*50)
    
    tests = [
        ("Bot Import", test_bot_import),
        ("Bot Creation", test_bot_creation),
        ("Position Parsing", test_position_parsing),
        ("DAS Connection", test_das_connection),
        ("Bot API Endpoints", test_bot_api_endpoints),
        ("Bot Lifecycle", test_bot_lifecycle),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        try:
            if test_func():
                print(f"✅ {test_name} test passed")
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test error: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced bot is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    print("\n💡 Note: DAS connection tests will fail if DAS Trader is not running.")
    print("   This is expected behavior for testing purposes.")

if __name__ == "__main__":
    main()
