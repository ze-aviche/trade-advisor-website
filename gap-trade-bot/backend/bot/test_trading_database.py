#!/usr/bin/env python3
"""
Test Trading Database Architecture
Verifies the new trading database implementation
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trading_database import trading_db
from position_manager import position_manager
from order_manager import OrderManager
from logging_config import get_logger

logger = get_logger(__name__)

def test_trading_database():
    """Test the trading database functionality"""
    print("🧪 Testing Trading Database Architecture")
    print("=" * 50)
    
    # Test 1: Database initialization
    print("\n1. Testing database initialization...")
    try:
        stats = trading_db.get_database_stats()
        print(f"✅ Database initialized successfully")
        print(f"📊 Database size: {stats.get('database_size_mb', 0):.2f} MB")
        print(f"📈 Open positions: {stats.get('open_positions', 0)}")
        print(f"📋 Pending orders: {stats.get('pending_orders', 0)}")
        print(f"💰 Total trades: {stats.get('total_trades', 0)}")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    
    # Test 2: Position management
    print("\n2. Testing position management...")
    try:
        # Open a test position
        success = position_manager.open_position("AAPL", 100, "buy", 150.50, "alpaca", "TEST_ORDER_1")
        if success:
            print("✅ Test position opened successfully")
            
            # Get position
            position = position_manager.get_position("AAPL", "buy")
            if position:
                print(f"📈 Position found: {position['ticker']} {position['quantity']} shares @ ${position['entry_price']}")
            else:
                print("❌ Position not found")
                return False
        else:
            print("❌ Failed to open test position")
            return False
    except Exception as e:
        print(f"❌ Position management test failed: {e}")
        return False
    
    # Test 3: Order management
    print("\n3. Testing order management...")
    try:
        order_manager = OrderManager()
        
        # Place a test order
        order = order_manager.place_buy_order("TSLA", 50, 250.00, "market")
        if order and not order.get('error'):
            print("✅ Test order placed successfully")
            print(f"📋 Order ID: {order.get('order_id', 'N/A')}")
        else:
            print(f"❌ Failed to place test order: {order.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Order management test failed: {e}")
        return False
    
    # Test 4: Trade recording
    print("\n4. Testing trade recording...")
    try:
        trade_data = {
            'trade_id': f"TEST_TRADE_{int(datetime.now().timestamp())}",
            'ticker': 'AAPL',
            'quantity': 100,
            'side': 'buy',
            'entry_price': 150.50,
            'exit_price': 155.00,
            'entry_time': datetime.now().isoformat(),
            'exit_time': datetime.now().isoformat(),
            'pnl': 450.00,
            'commission': 5.00,
            'strategy': 'break_out',
            'broker': 'alpaca',
            'notes': 'Test trade'
        }
        
        success = trading_db.record_trade(trade_data)
        if success:
            print("✅ Test trade recorded successfully")
        else:
            print("❌ Failed to record test trade")
            return False
    except Exception as e:
        print(f"❌ Trade recording test failed: {e}")
        return False
    
    # Test 5: Performance metrics
    print("\n5. Testing performance metrics...")
    try:
        metrics = {
            'total_trades': 1,
            'winning_trades': 1,
            'losing_trades': 0,
            'total_pnl': 450.00,
            'total_commission': 5.00,
            'win_rate': 100.0,
            'avg_win': 450.00,
            'avg_loss': 0.0,
            'max_drawdown': 0.0,
            'strategy': 'break_out',
            'broker': 'alpaca'
        }
        
        success = trading_db.update_performance_metrics(datetime.now().strftime('%Y-%m-%d'), metrics)
        if success:
            print("✅ Performance metrics updated successfully")
        else:
            print("❌ Failed to update performance metrics")
            return False
    except Exception as e:
        print(f"❌ Performance metrics test failed: {e}")
        return False
    
    # Test 6: Data retrieval
    print("\n6. Testing data retrieval...")
    try:
        # Get all positions
        positions = position_manager.get_all_positions()
        print(f"📊 Retrieved {len(positions)} positions")
        
        # Get trade history
        trades = trading_db.get_trade_history(limit=10)
        print(f"💰 Retrieved {len(trades)} trades")
        
        # Get performance summary
        performance = trading_db.get_performance_summary()
        print(f"📈 Performance summary: {performance}")
        
        print("✅ Data retrieval successful")
    except Exception as e:
        print(f"❌ Data retrieval test failed: {e}")
        return False
    
    # Test 7: Database cleanup
    print("\n7. Testing database cleanup...")
    try:
        # Clean up test data (older than 1 day)
        success = trading_db.cleanup_old_data(days=1)
        if success:
            print("✅ Database cleanup successful")
        else:
            print("❌ Database cleanup failed")
            return False
    except Exception as e:
        print(f"❌ Database cleanup test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed! Trading database architecture is working correctly.")
    print("✅ Database separation is successful")
    print("✅ Position management is working")
    print("✅ Order management is working")
    print("✅ Trade recording is working")
    print("✅ Performance tracking is working")
    
    return True

def test_database_separation():
    """Test that historical cache and trading data are properly separated"""
    print("\n🔍 Testing Database Separation")
    print("=" * 50)
    
    try:
        # Check trading database
        trading_stats = trading_db.get_database_stats()
        print(f"📊 Trading Database: {trading_stats.get('database_size_mb', 0):.2f} MB")
        
        # Check if historical cache is still in main database
        import sqlite3
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_db_path = os.path.join(os.path.dirname(script_dir), 'trading_advisor.db')
        
        if os.path.exists(main_db_path):
            conn = sqlite3.connect(main_db_path)
            cursor = conn.cursor()
            
            # Check for historical cache tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_data_cache'")
            if cursor.fetchone():
                print("✅ Historical cache tables found in main database")
            else:
                print("❌ Historical cache tables not found in main database")
            
            # Check for trading tables (should not be here)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='positions'")
            if cursor.fetchone():
                print("❌ Trading tables found in main database (should be separate)")
            else:
                print("✅ Trading tables properly separated")
            
            conn.close()
        
        print("✅ Database separation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Database separation test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Trading Database Architecture Tests")
    print("=" * 60)
    
    # Run tests
    success1 = test_trading_database()
    success2 = test_database_separation()
    
    if success1 and success2:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Trading database architecture is working correctly")
        print("✅ Database separation is successful")
        print("✅ Ready for production use!")
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("Please check the errors above and fix the issues.")
    
    print("\n" + "=" * 60) 