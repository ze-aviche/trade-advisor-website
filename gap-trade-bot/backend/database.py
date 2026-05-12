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

# Use DATABASE_PATH env var if set (e.g. Render persistent disk at /data),
# otherwise fall back to a local file next to this script.
script_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.environ.get(
    'DATABASE_PATH',
    os.path.join(script_dir, 'trading_advisor.db')
)

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
            
            # Create positions table for current position tracking (latest state)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    type INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    avg_cost REAL NOT NULL,
                    init_quantity INTEGER DEFAULT 0,
                    init_price REAL DEFAULT 0.0,
                    realized REAL DEFAULT 0.0,
                    create_time TEXT NOT NULL,
                    date TEXT NOT NULL,
                    unrealized REAL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, type)
                )
            ''')
            
            # Create daily_positions table for daily position history retention
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    type INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    avg_cost REAL NOT NULL,
                    init_quantity INTEGER DEFAULT 0,
                    init_price REAL DEFAULT 0.0,
                    realized REAL DEFAULT 0.0,
                    create_time TEXT NOT NULL,
                    date TEXT NOT NULL,
                    unrealized REAL DEFAULT 0.0,
                    snapshot_date DATE NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, type, snapshot_date)
                )
            ''')
            
            # Gap-up daily snapshots
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gap_up_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    session TEXT NOT NULL,
                    company_name TEXT,
                    price REAL,
                    previous_close REAL,
                    change_amount REAL,
                    gap_percent REAL,
                    volume INTEGER,
                    market_cap INTEGER,
                    float_shares INTEGER DEFAULT 0,
                    sector TEXT,
                    data_source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, ticker)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gap_snapshots_date ON gap_up_snapshots(date)')
            # Migration: add float_shares to existing databases that lack the column
            try:
                cursor.execute('ALTER TABLE gap_up_snapshots ADD COLUMN float_shares INTEGER DEFAULT 0')
            except Exception:
                pass

            # Create indexes for better query performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_type ON positions(type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_updated ON positions(last_updated)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_positions_symbol ON daily_positions(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_positions_type ON daily_positions(type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_positions_date ON daily_positions(snapshot_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_positions_symbol_date ON daily_positions(symbol, snapshot_date)')

            # Email leads for landing page capture
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    source TEXT DEFAULT 'landing_popup',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    welcome_sent INTEGER DEFAULT 0
                )
            ''')

            conn.commit()
            print(f"✅ Database initialized: {self.db_file}")

        self._migrate_schema()

    def _migrate_schema(self):
        """Add new columns to existing tables without data loss"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for column, definition in [
                ('role', "TEXT DEFAULT 'developer'"),
                ('is_active', 'INTEGER DEFAULT 1'),
                ('system_role', 'TEXT DEFAULT NULL'),
                ('subscription_tier', "TEXT DEFAULT 'basic'"),
                ('subscription_status', "TEXT DEFAULT 'active'"),
                ('subscription_expires_at', 'TIMESTAMP DEFAULT NULL'),
                ('stripe_customer_id', 'TEXT DEFAULT NULL'),
                ('stripe_subscription_id', 'TEXT DEFAULT NULL'),
                ('reset_token', 'TEXT DEFAULT NULL'),
                ('reset_token_expires_at', 'TIMESTAMP DEFAULT NULL'),
                ('first_name', 'TEXT DEFAULT NULL'),
                ('last_name', 'TEXT DEFAULT NULL'),
                ('address', 'TEXT DEFAULT NULL'),
                ('profession', 'TEXT DEFAULT NULL'),
                ('annual_income_range', 'TEXT DEFAULT NULL'),
                ('trial_expires_at', 'TIMESTAMP DEFAULT NULL'),
                ('trial_reminder_sent', 'INTEGER DEFAULT 0'),
            ]:
                try:
                    cursor.execute(f'ALTER TABLE users ADD COLUMN {column} {definition}')
                except sqlite3.OperationalError:
                    pass  # column already exists

            # Promote existing 'admin' role users to super_admin system_role
            cursor.execute("UPDATE users SET system_role = 'super_admin' WHERE role = 'admin' AND system_role IS NULL")

            # If still no super_admin exists, promote the earliest user
            cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE system_role = 'super_admin'")
            if cursor.fetchone()['cnt'] == 0:
                cursor.execute("UPDATE users SET system_role = 'super_admin' WHERE id = (SELECT MIN(id) FROM users)")
                if cursor.rowcount:
                    print("✅ Promoted earliest user to super_admin")

            # ── Swing trading columns ─────────────────────────────────────────
            for tbl, col, defn in [
                # positions: tag each row as day or swing
                ('positions',       'position_type',      "TEXT DEFAULT 'day'"),
                ('positions',       'swing_stop_loss',    'REAL DEFAULT NULL'),
                ('positions',       'swing_target',       'REAL DEFAULT NULL'),
                ('positions',       'swing_entry_reason', 'TEXT DEFAULT NULL'),
                ('positions',       'max_hold_days',      'INTEGER DEFAULT NULL'),
                ('positions',       'entry_date',         'TEXT DEFAULT NULL'),
                # daily_positions: same tags for history
                ('daily_positions', 'position_type',      "TEXT DEFAULT 'day'"),
                ('daily_positions', 'swing_stop_loss',    'REAL DEFAULT NULL'),
                ('daily_positions', 'swing_target',       'REAL DEFAULT NULL'),
                # trades: track which style produced the trade
                ('trades',          'position_type',      "TEXT DEFAULT 'day'"),
                ('trades',          'days_held',          'INTEGER DEFAULT NULL'),
            ]:
                try:
                    cursor.execute(f'ALTER TABLE {tbl} ADD COLUMN {col} {defn}')
                except sqlite3.OperationalError:
                    pass  # column already exists

            # swing_bot_config: per-user swing exit settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS swing_bot_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    profit_target_pct REAL DEFAULT 15.0,
                    stop_loss_pct REAL DEFAULT 7.0,
                    trailing_stop_enabled INTEGER DEFAULT 0,
                    trailing_stop_pct REAL DEFAULT 4.0,
                    max_hold_days INTEGER DEFAULT 20,
                    earnings_protection_enabled INTEGER DEFAULT 1,
                    earnings_exit_days INTEGER DEFAULT 2,
                    daily_close_exit_enabled INTEGER DEFAULT 1,
                    breakeven_stop_enabled INTEGER DEFAULT 1,
                    breakeven_trigger_pct REAL DEFAULT 50.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # seed a default row if table is empty
            cursor.execute('SELECT COUNT(*) as cnt FROM swing_bot_config')
            if cursor.fetchone()['cnt'] == 0:
                cursor.execute('INSERT INTO swing_bot_config (user_id) VALUES (1)')

            # brown_bot_config: autonomous BrownBot settings (day + swing + risk + scanner)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS brown_bot_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    day_profit_target_pct REAL DEFAULT 5.0,
                    day_stop_loss_pct REAL DEFAULT 2.5,
                    day_trailing_stop_enabled INTEGER DEFAULT 0,
                    day_trailing_stop_pct REAL DEFAULT 1.5,
                    day_eod_exit_time TEXT DEFAULT '15:45',
                    day_breakeven_trigger_pct REAL DEFAULT 50.0,
                    swing_profit_target_pct REAL DEFAULT 15.0,
                    swing_stop_loss_pct REAL DEFAULT 7.0,
                    swing_max_hold_days INTEGER DEFAULT 20,
                    swing_earnings_protection_enabled INTEGER DEFAULT 1,
                    swing_earnings_exit_days INTEGER DEFAULT 2,
                    swing_breakeven_trigger_pct REAL DEFAULT 50.0,
                    max_daily_loss REAL DEFAULT -500.0,
                    max_concurrent_day INTEGER DEFAULT 3,
                    max_concurrent_swing INTEGER DEFAULT 5,
                    min_gap_pct REAL DEFAULT 10.0,
                    min_price REAL DEFAULT 5.0,
                    max_price REAL DEFAULT 500.0,
                    min_volume_m REAL DEFAULT 0.5,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('SELECT COUNT(*) as cnt FROM brown_bot_config')
            if cursor.fetchone()['cnt'] == 0:
                cursor.execute('INSERT INTO brown_bot_config (user_id) VALUES (1)')

            # brown_watchlist: manually pinned symbols for BrownBot
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS brown_watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL UNIQUE,
                    note TEXT,
                    trade_type TEXT DEFAULT 'day',
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # broker_configs: per-user broker API credentials
            # api_key and api_secret are stored as-is; encrypt at the app layer
            # if required. paper_trading=1 means sandbox/paper environment.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS broker_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    broker_name TEXT NOT NULL,
                    api_key TEXT DEFAULT '',
                    api_secret TEXT DEFAULT '',
                    account_id TEXT DEFAULT '',
                    extra_config TEXT DEFAULT '{}',
                    paper_trading INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, broker_name)
                )
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_broker_configs_user '
                'ON broker_configs(user_id)'
            )

            conn.commit()

    def _get_user_count(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as cnt FROM users')
                return cursor.fetchone()['cnt']
        except Exception:
            return 0

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
    
    def update_user_profile(self, user_id, first_name=None, last_name=None, email=None,
                             address=None, profession=None, annual_income_range=None):
        """Update editable profile fields for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''UPDATE users SET first_name=?, last_name=?, email=?,
                       address=?, profession=?, annual_income_range=? WHERE id=?''',
                    (first_name, last_name, email, address, profession, annual_income_range, user_id)
                )
                conn.commit()
                return True, "Profile updated"
        except sqlite3.IntegrityError:
            return False, "Email is already in use by another account"
        except Exception as e:
            return False, str(e)

    def create_user(self, username, email, password_hash, system_role=None, subscription_tier='basic',
                    preferences=None, first_name=None, last_name=None, address=None,
                    profession=None, annual_income_range=None):
        """Create a new user. First user automatically becomes super_admin."""
        if preferences is None:
            preferences = {"gap_threshold": 25.0, "notifications_enabled": True, "theme": "dark"}

        # First ever user becomes super_admin
        if system_role is None and self._get_user_count() == 0:
            system_role = 'super_admin'

        trial_expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, system_role, subscription_tier,
                                       subscription_status, is_active, preferences,
                                       first_name, last_name, address, profession, annual_income_range,
                                       trial_expires_at)
                    VALUES (?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?, ?, ?, ?)
                ''', (username, email, password_hash, system_role, subscription_tier, json.dumps(preferences),
                      first_name, last_name, address, profession, annual_income_range, trial_expires_at))
                conn.commit()
                return True, "User created successfully"
        except sqlite3.IntegrityError:
            return False, "Username or email already exists"
        except Exception as e:
            return False, f"Database error: {str(e)}"
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, password_hash, system_role, subscription_tier,
                           subscription_status, subscription_expires_at, is_active, created_at, last_login,
                           preferences, stripe_customer_id, stripe_subscription_id,
                           first_name, last_name, address, profession, annual_income_range,
                           trial_expires_at
                    FROM users WHERE id = ?
                ''', (user_id,))
                row = cursor.fetchone()
                if row:
                    user = dict(row)
                    user['preferences'] = json.loads(user['preferences'] or '{}')
                    return user
                return None
        except Exception as e:
            print(f"Database error getting user by id: {e}")
            return None

    def get_user_by_username(self, username):
        """Get user by username"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, password_hash, system_role, subscription_tier,
                           subscription_status, subscription_expires_at, is_active, created_at, last_login,
                           preferences, stripe_customer_id, stripe_subscription_id,
                           first_name, last_name, address, profession, annual_income_range,
                           trial_expires_at
                    FROM users WHERE username = ?
                ''', (username,))
                row = cursor.fetchone()

                if row:
                    user = dict(row)
                    user['preferences'] = json.loads(user['preferences'] or '{}')
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
                    SELECT id, username, email, system_role, subscription_tier,
                           subscription_status, is_active, created_at, last_login
                    FROM users ORDER BY created_at ASC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error getting all users: {e}")
            return []

    def delete_user(self, user_id):
        """Permanently delete a user and their sessions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                row = cursor.fetchone()
                if not row:
                    return False, "User not found"
                cursor.execute('DELETE FROM sessions WHERE username = ?', (row['username'],))
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                conn.commit()
                return True, "User deleted"
        except Exception as e:
            return False, str(e)

    def update_user_password(self, user_id, password_hash):
        """Set a new password hash for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
                conn.commit()
                return True, "Password updated"
        except Exception as e:
            return False, str(e)

    def get_user_by_email(self, email):
        """Look up a user by email address"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, username, email, is_active FROM users WHERE email = ?', (email,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Database error getting user by email: {e}")
            return None

    def set_reset_token(self, user_id, token, expires_at):
        """Store a password-reset token for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET reset_token = ?, reset_token_expires_at = ? WHERE id = ?',
                    (token, expires_at.isoformat(), user_id)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error setting reset token: {e}")
            return False

    def get_user_by_reset_token(self, token):
        """Return the user with the given unexpired reset token, or None"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, username, email, reset_token_expires_at FROM users WHERE reset_token = ?',
                    (token,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error looking up reset token: {e}")
            return None

    def clear_reset_token(self, user_id):
        """Remove reset token after successful use"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET reset_token = NULL, reset_token_expires_at = NULL WHERE id = ?',
                    (user_id,)
                )
                conn.commit()
        except Exception as e:
            print(f"Error clearing reset token: {e}")

    def update_user_system_role(self, user_id, system_role):
        """Set or clear a user's system role"""
        valid = (None, 'super_admin', 'dev_master', 'bot_admin')
        if system_role not in valid:
            return False, "Invalid system role"
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET system_role = ? WHERE id = ?', (system_role, user_id))
                conn.commit()
                return True, "System role updated"
        except Exception as e:
            return False, str(e)

    def update_user_subscription(self, user_id, tier, status='active', subscription_id=None):
        """Change a user's subscription tier, optionally recording the Stripe subscription ID"""
        if tier not in ('basic', 'beginner', 'advanced', 'yogi'):
            return False, "Invalid subscription tier"
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if subscription_id:
                    cursor.execute(
                        'UPDATE users SET subscription_tier=?, subscription_status=?, stripe_subscription_id=? WHERE id=?',
                        (tier, status, subscription_id, user_id)
                    )
                else:
                    cursor.execute(
                        'UPDATE users SET subscription_tier=?, subscription_status=? WHERE id=?',
                        (tier, status, user_id)
                    )
                conn.commit()
                return True, "Subscription updated"
        except Exception as e:
            return False, str(e)

    def cancel_user_subscription(self, user_id):
        """Revert a user to free Basic tier and clear Stripe subscription ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET subscription_tier='basic', subscription_status='cancelled', "
                    "stripe_subscription_id=NULL WHERE id=?",
                    (user_id,)
                )
                conn.commit()
                return True, "Subscription cancelled"
        except Exception as e:
            return False, str(e)

    def update_stripe_customer_id(self, user_id, customer_id):
        """Store the Stripe customer ID for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET stripe_customer_id=? WHERE id=?', (customer_id, user_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error storing stripe_customer_id: {e}")
            return False

    def get_user_by_stripe_customer_id(self, customer_id):
        """Look up a user by their Stripe customer ID (used in webhook handling)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, username, email, subscription_tier, subscription_status, '
                    'stripe_customer_id, stripe_subscription_id, system_role '
                    'FROM users WHERE stripe_customer_id=?',
                    (customer_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error looking up user by stripe_customer_id: {e}")
            return None

    def update_user_active_status(self, user_id, is_active):
        """Activate or deactivate a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET is_active = ? WHERE id = ?', (1 if is_active else 0, user_id))
                conn.commit()
                return True, "Status updated"
        except Exception as e:
            return False, str(e)

    def add_trade(self, trade_data):
        """Add a new trade to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trades (
                        trade_id, symbol, side, quantity, price, route,
                        trade_time, order_id, liquidity, ecn_fee, pnl, trade_date,
                        position_type, days_held
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    trade_data['trade_date'],
                    trade_data.get('position_type', 'day'),
                    trade_data.get('days_held'),
                ))
                conn.commit()
                return True, "Trade added successfully"
        except Exception as e:
            return False, f"Database error adding trade: {str(e)}"
    
    def upsert_position(self, position_data):
        """Upsert position data (insert or update) and save daily snapshot"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get current date for daily snapshot
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                # Check if position exists
                cursor.execute('''
                    SELECT id FROM positions 
                    WHERE symbol = ? AND type = ?
                ''', (position_data['symbol'], position_data['type']))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing position (preserve swing fields if not provided)
                    cursor.execute('''
                        UPDATE positions SET
                            quantity = ?,
                            avg_cost = ?,
                            init_quantity = ?,
                            init_price = ?,
                            realized = ?,
                            create_time = ?,
                            date = ?,
                            unrealized = ?,
                            position_type = COALESCE(?, position_type),
                            entry_date = COALESCE(?, entry_date),
                            swing_stop_loss = COALESCE(?, swing_stop_loss),
                            swing_target = COALESCE(?, swing_target),
                            swing_entry_reason = COALESCE(?, swing_entry_reason),
                            max_hold_days = COALESCE(?, max_hold_days),
                            last_updated = CURRENT_TIMESTAMP
                        WHERE symbol = ? AND type = ?
                    ''', (
                        position_data['quantity'],
                        position_data['avg_cost'],
                        position_data.get('init_quantity', 0),
                        position_data.get('init_price', 0.0),
                        position_data.get('realized', 0.0),
                        position_data['create_time'],
                        position_data['date'],
                        position_data.get('unrealized', 0.0),
                        position_data.get('position_type'),
                        position_data.get('entry_date'),
                        position_data.get('swing_stop_loss'),
                        position_data.get('swing_target'),
                        position_data.get('swing_entry_reason'),
                        position_data.get('max_hold_days'),
                        position_data['symbol'],
                        position_data['type']
                    ))
                else:
                    # Insert new position
                    cursor.execute('''
                        INSERT INTO positions (
                            symbol, type, quantity, avg_cost, init_quantity, init_price,
                            realized, create_time, date, unrealized,
                            position_type, entry_date, swing_stop_loss, swing_target,
                            swing_entry_reason, max_hold_days
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        position_data['symbol'],
                        position_data['type'],
                        position_data['quantity'],
                        position_data['avg_cost'],
                        position_data.get('init_quantity', 0),
                        position_data.get('init_price', 0.0),
                        position_data.get('realized', 0.0),
                        position_data['create_time'],
                        position_data['date'],
                        position_data.get('unrealized', 0.0),
                        position_data.get('position_type', 'day'),
                        position_data.get('entry_date'),
                        position_data.get('swing_stop_loss'),
                        position_data.get('swing_target'),
                        position_data.get('swing_entry_reason'),
                        position_data.get('max_hold_days'),
                    ))

                # Save daily snapshot - upsert to avoid duplicates for the same day
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_positions (
                        symbol, type, quantity, avg_cost, init_quantity, init_price,
                        realized, create_time, date, unrealized, snapshot_date,
                        position_type, swing_stop_loss, swing_target
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    position_data['symbol'],
                    position_data['type'],
                    position_data['quantity'],
                    position_data['avg_cost'],
                    position_data.get('init_quantity', 0),
                    position_data.get('init_price', 0.0),
                    position_data.get('realized', 0.0),
                    position_data['create_time'],
                    position_data['date'],
                    position_data.get('unrealized', 0.0),
                    current_date,
                    position_data.get('position_type', 'day'),
                    position_data.get('swing_stop_loss'),
                    position_data.get('swing_target'),
                ))
                
                conn.commit()
                return True, "Position updated successfully"
                
        except Exception as e:
            return False, f"Database error upserting position: {str(e)}"
    
    def get_positions(self, symbol=None, type_filter=None, limit=100):
        """Get positions with optional filtering"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, symbol, type, quantity, avg_cost, init_quantity, init_price,
                           realized, create_time, date, unrealized, last_updated, created_at
                    FROM positions
                    WHERE 1=1
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if type_filter is not None:
                    query += ' AND type = ?'
                    params.append(type_filter)
                
                query += ' ORDER BY last_updated DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                positions = []
                for row in rows:
                    position = dict(row)
                    positions.append(position)
                
                return positions
                
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []

    def get_position_type(self, symbol: str) -> str:
        """Return the stored position_type ('day' or 'swing') for a symbol, or 'day' if not found."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT position_type FROM positions WHERE symbol = ? ORDER BY last_updated DESC LIMIT 1',
                    (symbol.upper(),)
                )
                row = cursor.fetchone()
                if row and row['position_type']:
                    return row['position_type']
        except Exception as e:
            print(f"Error looking up position_type for {symbol}: {e}")
        return 'day'

    def get_position_summary(self, symbol=None, type_filter=None):
        """Get position summary statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        COUNT(*) as total_positions,
                        SUM(CASE WHEN quantity != 0 THEN 1 ELSE 0 END) as active_positions,
                        SUM(quantity) as total_quantity,
                        SUM(realized) as total_realized,
                        SUM(unrealized) as total_unrealized,
                        SUM(quantity * avg_cost) as total_cost_basis
                    FROM positions
                    WHERE 1=1
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if type_filter is not None:
                    query += ' AND type = ?'
                    params.append(type_filter)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                else:
                    return {
                        'total_positions': 0,
                        'active_positions': 0,
                        'total_quantity': 0,
                        'total_realized': 0.0,
                        'total_unrealized': 0.0,
                        'total_cost_basis': 0.0
                    }
                
        except Exception as e:
            print(f"Error getting position summary: {e}")
            return {
                'total_positions': 0,
                'active_positions': 0,
                'total_quantity': 0,
                'total_realized': 0.0,
                'total_unrealized': 0.0,
                'total_cost_basis': 0.0
            }
    
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

    def get_positions_summary(self):
        """Get positions-based summary statistics for dashboard"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total Positions: count of number of positions in the positions table
                cursor.execute('SELECT COUNT(*) as total_positions FROM positions')
                total_positions = cursor.fetchone()['total_positions']
                
                # Total P&L: Sum of all realized positions
                cursor.execute('SELECT COALESCE(SUM(realized), 0) as total_pnl FROM positions')
                total_pnl = cursor.fetchone()['total_pnl']
                
                # Win Rate: (profitable positions) / (total positions with realized P&L)
                cursor.execute('''
                    SELECT 
                        COALESCE(SUM(CASE WHEN realized > 0 THEN 1 ELSE 0 END), 0) as profitable_positions,
                        COALESCE(SUM(CASE WHEN realized != 0 THEN 1 ELSE 0 END), 0) as total_realized_positions
                    FROM positions
                ''')
                win_rate_data = cursor.fetchone()
                profitable_positions = win_rate_data['profitable_positions']
                total_realized_positions = win_rate_data['total_realized_positions']
                
                # Calculate win rate percentage
                win_rate = (profitable_positions / total_realized_positions * 100) if total_realized_positions > 0 else 0
                
                # Active positions (positions with quantity > 0)
                cursor.execute('SELECT COUNT(*) as active_positions FROM positions WHERE quantity > 0')
                active_positions = cursor.fetchone()['active_positions']
                
                summary = {
                    'total_positions': total_positions,
                    'total_pnl': total_pnl,
                    'win_rate': win_rate,
                    'profitable_positions': profitable_positions,
                    'total_realized_positions': total_realized_positions,
                    'active_positions': active_positions
                }
                
                return summary
        except Exception as e:
            print(f"Database error getting positions summary: {e}")
            return None
    
    def parse_das_trades_data(self, das_trades_text):
        """Parse DAS trades data and return list of trade dictionaries with calculated PnL"""
        trades = []
        lines = das_trades_text.strip().split('\n')
        
        # Group trades by symbol to calculate PnL
        symbol_trades = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('%TRADE'):
                # Parse trade line: %TRADE 1 MSFT B 100 28.3
                parts = line.split()
                if len(parts) >= 6:
                    symbol = parts[2]
                    if symbol not in symbol_trades:
                        symbol_trades[symbol] = []
                    
                    trade_data = {
                        'trade_id': int(parts[1]),
                        'symbol': symbol,
                        'side': parts[3],
                        'quantity': int(parts[4]),
                        'price': float(parts[5]),
                        'route': '',
                        'trade_time': '',
                        'order_id': None,
                        'liquidity': '',
                        'ecn_fee': 0.0,
                        'pnl': 0.0,  # Will be calculated below
                        'trade_date': datetime.now().date().isoformat()
                    }
                    symbol_trades[symbol].append(trade_data)
        
        # Calculate PnL for each symbol's trades
        for symbol, symbol_trade_list in symbol_trades.items():
            # Sort trades by trade_id to ensure proper order
            symbol_trade_list.sort(key=lambda x: x['trade_id'])
            
            # Calculate PnL for closing trades
            for i, trade in enumerate(symbol_trade_list):
                if trade['side'] in ['S', 'SS']:  # Sell trade (closing position)
                    # Find the corresponding buy trade
                    for j in range(i-1, -1, -1):  # Look backwards for buy trade
                        if symbol_trade_list[j]['side'] == 'B':
                            buy_trade = symbol_trade_list[j]
                            # Calculate PnL: (sell_price - buy_price) * quantity
                            pnl = (trade['price'] - buy_trade['price']) * trade['quantity']
                            trade['pnl'] = round(pnl, 2)
                            break
                elif trade['side'] == 'B':  # Buy trade (opening position)
                    # PnL will be calculated when the corresponding sell trade is processed
                    trade['pnl'] = 0.0
        
        # Flatten the trades back to a single list
        for symbol_trade_list in symbol_trades.values():
            trades.extend(symbol_trade_list)
        
        return trades
    
    def recalculate_pnl_for_existing_trades(self):
        """Recalculate PnL for all existing trades in the database using roundtrip logic"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all trades grouped by symbol
                cursor.execute('''
                    SELECT id, trade_id, symbol, side, quantity, price, trade_date
                    FROM trades 
                    ORDER BY symbol, trade_date, trade_time, trade_id
                ''')
                all_trades = cursor.fetchall()
                
                # Group trades by symbol
                symbol_trades = {}
                for trade in all_trades:
                    symbol = trade['symbol']
                    if symbol not in symbol_trades:
                        symbol_trades[symbol] = []
                    symbol_trades[symbol].append(dict(trade))
                
                # Calculate PnL for each symbol's trades using roundtrip logic
                updates_made = 0
                for symbol, trades in symbol_trades.items():
                    # Sort trades by date and time
                    trades.sort(key=lambda x: (x['trade_date'], x.get('trade_time', ''), x['trade_id']))
                    
                    # Separate buy and sell trades
                    buy_trades = [t for t in trades if t['side'] == 'B']
                    sell_trades = [t for t in trades if t['side'] in ['S', 'SS']]
                    
                    # Calculate total quantities
                    total_buy_qty = sum(trade['quantity'] for trade in buy_trades)
                    total_sell_qty = sum(trade['quantity'] for trade in sell_trades)
                    
                    # Only calculate PnL if we have complete roundtrips
                    if total_buy_qty > 0 and total_sell_qty > 0:
                        # Calculate weighted average buy price
                        total_buy_value = sum(trade['quantity'] * (trade['price'] or 0) for trade in buy_trades)
                        avg_buy_price = total_buy_value / total_buy_qty if total_buy_qty > 0 else 0
                        
                        # Calculate weighted average sell price
                        total_sell_value = sum(trade['quantity'] * (trade['price'] or 0) for trade in sell_trades)
                        avg_sell_price = total_sell_value / total_sell_qty if total_sell_qty > 0 else 0
                        
                        # Calculate PnL for the roundtrip
                        if avg_buy_price > 0 and avg_sell_price > 0:
                            roundtrip_qty = min(total_buy_qty, total_sell_qty)
                            pnl = (avg_sell_price - avg_buy_price) * roundtrip_qty
                            pnl = round(pnl, 2)  # Round to 2 decimal places
                            
                            # Update all sell trades with the calculated PnL
                            for sell_trade in sell_trades:
                                cursor.execute('''
                                    UPDATE trades SET pnl = ? WHERE id = ?
                                ''', (pnl, sell_trade['id']))
                                updates_made += 1
                    
                    # Set PnL to 0 for buy trades (opening positions)
                    for buy_trade in buy_trades:
                        cursor.execute('''
                            UPDATE trades SET pnl = 0.0 WHERE id = ?
                        ''', (buy_trade['id'],))
                        updates_made += 1
                
                conn.commit()
                print(f"✅ Recalculated PnL for {updates_made} trades using roundtrip logic")
                return True, f"Successfully recalculated PnL for {updates_made} trades using roundtrip logic"
                
        except Exception as e:
            print(f"Database error recalculating PnL: {e}")
            return False, f"Error recalculating PnL: {str(e)}"

    def get_daily_positions(self, symbol=None, type_filter=None, start_date=None, end_date=None, limit=1000):
        """Get daily position history with optional filtering"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, symbol, type, quantity, avg_cost, init_quantity, init_price,
                           realized, create_time, date, unrealized, snapshot_date, 
                           last_updated, created_at
                    FROM daily_positions
                    WHERE 1=1
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if type_filter is not None:
                    query += ' AND type = ?'
                    params.append(type_filter)
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                query += ' ORDER BY snapshot_date DESC, symbol ASC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                positions = []
                for row in rows:
                    position = dict(row)
                    positions.append(position)
                
                return positions
                
        except Exception as e:
            print(f"Error getting daily positions: {e}")
            return []
    
    def get_daily_position_summary(self, symbol=None, type_filter=None, start_date=None, end_date=None):
        """Get daily position summary statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        COUNT(*) as total_snapshots,
                        COUNT(DISTINCT symbol) as unique_symbols,
                        COUNT(DISTINCT snapshot_date) as unique_dates,
                        SUM(CASE WHEN quantity != 0 THEN 1 ELSE 0 END) as total_active_positions,
                        SUM(quantity) as total_quantity,
                        SUM(realized) as total_realized,
                        SUM(unrealized) as total_unrealized,
                        SUM(quantity * avg_cost) as total_cost_basis
                    FROM daily_positions
                    WHERE 1=1
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if type_filter is not None:
                    query += ' AND type = ?'
                    params.append(type_filter)
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                else:
                    return {
                        'total_snapshots': 0,
                        'unique_symbols': 0,
                        'unique_dates': 0,
                        'total_active_positions': 0,
                        'total_quantity': 0,
                        'total_realized': 0.0,
                        'total_unrealized': 0.0,
                        'total_cost_basis': 0.0
                    }
                
        except Exception as e:
            print(f"Error getting daily position summary: {e}")
            return {
                'total_snapshots': 0,
                'unique_symbols': 0,
                'unique_dates': 0,
                'total_active_positions': 0,
                'total_quantity': 0,
                'total_realized': 0.0,
                'total_unrealized': 0.0,
                'total_cost_basis': 0.0
            }
    
    def get_position_history_by_date(self, date, symbol=None, type_filter=None):
        """Get all positions for a specific date"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, symbol, type, quantity, avg_cost, init_quantity, init_price,
                           realized, create_time, date, unrealized, snapshot_date, 
                           last_updated, created_at
                    FROM daily_positions
                    WHERE snapshot_date = ?
                '''
                params = [date]
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if type_filter is not None:
                    query += ' AND type = ?'
                    params.append(type_filter)
                
                query += ' ORDER BY symbol ASC'
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                positions = []
                for row in rows:
                    position = dict(row)
                    positions.append(position)
                
                return positions
                
        except Exception as e:
            print(f"Error getting position history for date {date}: {e}")
            return []
    
    def get_available_dates(self):
        """Get list of available dates in daily positions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT DISTINCT snapshot_date 
                    FROM daily_positions 
                    ORDER BY snapshot_date DESC
                ''')
                
                rows = cursor.fetchall()
                dates = [row['snapshot_date'] for row in rows]
                return dates
                
        except Exception as e:
            print(f"Error getting available dates: {e}")
            return []

    def get_positions_pnl_history(self, symbol=None, start_date=None, end_date=None, limit=100):
        """Get positions PnL history for charting (similar to trades but using realized field)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, symbol, type, quantity, avg_cost, init_quantity, init_price,
                           realized, create_time, date, unrealized, last_updated, created_at
                    FROM positions
                    WHERE realized != 0
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if start_date:
                    query += ' AND date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND date <= ?'
                    params.append(end_date)
                
                query += ' ORDER BY date DESC, last_updated DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                positions = []
                for row in rows:
                    position = dict(row)
                    # Convert datetime objects to strings for JSON serialization
                    if position['created_at']:
                        if hasattr(position['created_at'], 'isoformat'):
                            position['created_at'] = position['created_at'].isoformat()
                        elif isinstance(position['created_at'], str):
                            pass
                        else:
                            position['created_at'] = str(position['created_at'])
                    
                    if position['last_updated']:
                        if hasattr(position['last_updated'], 'isoformat'):
                            position['last_updated'] = position['last_updated'].isoformat()
                        elif isinstance(position['last_updated'], str):
                            pass
                        else:
                            position['last_updated'] = str(position['last_updated'])
                    
                    positions.append(position)
                
                return positions
        except Exception as e:
            print(f"Database error getting positions PnL history: {e}")
            return []

    def get_positions_pnl_summary(self, symbol=None, start_date=None, end_date=None):
        """Get positions PnL summary statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        COUNT(*) as total_positions,
                        COALESCE(SUM(CASE WHEN realized > 0 THEN 1 ELSE 0 END), 0) as profitable_positions,
                        COALESCE(SUM(CASE WHEN realized < 0 THEN 1 ELSE 0 END), 0) as losing_positions,
                        COALESCE(SUM(realized), 0) as total_pnl,
                        COALESCE(SUM(CASE WHEN realized > 0 THEN realized ELSE 0 END), 0) as total_profits,
                        COALESCE(SUM(CASE WHEN realized < 0 THEN realized ELSE 0 END), 0) as total_losses
                    FROM positions
                    WHERE realized != 0
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if start_date:
                    query += ' AND date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND date <= ?'
                    params.append(end_date)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    summary = dict(row)
                    
                    # Calculate win rate
                    total_positions = summary['total_positions'] or 0
                    profitable_positions = summary['profitable_positions'] or 0
                    win_rate = (profitable_positions / total_positions * 100) if total_positions > 0 else 0
                    
                    summary['win_rate'] = round(win_rate, 2)
                    
                    # Ensure all values are numbers, not None
                    summary['total_positions'] = summary['total_positions'] or 0
                    summary['profitable_positions'] = summary['profitable_positions'] or 0
                    summary['losing_positions'] = summary['losing_positions'] or 0
                    summary['total_pnl'] = summary['total_pnl'] or 0
                    summary['total_profits'] = summary['total_profits'] or 0
                    summary['total_losses'] = summary['total_losses'] or 0
                    
                    return summary
                else:
                    return {
                        'total_positions': 0,
                        'profitable_positions': 0,
                        'losing_positions': 0,
                        'total_pnl': 0,
                        'total_profits': 0,
                        'total_losses': 0,
                        'win_rate': 0
                    }
                
        except Exception as e:
            print(f"Database error getting positions PnL summary: {e}")
            return {
                'total_positions': 0,
                'profitable_positions': 0,
                'losing_positions': 0,
                'total_pnl': 0,
                'total_profits': 0,
                'total_losses': 0,
                'win_rate': 0
            }

    def get_total_positions_count(self, symbol=None, start_date=None, end_date=None):
        """Get total count of positions from daily_positions table for historical stats"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT COUNT(*) as total FROM daily_positions'
                params = []
                
                if symbol:
                    query += ' WHERE symbol = ?'
                    params.append(symbol.upper())
                else:
                    query += ' WHERE 1=1'
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                return row['total'] if row else 0
        except Exception as e:
            print(f"Database error getting total positions count: {e}")
            return 0

    def get_total_positions_pnl(self, symbol=None, start_date=None, end_date=None):
        """Get total P&L from daily_positions table for historical stats"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT COALESCE(SUM(realized), 0) as total_pnl FROM daily_positions WHERE realized != 0'
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                return row['total_pnl'] if row else 0
        except Exception as e:
            print(f"Database error getting total positions P&L: {e}")
            return 0

    def get_positions_winrate(self, symbol=None, start_date=None, end_date=None):
        """Get win rate from daily_positions table for historical stats"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        COALESCE(SUM(CASE WHEN realized > 0 THEN 1 ELSE 0 END), 0) as profitable_positions,
                        COALESCE(SUM(CASE WHEN realized < 0 THEN 1 ELSE 0 END), 0) as losing_positions
                    FROM daily_positions
                    WHERE realized != 0
                '''
                params = []
                
                if symbol:
                    query += ' AND symbol = ?'
                    params.append(symbol.upper())
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    profitable_positions = row['profitable_positions'] or 0
                    losing_positions = row['losing_positions'] or 0
                    total_positions = profitable_positions + losing_positions
                    
                    if total_positions > 0:
                        win_rate = (profitable_positions / total_positions) * 100
                        return round(win_rate, 2)
                    else:
                        return 0
                else:
                    return 0
        except Exception as e:
            print(f"Database error getting positions win rate: {e}")
            return 0

    def get_daily_pnl_data(self, start_date=None, end_date=None):
        """Get daily P&L data from daily_positions table for charting"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        date,
                        COALESCE(SUM(realized), 0) as daily_pnl,
                        COUNT(*) as positions_count
                    FROM daily_positions 
                    WHERE realized != 0
                '''
                params = []
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                query += '''
                    GROUP BY date 
                    ORDER BY date ASC
                '''
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                daily_data = []
                for row in rows:
                    daily_data.append({
                        'date': row['date'],
                        'daily_pnl': float(row['daily_pnl']),
                        'positions_count': row['positions_count']
                    })
                
                return daily_data
        except Exception as e:
            print(f"Database error getting daily P&L data: {e}")
            return []

    def get_cumulative_pnl_data(self, start_date=None, end_date=None):
        """Get cumulative P&L data from daily_positions table for growth tracking"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        date,
                        COALESCE(SUM(realized), 0) as daily_pnl
                    FROM daily_positions 
                    WHERE realized != 0
                '''
                params = []
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                query += '''
                    GROUP BY date 
                    ORDER BY date ASC
                '''
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                cumulative_data = []
                running_total = 0.0
                
                for row in rows:
                    daily_pnl = float(row['daily_pnl'])
                    running_total += daily_pnl
                    cumulative_data.append({
                        'date': row['date'],
                        'daily_pnl': daily_pnl,
                        'cumulative_pnl': running_total
                    })
                
                return cumulative_data
        except Exception as e:
            print(f"Database error getting cumulative P&L data: {e}")
            return []

    def get_long_short_pnl_data(self, start_date=None, end_date=None):
        """Get P&L breakdown by long vs short positions for pie chart"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        CASE 
                            WHEN type = 1 THEN 'Long'
                            WHEN type = 2 THEN 'Short'
                            ELSE 'Unknown'
                        END as position_type,
                        COALESCE(SUM(realized), 0) as total_pnl,
                        COUNT(*) as position_count
                    FROM daily_positions 
                    WHERE realized != 0
                '''
                params = []
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                query += '''
                    GROUP BY type
                    ORDER BY total_pnl DESC
                '''
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                long_short_data = []
                for row in rows:
                    long_short_data.append({
                        'position_type': row['position_type'],
                        'total_pnl': float(row['total_pnl']),
                        'position_count': row['position_count']
                    })
                
                return long_short_data
        except Exception as e:
            print(f"Database error getting long/short P&L data: {e}")
            return []

    def get_symbol_pnl_data(self, start_date=None, end_date=None, limit=10):
        """Get P&L breakdown by symbol for pie chart"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        symbol,
                        COALESCE(SUM(realized), 0) as total_pnl,
                        COUNT(*) as position_count,
                        AVG(realized) as avg_pnl
                    FROM daily_positions 
                    WHERE realized != 0
                '''
                params = []
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                query += '''
                    GROUP BY symbol
                    ORDER BY total_pnl DESC
                    LIMIT ?
                '''
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                symbol_data = []
                for row in rows:
                    symbol_data.append({
                        'symbol': row['symbol'],
                        'total_pnl': float(row['total_pnl']),
                        'position_count': row['position_count'],
                        'avg_pnl': float(row['avg_pnl'])
                    })
                
                return symbol_data
        except Exception as e:
            print(f"Database error getting symbol P&L data: {e}")
            return []

    def get_win_loss_pnl_data(self, start_date=None, end_date=None):
        """Get P&L breakdown by winning vs losing trades for pie chart"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        CASE 
                            WHEN realized > 0 THEN 'Winning'
                            WHEN realized < 0 THEN 'Losing'
                            ELSE 'Break Even'
                        END as trade_result,
                        COALESCE(SUM(realized), 0) as total_pnl,
                        COUNT(*) as position_count
                    FROM daily_positions 
                    WHERE realized != 0
                '''
                params = []
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                query += '''
                    GROUP BY trade_result
                    ORDER BY total_pnl DESC
                '''
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                win_loss_data = []
                for row in rows:
                    win_loss_data.append({
                        'trade_result': row['trade_result'],
                        'total_pnl': float(row['total_pnl']),
                        'position_count': row['position_count']
                    })
                
                return win_loss_data
        except Exception as e:
            print(f"Database error getting win/loss P&L data: {e}")
            return []

    def get_monthly_pnl_data(self, start_date=None, end_date=None):
        """Get P&L breakdown by month for pie chart"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        strftime('%Y-%m', snapshot_date) as month,
                        COALESCE(SUM(realized), 0) as total_pnl,
                        COUNT(*) as position_count
                    FROM daily_positions 
                    WHERE realized != 0
                '''
                params = []
                
                if start_date:
                    query += ' AND snapshot_date >= ?'
                    params.append(start_date)
                
                if end_date:
                    query += ' AND snapshot_date <= ?'
                    params.append(end_date)
                
                query += '''
                    GROUP BY month
                    ORDER BY month ASC
                '''
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                monthly_data = []
                for row in rows:
                    monthly_data.append({
                        'month': row['month'],
                        'total_pnl': float(row['total_pnl']),
                        'position_count': row['position_count']
                    })
                
                return monthly_data
        except Exception as e:
            print(f"Database error getting monthly P&L data: {e}")
            return []

    # ------------------------------------------------------------------
    # Gap-up snapshot methods
    # ------------------------------------------------------------------

    def upsert_gap_up_stocks(self, date_str: str, stocks: list) -> int:
        """
        Upsert gap-up stocks for the day, preserving the original session tag on
        conflict.  Re-fetching during market hours will update price/volume/etc.
        but will NOT overwrite a premarket tag with intraday — the session column
        is intentionally excluded from the ON CONFLICT UPDATE clause.
        Returns number of rows affected.
        """
        if not stocks:
            return 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    '''INSERT INTO gap_up_snapshots
                       (date, ticker, session, company_name, price, previous_close,
                        change_amount, gap_percent, volume, market_cap, float_shares, sector, data_source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(date, ticker) DO UPDATE SET
                           company_name   = excluded.company_name,
                           price          = excluded.price,
                           previous_close = excluded.previous_close,
                           change_amount  = excluded.change_amount,
                           gap_percent    = excluded.gap_percent,
                           volume         = excluded.volume,
                           market_cap     = excluded.market_cap,
                           float_shares   = excluded.float_shares,
                           sector         = excluded.sector,
                           data_source    = excluded.data_source''',
                    [
                        (
                            date_str,
                            s.get('ticker'),
                            s.get('session', 'intraday'),
                            s.get('company_name'),
                            s.get('price'),
                            s.get('previous_close'),
                            s.get('change'),
                            s.get('gap_percent'),
                            s.get('volume'),
                            s.get('market_cap'),
                            s.get('float_shares', 0),
                            s.get('sector'),
                            s.get('data_source'),
                        )
                        for s in stocks if s.get('ticker')
                    ]
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"Database error upserting gap-up stocks: {e}")
            return 0

    def save_gap_up_snapshot(self, date_str: str, stocks: list) -> int:
        """End-of-day snapshot save (overwrites all fields including session)."""
        if not stocks:
            return 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    '''INSERT OR REPLACE INTO gap_up_snapshots
                       (date, ticker, session, company_name, price, previous_close,
                        change_amount, gap_percent, volume, market_cap, float_shares, sector, data_source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    [
                        (
                            date_str,
                            s.get('ticker'),
                            s.get('session', 'intraday'),
                            s.get('company_name'),
                            s.get('price'),
                            s.get('previous_close'),
                            s.get('change'),
                            s.get('gap_percent'),
                            s.get('volume'),
                            s.get('market_cap'),
                            s.get('float_shares', 0),
                            s.get('sector'),
                            s.get('data_source'),
                        )
                        for s in stocks if s.get('ticker')
                    ]
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"Database error saving gap-up snapshot: {e}")
            return 0

    def get_gap_up_snapshot(self, date_str: str) -> list:
        """Return all gap-up stocks stored for *date_str*, sorted by gap% desc."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT ticker, session, company_name, price, previous_close,
                              change_amount AS change, gap_percent, volume, market_cap,
                              float_shares, sector, data_source
                       FROM gap_up_snapshots
                       WHERE date = ?
                       ORDER BY gap_percent DESC''',
                    (date_str,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error fetching gap-up snapshot: {e}")
            return []

    def get_gap_up_snapshot_dates(self) -> list:
        """Return distinct dates that have saved snapshots, newest first."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT DISTINCT date FROM gap_up_snapshots ORDER BY date DESC'
                )
                return [row['date'] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error fetching snapshot dates: {e}")
            return []

    def get_gap_up_ticker_history(self, ticker: str, days: int = None) -> list:
        """Return all gap-up snapshot rows for a given ticker, newest first.
        Optionally filter to only the last *days* calendar days."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if days:
                    from datetime import datetime, timedelta
                    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                    cursor.execute(
                        '''SELECT date, session, company_name, price, previous_close,
                                  change_amount AS change, gap_percent, volume, market_cap,
                                  float_shares, sector, data_source
                           FROM gap_up_snapshots
                           WHERE ticker = ? AND date >= ?
                           ORDER BY date DESC''',
                        (ticker.upper(), cutoff)
                    )
                else:
                    cursor.execute(
                        '''SELECT date, session, company_name, price, previous_close,
                                  change_amount AS change, gap_percent, volume, market_cap,
                                  float_shares, sector, data_source
                           FROM gap_up_snapshots
                           WHERE ticker = ?
                           ORDER BY date DESC''',
                        (ticker.upper(),)
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error fetching ticker history for {ticker}: {e}")
            return []


    def get_trial_expiring_users(self, hours_from_now: int = 24, window_hours: int = 2) -> list:
        """
        Return users whose trial expires within [hours_from_now - window_hours,
        hours_from_now + window_hours] and haven't received a reminder yet.
        Default: trials expiring in 22-26 h from now.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                lo = (datetime.now() + timedelta(hours=hours_from_now - window_hours)).strftime('%Y-%m-%d %H:%M:%S')
                hi = (datetime.now() + timedelta(hours=hours_from_now + window_hours)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''SELECT id, username, email, first_name, trial_expires_at
                       FROM users
                       WHERE trial_expires_at BETWEEN ? AND ?
                         AND trial_reminder_sent = 0
                         AND is_active = 1''',
                    (lo, hi)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error fetching expiring trials: {e}")
            return []

    def mark_trial_reminder_sent(self, user_id: int):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET trial_reminder_sent=1 WHERE id=?', (user_id,))
                conn.commit()
        except Exception as e:
            print(f"Database error marking trial reminder sent: {e}")

    def save_email_lead(self, email: str, source: str = 'landing_popup') -> tuple:
        """Save a lead email. Returns (True, 'new'|'exists')."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT OR IGNORE INTO email_leads (email, source) VALUES (?, ?)',
                    (email.lower().strip(), source)
                )
                conn.commit()
                if cursor.rowcount:
                    return True, 'new'
                return True, 'exists'
        except Exception as e:
            print(f"Database error saving email lead: {e}")
            return False, str(e)

    def get_email_leads(self) -> list:
        """Return all email leads (admin use)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM email_leads ORDER BY created_at DESC')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error fetching leads: {e}")
            return []

    def mark_welcome_sent(self, email: str):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE email_leads SET welcome_sent=1 WHERE email=?', (email.lower().strip(),))
                conn.commit()
        except Exception as e:
            print(f"Database error marking welcome sent: {e}")

    # ── Swing bot config ──────────────────────────────────────────────────────

    def get_swing_bot_config(self, user_id: int = 1) -> dict:
        """Return swing bot config for user_id. Falls back to defaults if row missing."""
        defaults = {
            'profit_target_pct': 15.0,
            'stop_loss_pct': 7.0,
            'trailing_stop_enabled': False,
            'trailing_stop_pct': 4.0,
            'max_hold_days': 20,
            'earnings_protection_enabled': True,
            'earnings_exit_days': 2,
            'daily_close_exit_enabled': True,
            'breakeven_stop_enabled': True,
            'breakeven_trigger_pct': 50.0,
        }
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM swing_bot_config WHERE user_id=? LIMIT 1', (user_id,))
                row = cursor.fetchone()
                if row:
                    cfg = dict(row)
                    cfg['trailing_stop_enabled'] = bool(cfg.get('trailing_stop_enabled', 0))
                    cfg['earnings_protection_enabled'] = bool(cfg.get('earnings_protection_enabled', 1))
                    cfg['daily_close_exit_enabled'] = bool(cfg.get('daily_close_exit_enabled', 1))
                    cfg['breakeven_stop_enabled'] = bool(cfg.get('breakeven_stop_enabled', 1))
                    return cfg
        except Exception as e:
            print(f"Database error fetching swing config: {e}")
        return defaults

    def update_swing_bot_config(self, config: dict, user_id: int = 1) -> tuple:
        """Upsert swing bot config for user_id."""
        fields = [
            'profit_target_pct', 'stop_loss_pct', 'trailing_stop_enabled',
            'trailing_stop_pct', 'max_hold_days', 'earnings_protection_enabled',
            'earnings_exit_days', 'daily_close_exit_enabled',
            'breakeven_stop_enabled', 'breakeven_trigger_pct',
        ]
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM swing_bot_config WHERE user_id=?', (user_id,))
                row = cursor.fetchone()
                if row:
                    sets = ', '.join(f'{f}=?' for f in fields if f in config)
                    vals = [config[f] for f in fields if f in config]
                    if sets:
                        vals.append(user_id)
                        cursor.execute(f'UPDATE swing_bot_config SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE user_id=?', vals)
                else:
                    cursor.execute('INSERT INTO swing_bot_config (user_id) VALUES (?)', (user_id,))
                    sets = ', '.join(f'{f}=?' for f in fields if f in config)
                    vals = [config[f] for f in fields if f in config]
                    if sets:
                        vals.append(user_id)
                        cursor.execute(f'UPDATE swing_bot_config SET {sets} WHERE user_id=?', vals)
                conn.commit()
                return True, "Swing config updated"
        except Exception as e:
            return False, f"Database error updating swing config: {e}"


    # ── BrownBot config ──────────────────────────────────────────────────────

    def get_brown_bot_config(self, user_id: int = 1) -> dict:
        defaults = {
            'day_profit_target_pct': 5.0, 'day_stop_loss_pct': 2.5,
            'day_trailing_stop_enabled': False, 'day_trailing_stop_pct': 1.5,
            'day_eod_exit_time': '15:45', 'day_breakeven_trigger_pct': 50.0,
            'swing_profit_target_pct': 15.0, 'swing_stop_loss_pct': 7.0,
            'swing_max_hold_days': 20, 'swing_earnings_protection_enabled': True,
            'swing_earnings_exit_days': 2, 'swing_breakeven_trigger_pct': 50.0,
            'max_daily_loss': -500.0, 'max_concurrent_day': 3, 'max_concurrent_swing': 5,
            'min_gap_pct': 10.0, 'min_price': 5.0, 'max_price': 500.0, 'min_volume_m': 0.5,
        }
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM brown_bot_config WHERE user_id=? LIMIT 1', (user_id,))
                row = cursor.fetchone()
                if row:
                    cfg = dict(row)
                    cfg['day_trailing_stop_enabled'] = bool(cfg.get('day_trailing_stop_enabled', 0))
                    cfg['swing_earnings_protection_enabled'] = bool(cfg.get('swing_earnings_protection_enabled', 1))
                    return cfg
        except Exception as e:
            print(f"Database error fetching brown_bot_config: {e}")
        return defaults

    def update_brown_bot_config(self, config: dict, user_id: int = 1) -> tuple:
        fields = [
            'day_profit_target_pct', 'day_stop_loss_pct', 'day_trailing_stop_enabled',
            'day_trailing_stop_pct', 'day_eod_exit_time', 'day_breakeven_trigger_pct',
            'swing_profit_target_pct', 'swing_stop_loss_pct', 'swing_max_hold_days',
            'swing_earnings_protection_enabled', 'swing_earnings_exit_days',
            'swing_breakeven_trigger_pct', 'max_daily_loss', 'max_concurrent_day',
            'max_concurrent_swing', 'min_gap_pct', 'min_price', 'max_price', 'min_volume_m',
        ]
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM brown_bot_config WHERE user_id=?', (user_id,))
                row = cursor.fetchone()
                sets = ', '.join(f'{f}=?' for f in fields if f in config)
                vals = [config[f] for f in fields if f in config]
                if sets:
                    if row:
                        vals.append(user_id)
                        cursor.execute(f'UPDATE brown_bot_config SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE user_id=?', vals)
                    else:
                        cursor.execute('INSERT INTO brown_bot_config (user_id) VALUES (?)', (user_id,))
                        vals.append(user_id)
                        cursor.execute(f'UPDATE brown_bot_config SET {sets} WHERE user_id=?', vals)
                conn.commit()
                return True, "BrownBot config updated"
        except Exception as e:
            return False, f"Database error updating brown_bot_config: {e}"

    # ── BrownBot watchlist ────────────────────────────────────────────────────

    def get_brown_watchlist(self) -> list:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT symbol, note, trade_type, added_at FROM brown_watchlist ORDER BY added_at DESC')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error fetching brown_watchlist: {e}")
            return []

    def add_to_brown_watchlist(self, symbol: str, note: str = '', trade_type: str = 'day') -> tuple:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT OR REPLACE INTO brown_watchlist (symbol, note, trade_type) VALUES (?, ?, ?)',
                    (symbol.upper().strip(), note, trade_type)
                )
                conn.commit()
                return True, "Added to watchlist"
        except Exception as e:
            return False, str(e)

    def remove_from_brown_watchlist(self, symbol: str) -> tuple:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM brown_watchlist WHERE symbol=?', (symbol.upper().strip(),))
                conn.commit()
                return True, "Removed from watchlist"
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Broker config CRUD
    # ------------------------------------------------------------------

    def get_broker_configs(self, user_id: int = 1) -> list:
        """Return all broker configs for *user_id*, newest first."""
        try:
            import json
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT broker_name, api_key, api_secret, account_id,
                              extra_config, paper_trading, is_active, updated_at
                       FROM broker_configs WHERE user_id=? ORDER BY updated_at DESC''',
                    (user_id,)
                )
                rows = []
                for r in cursor.fetchall():
                    row = dict(r)
                    try:
                        row['extra_config'] = json.loads(row.get('extra_config') or '{}')
                    except Exception:
                        row['extra_config'] = {}
                    # Never send secrets to the caller in plaintext
                    row['api_key_set']    = bool(row.get('api_key'))
                    row['api_secret_set'] = bool(row.get('api_secret'))
                    del row['api_key'], row['api_secret']
                    rows.append(row)
                return rows
        except Exception as e:
            print(f'Database error fetching broker_configs: {e}')
            return []

    def get_broker_config(self, broker_name: str, user_id: int = 1) -> dict:
        """Return the raw config (including secrets) for a specific broker."""
        try:
            import json
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT broker_name, api_key, api_secret, account_id,
                              extra_config, paper_trading, is_active
                       FROM broker_configs WHERE user_id=? AND broker_name=? LIMIT 1''',
                    (user_id, broker_name)
                )
                row = cursor.fetchone()
                if not row:
                    return {}
                result = dict(row)
                try:
                    result['extra_config'] = json.loads(result.get('extra_config') or '{}')
                except Exception:
                    result['extra_config'] = {}
                return result
        except Exception as e:
            print(f'Database error fetching broker_config {broker_name}: {e}')
            return {}

    def upsert_broker_config(self, broker_name: str, config: dict,
                              user_id: int = 1) -> tuple:
        """
        Insert or update a broker config row.
        Pass api_key / api_secret only when the user explicitly sets them
        (empty string means "leave existing value unchanged").
        """
        import json
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, api_key, api_secret FROM broker_configs '
                    'WHERE user_id=? AND broker_name=?',
                    (user_id, broker_name)
                )
                existing = cursor.fetchone()

                api_key    = config.get('api_key',    '') or (existing['api_key']    if existing else '')
                api_secret = config.get('api_secret', '') or (existing['api_secret'] if existing else '')
                account_id    = config.get('account_id', '')
                extra_config  = json.dumps(config.get('extra_config', {}))
                paper_trading = int(config.get('paper_trading', 1))
                is_active     = int(config.get('is_active', 1))

                if existing:
                    cursor.execute(
                        '''UPDATE broker_configs
                           SET api_key=?, api_secret=?, account_id=?,
                               extra_config=?, paper_trading=?, is_active=?,
                               updated_at=CURRENT_TIMESTAMP
                           WHERE user_id=? AND broker_name=?''',
                        (api_key, api_secret, account_id, extra_config,
                         paper_trading, is_active, user_id, broker_name)
                    )
                else:
                    cursor.execute(
                        '''INSERT INTO broker_configs
                           (user_id, broker_name, api_key, api_secret, account_id,
                            extra_config, paper_trading, is_active)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (user_id, broker_name, api_key, api_secret, account_id,
                         extra_config, paper_trading, is_active)
                    )
                conn.commit()
                return True, 'Broker config saved'
        except Exception as e:
            return False, str(e)

    def delete_broker_config(self, broker_name: str, user_id: int = 1) -> tuple:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM broker_configs WHERE user_id=? AND broker_name=?',
                    (user_id, broker_name)
                )
                conn.commit()
                return True, 'Broker config deleted'
        except Exception as e:
            return False, str(e)


# Global database manager instance
db_manager = DatabaseManager()