#!/usr/bin/env python3
"""
Test script to verify the trade populator functionality
"""
import sys
import os
import time
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from populate_trades import TradePopulator
from database import db_manager

def test_populate_trades():
    """Test the trade populator functionality"""
    print("=== Testing Trade Populator ===")
    
    # Create populator instance
    populator = TradePopulator()
    
    # Test connection
    print("Testing DAS connection...")
    if populator.connect_to_das():
        print("✅ DAS connection successful")
        
        # Test getting positions
        print("Testing position retrieval...")
        positions_raw = populator.get_current_positions()
        print(f"Raw positions: {repr(positions_raw)}")
        
        if positions_raw and positions_raw.strip():
            from bot.trading_bot import PositionParser
            positions = PositionParser.parse_positions_raw(positions_raw)
            print(f"Parsed {len(positions)} positions:")
            for pos in positions:
                print(f"  {pos['symbol']} {pos['type']} {pos['quantity']} @ ${pos['avg_price']:.2f}")
                print(f"    Realized PnL: ${pos.get('realized_pnl', 0.0):.2f}")
                print(f"    Unrealized PnL: ${pos.get('unrealized_pnl', 0.0):.2f}")
        else:
            print("ℹ️ No positions found")
        
        # Test initialization
        print("Testing position tracking initialization...")
        populator.initialize_position_tracking()
        print(f"Tracked symbols: {list(populator.last_realized_pnl.keys())}")
        
        # Test change detection with current positions
        if positions_raw and positions_raw.strip():
            positions = PositionParser.parse_positions_raw(positions_raw)
            changes = populator.detect_trade_changes(positions)
            print(f"Detected {len(changes)} changes")
            for change in changes:
                print(f"  {change['type']}: {change['symbol']}")
        
        # Disconnect
        populator.disconnect_from_das()
    else:
        print("❌ DAS connection failed")
    
    # Check current database state
    print("\n--- Current Database State ---")
    try:
        trades = db_manager.get_trades(limit=10)
        if trades:
            print(f"Found {len(trades)} trades in database:")
            for trade in trades:
                print(f"  {trade['symbol']} {trade['trade_date']} {trade['trade_time']} {trade['side']} {trade['quantity']} @ ${trade['price']:.2f}, PnL: ${trade['pnl']:.2f}")
        else:
            print("No trades found in database")
    except Exception as e:
        print(f"Error checking database: {e}")

def run_quick_poll():
    """Run a quick poll to test the system"""
    print("\n=== Quick Poll Test ===")
    print("Running a quick poll to test the system...")
    
    populator = TradePopulator()
    
    try:
        # Connect and initialize
        if populator.connect_to_das():
            populator.initialize_position_tracking()
            
            # Do one poll cycle
            print("Performing one poll cycle...")
            positions_raw = populator.get_current_positions()
            
            if positions_raw and positions_raw.strip():
                from bot.trading_bot import PositionParser
                positions = PositionParser.parse_positions_raw(positions_raw)
                changes = populator.detect_trade_changes(positions)
                
                print(f"Poll results: {len(positions)} positions, {len(changes)} changes")
                
                # Save any changes
                for change in changes:
                    populator.save_trade_change(change)
                    print(f"Saved change: {change['type']} for {change['symbol']}")
            else:
                print("No positions found in poll")
            
            populator.disconnect_from_das()
        else:
            print("Failed to connect to DAS")
            
    except Exception as e:
        print(f"Error in quick poll: {e}")

if __name__ == "__main__":
    test_populate_trades()
    run_quick_poll()
