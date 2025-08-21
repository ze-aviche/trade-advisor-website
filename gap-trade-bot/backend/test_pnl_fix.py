#!/usr/bin/env python3
"""
Test script to verify PnL calculation and database storage
"""
import sqlite3
import os
from datetime import datetime

# Database file path
script_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(script_dir, 'trading_advisor.db')

def test_pnl_calculation():
    """Test PnL calculation logic with rounding"""
    print("=== Testing PnL Calculation Logic (with rounding) ===")
    
    # Test cases with decimal values to test rounding
    test_cases = [
        {"type": "LONG", "entry_price": 10.0, "exit_price": 12.0, "quantity": 100, "expected_pnl": 200.0},
        {"type": "LONG", "entry_price": 10.0, "exit_price": 8.0, "quantity": 100, "expected_pnl": -200.0},
        {"type": "SHORT", "entry_price": 10.0, "exit_price": 8.0, "quantity": 100, "expected_pnl": 200.0},
        {"type": "SHORT", "entry_price": 10.0, "exit_price": 12.0, "quantity": 100, "expected_pnl": -200.0},
        {"type": "LONG", "entry_price": 10.123, "exit_price": 12.456, "quantity": 100, "expected_pnl": 233.3},  # Should round to 233.30
        {"type": "SHORT", "entry_price": 15.789, "exit_price": 14.321, "quantity": 50, "expected_pnl": 73.4}   # Should round to 73.40
    ]
    
    for i, case in enumerate(test_cases, 1):
        if case["type"] == "LONG":
            pnl = (case["exit_price"] - case["entry_price"]) * case["quantity"]
        else:
            pnl = (case["entry_price"] - case["exit_price"]) * case["quantity"]
        
        # Round PnL to 2 decimal places
        pnl = round(pnl, 2)
        
        print(f"Test {i}: {case['type']} {case['quantity']} @ ${case['entry_price']:.2f} -> ${case['exit_price']:.2f}")
        print(f"  Expected PnL: ${case['expected_pnl']:.2f}, Calculated PnL: ${pnl:.2f}")
        print(f"  {'✅ PASS' if abs(pnl - case['expected_pnl']) < 0.01 else '❌ FAIL'}")
        print()

def check_database_trades():
    """Check current trades in database"""
    print("=== Current Trades in Database ===")
    
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Database file not found: {DATABASE_FILE}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get recent trades
        cursor.execute('''
            SELECT symbol, side, quantity, price, pnl, trade_date, trade_time, created_at
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        
        rows = cursor.fetchall()
        
        if not rows:
            print("No trades found in database")
        else:
            print(f"Found {len(rows)} recent trades:")
            print("-" * 80)
            for row in rows:
                symbol, side, quantity, price, pnl, trade_date, trade_time, created_at = row
                print(f"Symbol: {symbol:6} | Side: {side} | Qty: {quantity:4} | Price: ${price:8.2f} | PnL: ${pnl:8.2f} | Date: {trade_date} | Time: {trade_time}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error accessing database: {e}")

def test_database_insert():
    """Test inserting a trade with PnL to database"""
    print("\n=== Testing Database Insert with PnL ===")
    
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Database file not found: {DATABASE_FILE}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Test trade data
        test_trade = {
            'trade_id': int(datetime.now().timestamp() * 1000) % 1000000,
            'symbol': 'TEST',
            'side': 'S',
            'quantity': 100,
            'price': 12.50,
            'route': 'SMAT',
            'trade_time': datetime.now().strftime('%H:%M:%S'),
            'order_id': 12345,
            'liquidity': '',
            'ecn_fee': 0.0,
            'pnl': 250.0,  # Test PnL value
            'trade_date': datetime.now().date().isoformat()
        }
        
        # Insert test trade
        cursor.execute('''
            INSERT INTO trades (
                trade_id, symbol, side, quantity, price, route, 
                trade_time, order_id, liquidity, ecn_fee, pnl, trade_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_trade['trade_id'],
            test_trade['symbol'],
            test_trade['side'],
            test_trade['quantity'],
            test_trade['price'],
            test_trade['route'],
            test_trade['trade_time'],
            test_trade['order_id'],
            test_trade['liquidity'],
            test_trade['ecn_fee'],
            test_trade['pnl'],
            test_trade['trade_date']
        ))
        
        conn.commit()
        print(f"✅ Test trade inserted successfully")
        print(f"   Symbol: {test_trade['symbol']}, Side: {test_trade['side']}, Qty: {test_trade['quantity']}")
        print(f"   Price: ${test_trade['price']:.2f}, PnL: ${test_trade['pnl']:.2f}")
        
        # Verify the insert
        cursor.execute('SELECT symbol, side, quantity, price, pnl FROM trades WHERE symbol = ? ORDER BY created_at DESC LIMIT 1', ('TEST',))
        row = cursor.fetchone()
        if row:
            symbol, side, quantity, price, pnl = row
            print(f"✅ Verified in database: {symbol} {side} {quantity} @ ${price:.2f}, PnL: ${pnl:.2f}")
        else:
            print("❌ Could not verify test trade in database")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error testing database insert: {e}")

if __name__ == "__main__":
    test_pnl_calculation()
    check_database_trades()
    test_database_insert()
