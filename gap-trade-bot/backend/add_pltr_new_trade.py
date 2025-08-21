#!/usr/bin/env python3
"""
Script to add the new PLTR trade to the database
"""
import sys
import os
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db_manager

def add_pltr_new_trade():
    """Add the new PLTR trade to the database"""
    print("=== Adding New PLTR Trade ===")
    
    # Trade details from DAS data
    trades = [
        {
            'trade_id': 11469,
            'symbol': 'PLTR',
            'side': 'B',
            'quantity': 20,
            'price': 159.24,
            'route': 'SMAT',
            'trade_time': '20:48:08',
            'order_id': 12338,
            'liquidity': '',
            'ecn_fee': 0.06,
            'pnl': 0.0,  # Entry trade
            'trade_date': '2025-08-20'
        },
        {
            'trade_id': 11470,
            'symbol': 'PLTR',
            'side': 'S',
            'quantity': 20,
            'price': 159.18,
            'route': 'SMAT',
            'trade_time': '20:48:15',
            'order_id': 12339,
            'liquidity': '',
            'ecn_fee': 0.06,
            'pnl': -1.20,  # Exit trade with PnL
            'trade_date': '2025-08-20'
        }
    ]
    
    # Add trades to database
    for trade_data in trades:
        print(f"Adding trade: {trade_data['symbol']} {trade_data['side']} {trade_data['quantity']} @ ${trade_data['price']:.2f}")
        success, message = db_manager.add_trade(trade_data)
        if success:
            print(f"✅ Trade added successfully: {message}")
        else:
            print(f"❌ Failed to add trade: {message}")
    
    print("\n=== Checking Updated Database ===")
    
    # Get recent trades
    success, trades = db_manager.get_recent_trades(10)
    if success:
        print(f"📊 Total trades in database: {len(trades)}")
        print("\n📋 Recent trades:")
        for i, trade in enumerate(trades, 1):
            print(f"  {i}. {trade['symbol']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}, Date: {trade['trade_date']}, Time: {trade['trade_time']}")
    else:
        print(f"❌ Error getting trades: {trades}")

if __name__ == "__main__":
    add_pltr_new_trade()
