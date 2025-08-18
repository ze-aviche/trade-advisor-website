#!/usr/bin/env python3
"""
Utility script to fix trade dates in the database.
The trades currently have dates in 2025 (future dates) which need to be corrected.
"""

import sqlite3
import os
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_trade_dates():
    """Fix trade dates that are incorrectly set to 2025"""
    db_file = 'trading_advisor.db'
    
    if not os.path.exists(db_file):
        logger.error(f"Database file {db_file} not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # First, let's see what we're working with
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        logger.info(f"Total trades in database: {total_trades}")
        
        cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM trades')
        min_date, max_date = cursor.fetchone()
        logger.info(f"Date range in database: {min_date} to {max_date}")
        
        # Check for trades with 2025 dates
        cursor.execute('SELECT COUNT(*) FROM trades WHERE trade_date LIKE "2025-%"')
        future_trades = cursor.fetchone()[0]
        logger.info(f"Trades with 2025 dates: {future_trades}")
        
        if future_trades == 0:
            logger.info("No trades with 2025 dates found. Nothing to fix.")
            return True
        
        # Get the current date
        current_date = datetime.now().date()
        logger.info(f"Current date: {current_date}")
        
        # Calculate the date offset (difference between 2025 and current year)
        # We'll assume the trades should be from the current year
        year_offset = 2025 - current_date.year
        
        if year_offset <= 0:
            logger.warning("No year offset needed or negative offset. Please check manually.")
            return False
        
        logger.info(f"Year offset to apply: -{year_offset} years")
        
        # Update all trades with 2025 dates
        cursor.execute('''
            UPDATE trades 
            SET trade_date = date(trade_date, '-1 year')
            WHERE trade_date LIKE '2025-%'
        ''')
        
        updated_count = cursor.rowcount
        conn.commit()
        
        logger.info(f"Updated {updated_count} trades with corrected dates")
        
        # Verify the fix
        cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM trades')
        new_min_date, new_max_date = cursor.fetchone()
        logger.info(f"New date range: {new_min_date} to {new_max_date}")
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE trade_date LIKE "2025-%"')
        remaining_future_trades = cursor.fetchone()[0]
        logger.info(f"Remaining trades with 2025 dates: {remaining_future_trades}")
        
        conn.close()
        
        if remaining_future_trades == 0:
            logger.info("✅ Successfully fixed all trade dates!")
            return True
        else:
            logger.warning(f"⚠️ {remaining_future_trades} trades still have 2025 dates")
            return False
            
    except Exception as e:
        logger.error(f"Error fixing trade dates: {e}")
        return False

def show_trade_summary():
    """Show a summary of trades by date"""
    db_file = 'trading_advisor.db'
    
    if not os.path.exists(db_file):
        logger.error(f"Database file {db_file} not found!")
        return
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT trade_date, COUNT(*) as trade_count, 
                   SUM(CASE WHEN side = 'B' THEN quantity ELSE 0 END) as buy_qty,
                   SUM(CASE WHEN side IN ('S', 'SS') THEN quantity ELSE 0 END) as sell_qty,
                   SUM(pnl) as total_pnl
            FROM trades 
            GROUP BY trade_date 
            ORDER BY trade_date DESC 
            LIMIT 10
        ''')
        
        rows = cursor.fetchall()
        logger.info("Recent trades by date:")
        logger.info("Date       | Trades | Buy Qty | Sell Qty | Total PnL")
        logger.info("-" * 50)
        
        for row in rows:
            date, count, buy_qty, sell_qty, total_pnl = row
            logger.info(f"{date} | {count:6d} | {buy_qty:7.0f} | {sell_qty:8.0f} | ${total_pnl:8.2f}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error showing trade summary: {e}")

if __name__ == "__main__":
    logger.info("🔧 Trade Date Fix Utility")
    logger.info("=" * 40)
    
    # Show current state
    show_trade_summary()
    
    # Ask for confirmation
    response = input("\nDo you want to fix the trade dates? (y/N): ")
    if response.lower() in ['y', 'yes']:
        success = fix_trade_dates()
        if success:
            logger.info("\n✅ Trade dates fixed successfully!")
            show_trade_summary()
        else:
            logger.error("\n❌ Failed to fix trade dates")
    else:
        logger.info("Operation cancelled.")
