#!/usr/bin/env python3
"""
Script to add the TSLA trade to the database
"""
import sys
import os
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager

def add_tsla_trade():
    """Add TSLA trade to the database"""
    print("=== Adding TSLA Trade to Database ===")
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Add TSLA trade (entry and exit)
        tsla_entry_trade = {
            'trade_id': int(datetime.now().timestamp() * 1000) % 1000000,
            'symbol': 'TSLA',
            'side': 'B',  # Buy (entry)
            'quantity': 10,
            'price': 324.42,  # Entry price
            'route': 'SMAT',
            'trade_time': '19:10:00',  # Approximate time
            'order_id': 12340,
            'liquidity': '',
            'ecn_fee': 0.0,
            'pnl': 0.0,  # Entry trades have PnL = 0
            'trade_date': '2025-08-20'
        }
        
        tsla_exit_trade = {
            'trade_id': int(datetime.now().timestamp() * 1000) % 1000000 + 1,
            'symbol': 'TSLA',
            'side': 'S',  # Sell (exit)
            'quantity': 10,
            'price': 325.50,  # Exit price
            'route': 'SMAT',
            'trade_time': '19:15:00',  # Approximate time
            'order_id': 12341,
            'liquidity': '',
            'ecn_fee': 0.0,
            'pnl': 10.80,  # PnL: (325.50 - 324.42) * 10 = 10.80
            'trade_date': '2025-08-20'
        }
        
        # Add TSLA entry trade
        print(f"📊 Adding TSLA Entry:")
        print(f"   Symbol: {tsla_entry_trade['symbol']}")
        print(f"   Side: {tsla_entry_trade['side']}")
        print(f"   Quantity: {tsla_entry_trade['quantity']}")
        print(f"   Price: ${tsla_entry_trade['price']:.2f}")
        print(f"   PnL: ${tsla_entry_trade['pnl']:.2f}")
        
        success, message = db_manager.add_trade(tsla_entry_trade)
        if success:
            print(f"   ✅ TSLA Entry added successfully")
        else:
            print(f"   ❌ Failed to add TSLA Entry: {message}")
        print()
        
        # Add TSLA exit trade
        print(f"📊 Adding TSLA Exit:")
        print(f"   Symbol: {tsla_exit_trade['symbol']}")
        print(f"   Side: {tsla_exit_trade['side']}")
        print(f"   Quantity: {tsla_exit_trade['quantity']}")
        print(f"   Price: ${tsla_exit_trade['price']:.2f}")
        print(f"   PnL: ${tsla_exit_trade['pnl']:.2f}")
        
        success, message = db_manager.add_trade(tsla_exit_trade)
        if success:
            print(f"   ✅ TSLA Exit added successfully")
        else:
            print(f"   ❌ Failed to add TSLA Exit: {message}")
        print()
        
        # Verify trades were added
        print("📋 Verifying TSLA trades in database:")
        trades = db_manager.get_trades(limit=5)
        if trades:
            for trade in trades:
                print(f"   {trade['symbol']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}")
        else:
            print("   ❌ No trades found in database")
            
    except Exception as e:
        print(f"❌ Error adding TSLA trade: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_tsla_trade()
