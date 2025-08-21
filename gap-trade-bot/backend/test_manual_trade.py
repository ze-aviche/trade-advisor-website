#!/usr/bin/env python3
"""
Test script to manually add a trade to the database
This will help verify that the database connection and trade saving is working
"""
import sys
import os
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager

def test_manual_trade():
    """Test adding a manual trade to the database"""
    print("=== Testing Manual Trade Addition ===")
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Create a test trade data
        test_trade = {
            'trade_id': int(datetime.now().timestamp() * 1000) % 1000000,
            'symbol': 'TSLA',
            'side': 'S',  # Sell
            'quantity': 10,
            'price': 325.50,  # Example execution price
            'route': 'SMAT',
            'trade_time': datetime.now().strftime('%H:%M:%S'),
            'order_id': 12345,
            'liquidity': '',
            'ecn_fee': 0.0,
            'pnl': 10.80,  # Example PnL: (325.50 - 324.42) * 10 = 10.80
            'trade_date': datetime.now().date().isoformat()
        }
        
        print(f"📊 Test trade data:")
        print(f"   Symbol: {test_trade['symbol']}")
        print(f"   Side: {test_trade['side']}")
        print(f"   Quantity: {test_trade['quantity']}")
        print(f"   Price: ${test_trade['price']:.2f}")
        print(f"   PnL: ${test_trade['pnl']:.2f}")
        print(f"   Trade ID: {test_trade['trade_id']}")
        
        # Add trade to database
        success, message = db_manager.add_trade(test_trade)
        
        if success:
            print(f"✅ Trade successfully added to database!")
            print(f"   Message: {message}")
            
            # Verify the trade was added
            trades = db_manager.get_trades(limit=5)
            if trades:
                print(f"📋 Recent trades in database:")
                for trade in trades:
                    print(f"   {trade['symbol']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}")
            else:
                print("❌ No trades found in database")
        else:
            print(f"❌ Failed to add trade: {message}")
            
    except Exception as e:
        print(f"❌ Error testing manual trade: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_manual_trade()
