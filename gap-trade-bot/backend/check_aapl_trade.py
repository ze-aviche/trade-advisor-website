#!/usr/bin/env python3
"""
Script to check for AAPL trades and manually detect realized PnL changes
"""
import sys
import os
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.trading_bot import trading_bot, PositionParser
from database import db_manager

def check_aapl_trade():
    """Check for AAPL trades and detect any realized PnL changes"""
    print("=== Checking AAPL Trade Status ===")
    
    # Check if bot is running
    print(f"Bot running: {trading_bot.is_running}")
    print(f"Bot monitoring: {trading_bot.monitoring}")
    print(f"DAS connected: {trading_bot.connection is not None}")
    
    # Get current positions from DAS
    print("\n--- Current Positions from DAS ---")
    positions_raw = trading_bot.get_current_positions()
    print(f"Raw positions: {repr(positions_raw)}")
    
    if positions_raw and positions_raw.strip():
        positions = PositionParser.parse_positions_raw(positions_raw)
        print(f"Parsed {len(positions)} positions:")
        for pos in positions:
            print(f"  {pos['symbol']} {pos['type']} {pos['quantity']} @ ${pos['avg_price']:.2f}")
            print(f"    Realized PnL: ${pos.get('realized_pnl', 0.0):.2f}")
            print(f"    Unrealized PnL: ${pos.get('unrealized_pnl', 0.0):.2f}")
    else:
        print("No positions found in DAS")
    
    # Check database for any AAPL trades
    print("\n--- AAPL Trades in Database ---")
    try:
        trades = db_manager.get_trades(symbol='AAPL', limit=10)
        if trades:
            print(f"Found {len(trades)} AAPL trades:")
            for trade in trades:
                print(f"  {trade['trade_date']} {trade['trade_time']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}")
        else:
            print("No AAPL trades found in database")
    except Exception as e:
        print(f"Error checking database: {e}")
    
    # Check all recent trades
    print("\n--- Recent Trades in Database ---")
    try:
        all_trades = db_manager.get_trades(limit=10)
        if all_trades:
            print(f"Found {len(all_trades)} recent trades:")
            for trade in all_trades:
                print(f"  {trade['symbol']} {trade['trade_date']} {trade['trade_time']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}")
        else:
            print("No trades found in database")
    except Exception as e:
        print(f"Error checking recent trades: {e}")
    
    # Check realized PnL tracking
    print("\n--- Realized PnL Tracking ---")
    print(f"Tracked symbols: {list(trading_bot.last_realized_pnl.keys())}")
    for symbol, pnl in trading_bot.last_realized_pnl.items():
        print(f"  {symbol}: ${pnl:.2f}")

if __name__ == "__main__":
    check_aapl_trade()
