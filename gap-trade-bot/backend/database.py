#!/usr/bin/env python3
"""
Database Management for Trading Advisor
Handles SQLite database operations for users and sessions
"""
import sqlite3
import os
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

# Use absolute path to ensure consistency
script_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(script_dir, 'trading_advisor.db')

class DatabaseManager:
    def __init__(self):
        self.db_file = DATABASE_FILE
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    preferences TEXT DEFAULT '{}'
                )
            ''')
            
            # Create sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (username) REFERENCES users (username)
                )
            ''')
            
            # Create trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK (side IN ('B', 'S', 'SS')),
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    route TEXT NOT NULL,
                    trade_time TEXT NOT NULL,
                    order_id INTEGER,
                    liquidity TEXT,
                    ecn_fee REAL DEFAULT 0.0,
                    pnl REAL DEFAULT 0.0,
                    trade_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better query performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side)')
            
            conn.commit()
            print(f"✅ Database initialized: {self.db_file}")
    
    def migrate_existing_users(self):
        """Migrate existing users from JSON file to database"""
        users_file = 'users.json'
        if not os.path.exists(users_file):
            return
        
        try:
            with open(users_file, 'r') as f:
                users_data = json.load(f)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for username, user_data in users_data.items():
                    # Check if user already exists
                    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                    if cursor.fetchone():
                        continue
                    
                    # Insert user
                    cursor.execute('''
                        INSERT INTO users (username, email, password_hash, created_at, last_login, preferences)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        username,
                        user_data.get('email', f'{username}@example.com'),
                        user_data.get('password_hash', ''),
                        user_data.get('created_at', datetime.now().isoformat()),
                        user_data.get('last_login', datetime.now().isoformat()),
                        json.dumps(user_data.get('preferences', {}))
                    ))
                
                conn.commit()
                print(f"✅ Migrated {len(users_data)} users from JSON to database")
                
        except Exception as e:
            print(f"⚠️ Error migrating users: {e}")
    
    def create_user(self, username, email, password_hash, preferences=None):
        """Create a new user"""
        if preferences is None:
            preferences = {
                "gap_threshold": 25.0,
                "notifications_enabled": True,
                "theme": "dark"
            }
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, preferences)
                    VALUES (?, ?, ?, ?)
                ''', (username, email, password_hash, json.dumps(preferences)))
                conn.commit()
                return True, "User created successfully"
        except sqlite3.IntegrityError:
            return False, "Username or email already exists"
        except Exception as e:
            return False, f"Database error: {str(e)}"
    
    def get_user_by_username(self, username):
        """Get user by username"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, password_hash, created_at, last_login, preferences
                    FROM users WHERE username = ?
                ''', (username,))
                row = cursor.fetchone()
                
                if row:
                    user = dict(row)
                    user['preferences'] = json.loads(user['preferences'])
                    return user
                return None
        except Exception as e:
            print(f"Database error getting user: {e}")
            return None
    
    def update_last_login(self, username):
        """Update user's last login time"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP
                    WHERE username = ?
                ''', (username,))
                conn.commit()
        except Exception as e:
            print(f"Database error updating last login: {e}")
    
    def create_session(self, session_token, username, expires_at):
        """Create a new session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sessions (session_token, username, expires_at)
                    VALUES (?, ?, ?)
                ''', (session_token, username, expires_at.isoformat()))
                conn.commit()
                return True
        except Exception as e:
            print(f"Database error creating session: {e}")
            return False
    
    def get_session(self, session_token):
        """Get session by token"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT session_token, username, created_at, expires_at
                    FROM sessions WHERE session_token = ?
                ''', (session_token,))
                row = cursor.fetchone()
                
                if row:
                    session = dict(row)
                    # Safely convert string dates to datetime objects
                    if session['expires_at'] and isinstance(session['expires_at'], str):
                        session['expires_at'] = datetime.fromisoformat(session['expires_at'])
                    if session['created_at'] and isinstance(session['created_at'], str):
                        session['created_at'] = datetime.fromisoformat(session['created_at'])
                    return session
                return None
        except Exception as e:
            print(f"Database error getting session: {e}")
            return None
    
    def delete_session(self, session_token):
        """Delete a session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM sessions WHERE session_token = ?', (session_token,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Database error deleting session: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP
                ''')
                deleted_count = cursor.rowcount
                conn.commit()
                if deleted_count > 0:
                    print(f"🧹 Cleaned up {deleted_count} expired sessions")
                return deleted_count
        except Exception as e:
            print(f"Database error cleaning sessions: {e}")
            return 0
    
    def update_user_preferences(self, username, preferences):
        """Update user preferences"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET preferences = ? WHERE username = ?
                ''', (json.dumps(preferences), username))
                conn.commit()
                return True
        except Exception as e:
            print(f"Database error updating preferences: {e}")
            return False
    
    def get_all_users(self):
        """Get all users (for admin purposes)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, created_at, last_login, preferences
                    FROM users ORDER BY created_at DESC
                ''')
                rows = cursor.fetchall()
                users = []
                for row in rows:
                    user = dict(row)
                    user['preferences'] = json.loads(user['preferences'])
                    users.append(user)
                return users
        except Exception as e:
            print(f"Database error getting all users: {e}")
            return []

    def add_trade(self, trade_data):
        """Add a new trade to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trades (
                        trade_id, symbol, side, quantity, price, route, 
                        trade_time, order_id, liquidity, ecn_fee, pnl, trade_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_data['trade_id'],
                    trade_data['symbol'],
                    trade_data['side'],
                    trade_data['quantity'],
                    trade_data['price'],
                    trade_data['route'],
                    trade_data['trade_time'],
                    trade_data.get('order_id'),
                    trade_data.get('liquidity'),
                    trade_data.get('ecn_fee', 0.0),
                    trade_data.get('pnl', 0.0),
                    trade_data['trade_date']
                ))
                conn.commit()
                return True, "Trade added successfully"
        except Exception as e:
            return False, f"Database error adding trade: {str(e)}"
    
    def get_trades(self, symbol=None, start_date=None, end_date=None, limit=100):
        """Get trades with optional filtering"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, trade_id, symbol, side, quantity, price, route, 
                           trade_time, order_id, liquidity, ecn_fee, pnl, 
                           trade_date, created_at
                    FROM trades
                    WHERE 1=1
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                
                query += ' ORDER BY trade_date DESC, trade_time DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                trades = []
                for row in rows:
                    trade = dict(row)
                    # Convert datetime objects to strings for JSON serialization
                    if trade['created_at']:
                        # Check if it's already a string or needs conversion
                        if hasattr(trade['created_at'], 'isoformat'):
                            # It's a datetime object
                            trade['created_at'] = trade['created_at'].isoformat()
                        elif isinstance(trade['created_at'], str):
                            # It's already a string, leave as is
                            pass
                        else:
                            # Convert to string using str() as fallback
                            trade['created_at'] = str(trade['created_at'])
                    trades.append(trade)
                
                return trades
        except Exception as e:
            print(f"Database error getting trades: {e}")
            return []
    
    def get_trade_summary(self, symbol=None, start_date=None, end_date=None):
        """Get trade summary statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        COUNT(*) as total_trades,
                        COALESCE(SUM(CASE WHEN side = 'B' THEN quantity ELSE 0 END), 0) as total_buy_quantity,
                        COALESCE(SUM(CASE WHEN side IN ('S', 'SS') THEN quantity ELSE 0 END), 0) as total_sell_quantity,
                        COALESCE(SUM(CASE WHEN side = 'B' THEN quantity * price ELSE 0 END), 0) as total_buy_value,
                        COALESCE(SUM(CASE WHEN side IN ('S', 'SS') THEN quantity * price ELSE 0 END), 0) as total_sell_value,
                        COALESCE(SUM(pnl), 0) as total_pnl,
                        COALESCE(SUM(ecn_fee), 0) as total_fees
                    FROM trades
                    WHERE 1=1
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    summary = dict(row)
                    
                    # Ensure all values are numbers, not None
                    summary['total_trades'] = summary['total_trades'] or 0
                    summary['total_buy_quantity'] = summary['total_buy_quantity'] or 0
                    summary['total_sell_quantity'] = summary['total_sell_quantity'] or 0
                    summary['total_buy_value'] = summary['total_buy_value'] or 0
                    summary['total_sell_value'] = summary['total_sell_value'] or 0
                    summary['total_pnl'] = summary['total_pnl'] or 0
                    summary['total_fees'] = summary['total_fees'] or 0
                    
                    # Calculate additional metrics with safe arithmetic
                    summary['net_quantity'] = summary['total_buy_quantity'] - summary['total_sell_quantity']
                    summary['net_value'] = summary['total_buy_value'] - summary['total_sell_value']
                    
                    # Safe division with zero checks
                    summary['avg_buy_price'] = (
                        summary['total_buy_value'] / summary['total_buy_quantity'] 
                        if summary['total_buy_quantity'] > 0 else 0
                    )
                    summary['avg_sell_price'] = (
                        summary['total_sell_value'] / summary['total_sell_quantity'] 
                        if summary['total_sell_quantity'] > 0 else 0
                    )
                    
                    return summary
                return None
        except Exception as e:
            print(f"Database error getting trade summary: {e}")
            return None
    
    def parse_das_trades_data(self, das_trades_text):
        """Parse DAS trades data and return list of trade dictionaries"""
        trades = []
        lines = das_trades_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('%TRADE'):
                # Parse trade line: %TRADE 1 MSFT B 100 28.3
                parts = line.split()
                if len(parts) >= 6:
                    trade_data = {
                        'trade_id': int(parts[1]),
                        'symbol': parts[2],
                        'side': parts[3],
                        'quantity': int(parts[4]),
                        'price': float(parts[5]),
                        'route': '',
                        'trade_time': '',
                        'order_id': None,
                        'liquidity': '',
                        'ecn_fee': 0.0,
                        'pnl': 0.0,
                        'trade_date': datetime.now().date().isoformat()
                    }
                    trades.append(trade_data)
        
        return trades

# Global database manager instance
db_manager = DatabaseManager() 