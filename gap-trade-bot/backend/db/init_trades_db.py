import sqlite3
import os
from datetime import datetime

def init_trades_db(db_path="db/trades.db"):
    # Ensure the db directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create comprehensive trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                direction TEXT NOT NULL,  -- 'long' or 'short'
                action TEXT NOT NULL,     -- 'buy', 'sell', 'stop_loss', 'take_profit'
                order_type TEXT NOT NULL, -- 'market', 'limit', 'stop'
                quantity INTEGER NOT NULL,
                price REAL,               -- NULL for market orders
                stop_price REAL,          -- For stop orders
                limit_price REAL,         -- For limit orders
                status TEXT NOT NULL,     -- 'submitted', 'filled', 'cancelled', 'rejected'
                order_id TEXT,            -- Alpaca order ID
                submitted_at TEXT NOT NULL,
                filled_at TEXT,           -- NULL until filled
                filled_price REAL,        -- Actual fill price
                filled_quantity INTEGER,  -- Actual filled quantity
                commission REAL DEFAULT 0.0,
                notes TEXT,               -- Additional notes
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_ticker 
            ON trades(ticker)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp 
            ON trades(submitted_at)
        """)

        conn.commit()
        conn.close()
        print(f"✅ trades.db initialized with comprehensive structure.")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        raise

if __name__ == "__main__":
    init_trades_db()
