#!/usr/bin/env python3
"""
Test script to verify the integrated trade populator is working
"""
import sys
import os
import time
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.trading_bot import trading_bot

def test_integrated_populator():
    """Test the integrated trade populator"""
    print("=== Testing Integrated Trade Populator ===")
    
    # Check if bot is running
    print(f"Bot running: {trading_bot.is_running}")
    print(f"Bot monitoring: {trading_bot.monitoring}")
    print(f"DAS connected: {trading_bot.connection is not None}")
    
    # Check trade populator status
    print(f"Trade populator enabled: {trading_bot.trade_populator_enabled}")
    print(f"Trade populator running: {trading_bot.trade_populator_running}")
    
    # Get current positions from DAS
    print("\nGetting current positions from DAS...")
    positions_raw = trading_bot.get_current_positions()
    print(f"Raw positions length: {len(positions_raw) if positions_raw else 0}")
    
    if positions_raw:
        print("First 500 characters of positions:")
        print(positions_raw[:500])
    
    # Test position parsing
    from bot.trading_bot import PositionParser
    positions = PositionParser.parse_positions_raw(positions_raw)
    print(f"\nParsed positions: {len(positions)}")
    
    for pos in positions:
        symbol = pos['symbol']
        realized = pos.get('realized_pnl', 0.0)
        unrealized = pos.get('unrealized_pnl', 0.0)
        quantity = pos.get('quantity', 0)
        print(f"  {symbol}: Qty={quantity}, Realized=${realized:.2f}, Unrealized=${unrealized:.2f}")
    
    # Test trade change detection
    print("\nTesting trade change detection...")
    changes = trading_bot._detect_trade_changes(positions)
    print(f"Detected changes: {len(changes)}")
    
    for change in changes:
        print(f"  {change['symbol']}: PnL change ${change['pnl_change']:.2f}")
    
    # Test manual trade populator start
    print("\nTesting manual trade populator start...")
    trading_bot.start_trade_populator()
    print(f"Trade populator running: {trading_bot.trade_populator_running}")
    print(f"Trade populator thread alive: {trading_bot.trade_populator_thread.is_alive() if trading_bot.trade_populator_thread else 'No thread'}")
    
    # Wait a bit to see if it processes
    print("\nWaiting 5 seconds to see if populator processes...")
    time.sleep(5)
    
    print(f"Trade populator thread still alive: {trading_bot.trade_populator_thread.is_alive() if trading_bot.trade_populator_thread else 'No thread'}")
    
    # Check database for any new trades
    print("\nChecking database for trades...")
    from database import db_manager
    trades = db_manager.get_trades(limit=10)
    print(f"Total trades in database: {len(trades)}")
    for i, trade in enumerate(trades[:5], 1):
        print(f"  {i}. {trade['symbol']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}")

if __name__ == "__main__":
    test_integrated_populator()
