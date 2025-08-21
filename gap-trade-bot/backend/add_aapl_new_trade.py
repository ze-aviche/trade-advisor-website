#!/usr/bin/env python3
"""
Script to add the new AAPL trade to the database
"""
import sys
import os
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db_manager

def add_aapl_new_trade():
    """Add the new AAPL trade to the database"""
    print("=== Adding New AAPL Trade ===")
    
    # Trade details from your description and DAS data
    trades = [
        {
            'trade_id': 11467,
            'symbol': 'AAPL',
            'side': 'B',
            'quantity': 20,
            'price': 225.64,
            'route': 'SMAT',
            'trade_time': '20:45:14',
            'order_id': 12336,
            'liquidity': '',
            'ecn_fee': 0.06,
            'pnl': 0.0,  # Entry trade
            'trade_date': '2025-08-20'
        },
        {
            'trade_id': 11468,
            'symbol': 'AAPL',
            'side': 'S',
            'quantity': 20,
            'price': 225.60,
            'route': 'SMAT',
            'trade_time': '20:45:33',
            'order_id': 12337,
            'liquidity': '',
            'ecn_fee': 0.06,
            'pnl': -0.80,  # Exit trade with realized PnL
            'trade_date': '2025-08-20'
        }
    ]
    
    for trade_data in trades:
        print(f"Adding trade: {trade_data['side']} {trade_data['quantity']} {trade_data['symbol']} @ ${trade_data['price']:.2f}")
        
        success, message = db_manager.add_trade(trade_data)
        if success:
            print(f"✅ Trade added successfully")
        else:
            print(f"❌ Failed to add trade: {message}")
    
    print("\n=== Checking Updated Database ===")
    
    # Get recent trades
    try:
        trades = db_manager.get_trades(limit=10)
        if trades:
            print(f"📊 Found {len(trades)} recent trades:")
            for trade in trades:
                print(f"  {trade['symbol']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}, Date: {trade['trade_date']}, Time: {trade['trade_time']}")
        else:
            print("No trades found in database")
    except Exception as e:
        print(f"Error checking trades: {e}")

if __name__ == "__main__":
    add_aapl_new_trade()
