#!/usr/bin/env python3
"""
Simple script to check trades in the database
"""
import sqlite3
import os

# Database file path
script_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(script_dir, 'trading_advisor.db')

def check_trades():
    """Check and display trades in the database"""
    print("=== Checking Trades in Database ===")
    
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Database file not found: {DATABASE_FILE}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_count = cursor.fetchone()[0]
        print(f"📊 Total trades in database: {total_count}")
        
        if total_count > 0:
            # Get recent trades
            cursor.execute('''
                SELECT symbol, side, quantity, price, pnl, trade_date, trade_time 
                FROM trades 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            rows = cursor.fetchall()
            
            print(f"\n📋 Recent trades:")
            for i, row in enumerate(rows, 1):
                symbol, side, quantity, price, pnl, trade_date, trade_time = row
                print(f"  {i}. {symbol} {side} {quantity} @ ${price:.2f}, PnL: ${pnl:.2f}, Date: {trade_date}, Time: {trade_time}")
        else:
            print("📭 No trades found in database")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking trades: {e}")

if __name__ == "__main__":
    check_trades()
