import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DB_PATH = "db/trades.db"

def log_trade_submission(ticker: str, direction: str, action: str, order_type: str, 
                        quantity: int, price: Optional[float] = None, 
                        stop_price: Optional[float] = None, limit_price: Optional[float] = None,
                        order_id: Optional[str] = None, notes: str = "") -> int:
    """
    Log a trade submission to the database
    Returns the trade_id for future updates
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    
    # Convert order_id to string if it's a UUID object
    if order_id is not None:
        order_id = str(order_id)
    
    cursor.execute("""
        INSERT INTO trades (
            ticker, direction, action, order_type, quantity, price, 
            stop_price, limit_price, status, order_id, submitted_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker, direction, action, order_type, quantity, price,
        stop_price, limit_price, 'submitted', order_id, current_time, notes
    ))
    
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"📝 Trade logged: {action.upper()} {quantity} {ticker} at ${price or 'MARKET'}")
    return trade_id

def update_trade_fill(trade_id: int, filled_price: float, filled_quantity: int, 
                     commission: float = 0.0, order_id: Optional[str] = None) -> bool:
    """
    Update a trade when it gets filled
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    
    cursor.execute("""
        UPDATE trades SET 
            status = 'filled',
            filled_at = ?,
            filled_price = ?,
            filled_quantity = ?,
            commission = ?,
            order_id = COALESCE(?, order_id)
        WHERE id = ?
    """, (current_time, filled_price, filled_quantity, commission, order_id, trade_id))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        print(f"✅ Trade filled: ID {trade_id} at ${filled_price}")
        return True
    else:
        conn.close()
        print(f"❌ Trade not found: ID {trade_id}")
        return False

def update_trade_status(trade_id: int, status: str, notes: str = "") -> bool:
    """
    Update trade status (cancelled, rejected, etc.)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE trades SET 
            status = ?,
            notes = CASE WHEN notes = '' THEN ? ELSE notes || '; ' || ? END
        WHERE id = ?
    """, (status, notes, notes, trade_id))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        print(f"📝 Trade status updated: ID {trade_id} -> {status}")
        return True
    else:
        conn.close()
        print(f"❌ Trade not found: ID {trade_id}")
        return False

def get_trade_history(ticker: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """
    Get trade history, optionally filtered by ticker
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if ticker:
        cursor.execute("""
            SELECT * FROM trades 
            WHERE ticker = ? 
            ORDER BY submitted_at DESC 
            LIMIT ?
        """, (ticker, limit))
    else:
        cursor.execute("""
            SELECT * FROM trades 
            ORDER BY submitted_at DESC 
            LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    columns = [description[0] for description in cursor.description]
    trades = []
    for row in rows:
        trades.append(dict(zip(columns, row)))
    
    return trades

def get_trades_by_status(status: str) -> List[Dict]:
    """
    Get all trades with a specific status
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM trades 
        WHERE status = ? 
        ORDER BY submitted_at DESC
    """, (status,))
    
    rows = cursor.fetchall()
    conn.close()
    
    columns = [description[0] for description in cursor.description]
    trades = []
    for row in rows:
        trades.append(dict(zip(columns, row)))
    
    return trades

def get_trade_summary(ticker: Optional[str] = None) -> Dict:
    """
    Get trading summary statistics
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if ticker:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN status = 'filled' THEN 1 END) as filled_trades,
                COUNT(CASE WHEN status = 'submitted' THEN 1 END) as pending_trades,
                SUM(CASE WHEN status = 'filled' THEN filled_quantity * filled_price ELSE 0 END) as total_volume,
                AVG(CASE WHEN status = 'filled' THEN filled_price ELSE NULL END) as avg_fill_price,
                SUM(CASE WHEN status = 'filled' THEN commission ELSE 0 END) as total_commission
            FROM trades 
            WHERE ticker = ?
        """, (ticker,))
    else:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN status = 'filled' THEN 1 END) as filled_trades,
                COUNT(CASE WHEN status = 'submitted' THEN 1 END) as pending_trades,
                SUM(CASE WHEN status = 'filled' THEN filled_quantity * filled_price ELSE 0 END) as total_volume,
                AVG(CASE WHEN status = 'filled' THEN filled_price ELSE NULL END) as avg_fill_price,
                SUM(CASE WHEN status = 'filled' THEN commission ELSE 0 END) as total_commission
            FROM trades
        """)
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'total_trades': row[0],
            'filled_trades': row[1],
            'pending_trades': row[2],
            'total_volume': row[3] or 0,
            'avg_fill_price': row[4] or 0,
            'total_commission': row[5] or 0
        }
    return {}

# Legacy function for backward compatibility
def insert_trade_from_alpaca(order_json):
    """
    Legacy function - use log_trade_submission instead
    """
    return log_trade_submission(
        ticker=order_json.get("symbol"),
        direction="long" if order_json.get("side") == "buy" else "short",
        action=order_json.get("side"),
        order_type="market",  # Default assumption
        quantity=order_json.get("qty"),
        price=float(order_json.get("filled_avg_price", 0.0)),
        order_id=order_json.get("id"),
        notes="Legacy import from Alpaca"
    )