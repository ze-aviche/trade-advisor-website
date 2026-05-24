#!/usr/bin/env python3
"""
Database Management for Trading Advisor
Handles SQLite database operations for users and sessions
"""
import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

_db_logger = logging.getLogger(__name__)

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
            
            # Drop the legacy DAS-only positions table — BrownBot never uses it
            cursor.execute('DROP TABLE IF EXISTS positions')

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
                ('email_digest_enabled', 'INTEGER DEFAULT 1'),
                ('email_digest_unsubscribe_token', 'TEXT DEFAULT NULL'),
            ]:
                try:
                    cursor.execute(f'ALTER TABLE users ADD COLUMN {column} {definition}')
                except sqlite3.OperationalError:
                    pass  # column already exists

            # Generate unsubscribe tokens for users that don't have one yet
            import uuid as _uuid
            cursor.execute('SELECT id FROM users WHERE email_digest_unsubscribe_token IS NULL')
            for _row in cursor.fetchall():
                cursor.execute('UPDATE users SET email_digest_unsubscribe_token = ? WHERE id = ?',
                               (str(_uuid.uuid4()), _row['id']))

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
                # daily_positions: same tags for history
                ('daily_positions', 'position_type',      "TEXT DEFAULT 'day'"),
                ('daily_positions', 'swing_stop_loss',    'REAL DEFAULT NULL'),
                ('daily_positions', 'swing_target',       'REAL DEFAULT NULL'),
                # trades: track which style produced the trade
                ('trades',          'position_type',      "TEXT DEFAULT 'day'"),
                ('trades',          'days_held',          'INTEGER DEFAULT NULL'),
                ('trades',          'source',             "TEXT DEFAULT 'brownbot'"),
                ('trades',          'broker',             'TEXT DEFAULT NULL'),
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

            # brown_bot_config: additive migrations
            for col, defn in [
                ('day_time_gate_enabled',  'INTEGER DEFAULT 1'),
                ('day_time_gate_start',    "TEXT DEFAULT '09:35'"),
                ('day_time_gate_end',      "TEXT DEFAULT '10:30'"),
                ('max_float_m',            'REAL DEFAULT 0.0'),
                ('float_operator',         "TEXT DEFAULT '<='"),
                ('day_check_vwap',         'INTEGER DEFAULT 0'),
                ('day_check_candle',       'INTEGER DEFAULT 0'),
                ('day_max_extension_pct',  'REAL DEFAULT 0.0'),
                ('day_check_volume_surge', 'INTEGER DEFAULT 0'),
                ('day_ai_playbook',        'INTEGER DEFAULT 1'),
                ('day_position_pct',        'REAL DEFAULT 5.0'),
                ('swing_position_pct',     'REAL DEFAULT 3.0'),
                ('day_trades_enabled',     'INTEGER DEFAULT 1'),
                ('swing_trades_enabled',   'INTEGER DEFAULT 1'),
                # Swing scanner filters
                ('swing_scan_source',      "TEXT DEFAULT 'both'"),
                ('swing_scan_top_n',       'INTEGER DEFAULT 30'),
                ('swing_min_price',        'REAL DEFAULT 5.0'),
                ('swing_max_price',        'REAL DEFAULT 500.0'),
                ('swing_min_avg_vol_k',    'REAL DEFAULT 500.0'),
                ('swing_min_market_cap_m', 'REAL DEFAULT 200.0'),
                ('swing_max_market_cap_m', 'REAL DEFAULT 0.0'),
                ('swing_max_float_m',      'REAL DEFAULT 0.0'),
                # Swing entry signals
                ('swing_check_above_sma20','INTEGER DEFAULT 0'),
                ('swing_check_ma_cross',   'INTEGER DEFAULT 0'),
                ('swing_check_rsi_range',  'INTEGER DEFAULT 0'),
                ('swing_rsi_min',          'REAL DEFAULT 40.0'),
                ('swing_rsi_max',          'REAL DEFAULT 70.0'),
                ('swing_check_rel_vol',         'INTEGER DEFAULT 0'),
                ('swing_rel_vol_min',           'REAL DEFAULT 1.2'),
                # Swing trailing stop
                ('swing_trailing_stop_enabled', 'INTEGER DEFAULT 0'),
                ('swing_trailing_stop_pct',     'REAL DEFAULT 5.0'),
                # Swing entry time gate
                ('swing_time_gate_enabled',     'INTEGER DEFAULT 0'),
                ('swing_time_gate_start',       "TEXT DEFAULT '09:30'"),
                ('swing_time_gate_end',         "TEXT DEFAULT '15:00'"),
            ]:
                try:
                    cursor.execute(f'ALTER TABLE brown_bot_config ADD COLUMN {col} {defn}')
                except sqlite3.OperationalError:
                    pass  # column already exists

            # swing_daily_picks: persisted AI-ranked swing picks keyed by trading date
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS swing_daily_picks (
                    date TEXT PRIMARY KEY,
                    picks_json TEXT NOT NULL,
                    market_note TEXT DEFAULT '',
                    candidates_scanned INTEGER DEFAULT 0,
                    source_counts_json TEXT DEFAULT '{}',
                    sources_tickers_json TEXT DEFAULT '{}',
                    created_at TEXT
                )
            ''')

            # swing_screener_history: one row per (date, ticker) from BrownBot swing scans.
            # Powers Option-B swing backtest — forward returns calculated at query time.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS swing_screener_history (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    date         TEXT    NOT NULL,
                    screened_at  TEXT,
                    ticker       TEXT    NOT NULL,
                    price        REAL,
                    chg_pct      REAL,
                    volume_m     REAL,
                    avg_vol_k    REAL,
                    market_cap_m REAL,
                    float_m      REAL,
                    sector       TEXT,
                    rsi14        REAL,
                    sma9         REAL,
                    sma20        REAL,
                    above_sma20  INTEGER,
                    rel_vol      REAL,
                    ai_grade     TEXT,
                    ai_bias      TEXT,
                    ai_summary   TEXT,
                    was_entered  INTEGER DEFAULT 0,
                    entry_price  REAL,
                    UNIQUE(date, ticker)
                )
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_ssh_date ON swing_screener_history(date)')

            # brown_positions: additive P&L tracking columns
            for col, defn in [
                ('status',             "TEXT DEFAULT 'open'"),
                ('trade_date',         'TEXT'),
                ('entry_order_id',     'TEXT'),
                ('avg_entry_price',    'REAL'),
                ('current_price',      'REAL'),
                ('unrealized_pnl',     'REAL DEFAULT 0'),
                ('unrealized_pnl_pct', 'REAL DEFAULT 0'),
                ('realized_pnl',       'REAL DEFAULT 0'),
                ('realized_pnl_pct',   'REAL DEFAULT 0'),
                ('exit_order_id',      'TEXT'),
                ('exit_price',         'REAL'),
                ('exit_reason',        'TEXT'),
                ('exit_time',          'TEXT'),
            ]:
                try:
                    cursor.execute(f'ALTER TABLE brown_positions ADD COLUMN {col} {defn}')
                except sqlite3.OperationalError:
                    pass  # column already exists

            # swing_daily_bars: daily OHLCV cache used by the swing backtest to compute
            # forward returns without hitting Alpaca on every backtest run.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS swing_daily_bars (
                    ticker TEXT    NOT NULL,
                    date   TEXT    NOT NULL,
                    open   REAL,
                    high   REAL,
                    low    REAL,
                    close  REAL,
                    volume INTEGER,
                    PRIMARY KEY (ticker, date)
                )
            ''')

            # brown_positions: active BrownBot positions persisted across server restarts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS brown_positions (
                    position_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    position_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    profit_target REAL,
                    profit_target_pct REAL,
                    stop_loss REAL,
                    stop_loss_pct REAL,
                    entry_time TEXT NOT NULL,
                    entry_time_epoch REAL,
                    data_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # brown_orders: immutable per-order log (one row per BUY or SELL order placed by BrownBot)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS brown_orders (
                    order_id      TEXT PRIMARY KEY,
                    position_id   TEXT,
                    symbol        TEXT NOT NULL,
                    side          TEXT NOT NULL,
                    order_type    TEXT NOT NULL,
                    position_type TEXT,
                    submitted_qty INTEGER,
                    submitted_price REAL,
                    filled_qty    INTEGER,
                    filled_price  REAL,
                    status        TEXT DEFAULT 'pending',
                    exit_reason   TEXT,
                    submitted_at  TEXT,
                    filled_at     TEXT,
                    trade_date    TEXT,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_brown_orders_position_id ON brown_orders(position_id)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_brown_orders_trade_date ON brown_orders(trade_date)')

            # Upgrade trades.trade_id to UNIQUE — deduplicate first, then swap index.
            try:
                # Remove duplicate rows, keeping the one with the lowest id per trade_id.
                cursor.execute('''
                    DELETE FROM trades WHERE id NOT IN (
                        SELECT MIN(id) FROM trades GROUP BY trade_id
                    )
                ''')
                cursor.execute('DROP INDEX IF EXISTS idx_trades_trade_id')
                cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id)')
            except Exception:
                pass  # If it already exists as unique, or any other issue, leave as-is

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
        import uuid as _uuid
        unsubscribe_token = str(_uuid.uuid4())

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, system_role, subscription_tier,
                                       subscription_status, is_active, preferences,
                                       first_name, last_name, address, profession, annual_income_range,
                                       trial_expires_at, email_digest_unsubscribe_token)
                    VALUES (?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (username, email, password_hash, system_role, subscription_tier, json.dumps(preferences),
                      first_name, last_name, address, profession, annual_income_range, trial_expires_at,
                      unsubscribe_token))
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

    def update_session_expiry(self, session_token, expires_at):
        """Extend an existing session's expiry time."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE sessions SET expires_at = ? WHERE session_token = ?',
                    (expires_at.isoformat(), session_token)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Database error updating session expiry: {e}")
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
            _db_logger.error(f"Database error getting user by email: {e}", exc_info=True)
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
            _db_logger.error(f"Error setting reset token for user {user_id}: {e}", exc_info=True)
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
            _db_logger.error(f"Error looking up reset token: {e}", exc_info=True)
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
            _db_logger.error(f"Error clearing reset token for user {user_id}: {e}", exc_info=True)

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

    def delete_buy_trade_by_order_id(self, order_id: str) -> bool:
        """Delete an unmatched BUY trade record by its broker order_id.

        Used at startup when a stale position (in DB but not in broker) is discarded,
        so its phantom buy entry doesn't pollute the Positions tab FIFO matching.
        Only deletes side='B' rows to avoid accidentally removing sell records.
        """
        if not order_id:
            return False
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "DELETE FROM trades WHERE order_id = ? AND side = 'B'",
                    (str(order_id),)
                )
                conn.commit()
                return True
        except Exception as e:
            return False

    def add_trade(self, trade_data):
        """Add a new trade to the database"""
        qty = int(trade_data.get('quantity', 0))
        if qty <= 0 or qty > 1_000_000:
            return False, f"Rejected: quantity {qty} out of valid range (1–1,000,000)"
        price = float(trade_data.get('price', 0))
        if price <= 0 or price > 1_000_000:
            return False, f"Rejected: price {price} out of valid range"
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO trades (
                        trade_id, symbol, side, quantity, price, route,
                        trade_time, order_id, liquidity, ecn_fee, pnl, trade_date,
                        position_type, days_held, source, broker
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    trade_data.get('source', 'brownbot'),
                    trade_data.get('broker'),
                ))
                conn.commit()
                return True, "Trade added successfully"
        except Exception as e:
            return False, f"Database error adding trade: {str(e)}"
    
    def get_position_summary(self, symbol=None, type_filter=None):
        """Get position summary statistics (positions table dropped; returns empty defaults)."""
        return {
            'total_positions': 0,
            'active_positions': 0,
            'total_quantity': 0,
            'total_realized': 0.0,
            'total_unrealized': 0.0,
            'total_cost_basis': 0.0,
        }
    
    def get_trades(self, symbol=None, start_date=None, end_date=None, limit=100):
        """Get trades with optional filtering"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, trade_id, symbol, side, quantity, price, route,
                           trade_time, order_id, liquidity, ecn_fee, pnl,
                           trade_date, position_type, source, created_at
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
    
    def get_trades_for_feedback(self, lookback_days: int = 30) -> list:
        """Return completed trades (pnl != 0) for the past N days for feedback analysis."""
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=lookback_days)).isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT symbol, side, pnl, trade_time, trade_date,
                              position_type, source
                       FROM trades
                       WHERE trade_date >= ?
                         AND pnl != 0
                       ORDER BY trade_date ASC, trade_time ASC''',
                    (start,),
                )
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            print(f'Database error in get_trades_for_feedback: {e}')
            return []

    def get_trade_summary(self, symbol=None, start_date=None, end_date=None):
        """Get trade summary statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT
                        COALESCE(SUM(CASE WHEN side IN ('S', 'SS') THEN 1 ELSE 0 END), 0) as total_trades,
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
        """Get closed-trade PnL history for charting, sourced from the trades table."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT id, symbol, side, quantity,
                           price     AS avg_cost,
                           price     AS init_price,
                           quantity  AS init_quantity,
                           pnl       AS realized,
                           trade_time AS create_time,
                           trade_date AS date,
                           0.0       AS unrealized,
                           updated_at AS last_updated,
                           created_at
                    FROM trades
                    WHERE pnl != 0
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
                query += ' ORDER BY trade_date DESC, updated_at DESC LIMIT ?'
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                positions = []
                for row in rows:
                    position = dict(row)
                    for field in ('created_at', 'last_updated'):
                        v = position.get(field)
                        if v and hasattr(v, 'isoformat'):
                            position[field] = v.isoformat()
                        elif v and not isinstance(v, str):
                            position[field] = str(v)
                    positions.append(position)
                return positions
        except Exception as e:
            _db_logger.error(f"Database error getting positions PnL history: {e}")
            return []

    def get_positions_pnl_summary(self, symbol=None, start_date=None, end_date=None):
        """Get closed-trade PnL summary statistics, sourced from the trades table."""
        _empty = {
            'total_positions': 0, 'profitable_positions': 0, 'losing_positions': 0,
            'total_pnl': 0, 'total_profits': 0, 'total_losses': 0, 'win_rate': 0,
        }
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        COUNT(*) as total_positions,
                        COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as profitable_positions,
                        COALESCE(SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END), 0) as losing_positions,
                        COALESCE(SUM(pnl), 0) as total_pnl,
                        COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0) as total_profits,
                        COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0) as total_losses
                    FROM trades
                    WHERE side IN ('S', 'SS')
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
                if not row:
                    return _empty
                summary = dict(row)
                total = summary['total_positions'] or 0
                summary['win_rate'] = round(
                    (summary['profitable_positions'] / total * 100) if total else 0, 2
                )
                for k in ('total_positions', 'profitable_positions', 'losing_positions',
                          'total_pnl', 'total_profits', 'total_losses'):
                    summary[k] = summary[k] or 0
                return summary
        except Exception as e:
            _db_logger.error(f"Database error getting positions PnL summary: {e}")
            return _empty

    def get_total_positions_count(self, symbol=None, start_date=None, end_date=None):
        """Count closed positions (exit trades) from the trades table."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) as total FROM trades WHERE side IN ('S', 'SS') AND source = 'brownbot'"
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
                return row['total'] if row else 0
        except Exception as e:
            print(f"Database error getting total positions count: {e}")
            return 0

    def get_total_positions_pnl(self, symbol=None, start_date=None, end_date=None):
        """Sum realized P&L from closed BrownBot trades."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COALESCE(SUM(pnl), 0) as total_pnl FROM trades WHERE side IN ('S', 'SS') AND source = 'brownbot'"
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
                return float(row['total_pnl']) if row else 0.0
        except Exception as e:
            print(f"Database error getting total positions P&L: {e}")
            return 0.0

    def get_positions_winrate(self, symbol=None, start_date=None, end_date=None):
        """Win rate from closed BrownBot exit trades."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as wins,
                        COALESCE(SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END), 0) as losses
                    FROM trades
                    WHERE side IN ('S', 'SS') AND source = 'brownbot'
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
                    wins = row['wins'] or 0
                    total = wins + (row['losses'] or 0)
                    return round((wins / total) * 100, 2) if total > 0 else 0.0
                return 0.0
        except Exception as e:
            print(f"Database error getting positions win rate: {e}")
            return 0.0

    def get_daily_pnl_data(self, start_date=None, end_date=None):
        """Daily P&L grouped by trade_date from closed BrownBot exit trades."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        trade_date as date,
                        COALESCE(SUM(pnl), 0) as daily_pnl,
                        COUNT(*) as positions_count
                    FROM trades
                    WHERE side IN ('S', 'SS') AND source = 'brownbot'
                '''
                params = []
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                query += ' GROUP BY trade_date ORDER BY trade_date ASC'
                cursor.execute(query, params)
                return [
                    {'date': row['date'], 'daily_pnl': float(row['daily_pnl']), 'positions_count': row['positions_count']}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            print(f"Database error getting daily P&L data: {e}")
            return []

    def get_cumulative_pnl_data(self, start_date=None, end_date=None):
        """Cumulative P&L running total from closed BrownBot exit trades."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        trade_date as date,
                        COALESCE(SUM(pnl), 0) as daily_pnl
                    FROM trades
                    WHERE side IN ('S', 'SS') AND source = 'brownbot'
                '''
                params = []
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                query += ' GROUP BY trade_date ORDER BY trade_date ASC'
                cursor.execute(query, params)
                rows = cursor.fetchall()
                running = 0.0
                result = []
                for row in rows:
                    daily = float(row['daily_pnl'])
                    running += daily
                    result.append({'date': row['date'], 'daily_pnl': daily, 'cumulative_pnl': running})
                return result
        except Exception as e:
            print(f"Database error getting cumulative P&L data: {e}")
            return []

    def get_closed_positions(self, symbol=None, start_date=None, end_date=None, limit=1000, position_type=None):
        """
        Return closed BrownBot positions for the Positions tab.
        Each row is an exit trade joined with its matching entry trade to get entry_price.
        Shape matches what the Positions tab HTML expects.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        x.id,
                        x.symbol,
                        x.side,
                        x.quantity,
                        x.price          AS exit_price,
                        x.pnl            AS realized,
                        x.trade_date,
                        x.trade_time,
                        x.position_type,
                        e.price          AS entry_price,
                        e.trade_time     AS entry_time
                    FROM trades x
                    LEFT JOIN trades e
                        ON  e.symbol     = x.symbol
                        AND e.side       = 'B'
                        AND e.source     = 'brownbot'
                        AND e.trade_date = x.trade_date
                    WHERE x.side IN ('S', 'SS')
                      AND x.source = 'brownbot'
                '''
                params = []
                if symbol:
                    query += ' AND x.symbol = ?'
                    params.append(symbol.upper())
                if start_date:
                    query += ' AND x.trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    query += ' AND x.trade_date <= ?'
                    params.append(end_date)
                if position_type:
                    query += ' AND x.position_type = ?'
                    params.append(position_type.lower())
                query += ' ORDER BY x.trade_date DESC, x.trade_time DESC LIMIT ?'
                params.append(limit)
                cursor.execute(query, params)
                rows = cursor.fetchall()

                positions = []
                for row in rows:
                    entry_px = row['entry_price']
                    exit_px  = float(row['exit_price'])
                    qty      = row['quantity']
                    pnl      = float(row['realized'])
                    # Fall back to computing entry price from PnL if no matching entry row
                    if entry_px is None:
                        entry_px = exit_px - (pnl / qty) if qty else exit_px
                    else:
                        entry_px = float(entry_px)
                    positions.append({
                        'id':            row['id'],
                        'symbol':        row['symbol'],
                        'type':          1,   # BrownBot is long-only today
                        'quantity':      qty,
                        'avg_cost':      round(entry_px, 4),
                        'init_quantity': qty,
                        'init_price':    round(entry_px, 4),
                        'exit_price':    round(exit_px, 4),
                        'realized':      round(pnl, 2),
                        'unrealized':    0.0,
                        'create_time':   row['entry_time'] or row['trade_time'],
                        'date':          row['trade_date'],
                        'position_type': row['position_type'] or 'day',
                    })
                return positions
        except Exception as e:
            print(f"Database error getting closed positions: {e}")
            return []

    def get_consolidated_positions(self, symbol=None, start_date=None, end_date=None,
                                    position_type=None, source=None, limit=1000):
        """
        Consolidated closed positions — one row per round-trip per symbol per session.

        Algorithm:
          1. Fetch all BUY and SELL trades sorted chronologically.
          2. FIFO-match buys to sells per (symbol, position_type).
             Handles multiple buys before one sell (weighted avg entry).
          3. Consolidate multiple sells on the same (symbol, exit_date, position_type)
             into a single row (user may exit in batches).
          4. Apply start_date filter at result level so FIFO has full buy history.
        """
        from collections import defaultdict, deque
        from datetime import date as _date

        with self.get_connection() as conn:
            query = '''
                SELECT symbol, side, quantity, price, pnl, trade_date, trade_time,
                       COALESCE(position_type, 'day') AS position_type,
                       COALESCE(source, 'brownbot')   AS source,
                       COALESCE(days_held, 0)          AS days_held,
                       broker,
                       order_id
                FROM trades
                WHERE side IN ('B', 'S', 'SS')
            '''
            params = []
            if symbol:
                query += ' AND symbol = ?';        params.append(symbol.upper())
            if source:
                query += ' AND source = ?';        params.append(source)
            if position_type:
                query += ' AND position_type = ?'; params.append(position_type.lower())
            if end_date:
                # Include all buys up to end_date so FIFO matching is complete
                query += ' AND trade_date <= ?';   params.append(end_date)
            query += ' ORDER BY symbol, position_type, trade_date, trade_time'
            rows = conn.execute(query, params).fetchall()

        buy_queues = defaultdict(deque)
        raw_results = []

        for row in rows:
            sym  = row['symbol']
            pt   = row['position_type']
            key  = (sym, pt)
            side = (row['side'] or '').upper()

            raw_qty   = int(row['quantity'])
            raw_price = float(row['price'])
            # Skip obviously corrupt records (data sanity guard)
            if raw_qty <= 0 or raw_qty > 1_000_000 or raw_price <= 0 or raw_price > 1_000_000:
                continue

            if side == 'B':
                buy_queues[key].append({
                    'qty':   raw_qty,
                    'price': raw_price,
                    'date':  row['trade_date'],
                })
            elif side in ('S', 'SS'):
                sell_qty   = raw_qty
                sell_price = raw_price
                pnl        = float(row['pnl'] or 0)
                exit_date  = row['trade_date']
                exit_time  = row['trade_time'] or ''
                src        = row['source']
                broker     = row['broker']
                order_id   = row['order_id'] or ''

                # Consume buys FIFO to compute weighted avg entry
                remaining    = sell_qty
                matched_buys = []
                queue        = buy_queues[key]

                while remaining > 0 and queue:
                    b    = queue[0]
                    take = min(b['qty'], remaining)
                    matched_buys.append({'qty': take, 'price': b['price'], 'date': b['date']})
                    remaining -= take
                    if take == b['qty']:
                        queue.popleft()
                    else:
                        queue[0] = {**b, 'qty': b['qty'] - take}

                if matched_buys:
                    total_cost = sum(b['qty'] * b['price'] for b in matched_buys)
                    total_qty  = sum(b['qty'] for b in matched_buys)
                    avg_entry  = total_cost / total_qty if total_qty else None
                    entry_date = min(b['date'] for b in matched_buys)
                else:
                    # No buy found — back-calculate from stored P&L
                    avg_entry  = sell_price - (pnl / sell_qty) if sell_qty else None
                    entry_date = exit_date

                try:
                    duration_days = (
                        _date.fromisoformat(exit_date) - _date.fromisoformat(entry_date)
                    ).days
                except Exception:
                    duration_days = int(row['days_held'] or 0)

                raw_results.append({
                    'symbol':        sym,
                    'position_type': pt,
                    'source':        src,
                    'broker':        broker,
                    'qty':           sell_qty,
                    'avg_entry':     round(avg_entry, 4) if avg_entry is not None else None,
                    'avg_exit':      round(sell_price, 4),
                    'pnl':           round(pnl, 2),
                    'entry_date':    entry_date,
                    'exit_date':     exit_date,
                    'exit_time':     exit_time,
                    'duration_days': duration_days,
                    '_order_id':     order_id,  # used for consolidation key, not exposed to frontend
                })

        # Consolidate partial fills: multiple SELL records for the same exit order
        # (same order_id) are merged into one row. Separate exits for the same symbol
        # on the same day (different order_ids) stay as distinct rows — each BrownBot
        # round-trip must appear separately in the positions list.
        from collections import OrderedDict
        consolidated = OrderedDict()
        for r in raw_results:
            oid = r.get('_order_id') or ''
            # If we have a broker order_id, use it to distinguish exits precisely.
            # Fall back to exit_time (second granularity) so that two exits within the
            # same second (near-impossible) still consolidate, while different-minute
            # exits for the same symbol on the same day remain separate rows.
            exit_discriminator = oid if oid else r['exit_time'][11:19]  # HH:MM:SS (ISO: YYYY-MM-DDTHH:MM:SS)
            ck = (r['symbol'], r['exit_date'], r['position_type'], exit_discriminator)
            if ck not in consolidated:
                consolidated[ck] = dict(r)
            else:
                ex      = consolidated[ck]
                old_qty = ex['qty']
                add_qty = r['qty']
                total   = old_qty + add_qty
                if ex['avg_entry'] and r['avg_entry']:
                    ex['avg_entry'] = round(
                        (ex['avg_entry'] * old_qty + r['avg_entry'] * add_qty) / total, 4
                    )
                ex['avg_exit'] = round(
                    (ex['avg_exit'] * old_qty + r['avg_exit'] * add_qty) / total, 4
                )
                ex['qty']           += add_qty
                ex['pnl']            = round(ex['pnl'] + r['pnl'], 2)
                ex['entry_date']     = min(ex['entry_date'], r['entry_date'])
                ex['duration_days']  = max(ex['duration_days'], r['duration_days'])

        results = list(consolidated.values())

        # Strip internal bookkeeping field before returning
        for r in results:
            r.pop('_order_id', None)

        # Apply start_date on exit_date (couldn't do it in SQL or FIFO would miss earlier buys)
        if start_date:
            results = [r for r in results if r['exit_date'] >= start_date]

        results.sort(key=lambda r: (r['exit_date'], r['exit_time']), reverse=True)
        return results[:limit]

    def get_long_short_pnl_data(self, start_date=None, end_date=None):
        """P&L breakdown by Day vs Swing (BrownBot is long-only so Long/Short is meaningless)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        COALESCE(position_type, 'day') AS position_type,
                        COALESCE(SUM(pnl), 0)          AS total_pnl,
                        COUNT(*)                        AS position_count
                    FROM trades
                    WHERE side IN ('S', 'SS')
                      AND source = 'brownbot'
                      AND pnl != 0
                '''
                params = []
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                query += ' GROUP BY position_type ORDER BY total_pnl DESC'
                cursor.execute(query, params)
                return [{'position_type': r['position_type'], 'total_pnl': float(r['total_pnl']),
                         'position_count': r['position_count']} for r in cursor.fetchall()]
        except Exception as e:
            print(f"Database error getting day/swing P&L data: {e}")
            return []

    def get_symbol_pnl_data(self, start_date=None, end_date=None, limit=10):
        """P&L breakdown by symbol for pie chart."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        symbol,
                        COALESCE(SUM(pnl), 0) AS total_pnl,
                        COUNT(*)               AS position_count,
                        AVG(pnl)               AS avg_pnl
                    FROM trades
                    WHERE side IN ('S', 'SS')
                      AND source = 'brownbot'
                      AND pnl != 0
                '''
                params = []
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                query += ' GROUP BY symbol ORDER BY total_pnl DESC LIMIT ?'
                params.append(limit)
                cursor.execute(query, params)
                return [{'symbol': r['symbol'], 'total_pnl': float(r['total_pnl']),
                         'position_count': r['position_count'], 'avg_pnl': float(r['avg_pnl'])}
                        for r in cursor.fetchall()]
        except Exception as e:
            print(f"Database error getting symbol P&L data: {e}")
            return []

    def get_win_loss_pnl_data(self, start_date=None, end_date=None):
        """P&L breakdown by winning vs losing trades for pie chart."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        CASE
                            WHEN pnl > 0 THEN 'Winning'
                            WHEN pnl < 0 THEN 'Losing'
                            ELSE 'Break Even'
                        END                    AS trade_result,
                        COALESCE(SUM(pnl), 0)  AS total_pnl,
                        COUNT(*)               AS position_count
                    FROM trades
                    WHERE side IN ('S', 'SS')
                      AND source = 'brownbot'
                '''
                params = []
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                query += ' GROUP BY trade_result ORDER BY total_pnl DESC'
                cursor.execute(query, params)
                return [{'trade_result': r['trade_result'], 'total_pnl': float(r['total_pnl']),
                         'position_count': r['position_count']} for r in cursor.fetchall()]
        except Exception as e:
            print(f"Database error getting win/loss P&L data: {e}")
            return []

    def get_monthly_pnl_data(self, start_date=None, end_date=None):
        """P&L breakdown by month for pie chart."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        strftime('%Y-%m', trade_date) AS month,
                        COALESCE(SUM(pnl), 0)         AS total_pnl,
                        COUNT(*)                      AS position_count
                    FROM trades
                    WHERE side IN ('S', 'SS')
                      AND source = 'brownbot'
                      AND pnl != 0
                '''
                params = []
                if start_date:
                    query += ' AND trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    query += ' AND trade_date <= ?'
                    params.append(end_date)
                query += ' GROUP BY month ORDER BY month ASC'
                cursor.execute(query, params)
                return [{'month': r['month'], 'total_pnl': float(r['total_pnl']),
                         'position_count': r['position_count']} for r in cursor.fetchall()]
        except Exception as e:
            print(f"Database error getting monthly P&L data: {e}")
            return []

    def get_extended_stats(self, start_date=None, end_date=None):
        """Extended trading metrics: profit factor, expectancy, streaks, etc."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                base_filter = "side IN ('S','SS') AND source='brownbot'"
                params = []
                date_clause = ''
                if start_date:
                    date_clause += ' AND trade_date >= ?'
                    params.append(start_date)
                if end_date:
                    date_clause += ' AND trade_date <= ?'
                    params.append(end_date)

                cursor.execute(f'''
                    SELECT
                        COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl  ELSE 0   END), 0) AS gross_profit,
                        COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl  ELSE 0   END), 0) AS gross_loss,
                        COALESCE(AVG(CASE WHEN pnl > 0 THEN pnl  ELSE NULL END), 0) AS avg_win,
                        COALESCE(AVG(CASE WHEN pnl < 0 THEN pnl  ELSE NULL END), 0) AS avg_loss,
                        COALESCE(MAX(pnl), 0) AS best_trade,
                        COALESCE(MIN(pnl), 0) AS worst_trade,
                        COALESCE(AVG(pnl),   0) AS avg_pnl,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS win_count,
                        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS loss_count,
                        SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END) AS breakeven_count,
                        COUNT(*) AS total_count
                    FROM trades WHERE {base_filter}{date_clause}
                ''', params)
                row = cursor.fetchone()

                if not row or (row['total_count'] or 0) == 0:
                    return self._empty_extended_stats()

                gross_profit   = float(row['gross_profit'])
                gross_loss_raw = float(row['gross_loss'])   # negative
                gross_loss     = abs(gross_loss_raw)
                avg_win        = float(row['avg_win'])
                avg_loss       = float(row['avg_loss'])     # negative
                best_trade     = float(row['best_trade'])
                worst_trade    = float(row['worst_trade'])
                avg_pnl        = float(row['avg_pnl'])
                win_count      = row['win_count'] or 0
                loss_count     = row['loss_count'] or 0
                total_count    = row['total_count'] or 0

                profit_factor  = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0
                win_rate       = win_count / total_count if total_count else 0
                loss_rate      = loss_count / total_count if total_count else 0
                expectancy     = round((win_rate * avg_win) + (loss_rate * avg_loss), 2)
                win_loss_ratio = round(avg_win / abs(avg_loss), 2) if avg_loss < 0 else 0.0

                # Best/worst trade symbols
                def _sym(pnl_val):
                    q = f"SELECT symbol FROM trades WHERE {base_filter} AND pnl=?{date_clause} ORDER BY submitted_at DESC LIMIT 1"
                    cursor.execute(q, [pnl_val] + params)
                    r = cursor.fetchone()
                    return r['symbol'] if r else ''

                # Consecutive wins/losses — sorted by time
                cursor.execute(
                    f"SELECT pnl FROM trades WHERE {base_filter}{date_clause} ORDER BY submitted_at ASC",
                    params
                )
                pnl_seq = [float(r['pnl']) for r in cursor.fetchall()]
                max_cw = max_cl = cur_w = cur_l = 0
                for p in pnl_seq:
                    if p > 0:
                        cur_w += 1; cur_l = 0
                        max_cw = max(max_cw, cur_w)
                    elif p < 0:
                        cur_l += 1; cur_w = 0
                        max_cl = max(max_cl, cur_l)
                    else:
                        cur_w = cur_l = 0

                return {
                    'gross_profit':          round(gross_profit, 2),
                    'gross_loss':            round(gross_loss, 2),
                    'profit_factor':         profit_factor,
                    'avg_win':               round(avg_win, 2),
                    'avg_loss':              round(avg_loss, 2),
                    'win_loss_ratio':        win_loss_ratio,
                    'best_trade':            round(best_trade, 2),
                    'best_trade_symbol':     _sym(best_trade),
                    'worst_trade':           round(worst_trade, 2),
                    'worst_trade_symbol':    _sym(worst_trade),
                    'avg_pnl':               round(avg_pnl, 2),
                    'win_count':             win_count,
                    'loss_count':            loss_count,
                    'breakeven_count':       row['breakeven_count'] or 0,
                    'total_count':           total_count,
                    'expectancy':            expectancy,
                    'max_consecutive_wins':  max_cw,
                    'max_consecutive_losses': max_cl,
                }
        except Exception as e:
            print(f"Database error getting extended stats: {e}")
            return self._empty_extended_stats()

    def _empty_extended_stats(self):
        return {
            'gross_profit': 0.0, 'gross_loss': 0.0, 'profit_factor': 0.0,
            'avg_win': 0.0, 'avg_loss': 0.0, 'win_loss_ratio': 0.0,
            'best_trade': 0.0, 'best_trade_symbol': '', 'worst_trade': 0.0,
            'worst_trade_symbol': '', 'avg_pnl': 0.0, 'win_count': 0,
            'loss_count': 0, 'breakeven_count': 0, 'total_count': 0,
            'expectancy': 0.0, 'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
        }

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
            'day_time_gate_enabled': True, 'day_time_gate_start': '09:35', 'day_time_gate_end': '10:30',
            'swing_profit_target_pct': 15.0, 'swing_stop_loss_pct': 7.0,
            'swing_max_hold_days': 20, 'swing_earnings_protection_enabled': True,
            'swing_earnings_exit_days': 2, 'swing_breakeven_trigger_pct': 50.0,
            'max_daily_loss': -500.0, 'max_concurrent_day': 3, 'max_concurrent_swing': 5,
            'min_gap_pct': 10.0, 'min_price': 5.0, 'max_price': 500.0, 'min_volume_m': 0.5,
            'max_float_m': 0.0, 'float_operator': '<=',
            'day_check_vwap': False, 'day_check_candle': False,
            'day_max_extension_pct': 0.0, 'day_check_volume_surge': False, 'day_ai_playbook': True,
            'day_position_pct': 5.0, 'swing_position_pct': 3.0,
            'day_trades_enabled': True, 'swing_trades_enabled': True,
            # Swing scanner filters
            'swing_scan_source': 'both', 'swing_scan_top_n': 30,
            'swing_min_price': 5.0, 'swing_max_price': 500.0,
            'swing_min_avg_vol_k': 500.0,
            'swing_min_market_cap_m': 200.0, 'swing_max_market_cap_m': 0.0,
            'swing_max_float_m': 0.0,
            # Swing entry signals
            'swing_check_above_sma20': False, 'swing_check_ma_cross': False,
            'swing_check_rsi_range': False, 'swing_rsi_min': 40.0, 'swing_rsi_max': 70.0,
            'swing_check_rel_vol': False, 'swing_rel_vol_min': 1.2,
            # Swing trailing stop
            'swing_trailing_stop_enabled': False, 'swing_trailing_stop_pct': 5.0,
            # Swing entry time gate
            'swing_time_gate_enabled': False, 'swing_time_gate_start': '09:30', 'swing_time_gate_end': '15:00',
        }
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM brown_bot_config WHERE user_id=? LIMIT 1', (user_id,))
                row = cursor.fetchone()
                if row:
                    cfg = dict(row)
                    # Fall back to defaults for any NULL or empty-string values so
                    # float() conversions downstream never receive '' or None.
                    for k, v in defaults.items():
                        if cfg.get(k) is None or cfg.get(k) == '':
                            cfg[k] = v
                    cfg['day_trailing_stop_enabled'] = bool(cfg.get('day_trailing_stop_enabled', 0))
                    cfg['swing_earnings_protection_enabled'] = bool(cfg.get('swing_earnings_protection_enabled', 1))
                    cfg['day_time_gate_enabled'] = bool(cfg.get('day_time_gate_enabled', 1))
                    cfg['day_check_vwap'] = bool(cfg.get('day_check_vwap', 0))
                    cfg['day_check_candle'] = bool(cfg.get('day_check_candle', 0))
                    cfg['day_check_volume_surge'] = bool(cfg.get('day_check_volume_surge', 0))
                    cfg['day_ai_playbook']        = bool(cfg.get('day_ai_playbook', 1))
                    cfg['day_trades_enabled']       = bool(cfg.get('day_trades_enabled', 1))
                    cfg['swing_trades_enabled']     = bool(cfg.get('swing_trades_enabled', 1))
                    cfg['swing_check_above_sma20']      = bool(cfg.get('swing_check_above_sma20', 0))
                    cfg['swing_check_ma_cross']         = bool(cfg.get('swing_check_ma_cross', 0))
                    cfg['swing_check_rsi_range']        = bool(cfg.get('swing_check_rsi_range', 0))
                    cfg['swing_check_rel_vol']          = bool(cfg.get('swing_check_rel_vol', 0))
                    cfg['swing_trailing_stop_enabled']  = bool(cfg.get('swing_trailing_stop_enabled', 0))
                    cfg['swing_time_gate_enabled']      = bool(cfg.get('swing_time_gate_enabled', 0))
                    return cfg
        except Exception as e:
            print(f"Database error fetching brown_bot_config: {e}")
        return defaults

    def update_brown_bot_config(self, config: dict, user_id: int = 1) -> tuple:
        fields = [
            'day_profit_target_pct', 'day_stop_loss_pct', 'day_trailing_stop_enabled',
            'day_trailing_stop_pct', 'day_eod_exit_time', 'day_breakeven_trigger_pct',
            'day_time_gate_enabled', 'day_time_gate_start', 'day_time_gate_end',
            'swing_profit_target_pct', 'swing_stop_loss_pct', 'swing_max_hold_days',
            'swing_earnings_protection_enabled', 'swing_earnings_exit_days',
            'swing_breakeven_trigger_pct', 'max_daily_loss', 'max_concurrent_day',
            'max_concurrent_swing', 'min_gap_pct', 'min_price', 'max_price', 'min_volume_m',
            'max_float_m', 'float_operator',
            'day_check_vwap', 'day_check_candle', 'day_max_extension_pct', 'day_check_volume_surge', 'day_ai_playbook',
            'day_position_pct', 'swing_position_pct',
            'day_trades_enabled', 'swing_trades_enabled',
            'swing_scan_source', 'swing_scan_top_n',
            'swing_min_price', 'swing_max_price', 'swing_min_avg_vol_k',
            'swing_min_market_cap_m', 'swing_max_market_cap_m', 'swing_max_float_m',
            'swing_check_above_sma20', 'swing_check_ma_cross',
            'swing_check_rsi_range', 'swing_rsi_min', 'swing_rsi_max',
            'swing_check_rel_vol', 'swing_rel_vol_min',
            'swing_trailing_stop_enabled', 'swing_trailing_stop_pct',
            'swing_time_gate_enabled', 'swing_time_gate_start', 'swing_time_gate_end',
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

    # ── Daily digest ──────────────────────────────────────────────────────────

    def get_digest_recipients(self) -> list:
        """Return active users who have opted in to the daily digest email."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, first_name, last_name,
                           subscription_status, trial_expires_at,
                           email_digest_enabled, email_digest_unsubscribe_token
                    FROM users
                    WHERE is_active = 1
                      AND email_digest_enabled = 1
                      AND email IS NOT NULL
                      AND subscription_status IN ('active', 'trialing')
                    ORDER BY id ASC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Database error getting digest recipients: {e}")
            return []

    def set_email_digest_enabled(self, token: str, enabled: bool) -> bool:
        """Enable or disable digest for the user who owns this unsubscribe token."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET email_digest_enabled = ? WHERE email_digest_unsubscribe_token = ?',
                    (1 if enabled else 0, token)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Database error updating digest preference: {e}")
            return False

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
    # Swing daily picks persistence
    # ------------------------------------------------------------------

    def save_swing_picks(self, date: str, picks: list, market_note: str = '',
                         candidates_scanned: int = 0, source_counts: dict = None,
                         sources_tickers: dict = None) -> bool:
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO swing_daily_picks
                       (date, picks_json, market_note, candidates_scanned,
                        source_counts_json, sources_tickers_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (date, json.dumps(picks), market_note or '', candidates_scanned,
                     json.dumps(source_counts or {}), json.dumps(sources_tickers or {}),
                     datetime.now().isoformat())
                )
                conn.commit()
                return True
        except Exception as e:
            _db_logger.error(f'Database error saving swing_daily_picks: {e}', exc_info=True)
            return False

    def get_swing_picks(self, date: str = None) -> dict | None:
        """Return picks for *date*, or the most recent row if date is None.
        When date is None, prefers the most recent row that has actual picks;
        falls back to any row so the caller can distinguish "no rows" from
        "rows with empty picks"."""
        try:
            with self.get_connection() as conn:
                if date:
                    row = conn.execute(
                        'SELECT * FROM swing_daily_picks WHERE date = ?', (date,)
                    ).fetchone()
                else:
                    # Prefer latest row with non-empty picks
                    row = conn.execute(
                        "SELECT * FROM swing_daily_picks WHERE picks_json != '[]'"
                        " AND picks_json IS NOT NULL ORDER BY date DESC LIMIT 1"
                    ).fetchone()
                    if not row:
                        row = conn.execute(
                            'SELECT * FROM swing_daily_picks ORDER BY date DESC LIMIT 1'
                        ).fetchone()
                if not row:
                    return None
                return {
                    'date':               row['date'],
                    'picks':              json.loads(row['picks_json'] or '[]'),
                    'market_note':        row['market_note'] or '',
                    'candidates_scanned': row['candidates_scanned'] or 0,
                    'source_counts':      json.loads(row['source_counts_json'] or '{}'),
                    'sources_tickers':    json.loads(row['sources_tickers_json'] or '{}'),
                    'created_at':         row['created_at'],
                }
        except Exception as e:
            _db_logger.error(f'Database error fetching swing_daily_picks date={date}: {e}', exc_info=True)
            return None

    def get_swing_picks_range(self, start_date: str, end_date: str) -> list:
        """Return all swing_daily_picks rows between start_date and end_date (inclusive).
        Each item: {'date': str, 'picks': list[dict]}."""
        try:
            with self.get_connection() as conn:
                rows = conn.execute(
                    "SELECT date, picks_json FROM swing_daily_picks "
                    "WHERE date BETWEEN ? AND ? ORDER BY date",
                    (start_date, end_date)
                ).fetchall()
                return [
                    {'date': r['date'], 'picks': json.loads(r['picks_json'] or '[]')}
                    for r in rows
                ]
        except Exception as e:
            _db_logger.error(f'get_swing_picks_range error: {e}')
            return []

    # ------------------------------------------------------------------
    # Swing screener history (Option-B backtest data collection)
    # ------------------------------------------------------------------

    def save_swing_screener_snapshot(self, date: str, candidates: list, picks: list,
                                     screened_at: str = None) -> int:
        """
        Upsert one row per candidate into swing_screener_history for *date*.
        picks is the AI-ranked list from SwingPicksAgent; merged by ticker.
        Returns number of rows inserted/replaced.
        """
        if not candidates:
            return 0
        from datetime import datetime as _dt
        screened_at = screened_at or _dt.utcnow().isoformat()
        grades = {p['ticker']: p for p in (picks or [])}
        rows = []
        for c in candidates:
            t = c.get('ticker') or c.get('symbol', '')
            if not t:
                continue
            p = grades.get(t, {})
            sma20 = c.get('sma20')
            price = c.get('price') or 0
            rows.append((
                date, screened_at, t.upper(),
                price,
                c.get('chg_pct'),
                c.get('volume_m'),
                c.get('avg_vol_k'),
                c.get('market_cap_m'),
                c.get('float_m'),
                c.get('sector'),
                c.get('rsi'),
                c.get('sma9'),
                sma20,
                1 if (sma20 and price and price > sma20) else 0,
                c.get('rel_vol'),
                p.get('grade'),
                p.get('bias'),
                p.get('reason') or p.get('summary', ''),
            ))
        if not rows:
            return 0
        try:
            with self.get_connection() as conn:
                # Insert first-time rows; ignore duplicates to preserve was_entered flag.
                conn.executemany('''
                    INSERT OR IGNORE INTO swing_screener_history
                    (date, screened_at, ticker, price, chg_pct, volume_m, avg_vol_k,
                     market_cap_m, float_m, sector, rsi14, sma9, sma20, above_sma20,
                     rel_vol, ai_grade, ai_bias, ai_summary)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', rows)
                # Update AI grade/bias on existing rows when they were previously NULL
                # (first scan may save before AI ranking completes).
                conn.executemany('''
                    UPDATE swing_screener_history
                    SET ai_grade=?, ai_bias=?, ai_summary=?
                    WHERE date=? AND ticker=? AND ai_grade IS NULL
                ''', [
                    (r[15], r[16], r[17], r[0], r[2])
                    for r in rows if r[15] is not None
                ])
                conn.commit()
            return len(rows)
        except Exception as e:
            _db_logger.error(f'save_swing_screener_snapshot error: {e}')
            return 0

    def mark_swing_screener_entered(self, date: str, ticker: str,
                                    entry_price: float) -> None:
        """Mark a screener-history row as actually entered by BrownBot."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''UPDATE swing_screener_history
                       SET was_entered=1, entry_price=?
                       WHERE date=? AND ticker=?''',
                    (entry_price, date, ticker.upper()),
                )
                conn.commit()
        except Exception as e:
            _db_logger.warning(f'mark_swing_screener_entered error: {e}')

    def get_swing_screener_history(self, start_date: str, end_date: str) -> list:
        """Return all screener-history rows between start_date and end_date (inclusive)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM swing_screener_history
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date, ticker
                ''', (start_date, end_date))
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            _db_logger.error(f'get_swing_screener_history error: {e}')
            return []

    def cache_swing_daily_bars(self, ticker: str, bars: list) -> None:
        """Upsert daily OHLCV bars into swing_daily_bars cache."""
        if not bars:
            return
        try:
            with self.get_connection() as conn:
                conn.executemany('''
                    INSERT OR IGNORE INTO swing_daily_bars
                    (ticker, date, open, high, low, close, volume)
                    VALUES (?,?,?,?,?,?,?)
                ''', [
                    (ticker.upper(), b['date'], b.get('open'), b.get('high'),
                     b.get('low'), b.get('close'), b.get('volume'))
                    for b in bars
                ])
                conn.commit()
        except Exception as e:
            _db_logger.warning(f'cache_swing_daily_bars error: {e}')

    def get_swing_daily_bars(self, ticker: str, start_date: str,
                             end_date: str) -> list:
        """Return cached daily bars for ticker between start and end dates."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT date, open, high, low, close, volume
                    FROM swing_daily_bars
                    WHERE ticker=? AND date BETWEEN ? AND ?
                    ORDER BY date
                ''', (ticker.upper(), start_date, end_date))
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            _db_logger.warning(f'get_swing_daily_bars error: {e}')
            return []

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

                # Saving a broker config always makes it the sole active broker
                if is_active:
                    cursor.execute(
                        'UPDATE broker_configs SET is_active=0 WHERE user_id=? AND broker_name!=?',
                        (user_id, broker_name)
                    )

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

    def activate_broker(self, broker_name: str, user_id: int = 1) -> tuple:
        """Set broker_name as the only active broker for user_id (no credential change)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id FROM broker_configs WHERE user_id=? AND broker_name=?',
                    (user_id, broker_name)
                )
                if not cursor.fetchone():
                    return False, f'No saved config for {broker_name}'
                cursor.execute(
                    'UPDATE broker_configs SET is_active=0 WHERE user_id=?',
                    (user_id,)
                )
                cursor.execute(
                    'UPDATE broker_configs SET is_active=1, updated_at=CURRENT_TIMESTAMP '
                    'WHERE user_id=? AND broker_name=?',
                    (user_id, broker_name)
                )
                conn.commit()
                return True, f'{broker_name} is now the active broker'
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # BrownBot active position persistence
    # ------------------------------------------------------------------

    def save_brown_position(self, position_id: str, position: dict) -> bool:
        """Upsert a BrownBot active position so it survives server restarts."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO brown_positions
                       (position_id, symbol, position_type, entry_price, quantity,
                        profit_target, profit_target_pct, stop_loss, stop_loss_pct,
                        entry_time, entry_time_epoch, data_json,
                        status, trade_date, entry_order_id, avg_entry_price,
                        current_price, unrealized_pnl, unrealized_pnl_pct)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (position_id,
                     position.get('symbol'),
                     position.get('position_type', 'day'),
                     float(position.get('entry_price', 0)),
                     int(position.get('quantity', 0)),
                     position.get('profit_target'),
                     position.get('profit_target_pct'),
                     position.get('stop_loss'),
                     position.get('stop_loss_pct'),
                     position.get('entry_time'),
                     position.get('entry_time_epoch'),
                     json.dumps({k: v for k, v in position.items()
                                 if k not in ('unrealized_pnl', 'realized_pnl')}),
                     position.get('status', 'open'),
                     position.get('trade_date'),
                     position.get('entry_order_id'),
                     position.get('avg_entry_price') or position.get('entry_price'),
                     position.get('_current_price'),
                     float(position.get('unrealized_pnl', 0) or 0),
                     float(position.get('unrealized_pnl_pct', 0) or 0))
                )
                conn.commit()
                return True
        except Exception as e:
            print(f'Database error saving brown_position: {e}')
            return False

    def delete_brown_position(self, position_id: str) -> bool:
        """Remove a BrownBot position record after it has been closed."""
        try:
            with self.get_connection() as conn:
                conn.execute('DELETE FROM brown_positions WHERE position_id = ?', (position_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f'Database error deleting brown_position: {e}')
            return False

    def get_brown_positions(self) -> list:
        """Return active BrownBot positions (status open or legacy NULL), ordered by entry time.

        DB columns for avg_entry_price and trade_date are overlaid on the data_json blob
        so that targeted UPDATE calls (update_brown_position_entry) survive a crash that
        occurs before the subsequent save_brown_position call refreshes data_json.
        """
        try:
            with self.get_connection() as conn:
                rows = conn.execute(
                    "SELECT data_json, avg_entry_price, trade_date, stop_loss, profit_target "
                    "FROM brown_positions "
                    "WHERE status IS NULL OR status = 'open' "
                    "ORDER BY entry_time_epoch ASC"
                ).fetchall()
                positions = []
                for row in rows:
                    try:
                        pos = json.loads(row['data_json'] or '{}')
                        if not pos:
                            continue
                        # Overlay DB columns so confirmed fill prices survive partial updates
                        if row['avg_entry_price'] is not None:
                            pos['avg_entry_price'] = row['avg_entry_price']
                        if row['trade_date'] is not None:
                            pos['trade_date'] = row['trade_date']
                        positions.append(pos)
                    except Exception:
                        pass
                return positions
        except Exception as e:
            print(f'Database error fetching brown_positions: {e}')
            return []

    def add_brown_order(self, order_data: dict) -> bool:
        """Insert a new BrownBot order record (immutable log entry)."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''INSERT OR IGNORE INTO brown_orders
                       (order_id, position_id, symbol, side, order_type, position_type,
                        submitted_qty, submitted_price, status, exit_reason,
                        submitted_at, trade_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (str(order_data.get('order_id', '')),
                     order_data.get('position_id'),
                     order_data.get('symbol'),
                     order_data.get('side'),
                     order_data.get('order_type'),
                     order_data.get('position_type'),
                     order_data.get('submitted_qty'),
                     order_data.get('submitted_price'),
                     order_data.get('status', 'pending'),
                     order_data.get('exit_reason'),
                     order_data.get('submitted_at'),
                     order_data.get('trade_date'))
                )
                conn.commit()
                return True
        except Exception as e:
            print(f'Database error adding brown_order: {e}')
            return False

    def update_brown_order_fill(self, order_id: str, fill_price: float, fill_qty: int,
                                status: str = 'filled', filled_at: str = None) -> bool:
        """Update a BrownBot order with actual broker fill data."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''UPDATE brown_orders
                       SET filled_price = ?, filled_qty = ?, status = ?, filled_at = ?
                       WHERE order_id = ?''',
                    (fill_price, fill_qty, status,
                     filled_at or datetime.now().isoformat(), str(order_id))
                )
                conn.commit()
                return True
        except Exception as e:
            print(f'Database error updating brown_order fill: {e}')
            return False

    def update_brown_position_entry(self, position_id: str, avg_entry_price: float,
                                    quantity: int) -> bool:
        """Update position with confirmed fill price after broker confirms entry."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''UPDATE brown_positions
                       SET avg_entry_price = ?, quantity = ?
                       WHERE position_id = ?''',
                    (avg_entry_price, quantity, position_id)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f'Database error updating brown_position entry: {e}')
            return False

    def update_brown_position_unrealized(self, position_id: str, current_price: float,
                                         unrealized_pnl: float,
                                         unrealized_pnl_pct: float) -> bool:
        """Persist the latest unrealized P&L for an active position."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''UPDATE brown_positions
                       SET current_price = ?, unrealized_pnl = ?, unrealized_pnl_pct = ?
                       WHERE position_id = ? AND (status IS NULL OR status = 'open')''',
                    (current_price, unrealized_pnl, unrealized_pnl_pct, position_id)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f'Database error updating brown_position unrealized: {e}')
            return False

    def close_brown_position(self, position_id: str, exit_price: float,
                             exit_order_id: str, exit_reason: str,
                             realized_pnl: float, realized_pnl_pct: float,
                             exit_time: str = None) -> bool:
        """Mark a BrownBot position as closed and record realized P&L."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    '''UPDATE brown_positions
                       SET status = 'closed', exit_price = ?, exit_order_id = ?,
                           exit_reason = ?, realized_pnl = ?, realized_pnl_pct = ?,
                           exit_time = ?, unrealized_pnl = 0, unrealized_pnl_pct = 0
                       WHERE position_id = ?''',
                    (exit_price,
                     str(exit_order_id) if exit_order_id else None,
                     exit_reason, realized_pnl, realized_pnl_pct,
                     exit_time or datetime.now().isoformat(), position_id)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f'Database error closing brown_position: {e}')
            return False

    def get_brown_positions_pnl_by_ticker(self, trade_date: str = None) -> list:
        """Return per-ticker realized and unrealized P&L from brown_positions."""
        try:
            with self.get_connection() as conn:
                params = (trade_date,) if trade_date else ()
                where  = 'WHERE trade_date = ?' if trade_date else ''
                rows = conn.execute(
                    f'''SELECT symbol,
                               ROUND(SUM(realized_pnl), 2)                                      AS realized_pnl,
                               ROUND(SUM(CASE WHEN status IS NULL OR status = 'open'
                                              THEN unrealized_pnl ELSE 0 END), 2)               AS unrealized_pnl,
                               COUNT(*)                                                          AS trades
                        FROM brown_positions
                        {where}
                        GROUP BY symbol
                        ORDER BY SUM(realized_pnl) DESC''',
                    params
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f'Database error fetching brown_positions_pnl_by_ticker: {e}')
            return []

    def get_brown_daily_realized_pnl(self, trade_date: str = None) -> float:
        """Return total realized P&L for closed BrownBot positions on a given trading date."""
        try:
            with self.get_connection() as conn:
                params = (trade_date,) if trade_date else ()
                where  = "AND trade_date = ?" if trade_date else ''
                row = conn.execute(
                    f"SELECT COALESCE(SUM(realized_pnl), 0) AS total "
                    f"FROM brown_positions WHERE status = 'closed' {where}",
                    params
                ).fetchone()
                return float(row['total']) if row else 0.0
        except Exception as e:
            print(f'Database error fetching brown_daily_realized_pnl: {e}')
            return 0.0


# Global database manager instance
db_manager = DatabaseManager()