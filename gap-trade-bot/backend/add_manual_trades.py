#!/usr/bin/env python3
"""
Script to manually add missing trades to the database
"""
import sys
import os
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager

def add_missing_trades():
    """Add missing trades to the database"""
    print("=== Adding Missing Trades to Database ===")
    
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
        
        # Add PLTR trade (entry and exit)
        pltr_entry_trade = {
            'trade_id': int(datetime.now().timestamp() * 1000) % 1000000 + 2,
            'symbol': 'PLTR',
            'side': 'B',  # Buy (entry)
            'quantity': 10,
            'price': 25.00,  # Entry price (approximate)
            'route': 'SMAT',
            'trade_time': '19:20:00',  # Approximate time
            'order_id': 12342,
            'liquidity': '',
            'ecn_fee': 0.0,
            'pnl': 0.0,  # Entry trades have PnL = 0
            'trade_date': '2025-08-20'
        }
        
        pltr_exit_trade = {
            'trade_id': int(datetime.now().timestamp() * 1000) % 1000000 + 3,
            'symbol': 'PLTR',
            'side': 'S',  # Sell (exit)
            'quantity': 10,
            'price': 24.94,  # Exit price (calculated from PnL: -0.60/10 = -0.06, so 25.00 - 0.06 = 24.94)
            'route': 'SMAT',
            'trade_time': '19:25:00',  # Approximate time
            'order_id': 12343,
            'liquidity': '',
            'ecn_fee': 0.0,
            'pnl': -0.60,  # PnL as provided
            'trade_date': '2025-08-20'
        }
        
        # List of trades to add
        trades_to_add = [
            ('TSLA Entry', tsla_entry_trade),
            ('TSLA Exit', tsla_exit_trade),
            ('PLTR Entry', pltr_entry_trade),
            ('PLTR Exit', pltr_exit_trade)
        ]
        
        # Add each trade
        for trade_name, trade_data in trades_to_add:
            print(f"📊 Adding {trade_name}:")
            print(f"   Symbol: {trade_data['symbol']}")
            print(f"   Side: {trade_data['side']}")
            print(f"   Quantity: {trade_data['quantity']}")
            print(f"   Price: ${trade_data['price']:.2f}")
            print(f"   PnL: ${trade_data['pnl']:.2f}")
            
            success, message = db_manager.add_trade(trade_data)
            if success:
                print(f"   ✅ {trade_name} added successfully")
            else:
                print(f"   ❌ Failed to add {trade_name}: {message}")
            print()
        
        # Verify all trades were added
        print("📋 Verifying trades in database:")
        trades = db_manager.get_trades(limit=10)
        if trades:
            for trade in trades:
                print(f"   {trade['symbol']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}")
        else:
            print("   ❌ No trades found in database")
            
    except Exception as e:
        print(f"❌ Error adding trades: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_missing_trades()
