#!/usr/bin/env python3
"""
Script to clear all trades from the database
"""
import sqlite3
import os

# Database file path
script_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(script_dir, 'trading_advisor.db')

def clear_all_trades():
    """Clear all trades from the database"""
    print("=== Clearing All Trades from Database ===")
    
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Database file not found: {DATABASE_FILE}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get count of trades before deletion
        cursor.execute('SELECT COUNT(*) FROM trades')
        before_count = cursor.fetchone()[0]
        print(f"📊 Found {before_count} trades in database")
        
        if before_count > 0:
            # Delete all trades
            cursor.execute('DELETE FROM trades')
            conn.commit()
            
            # Verify deletion
            cursor.execute('SELECT COUNT(*) FROM trades')
            after_count = cursor.fetchone()[0]
            
            print(f"✅ Deleted {before_count - after_count} trades")
            print(f"📊 Remaining trades: {after_count}")
            
            # Reset the auto-increment counter
            cursor.execute('DELETE FROM sqlite_sequence WHERE name="trades"')
            conn.commit()
            print("✅ Reset auto-increment counter")
        else:
            print("ℹ️  No trades to delete")
        
        conn.close()
        print("✅ Database cleared successfully")
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")

if __name__ == "__main__":
    clear_all_trades()
