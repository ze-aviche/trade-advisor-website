#!/usr/bin/env python3
"""
Gap-Up Detection Web API
Flask backend for the gap-up detection dashboard
"""
import os
import sys
import json
import random
import socket
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, time as time_class
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from logging_config import (setup_logging, get_logger, log_api_request, log_performance, log_error,
                            set_debug_user, is_debug_user, get_debug_users)

# Load environment variables
load_dotenv()

# Error monitoring — must be initialised before Flask app is created
_sentry_dsn = os.environ.get('SENTRY_DSN')
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# Setup comprehensive logging
setup_logging(log_level='INFO', log_dir='logs')
app_logger = get_logger('app')

# Apply emoji filter to prevent Unicode errors on Windows console
from logging_config import apply_emoji_filter
apply_emoji_filter()

# Import real gap-up detection functions
try:
    from gap_up_detector import get_gap_up_stocks_for_frontend
    from historical_data import get_historical_gap_up_data
    REAL_DATA_AVAILABLE = True
except ImportError as e:
    app_logger.warning(f"Warning: Could not import gap_up_detector: {e}")
    REAL_DATA_AVAILABLE = False

from database import db_manager

# Import auth functions (these should always be available)
try:
    from auth import auth_manager, require_auth, require_role
except ImportError as e:
    app_logger.warning(f"Warning: Could not import auth: {e}")
    auth_manager = None
    require_auth = lambda f: f
    def require_role(*roles):
        return lambda f: f

# Import scheduled DAS sync
try:
    from scheduled_das_sync import start_scheduled_sync, stop_scheduled_sync, get_sync_status, manual_sync
    SCHEDULED_SYNC_AVAILABLE = True
except ImportError as e:
    pass  # app_logger.warning(f"Warning: Could not import scheduled_das_sync: {e}")
    SCHEDULED_SYNC_AVAILABLE = False

# Import trading bot
try:
    from bot.trading_bot import trading_bot
    BOT_AVAILABLE = True
except ImportError as e:
    app_logger.warning(f"Warning: Could not import trading bot: {e}")
    BOT_AVAILABLE = False

# Import BrownBot risk manager
try:
    from bot.risk_manager import RiskManager
    RISK_MANAGER_AVAILABLE = True
except ImportError as e:
    app_logger.warning(f"Warning: Could not import RiskManager: {e}")
    RISK_MANAGER_AVAILABLE = False

# Import Stripe manager
try:
    from stripe_manager import StripeManager
    stripe_mgr = StripeManager()
    STRIPE_AVAILABLE = True
except Exception as e:
    app_logger.warning(f"Warning: Stripe not available: {e}")
    stripe_mgr = None
    STRIPE_AVAILABLE = False

# Import Claude AI Agent (chat interface)
try:
    from ai_agent import ClaudeAIAgent, GapUpTradeAgent, SwingPicksAgent
    _ai_agent    = ClaudeAIAgent()
    _gap_up_agent = GapUpTradeAgent()
    _swing_agent  = SwingPicksAgent()
    AI_AGENT_AVAILABLE = True
except Exception as e:
    app_logger.warning(f"Warning: Could not initialize Claude AI Agent: {e}")
    _ai_agent     = None
    _gap_up_agent = None
    _swing_agent  = None
    AI_AGENT_AVAILABLE = False

# Feature flag: controls DAS Trader integration.
# Set DAS_ENABLED=true in .env (or environment) to enable for local/mock testing.
DAS_ENABLED = os.environ.get('DAS_ENABLED', 'false').lower() == 'true'
if not DAS_ENABLED:
    BOT_AVAILABLE = False
    SCHEDULED_SYNC_AVAILABLE = False

# app_logger.info(f"[STARTUP] DAS_ENABLED={DAS_ENABLED}  BOT_AVAILABLE={BOT_AVAILABLE}  SCHEDULED_SYNC={SCHEDULED_SYNC_AVAILABLE}")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gap-up-detection-web-2024')

_cors_origins_raw = os.environ.get('CORS_ORIGINS', '*').strip()
_cors_origins = '*' if _cors_origins_raw == '*' else [o.strip() for o in _cors_origins_raw.split(',')]
CORS(app, origins=_cors_origins)
# eventlet doesn't support Python 3.13 — fall back to threading for local dev
_async_mode = 'eventlet'
try:
    import eventlet  # noqa: F401
    eventlet.green.thread.start_joinable_thread  # probe the broken attribute
except (ImportError, AttributeError):
    _async_mode = 'threading'
socketio = SocketIO(app, cors_allowed_origins=_cors_origins, async_mode=_async_mode)

# Set user context on every request so log lines carry user_id even on public routes.
# Protected routes also call auth._tag_request_context() which overwrites with verified data.
@app.before_request
def _set_request_context():
    g._req_start = time.time()
    g.current_user_id = '-'
    try:
        token = (request.headers.get('Authorization', '').replace('Bearer ', '')
                 or request.cookies.get('session_token', ''))
        if token and auth_manager:
            user = auth_manager.get_user_by_session(token)
            if user:
                uid = user.get('id')
                g.current_user_id = uid
                if _sentry_dsn:
                    import sentry_sdk as _sdk
                    _sdk.set_user({'id': str(uid), 'username': user.get('username'),
                                   'email': user.get('email')})
    except Exception:
        pass


@app.after_request
def _log_api_request(response):
    """Log every API call with username, method, path, status, and duration."""
    if not request.path.startswith('/api/'):
        return response

    ms = int((time.time() - getattr(g, '_req_start', time.time())) * 1000)

    user = getattr(request, 'user', None)
    if user:
        who = user.get('username') or user.get('email') or f"uid:{user.get('id', '?')}"
    else:
        # Not a protected endpoint — try session token lookup for context
        token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.cookies.get('session_token')
        if token and auth_manager:
            u = auth_manager.get_user_by_session(token)
            who = (u.get('username') or u.get('email')) if u else 'anonymous'
        else:
            who = 'anonymous'

    msg = f"[{who}] {request.method} {request.path} → {response.status_code} ({ms}ms)"

    _POLLING_PATHS = {
        '/api/brown-bot/status', '/api/brown-bot/logs', '/api/brown-bot/risk-status',
        '/api/bot/status', '/api/entry-bot/status', '/api/session/ping',
        '/api/health',
    }

    if response.status_code >= 500:
        app_logger.error(msg)
    elif response.status_code >= 400:
        app_logger.warning(msg)
    elif request.path in _POLLING_PATHS:
        app_logger.debug(msg)
    else:
        app_logger.info(msg)

    return response


@app.errorhandler(Exception)
def _handle_unhandled_exception(exc):
    """Catch any exception not handled by a route and log it with user context."""
    import traceback as _tb
    uid       = getattr(g, 'current_user_id', None)
    endpoint  = request.endpoint or request.path
    tb_str    = _tb.format_exc()
    app_logger.error(
        f"Unhandled exception in {request.method} {request.path}: "
        f"{type(exc).__name__}: {exc}",
        exc_info=True,
    )
    # Persist to DB so admins can query per-user errors
    try:
        payload = None
        if request.is_json:
            payload = request.get_data(as_text=True)[:2000]
        db_manager.add_error_log(
            user_id         = uid,
            endpoint        = endpoint,
            method          = request.method,
            error_type      = type(exc).__name__,
            error_message   = str(exc)[:500],
            traceback_str   = tb_str[:4000],
            request_payload = payload,
            ip_address      = request.remote_addr,
        )
    except Exception:
        pass
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


# Global variables for real-time data
active_stocks = set()
price_cache = {}
websocket_connected = False
real_time_gap_ups = []  # Store real-time detected gap-ups

# Historical prefetch daemon state
_hist_prefetch_status = {}   # {ticker: {'date': str, 'records': int, 'fetched_at': str}}
_hist_prefetch_lock = threading.Lock()

# Entry Bot global variables and data structures
entry_bot_running = False
entry_bot_stats = {
    'positions_entered': 0,
    'active_positions_count': 0
}
tracking_symbols = {}  # Store tracking data for each symbol
entry_bot_logs = []  # Store debug logs for Entry Bot
_entry_bot_log_id = 0  # Monotonic counter for unique log entry IDs
tracking_thread = None  # Background thread for continuous tracking
tracking_active = False  # Flag to control tracking thread
active_positions = {}  # Store active positions entered by the bot

# Broker abstraction layer — active broker instance cache (lazy-loaded per user)
# Key: user_id (int), Value: BrokerBase instance (already connected)
_broker_cache: dict = {}
_broker_cache_lock = threading.Lock()


def _get_broker(user_id: int = 1):
    """
    Return the active BrokerBase instance for *user_id*, lazy-loading from DB.
    Returns None if no broker is configured or connection fails.
    Falls back to the legacy DAS path when DAS_ENABLED and no broker configured.
    """
    with _broker_cache_lock:
        if user_id in _broker_cache:
            broker = _broker_cache[user_id]
            if broker.is_connected():
                return broker
            # Stale — remove and re-connect below
            del _broker_cache[user_id]

    try:
        configs = db_manager.get_broker_configs(user_id)
        active = next((c for c in configs if c.get('is_active')), None)
        if not active:
            return None
        broker_name = active['broker_name']
        row = db_manager.get_broker_config(broker_name, user_id)
        if not row:
            return None

        from bot.broker import create_broker
        cfg = {
            'api_key':    row.get('api_key', ''),
            'api_secret': row.get('api_secret', ''),
            'account_id': row.get('account_id', ''),
            'paper':      bool(row.get('paper_trading', 1)),
            **row.get('extra_config', {}),
        }
        broker = create_broker(broker_name, cfg)
        if broker.connect():
            with _broker_cache_lock:
                _broker_cache[user_id] = broker
            app_logger.info(f'[Broker] Connected: {broker.name} (user {user_id})')
            return broker
        app_logger.warning(f'[Broker] Connection failed for {broker_name} (user {user_id})')
    except Exception as e:
        app_logger.warning(f'[Broker] _get_broker error: {e}')
    return None


def _invalidate_broker_cache(user_id: int = 1):
    """Call after saving new broker credentials so the next request re-connects."""
    with _broker_cache_lock:
        _broker_cache.pop(user_id, None)


# BrownBot per-user session state
# Each user who starts BrownBot gets an isolated BrownSession.
# Background threads receive user_id and look up _brown_sessions[user_id].
class BrownSession:
    """All runtime state for one user's BrownBot instance."""
    __slots__ = [
        'user_id', 'running', 'broker', 'risk_manager', 'lock',
        'active_positions', 'entry_counts', 'attempted_symbols',
        'eod_flattened_symbols', 'closing_positions', 'pending_orders',
        'logs', 'log_id', 'stats',
        'scanner_thread', 'exit_thread', 'order_monitor_thread',
        'swing_candidates_cache', 'swing_ai_picks_cache',
        'playbook_cache', 'playbook_pending', 'playbook_failed',
    ]

    def __init__(self, user_id: int):
        self.user_id            = user_id
        self.running            = False
        self.broker             = None
        self.risk_manager       = None
        self.lock               = threading.Lock()
        self.active_positions   = {}   # position_id -> position dict
        self.entry_counts: dict = {}   # symbol -> successful entries this session
        self.attempted_symbols: set = set()
        self.eod_flattened_symbols: set = set()
        self.closing_positions: set = set()
        self.pending_orders: dict = {}  # order_id -> metadata
        self.logs: list = []
        self.log_id: int = 0
        self.stats = {'day_entered': 0, 'swing_entered': 0, 'day_exited': 0, 'swing_exited': 0}
        self.scanner_thread      = None
        self.exit_thread         = None
        self.order_monitor_thread = None
        self.swing_candidates_cache = {'ts': 0.0, 'candidates': []}
        self.swing_ai_picks_cache   = {'ts': 0.0, 'picks': [], 'fingerprint': ''}
        self.playbook_cache:   dict = {}
        self.playbook_pending: set  = set()
        self.playbook_failed:  set  = set()


_brown_sessions: dict = {}           # user_id (int) -> BrownSession
_brown_sessions_lock = threading.Lock()  # guards _brown_sessions dict mutations only


def _get_brown_session(user_id: int):
    """Return the BrownSession for user_id, or None if not running."""
    return _brown_sessions.get(user_id)


class _DasDirectSocket:
    """Raw TCP connection to DAS / mock server.
    Used as a fallback when the CMDAPI library is unavailable (mock testing).
    Thread-safe; reconnects automatically on failure.
    """
    def __init__(self):
        self._sock = None
        self._lock = threading.Lock()
        self._host = os.environ.get('DAS_HOST', '127.0.0.1')
        self._port = int(os.environ.get('DAS_PORT', '9800'))

    def _connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((self._host, self._port))
        s.sendall(b'LOGIN IDAS12181\r\n')
        time.sleep(0.1)
        try:
            s.recv(4096)  # discard login banner
        except socket.timeout:
            pass
        self._sock = s

    def send_script(self, cmd: str) -> str:
        with self._lock:
            for attempt in range(2):
                try:
                    if self._sock is None:
                        self._connect()
                    self._sock.sendall(cmd.encode('ascii'))
                    time.sleep(0.15)
                    data = b''
                    self._sock.settimeout(0.5)
                    try:
                        while True:
                            chunk = self._sock.recv(4096)
                            if not chunk:
                                break
                            data += chunk
                    except socket.timeout:
                        pass
                    return data.decode('ascii', errors='replace')
                except Exception as e:
                    pass  # app_logger.warning(f"DAS direct socket error (attempt {attempt + 1}): {e}")
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    self._sock = None
            return ''


_das_direct = _DasDirectSocket()


def start_position_sync_scheduler():
    """Start automatic position sync every 10 seconds"""
    def sync_loop():
        while True:
            try:
                # Import here to avoid circular imports
                from das_integration import das_trade_manager
                success, message, updated_count = das_trade_manager.sync_positions_from_das()
                
                current_time = datetime.now().strftime('%H:%M:%S')
                if success:
                    app_logger.info(f"[{current_time}] ✅ Auto position sync: {message}")
                else:
                    app_logger.warning(f"[{current_time}] ⚠️ Auto position sync failed: {message}")
                    
            except Exception as e:
                app_logger.error(f"❌ Error in auto position sync: {e}")
            
            # Wait 10 seconds before next sync
            time.sleep(10)
    
    # Start the sync loop in a daemon thread
    sync_thread = threading.Thread(target=sync_loop, daemon=True)
    sync_thread.start()
    app_logger.info("✅ Automatic position sync started (every 10 seconds)")

# Entry Bot helper functions
def add_entry_bot_log(level, message):
    """Add a log entry to the Entry Bot logs"""
    global entry_bot_logs, _entry_bot_log_id
    import pytz as _tz
    _et_now = datetime.now(_tz.timezone('US/Eastern'))
    _entry_bot_log_id += 1
    log_entry = {
        'id': _entry_bot_log_id,
        'timestamp': _et_now.isoformat(),
        'level': level,
        'message': message
    }
    entry_bot_logs.append(log_entry)
    
    # Keep only the last 100 logs
    if len(entry_bot_logs) > 100:
        entry_bot_logs = entry_bot_logs[-100:]
    
    # Also log to the main application logger
    if level == 'error':
        app_logger.error(f"Entry Bot: {message}")
    elif level == 'warning':
        app_logger.warning(f"Entry Bot: {message}")
    else:
        app_logger.info(f"Entry Bot: {message}")


def _add_brown_log(level: str, message: str, user_id: int = 0):
    """Add a log entry to the requesting user's BrownBot session log."""
    import pytz as _tz
    _et_now = datetime.now(_tz.timezone('US/Eastern'))
    sess = _brown_sessions.get(user_id)
    if sess is not None:
        sess.log_id += 1
        sess.logs.append({
            'id': sess.log_id,
            'timestamp': _et_now.isoformat(),
            'level': level,
            'message': message,
        })
        if len(sess.logs) > 200:
            sess.logs = sess.logs[-200:]
    if level == 'error':
        app_logger.error(f"BrownBot[uid={user_id}]: {message}")
    elif level == 'warning':
        app_logger.warning(f"BrownBot[uid={user_id}]: {message}")
    else:
        app_logger.info(f"BrownBot[uid={user_id}]: {message}")


def _brown_debug(user_id: int, msg: str) -> None:
    """Emit a verbose detail line at INFO level only when admin has debug-mode enabled for
    this user. Use instead of app_logger.debug() in BrownBot daemon threads so the output
    appears in structured logs without flooding all users' logs."""
    if is_debug_user(user_id):
        app_logger.info(f"BrownBot[uid={user_id}][DBG] {msg}")


# Global DAS connection for reuse
_das_connection = None
_das_connection_lock = threading.Lock()

def get_das_connection():
    """Get or create a DAS connection (singleton pattern)"""
    global _das_connection

    if not DAS_ENABLED:
        return None

    with _das_connection_lock:
        if _das_connection is None:
            try:
                from cmdapi.CMDAPI_PYTHON import Connection
                _das_connection = Connection()
                _das_connection.ConnectToServer()
                pass  # app_logger.info("✅ DAS connection established")
            except Exception as e:
                pass  # app_logger.error(f"❌ Failed to establish DAS connection: {e}")
                _das_connection = None
                return None
        
        return _das_connection

def close_das_connection():
    """Close the global DAS connection"""
    global _das_connection
    
    with _das_connection_lock:
        if _das_connection is not None:
            try:
                _das_connection.Disconnect()
                pass  # app_logger.info("🛑 DAS connection closed")
            except Exception as e:
                pass  # app_logger.error(f"❌ Error closing DAS connection: {e}")
            finally:
                _das_connection = None

def _send_das_script(script: str) -> str:
    """Send a raw DAS script and return the response.

    Priority:
    1. trading_bot.connection — the exit bot's established, lock-protected socket.
       This is the preferred path: no extra connection needed, works with mock server.
    2. _das_direct — a separate persistent TCP socket to 127.0.0.1:9800.
       Fallback when the exit bot has not been started.

    The CMDAPI library is intentionally NOT used here. Its class-level shared socket
    is not thread-safe and conflicts with reconnection logic.
    """
    script_bytes = bytearray(script, encoding="ascii")

    # Path 1: reuse the exit bot's connection (thread-safe via its own lock)
    if BOT_AVAILABLE:
        try:
            conn = trading_bot.connection
            if conn is not None:
                result = conn.SendScript(script_bytes)
                if result:
                    return result
        except Exception as e:
            app_logger.warning(f"trading_bot socket error for script '{script.strip()}': {e}")

    # Path 2: dedicated direct TCP socket
    try:
        result = _das_direct.send_script(script)
        if result:
            return result
    except Exception as e:
        pass  # app_logger.error(f"_das_direct failed for script '{script.strip()}': {e}")

    return ""


def get_real_stock_data(symbol, user_id: int = 1):
    """
    Get real-time quote data for *symbol*.
    Tries the configured broker first; falls back to DAS Level 1 if DAS_ENABLED.
    Returns a dict compatible with the legacy DAS quote format, or None on failure.
    """
    sym = symbol.upper()

    # ── Path 1: cloud broker ─────────────────────────────────────────
    broker = _get_broker(user_id)
    if broker:
        try:
            q = broker.get_quote(sym)
            mid = (q.bid + q.ask) / 2 if q.bid and q.ask else (q.last or 0)
            dollar_vol = round(mid * q.volume / 1_000_000, 2) if q.volume else 0.0
            return {
                'symbol':         sym,
                'current_price':  round(q.last or mid, 2),
                'bid':            q.bid,
                'ask':            q.ask,
                'volume':         round(q.volume / 1_000_000, 2),   # millions
                'dollar_volume':  dollar_vol,
            }
        except Exception as e:
            pass  # app_logger.warning(f'[Broker] get_quote {sym} failed: {e}')

    # ── Path 2: legacy DAS Level 1 ───────────────────────────────────
    if not DAS_ENABLED:
        return None

    result = _send_das_script(f"SB {sym} Lv1\r\n")
    if result:
        quote_data = _parse_das_level1_response(result, sym)
        if quote_data:
            # app_logger.info(
            #     f"Level 1 {sym}: ${quote_data['current_price']} "
            #     f"Vol={quote_data['volume']}M DolVol=${quote_data['dollar_volume']}M"
            # )
            return quote_data

    # app_logger.warning(f"No quote data available for {sym}")
    return None

def _parse_das_level1_response(response: str, symbol: str):
    """Parse DAS Level 1 response to extract volume, price, and dollar volume"""
    try:
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            # Look for the $Quote line format: $Quote symbol A:askprice Asz:asksize B:bidprice Bsz:bidsize V:volume L:lastprice Hi:highprice Lo:lowprice op:openprice ycl:yesterdayclose tcl:todayclose PE:primExchange VWAP:vwapValue T:QuoteTime(HHMMSS)
            if line.startswith('$Quote') and symbol in line:
                parts = line.split()
                pass  # app_logger.debug(f"Parsing DAS Level 1 line: {line}")
                
                # Initialize variables
                current_price = None
                volume = None
                ask_price = None
                bid_price = None
                last_price = None
                
                for part in parts:
                    # Extract ask price (A:PRICE)
                    if part.startswith('A:') and len(part) > 2:
                        try:
                            ask_price = float(part[2:])
                        except ValueError:
                            continue
                    
                    # Extract bid price (B:PRICE)
                    elif part.startswith('B:') and len(part) > 2:
                        try:
                            bid_price = float(part[2:])
                        except ValueError:
                            continue
                    
                    # Extract last price (L:PRICE)
                    elif part.startswith('L:') and len(part) > 2:
                        try:
                            last_price = float(part[2:])
                        except ValueError:
                            continue
                    
                    # Extract volume (V:VOLUME)
                    elif part.startswith('V:') and len(part) > 2:
                        try:
                            volume = int(part[2:])
                        except ValueError:
                            continue
                
                # Determine current price (prefer last price, then ask, then bid)
                if last_price and last_price > 0:
                    current_price = last_price
                elif ask_price and ask_price > 0:
                    current_price = ask_price
                elif bid_price and bid_price > 0:
                    current_price = bid_price
                else:
                    pass  # app_logger.warning(f"No valid price found in DAS Level 1 data for {symbol}")
                    return None
                
                # Convert volume from shares to millions
                if volume and volume > 0:
                    volume_millions = volume / 1_000_000
                else:
                    pass  # app_logger.warning(f"No valid volume found in DAS Level 1 data for {symbol}")
                    return None
                
                # Calculate dollar volume (volume * current price)
                dollar_volume_millions = (volume * current_price) / 1_000_000
                
                return {
                    'symbol': symbol.upper(),
                    'current_price': round(current_price, 2),
                    'volume': round(volume_millions, 2),  # in millions
                    'dollar_volume': round(dollar_volume_millions, 2),  # in millions
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'DAS Level 1'
                }
        
        pass  # app_logger.warning(f"No valid Level 1 line found for {symbol} in response")
        return None
        
    except Exception as e:
        pass  # app_logger.error(f"Error parsing DAS Level 1 response for {symbol}: {e}")
        return None

def check_entry_conditions(symbol_data, entry_params):
    """Check if entry conditions are met for a symbol.
    Swing trades have no volume/time conditions — they enter immediately.
    """
    current_time_str = datetime.now().time().strftime('%H:%M:%S')

    # Swing trades: no volume or time gate — enter at current price right away
    if entry_params.get('position_type') == 'swing':
        return {
            'conditions_met': True,
            'volume_met': None,
            'dollar_volume_met': None,
            'time_met': None,
            'current_volume': symbol_data.get('volume'),
            'current_dollar_volume': symbol_data.get('dollar_volume'),
            'current_time': current_time_str,
            'entry_time': None,
        }

    try:
        current_volume = symbol_data['volume']
        current_dollar_volume = symbol_data['dollar_volume']
        current_time = datetime.now().time()

        # Parse entry time (assuming format like "10:00")
        entry_time_str = entry_params['entry_time']
        entry_hour, entry_minute = map(int, entry_time_str.split(':'))
        entry_time = time_class(entry_hour, entry_minute)

        # Check conditions
        volume_met = current_volume >= float(entry_params['total_volume'])
        dollar_volume_met = current_dollar_volume >= float(entry_params['dollar_volume'])
        time_met = current_time >= entry_time

        conditions_met = volume_met and dollar_volume_met and time_met

        return {
            'conditions_met': conditions_met,
            'volume_met': volume_met,
            'dollar_volume_met': dollar_volume_met,
            'time_met': time_met,
            'current_volume': current_volume,
            'current_dollar_volume': current_dollar_volume,
            'current_time': current_time.strftime('%H:%M:%S'),
            'entry_time': entry_time_str
        }
    except Exception as e:
        add_entry_bot_log('error', f"Error checking entry conditions for {symbol_data.get('symbol', 'Unknown')}: {e}")
        return {
            'conditions_met': False,
            'volume_met': False,
            'dollar_volume_met': False,
            'time_met': False,
            'error': str(e)
        }

def place_das_order(symbol, order_side, route, quantity, order_type, limit_price=None):
    """Place an order via DAS using _send_das_script (trading_bot socket → _das_direct)."""
    if not DAS_ENABLED:
        return False, None, "DAS integration is disabled"

    import uuid
    unID = int(uuid.uuid4()) % (2 ** 31)

    if order_type == 'MKT':
        script = f"NEWORDER {unID} {order_side} {symbol.upper()} {route} {quantity} MKT TIF=DAY\r\n"
    elif order_type == 'LIMIT':
        script = f"NEWORDER {unID} {order_side} {symbol.upper()} {route} {quantity} {limit_price} TIF=DAY\r\n"
    else:
        return False, None, f"Unsupported order type: {order_type}"

    # add_entry_bot_log('info', f"Sending DAS order: {script.strip()}")

    result = _send_das_script(script)
    # add_entry_bot_log('info', f"DAS order result: {result.strip() if result else '(no response)'}")

    if result and ("SUCCESS" in result.upper() or "ACCEPTED" in result.upper()):
        return True, unID, result

    add_entry_bot_log('error', f"Order rejected or no response: {result.strip() if result else '(no response)'}")
    return False, None, result or "No response from DAS"


def place_order(symbol: str, side: str, quantity: int,
                order_type: str = 'MKT', limit_price=None,
                user_id: int = 1) -> tuple:
    """
    Unified order placement — routes through the configured broker if available,
    falls back to the legacy DAS path if DAS_ENABLED and no broker is set.

    Returns (success: bool, order_id, message: str).
    `side` accepts 'B'/'BUY'/'buy' for buys, 'S'/'SELL'/'sell' for sells.
    """
    from bot.broker.base import OrderSide, OrderType as OType

    # Normalise side
    side_upper = side.upper()
    broker_side = OrderSide.BUY if side_upper in ('B', 'BUY') else OrderSide.SELL

    # Normalise order type
    otype_map = {'MKT': OType.MARKET, 'MARKET': OType.MARKET,
                 'LIMIT': OType.LIMIT, 'LMT': OType.LIMIT,
                 'STOP': OType.STOP, 'STPLMT': OType.STOP_LIMIT}
    broker_otype = otype_map.get(order_type.upper(), OType.MARKET)

    # ── Path 1: cloud broker ──────────────────────────────────────────
    broker = _get_broker(user_id)
    if broker:
        try:
            order = broker.place_order(
                symbol      = symbol,
                side        = broker_side,
                qty         = float(quantity),
                order_type  = broker_otype,
                limit_price = limit_price,
            )
            app_logger.info(
                f'[Broker:{broker.name}] {side_upper} {quantity} {symbol} '
                f'→ order_id={order.order_id} status={order.status}'
            )
            return True, order.order_id, str(order.status)
        except Exception as e:
            app_logger.error(f'[Broker] place_order failed: {e}')
            return False, None, str(e)

    # ── Path 2: legacy DAS fallback ───────────────────────────────────
    das_side = 'B' if broker_side == OrderSide.BUY else 'S'
    return place_das_order(symbol, das_side, 'SMAT', quantity, order_type, limit_price)


def enter_position(symbol, entry_price, entry_params):
    """Enter a position for a symbol at the given price."""
    global active_positions, entry_bot_stats

    try:
        # Extract order parameters from entry_params
        order_side  = entry_params.get('order_side', 'B')
        quantity    = entry_params.get('quantity', 100)
        order_type  = entry_params.get('order_type', 'MKT')
        limit_price = entry_params.get('limit_price')
        route       = entry_params.get('route', 'SMAT')

        # Route through broker abstraction layer (falls back to DAS if no broker configured)
        success, order_id, result = place_order(
            symbol, order_side, quantity, order_type, limit_price
        )

        if not success:
            add_entry_bot_log('error', f"❌ Failed to place order for {symbol}")
            return False, None
        
        # Generate a unique position ID
        position_id = f"ENTRY_{symbol}_{int(time.time())}"
        
        # Store the position details
        position = {
            'position_id': position_id,
            'order_id': order_id,
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': datetime.now().isoformat(),
            'quantity': quantity,
            'order_side': order_side,
            'order_type': order_type,
            'route': route,
            'limit_price': limit_price,
            'das_result': result,
            'entry_params': entry_params,
            'status': 'active'
        }
        
        # Store the position
        active_positions[position_id] = position
        
        # Update bot statistics
        entry_bot_stats['positions_entered'] += 1
        entry_bot_stats['active_positions_count'] = len(active_positions)
        
        add_entry_bot_log('info', f"✅ Position entered for {symbol} at ${entry_price} - Position ID: {position_id}, Order ID: {order_id}")
        
        return True, position_id
        
    except Exception as e:
        add_entry_bot_log('error', f"❌ Failed to enter position for {symbol}: {e}")
        return False, None

def continuous_tracking_loop():
    """Background thread function for continuous tracking every 1 second"""
    global tracking_active, tracking_symbols, active_positions
    
    while tracking_active:
        try:
            if tracking_symbols:
                # Log tracking activity
                symbols_list = list(tracking_symbols.keys())
                app_logger.info(f"🔄 Continuous tracking check for symbols: {', '.join(symbols_list)}")
                
                # Check each symbol's conditions (create a copy to avoid modification during iteration)
                symbols_to_check = list(tracking_symbols.items())
                for symbol, params in symbols_to_check:
                    try:
                        # Skip if we already have an active position for this symbol
                        if any(pos['symbol'] == symbol for pos in active_positions.values()):
                            continue
                        
                        # Get current market data
                        current_data = get_real_stock_data(symbol)
                        
                        # Skip if no data available
                        if current_data is None:
                            app_logger.warning(f"⏳ {symbol}: No market data available, skipping check")
                            continue
                        
                        # Check entry conditions
                        conditions = check_entry_conditions(current_data, params)
                        
                        # Log condition status
                        if conditions['conditions_met']:
                            app_logger.info(f"✅ {symbol}: All conditions met! Volume: {conditions['current_volume']}M >= {params['total_volume']}M, Dollar Vol: ${conditions['current_dollar_volume']}M >= ${params['dollar_volume']}M, Time: {conditions['current_time']} >= {conditions['entry_time']}")
                            
                            # Enter position at ask price (market order)
                            entry_price = current_data['current_price']
                            success, position_id = enter_position(symbol, entry_price, params)
                            
                            if success:
                                # Remove from tracking since position is entered
                                del tracking_symbols[symbol]
                                app_logger.info(f"🎯 Position entered for {symbol} - removed from tracking")
                            else:
                                app_logger.error(f"❌ Failed to enter position for {symbol}")
                        else:
                            app_logger.info(f"⏳ {symbol}: Conditions not met - Volume: {conditions['current_volume']}M/{params['total_volume']}M, Dollar Vol: ${conditions['current_dollar_volume']}M/${params['dollar_volume']}M, Time: {conditions['current_time']}/{conditions['entry_time']}")
                            
                    except Exception as e:
                        app_logger.error(f"❌ Error tracking {symbol}: {e}")
                
            # Wait 1 second before next check
            time.sleep(1)
            
        except Exception as e:
            app_logger.error(f"❌ Error in continuous tracking loop: {e}")
            time.sleep(1)  # Continue even if there's an error

def start_continuous_tracking():
    """Start the continuous tracking thread"""
    global tracking_thread, tracking_active
    
    if tracking_active:
        app_logger.warning("⚠️ Continuous tracking is already active")
        return
    
    tracking_active = True
    tracking_thread = threading.Thread(target=continuous_tracking_loop, daemon=True)
    tracking_thread.start()
    app_logger.info("🚀 Continuous tracking started (every 1 second)")

def stop_continuous_tracking():
    """Stop the continuous tracking thread"""
    global tracking_active, tracking_thread
    
    if not tracking_active:
        app_logger.warning("⚠️ Continuous tracking is not active")
        return
    
    tracking_active = False
    if tracking_thread and tracking_thread.is_alive():
        tracking_thread.join(timeout=2)  # Wait up to 2 seconds for thread to stop
    app_logger.info("🛑 Continuous tracking stopped")

# Frontend serving
@app.route('/')
def serve_landing():
    return send_from_directory(FRONTEND_DIR, 'landing.html')

@app.route('/app')
def serve_app():
    resp = send_from_directory(FRONTEND_DIR, 'index.html')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/login')
def serve_login():
    resp = send_from_directory(FRONTEND_DIR, 'login.html')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/unsubscribe/<token>')
def unsubscribe_digest(token):
    """One-click digest unsubscribe — no auth required, linked from email footer."""
    if not token:
        return 'Invalid link.', 400
    success = db_manager.set_email_digest_enabled(token, False)
    if success:
        body = (
            '<html><body style="font-family:Arial,sans-serif;text-align:center;padding:80px 20px;'
            'background:#0d1117;color:#e2e8f0;">'
            '<div style="max-width:420px;margin:0 auto;background:#161b22;border:1px solid #30363d;'
            'border-radius:12px;padding:40px;">'
            '<div style="font-size:22px;font-weight:800;color:#fff;margin-bottom:6px;">'
            'Accentor <span style="color:#93c5fd;">AI</span></div>'
            '<h2 style="color:#4ade80;margin:20px 0 10px;">Unsubscribed &#10003;</h2>'
            '<p style="color:#9ca3af;font-size:14px;line-height:1.7;">'
            "You've been removed from the daily digest. You can re-enable it in your Account Settings.</p>"
            '<a href="/app" style="display:inline-block;margin-top:20px;background:#2563eb;color:#fff;'
            'text-decoration:none;font-weight:700;font-size:13px;padding:10px 24px;border-radius:8px;">'
            '&#8592; Go to Accentor AI</a></div></body></html>'
        )
        return body, 200
    body = (
        '<html><body style="font-family:Arial,sans-serif;text-align:center;padding:80px 20px;'
        'background:#0d1117;color:#e2e8f0;">'
        '<div style="max-width:420px;margin:0 auto;background:#161b22;border:1px solid #30363d;'
        'border-radius:12px;padding:40px;">'
        '<div style="font-size:22px;font-weight:800;color:#fff;margin-bottom:6px;">'
        'Accentor <span style="color:#93c5fd;">AI</span></div>'
        '<h2 style="color:#f87171;margin:20px 0 10px;">Link not found</h2>'
        '<p style="color:#9ca3af;font-size:14px;">This unsubscribe link is invalid or has already been used.</p>'
        '<a href="/app" style="display:inline-block;margin-top:20px;background:#2563eb;color:#fff;'
        'text-decoration:none;font-weight:700;font-size:13px;padding:10px 24px;border-radius:8px;">'
        '&#8592; Go to Accentor AI</a></div></body></html>'
    )
    return body, 404


@app.route('/brownbot-logs')
@app.route('/brownbot-logs.html')
def serve_brownbot_logs():
    return send_from_directory(FRONTEND_DIR, 'brownbot-logs.html')


@app.route('/api/music/search')
def music_search():
    """Proxy Deezer search so the browser doesn't hit CORS. Returns 30-second preview tracks."""
    from auth import login_required as _lr
    # Only serve to authenticated sessions
    from flask import session as _sess
    if not _sess.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'tracks': []})
    try:
        import requests as _req
        resp = _req.get(
            'https://api.deezer.com/search',
            params={'q': q, 'limit': 8},
            timeout=5
        )
        resp.raise_for_status()
        raw = resp.json().get('data', [])
        tracks = [
            {
                'id':      t['id'],
                'title':   t['title'],
                'artist':  t['artist']['name'],
                'cover':   t['album'].get('cover_small', ''),
                'preview': t.get('preview', ''),
            }
            for t in raw
            if t.get('preview')  # skip tracks with no playable preview
        ]
        return jsonify({'tracks': tracks})
    except Exception as e:
        app_logger.error(f"Music search error: {e}")
        return jsonify({'tracks': [], 'error': str(e)}), 500


@app.route('/api/contact', methods=['POST'])
def contact():
    """Handle contact form submission and email it to the site owner"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        subject = (data.get('subject') or '').strip()
        message = (data.get('message') or '').strip()
        if not name or not email or not message:
            return jsonify({'success': False, 'error': 'Name, email, and message are required'}), 400

        app_logger.info(f"Contact form: from={email!r} name={name!r} subject={subject!r} message={message[:120]!r}")

        to_email = os.getenv('CONTACT_EMAIL_TO', 'mravinash1308@gmail.com')
        from_email = os.getenv('CONTACT_EMAIL_FROM', '')
        app_password = os.getenv('GMAIL_APP_PASSWORD', '')

        if from_email and app_password:
            try:
                mail_subject = f"[GapTradeBot Contact] {subject or 'New message'} — from {name}"
                body = (
                    f"You have a new contact form submission:\n\n"
                    f"Name:    {name}\n"
                    f"Email:   {email}\n"
                    f"Subject: {subject or '(none)'}\n\n"
                    f"Message:\n{message}\n"
                )
                msg = MIMEMultipart()
                msg['From'] = from_email
                msg['To'] = to_email
                msg['Reply-To'] = email
                msg['Subject'] = mail_subject
                msg.attach(MIMEText(body, 'plain'))

                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(from_email, app_password)
                    server.sendmail(from_email, to_email, msg.as_string())

                app_logger.info(f"Contact email sent to {to_email}")
            except Exception as mail_err:
                app_logger.error(f"Failed to send contact email: {mail_err}")
                # Still return success to the user; the submission was received
        else:
            app_logger.warning("Contact email not sent: GMAIL_APP_PASSWORD or CONTACT_EMAIL_FROM not configured")

        return jsonify({'success': True, 'message': 'Message received'})
    except Exception as e:
        app_logger.error(f"Contact form error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

# Auth endpoints
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        email      = (data.get('email') or '').strip()
        first_name = (data.get('first_name') or '').strip() or None

        success, message = auth_manager.register_user(
            data.get('username', ''),
            email,
            data.get('password', ''),
            first_name=first_name,
            last_name=(data.get('last_name') or '').strip() or None,
            address=(data.get('address') or '').strip() or None,
            profession=(data.get('profession') or '').strip() or None,
            annual_income_range=(data.get('annual_income_range') or '').strip() or None,
        )
        if success:
            _send_registration_welcome(email, first_name or data.get('username', ''))
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error registering user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _send_registration_welcome(to_email: str, first_name: str):
    """Send a welcome email to a newly registered user (fire-and-forget)."""
    from_email   = os.getenv('CONTACT_EMAIL_FROM', '')
    app_password = os.getenv('GMAIL_APP_PASSWORD', '')
    if not from_email or not app_password or not to_email:
        return
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Welcome to Accentor AI, {first_name} — Your 7-Day Trial Has Started'
        msg['From']    = from_email
        msg['To']      = to_email

        html_body = f"""
<html><body style="margin:0;padding:0;background:#0d1117;font-family:Arial,sans-serif;color:#e2e8f0;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:40px 0;">
  <tr><td align="center">
    <table width="620" cellpadding="0" cellspacing="0"
           style="background:#161b22;border:1px solid #30363d;border-radius:14px;overflow:hidden;max-width:620px;">

      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#1e3a8a 0%,#6d28d9 100%);padding:36px 44px;text-align:center;">
        <div style="font-size:30px;font-weight:800;color:#fff;letter-spacing:-0.5px;">
          Accentor <span style="color:#93c5fd;">AI</span>
        </div>
        <div style="color:#bfdbfe;font-size:13px;margin-top:6px;letter-spacing:0.04em;">
          INTELLIGENT TRADING PLATFORM
        </div>
      </td></tr>

      <!-- Welcome message -->
      <tr><td style="padding:36px 44px 0;">
        <h2 style="color:#fff;font-size:21px;margin:0 0 14px;font-weight:700;">
          Welcome aboard, {first_name}. Your free trial is active.
        </h2>
        <p style="color:#9ca3af;font-size:14px;line-height:1.75;margin:0 0 28px;">
          You now have <strong style="color:#fff;">full Yogi-tier access for 7 days</strong> — no credit card
          required. Explore every feature, run the bots live, and see exactly what Accentor AI can do
          for your trading edge before you decide to subscribe.
        </p>
      </td></tr>

      <!-- What you can do -->
      <tr><td style="padding:0 44px;">
        <div style="background:#1c2230;border:1px solid #30363d;border-radius:10px;padding:24px;">
          <div style="font-size:13px;font-weight:700;color:#60a5fa;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:16px;">What's included in your trial</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="padding:8px 0;border-bottom:1px solid #21262d;">
              <span style="color:#34d399;font-weight:700;">✓</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Daily Gap-Up Scanner</strong> — pre-market momentum movers with sector context
              </span>
            </td></tr>
            <tr><td style="padding:8px 0;border-bottom:1px solid #21262d;">
              <span style="color:#34d399;font-weight:700;">✓</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Swing Trading Tab</strong> — daily AI-ranked hot picks, full technicals (RSI, MACD, Bollinger Bands, ATR), and sector momentum
              </span>
            </td></tr>
            <tr><td style="padding:8px 0;border-bottom:1px solid #21262d;">
              <span style="color:#34d399;font-weight:700;">✓</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Automated Exit Bot</strong> — trailing stop, breakeven stop, and EOD force-exit, all configurable from the dashboard
              </span>
            </td></tr>
            <tr><td style="padding:8px 0;border-bottom:1px solid #21262d;">
              <span style="color:#34d399;font-weight:700;">✓</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Entry Bot</strong> — automated order entry rules wired directly to your DAS Trader account
              </span>
            </td></tr>
            <tr><td style="padding:8px 0;border-bottom:1px solid #21262d;">
              <span style="color:#34d399;font-weight:700;">✓</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Historical Analytics &amp; Backtesting</strong> — P&amp;L curves, win-rate breakdowns, and strategy backtests on real gap-up data
              </span>
            </td></tr>
            <tr><td style="padding:8px 0;">
              <span style="color:#34d399;font-weight:700;">✓</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">AI Chat Assistant</strong> — ask anything about the markets, your positions, or trading strategy
              </span>
            </td></tr>
          </table>
        </div>
      </td></tr>

      <!-- Alpaca setup guide -->
      <tr><td style="padding:28px 44px 0;">
        <div style="font-size:13px;font-weight:700;color:#34d399;text-transform:uppercase;
                    letter-spacing:0.08em;margin-bottom:16px;">🚀 Get started in 10 minutes — connect your broker</div>
        <div style="background:#0d1f17;border:1px solid #1a4731;border-radius:10px;padding:24px;">
          <p style="color:#9ca3af;font-size:13px;line-height:1.7;margin:0 0 20px;">
            BrownBot places live trades through <strong style="color:#fff;">Alpaca Markets</strong> — a free, commission-free broker
            with a paper trading environment. We strongly recommend starting with paper money to get comfortable
            before risking real capital.
          </p>

          <!-- Step 1 -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
            <tr>
              <td width="32" valign="top">
                <div style="background:#1d4ed8;color:#fff;font-size:11px;font-weight:800;width:24px;height:24px;
                            border-radius:50%;text-align:center;line-height:24px;">1</div>
              </td>
              <td style="padding-left:12px;">
                <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:3px;">Create a free Alpaca account</div>
                <div style="color:#9ca3af;font-size:12px;line-height:1.6;">
                  Go to <a href="https://alpaca.markets" style="color:#60a5fa;">alpaca.markets</a> and sign up — no minimums, no monthly fees.
                  Alpaca offers both a <strong style="color:#fde68a;">Paper Trading</strong> account (virtual money) and a
                  <strong style="color:#fca5a5;">Live</strong> account (real money). Start with paper.
                </div>
              </td>
            </tr>
          </table>

          <!-- Step 2 -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
            <tr>
              <td width="32" valign="top">
                <div style="background:#1d4ed8;color:#fff;font-size:11px;font-weight:800;width:24px;height:24px;
                            border-radius:50%;text-align:center;line-height:24px;">2</div>
              </td>
              <td style="padding-left:12px;">
                <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:3px;">Generate your API keys</div>
                <div style="color:#9ca3af;font-size:12px;line-height:1.6;">
                  In your Alpaca dashboard: <strong style="color:#d1d5db;">Paper Trading → API Keys → Generate new key.</strong>
                  Copy the <strong style="color:#d1d5db;">Key ID</strong> (starts with
                  <span style="font-family:monospace;background:#111827;color:#fde68a;padding:1px 5px;border-radius:3px;">PK</span>)
                  and the <strong style="color:#d1d5db;">Secret Key</strong> — the secret is shown only once.
                </div>
              </td>
            </tr>
          </table>

          <!-- Step 3 -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
            <tr>
              <td width="32" valign="top">
                <div style="background:#1d4ed8;color:#fff;font-size:11px;font-weight:800;width:24px;height:24px;
                            border-radius:50%;text-align:center;line-height:24px;">3</div>
              </td>
              <td style="padding-left:12px;">
                <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:3px;">Connect to Accentor AI</div>
                <div style="color:#9ca3af;font-size:12px;line-height:1.6;">
                  In the platform: <strong style="color:#d1d5db;">My Account → Broker Connection → Alpaca → Configure.</strong>
                  Paste your keys, select <strong style="color:#fde68a;">Paper</strong>, click Save then Test Connection.
                  A green ✓ confirms you're live.
                </div>
              </td>
            </tr>
          </table>

          <!-- Step 4 -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
            <tr>
              <td width="32" valign="top">
                <div style="background:#1d4ed8;color:#fff;font-size:11px;font-weight:800;width:24px;height:24px;
                            border-radius:50%;text-align:center;line-height:24px;">4</div>
              </td>
              <td style="padding-left:12px;">
                <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:3px;">Run BrownBot on paper for a week</div>
                <div style="color:#9ca3af;font-size:12px;line-height:1.6;">
                  Start BrownBot with your risk settings configured (daily loss limit, position size %).
                  Watch the Logs tab, review the Stats charts after a few sessions, and build confidence in
                  the strategy before touching real money.
                </div>
              </td>
            </tr>
          </table>

          <!-- Paper → Live callout -->
          <div style="background:#1c1c0a;border:1px solid #854d0e;border-radius:8px;padding:14px 16px;">
            <div style="font-size:12px;font-weight:700;color:#fde68a;margin-bottom:6px;">
              ⚠️ When you're ready to go live
            </div>
            <div style="color:#a3a300;font-size:12px;line-height:1.6;">
              Generate a separate set of keys under your Alpaca <strong style="color:#fde68a;">Live Trading</strong> account,
              update the Broker Settings, and switch the environment to <strong style="color:#fca5a5;">Live</strong>.
              Fund your account first — Alpaca has no minimum but most traders start with $1,000–$5,000.
              Always keep the daily loss limit set.
            </div>
          </div>
        </div>
      </td></tr>

      <!-- Why Accentor AI -->
      <tr><td style="padding:28px 44px 0;">
        <div style="font-size:13px;font-weight:700;color:#a78bfa;text-transform:uppercase;
                    letter-spacing:0.08em;margin-bottom:16px;">Why traders choose Accentor AI</div>
        <div style="background:#1c2230;border:1px solid #30363d;border-radius:10px;padding:24px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="padding:7px 0;border-bottom:1px solid #21262d;">
              <span style="color:#a78bfa;font-weight:700;font-size:13px;">→</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">All-in-one platform</strong> — scanning, AI analysis, automated execution, and analytics in a single dashboard. No juggling multiple subscriptions.
              </span>
            </td></tr>
            <tr><td style="padding:7px 0;border-bottom:1px solid #21262d;">
              <span style="color:#a78bfa;font-weight:700;font-size:13px;">→</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Zero setup complexity</strong> — gap-up alerts, AI-ranked swing picks, and live technicals are ready the moment you log in. No scripting or manual configuration required.
              </span>
            </td></tr>
            <tr><td style="padding:7px 0;border-bottom:1px solid #21262d;">
              <span style="color:#a78bfa;font-weight:700;font-size:13px;">→</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Scan to execution in seconds</strong> — live scans are paired with direct order routing through DAS Trader so you act on signals before the crowd.
              </span>
            </td></tr>
            <tr><td style="padding:7px 0;border-bottom:1px solid #21262d;">
              <span style="color:#a78bfa;font-weight:700;font-size:13px;">→</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Intelligent risk management</strong> — automated trailing stops, breakeven triggers, and EOD force-exits protect your capital even when you step away from the screen.
              </span>
            </td></tr>
            <tr><td style="padding:7px 0;border-bottom:1px solid #21262d;">
              <span style="color:#a78bfa;font-weight:700;font-size:13px;">→</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">AI-powered insight, not just data</strong> — contextual news summaries, sector momentum, and ranked swing candidates are generated fresh every session, not recycled from static screeners.
              </span>
            </td></tr>
            <tr><td style="padding:7px 0;">
              <span style="color:#a78bfa;font-weight:700;font-size:13px;">→</span>
              <span style="color:#d1d5db;font-size:13px;margin-left:10px;">
                <strong style="color:#fff;">Built for active day traders</strong> — every feature is optimised for gap-up and intraday setups, not generic long-term investing tools.
              </span>
            </td></tr>
          </table>
        </div>
      </td></tr>

      <!-- CTA -->
      <tr><td style="padding:32px 44px;text-align:center;">
        <a href="https://accentorai.com/app"
           style="display:inline-block;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;
                  text-decoration:none;font-weight:700;font-size:15px;padding:15px 40px;
                  border-radius:10px;letter-spacing:0.02em;box-shadow:0 4px 15px rgba(124,58,237,0.3);">
          Open the Dashboard →
        </a>
        <div style="color:#6b7280;font-size:12px;margin-top:12px;">
          Your trial runs for 7 days. No credit card required to explore.
        </div>
      </td></tr>

      <!-- Footer -->
      <tr><td style="background:#0d1117;padding:20px 44px;border-top:1px solid #21262d;">
        <p style="color:#4b5563;font-size:11px;line-height:1.6;margin:0;text-align:center;">
          If you have questions, reply to this email — we read every one.
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>"""

        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(from_email, app_password)
            server.sendmail(from_email, to_email, msg.as_string())
        app_logger.info(f"Registration welcome email sent to {to_email}")
    except Exception as e:
        app_logger.warning(f"Registration welcome email failed for {to_email}: {e}")


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login a user and return a session token"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        success, result = auth_manager.login_user(
            data.get('username', ''),
            data.get('password', '')
        )
        if success:
            return jsonify({'success': True, 'data': result})
        return jsonify({'success': False, 'error': result}), 401
    except Exception as e:
        app_logger.error(f"Error logging in: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout a user by invalidating their session token"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        auth_manager.logout_user(session_token)
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        app_logger.error(f"Error logging out: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/profile', methods=['GET'])
def get_auth_profile():
    """Get the profile of the currently authenticated user"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_manager.get_user_by_session(session_token)
        if not user:
            return jsonify({'success': False, 'error': 'Invalid or expired session'}), 401
        # ── Trial calculation ──────────────────────────────────────────────
        trial_expires_raw = user.get('trial_expires_at')
        trial_active = False
        trial_days_left = 0
        if trial_expires_raw:
            try:
                trial_exp = datetime.fromisoformat(str(trial_expires_raw))
                delta = trial_exp - datetime.now()
                if delta.total_seconds() > 0:
                    trial_active = True
                    trial_days_left = max(1, delta.days + 1)
            except Exception:
                pass

        base_tier = user.get('subscription_tier', 'basic')
        # Grant beginner access during trial for basic-tier users
        # During trial, basic users get full yogi access; after expiry they revert to basic
        effective_tier = 'yogi' if (trial_active and base_tier == 'basic') else base_tier

        safe_user = {
            'id': user.get('id'),
            'username': user.get('username'),
            'email': user.get('email'),
            'system_role': user.get('system_role'),
            'subscription_tier': effective_tier,
            'subscription_tier_actual': base_tier,
            'subscription_status': user.get('subscription_status', 'active'),
            'has_billing_account': bool(user.get('stripe_customer_id')),
            'is_active': user.get('is_active', 1),
            'preferences': user.get('preferences', {}),
            'created_at': str(user.get('created_at', '')),
            'last_login': str(user.get('last_login', '')),
            'first_name': user.get('first_name') or '',
            'last_name': user.get('last_name') or '',
            'address': user.get('address') or '',
            'profession': user.get('profession') or '',
            'annual_income_range': user.get('annual_income_range') or '',
            'trial_active': trial_active,
            'trial_days_left': trial_days_left,
            'trial_expires_at': str(trial_expires_raw) if trial_expires_raw else None,
        }
        return jsonify({'success': True, 'data': safe_user})
    except Exception as e:
        app_logger.error(f"Error getting auth profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/session/ping', methods=['POST'])
@require_auth
def session_ping():
    """Extend the session and return the new expiry time (used by keepalive)."""
    try:
        # validate_session already extended the expiry inside require_auth.
        # Re-query the updated expiry so the client knows exactly when it lapses.
        token = (request.headers.get('Authorization', '').replace('Bearer ', '')
                 or request.cookies.get('session_token', ''))
        session = db_manager.get_session(token)
        expires_at = str(session['expires_at']) if session else None
        return jsonify({'ok': True, 'expires_at': expires_at})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# Admin endpoints
@app.route('/api/admin/users', methods=['GET'])
@require_role('super_admin', 'dev_master', 'bot_admin')
def admin_list_users():
    """List all users — super_admin, dev_master and bot_admin"""
    try:
        from database import db_manager
        users = db_manager.get_all_users()
        return jsonify({'success': True, 'data': users})
    except Exception as e:
        app_logger.error(f"Error listing users: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users', methods=['POST'])
@require_role('super_admin', 'dev_master', 'bot_admin')
def admin_add_user():
    """Add a new user — super_admin, dev_master and bot_admin (always basic tier)"""
    try:
        from database import db_manager
        from auth import auth_manager as _am
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        if not username or not email or not password:
            return jsonify({'success': False, 'error': 'username, email and password are required'}), 400
        if len(password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        if not any(c.isupper() for c in password):
            return jsonify({'success': False, 'error': 'Password must contain at least one uppercase letter'}), 400
        if not any(c.isdigit() for c in password):
            return jsonify({'success': False, 'error': 'Password must contain at least one number'}), 400
        password_hash = _am.hash_password(password)
        success, message = db_manager.create_user(username, email, password_hash)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error adding user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>/system-role', methods=['PUT'])
@require_role('super_admin')
def admin_update_system_role(user_id):
    """Change a user's system role — super_admin only"""
    try:
        from database import db_manager
        data = request.get_json()
        new_role = data.get('system_role')  # None, 'super_admin', or 'dev_master'
        if request.user.get('id') == user_id:
            return jsonify({'success': False, 'error': 'Cannot change your own system role'}), 400
        success, message = db_manager.update_user_system_role(user_id, new_role)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error updating system role: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>/subscription', methods=['PUT'])
@require_role('super_admin')
def admin_update_subscription(user_id):
    """Change a user's subscription tier — super_admin only"""
    try:
        from database import db_manager
        data = request.get_json()
        tier = data.get('tier', 'basic')
        status = data.get('status', 'active')
        success, message = db_manager.update_user_subscription(user_id, tier, status)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error updating subscription: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>/active', methods=['PUT'])
@require_role('super_admin')
def admin_update_active(user_id):
    """Activate or deactivate a user — super_admin only"""
    try:
        from database import db_manager
        data = request.get_json()
        is_active = data.get('is_active', True)
        if request.user.get('id') == user_id and not is_active:
            return jsonify({'success': False, 'error': 'Cannot deactivate your own account'}), 400
        success, message = db_manager.update_user_active_status(user_id, is_active)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error updating active status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_role('super_admin', 'bot_admin')
def admin_delete_user(user_id):
    """Permanently delete a user — super_admin and bot_admin"""
    try:
        from database import db_manager
        if request.user.get('id') == user_id:
            return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400
        success, message = db_manager.delete_user(user_id)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error deleting user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>/password', methods=['PUT'])
@require_role('super_admin', 'bot_admin')
def admin_reset_user_password(user_id):
    """Admin sets a new password for a user — super_admin and bot_admin"""
    try:
        from database import db_manager
        from auth import auth_manager as _am
        data = request.get_json()
        new_password = (data.get('password') or '').strip()
        if len(new_password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        if not any(c.isupper() for c in new_password):
            return jsonify({'success': False, 'error': 'Password must contain at least one uppercase letter'}), 400
        if not any(c.isdigit() for c in new_password):
            return jsonify({'success': False, 'error': 'Password must contain at least one number'}), 400
        password_hash = _am.hash_password(new_password)
        success, message = db_manager.update_user_password(user_id, password_hash)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error resetting user password: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/db-query', methods=['POST'])
@require_role('super_admin', 'dev_master')
def admin_db_query():
    """Execute a SQL query against the SQLite database.
    SELECT and PRAGMA are always allowed (read-only connection).
    UPDATE, INSERT, DELETE, ALTER, CREATE, DROP are allowed for super_admin
    and dev_master and are committed immediately."""
    import time as _time
    import re as _re
    try:
        body = request.get_json(force=True) or {}
        sql = (body.get('sql') or '').strip()
        if not sql:
            return jsonify({'success': False, 'error': 'No SQL provided'}), 400

        # Strip comments then identify the statement type
        sql_clean = _re.sub(r'--[^\n]*', '', sql)
        sql_clean = _re.sub(r'/\*.*?\*/', '', sql_clean, flags=_re.S).strip()
        first_token = (_re.split(r'\s+', sql_clean)[0] or '').upper()

        READ_TOKENS  = {'SELECT', 'PRAGMA'}
        WRITE_TOKENS = {'UPDATE', 'INSERT', 'DELETE', 'ALTER', 'CREATE', 'DROP'}

        if first_token not in READ_TOKENS | WRITE_TOKENS:
            return jsonify({'success': False,
                            'error': f'Statement type "{first_token}" is not permitted.'}), 400

        # Prevent multi-statement injection (semicolon not at the very end)
        if ';' in sql_clean.rstrip('; \t\n'):
            return jsonify({'success': False,
                            'error': 'Multi-statement queries are not allowed.'}), 400

        is_write = first_token in WRITE_TOKENS
        user = getattr(request, 'user', {})
        log_prefix = '[admin-db-WRITE]' if is_write else '[admin-db-query]'
        app_logger.info(f"{log_prefix} {user.get('username','?')}: {sql[:300]}")

        t0 = _time.time()
        with db_manager.get_connection() as conn:
            if not is_write:
                conn.execute('PRAGMA query_only = ON')
            cursor = conn.execute(sql)
            if is_write:
                conn.commit()
            columns = [d[0] for d in (cursor.description or [])]
            rows = [list(r) for r in cursor.fetchmany(500)] if cursor.description else []
            rows_affected = cursor.rowcount if is_write else None
        elapsed_ms = round((_time.time() - t0) * 1000)

        return jsonify({
            'success':       True,
            'columns':       columns,
            'rows':          rows,
            'row_count':     len(rows),
            'rows_affected': rows_affected,
            'elapsed_ms':    elapsed_ms,
            'truncated':     len(rows) == 500,
            'write':         is_write,
        })
    except Exception as e:
        app_logger.warning(f'admin_db_query error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/admin/debug-user', methods=['POST', 'GET'])
@require_auth
@require_role('super_admin', 'dev_master')
def admin_debug_user():
    """GET — list users currently in verbose debug mode.
    POST { user_id, enable } — toggle per-user debug logging."""
    if request.method == 'GET':
        return jsonify({'success': True, 'debug_user_ids': get_debug_users()})
    data    = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    enable  = bool(data.get('enable', True))
    if user_id is None:
        return jsonify({'success': False, 'error': 'user_id required'}), 400
    set_debug_user(int(user_id), enable)
    action = 'enabled' if enable else 'disabled'
    app_logger.info(f"[admin] debug logging {action} for user_id={user_id} "
                    f"by {request.user.get('username')}")
    return jsonify({'success': True, 'user_id': user_id, 'debug': enable,
                    'debug_user_ids': get_debug_users()})


@app.route('/api/admin/error-logs', methods=['GET'])
@require_auth
@require_role('super_admin', 'dev_master')
def admin_error_logs():
    """Return recent server-side error log entries, optionally filtered by user_id."""
    user_id = request.args.get('user_id', type=int)
    limit   = min(request.args.get('limit', 100, type=int), 500)
    since   = request.args.get('since')          # ISO timestamp lower bound
    logs    = db_manager.get_error_logs(user_id=user_id, limit=limit, since=since)
    return jsonify({'success': True, 'logs': logs, 'count': len(logs)})


@app.route('/api/auth/profile', methods=['PUT'])
@require_auth
def update_auth_profile():
    """Update editable profile fields for the authenticated user"""
    try:
        from database import db_manager
        user = request.user
        data = request.get_json() or {}
        email = (data.get('email') or '').strip()
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'Valid email is required'}), 400
        success, message = db_manager.update_user_profile(
            user['id'],
            first_name=(data.get('first_name') or '').strip() or None,
            last_name=(data.get('last_name') or '').strip() or None,
            email=email,
            address=(data.get('address') or '').strip() or None,
            profession=(data.get('profession') or '').strip() or None,
            annual_income_range=(data.get('annual_income_range') or '').strip() or None,
        )
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error updating profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/change-password', methods=['PUT'])
@require_auth
def change_password():
    """Change password for the authenticated user — requires current password"""
    try:
        from database import db_manager
        from auth import auth_manager as _am
        user = request.user
        data = request.get_json() or {}
        current_password = (data.get('current_password') or '').strip()
        new_password = (data.get('new_password') or '').strip()
        if not current_password or not new_password:
            return jsonify({'success': False, 'error': 'Current and new password are required'}), 400
        # Verify current password
        full_user = db_manager.get_user_by_id(user['id'])
        if not full_user or full_user['password_hash'] != _am.hash_password(current_password):
            return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400
        # Validate new password strength
        if len(new_password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        if not any(c.isupper() for c in new_password):
            return jsonify({'success': False, 'error': 'Password must contain at least one uppercase letter'}), 400
        if not any(c.isdigit() for c in new_password):
            return jsonify({'success': False, 'error': 'Password must contain at least one number'}), 400
        password_hash = _am.hash_password(new_password)
        success, message = db_manager.update_user_password(user['id'], password_hash)
        if success:
            return jsonify({'success': True, 'message': 'Password updated successfully'})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error changing password: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Send a password-reset link to the user's email address"""
    import secrets as _secrets
    from datetime import datetime as _dt, timedelta as _td
    try:
        from database import db_manager
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        user = db_manager.get_user_by_email(email)
        if not user:
            return jsonify({'success': False, 'error': 'No account found with that email address'}), 404
        if not user.get('is_active', 1):
            return jsonify({'success': False, 'error': 'This account has been deactivated'}), 403
        token = _secrets.token_urlsafe(32)
        expires_at = _dt.now() + _td(hours=1)
        ok = db_manager.set_reset_token(user['id'], token, expires_at)
        if not ok:
            app_logger.error("Failed to store reset token for user %s", user['id'])
            return jsonify({'success': False, 'error': 'Could not generate reset token. Please try again.'}), 500
        app_logger.info("Password reset token generated for user %s", user['id'])

        # Build the reset URL
        base_url = request.host_url.rstrip('/')
        reset_url = f"{base_url}/login?reset={token}"

        # Send email via Gmail SMTP
        from_email = os.getenv('CONTACT_EMAIL_FROM', '')
        app_password = os.getenv('GMAIL_APP_PASSWORD', '')
        if from_email and app_password:
            try:
                subject = "Reset your Accentor AI password"
                body = (
                    f"Hi {user.get('username', '')},\n\n"
                    f"We received a request to reset your Accentor AI password.\n\n"
                    f"Click the link below to choose a new password (expires in 1 hour):\n\n"
                    f"  {reset_url}\n\n"
                    f"If you didn't request this, you can safely ignore this email — "
                    f"your password will not be changed.\n\n"
                    f"— Accentor AI Team\n"
                )
                msg = MIMEMultipart()
                msg['From'] = from_email
                msg['To'] = email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(from_email, app_password)
                    server.sendmail(from_email, email, msg.as_string())
                app_logger.info("Password reset email sent to %s", email)
            except Exception as mail_err:
                app_logger.error(f"Failed to send reset email: {mail_err}")
        else:
            app_logger.warning("Reset email not sent: GMAIL credentials not configured. Token: %s", token)

        return jsonify({'success': True, 'message': 'A reset link has been sent to your email address.'})
    except Exception as e:
        app_logger.error(f"Error generating reset token: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset a user's password using a valid reset token"""
    from datetime import datetime as _dt
    try:
        from database import db_manager
        from auth import auth_manager as _am
        data = request.get_json() or {}
        token = (data.get('token') or '').strip()
        new_password = (data.get('password') or '').strip()
        if not token or not new_password:
            return jsonify({'success': False, 'error': 'Token and new password are required'}), 400
        if len(new_password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        if not any(c.isupper() for c in new_password):
            return jsonify({'success': False, 'error': 'Password must contain at least one uppercase letter'}), 400
        if not any(c.isdigit() for c in new_password):
            return jsonify({'success': False, 'error': 'Password must contain at least one number'}), 400
        user = db_manager.get_user_by_reset_token(token)
        if not user:
            return jsonify({'success': False, 'error': 'Invalid or expired reset token'}), 400
        expires_str = user.get('reset_token_expires_at', '')
        if expires_str:
            try:
                expires_at = _dt.fromisoformat(str(expires_str))
                if _dt.now() > expires_at:
                    return jsonify({'success': False, 'error': 'Reset token has expired'}), 400
            except Exception:
                pass
        password_hash = _am.hash_password(new_password)
        ok, err = db_manager.update_user_password(user['id'], password_hash)
        if not ok:
            app_logger.error("Failed to update password for user %s: %s", user['id'], err)
            return jsonify({'success': False, 'error': 'Failed to update password. Please try again.'}), 500
        db_manager.clear_reset_token(user['id'])
        return jsonify({'success': True, 'message': 'Password reset successfully. You can now log in.'})
    except Exception as e:
        app_logger.error(f"Error resetting password: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Subscription self-service endpoints
@app.route('/api/subscription', methods=['GET'])
@require_auth
def get_subscription():
    """Get current user's subscription info"""
    try:
        user = request.user
        return jsonify({'success': True, 'data': {
            'subscription_tier': user.get('subscription_tier', 'basic'),
            'subscription_status': user.get('subscription_status', 'active'),
            'system_role': user.get('system_role'),
            'has_billing_account': bool(user.get('stripe_customer_id')),
            'stripe_available': STRIPE_AVAILABLE,
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stripe/create-checkout-session', methods=['POST'])
@require_auth
def stripe_create_checkout():
    """Start a Stripe Checkout flow for a subscription upgrade"""
    if not STRIPE_AVAILABLE:
        return jsonify({'success': False, 'error': 'Stripe is not configured on this server'}), 503
    try:
        from database import db_manager
        user = request.user
        if user.get('system_role'):
            return jsonify({'success': False, 'error': 'Staff accounts do not use paid subscriptions'}), 400
        data = request.get_json()
        tier = data.get('tier', '')
        if tier not in ('beginner', 'advanced', 'yogi'):
            return jsonify({'success': False, 'error': f"Invalid tier: {tier}"}), 400

        base_url = request.host_url.rstrip('/')
        result = stripe_mgr.create_checkout_session(
            user_id=user['id'],
            email=user['email'],
            username=user['username'],
            tier=tier,
            success_url=f"{base_url}/?payment=success",
            cancel_url=f"{base_url}/?payment=cancelled",
            existing_customer_id=user.get('stripe_customer_id')
        )
        # Pre-emptively store the customer ID so we can link the webhook
        db_manager.update_stripe_customer_id(user['id'], result['customer_id'])

        return jsonify({'success': True, 'url': result['url']})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        app_logger.error(f"Stripe checkout error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stripe/create-portal-session', methods=['POST'])
@require_auth
def stripe_create_portal():
    """Open the Stripe Customer Portal for self-service billing management"""
    if not STRIPE_AVAILABLE:
        return jsonify({'success': False, 'error': 'Stripe is not configured on this server'}), 503
    try:
        user = request.user
        customer_id = user.get('stripe_customer_id')
        if not customer_id:
            return jsonify({'success': False, 'error': 'No billing account found. Please subscribe first.'}), 400

        base_url = request.host_url.rstrip('/')
        result = stripe_mgr.create_portal_session(
            customer_id=customer_id,
            return_url=f"{base_url}/?tab=account"
        )
        return jsonify({'success': True, 'url': result['url']})
    except Exception as e:
        app_logger.error(f"Stripe portal error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe webhook — verifies signature, updates subscription state in DB"""
    if not STRIPE_AVAILABLE:
        return jsonify({'error': 'Stripe not configured'}), 503

    from database import db_manager
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        # Verify signature — raises on failure
        stripe_mgr.construct_webhook_event(payload, sig_header)
    except Exception as e:
        app_logger.warning(f"Stripe webhook signature error: {e}")
        return jsonify({'error': str(e)}), 400

    # Use raw JSON for data access — avoids Stripe SDK v10 typed-object issues
    event_dict = json.loads(payload)
    etype = event_dict['type']
    obj = event_dict['data']['object']

    try:
        if etype == 'checkout.session.completed':
            metadata = obj.get('metadata') or {}
            user_id = int(metadata.get('user_id', 0))
            tier = metadata.get('tier', 'basic')
            customer_id = obj.get('customer')
            subscription_id = obj.get('subscription')
            if user_id:
                db_manager.update_stripe_customer_id(user_id, customer_id)
                db_manager.update_user_subscription(user_id, tier, 'active', subscription_id)
                app_logger.info(f"Checkout completed: user {user_id} → {tier}")

        elif etype == 'customer.subscription.updated':
            customer_id = obj.get('customer')
            user = db_manager.get_user_by_stripe_customer_id(customer_id)
            if user:
                # Determine tier from price ID in subscription items
                items = obj.get('items', {}).get('data', [])
                tier = 'basic'
                for item in items:
                    price_id = item.get('price', {}).get('id', '')
                    from stripe_manager import _PRICE_TIER_MAP
                    if price_id in _PRICE_TIER_MAP:
                        tier = _PRICE_TIER_MAP[price_id]
                        break
                if tier == 'basic':
                    tier = (obj.get('metadata') or {}).get('tier', 'basic')
                raw_status = obj.get('status', 'active')
                status_map = {'active': 'active', 'past_due': 'past_due',
                              'unpaid': 'past_due', 'canceled': 'cancelled',
                              'incomplete': 'incomplete', 'trialing': 'active'}
                status = status_map.get(raw_status, raw_status)
                db_manager.update_user_subscription(user['id'], tier, status, obj.get('id'))
                app_logger.info(f"Subscription updated: user {user['id']} → {tier} ({status})")

        elif etype == 'customer.subscription.deleted':
            customer_id = obj.get('customer')
            user = db_manager.get_user_by_stripe_customer_id(customer_id)
            if user:
                db_manager.cancel_user_subscription(user['id'])
                app_logger.info(f"Subscription deleted: user {user['id']} reverted to basic")

        elif etype == 'invoice.payment_failed':
            customer_id = obj.get('customer')
            user = db_manager.get_user_by_stripe_customer_id(customer_id)
            if user:
                db_manager.update_user_subscription(
                    user['id'], user.get('subscription_tier', 'basic'), 'past_due'
                )
                app_logger.warning(f"Payment failed: user {user['id']} marked past_due")

        elif etype == 'invoice.payment_succeeded':
            customer_id = obj.get('customer')
            user = db_manager.get_user_by_stripe_customer_id(customer_id)
            if user and user.get('subscription_status') == 'past_due':
                db_manager.update_user_subscription(
                    user['id'], user.get('subscription_tier', 'basic'), 'active'
                )
                app_logger.info(f"Payment recovered: user {user['id']} reactivated")

    except Exception as e:
        app_logger.error(f"Error processing Stripe webhook {etype}: {e}", exc_info=True)
        return jsonify({'received': True, 'warning': str(e)})

    return jsonify({'received': True})


@app.route('/api/subscription/cancel', methods=['PUT'])
@require_auth
def cancel_subscription():
    """Cancel subscription — redirects paid users to Stripe Portal, clears free users directly"""
    try:
        from database import db_manager
        user = request.user
        if user.get('system_role'):
            return jsonify({'success': False, 'error': 'Staff accounts do not use subscriptions'}), 400
        # If they have a Stripe customer, tell the frontend to use the portal instead
        if user.get('stripe_customer_id') and STRIPE_AVAILABLE:
            return jsonify({
                'success': False,
                'use_portal': True,
                'error': 'Please manage your subscription via the billing portal'
            }), 400
        success, message = db_manager.cancel_user_subscription(user['id'])
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'real_data_available': REAL_DATA_AVAILABLE,
            'websocket_connected': websocket_connected
        })
    except Exception as e:
        app_logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/gap-ups')
def get_gap_ups():
    """Get gap-up stocks data"""
    try:
        if not REAL_DATA_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Gap-up detection not available'
            }), 503
        
        # Get gap-up data
        gap_ups = get_gap_up_stocks_for_frontend()
        
        return jsonify({
            'success': True,
            'data': gap_ups,
            'timestamp': datetime.now().isoformat(),
            'count': len(gap_ups)
        })
    except Exception as e:
        app_logger.error(f"Error getting gap-ups: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/gap-ups/force-refresh', methods=['POST'])
def force_refresh_gap_ups():
    """
    Nuke ALL gap-up caches (session-aware + legacy) and immediately re-fetch.
    Updates both the frontend cache AND the real_time_gap_ups global that
    BrownBot's day scanner reads every 30 seconds.
    """
    global real_time_gap_ups
    try:
        from gap_up_cache import invalidate_gap_up_cache
        invalidate_gap_up_cache()
        app_logger.info('[ForceRefresh] All gap-up caches cleared — fetching fresh data...')
        fresh = get_gap_up_stocks_for_frontend()
        # Update the global that BrownBot reads so it also sees fresh data immediately.
        real_time_gap_ups = fresh
        app_logger.info(f'[ForceRefresh] Done — {len(fresh)} stocks returned, real_time_gap_ups updated')
        return jsonify({'success': True, 'data': fresh, 'count': len(fresh),
                        'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f'[ForceRefresh] Error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gap-ups/<ticker>')
def get_gap_up_details(ticker):
    """Get detailed gap-up information for a specific ticker"""
    try:
        if not REAL_DATA_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Gap-up detection not available'
            }), 503
        
        # Get historical gap-up data for the ticker
        historical_data = get_historical_gap_up_data(ticker)
        
        return jsonify({
            'success': True,
            'data': {
                'ticker': ticker,
                'historical_data': historical_data
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting gap-up details for {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/gap-ups/config', methods=['GET', 'POST'])
def gap_ups_config():
    """Gap-up config endpoint — threshold filter removed; invalidate cache on POST."""
    try:
        if request.method == 'POST':
            try:
                from gap_up_cache import invalidate_gap_up_cache
                invalidate_gap_up_cache()
            except Exception:
                pass
        return jsonify({'success': True, 'data': {}})
    except Exception as e:
        app_logger.error(f"Error in gap-ups config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gap-ups/snapshot/dates')
def get_gap_up_snapshot_dates():
    """Return the list of dates that have saved gap-up snapshots."""
    try:
        from database import db_manager
        dates = db_manager.get_gap_up_snapshot_dates()
        return jsonify({'success': True, 'dates': dates})
    except Exception as e:
        app_logger.error(f"Error fetching snapshot dates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gap-ups/snapshot/<date>')
def get_gap_up_snapshot(date):
    """Return the gap-up snapshot for a specific trading date (YYYY-MM-DD)."""
    try:
        from database import db_manager
        stocks = db_manager.get_gap_up_snapshot(date)
        return jsonify({'success': True, 'date': date, 'data': stocks, 'count': len(stocks)})
    except Exception as e:
        app_logger.error(f"Error fetching gap-up snapshot for {date}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gap-ups/history/<ticker>')
def get_gap_up_ticker_history(ticker):
    """Return all gap-up snapshot records for a ticker from the local database."""
    try:
        from database import db_manager
        days = request.args.get('days', None, type=int)
        records = db_manager.get_gap_up_ticker_history(ticker.upper(), days=days)
        return jsonify({
            'success': True,
            'ticker': ticker.upper(),
            'data': records,
            'count': len(records)
        })
    except Exception as e:
        app_logger.error(f"Error fetching gap-up history for {ticker}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/historical-data/<ticker>')
def get_historical_data(ticker):
    """Get historical data for a specific ticker"""
    try:
        app_logger.info(f"🔍 Historical data request for {ticker}")
        
        if not REAL_DATA_AVAILABLE:
            app_logger.warning(f"Historical data not available for {ticker}")
            return jsonify({
                'success': False,
                'error': 'Historical data not available'
            }), 503
        
        # Get query parameters - accept both 'period' and 'days' for compatibility
        period = request.args.get('period', '365', type=int)
        days = request.args.get('days', period, type=int)  # Use period as fallback for days
        use_cache = request.args.get('cache', 'true').lower() == 'true'
        min_gap = request.args.get('min_gap', 25, type=float)

        app_logger.info(f"📊 Fetching historical data for {ticker} - {days} days, min_gap={min_gap}%, cache: {use_cache}")
        
        # Add timeout protection for historical data fetching using threading
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def fetch_data():
            try:
                app_logger.info(f"🔄 Starting data fetch for {ticker}")
                data = get_historical_gap_up_data(ticker, days=days, use_cache=use_cache, min_gap_percent=min_gap)
                app_logger.info(f"✅ Data fetch completed for {ticker}, got {len(data) if data else 0} records")
                result_queue.put(data)
            except Exception as e:
                app_logger.error(f"❌ Exception in data fetch for {ticker}: {e}")
                exception_queue.put(e)
        
        # Start the data fetching in a separate thread
        fetch_thread = threading.Thread(target=fetch_data)
        fetch_thread.daemon = True
        fetch_thread.start()
        
        # Wait for result with timeout (30 seconds)
        try:
            fetch_thread.join(timeout=30)
            
            if fetch_thread.is_alive():
                app_logger.error(f"⏰ Timeout fetching historical data for {ticker}")
                return jsonify({
                    'success': False,
                    'error': f'Timeout fetching historical data for {ticker}. Please try again.'
                }), 408
            
            # Check for exceptions
            if not exception_queue.empty():
                exception = exception_queue.get()
                app_logger.error(f"❌ Exception in historical data fetch for {ticker}: {exception}")
                return jsonify({
                    'success': False,
                    'error': f'Error fetching data: {str(exception)}'
                }), 500
            
            # Get the result
            historical_data = result_queue.get()
            
        except Exception as e:
            app_logger.error(f"❌ Error in historical data fetch for {ticker}: {e}")
            return jsonify({
                'success': False,
                'error': f'Error in data fetch: {str(e)}'
            }), 500
        
        if historical_data is None:
            app_logger.warning(f"⚠️ No bar data returned for {ticker} — Alpaca API may be down or credentials/subscription invalid")
            return jsonify({
                'success': False,
                'error': (
                    f'No price data available for {ticker}. '
                    f'This usually means the Alpaca API key is missing or the subscription '
                    f'does not include historical bars. Check server logs for details.'
                )
            }), 404
        
        # Ensure we return a list even if empty
        if not isinstance(historical_data, list):
            app_logger.warning(f"⚠️ Historical data for {ticker} is not a list: {type(historical_data)}")
            historical_data = []
        
        app_logger.info(f"✅ Successfully retrieved {len(historical_data)} records for {ticker}")

        resp = jsonify({
            'success': True,
            'data': historical_data,
            'ticker': ticker,
            'days': days,
            'count': len(historical_data),
            'timestamp': datetime.now().isoformat()
        })
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        return resp
        
    except Exception as e:
        app_logger.error(f"❌ Unexpected error getting historical data for {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }), 500


@app.route('/api/historical-prefetch/status')
def get_historical_prefetch_status():
    """Returns which gap-up tickers have been pre-fetched today for the Historical tab."""
    today = datetime.now().date().isoformat()
    with _hist_prefetch_lock:
        today_ok = {
            t: {'records': v['records'], 'fetched_at': v['fetched_at']}
            for t, v in _hist_prefetch_status.items()
            if v.get('date') == today and not v.get('error')
        }
    return jsonify({'success': True, 'prefetched': today_ok, 'total': len(today_ok), 'date': today})


# ── In-memory cache + rate limiter (no Redis needed) ─────────────────────────
import threading as _threading

_analysis_cache:    dict = {}   # cache_key  -> (stored_at: float, payload: dict)
_sector_etf_cache:  dict = {}   # etf_symbol -> (stored_at: float, perf: dict)
_news_cache:        dict = {}   # ticker     -> (stored_at: float, payload: dict)
_rate_limit_store:  dict = {}   # client_ip  -> [call_timestamps: float]
_cache_lock = _threading.Lock()

_ANALYSIS_TTL    = 4 * 3600    # re-use analysis result for 4 h
_SECTOR_ETF_TTL  = 4 * 3600    # sector ETF bars stale after 4 h
_NEWS_TTL        = 30 * 60     # news stale after 30 min
_RATE_MAX        = 20           # max AI Predict calls per hour per IP (cache hits don't count)
_RATE_WINDOW     = 3600         # …per hour per IP


def _cache_get(store: dict, key: str, ttl: float):
    with _cache_lock:
        entry = store.get(key)
        if entry and (time.time() - entry[0]) < ttl:
            return entry[1]
        store.pop(key, None)
        return None


def _cache_set(store: dict, key: str, value):
    with _cache_lock:
        store[key] = (time.time(), value)


def _check_rate_limit(ip: str):
    """Return (allowed: bool, retry_after_seconds: int)."""
    now = time.time()
    with _cache_lock:
        recent = [t for t in _rate_limit_store.get(ip, []) if now - t < _RATE_WINDOW]
        if len(recent) >= _RATE_MAX:
            retry = int(_RATE_WINDOW - (now - recent[0]))
            _rate_limit_store[ip] = recent
            return False, retry
        recent.append(now)
        _rate_limit_store[ip] = recent
        return True, 0


# ── Sector analysis helpers ────────────────────────────────────────────────────

def _sic_to_sector_etf(sic_code, sic_desc=''):
    """Map Polygon SIC code + description to (sector_name, sector_SPDR_ETF)."""
    desc = (sic_desc or '').upper()
    # Description keyword matching takes priority — more reliable than SIC ranges
    _kw_map = [
        (['SOFTWARE', 'PREPACKAGED', 'COMPUTER INTEGRATED', 'SEMICONDUCTOR', 'MICROCHIP',
          'INTERNET', 'DATA PROCESSING', 'INFORMATION TECHNOLOGY', 'ARTIFICIAL INTEL',
          'ELECTRONIC COMPONENT', 'ELECTRONIC EQUIPMENT', 'OPTICAL INSTRUMENT'], ('Technology', 'XLK')),
        (['PHARMACEUTICAL', 'BIOTECHNOLOGY', 'MEDICAL DEVICE', 'MEDICAL EQUIPMENT',
          'HEALTH SERVICE', 'HOSPITAL', 'DIAGNOSTIC', 'DRUG STORE', 'DRUG MFRS',
          'BIOLOGICAL PRODUCT', 'DENTAL', 'CLINICAL', 'GENOMIC'], ('Healthcare', 'XLV')),
        (['BANK', 'SAVINGS INSTITUTION', 'INSURANCE', 'INVESTMENT', 'SECURITY BROKER',
          'FINANCE SERVICE', 'CREDIT SERVICE', 'MORTGAGE', 'FINANCIAL SERVICE',
          'ASSET MANAGEMENT', 'HEDGE FUND', 'BROKERAGE'], ('Financials', 'XLF')),
        (['OIL AND GAS', 'PETROLEUM', 'CRUDE OIL', 'NATURAL GAS', 'PIPELINE',
          'REFIN', 'COAL MINING', 'OFFSHORE DRILL'], ('Energy', 'XLE')),
        (['RETAIL STORE', 'RESTAURANT', 'HOTEL', 'MOTEL', 'CASINO', 'GAMBLING',
          'AUTOMOTIVE', 'APPAREL', 'LEISURE', 'ENTERTAINMENT', 'HOME FURNISH',
          'APPLIANCE', 'CLOTHING', 'FOOTWEAR'], ('Consumer Discretionary', 'XLY')),
        (['FOOD', 'BEVERAGE', 'GROCERY', 'TOBACCO', 'HOUSEHOLD PRODUCT',
          'PERSONAL CARE', 'COSMETIC', 'SOAP', 'CLEANING PRODUCT'], ('Consumer Staples', 'XLP')),
        (['AEROSPACE', 'DEFENSE', 'MACHINERY', 'RAILROAD', 'AIRLINE', 'AIR TRANSPORT',
          'SHIPPING', 'FREIGHT', 'TRUCKING', 'CONSTRUCTION', 'ENGINEERING',
          'INDUSTRIAL MACHINE', 'ELECTRICAL EQUIPMENT'], ('Industrials', 'XLI')),
        (['ELECTRIC UTILITY', 'GAS DISTRIBUTION', 'WATER SUPPLY', 'POWER GENERAT',
          'SANITARY SERVICE'], ('Utilities', 'XLU')),
        (['CABLE', 'BROADCASTING', 'PUBLISHING', 'WIRELESS TELECOM', 'TELECOM',
          'TELEPHONE', 'MEDIA', 'SOCIAL NETWORK', 'ADVERTISING AGENCY',
          'MOTION PICTURE'], ('Communication Services', 'XLC')),
        (['MINING', 'METAL SERVICE', 'CHEMICAL', 'PAPER MILL', 'TIMBER', 'GLASS',
          'STEEL WORK', 'ALUMINUM', 'GOLD MINING', 'SILVER MINING'], ('Materials', 'XLB')),
        (['REAL ESTATE', 'REIT', 'PROPERTY MANAGEMENT', 'APARTMENT', 'LAND SUBDIVIDER',
          'OPERATORS OF APART'], ('Real Estate', 'XLRE')),
    ]
    for keywords, result in _kw_map:
        if any(kw in desc for kw in keywords):
            return result

    # Fallback: SIC numeric ranges
    try:
        sic = int(sic_code) if sic_code else 0
    except (ValueError, TypeError):
        return ('Diversified', 'SPY')

    if 7370 <= sic <= 7379 or 3570 <= sic <= 3579 or 3670 <= sic <= 3679:
        return ('Technology', 'XLK')
    if 4800 <= sic <= 4899:
        return ('Communication Services', 'XLC')
    if 4900 <= sic <= 4999:
        return ('Utilities', 'XLU')
    if 6000 <= sic <= 6799:
        return ('Financials', 'XLF')
    if 1300 <= sic <= 1399 or 2900 <= sic <= 2999:
        return ('Energy', 'XLE')
    if 2000 <= sic <= 2199:
        return ('Consumer Staples', 'XLP')
    if 5900 <= sic <= 5999:
        return ('Consumer Discretionary', 'XLY')
    if 8000 <= sic <= 8099:
        return ('Healthcare', 'XLV')
    if 2800 <= sic <= 2899 or 1000 <= sic <= 1499:
        return ('Materials', 'XLB')
    if 3400 <= sic <= 3699 or 3700 <= sic <= 3799:
        return ('Industrials', 'XLI')
    if 6500 <= sic <= 6552:
        return ('Real Estate', 'XLRE')
    return ('Diversified', 'SPY')


def _get_sector_context(ticker):
    """
    Fetch sector classification (yfinance) and recent sector ETF + SPY performance (Alpaca).
    Returns (sector_info dict, perf dict).  Safe — never raises.
    """
    import requests as _req

    sector_info = {'sector': 'Unknown', 'etf': 'SPY',
                   'sic_code': '', 'sic_description': '', 'company_name': ticker}
    perf = {}

    # Step 1: company/sector info via yfinance
    try:
        import yfinance as yf
        info = yf.Ticker(ticker.upper()).info
        yf_sector = info.get('sector', '') or ''
        # Map yfinance sector name → (sector, ETF) via keyword match using existing _sic_to_sector_etf
        sector, etf = _sic_to_sector_etf('', yf_sector.upper())
        sector_info = {
            'sector':          sector,
            'etf':             etf,
            'sic_code':        '',
            'sic_description': yf_sector,
            'company_name':    info.get('longName', ticker),
        }
    except Exception as e:
        app_logger.warning(f"Sector ref lookup failed for {ticker}: {e}")

    # Step 2: sector ETF + SPY performance — check cache first (4 h TTL)
    etf_sym = sector_info['etf']
    cached_perf = _cache_get(_sector_etf_cache, etf_sym, _SECTOR_ETF_TTL)
    if cached_perf is not None:
        app_logger.info(f"Sector ETF cache HIT for {etf_sym}")
        return sector_info, cached_perf

    end_dt   = datetime.now().strftime('%Y-%m-%d')
    start_dt = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
    _ak = os.getenv('ALPACA_API_KEY', '')
    _as = os.getenv('ALPACA_API_SECRET', '')
    if not _ak or not _as:
        return sector_info, perf
    _alpaca_hdrs = {
        'APCA-API-KEY-ID':     _ak,
        'APCA-API-SECRET-KEY': _as,
    }

    def _bars(sym):
        try:
            r = _req.get(
                f'https://data.alpaca.markets/v2/stocks/{sym}/bars',
                headers=_alpaca_hdrs,
                params={'timeframe': '1Day', 'start': start_dt, 'end': end_dt,
                        'limit': 15, 'adjustment': 'raw', 'feed': 'sip'},
                timeout=8,
            )
            return r.json().get('bars', []) if r.status_code == 200 else []
        except Exception:
            return []

    def _summarize(bars, sym):
        if not bars or len(bars) < 2:
            return {}
        closes = [b['c'] for b in bars]
        chg_1d = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
        n = min(6, len(closes))
        chg_5d = round((closes[-1] - closes[-n]) / closes[-n] * 100, 2)
        up_days = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
        trend = ('uptrending' if chg_5d > 0.5 else ('downtrending' if chg_5d < -0.5 else 'flat'))
        return {'symbol': sym, 'last_close': round(closes[-1], 2),
                'change_1d_pct': chg_1d, 'change_5d_pct': chg_5d,
                'trend_5d': trend, 'up_days_of_10': up_days}

    etf_bars = _bars(etf_sym)
    spy_bars = _bars('SPY') if etf_sym != 'SPY' else etf_bars

    perf['sector_etf'] = _summarize(etf_bars, etf_sym)
    if etf_sym != 'SPY':
        perf['spy'] = _summarize(spy_bars, 'SPY')
        sec_5d = perf['sector_etf'].get('change_5d_pct') or 0
        spy_5d = perf['spy'].get('change_5d_pct') or 0
        rel = round(sec_5d - spy_5d, 2)
        perf['sector_vs_market_5d'] = rel
        perf['relative_strength'] = ('outperforming' if rel > 0.3
                                     else ('underperforming' if rel < -0.3 else 'in-line with'))
    else:
        perf['spy'] = perf['sector_etf']
        perf['sector_vs_market_5d'] = 0
        perf['relative_strength'] = 'in-line with'

    _cache_set(_sector_etf_cache, etf_sym, perf)
    app_logger.info(f"Sector ETF cache SET for {etf_sym}")
    return sector_info, perf


# ── Historical AI analysis endpoint ───────────────────────────────────────────

@app.route('/api/historical-analysis/<ticker>', methods=['POST'])
def get_historical_analysis(ticker):
    """Use Claude AI to analyze historical gap-up patterns and predict next gap-up day behavior."""
    try:
        if not AI_AGENT_AVAILABLE or not _ai_agent:
            return jsonify({'success': False, 'error': 'AI analysis not available'}), 503

        if not _gap_up_agent:
            return jsonify({'success': False, 'error': 'AI analysis not available'}), 503

        body  = request.get_json(force=True) or {}
        stats = body.get('stats', {})
        rows  = body.get('rows', [])  # raw per-day data rows from the frontend

        # ── Analysis cache: keyed by ticker + row count + min gap + calendar date ──
        # Check cache BEFORE rate limiting — cache hits are free and don't count against the limit.
        today     = datetime.now().strftime('%Y-%m-%d')
        cache_key = f"{ticker.upper()}|rows={len(rows)}|minGap={stats.get('minGap','')}|{today}"
        cached_result = _cache_get(_analysis_cache, cache_key, _ANALYSIS_TTL)
        if cached_result is not None:
            app_logger.info(f"Analysis cache HIT for {cache_key}")
            cached_result['cached'] = True
            return jsonify(cached_result)

        # ── Rate limit: only applies to real Claude API calls, not cache hits ──
        client_ip = (request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown').split(',')[0].strip()
        allowed, retry_after = _check_rate_limit(client_ip)
        if not allowed:
            mins, secs = divmod(retry_after, 60)
            wait_str = f"{mins}m {secs}s" if mins else f"{secs}s"
            app_logger.warning(f"Rate limit hit for {client_ip} on /api/historical-analysis/{ticker}")
            return jsonify({
                'success': False,
                'error': f'Too many AI Predict requests. Please wait {wait_str} before trying again.',
                'rate_limited': True,
                'retry_after': retry_after
            }), 429

        sector_info, sector_perf = _get_sector_context(ticker)

        analysis = _gap_up_agent.analyze(
            ticker     = ticker,
            rows       = rows,
            stats      = stats,
            sector_info = sector_info,
            sector_perf = sector_perf,
        )

        result = {
            'success': True,
            'analysis': analysis,
            'ticker': ticker.upper(),
            'sector_info': sector_info,
            'sector_perf': sector_perf,
            'stats': stats,
            'cached': False
        }
        _cache_set(_analysis_cache, cache_key, result)
        app_logger.info(f"Analysis cache SET for {cache_key}")
        return jsonify(result)

    except json.JSONDecodeError as e:
        app_logger.error(f"JSON parse error in historical analysis for {ticker}: {e}")
        return jsonify({'success': False, 'error': 'AI returned malformed response, try again'}), 500
    except Exception as e:
        app_logger.error(f"Error in historical analysis for {ticker}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stock-news/<ticker>')
def get_stock_news_endpoint(ticker):
    """Fetch latest news for a ticker from Polygon and summarise with Claude."""
    import requests as _req
    import re as _re

    ticker = ticker.upper()

    cached = _cache_get(_news_cache, ticker, _NEWS_TTL)
    if cached:
        cached['cached'] = True
        return jsonify(cached)

    articles = []

    # Primary: yfinance news
    try:
        import yfinance as yf
        yf_news = yf.Ticker(ticker).news or []
        for item in yf_news[:8]:
            content = item.get('content') or {}
            articles.append({
                'title':       content.get('title') or item.get('title', ''),
                'url':         (content.get('canonicalUrl') or {}).get('url') or item.get('link', ''),
                'source':      (content.get('provider') or {}).get('displayName', ''),
                'published':   content.get('pubDate', ''),
                'description': (content.get('summary') or '')[:220],
            })
    except Exception as e:
        app_logger.warning(f"yfinance news failed for {ticker}: {e}")

    # Fallback: AI agent web search
    if not articles and AI_AGENT_AVAILABLE and _ai_agent:
        try:
            result = _ai_agent._get_stock_news(ticker, days=7)
            for item in (result.get('news') or []):
                articles.append({
                    'title':       item.get('title') or item.get('snippet', ''),
                    'url':         item.get('url', ''),
                    'source':      '',
                    'published':   '',
                    'description': item.get('snippet', ''),
                })
        except Exception as e:
            app_logger.warning(f"Web search news fallback failed for {ticker}: {e}")

    # Claude summary of top headlines
    summary = ''
    if articles and AI_AGENT_AVAILABLE and _ai_agent:
        headlines = '\n'.join(f"- {a['title']}" for a in articles[:6] if a['title'])
        try:
            resp = _ai_agent.process_message(
                f"You are a concise trading news analyst. Summarise these recent news headlines about {ticker} "
                f"in exactly 2-3 sentences. Focus on: key catalysts, market sentiment, and what traders should watch. "
                f"Do not use bullet points — write flowing prose.\n\nHeadlines:\n{headlines}",
                user_id=f"news_summary_{ticker}"
            )
            if resp.get('success'):
                summary = resp.get('response', '').strip()
        except Exception as e:
            app_logger.warning(f"News summary Claude call failed for {ticker}: {e}")

    result = {
        'success':  True,
        'ticker':   ticker,
        'articles': articles[:6],
        'summary':  summary,
        'cached':   False,
    }
    _cache_set(_news_cache, ticker, result)
    return jsonify(result)


@app.route('/api/lead-capture', methods=['POST'])
def lead_capture():
    """
    Save a landing-page email lead and send a welcome email with a
    free market analysis / gap-up overview.
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    source = data.get('source', 'landing_popup')

    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Valid email required'}), 400

    from database import db_manager as _db
    ok, status = _db.save_email_lead(email, source)
    if not ok:
        return jsonify({'success': False, 'error': 'Could not save email'}), 500

    # Send welcome email (fire-and-forget; don't fail the request if SMTP isn't configured)
    from_email   = os.getenv('CONTACT_EMAIL_FROM', '')
    app_password = os.getenv('GMAIL_APP_PASSWORD', '')
    if from_email and app_password and status == 'new':
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Welcome to Accentor AI — Your Free Market Edge Starts Here'
            msg['From']    = from_email
            msg['To']      = email

            html_body = """
<html><body style="margin:0;padding:0;background:#0d1117;font-family:Arial,sans-serif;color:#e2e8f0;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:40px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">
      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#1d4ed8,#7c3aed);padding:32px 40px;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#fff;letter-spacing:-0.5px;">Accentor <span style="color:#93c5fd;">AI</span></div>
        <div style="color:#bfdbfe;font-size:13px;margin-top:6px;">AI-Powered Gap-Up Trading Intelligence</div>
      </td></tr>
      <!-- Body -->
      <tr><td style="padding:36px 40px;">
        <h2 style="color:#fff;font-size:20px;margin:0 0 12px;">Welcome — you're in! 🎉</h2>
        <p style="color:#9ca3af;font-size:14px;line-height:1.7;margin:0 0 20px;">
          Thanks for joining. Every trading day you'll get the edge that most retail traders miss:
          pre-market gap-up scans, sector momentum shifts, and AI-powered swing setups — straight to your inbox.
        </p>
        <!-- Feature list -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
          <tr><td style="padding:10px 0;border-bottom:1px solid #21262d;">
            <span style="color:#60a5fa;font-size:13px;">📈</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;"><strong style="color:#fff;">Daily Gap-Up Scan</strong> — pre-market movers filtered for momentum</span>
          </td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #21262d;">
            <span style="color:#60a5fa;font-size:13px;">🤖</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;"><strong style="color:#fff;">AI Market Summary</strong> — sector context and key levels to watch</span>
          </td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #21262d;">
            <span style="color:#60a5fa;font-size:13px;">🔥</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;"><strong style="color:#fff;">Hot Swing Picks</strong> — top 6-8 setups ranked by AI each session</span>
          </td></tr>
          <tr><td style="padding:10px 0;">
            <span style="color:#60a5fa;font-size:13px;">📰</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;"><strong style="color:#fff;">News Digest</strong> — catalyst headlines summarised for traders</span>
          </td></tr>
        </table>
        <!-- CTA -->
        <div style="text-align:center;margin-bottom:28px;">
          <a href="https://accentorai.com/login?view=register"
             style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;
                    font-weight:700;font-size:14px;padding:14px 32px;border-radius:10px;
                    letter-spacing:0.02em;">
            Start Your Free 7-Day Trial →
          </a>
          <div style="color:#6b7280;font-size:11px;margin-top:10px;">No credit card required</div>
        </div>
        <p style="color:#6b7280;font-size:12px;line-height:1.6;margin:0;">
          You're receiving this because you signed up at accentorai.com.
          You can <a href="#" style="color:#60a5fa;">unsubscribe</a> at any time.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

            msg.attach(MIMEText(html_body, 'html'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(from_email, app_password)
                server.sendmail(from_email, email, msg.as_string())
            _db.mark_welcome_sent(email)
            app_logger.info(f"Welcome email sent to lead: {email}")
        except Exception as mail_err:
            app_logger.warning(f"Welcome email failed for {email}: {mail_err}")

    return jsonify({
        'success': True,
        'status':  status,   # 'new' or 'exists'
        'message': "You're on the list! Check your inbox for your free market analysis."
            if status == 'new' else "You're already on the list — watch your inbox!"
    })


@app.route('/api/test-historical/<ticker>')
def test_historical_data(ticker):
    """Test endpoint for historical data functionality"""
    try:
        app_logger.info(f"🧪 Testing historical data for {ticker}")
        
        # Test the import
        try:
            from historical_data import get_historical_gap_up_data
            app_logger.info("✅ Historical data module imported successfully")
        except Exception as e:
            app_logger.error(f"❌ Failed to import historical data module: {e}")
            return jsonify({
                'success': False,
                'error': f'Import error: {str(e)}'
            }), 500
        
        # Test with a small number of days
        try:
            data = get_historical_gap_up_data(ticker, days=7, use_cache=False)
            app_logger.info(f"✅ Test data fetch successful, got {len(data) if data else 0} records")
            return jsonify({
                'success': True,
                'message': f'Test successful for {ticker}',
                'records_found': len(data) if data else 0,
                'data_type': str(type(data))
            })
        except Exception as e:
            app_logger.error(f"❌ Test data fetch failed: {e}")
            return jsonify({
                'success': False,
                'error': f'Test fetch error: {str(e)}'
            }), 500
            
    except Exception as e:
        app_logger.error(f"❌ Test endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': f'Test error: {str(e)}'
        }), 500

@app.route('/api/cache/status')
def get_cache_status():
    """Get overall cache status and statistics"""
    try:
        from historical_cache import historical_cache
        
        # Get cache stats
        stats = historical_cache.get_cache_stats()
        
        # Get recent cache activity
        recent_activity = []
        try:
            with historical_cache.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ticker, updated_at, COUNT(*) as records
                    FROM historical_data_cache 
                    GROUP BY ticker 
                    ORDER BY updated_at DESC 
                    LIMIT 10
                ''')
                recent_activity = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            app_logger.error(f"Error getting recent activity: {e}")
        
        return jsonify({
            'success': True,
            'cache_stats': stats,
            'recent_activity': recent_activity,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app_logger.error(f"Error getting cache status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/clear/<ticker>')
def clear_cache_for_ticker(ticker):
    """Clear cache for a specific ticker"""
    try:
        from historical_cache import historical_cache
        
        success = historical_cache.clear_cache(ticker)
        
        if success:
            app_logger.info(f"🗑️ Cleared cache for {ticker}")
            return jsonify({
                'success': True,
                'message': f'Cache cleared for {ticker}',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to clear cache for {ticker}'
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error clearing cache for {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/clear')
def clear_all_cache():
    """Clear all historical data cache"""
    try:
        from historical_cache import historical_cache
        
        success = historical_cache.clear_cache()
        
        if success:
            app_logger.info("🗑️ Cleared all historical data cache")
            return jsonify({
                'success': True,
                'message': 'All cache cleared',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clear cache'
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error clearing all cache: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_stocks():
    """Analyze stocks with technical indicators"""
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({
                'success': False,
                'error': 'No tickers provided'
            }), 400
        
        analysis = []
        for ticker in tickers:
            analysis.append({
                'ticker': ticker,
                'recommendation': random.choice(['buy', 'sell', 'hold']),
                'confidence': random.uniform(0.6, 0.95),
                'price_target': round(random.uniform(100, 500), 2),
                'risk_level': random.choice(['low', 'medium', 'high']),
                'analysis': f"Technical analysis for {ticker} shows {random.choice(['bullish', 'bearish', 'neutral'])} signals."
            })
        
        return jsonify({
            'success': True,
            'data': analysis,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



# Bot-related endpoints
@app.route('/api/bot/status')
def get_bot_status():
    """Get bot status"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        status = trading_bot.get_status()
        broker = _get_broker()
        return jsonify({
            'success': True,
            'data': status,
            'broker': broker.to_dict() if broker else None,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting bot status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    try:
        if not BOT_AVAILABLE:
            pass  # app_logger.warning("start_bot called but BOT_AVAILABLE=False (DAS_ENABLED may be False or bot import failed)")
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503

        app_logger.info("start_bot: calling trading_bot.start()...")
        broker = _get_broker()
        trading_bot.set_broker(broker)
        success = trading_bot.start()
        if success:
            msg = (f'Bot started via {broker.name}' if broker
                   else 'Bot started via DAS Trader')
            return jsonify({
                'success': True,
                'message': msg,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': ('Failed to start bot: could not connect to broker or DAS Trader. '
                          'Check your broker credentials or ensure DAS Trader is running.'),
                'details': 'Configure a broker in the Account → Broker Connection tab, or ensure DAS Trader is running.'
            }), 500
    except Exception as e:
        app_logger.error(f"Error starting bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        success = trading_bot.stop()
        if success:
            return jsonify({
                'success': True,
                'message': 'Bot stopped successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to stop bot'
            }), 500
    except Exception as e:
        app_logger.error(f"Error stopping bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/update-strategies', methods=['POST'])
def update_strategies():
    """Update day bot strategies"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bot not available'}), 503

        data = request.get_json()
        success = trading_bot.update_strategies(data)
        if success:
            return jsonify({'success': True, 'message': 'Strategies updated successfully', 'timestamp': datetime.now().isoformat()})
        return jsonify({'success': False, 'error': 'Failed to update strategies'}), 500
    except Exception as e:
        app_logger.error(f"Error updating strategies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/swing-bot/config', methods=['GET'])
def get_swing_bot_config():
    """Return current swing bot config."""
    try:
        cfg = db_manager.get_swing_bot_config()
        return jsonify({'success': True, 'data': cfg, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error fetching swing config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/swing-bot/update-config', methods=['POST'])
def update_swing_bot_config():
    """Update swing bot config and apply to running bot."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Persist to DB
        ok, msg = db_manager.update_swing_bot_config(data)
        if not ok:
            return jsonify({'success': False, 'error': msg}), 500

        # Apply to live bot if running
        if BOT_AVAILABLE:
            trading_bot.update_swing_strategies(data)

        return jsonify({'success': True, 'message': 'Swing config updated', 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error updating swing config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ── BrownBot core logic ────────────────────────────────────────────────────

def _get_intraday_bars(symbol):
    """
    Fetch 1-min bars from 09:30 ET to now for a symbol.
    Uses Alpaca Data API directly via HTTP — no broker connection required.
    Falls back to the broker SDK if direct HTTP fails.
    Returns list of {o, h, l, c, v, vw} dicts, or [] if unavailable.
    """
    import requests as _req
    import pytz as _pytz
    _et = _pytz.timezone('US/Eastern')
    now_et = datetime.now(_et)
    start_et = now_et.replace(hour=9, minute=30, second=0, microsecond=0)

    ak = os.environ.get('ALPACA_API_KEY', '')
    as_ = os.environ.get('ALPACA_API_SECRET', '')

    # Primary: direct HTTP — works even when broker is not connected.
    # Try SIP feed first (paid plan); fall back to IEX (free plan) on 403.
    if ak and as_:
        for feed in ('sip', 'iex'):
            try:
                resp = _req.get(
                    f'https://data.alpaca.markets/v2/stocks/{symbol.upper()}/bars',
                    headers={'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': as_},
                    params={
                        'timeframe':  '1Min',
                        'start':      start_et.isoformat(),
                        'end':        now_et.isoformat(),
                        'limit':      1000,
                        'adjustment': 'raw',
                        'feed':       feed,
                    },
                    timeout=10,
                )
                if resp.status_code == 403:
                    app_logger.debug(f'Alpaca bars {symbol}: {feed} feed not on plan, trying fallback')
                    continue
                if resp.status_code != 200:
                    app_logger.warning(f'Alpaca bars {symbol} ({feed}): HTTP {resp.status_code} — {resp.text[:200]}')
                    break
                raw = resp.json().get('bars') or []
                if raw:
                    return [{'o': float(b['o']), 'h': float(b['h']),
                             'l': float(b['l']), 'c': float(b['c']),
                             'v': float(b['v']), 'vw': b.get('vw')}
                            for b in raw]
                app_logger.debug(f'Alpaca bars {symbol} ({feed}): 200 OK but empty bars')
                break
            except Exception as e:
                app_logger.warning(f'Alpaca intraday bars {symbol} ({feed}): {e}')
                break

    # Fallback: broker SDK data client
    broker = _get_broker()
    if broker and hasattr(broker, '_data_client') and broker._data_client:
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            req = StockBarsRequest(
                symbol_or_symbols=symbol.upper(),
                timeframe=TimeFrame.Minute,
                start=start_et,
                end=now_et,
            )
            data = broker._data_client.get_stock_bars(req)
            bars = data.get(symbol.upper(), [])
            if bars:
                return [{'o': float(b.open), 'h': float(b.high),
                         'l': float(b.low),  'c': float(b.close), 'v': float(b.volume),
                         'vw': float(b.vwap) if b.vwap else None}
                        for b in bars]
        except Exception as e:
            app_logger.debug(f'Alpaca intraday bars SDK {symbol}: {e}')

    return []


def _check_day_entry_signal(symbol, current_price, gap_price, config):
    """
    Intraday trend checks for day trade entries.
    Returns (enter: bool, checks: list[dict], reason: str).
    Each check dict: {name, label, passed, detail}
    If no checks are enabled, always returns (True, [], 'No trend filters enabled').
    """
    vwap_on   = bool(config.get('day_check_vwap', False))
    candle_on = bool(config.get('day_check_candle', False))
    ext_pct   = float(config.get('day_max_extension_pct', 0.0))
    vol_on    = bool(config.get('day_check_volume_surge', False))

    if not (vwap_on or candle_on or ext_pct > 0 or vol_on):
        return True, [], 'No trend filters enabled'

    bars = _get_intraday_bars(symbol)
    checks = []
    all_pass = True

    # ── VWAP (session VWAP from 09:30) ──────────────────────────────────
    vwap = None
    if bars:
        # Use Alpaca's per-bar vw (bar VWAP) when available; fall back to (h+l+c)/3
        tp_vol  = sum((b.get('vw') or (b['h'] + b['l'] + b['c']) / 3) * b['v'] for b in bars)
        total_v = sum(b['v'] for b in bars)
        vwap    = round(tp_vol / total_v, 2) if total_v > 0 else None

    if vwap_on:
        if vwap is None:
            passed, detail, value = False, 'No bar data for VWAP', '—'
        else:
            passed = float(current_price) > vwap
            detail = f'${float(current_price):.2f} {">" if passed else "≤"} VWAP ${vwap:.2f}'
            value  = f'${vwap:.2f}'
        checks.append({'name': 'vwap', 'label': 'Above VWAP', 'passed': passed,
                       'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    # ── Last 1-min candle direction ──────────────────────────────────────
    if candle_on:
        if not bars:
            passed, detail, value = False, 'No bar data', '—'
        else:
            last      = bars[-1]
            passed    = last['c'] >= last['o']
            direction = 'green' if passed else 'red'
            detail    = f'O:${last["o"]:.2f} C:${last["c"]:.2f} — {"bullish" if passed else "bearish"}'
            value     = direction
        checks.append({'name': 'candle', 'label': 'Bullish candle', 'passed': passed,
                       'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    # ── Extension from gap price ─────────────────────────────────────────
    if ext_pct > 0:
        if not gap_price:
            passed, detail, value = True, 'No gap price reference', '—'
        else:
            ext    = round((float(current_price) - float(gap_price)) / float(gap_price) * 100, 1)
            passed = ext <= ext_pct
            detail = f'+{ext:.1f}% from gap (max +{ext_pct:.1f}%)'
            value  = f'+{ext:.1f}%'
        checks.append({'name': 'extension', 'label': f'Not over-extended (≤{ext_pct:.0f}%)',
                       'passed': passed, 'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    # ── Volume surge on latest bar ───────────────────────────────────────
    if vol_on:
        if len(bars) < 3:
            passed, detail, value = False, 'Not enough bars', '—'
        else:
            vols     = [b['v'] for b in bars]
            avg_v    = sum(vols[:-1]) / (len(vols) - 1)
            latest_v = vols[-1]
            passed   = avg_v > 0 and latest_v >= avg_v * 1.5
            ratio    = (latest_v / avg_v) if avg_v > 0 else 0
            detail   = f'{latest_v:,.0f} vs avg {avg_v:,.0f} ({ratio:.1f}×)'
            value    = f'{ratio:.1f}×'
        checks.append({'name': 'vol_surge', 'label': 'Volume surge (≥1.5×)', 'passed': passed,
                       'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    parts = [f'{"✓" if c["passed"] else "✗"} {c["label"]}: {c["detail"]}' for c in checks]
    return all_pass, checks, ' | '.join(parts)



def _compute_stats_from_rows(rows: list, min_gap: float = 5.0) -> dict:
    """Python equivalent of the frontend buildHistoricalStats() — builds aggregate stats from raw gap-up rows."""
    data = [r for r in rows if (r.get('gap up % at open') or 0) >= min_gap]
    total = len(data)
    if not total:
        return {'totalDays': 0, 'period': f'5yr', 'minGap': min_gap}

    runner_days  = sum(1 for d in data if d.get('Runner/Fader') == 'Runner')
    fader_days   = sum(1 for d in data if d.get('Runner/Fader') == 'Fader')
    neutral_days = total - runner_days - fader_days

    def _avg(key):
        vals = [float(d[key]) for d in data if d.get(key) not in (None, '')]
        return round(sum(vals) / len(vals), 2) if vals else 0

    # Most common day-high time
    time_counts = {}
    for d in data:
        t = d.get('day high time')
        if t:
            time_counts[t] = time_counts.get(t, 0) + 1
    common_high_time = max(time_counts, key=time_counts.get) if time_counts else 'N/A'

    # Gap size distribution
    gap_dist = {'5-15%': 0, '15-30%': 0, '30-50%': 0, '50%+': 0}
    for d in data:
        g = float(d.get('gap up % at open') or 0)
        if   g >= 50: gap_dist['50%+']  += 1
        elif g >= 30: gap_dist['30-50%'] += 1
        elif g >= 15: gap_dist['15-30%'] += 1
        else:         gap_dist['5-15%']  += 1

    # Recent 30-day runner rate
    from datetime import datetime as _dt2
    cutoff = (_dt2.now().date() - __import__('datetime').timedelta(days=30)).isoformat()
    recent = [d for d in data if str(d.get('date', '')) >= cutoff]
    recent30_runner_pct = (
        round(sum(1 for d in recent if d.get('Runner/Fader') == 'Runner') / len(recent) * 100)
        if recent else 0
    )

    # High-volume runner rate (top 50% by premarket volume)
    sorted_by_vol = sorted(data, key=lambda d: float(d.get('premarket volume') or 0), reverse=True)
    top_half = sorted_by_vol[:max(1, total // 2)]
    high_vol_runner_pct = round(
        sum(1 for d in top_half if d.get('Runner/Fader') == 'Runner') / len(top_half) * 100
    )

    return {
        'totalDays':        total,
        'runnerDays':       runner_days,
        'faderDays':        fader_days,
        'neutralDays':      neutral_days,
        'runnerPct':        round(runner_days  / total * 100) if total else 0,
        'faderPct':         round(fader_days   / total * 100) if total else 0,
        'neutralPct':       round(neutral_days / total * 100) if total else 0,
        'avgGap':           _avg('gap up % at open'),
        'avgDayHigh':       _avg('day high %'),
        'avgClose':         _avg('closing percent'),
        'avgPremarketVol':  round(_avg('premarket volume') / 1_000_000, 2),
        'commonHighTime':   common_high_time,
        'gapDistribution':  gap_dist,
        'recent30RunnerPct': recent30_runner_pct,
        'highVolRunnerPct': high_vol_runner_pct,
        'period':           '5yr',
        'minGap':           min_gap,
    }


def _parse_playbook_pcts(playbook: dict):
    """
    Extract (stop_pct, target_pct) floats from the playbook string fields.
    Returns (None, None) when neither can be parsed.
    """
    import re as _re

    def _first_float(s):
        m = _re.search(r'(\d+(?:\.\d+)?)', str(s or ''))
        return float(m.group(1)) if m else None

    stop_pct   = _first_float((playbook.get('stop')   or {}).get('pct_from_entry', ''))
    target_pct = _first_float((playbook.get('exit')   or {}).get('primary_target', ''))
    # Fallback to setup_card if the structured fields don't parse
    if not stop_pct and not target_pct:
        card = playbook.get('setup_card') or {}
        stop_pct   = _first_float(card.get('stop', ''))
        target_pct = _first_float(card.get('target_1', ''))
    return stop_pct, target_pct


def _fetch_and_cache_playbook(symbol: str, sector_info: dict, sector_perf: dict, user_id: int = 0):
    """
    Background thread: fetch 5-year gap-up history and run GapUpTradeAgent for a symbol.
    Result is stored in sess.playbook_cache[symbol]; pending/failed sets updated on exit.
    """
    sess = _get_brown_session(user_id)
    playbook_cache   = sess.playbook_cache   if sess else {}
    playbook_pending = sess.playbook_pending if sess else set()
    playbook_failed  = sess.playbook_failed  if sess else set()
    try:
        from historical_data import get_historical_gap_up_data
        _add_brown_log('info', f'[Playbook] Fetching 5yr history for {symbol}…', user_id)
        rows = get_historical_gap_up_data(symbol, days=1825, use_cache=True, min_gap_percent=5) or []
        if not rows:
            _add_brown_log('warning', f'[Playbook] No historical data for {symbol} — using config defaults', user_id)
            playbook_failed.add(symbol)
            return
        stats    = _compute_stats_from_rows(rows, min_gap=5.0)
        playbook = _gap_up_agent.analyze(symbol, rows, stats, sector_info, sector_perf)
        playbook_cache[symbol] = playbook
        bias = playbook.get('bias', '?')
        conf = playbook.get('bias_confidence', '?')
        stp, tgt = _parse_playbook_pcts(playbook)
        _add_brown_log('info',
            f'[Playbook] {symbol} ready — bias={bias}/{conf} '
            f'stop={stp}% target={tgt}% '
            f'({stats["totalDays"]} gap-up days analyzed)', user_id=user_id)
    except Exception as _e:
        _add_brown_log('warning', f'[Playbook] {symbol} fetch failed: {_e} — will use config defaults', user_id)
        app_logger.warning(f'Playbook fetch failed for {symbol}: {_e}', exc_info=True)
        playbook_failed.add(symbol)
    finally:
        playbook_pending.discard(symbol)


def _brown_enter_position(user_id: int, symbol, position_type, config, approx_price, playbook_override=None):
    """Place a BUY order for BrownBot and record the position in memory."""
    sess = _get_brown_session(user_id)
    if not sess:
        return
    active_positions = sess.active_positions
    lock             = sess.lock
    entry_counts     = sess.entry_counts
    attempted_symbols = sess.attempted_symbols
    pending_orders   = sess.pending_orders
    broker           = sess.broker
    stats            = sess.stats

    price = float(approx_price or 0)
    _add_brown_log('info', f'{symbol}: entry started — approx ${price:.2f}, type={position_type}', user_id)
    pct_key = 'day_position_pct' if position_type == 'day' else 'swing_position_pct'
    position_pct = float(config.get(pct_key, 5.0 if position_type == 'day' else 3.0))

    # Hard safety cap: no single trade can exceed 10% (day) / 20% (swing) of equity,
    # regardless of what the config says — guards against accidental large values.
    MAX_PCT = 10.0 if position_type == 'day' else 20.0
    if position_pct > MAX_PCT:
        _add_brown_log('warning',
            f'{symbol}: {pct_key} {position_pct:.1f}% exceeds safety cap {MAX_PCT:.0f}% '
            f'— capped. Check your BrownBot config.', user_id=user_id)
        position_pct = MAX_PCT

    if not broker:
        _add_brown_log('error', f'SKIP {symbol}: no broker available', user_id)
        return

    # If approx_price is 0 or missing, try a direct Alpaca quote before giving up.
    if price <= 0:
        try:
            import requests as _req
            _ak = os.environ.get('ALPACA_API_KEY', '')
            _as = os.environ.get('ALPACA_API_SECRET', '')
            if _ak and _as:
                _snap = _req.get(
                    f'https://data.alpaca.markets/v2/stocks/snapshots',
                    headers={'APCA-API-KEY-ID': _ak, 'APCA-API-SECRET-KEY': _as},
                    params={'symbols': symbol, 'feed': 'sip'},
                    timeout=5,
                ).json()
                _p = (_snap.get(symbol) or {}).get('latestTrade', {}).get('p')
                if _p:
                    price = float(_p)
        except Exception:
            pass
        if price <= 0:
            # Transient price failure — do NOT mark attempted so the next scan can retry.
            _add_brown_log('warning',
                f'SKIP {symbol}: could not determine current price — will retry next scan', user_id=user_id)
            return

    # Fetch account equity to size the position and check buying power.
    # BP is checked BEFORE marking attempted — it's a transient condition that
    # restores as positions close intraday, so insufficient-BP should not block
    # the symbol for the full session.
    try:
        acct = broker.get_account()
        if acct.equity > 0:
            dollar_size = acct.equity * (position_pct / 100.0)
            quantity    = max(1, int(dollar_size / price))
            required    = price * quantity
            _add_brown_log('info',
                f'{symbol}: sizing {position_pct:.1f}% of ${acct.equity:,.0f} equity '
                f'= ${dollar_size:,.0f} → {quantity} shares @ ${price:.2f}', user_id=user_id)
            if acct.buying_power < required:
                _add_brown_log('warning',
                    f'SKIP {symbol}: insufficient buying power '
                    f'(need ${required:,.0f}, have ${acct.buying_power:,.0f}) '
                    f'— will retry when BP frees up', user_id=user_id)
                return  # NOT added to attempted — will retry on next scan
        else:
            _add_brown_log('warning', f'{symbol}: equity is 0 — using fallback 1 share', user_id)
            quantity = 1
    except Exception as _bp_err:
        _brown_debug(user_id, f'{symbol}: account fetch failed — {_bp_err}')
        quantity = max(1, int(dollar_size / price)) if 'dollar_size' in dir() else 1
        _add_brown_log('warning', f'{symbol}: account fetch failed — fallback {quantity} shares', user_id)

    # Mark as attempted now that BP is confirmed and we are about to place an order.
    # Fills, broker rejections, and order errors all lock the symbol for this session.
    # Transient failures (price unavailable, insufficient BP) return early above.
    attempted_symbols.add(symbol)

    try:
        from bot.broker.base import OrderSide, OrderType as OType
        order = broker.place_order(
            symbol     = symbol,
            side       = OrderSide.BUY,
            qty        = float(quantity),
            order_type = OType.MARKET,
        )
        order_id = order.order_id
        app_logger.info(f'[BrownBot:{broker.name}] BUY {quantity} {symbol} → order_id={order_id} status={order.status}')
    except Exception as _order_err:
        _add_brown_log('error', f'Order rejected for {symbol}: {_order_err}', user_id)
        return

    # Check immediately for fast fill or outright rejection.
    # If still pending, the monitor thread will confirm the fill and write to DB.
    _entry_confirmed = False
    if order_id:
        try:
            from bot.broker.base import OrderStatus as _OStatus
            _filled = broker.get_order(str(order_id))
            app_logger.debug(
                f'[BrownBot entry] immediate status check {symbol} '
                f'order={str(order_id)[:8]}… status={_filled.status} '
                f'filled_avg_price={_filled.filled_avg_price} filled_qty={_filled.filled_qty}')
            if _filled.status in (_OStatus.CANCELLED, _OStatus.REJECTED):
                _add_brown_log('error',
                    f'{symbol} order {str(order_id)[:8]}… rejected immediately — not entering', user_id=user_id)
                return
            if _filled.filled_avg_price:
                _fill_price = float(_filled.filled_avg_price)
                _fill_qty   = int(_filled.filled_qty or quantity)
                if _fill_price != price:
                    _add_brown_log('info',
                        f'{symbol} fill confirmed ${_fill_price:.2f} '
                        f'(scanner approx was ${price:.2f})', user_id=user_id)
                price    = _fill_price
                quantity = _fill_qty
                _entry_confirmed = True
            else:
                app_logger.debug(
                    f'[BrownBot entry] {symbol} order {str(order_id)[:8]}… '
                    f'not yet filled — deferring to monitor loop')
        except Exception as _fe:
            app_logger.debug(f'BrownBot fill check {symbol}: {_fe}')

    if position_type == 'day':
        cfg_tgt = float(config.get('day_profit_target_pct', 5.0))
        cfg_stp = float(config.get('day_stop_loss_pct', 2.5))
    else:
        cfg_tgt = float(config.get('swing_profit_target_pct', 15.0))
        cfg_stp = float(config.get('swing_stop_loss_pct', 7.0))

    # Apply playbook stop/target with safety bounds so we never chase a tiny
    # target or risk more than 1.5× the configured stop.
    playbook_bias = None
    playbook_summary = None
    tgt_src = stp_src = 'config'
    if playbook_override:
        playbook_bias    = playbook_override.get('bias')
        playbook_summary = playbook_override.get('summary')
        pb_stp, pb_tgt  = _parse_playbook_pcts(playbook_override)
        if pb_tgt is not None:
            tgt_pct = max(pb_tgt, cfg_tgt * 0.5)
            tgt_src = 'playbook'
        else:
            tgt_pct = cfg_tgt
        if pb_stp is not None:
            stp_pct = min(pb_stp, cfg_stp * 1.5)
            stp_src = 'playbook'
        else:
            stp_pct = cfg_stp
    else:
        tgt_pct = cfg_tgt
        stp_pct = cfg_stp

    profit_target = round(price * (1 + tgt_pct / 100), 2) if price else None
    stop_loss = round(price * (1 - stp_pct / 100), 2) if price else None
    position_id = f"BROWN_{symbol}_{int(time.time())}"

    _trade_date = _last_trading_date()
    position = {
        'position_id':         position_id,
        'symbol':              symbol,
        'position_type':       position_type,
        'entry_price':         price,
        'avg_entry_price':     price if _entry_confirmed else None,
        'quantity':            quantity,
        'profit_target':       profit_target,
        'profit_target_pct':   tgt_pct,
        'stop_loss':           stop_loss,
        'stop_loss_pct':       stp_pct,
        'entry_time':          datetime.now().isoformat(),
        'entry_time_epoch':    time.time(),
        'unrealized_pnl':      0.0,
        'unrealized_pnl_pct':  0.0,
        'entry_order_id':      str(order_id) if order_id else None,
        'trade_date':          _trade_date,
        'status':              'open',
        'playbook_bias':       playbook_bias,
        'playbook_stop_pct':   stp_pct if playbook_override else None,
        'playbook_target_pct': tgt_pct if playbook_override else None,
        'playbook_summary':    playbook_summary,
    }
    with lock:
        active_positions[position_id] = position

    app_logger.debug(
        f'[BrownBot entry] {symbol} position_id={position_id} '
        f'entry_confirmed={_entry_confirmed} avg_entry_price={position.get("avg_entry_price")} '
        f'target={position.get("profit_target")} stop={position.get("stop_loss")} '
        f'order_id={str(order_id)[:8] if order_id else None}…')

    # Persist position to DB so it survives a server restart
    try:
        db_manager.save_brown_position(position_id, position, user_id=user_id)
        app_logger.debug(f'[BrownBot entry] {symbol} position saved to DB (status=open)')
    except Exception as _e:
        _add_brown_log('warning', f'DB position save failed for {symbol}: {_e}', user_id)

    # Log the order to the immutable orders table
    if order_id:
        _order_status_str = 'filled' if _entry_confirmed else 'pending'
        try:
            db_manager.add_brown_order({
                'order_id':       str(order_id),
                'position_id':    position_id,
                'symbol':         symbol,
                'side':           'B',
                'order_type':     'entry',
                'position_type':  position_type,
                'submitted_qty':  quantity,
                'submitted_price': price,
                'status':         _order_status_str,
                'submitted_at':   datetime.now().isoformat(),
                'trade_date':     _trade_date,
            }, user_id=user_id)
            app_logger.debug(
                f'[BrownBot entry] {symbol} brown_orders row written '
                f'order={str(order_id)[:8]}… status={_order_status_str}')
            if _entry_confirmed:
                db_manager.update_brown_order_fill(str(order_id), price, quantity)
                db_manager.update_brown_position_entry(position_id, price, quantity)
                app_logger.debug(
                    f'[BrownBot entry] {symbol} fast-path: '
                    f'update_brown_order_fill + update_brown_position_entry done '
                    f'fill_price={price} fill_qty={quantity}')
        except Exception as _e:
            _add_brown_log('warning', f'DB order log failed for {symbol}: {_e}', user_id)

    if not _entry_confirmed and order_id:
        _add_brown_log('info',
            f'{symbol} BUY submitted order={str(order_id)[:8]}… — '
            f'waiting for broker fill confirmation', user_id=user_id)

    # Write BUY trade to DB only after broker confirms the fill.
    if _entry_confirmed:
        # Fast path: fill already confirmed above — write immediately.
        try:
            db_manager.add_trade({
                'trade_id':      f'BROWN_ENTRY_{symbol}_{order_id}',
                'symbol':        symbol,
                'side':          'B',
                'quantity':      quantity,
                'price':         price,
                'route':         'SMAT',
                'trade_time':    datetime.now().isoformat(),
                'order_id':      str(order_id) if order_id else None,
                'liquidity':     None,
                'ecn_fee':       0.0,
                'pnl':           0.0,
                'trade_date':    _trade_date,
                'position_type': position_type,
                'days_held':     None,
                'source':        'brownbot',
                'broker':        broker.name if broker else None,
                'user_id':       user_id,
            })
        except Exception as _e:
            _add_brown_log('warning', f'DB entry write failed for {symbol}: {_e}', user_id)
    elif order_id:
        # Slow path: order still pending — monitor thread will write DB on confirmed fill.
        with lock:
            pending_orders[str(order_id)] = {
                'type':          'entry',
                'symbol':        symbol,
                'position_id':   position_id,
                'order_id':      str(order_id),
                'submitted_at':  time.time(),
                'approx_price':  price,
                'quantity':      quantity,
                'position_type': position_type,
            }
        _add_brown_log('info', f'{symbol} BUY pending broker confirmation — DB write deferred', user_id)

    # Count only actual fills — not rejected/skipped attempts
    entry_counts[symbol] = entry_counts.get(symbol, 0) + 1
    entry_num = entry_counts[symbol]
    times_str = f'#{entry_num}' if entry_num == 1 else f'#{entry_num} (re-entry ×{entry_num - 1})'
    position['entry_num'] = entry_num

    _add_brown_log(
        'info',
        f"ENTERED {position_type.upper()} {symbol} {times_str} ~${price:.2f} | "
        f"target ${profit_target} (+{tgt_pct}%, {tgt_src}) | stop ${stop_loss} (-{stp_pct}%, {stp_src})"
        + (f' | playbook bias={playbook_bias}' if playbook_bias else ''),
        user_id)


# Swing scanner caches are now per-session (BrownSession.swing_candidates_cache / swing_ai_picks_cache)


def _fetch_swing_universe(config, user_id: int = 0):
    """
    Return (symbols: list[str], meta: dict) from Alpaca most-actives + movers.
    meta[symbol] = {'volume': int, 'price': float, 'chg_pct': float,
                    'high': float, 'low': float, 'close': float, 'prev_close': float}
    """
    import requests as _req
    ak  = os.environ.get('ALPACA_API_KEY', '')
    aks = os.environ.get('ALPACA_API_SECRET', '')
    if not (ak and aks):
        _add_brown_log('warning', 'Swing scanner: ALPACA_API_KEY/SECRET not set', user_id=user_id)
        return [], {}

    headers  = {'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': aks}
    top_n    = int(config.get('swing_scan_top_n', 30))
    source   = config.get('swing_scan_source', 'both')
    meta     = {}

    if source in ('actives', 'both'):
        try:
            resp = _req.get(
                'https://data.alpaca.markets/v1beta1/screener/stocks/most-actives',
                headers=headers,
                params={'by': 'volume', 'top': top_n},
                timeout=10,
            ).json()
            for item in (resp.get('most_actives') or []):
                sym = (item.get('symbol') or '').upper()
                if not sym:
                    continue
                prev = float(item.get('prev_close') or 0)
                close = float(item.get('close') or 0)
                meta[sym] = {
                    'volume':     int(item.get('volume') or 0),
                    'price':      close or float(item.get('open') or 0),
                    'chg_pct':    round((close - prev) / prev * 100, 2) if prev > 0 else 0.0,
                    'high':       float(item.get('high') or 0),
                    'low':        float(item.get('low') or 0),
                    'close':      close,
                    'prev_close': prev,
                }
        except Exception as e:
            app_logger.warning(f'Swing scanner: most-actives fetch failed: {e}')

    if source in ('gainers', 'both'):
        try:
            # Use top=50 (Alpaca API max) to capture the broadest % gainers universe.
            resp = _req.get(
                'https://data.alpaca.markets/v1beta1/screener/stocks/movers',
                headers=headers,
                params={'market_type': 'stocks', 'top': 50},
                timeout=10,
            ).json()
            for item in (resp.get('gainers') or []):
                sym = (item.get('symbol') or '').upper()
                if not sym:
                    continue
                m = meta.setdefault(sym, {})
                m['price']   = m.get('price') or float(item.get('price') or 0)
                m['chg_pct'] = float(item.get('percent_change') or m.get('chg_pct') or 0)
                m['volume']  = m.get('volume') or int(item.get('volume') or 0)
        except Exception as e:
            app_logger.warning(f'Swing scanner: movers fetch failed: {e}')

    return list(meta.keys()), meta


def _fetch_swing_daily_bars(symbols, days=30):
    """
    Fetch daily OHLCV bars for up to 100 symbols at a time from Alpaca.
    Returns {SYMBOL: [bar_dicts]} where bar_dict has keys o, h, l, c, v, t.
    """
    if not symbols:
        return {}
    import requests as _req
    ak  = os.environ.get('ALPACA_API_KEY', '')
    aks = os.environ.get('ALPACA_API_SECRET', '')
    if not (ak and aks):
        return {}

    import datetime as _dt_mod
    headers = {'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': aks}
    start   = (_dt_mod.datetime.now(_dt_mod.timezone.utc) - _dt_mod.timedelta(days=days + 5)).strftime('%Y-%m-%d')
    result  = {}

    for i in range(0, len(symbols), 100):
        batch = symbols[i:i + 100]
        try:
            resp = _req.get(
                'https://data.alpaca.markets/v2/stocks/bars',
                headers=headers,
                params={
                    'symbols':    ','.join(batch),
                    'timeframe':  '1Day',
                    'start':      start,
                    'limit':      1000,
                    'feed':       'sip',
                    'adjustment': 'split',
                },
                timeout=15,
            ).json()
            for sym, bars in (resp.get('bars') or {}).items():
                if bars:
                    result[sym.upper()] = bars
        except Exception as e:
            app_logger.warning(f'Swing scanner: daily bars batch {i//100+1} failed: {e}')

    return result


def _compute_sma(closes, period):
    """SMA of the last `period` closes. Returns None if insufficient data."""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _compute_rsi(closes, period=14):
    """Wilder RSI from a list of closes. Returns None if insufficient data."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 1)


def _check_swing_entry_signal(symbol, tech, config):
    """
    Optional technical signal checks for swing candidates.
    Returns (enter: bool, checks: list[dict], reason: str).
    All checks are off by default; any enabled check must pass.
    tech keys: price, sma9, sma20, rsi, rel_vol
    """
    above_sma20_on = bool(config.get('swing_check_above_sma20', False))
    ma_cross_on    = bool(config.get('swing_check_ma_cross', False))
    rsi_range_on   = bool(config.get('swing_check_rsi_range', False))
    rel_vol_on     = bool(config.get('swing_check_rel_vol', False))

    if not (above_sma20_on or ma_cross_on or rsi_range_on or rel_vol_on):
        return True, [], 'No swing signals enabled'

    price   = float(tech.get('price') or 0)
    sma9    = tech.get('sma9')
    sma20   = tech.get('sma20')
    rsi     = tech.get('rsi')
    rel_vol = tech.get('rel_vol')
    checks  = []
    all_pass = True

    if above_sma20_on:
        if sma20 is None:
            passed, detail, value = False, 'SMA20 unavailable (need 20+ daily bars)', '—'
        else:
            passed = price > sma20
            detail = f'${price:.2f} {">" if passed else "≤"} SMA20 ${sma20:.2f}'
            value  = f'${sma20:.2f}'
        checks.append({'name': 'above_sma20', 'label': 'Above SMA20',
                       'passed': passed, 'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    if ma_cross_on:
        if sma9 is None or sma20 is None:
            passed, detail, value = False, 'SMA data unavailable', '—'
        else:
            passed = sma9 > sma20
            spread = (sma9 - sma20) / sma20 * 100
            detail = f'SMA9 ${sma9:.2f} {">" if passed else "≤"} SMA20 ${sma20:.2f} ({spread:+.1f}%)'
            value  = f'{spread:+.1f}%'
        checks.append({'name': 'ma_cross', 'label': 'SMA9 > SMA20',
                       'passed': passed, 'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    if rsi_range_on:
        rsi_min = float(config.get('swing_rsi_min', 40.0))
        rsi_max = float(config.get('swing_rsi_max', 70.0))
        if rsi is None:
            passed, detail, value = False, 'RSI unavailable (need 15+ daily bars)', '—'
        else:
            passed = rsi_min <= rsi <= rsi_max
            detail = f'RSI {rsi:.1f} (range {rsi_min:.0f}–{rsi_max:.0f})'
            value  = f'{rsi:.1f}'
        checks.append({'name': 'rsi', 'label': f'RSI {rsi_min:.0f}–{rsi_max:.0f}',
                       'passed': passed, 'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    if rel_vol_on:
        rv_min = float(config.get('swing_rel_vol_min', 1.2))
        if rel_vol is None:
            passed, detail, value = False, 'RelVol unavailable', '—'
        else:
            passed = rel_vol >= rv_min
            detail = f'{rel_vol:.2f}× avg daily volume (min {rv_min:.1f}×)'
            value  = f'{rel_vol:.2f}×'
        checks.append({'name': 'rel_vol', 'label': f'RelVol ≥{rv_min:.1f}×',
                       'passed': passed, 'detail': detail, 'value': value})
        if not passed:
            all_pass = False

    parts = [f'{"✓" if c["passed"] else "✗"} {c["label"]}: {c["detail"]}' for c in checks]
    return all_pass, checks, ' | '.join(parts)


def _brown_scan_swing_candidates(config, user_id: int = 0):
    """
    Broad-market swing candidate scan: Alpaca most-actives + gainers →
    price/volume/market-cap/float filters → daily-bar technicals.
    Results are cached per-session for 5 minutes.
    Returns list of candidate dicts, each suitable for _check_swing_entry_signal
    and SwingPicksAgent.rank_candidates.
    """
    sess = _get_brown_session(user_id)
    swing_candidates_cache = sess.swing_candidates_cache if sess else {'ts': 0.0, 'candidates': []}

    now = time.time()
    if now - swing_candidates_cache.get('ts', 0) < 300:
        return swing_candidates_cache.get('candidates', [])

    _add_brown_log('info', 'Swing scanner: refreshing universe from Alpaca screener…', user_id)

    symbols_list, meta = _fetch_swing_universe(config, user_id=user_id)
    if not symbols_list:
        _add_brown_log('warning', 'Swing scanner: screener returned no symbols', user_id=user_id)
        if sess:
            sess.swing_candidates_cache = {'ts': now, 'candidates': []}
        return []

    _add_brown_log('info', f'Swing scanner: {len(symbols_list)} raw symbols from screener', user_id)

    # Pre-price filter: the Alpaca most-actives endpoint does NOT return OHLC data,
    # so many symbols will have price=0 in meta. Only exclude symbols whose price
    # is KNOWN (>0) and definitively out of range — the rest pass through so we can
    # fall back to the daily bar close and apply the real filter after bar fetch.
    min_price = float(config.get('swing_min_price', 5.0))
    max_price = float(config.get('swing_max_price', 500.0))
    price_ok  = [
        s for s in symbols_list
        if not (float(meta.get(s, {}).get('price') or 0) > 0
                and not (min_price <= float(meta.get(s, {}).get('price') or 0) <= max_price))
    ]
    if not price_ok:
        _add_brown_log('info', 'Swing scanner: no symbols passed pre-price filter', user_id)
        if sess:
            sess.swing_candidates_cache = {'ts': now, 'candidates': []}
        return []

    _add_brown_log('info',
        f'Swing scanner: {len(price_ok)} symbols after pre-price filter, '
        f'fetching 30-day daily bars…', user_id=user_id)

    bars_by_sym = _fetch_swing_daily_bars(price_ok, days=30)

    # Fundamentals from gap_up_detector enrichment cache
    try:
        from gap_up_detector import _fundamentals_cache as _funda_cache
    except Exception:
        _funda_cache = {}

    min_vol_k   = float(config.get('swing_min_avg_vol_k', 500.0))
    min_cap_m   = float(config.get('swing_min_market_cap_m', 200.0))
    max_cap_m   = float(config.get('swing_max_market_cap_m', 0.0))
    max_float_m = float(config.get('swing_max_float_m', 0.0))

    candidates = []
    skipped = {'no_bars': 0, 'volume': 0, 'market_cap': 0, 'float': 0}

    for sym in price_ok:
        bars = bars_by_sym.get(sym, [])
        if not bars:
            skipped['no_bars'] += 1
            continue

        closes  = [b['c'] for b in bars]
        volumes = [b['v'] for b in bars]

        # Average daily volume over last 20 days
        vol_window = volumes[-20:] if len(volumes) >= 20 else volumes
        avg_vol    = sum(vol_window) / len(vol_window) if vol_window else 0
        avg_vol_k  = avg_vol / 1_000

        if avg_vol_k < min_vol_k:
            skipped['volume'] += 1
            continue

        # Technicals
        sma9  = _compute_sma(closes, 9)
        sma20 = _compute_sma(closes, 20)
        rsi   = _compute_rsi(closes, 14)

        # Today's / most-recent bar
        last_bar   = bars[-1]
        prev_close = bars[-2]['c'] if len(bars) >= 2 else last_bar['c']

        # Prefer screener meta (intraday) for price; fall back to last bar close.
        # Apply real price filter here — most-actives symbols had no price in meta.
        m          = meta.get(sym, {})
        price      = float(m.get('price') or last_bar['c'])
        if not (min_price <= price <= max_price):
            continue
        today_high = float(m.get('high') or last_bar.get('h') or price)
        today_low  = float(m.get('low') or last_bar.get('l') or price)
        today_vol  = int(m.get('volume') or last_bar.get('v') or 0)
        chg_pct    = float(m.get('chg_pct') or
                           ((price - prev_close) / prev_close * 100 if prev_close else 0))
        day_range  = round((today_high - today_low) / today_low * 100, 2) if today_low else 0
        close_pos  = (
            round((price - today_low) / (today_high - today_low), 2)
            if today_high > today_low else 0.5
        )
        rel_vol    = round(today_vol / avg_vol, 2) if avg_vol > 0 and today_vol > 0 else None
        vol_m      = round(today_vol / 1_000_000, 2)

        # Fundamentals (may be empty for newly-listed or less-common tickers)
        funda      = _funda_cache.get(sym, {})
        cap_m      = (funda.get('market_cap') or 0) / 1_000_000
        float_m    = (funda.get('float_shares') or 0) / 1_000_000
        sector     = funda.get('sector', 'Unknown')

        if min_cap_m > 0 and cap_m > 0 and cap_m < min_cap_m:
            skipped['market_cap'] += 1
            continue
        if max_cap_m > 0 and cap_m > 0 and cap_m > max_cap_m:
            skipped['market_cap'] += 1
            continue
        if max_float_m > 0 and float_m > 0 and float_m > max_float_m:
            skipped['float'] += 1
            continue

        candidates.append({
            # SwingPicksAgent-compatible fields
            'ticker':     sym,
            'price':      round(price, 2),
            'chg_pct':    round(chg_pct, 2),
            'volume_m':   vol_m,
            'day_range':  day_range,
            'direction':  'up' if chg_pct >= 0 else 'down',
            'vol_ratio':  rel_vol,
            'market_cap_m': round(cap_m, 0) if cap_m else None,
            'sma10':      round(sma9, 2) if sma9 is not None else None,
            'close_pos':  close_pos,
            # Our signal-check fields
            'symbol':     sym,
            'sma9':       round(sma9, 2) if sma9 is not None else None,
            'sma20':      round(sma20, 2) if sma20 is not None else None,
            'rsi':        rsi,
            'rel_vol':    rel_vol,
            'avg_vol_k':  round(avg_vol_k, 1),
            'float_m':    round(float_m, 1) if float_m else None,
            'sector':     sector,
        })

    _add_brown_log('info',
        f'Swing scanner: {len(candidates)} candidates after all filters '
        f'(skipped no_bars={skipped["no_bars"]} vol={skipped["volume"]} '
        f'cap={skipped["market_cap"]} float={skipped["float"]})', user_id=user_id)

    if sess:
        sess.swing_candidates_cache = {'ts': now, 'candidates': candidates}
    return candidates


def _brown_rank_swing_ai(candidates, user_id: int = 0):
    """
    Run SwingPicksAgent.rank_candidates on `candidates` and return the
    AI-ranked picks list (grade A/B/C, bias Bullish/Bearish).
    Results are cached per-session for 15 minutes, or until candidate set changes.
    Falls back to treating all candidates as Grade B / Bullish if AI unavailable.
    """
    sess = _get_brown_session(user_id)
    swing_ai_picks_cache = sess.swing_ai_picks_cache if sess else {'ts': 0.0, 'picks': [], 'fingerprint': ''}

    fingerprint = ','.join(sorted(c['ticker'] for c in candidates))
    now = time.time()
    cached = swing_ai_picks_cache
    if (fingerprint == cached.get('fingerprint', '')
            and now - cached.get('ts', 0) < 900):
        return cached.get('picks', [])

    if not (AI_AGENT_AVAILABLE and _swing_agent):
        _add_brown_log('info',
            'Swing scanner: AI not available — treating all filtered candidates as approved', user_id=user_id)
        picks = [
            {'ticker': c['ticker'], 'grade': 'B', 'bias': 'Bullish',
             'reason': 'AI not configured', 'entry_zone': '', 'watch_for': '', 'risk': ''}
            for c in candidates
        ]
        if sess:
            sess.swing_ai_picks_cache = {'ts': now, 'picks': picks, 'fingerprint': fingerprint}
        try:
            db_manager.save_swing_screener_snapshot(_last_trading_date(), candidates, picks)
        except Exception as _ssh_err:
            app_logger.warning(f'BrownBot swing screener snapshot save failed (no-AI path): {_ssh_err}')
        return picks

    try:
        import pytz as _pytz
        _et    = _pytz.timezone('US/Eastern')
        now_et = datetime.now(_et)
        in_mkt = (now_et.weekday() < 5
                  and now_et.replace(hour=9, minute=30, second=0, microsecond=0)
                  <= now_et
                  <= now_et.replace(hour=16, minute=0, second=0, microsecond=0))
        session_key = _last_trading_date()

        _add_brown_log('info',
            f'Swing AI ranking {len(candidates)} candidates via SwingPicksAgent…', user_id=user_id)
        result = _swing_agent.rank_candidates(candidates, session_key, market_open=in_mkt)
        picks  = result.get('picks', [])
        market_note = result.get('market_note', '')
        if market_note:
            _add_brown_log('info', f'Swing AI market note: {market_note}', user_id)
        _add_brown_log('info',
            f'Swing AI ranked {len(picks)} picks — '
            f'grades: {", ".join(p.get("grade","?") + "/" + p.get("bias","?") for p in picks[:5])}…', user_id=user_id)
        if sess:
            sess.swing_ai_picks_cache = {'ts': now, 'picks': picks, 'fingerprint': fingerprint}
        # Save screener snapshot for Option-B backtest data collection (always — even
        # if picks is empty, candidates are worth recording for forward-return analysis).
        try:
            db_manager.save_swing_screener_snapshot(session_key, candidates, picks)
        except Exception as _ssh_err:
            app_logger.warning(f'BrownBot swing screener snapshot save failed: {_ssh_err}')

        # Only save when picks is non-empty — prevents overwriting good picks with an
        # empty result from a follow-up scan that excluded already-entered symbols.
        if picks:
            try:
                db_manager.save_swing_picks(session_key, picks, market_note,
                                            candidates_scanned=len(candidates))
            except Exception as _db_err:
                app_logger.warning(f'BrownBot swing picks DB save failed: {_db_err}')
            # Also update the in-memory daily picks cache so swing_daily_picks_latest
            # returns these picks immediately — without this, the stale cache entry
            # from the old Swing-tab pipeline would be served instead.
            _daily_picks_cache[session_key] = {
                'success': True, 'date': session_key,
                'picks': picks, 'market_note': market_note,
                'candidates_scanned': len(candidates),
                'source_counts': {}, 'sources_tickers': {},
            }
        return picks
    except Exception as e:
        app_logger.warning(f'BrownBot swing AI ranking failed: {e}', exc_info=True)
        _add_brown_log('warning', f'Swing AI ranking failed: {e} — skipping swing entries this cycle', user_id)
        return []


def _brown_bot_scan_and_enter(user_id: int):
    """One iteration of the BrownBot entry loop: scan, filter, gate, order."""
    sess = _get_brown_session(user_id)
    if not sess or not sess.running:
        return
    risk_manager     = sess.risk_manager
    active_positions = sess.active_positions
    attempted_symbols = sess.attempted_symbols

    import pytz as _pytz
    _et = _pytz.timezone('US/Eastern')
    now_et = datetime.now(_et)

    config = db_manager.get_brown_bot_config(user_id)

    # Rebuild RiskManager from fresh config each iteration so UI config changes
    # (slot caps, loss limit) take effect immediately without restarting the bot.
    if RISK_MANAGER_AVAILABLE:
        sess.risk_manager = RiskManager(config, user_id=user_id)
        risk_manager = sess.risk_manager

    # Use the live in-memory data kept current by the gap-up monitor loop.
    # Falls back to today's DB snapshot when the monitor hasn't populated yet.
    # Never drives a new Polygon API call from inside the BrownBot loop.
    raw_gaps = list(real_time_gap_ups)
    if not raw_gaps:
        try:
            _today_str = now_et.date().isoformat()
            raw_gaps = db_manager.get_gap_up_snapshot(_today_str) or []
            if raw_gaps:
                _add_brown_log('info', f'Scanner using DB snapshot ({len(raw_gaps)} stocks)', user_id)
        except Exception as e:
            _add_brown_log('warning', f'DB snapshot fallback failed: {e}', user_id)

    min_gap = float(config.get('min_gap_pct', 10.0))
    min_price = float(config.get('min_price', 5.0))
    max_price = float(config.get('max_price', 500.0))
    min_vol_m = float(config.get('min_volume_m', 0.5))
    float_val = float(config.get('max_float_m', 0.0))
    float_op  = config.get('float_operator', '<=')

    def _float_ok(s):
        if float_val <= 0:
            return True
        f = s.get('float_shares', 0) / 1_000_000
        if f == 0:
            return True  # no float data — don't exclude
        return f <= float_val if float_op == '<=' else f >= float_val

    scanner_hits = {
        s['ticker']: s for s in raw_gaps
        if s.get('gap_percent', 0) >= min_gap
        and min_price <= s.get('price', 0) <= max_price
        and s.get('volume', 0) / 1_000_000 >= min_vol_m
        and _float_ok(s)
    }

    # Log per-stock filter results so we can see exactly why each raw candidate passed or failed
    _add_brown_log('info',
        f'Scanner: {len(raw_gaps)} raw gaps → {len(scanner_hits)} passed filters '
        f'(gap≥{min_gap}%, price ${min_price:.0f}–${max_price:.0f}, vol≥{min_vol_m}M'
        + (f', float{float_op}{float_val}M' if float_val > 0 else '') + ')',
        user_id)
    for _s in raw_gaps:
        _t = _s.get('ticker', '?')
        if _t in scanner_hits:
            continue
        _reasons = []
        if _s.get('gap_percent', 0) < min_gap:
            _reasons.append(f'gap {_s.get("gap_percent", 0):.1f}% < {min_gap}%')
        _p = _s.get('price', 0)
        if not (min_price <= _p <= max_price):
            _reasons.append(f'price ${_p:.2f} outside ${min_price}–${max_price}')
        _vm = _s.get('volume', 0) / 1_000_000
        if _vm < min_vol_m:
            _reasons.append(f'vol {_vm:.2f}M < {min_vol_m}M')
        if not _float_ok(_s):
            _fm = _s.get('float_shares', 0) / 1_000_000
            _reasons.append(f'float {_fm:.1f}M failed {float_op}{float_val}M')
        _brown_debug(user_id, f'FILTER-OUT {_t}: {", ".join(_reasons) or "unknown"}')

    # Snapshot active state under lock
    with sess.lock:
        active_symbols = {p['symbol'] for p in active_positions.values()}
        active_copy = dict(active_positions)

    # Day time gate (configurable, default 09:35–10:30 ET)
    _gate_enabled = bool(config.get('day_time_gate_enabled', True))
    day_window_open = True
    _gate_str = 'disabled'
    if _gate_enabled:
        try:
            _gs = config.get('day_time_gate_start', '09:35').split(':')
            _ge = config.get('day_time_gate_end',   '10:30').split(':')
            day_open  = now_et.replace(hour=int(_gs[0]), minute=int(_gs[1]), second=0, microsecond=0)
            day_close = now_et.replace(hour=int(_ge[0]), minute=int(_ge[1]), second=0, microsecond=0)
            day_window_open = day_open <= now_et <= day_close
            _gate_str = f'{_gs[0]}:{_gs[1]}–{_ge[0]}:{_ge[1]} ET'
        except Exception:
            day_window_open = True  # parse error → don't block entries
            _gate_str = 'parse error → open'
    _add_brown_log('info',
        f'Day time gate: {"OPEN" if day_window_open else "CLOSED"} '
        f'(now {now_et.strftime("%H:%M")} ET, window {_gate_str})',
        user_id)

    # ── Hard market-hours guard (not user-configurable) ─────────────────────
    _mkt_open  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
    _mkt_close = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
    _in_market_hours = (_mkt_open <= now_et <= _mkt_close) and (now_et.weekday() < 5)
    if not _in_market_hours:
        _add_brown_log('info',
            f'Outside market hours ({now_et.strftime("%H:%M ET %A")}) — skipping day trade entries', user_id=user_id)

    # ── Process auto-scanned gap-up candidates (day trade) ──
    _day_trades_on = config.get('day_trades_enabled', True) and _in_market_hours
    if not config.get('day_trades_enabled', True):
        _add_brown_log('info', 'Day trades disabled — skipping day trade entries', user_id)
    for symbol, s in (scanner_hits.items() if _day_trades_on else []):
        if not sess.running:
            return
        if symbol in active_symbols:
            _add_brown_log('info', f'SKIP {symbol}: already in active positions', user_id)
            continue
        if symbol in attempted_symbols:
            continue  # already attempted this session (filled, rejected, or timed out)
        if symbol in sess.eod_flattened_symbols:
            _add_brown_log('info', f'SKIP {symbol}: EOD-flattened earlier today — no re-entry', user_id)
            continue
        if not day_window_open:
            _add_brown_log('info', f'SKIP {symbol}: outside day time gate ({now_et.strftime("%H:%M")} ET, window {_gate_str})', user_id)
            continue
        # Intraday trend signal check — use live broker quote for current price so
        # VWAP/extension checks aren't comparing against a stale gap-open price.
        # gap_price stays as the scanner price (the price at which the gap was detected).
        live_price = _brown_get_current_price(user_id, symbol) or s.get('price', 0)
        sig_ok, sig_checks, sig_reason = _check_day_entry_signal(
            symbol, live_price, s.get('price', 0), config)
        if not sig_ok:
            _add_brown_log('info', f'SKIP {symbol} [TREND] {sig_reason}', user_id)
            continue
        if sig_checks:
            _add_brown_log('info', f'Signal OK {symbol}: {sig_reason}', user_id)

        # Playbook gate — AI analysis of 5-yr gap history for this symbol.
        # Short/High-confidence bias means it historically gaps and reverses — skip.
        # If the playbook isn't ready yet, defer to the next scan cycle.
        playbook_override = None
        if config.get('day_ai_playbook', True) and AI_AGENT_AVAILABLE and _gap_up_agent:
            if symbol in sess.playbook_cache:
                pb       = sess.playbook_cache[symbol]
                pb_bias  = pb.get('bias', '')
                pb_conf  = pb.get('bias_confidence', '')
                if pb_bias == 'Short' and pb_conf == 'High':
                    _add_brown_log('info',
                        f'SKIP {symbol} [PLAYBOOK] bias=Short/High — historically bearish after gap', user_id=user_id)
                    continue
                playbook_override = pb
                _add_brown_log('info',
                    f'{symbol} playbook ready — bias={pb_bias}/{pb_conf}, using for stop/target', user_id=user_id)
            elif symbol in sess.playbook_pending:
                _add_brown_log('info',
                    f'DEFER {symbol}: playbook fetch in progress — will retry next scan cycle', user_id=user_id)
                continue
            elif symbol not in sess.playbook_failed:
                # First encounter — kick off background fetch and defer entry
                sess.playbook_pending.add(symbol)
                _pb_thread = threading.Thread(
                    target=_fetch_and_cache_playbook,
                    args=(symbol, {}, {}, user_id),
                    daemon=True,
                    name=f'Playbook-{symbol}',
                )
                _pb_thread.start()
                _add_brown_log('info',
                    f'DEFER {symbol}: started playbook fetch — will enter on next scan cycle', user_id=user_id)
                continue
            # else: playbook fetch previously failed → proceed with config defaults

        # Hard cap: re-read live day count under lock so a stale active_copy or
        # a concurrent order-monitor removal can never let us exceed the limit.
        max_day = int(config.get('max_concurrent_day', 3))
        with sess.lock:
            live_day = sum(
                1 for p in active_positions.values()
                if p.get('position_type') in ('day', 'brown_day')
                and not p.get('_exit_pending')
            )
            active_copy = dict(active_positions)
        if live_day >= max_day:
            _add_brown_log('info',
                f'Day cap {max_day} reached ({live_day} open) — no more day entries this scan', user_id=user_id)
            break

        if risk_manager:
            _unrealized = sum(p.get('unrealized_pnl', 0) for p in active_copy.values())
            _rs = risk_manager.status(active_copy, unrealized_pnl=_unrealized)
            allowed, reason = risk_manager.can_enter(symbol, 'day', active_copy, unrealized_pnl=_unrealized)
            if not allowed:
                _add_brown_log('warning',
                    f'SKIP {symbol} [RISK] {reason} '
                    f'(total P&L ${_rs["daily_pnl"]:.0f}, '
                    f'limit ${_rs["max_daily_loss"]:.0f}, '
                    f'day slots {_rs["open_day"]}/{_rs["max_concurrent_day"]})', user_id=user_id)
                continue
            _add_brown_log('info',
                f'{symbol} risk OK — total P&L ${_rs["daily_pnl"]:.0f} '
                f'(realized ${_rs["realized_pnl"]:.0f} + unrealized ${_rs["unrealized_pnl"]:.0f}), '
                f'day slots {_rs["open_day"]}/{_rs["max_concurrent_day"]}', user_id=user_id)
        _add_brown_log('info', f'Entering DAY {symbol} — gap {s["gap_percent"]:.1f}%', user_id)
        _brown_enter_position(user_id, symbol, 'day', config, s.get('price', 0), playbook_override=playbook_override)
        # Refresh active state after entry
        with sess.lock:
            active_symbols.add(symbol)
            active_copy = dict(active_positions)

    # ── Process swing candidates from broad-market scan ──────────────────
    # Steps 1-3 (scan → signal filter → AI ranking) run regardless of market hours
    # so the BrownBot table and Swing tab always show fresh candidates.
    # Step 4 (position entry) is gated to market hours only.
    _swing_entry_allowed = _in_market_hours and config.get('swing_trades_enabled', True)
    if not config.get('swing_trades_enabled', True):
        _add_brown_log('info', 'Swing trades disabled — will scan but not enter', user_id)
    elif _swing_entry_allowed and config.get('swing_time_gate_enabled'):
        _sg_start = config.get('swing_time_gate_start', '09:30')
        _sg_end   = config.get('swing_time_gate_end', '15:00')
        try:
            _sg_sh, _sg_sm = map(int, _sg_start.split(':'))
            _sg_eh, _sg_em = map(int, _sg_end.split(':'))
            _swing_entry_allowed = (
                (now_et.hour, now_et.minute) >= (_sg_sh, _sg_sm) and
                (now_et.hour, now_et.minute) <  (_sg_eh, _sg_em)
            )
        except Exception:
            pass
        if not _swing_entry_allowed:
            _add_brown_log('info', f'Swing entry gate closed ({_sg_start}–{_sg_end} ET) — scanning but not entering', user_id)

    # Step 1 — Universe scan: Alpaca most-actives + gainers, then
    # price / avg-volume / market-cap / float filters + daily-bar technicals.
    # Results are cached 5 min so the 30-s loop doesn't hammer the API.
    swing_raw = _brown_scan_swing_candidates(config, user_id)
    if not swing_raw:
        _add_brown_log('info', 'Swing scanner: no candidates after filters', user_id)
        return

    # Step 2 — User-configured entry signal filters (optional, all off by default).
    signal_passed = []
    for cand in swing_raw:
        sym = cand['symbol']
        if sym in active_symbols or sym in attempted_symbols:
            continue
        sig_ok, _checks, sig_reason = _check_swing_entry_signal(sym, cand, config)
        if sig_ok:
            signal_passed.append(cand)
        else:
            _add_brown_log('info', f'SKIP swing {sym} [SIGNAL] {sig_reason}', user_id)

    if not signal_passed:
        _add_brown_log('info', 'Swing scanner: no candidates passed entry signal filters', user_id)
        return

    # Step 3 — AI ranking via SwingPicksAgent (Haiku, Grade A/B + Bullish only).
    # Results cached 15 min; only re-runs when the candidate fingerprint changes.
    # Always runs so the BrownBot table and Swing tab are populated.
    ai_picks = _brown_rank_swing_ai(signal_passed, user_id)
    hot_swing_picks = [
        p for p in ai_picks
        if p.get('grade') in ('A', 'B') and p.get('bias', '').lower() == 'bullish'
    ]
    if not hot_swing_picks:
        _add_brown_log('info', 'Swing AI: no Grade A/B Bullish picks', user_id)
        return

    # Step 4 — Risk gate + position entry (market hours only)
    if not _swing_entry_allowed:
        _add_brown_log('info',
            f'Swing scan complete ({len(hot_swing_picks)} picks ready) — '
            f'entry {"disabled" if not config.get("swing_trades_enabled", True) else "waiting for market open"}', user_id=user_id)
        return
    for pick in hot_swing_picks:
        if not sess.running:
            return
        symbol = pick.get('ticker', '').upper()
        if not symbol:
            continue
        if symbol in active_symbols:
            continue
        if symbol in attempted_symbols:
            continue

        # Hard cap: re-read live swing count under lock
        max_swing = int(config.get('max_concurrent_swing', 5))
        with sess.lock:
            live_swing = sum(
                1 for p in active_positions.values()
                if p.get('position_type') in ('swing', 'brown_swing')
                and not p.get('_exit_pending')
            )
            active_copy = dict(active_positions)
        if live_swing >= max_swing:
            _add_brown_log('info',
                f'Swing cap {max_swing} reached ({live_swing} open) — no more swing entries this scan', user_id=user_id)
            break

        if risk_manager:
            _unrealized = sum(p.get('unrealized_pnl', 0) for p in active_copy.values())
            _rs = risk_manager.status(active_copy, unrealized_pnl=_unrealized)
            allowed, reason = risk_manager.can_enter(symbol, 'swing', active_copy, unrealized_pnl=_unrealized)
            if not allowed:
                _add_brown_log('warning',
                    f'SKIP swing {symbol} [RISK] {reason} '
                    f'(total P&L ${_rs["daily_pnl"]:.0f}, '
                    f'swing slots {_rs["open_swing"]}/{_rs["max_concurrent_swing"]})', user_id=user_id)
                continue
            _add_brown_log('info',
                f'{symbol} risk OK — total P&L ${_rs["daily_pnl"]:.0f} '
                f'(realized ${_rs["realized_pnl"]:.0f} + unrealized ${_rs["unrealized_pnl"]:.0f}), '
                f'swing slots {_rs["open_swing"]}/{_rs["max_concurrent_swing"]}', user_id=user_id)

        live_price  = _brown_get_current_price(user_id, symbol) or 0
        grade       = pick.get('grade', '?')
        pick_reason = pick.get('reason', '')
        entry_zone  = pick.get('entry_zone', '')
        _add_brown_log('info',
            f'Entering SWING {symbol} [Grade {grade}] — {pick_reason}'
            + (f' · entry zone: {entry_zone}' if entry_zone else ''), user_id=user_id)
        _brown_enter_position(user_id, symbol, 'swing', config, live_price)
        # Record actual entry in screener history for backtest accuracy
        try:
            import pytz as _ptz
            _hist_date = datetime.now(_ptz.timezone('US/Eastern')).date().isoformat()
            db_manager.mark_swing_screener_entered(_hist_date, symbol, live_price or 0)
        except Exception:
            pass
        with sess.lock:
            active_symbols.add(symbol)
            active_copy = dict(active_positions)


def _brown_bot_scanner_loop(user_id: int):
    """BrownBot daemon thread: scans and enters every 30 seconds."""
    _add_brown_log('info', 'BrownBot scanner loop started', user_id)
    sess = _get_brown_session(user_id)
    while sess and sess.running:
        try:
            _brown_bot_scan_and_enter(user_id)
        except Exception as e:
            app_logger.error(f'BrownBot scanner error: {e}', exc_info=True)
            _add_brown_log('error', f'Scanner loop error: {e}', user_id)
        # Sleep 30 s in 1-second ticks for clean shutdown
        for _ in range(30):
            if not sess.running:
                break
            time.sleep(1)
    _add_brown_log('info', 'BrownBot scanner loop stopped', user_id)


def _brown_get_current_price(user_id: int, symbol: str):
    """Fetch current price for an open BrownBot position via the active broker."""
    sess = _get_brown_session(user_id)
    broker = sess.broker if sess else None
    if not broker:
        return None
    try:
        return broker.get_current_price(symbol)
    except Exception as e:
        app_logger.warning(f'[BrownBot] price fetch failed for {symbol}: {e}')
    return None


def _brown_get_prices_batch(user_id: int, symbols):
    """
    Fetch prices for multiple symbols in ONE Alpaca snapshot call.
    Returns dict {symbol: price}.  Falls back to per-symbol on error.
    Used by the exit loop to avoid N individual API calls per tick.
    """
    sess = _get_brown_session(user_id)
    broker = sess.broker if sess else None
    if not broker or not symbols:
        return {}
    # Use batch snapshot if the broker supports it
    if hasattr(broker, 'get_quotes_batch'):
        try:
            return broker.get_quotes_batch(symbols)
        except Exception as e:
            app_logger.warning(f'[BrownBot] batch price fetch failed: {e} — falling back to per-symbol')
    # Fallback: individual calls (original behaviour)
    prices = {}
    for sym in symbols:
        p = _brown_get_current_price(user_id, sym)
        if p:
            prices[sym] = p
    return prices


# ── Broker-confirmed order monitor ────────────────────────────────────────────

def _brown_monitor_finalize_entry(user_id: int, oid, meta, fill_price, fill_qty):
    """Write the confirmed BUY trade to DB and update the in-memory position."""
    sess = _get_brown_session(user_id)
    symbol        = meta['symbol']
    position_id   = meta['position_id']
    position_type = meta['position_type']

    app_logger.debug(
        f'[BrownBot finalize_entry] {symbol} order={oid[:8]}… '
        f'fill_price={fill_price} fill_qty={fill_qty}')

    if sess:
        with sess.lock:
            pos = sess.active_positions.get(position_id)
            if pos:
                tgt_pct = pos.get('profit_target_pct', 5.0)
                stp_pct = pos.get('stop_loss_pct', 2.5)
                pos['entry_price']      = fill_price
                pos['avg_entry_price']  = fill_price
                pos['quantity']         = fill_qty
                pos['profit_target']    = round(fill_price * (1 + tgt_pct / 100), 2)
                pos['stop_loss']        = round(fill_price * (1 - stp_pct / 100), 2)
                pos['_entry_confirmed'] = True
                app_logger.debug(
                    f'[BrownBot finalize_entry] {symbol} memory updated — '
                    f'avg_entry={fill_price} target={pos["profit_target"]} stop={pos["stop_loss"]}')
            else:
                app_logger.debug(
                    f'[BrownBot finalize_entry] {symbol} position_id={position_id} '
                    f'NOT found in active_positions (may have been removed already)')
            sess.pending_orders.pop(oid, None)

    # Update the orders table with actual fill data
    try:
        db_manager.update_brown_order_fill(oid, fill_price, fill_qty)
    except Exception as _uoe:
        app_logger.debug(f'[BrownBot finalize_entry] {symbol} update_brown_order_fill failed: {_uoe}')

    try:
        db_manager.update_brown_position_entry(position_id, fill_price, fill_qty)
    except Exception as _upe:
        app_logger.debug(f'[BrownBot finalize_entry] {symbol} update_brown_position_entry failed: {_upe}')

    try:
        pos_snap = (sess.active_positions.get(position_id) if sess else None) or meta
        db_manager.save_brown_position(position_id, pos_snap, user_id=user_id)
    except Exception as _spe:
        app_logger.debug(f'[BrownBot finalize_entry] {symbol} save_brown_position failed: {_spe}')

    try:
        broker_name = sess.broker.name if (sess and sess.broker) else None
        db_manager.add_trade({
            'trade_id':      f'BROWN_ENTRY_{symbol}_{oid}',
            'symbol':        symbol,
            'side':          'B',
            'quantity':      fill_qty,
            'price':         fill_price,
            'route':         'SMAT',
            'trade_time':    datetime.now().isoformat(),
            'order_id':      oid,
            'liquidity':     None,
            'ecn_fee':       0.0,
            'pnl':           0.0,
            'trade_date':    _last_trading_date(),
            'position_type': position_type,
            'days_held':     None,
            'source':        'brownbot',
            'broker':        broker_name,
            'user_id':       user_id,
        })
        _add_brown_log('info', f'{symbol} BUY confirmed by broker: {fill_qty} @ ${fill_price:.2f}', user_id)
    except Exception as _e:
        _add_brown_log('warning', f'DB entry write failed for {symbol}: {_e}', user_id)


def _brown_monitor_finalize_exit(user_id: int, oid, meta, fill_price, fill_qty):
    """Write the confirmed SELL trade to DB and update exit stats."""
    sess = _get_brown_session(user_id)
    symbol        = meta['symbol']
    position_id   = meta['position_id']
    position_type = meta['position_type']
    exit_reason   = meta['exit_reason']
    entry_price   = meta['entry_price']
    avg_entry     = meta.get('avg_entry_price') or entry_price
    entry_num     = meta.get('entry_num', 1)
    days_held     = meta.get('days_held')

    app_logger.debug(
        f'[BrownBot finalize_exit] {symbol} order={oid[:8]}… '
        f'fill_price={fill_price} fill_qty={fill_qty} reason={exit_reason} '
        f'avg_entry={avg_entry} entry_price_in_meta={entry_price}')

    if sess:
        with sess.lock:
            sess.pending_orders.pop(oid, None)

    realized_pnl     = round((fill_price - avg_entry) * fill_qty, 2) if avg_entry else 0.0
    realized_pnl_pct = round((fill_price - avg_entry) / avg_entry * 100, 2) if avg_entry else 0.0

    try:
        db_manager.update_brown_order_fill(oid, fill_price, fill_qty)
    except Exception as _uoe:
        app_logger.debug(f'[BrownBot finalize_exit] {symbol} update_brown_order_fill failed: {_uoe}')

    try:
        db_manager.close_brown_position(
            position_id, fill_price, oid, exit_reason,
            realized_pnl, realized_pnl_pct
        )
    except Exception as _e:
        _add_brown_log('warning', f'DB position close failed for {symbol}: {_e}', user_id)

    try:
        broker_name = sess.broker.name if (sess and sess.broker) else None
        db_manager.add_trade({
            'trade_id':      f'BROWN_EXIT_{symbol}_{oid}',
            'symbol':        symbol,
            'side':          'S',
            'quantity':      fill_qty,
            'price':         fill_price,
            'route':         'SMAT',
            'trade_time':    datetime.now().isoformat(),
            'order_id':      oid,
            'liquidity':     None,
            'ecn_fee':       0.0,
            'pnl':           realized_pnl,
            'trade_date':    _last_trading_date(),
            'position_type': position_type,
            'days_held':     days_held,
            'source':        'brownbot',
            'broker':        broker_name,
            'user_id':       user_id,
        })
        app_logger.debug(f'[BrownBot finalize_exit] {symbol} trades row written pnl={realized_pnl}')
    except Exception as _e:
        _add_brown_log('warning', f'DB exit write failed for {symbol}: {_e}', user_id)

    if sess:
        if position_type == 'day':
            sess.stats['day_exited'] += 1
        else:
            sess.stats['swing_exited'] += 1

    pnl_str  = f'+${realized_pnl:.2f}' if realized_pnl >= 0 else f'-${abs(realized_pnl):.2f}'
    exit_tag = f'#{entry_num}' if entry_num == 1 else f'#{entry_num} (re-exit ×{entry_num - 1})'
    _add_brown_log(
        'info',
        f'EXITED {position_type.upper()} {symbol} {exit_tag} [{exit_reason}] '
        f'entry ${avg_entry:.2f} → exit ${fill_price:.2f} × {fill_qty} | P&L {pnl_str}',
        user_id)

    if sess:
        with sess.lock:
            sess.attempted_symbols.discard(symbol)
    _add_brown_log('info', f'{symbol}: unlocked for re-entry (exit confirmed)', user_id)


def _brown_order_monitor_loop(user_id: int):
    """
    Background thread: polls sess.pending_orders every 2 s and writes to DB
    only after the broker confirms a fill.  Handles rejections and timeouts.
    """
    ORDER_TIMEOUT = 60  # seconds before a stuck order is cancelled
    _last_status_log: dict = {}  # oid → last logged status string

    sess = _get_brown_session(user_id)
    while sess and sess.running:
        time.sleep(2)
        if not sess.pending_orders or not sess.broker:
            continue

        with sess.lock:
            pending_snapshot = list(sess.pending_orders.items())

        if pending_snapshot:
            app_logger.debug(
                f'[BrownBot monitor] polling {len(pending_snapshot)} pending order(s): '
                f'{[m["symbol"]+"/"+m["type"] for _, m in pending_snapshot]}')

        for oid, meta in pending_snapshot:
            if not sess.running:
                break
            symbol     = meta['symbol']
            order_type = meta['type']
            age        = time.time() - meta['submitted_at']

            try:
                order = sess.broker.get_order(oid)
            except Exception as _e:
                app_logger.debug(f'[BrownBot monitor] get_order {oid} failed: {_e}')
                continue

            from bot.broker.base import OrderStatus as _OStatus
            fill_price = (float(order.filled_avg_price)
                          if order.filled_avg_price else meta.get('approx_price', 0.0))
            fill_qty   = int(order.filled_qty or meta.get('quantity', 0))

            _cur_status_str = str(order.status)
            if _last_status_log.get(oid) != _cur_status_str:
                app_logger.debug(
                    f'[BrownBot monitor] {symbol} {order_type} order={oid[:8]}… '
                    f'status={_cur_status_str} age={age:.0f}s '
                    f'filled_avg_price={order.filled_avg_price} filled_qty={order.filled_qty}')
                _last_status_log[oid] = _cur_status_str

            if order.status == _OStatus.FILLED:
                if order_type == 'entry':
                    _brown_monitor_finalize_entry(user_id, oid, meta, fill_price, fill_qty)
                else:
                    _brown_monitor_finalize_exit(user_id, oid, meta, fill_price, fill_qty)

            elif order.status in (_OStatus.CANCELLED, _OStatus.REJECTED):
                with sess.lock:
                    sess.pending_orders.pop(oid, None)
                status_str = str(order.status).upper()
                _add_brown_log('warning', f'{symbol} {order_type} order {oid[:8]}… {status_str} — no DB write', user_id)
                if order_type == 'entry':
                    position_id = meta['position_id']
                    with sess.lock:
                        sess.active_positions.pop(position_id, None)
                        sess.entry_counts.pop(symbol, None)
                    try:
                        db_manager.delete_brown_position(position_id, user_id=user_id)
                    except Exception:
                        pass
                    _add_brown_log('warning', f'{symbol}: phantom entry removed — order was not filled', user_id)
                else:
                    saved_pos = meta.get('position')
                    if saved_pos:
                        with sess.lock:
                            sess.active_positions[meta['position_id']] = saved_pos
                        _add_brown_log('warning', f'{symbol}: exit order rejected — position restored for retry', user_id)

            elif age > ORDER_TIMEOUT:
                _add_brown_log('warning',
                    f'{symbol} {order_type} order {oid[:8]}… stuck {age:.0f}s — checking fill before cancel', user_id=user_id)
                try:
                    order = sess.broker.get_order(oid)
                    fill_price = (float(order.filled_avg_price)
                                  if order.filled_avg_price else meta.get('approx_price', 0.0))
                    fill_qty   = int(order.filled_qty or 0)
                    if order.status == _OStatus.FILLED:
                        _add_brown_log('info',
                            f'{symbol}: order filled just before timeout — finalising instead of cancelling', user_id=user_id)
                        if order_type == 'entry':
                            _brown_monitor_finalize_entry(user_id, oid, meta, fill_price, fill_qty)
                        else:
                            _brown_monitor_finalize_exit(user_id, oid, meta, fill_price, fill_qty)
                        continue
                    if order.status == _OStatus.PARTIAL and fill_qty > 0:
                        try:
                            sess.broker.cancel_order(oid)
                        except Exception:
                            pass
                        requested_qty = meta.get('quantity', fill_qty)
                        _add_brown_log('warning',
                            f'{symbol}: {order_type} order partially filled '
                            f'({fill_qty}/{requested_qty} shares) at timeout — '
                            f'cancelling remainder, accepting partial', user_id=user_id)
                        if order_type == 'entry':
                            _brown_monitor_finalize_entry(user_id, oid, meta, fill_price, fill_qty)
                        else:
                            _brown_monitor_finalize_exit(user_id, oid, meta, fill_price, fill_qty)
                            remaining_qty = requested_qty - fill_qty
                            if remaining_qty > 0:
                                saved_pos = meta.get('position')
                                if saved_pos:
                                    restored = dict(saved_pos)
                                    restored['quantity'] = remaining_qty
                                    position_id = meta.get('position_id')
                                    with sess.lock:
                                        sess.active_positions[position_id] = restored
                                        sess.closing_positions.discard(position_id)
                                    _add_brown_log('warning',
                                        f'{symbol}: {remaining_qty} shares restored to '
                                        f'active tracking after partial exit — exit loop will retry', user_id=user_id)
                        continue
                except Exception as _pre_cancel_e:
                    app_logger.debug(f'[BrownBot monitor] pre-cancel status check {oid} failed: {_pre_cancel_e}')

                try:
                    sess.broker.cancel_order(oid)
                except Exception:
                    pass
                with sess.lock:
                    sess.pending_orders.pop(oid, None)
                if order_type == 'entry':
                    position_id = meta['position_id']
                    with sess.lock:
                        sess.active_positions.pop(position_id, None)
                        sess.entry_counts.pop(symbol, None)
                    try:
                        db_manager.delete_brown_position(position_id, user_id=user_id)
                    except Exception:
                        pass
                    _add_brown_log('warning', f'{symbol}: entry timed out and not filled — position removed', user_id)
                else:
                    saved_pos = meta.get('position')
                    if saved_pos:
                        position_id = meta.get('position_id')
                        with sess.lock:
                            sess.active_positions[position_id] = saved_pos
                            sess.closing_positions.discard(position_id)
                        try:
                            db_manager.save_brown_position(position_id, saved_pos, user_id=user_id)
                        except Exception:
                            pass
                        _add_brown_log('warning',
                            f'{symbol}: exit order timed out — position restored, exit loop will retry', user_id=user_id)
                    else:
                        _add_brown_log('warning',
                            f'{symbol}: exit timed out but no saved position — position may be orphaned', user_id=user_id)


def _brown_close_position(user_id: int, position_id, position, exit_reason):
    """Close a BrownBot position, record the trade, and remove from active positions."""
    sess = _get_brown_session(user_id)
    if not sess:
        return False
    broker          = sess.broker
    lock            = sess.lock
    active_positions  = sess.active_positions
    closing_positions = sess.closing_positions
    pending_orders    = sess.pending_orders
    eod_flattened     = sess.eod_flattened_symbols

    symbol = position['symbol']
    quantity = int(position.get('quantity', 100))
    current_price = position.get('_current_price') or position.get('entry_price', 0)
    entry_price = float(position.get('entry_price', 0))
    position_type = position.get('position_type', 'day')

    if not broker:
        _add_brown_log('error', f'No broker available to close {symbol}', user_id=user_id)
        return False

    # Prevent double-exit race: if already being closed by another loop tick, skip.
    with lock:
        if position_id in closing_positions:
            _brown_debug(user_id, f'{symbol} ({position_id[:8]}…) already closing — duplicate exit skipped')
            return False
        closing_positions.add(position_id)

    order_id = None

    _brown_debug(user_id,
        f'CLOSE {symbol} position_id={position_id[:8]}… reason={exit_reason} '
        f'qty={quantity} price={current_price} avg_entry={position.get("avg_entry_price")}')

    # Verify the broker actually holds this position before selling.
    # If it doesn't exist (e.g. BUY never filled), abort cleanly.
    try:
        bp = broker.get_position(symbol)
    except Exception as _gpe:
        _brown_debug(user_id, f'{symbol}: broker.get_position raised: {_gpe}')
        bp = None
    if not bp:
        _add_brown_log('warning',
            f'No open position for {symbol} in broker — removing from tracking (no sell placed)',
            user_id=user_id)
        with lock:
            active_positions.pop(position_id, None)
            closing_positions.discard(position_id)
        return False

    _brown_debug(user_id,
        f'{symbol}: broker position confirmed — qty={bp.qty} '
        f'avg_entry={bp.avg_entry_price} unrealized={bp.unrealized_pnl}')

    # Use broker's close_position so we can never accidentally short.
    try:
        order = broker.close_position(symbol)
        order_id = order.order_id
        app_logger.info(f'[BrownBot:{broker.name}] SELL {symbol} → order_id={order_id}')
    except Exception as e:
        _add_brown_log('error', f'SELL order failed for {symbol}: {e}', user_id=user_id)
        with lock:
            closing_positions.discard(position_id)  # allow exit loop to retry
        return False

    # Calculate days held (needed for DB record written by the monitor)
    days_held = None
    entry_time_str = position.get('entry_time', '')
    if entry_time_str:
        try:
            entry_dt = datetime.fromisoformat(entry_time_str)
            days_held = (datetime.now() - entry_dt).days
        except Exception:
            pass

    _trade_date = _last_trading_date()

    # Log exit order to the immutable orders table
    try:
        db_manager.add_brown_order({
            'order_id':       str(order_id),
            'position_id':    position_id,
            'symbol':         symbol,
            'side':           'S',
            'order_type':     'exit',
            'position_type':  position_type,
            'submitted_qty':  quantity,
            'submitted_price': float(current_price),
            'status':         'pending',
            'exit_reason':    exit_reason,
            'submitted_at':   datetime.now().isoformat(),
            'trade_date':     _trade_date,
        }, user_id=user_id)
        _brown_debug(user_id,
            f'{symbol}: exit brown_orders row written — '
            f'order={str(order_id)[:8]}… status=pending reason={exit_reason}')
    except Exception as _e:
        _add_brown_log('warning', f'DB exit order log failed for {symbol}: {_e}', user_id=user_id)

    # Queue the exit for the monitor thread — DB write happens after confirmed fill.
    _avg_entry_for_meta = position.get('avg_entry_price') or entry_price
    with lock:
        pending_orders[str(order_id)] = {
            'type':            'exit',
            'symbol':          symbol,
            'position_id':     position_id,
            'order_id':        str(order_id),
            'submitted_at':    time.time(),
            'approx_price':    float(current_price),
            'quantity':        quantity,
            'entry_price':     entry_price,
            'avg_entry_price': _avg_entry_for_meta,
            'position_type':   position_type,
            'exit_reason':     exit_reason,
            'days_held':       days_held,
            'entry_num':       position.get('entry_num', 1),
            'position':        dict(position),  # kept so monitor can restore on rejection
        }

    _brown_debug(user_id,
        f'{symbol}: queued to pending_orders — order={str(order_id)[:8]}… '
        f'avg_entry={_avg_entry_for_meta} approx_exit={current_price}')

    # Don't delete from DB — close_brown_position (called after fill confirmation)
    # marks it as 'closed' with realized P&L. Keeping the row until fill ensures
    # correct recovery if the server restarts while the exit order is in-flight.
    with lock:
        active_positions.pop(position_id, None)
        closing_positions.discard(position_id)
    _brown_debug(user_id,
        f'{symbol}: removed from active_positions — monitor will finalize on fill')

    # EOD flatten tracking must happen immediately (blocks re-entry the same day)
    if position_type == 'day' and 'EOD_FLATTEN' in exit_reason:
        eod_flattened.add(symbol)

    _add_brown_log(
        'info',
        f'SELL submitted {position_type.upper()} {symbol} [{exit_reason}] — '
        f'awaiting fill confirmation (entry ${entry_price:.2f})',
        user_id=user_id,
    )
    return True


def _brown_bot_check_exits(user_id: int, check_swing_specific=False, verbose=False):
    """Evaluate all open BrownBot positions for exit conditions."""
    sess = _get_brown_session(user_id)
    if not sess or not sess.running:
        return
    lock             = sess.lock
    active_positions = sess.active_positions

    import pytz as _pytz
    _et = _pytz.timezone('US/Eastern')
    now_et = datetime.now(_et)

    config = db_manager.get_brown_bot_config(user_id)

    # Parse EOD time from config (e.g. '15:45')
    eod_str = config.get('day_eod_exit_time', '15:45')
    try:
        eod_h, eod_m = map(int, eod_str.split(':'))
    except Exception:
        eod_h, eod_m = 15, 45
    eod_time = now_et.replace(hour=eod_h, minute=eod_m, second=0, microsecond=0)

    # Earnings calendar (fetched once per swing check cycle to avoid redundant calls)
    earnings_symbols_soon = set()
    if check_swing_specific and config.get('swing_earnings_protection_enabled') and AI_AGENT_AVAILABLE and _ai_agent:
        try:
            earnings_exit_days = int(config.get('swing_earnings_exit_days', 2))
            cal = _ai_agent._get_earnings_calendar()
            if cal and 'earnings_next_5_days' in cal:
                today = datetime.now().date()
                for item in cal['earnings_next_5_days']:
                    try:
                        earn_date = datetime.strptime(item['date'], '%Y-%m-%d').date()
                        days_to_earn = (earn_date - today).days
                        if 0 <= days_to_earn <= earnings_exit_days:
                            earnings_symbols_soon.add((item.get('symbol') or '').upper())
                    except Exception:
                        pass
        except Exception as e:
            app_logger.debug(f'Earnings calendar fetch failed: {e}')

    # Sync profit_target and stop_loss for every active position from the latest config.
    # This makes target/stop % changes effective within 2 s without restarting the bot.
    # Skip rules (do NOT overwrite when any of these apply):
    #   profit_target: skip if position has a playbook-derived target (playbook_target_pct
    #                  is not None) — the AI set a specific % different from config.
    #   stop_loss:     skip if position has a playbook-derived stop  (playbook_stop_pct
    #                  is not None), OR breakeven has locked the stop at entry price, OR
    #                  the trailing stop is already tracking a high-water mark.
    _day_tgt_pct   = float(config.get('day_profit_target_pct', 5.0))
    _day_stp_pct   = float(config.get('day_stop_loss_pct', 2.5))
    _swing_tgt_pct = float(config.get('swing_profit_target_pct', 15.0))
    _swing_stp_pct = float(config.get('swing_stop_loss_pct', 7.0))
    with lock:
        for _pid, _pos in active_positions.items():
            _ptype  = _pos.get('position_type', 'day')
            _entry  = float(_pos.get('avg_entry_price') or _pos.get('entry_price') or 0)
            if not _entry:
                continue
            _tgt_pct = _day_tgt_pct if _ptype == 'day' else _swing_tgt_pct
            _stp_pct = _day_stp_pct if _ptype == 'day' else _swing_stp_pct
            # Profit target: only sync if no playbook override
            if _pos.get('playbook_target_pct') is None:
                _pos['profit_target']     = round(_entry * (1 + _tgt_pct / 100), 2)
                _pos['profit_target_pct'] = _tgt_pct
            # Stop loss: only sync if no playbook override AND stop hasn't been
            # moved to a more-favourable level by breakeven or trailing
            if (_pos.get('playbook_stop_pct') is None
                    and not _pos.get('_at_breakeven')
                    and not _pos.get('_trail_high')):
                _pos['stop_loss']     = round(_entry * (1 - _stp_pct / 100), 2)
                _pos['stop_loss_pct'] = _stp_pct
        positions_snapshot = dict(active_positions)

    # Batch-fetch all prices in ONE API call to avoid per-symbol rate limiting.
    _active_symbols = [p['symbol'] for p in positions_snapshot.values()
                       if not p.get('_exit_pending')]
    _price_cache = _brown_get_prices_batch(user_id, _active_symbols) if _active_symbols else {}
    if _active_symbols and verbose:
        app_logger.info(
            f'[BrownBot exits] monitoring {len(_active_symbols)} position(s): '
            f'{_active_symbols} | prices resolved: {len(_price_cache)}/{len(_active_symbols)}')
        for _pid, _pos in positions_snapshot.items():
            _psym = _pos.get('symbol', '?')
            _pprice = _price_cache.get(_psym)
            _pentry = float(_pos.get('avg_entry_price') or _pos.get('entry_price', 0) or 0)
            _pqty = int(_pos.get('quantity', 0))
            _ppnl = round((_pprice - _pentry) * _pqty, 2) if (_pprice and _pentry) else None
            _pstop = _pos.get('stop_loss')
            _ptgt  = _pos.get('profit_target')
            _pbe   = ' [BE]' if _pos.get('_at_breakeven') else ''
            _stop_str = f'${_pstop:.2f}' if _pstop else 'N/A'
            _tgt_str  = f'${_ptgt:.2f}' if _ptgt else 'N/A'
            _price_str = f'${_pprice:.2f}' if _pprice is not None else 'N/A'
            _pnl_str   = f'${_ppnl:+.2f}' if _ppnl is not None else 'N/A'
            app_logger.info(
                f'[BrownBot exits]   {_psym}{_pbe}: '
                f'entry=${_pentry:.2f} current={_price_str} '
                f'stop={_stop_str} target={_tgt_str} '
                f'pnl={_pnl_str} qty={_pqty} '
                f'type={_pos.get("position_type","?")} pending_exit={_pos.get("_exit_pending",False)}')

    for position_id, position in positions_snapshot.items():
        if not sess.running:
            return
        # Skip positions already being closed (close-all or individual exit in-flight)
        if position.get('_exit_pending'):
            continue
        symbol = position['symbol']
        position_type = position.get('position_type', 'day')

        # Wait 15 s after entry before attempting any exit — prevents wash-trade
        # rejection from Alpaca when the BUY order is still pending_new.
        if time.time() - position.get('entry_time_epoch', 0) < 15:
            continue

        current_price = _price_cache.get(symbol)

        # EOD force-flatten: time-based — must fire even if price fetch failed.
        # _brown_close_position falls back to entry_price when _current_price is None.
        if position_type == 'day' and now_et >= eod_time:
            _add_brown_log('trade', f'{symbol}: EOD force-flatten at {eod_str} ET', user_id=user_id)
            app_logger.info(f'[BrownBot] EOD flatten {symbol} (now={now_et.strftime("%H:%M:%S")} ET, eod={eod_str})')
            position_with_price = {**position, '_current_price': current_price}
            _brown_close_position(user_id, position_id, position_with_price, f'EOD_FLATTEN ({eod_str} ET)')
            continue

        # All remaining exit checks need a live price — skip if unavailable
        if current_price is None:
            app_logger.warning(f'[BrownBot] {symbol}: price unavailable, skipping exit check this tick')
            continue

        entry_price = float(position.get('avg_entry_price') or position.get('entry_price', 0))
        quantity = int(position.get('quantity', 0))
        unrealized_pnl = round((current_price - entry_price) * quantity, 2) if entry_price else 0.0
        unrealized_pnl_pct = round(
            (current_price - entry_price) / entry_price * 100, 2
        ) if entry_price else 0.0

        # Update unrealized P&L and current price in shared state
        with lock:
            if position_id in active_positions:
                active_positions[position_id]['unrealized_pnl']     = unrealized_pnl
                active_positions[position_id]['unrealized_pnl_pct'] = unrealized_pnl_pct
                active_positions[position_id]['_current_price']     = current_price

        # Persist unrealized P&L to DB so it survives between polls
        try:
            db_manager.update_brown_position_unrealized(
                position_id, current_price, unrealized_pnl, unrealized_pnl_pct
            )
        except Exception:
            pass

        profit_target = position.get('profit_target')
        stop_loss = position.get('stop_loss')

        # Breakeven stop: move stop to entry once price reaches halfway to target
        if (not position.get('_at_breakeven')
                and profit_target and entry_price
                and profit_target > entry_price):
            breakeven_pct = float(config.get(f'{position_type}_breakeven_trigger_pct', 50.0))
            progress = (current_price - entry_price) / (profit_target - entry_price) * 100
            if progress >= breakeven_pct:
                with lock:
                    if position_id in active_positions:
                        active_positions[position_id]['stop_loss'] = entry_price
                        active_positions[position_id]['_at_breakeven'] = True
                stop_loss = entry_price
                _add_brown_log('info', f'{symbol}: stop moved to breakeven ${entry_price:.2f} ({progress:.0f}% to target)', user_id=user_id)

        # ── Trailing stop: ratchet stop_loss up as price rises ──
        trail_key = f'{position_type}_trailing_stop_enabled'
        trail_pct_key = f'{position_type}_trailing_stop_pct'
        if config.get(trail_key) and entry_price:
            trail_pct = float(config.get(trail_pct_key, 5.0))
            # Initialise the high-water mark on first tick
            with lock:
                if position_id in active_positions:
                    if not active_positions[position_id].get('_trail_high'):
                        active_positions[position_id]['_trail_high'] = entry_price
                    if current_price > active_positions[position_id]['_trail_high']:
                        active_positions[position_id]['_trail_high'] = current_price
                    trail_high = active_positions[position_id]['_trail_high']
                    new_stop = round(trail_high * (1 - trail_pct / 100), 4)
                    cur_stop = active_positions[position_id].get('stop_loss') or 0
                    if new_stop > cur_stop:
                        active_positions[position_id]['stop_loss'] = new_stop
                        stop_loss = new_stop

        # ── Exit condition checks ──
        exit_reason = None

        if profit_target and current_price >= profit_target:
            exit_reason = 'PROFIT_TARGET'
        elif stop_loss and current_price <= stop_loss:
            exit_reason = 'STOP_LOSS'
        elif position_type == 'swing' and check_swing_specific:
            # Max hold days
            entry_time_str = position.get('entry_time', '')
            if entry_time_str:
                try:
                    entry_dt = datetime.fromisoformat(entry_time_str)
                    days_held = (datetime.now() - entry_dt).days
                    max_hold = int(config.get('swing_max_hold_days', 20))
                    if days_held >= max_hold:
                        exit_reason = f'MAX_HOLD_DAYS ({days_held}d)'
                except Exception:
                    pass
            # Earnings protection
            if not exit_reason and symbol.upper() in earnings_symbols_soon:
                exit_reason = 'EARNINGS_PROTECTION'

        if exit_reason:
            position_with_price = {**position, '_current_price': current_price}
            _brown_close_position(user_id, position_id, position_with_price, exit_reason)


def _brown_bot_exit_loop(user_id: int):
    """BrownBot exit daemon: checks open positions for exit conditions every 2 seconds."""
    sess = _get_brown_session(user_id)
    _add_brown_log('info', 'BrownBot exit loop started', user_id=user_id)
    tick = 0
    while sess and sess.running:
        try:
            # Verbose summary every 30 ticks (60 s) — logs all monitored positions with P&L.
            # Also verbose every tick when admin has debug mode enabled for this user.
            _verbose = (tick % 30 == 0) or is_debug_user(user_id)
            _brown_bot_check_exits(user_id, check_swing_specific=(tick % 30 == 0), verbose=_verbose)
            tick += 1
        except Exception as e:
            app_logger.error(f'BrownBot exit loop error: {e}', exc_info=True)
            _add_brown_log('error', f'Exit loop error: {e}', user_id=user_id)
        time.sleep(2)
    _add_brown_log('info', 'BrownBot exit loop stopped', user_id=user_id)


# ── Backtest API endpoints ─────────────────────────────────────────────────

@app.route('/api/backtest/info', methods=['GET'])
def get_backtest_info():
    """Return date range and candidate counts available in gap_data."""
    try:
        from backtest_engine import get_backtest_info as _info
        return jsonify({'success': True, **_info()})
    except Exception as e:
        app_logger.error(f'[Backtest] info error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backtest/run', methods=['POST'])
@require_auth
def run_backtest():
    """Run a gap-up backtest simulation and return trades + stats + equity curve."""
    try:
        from backtest_engine import run_backtest as _run
        cfg = request.get_json(force=True) or {}

        # Basic validation
        if not cfg.get('start_date') or not cfg.get('end_date'):
            return jsonify({'success': False, 'error': 'start_date and end_date are required'}), 400
        if float(cfg.get('initial_capital', 0)) <= 0:
            return jsonify({'success': False, 'error': 'initial_capital must be > 0'}), 400

        result = _run(cfg)
        return jsonify({'success': True, **result})
    except Exception as e:
        app_logger.error(f'[Backtest] run error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/seed-gap-data', methods=['POST'])
@require_role('super_admin', 'dev_master', 'bot_admin')
def seed_gap_data():
    """One-time import of gap_data_export.sql into the main database."""
    import sqlite3 as _sqlite3
    sql_path = os.path.join(os.path.dirname(__file__), 'gap_data_export.sql')
    if not os.path.exists(sql_path):
        return jsonify({'success': False, 'error': 'gap_data_export.sql not found in container'}), 404
    try:
        db_path = os.getenv('DATABASE_PATH') or os.path.join(os.path.dirname(__file__), 'trading_advisor.db')
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        conn = _sqlite3.connect(db_path)
        try:
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            inserted = 0
            for stmt in statements:
                upper = stmt.upper().lstrip()
                if upper.startswith('CREATE TABLE'):
                    try:
                        conn.execute(stmt)
                    except _sqlite3.OperationalError:
                        pass  # table already exists
                elif upper.startswith('INSERT'):
                    try:
                        conn.execute(stmt)
                        inserted += 1
                    except _sqlite3.IntegrityError:
                        pass  # duplicate — already seeded
            conn.commit()
            total = conn.execute("SELECT COUNT(*) FROM gap_data").fetchone()[0]
        finally:
            conn.close()
        return jsonify({'success': True, 'rows_inserted': inserted, 'total_rows': total})
    except Exception as e:
        app_logger.error(f'[seed-gap-data] {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ── BrownBot API endpoints ─────────────────────────────────────────────────

@app.route('/api/brown-bot/status', methods=['GET'])
@require_auth
def get_brown_bot_status():
    """Return BrownBot running state, stats, and active position count."""
    current_user_id = request.user.get('id', 1)
    sess = _brown_sessions.get(current_user_id)
    running = sess is not None and sess.running

    das_ok = DAS_ENABLED and _das_direct is not None
    broker = (sess.broker if sess else None) or _get_broker(current_user_id)
    broker_info = broker.to_dict() if broker else None

    if not sess:
        return jsonify({
            'success': True,
            'running': False,
            'das_enabled': DAS_ENABLED,
            'das_connected': das_ok,
            'broker': broker_info,
            'stats': {'day_entered': 0, 'swing_entered': 0, 'day_exited': 0, 'swing_exited': 0},
            'active_positions_count': 0,
            'active_positions': [],
            'entry_counts': {},
            'skipped_symbols': [],
        })

    lock             = sess.lock
    active_positions = sess.active_positions
    pending_orders   = sess.pending_orders

    # Snapshot in-memory BrownBot state under lock.
    with lock:
        bb_by_symbol = {
            (pos.get('symbol') or '').upper(): pos
            for pos in active_positions.values()
        }
        pending_exit_syms = {
            (meta.get('symbol') or '').upper()
            for meta in pending_orders.values()
            if meta.get('type') == 'exit'
        }
        entry_counts = dict(sess.entry_counts)
        skipped_symbols = list(sess.attempted_symbols - set(sess.entry_counts.keys()))

    # Use broker.get_positions() as the row source so the table always matches
    # what actually exists at the broker — no stale ghosts, no missing orphans.
    positions_list = []
    if broker:
        try:
            for lp in broker.get_positions():
                sym = lp.symbol.upper()
                bb  = bb_by_symbol.get(sym, {})
                _avg_entry   = round(lp.avg_entry_price, 4)
                _unr_pnl     = lp.unrealized_pnl
                _unr_pnl_pct = (
                    round((_unr_pnl / (_avg_entry * abs(lp.qty))) * 100, 2)
                    if _avg_entry and lp.qty else 0.0
                )
                positions_list.append({
                    'position_id':        bb.get('position_id', f'BROKER_{sym}'),
                    'symbol':             sym,
                    'position_type':      bb.get('position_type'),
                    'avg_entry':          _avg_entry,
                    'avg_entry_price':    _avg_entry,
                    'entry_price':        bb.get('entry_price') or _avg_entry,
                    'quantity':           int(abs(lp.qty)),
                    'profit_target':      bb.get('profit_target'),
                    'profit_target_pct':  bb.get('profit_target_pct'),
                    'stop_loss':          bb.get('stop_loss'),
                    'stop_loss_pct':      bb.get('stop_loss_pct'),
                    'entry_time':         bb.get('entry_time'),
                    'entry_time_epoch':   bb.get('entry_time_epoch'),
                    '_current_price':     lp.current_price,
                    'unrealized_pnl':     _unr_pnl,
                    'unrealized_pnl_pct': _unr_pnl_pct,
                    'market_value':       lp.market_value,
                    '_broker_synced':     True,
                    '_at_breakeven':      bb.get('_at_breakeven', False),
                    '_exit_pending':      sym in pending_exit_syms or bb.get('_exit_pending', False),
                })
            positions_list.sort(key=lambda p: p.get('symbol', ''))
        except Exception as _be:
            app_logger.debug(f'BrownBot status: broker fetch failed, falling back to in-memory: {_be}')
            with lock:
                positions_list = list(active_positions.values())
            for meta in pending_orders.values():
                if meta.get('type') == 'exit' and meta.get('position'):
                    pos = dict(meta['position'])
                    pos['_exit_pending'] = True
                    positions_list.append(pos)
            positions_list.sort(key=lambda p: p.get('symbol', ''))

    active_count = len(positions_list)

    # Clean up _exit_pending positions no longer held at broker (close-all confirmed).
    if broker:
        broker_syms = {p.get('symbol', '').upper() for p in positions_list}
        with lock:
            gone_pids = [
                pid for pid, pos in active_positions.items()
                if pos.get('_exit_pending') and
                   pos.get('symbol', '').upper() not in broker_syms
            ]
            for pid in gone_pids:
                active_positions.pop(pid, None)

    # Pull today's entry/exit counts from DB so stats survive restarts.
    today = _last_trading_date()
    stats = {'day_entered': 0, 'swing_entered': 0, 'day_exited': 0, 'swing_exited': 0}
    try:
        with db_manager.get_connection() as _conn:
            rows = _conn.execute(
                '''SELECT position_type, side, COUNT(*) AS cnt
                   FROM trades
                   WHERE trade_date = ? AND trade_id LIKE 'BROWN_%'
                     AND user_id = ?
                   GROUP BY position_type, side''',
                (today, current_user_id)
            ).fetchall()
        for r in rows:
            pt   = (r['position_type'] or 'day').lower()
            side = (r['side'] or '').upper()
            cnt  = r['cnt']
            if side == 'B':
                stats[f'{pt}_entered'] = cnt
            elif side in ('S', 'SS'):
                stats[f'{pt}_exited'] = cnt
    except Exception as _e:
        app_logger.warning(f'BrownBot stats DB query failed: {_e}')

    return jsonify({
        'success': True,
        'running': running,
        'das_enabled': DAS_ENABLED,
        'das_connected': das_ok,
        'broker': broker_info,
        'stats': stats,
        'active_positions_count': active_count,
        'active_positions': positions_list,
        'entry_counts': entry_counts,
        'skipped_symbols': skipped_symbols,
    })


@app.route('/api/brown-bot/broker-orders', methods=['GET'])
@require_auth
def get_brown_bot_broker_orders():
    """Return filled/closed orders directly from the broker (Alpaca).

    Query params:
        status  – 'filled' (default) | 'all' | 'open'
        limit   – max orders to return (default 50, max 100)
        after   – ISO date YYYY-MM-DD lower bound
        until   – ISO date YYYY-MM-DD upper bound
        symbols – comma-separated ticker filter, e.g. NVDA,TSLA
    """
    _uid = request.user.get('id', 1)
    _sess = _brown_sessions.get(_uid)
    broker = (_sess.broker if _sess else None) or _get_broker(_uid)
    if not broker:
        return jsonify({'success': False, 'error': 'No broker configured'})
    if not hasattr(broker, 'get_orders_history'):
        return jsonify({'success': False, 'error': f'{broker.name} does not support order history API'})

    status  = request.args.get('status', 'filled')
    limit   = min(int(request.args.get('limit', 50)), 100)
    after   = request.args.get('after')
    until   = request.args.get('until')
    sym_raw = request.args.get('symbols', '')
    symbols = [s.strip().upper() for s in sym_raw.split(',') if s.strip()] or None

    try:
        orders = broker.get_orders_history(
            status=status, limit=limit,
            after=after, until=until, symbols=symbols,
        )
        return jsonify({'success': True, 'orders': orders, 'count': len(orders)})
    except Exception as e:
        app_logger.warning(f'broker-orders error: {e}')
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/brown-bot/broker-activities', methods=['GET'])
@require_auth
def get_brown_bot_broker_activities():
    """Return account activities directly from the broker (Alpaca).

    Query params:
        type  – activity type, default 'FILL'
        date  – ISO date YYYY-MM-DD (Alpaca UTC day boundary)
        limit – max results (default 50, max 100)
    """
    _uid = request.user.get('id', 1)
    _sess = _brown_sessions.get(_uid)
    broker = (_sess.broker if _sess else None) or _get_broker(_uid)
    if not broker:
        return jsonify({'success': False, 'error': 'No broker configured'})
    if not hasattr(broker, 'get_activities'):
        return jsonify({'success': False, 'error': f'{broker.name} does not support activities API'})

    activity_type = request.args.get('type', 'FILL').upper()
    date          = request.args.get('date')
    limit         = min(int(request.args.get('limit', 50)), 100)

    try:
        activities = broker.get_activities(activity_type=activity_type, date=date, limit=limit)
        return jsonify({'success': True, 'activities': activities, 'count': len(activities)})
    except Exception as e:
        app_logger.warning(f'broker-activities error: {e}')
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/brown-bot/start', methods=['POST'])
@require_auth
def start_brown_bot():
    """Start BrownBot for the requesting user — each user gets an isolated session."""
    user_id = request.user.get('id', 1)

    with _brown_sessions_lock:
        existing = _brown_sessions.get(user_id)
        if existing and existing.running:
            return jsonify({'success': False, 'error': 'BrownBot is already running'})
        sess = BrownSession(user_id)
        _brown_sessions[user_id] = sess

    # Require a configured broker
    sess.broker = _get_broker(user_id)
    if not sess.broker and user_id != 1:
        sess.broker = _get_broker(1)
        if sess.broker:
            _add_brown_log('warning',
                'Using broker config from admin account (migration fallback). '
                'Re-save your broker credentials in Account Settings to assign them to your account.',
                user_id=user_id)
    if not sess.broker:
        with _brown_sessions_lock:
            _brown_sessions.pop(user_id, None)
        return jsonify({'success': False, 'error': 'No broker configured. Set up a broker in Account Settings before starting BrownBot.'})
    _add_brown_log('info', f'Broker ready: {sess.broker.name}', user_id=user_id)

    # Instantiate risk manager from saved config
    if RISK_MANAGER_AVAILABLE:
        try:
            config = db_manager.get_brown_bot_config(user_id)
            sess.risk_manager = RiskManager(config, user_id=user_id)
            _add_brown_log('info', f'RiskManager ready — max daily loss ${config.get("max_daily_loss", -500)}, '
                                   f'day limit {config.get("max_concurrent_day", 3)}, '
                                   f'swing limit {config.get("max_concurrent_swing", 5)}',
                           user_id=user_id)
        except Exception as e:
            _add_brown_log('warning', f'RiskManager init failed: {e}', user_id=user_id)

    # Restore positions from DB and cross-reference with broker
    try:
        import pytz as _pytz_r
        today_et = datetime.now(_pytz_r.timezone('US/Eastern')).strftime('%Y-%m-%d')
        saved = db_manager.get_brown_positions(user_id=user_id)
        restored, purged = 0, 0

        with sess.lock:
            for pos in (saved or []):
                pid = pos.get('position_id')
                if not pid:
                    continue
                pos_type = (pos.get('position_type') or 'day').lower()
                entry_time = pos.get('entry_time', '')
                if pos_type == 'day':
                    entry_date = entry_time[:10] if entry_time else ''
                    if entry_date != today_et:
                        db_manager.delete_brown_position(pid, user_id=user_id)
                        purged += 1
                        continue
                pos.setdefault('unrealized_pnl', 0.0)
                sess.active_positions[pid] = pos
                sym = pos.get('symbol', '')
                if sym:
                    sess.attempted_symbols.add(sym)
                    sess.entry_counts[sym] = sess.entry_counts.get(sym, 0) + 1
                restored += 1

        if purged:
            _add_brown_log('info', f'Purged {purged} stale day position(s) from previous session(s)', user_id=user_id)
        if restored:
            _add_brown_log('info', f'Restored {restored} position(s) from DB — verifying with broker…', user_id=user_id)

        if sess.broker:
            try:
                all_broker_pos = sess.broker.get_positions()
                broker_pos_map = {p.symbol.upper(): p for p in all_broker_pos}
                tracked_syms   = {pos.get('symbol', '').upper()
                                  for pos in sess.active_positions.values()}

                # 1 — drop stale (in DB but not in broker)
                stale = [
                    (pid, pos.get('symbol', '').upper(), pos.get('entry_order_id'), dict(pos))
                    for pid, pos in list(sess.active_positions.items())
                    if pos.get('symbol', '').upper() not in broker_pos_map
                ]
                with sess.lock:
                    for pid, sym, entry_oid, _sp in stale:
                        sess.active_positions.pop(pid, None)
                        sess.entry_counts.pop(sym, None)
                        sess.attempted_symbols.discard(sym)

                # 1b — patch missing avg_entry_price from broker
                with sess.lock:
                    for _pid, _pos in list(sess.active_positions.items()):
                        _sym = _pos.get('symbol', '').upper()
                        _bp  = broker_pos_map.get(_sym)
                        if not _bp or _pos.get('avg_entry_price'):
                            continue
                        _fp = float(_bp.avg_entry_price or _bp.current_price or 0)
                        if not _fp:
                            continue
                        _tgt = float(_pos.get('profit_target_pct', 5.0))
                        _stp = float(_pos.get('stop_loss_pct', 2.5))
                        _pos['avg_entry_price'] = _fp
                        _pos['entry_price']     = _fp
                        _pos['profit_target']   = round(_fp * (1 + _tgt / 100), 2)
                        _pos['stop_loss']       = round(_fp * (1 - _stp / 100), 2)
                        try:
                            db_manager.update_brown_position_entry(
                                _pid, _fp, int(abs(float(_bp.qty or 0))))
                        except Exception:
                            pass
                        _add_brown_log('info',
                            f'{_sym}: avg_entry_price confirmed from broker on restart = ${_fp:.2f}',
                            user_id=user_id)

                # Outside the lock: recovery of exit trades for stale positions
                for pid, sym, entry_oid, stale_pos in stale:
                    entry_price  = float(stale_pos.get('entry_price', 0) or 0)
                    pos_type     = stale_pos.get('position_type', 'day')
                    entry_date   = (stale_pos.get('entry_time', '') or '')[:10] or _last_trading_date()
                    exit_written = False
                    try:
                        existing_sells = db_manager.get_trades(symbol=sym, start_date=entry_date, limit=20)
                        has_db_sell = any(
                            t.get('side') in ('S', 'SS') and t.get('source') == 'brownbot'
                            for t in (existing_sells or [])
                        )
                    except Exception:
                        has_db_sell = False

                    if not has_db_sell and entry_oid and sess.broker:
                        try:
                            filled = sess.broker.get_orders_history(status='filled', symbols=[sym], limit=50)
                            sell_order = next((
                                o for o in (filled or [])
                                if o.get('side', '').lower() in ('sell', 'sell_short')
                                and o.get('filled_avg_price')
                                and str(o.get('filled_at', '') or '')[:10] >= entry_date
                            ), None)
                            if sell_order:
                                fill_price       = float(sell_order['filled_avg_price'])
                                fill_qty         = int(sell_order.get('filled_qty') or sell_order.get('qty') or 0)
                                fill_date        = str(sell_order.get('filled_at', '') or '')[:10] or entry_date
                                avg_entry        = float(stale_pos.get('avg_entry_price') or entry_price or 0)
                                realized_pnl     = round((fill_price - avg_entry) * fill_qty, 2) if avg_entry else 0.0
                                realized_pnl_pct = round((fill_price - avg_entry) / avg_entry * 100, 2) if avg_entry else 0.0
                                fill_time_str    = str(sell_order.get('filled_at') or datetime.now().isoformat())
                                db_manager.add_trade({
                                    'trade_id':      f'BROWN_EXIT_{sym}_{sell_order["order_id"]}',
                                    'symbol':        sym,
                                    'side':          'S',
                                    'quantity':      fill_qty,
                                    'price':         fill_price,
                                    'route':         'SMAT',
                                    'trade_time':    fill_time_str,
                                    'order_id':      str(sell_order['order_id']),
                                    'liquidity':     None,
                                    'ecn_fee':       0.0,
                                    'pnl':           realized_pnl,
                                    'trade_date':    fill_date or _last_trading_date(),
                                    'position_type': pos_type,
                                    'days_held':     None,
                                    'source':        'brownbot',
                                    'broker':        sess.broker.name,
                                    'user_id':       user_id,
                                })
                                db_manager.close_brown_position(
                                    pid, fill_price, str(sell_order['order_id']),
                                    'RECOVERED_ON_RESTART', realized_pnl, realized_pnl_pct,
                                    fill_time_str)
                                exit_written = True
                                _add_brown_log('info',
                                    f'{sym}: recovered exit trade on restart — '
                                    f'{fill_qty} @ ${fill_price:.2f}, P&L {"+$" if realized_pnl >= 0 else "-$"}{abs(realized_pnl):.2f}',
                                    user_id=user_id)
                        except Exception as _rec_err:
                            app_logger.debug(f'BrownBot startup recovery check {sym}: {_rec_err}')

                    if entry_oid and not has_db_sell and not exit_written:
                        try:
                            if sess.broker:
                                sess.broker.cancel_order(entry_oid)
                        except Exception:
                            pass
                        db_manager.delete_buy_trade_by_order_id(entry_oid)
                        db_manager.delete_brown_position(pid, user_id=user_id)
                        try:
                            db_manager.update_brown_order_fill(entry_oid, 0, 0, status='cancelled')
                        except Exception:
                            pass
                        app_logger.info(f'BrownBot startup: deleted phantom entry {sym} (entry_oid={entry_oid})')

                if stale:
                    _add_brown_log('info',
                        f'Startup: removed {len(stale)} position(s) not in broker '
                        f'({", ".join(sym for _, sym, _, _ in stale)})',
                        user_id=user_id)

                # 2 — adopt orphans
                config = db_manager.get_brown_bot_config(user_id)
                swing_tgt_pct = float(config.get('swing_profit_target_pct', 15.0))
                swing_stp_pct = float(config.get('swing_stop_loss_pct', 7.0))
                day_tgt_pct   = float(config.get('day_profit_target_pct', 5.0))
                day_stp_pct   = float(config.get('day_stop_loss_pct', 2.5))
                max_swing     = int(config.get('max_concurrent_swing', 5))
                max_day       = int(config.get('max_concurrent_day', 3))
                import pytz as _pytz_o
                _today_str_o = datetime.now(_pytz_o.timezone('US/Eastern')).strftime('%Y-%m-%d')
                adopted = 0
                for sym_up, bp in broker_pos_map.items():
                    if sym_up not in tracked_syms:
                        entry_price = float(bp.avg_entry_price or bp.current_price or 0)
                        pid = f'BROWN_{sym_up}_{int(time.time())}_{adopted}'
                        position_type = 'swing'
                        try:
                            recent_t = db_manager.get_trades(
                                symbol=sym_up, start_date=_today_str_o,
                                end_date=_today_str_o, limit=5, user_id=user_id)
                            buy_rec = next(
                                (t for t in recent_t
                                 if t.get('side') == 'B' and t.get('source') == 'brownbot'),
                                None)
                            if buy_rec:
                                pt = buy_rec.get('position_type', 'swing')
                                position_type = 'day' if pt in ('day', 'brown_day') else 'swing'
                        except Exception:
                            pass
                        use_tgt_pct = day_tgt_pct if position_type == 'day' else swing_tgt_pct
                        use_stp_pct = day_stp_pct if position_type == 'day' else swing_stp_pct
                        with sess.lock:
                            cur_swing = sum(1 for p in sess.active_positions.values()
                                            if p.get('position_type') in ('swing', 'brown_swing'))
                            cur_day   = sum(1 for p in sess.active_positions.values()
                                            if p.get('position_type') in ('day', 'brown_day'))
                        cap_exceeded = (
                            (position_type == 'swing' and cur_swing >= max_swing) or
                            (position_type == 'day'   and cur_day   >= max_day)
                        )
                        if cap_exceeded:
                            cap_val = max_swing if position_type == 'swing' else max_day
                            cur_val = cur_swing  if position_type == 'swing' else cur_day
                            _add_brown_log('warning',
                                f'{position_type.upper()} cap {cap_val} exceeded by orphan {sym_up} '
                                f'({cur_val + 1} {position_type} positions) — tracking for exit only',
                                user_id=user_id)
                        pos = {
                            'position_id':       pid,
                            'symbol':            sym_up,
                            'position_type':     position_type,
                            'entry_price':       entry_price,
                            'quantity':          int(abs(float(bp.qty or 0))),
                            'profit_target':     round(entry_price * (1 + use_tgt_pct / 100), 2) if entry_price else None,
                            'profit_target_pct': use_tgt_pct,
                            'stop_loss':         round(entry_price * (1 - use_stp_pct / 100), 2) if entry_price else None,
                            'stop_loss_pct':     use_stp_pct,
                            'entry_time':        datetime.now().isoformat(),
                            'entry_time_epoch':  time.time(),
                            'unrealized_pnl':    float(bp.unrealized_pnl or 0),
                        }
                        with sess.lock:
                            sess.active_positions[pid] = pos
                            sess.attempted_symbols.add(sym_up)
                            sess.entry_counts[sym_up] = sess.entry_counts.get(sym_up, 0) + 1
                        db_manager.save_brown_position(pid, pos, user_id=user_id)
                        adopted += 1
                        _add_brown_log('warning',
                            f'Adopted orphan {position_type} position: {sym_up} @ ${entry_price:.2f} '
                            f'(was in broker but not tracked — targets set from current config)',
                            user_id=user_id)
                if not stale and not adopted:
                    _add_brown_log('info', 'Startup check: all positions confirmed in sync with broker', user_id=user_id)
            except Exception as _ve:
                _add_brown_log('warning', f'Broker position verification failed (keeping DB positions): {_ve}', user_id=user_id)
    except Exception as _e:
        _add_brown_log('warning', f'Position restore from DB failed: {_e}', user_id=user_id)

    sess.running = True
    sess.scanner_thread = threading.Thread(
        target=_brown_bot_scanner_loop, args=(user_id,), daemon=True, name=f'BrownBotScanner-{user_id}'
    )
    sess.scanner_thread.start()
    sess.exit_thread = threading.Thread(
        target=_brown_bot_exit_loop, args=(user_id,), daemon=True, name=f'BrownBotExits-{user_id}'
    )
    sess.exit_thread.start()
    sess.order_monitor_thread = threading.Thread(
        target=_brown_order_monitor_loop, args=(user_id,), daemon=True, name=f'BrownBotOrderMonitor-{user_id}'
    )
    sess.order_monitor_thread.start()
    _add_brown_log('info', 'BrownBot scanner + exit + order-monitor loops launched', user_id=user_id)
    return jsonify({'success': True, 'message': 'BrownBot started'})


@app.route('/api/brown-bot/stop', methods=['POST'])
@require_auth
def stop_brown_bot():
    """Stop the requesting user's BrownBot session."""
    user_id = request.user.get('id', 1)
    is_super = request.user.get('system_role') in ('super_admin', 'dev_master')

    # Admins can stop any session by passing ?user_id=<uid> in the query string
    target_uid = user_id
    if is_super and request.args.get('user_id'):
        try:
            target_uid = int(request.args['user_id'])
        except (ValueError, TypeError):
            pass

    sess = _brown_sessions.get(target_uid)
    if not sess or not sess.running:
        return jsonify({'success': False, 'error': 'BrownBot is not running'})
    if target_uid != user_id and not is_super:
        return jsonify({'success': False, 'error': 'Only the user who started BrownBot (or a super admin) can stop it.'})

    sess.running = False
    # Short joins only — long joins block the eventlet greenlet.
    if sess.scanner_thread and sess.scanner_thread.is_alive():
        sess.scanner_thread.join(timeout=3)
    if sess.exit_thread and sess.exit_thread.is_alive():
        sess.exit_thread.join(timeout=3)
    if sess.order_monitor_thread and sess.order_monitor_thread.is_alive():
        sess.order_monitor_thread.join(timeout=3)
    _add_brown_log('info', 'BrownBot stopped', user_id=target_uid)
    with _brown_sessions_lock:
        _brown_sessions.pop(target_uid, None)
    return jsonify({'success': True, 'message': 'BrownBot stopped'})


@app.route('/api/brown-bot/close-all', methods=['POST'])
@require_auth
def brown_bot_close_all():
    """Close every position in the Alpaca account using the bulk endpoint.
    Marks positions _exit_pending and writes exit trades to DB.
    Memory cleanup is deferred to get_brown_bot_status once broker confirms fills."""
    current_user_id = request.user.get('id', 1)
    is_super = request.user.get('system_role') in ('super_admin', 'dev_master')
    sess = _brown_sessions.get(current_user_id)
    if sess and sess.running and sess.user_id != current_user_id and not is_super:
        return jsonify({'success': False, 'error': 'Cannot close positions — bot session belongs to another user.'})

    broker = (sess.broker if sess else None) or _get_broker(current_user_id)
    if not broker:
        return jsonify({'success': False, 'error': 'No broker available'})

    try:
        closed = broker.close_all_positions()
    except Exception as e:
        _add_brown_log('error', f'Close-all failed: {e}', user_id=current_user_id)
        return jsonify({'success': False, 'error': str(e)})

    closed_symbols = [c['symbol'] for c in closed]
    _add_brown_log('warning',
        f'CLOSE ALL: {len(closed)} position(s) submitted — {", ".join(closed_symbols) or "none"}', user_id=current_user_id)

    # Build a symbol→order_id map from the broker response for order logging
    closeall_order_map = {c['symbol']: c.get('order_id') for c in closed}

    # Write exit trades and close position records for every active position
    # not already being closed. Skip _exit_pending — previous close-all handled them.
    now_str = datetime.now().isoformat()
    _trade_date = _last_trading_date()
    _sess_ca = _brown_sessions.get(current_user_id)
    _active_ca  = _sess_ca.active_positions if _sess_ca else {}
    _lock_ca    = _sess_ca.lock if _sess_ca else threading.Lock()
    with _lock_ca:
        snapshot = {
            pid: pos for pid, pos in _active_ca.items()
            if not pos.get('_exit_pending')
        }

    for pid, pos in snapshot.items():
        sym         = pos.get('symbol', '').upper()
        exit_price  = float(pos.get('_current_price') or pos.get('entry_price', 0))
        avg_entry   = float(pos.get('avg_entry_price') or pos.get('entry_price', 0))
        quantity    = int(pos.get('quantity', 0))
        pos_type    = pos.get('position_type', 'day')
        order_id    = closeall_order_map.get(sym)
        realized    = round((exit_price - avg_entry) * quantity, 2) if avg_entry else round(pos.get('unrealized_pnl', 0), 2)
        realized_pct = round((exit_price - avg_entry) / avg_entry * 100, 2) if avg_entry else 0.0

        # Log exit order in the immutable orders table
        if order_id:
            try:
                db_manager.add_brown_order({
                    'order_id':       str(order_id),
                    'position_id':    pid,
                    'symbol':         sym,
                    'side':           'S',
                    'order_type':     'exit',
                    'position_type':  pos_type,
                    'submitted_qty':  quantity,
                    'submitted_price': exit_price,
                    'status':         'pending',
                    'exit_reason':    'CLOSE_ALL',
                    'submitted_at':   now_str,
                    'trade_date':     _trade_date,
                }, user_id=current_user_id)
            except Exception:
                pass

        try:
            db_manager.add_trade({
                'trade_id':      f'BROWN_CLOSEALL_{sym}_{int(time.time())}',
                'symbol':        sym,
                'side':          'S',
                'quantity':      quantity,
                'price':         exit_price,
                'route':         'SMAT',
                'trade_time':    now_str,
                'order_id':      order_id,
                'liquidity':     None,
                'ecn_fee':       0.0,
                'pnl':           realized,
                'trade_date':    _trade_date,
                'position_type': pos_type,
                'days_held':     None,
                'source':        'brownbot',
                'broker':        broker.name if broker else None,
                'user_id':       current_user_id,
            })
        except Exception as _e:
            app_logger.debug(f'close-all DB trade write failed for {sym}: {_e}')

        # Mark position as closed (preserves P&L history) instead of deleting
        try:
            db_manager.close_brown_position(
                pid, exit_price, order_id, 'CLOSE_ALL',
                realized, realized_pct, now_str
            )
        except Exception as _e:
            app_logger.debug(f'close-all position close failed for {sym}: {_e}')

    # Mark positions as pending-close rather than clearing immediately.
    with _lock_ca:
        for pos in _active_ca.values():
            pos['_exit_pending'] = True
    _add_brown_log('warning', f'CLOSE ALL: {len(closed)} order(s) submitted', user_id=current_user_id)

    return jsonify({
        'success': True,
        'closed':  len(closed),
        'symbols': closed_symbols,
    })


@app.route('/api/brown-bot/config', methods=['GET'])
@require_auth
def get_brown_bot_config_endpoint():
    """Return current BrownBot config."""
    try:
        cfg = db_manager.get_brown_bot_config(request.user.get('id', 1))
        return jsonify({'success': True, 'config': cfg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/config', methods=['POST'])
@require_auth
def update_brown_bot_config_endpoint():
    """Persist BrownBot config."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        ok, msg = db_manager.update_brown_bot_config(data, request.user.get('id', 1))
        if not ok:
            return jsonify({'success': False, 'error': msg}), 500
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/logs', methods=['GET'])
@require_auth
def get_brown_bot_logs():
    """Return recent BrownBot activity logs for the requesting user's session."""
    user_id = request.user.get('id', 1)
    sess = _brown_sessions.get(user_id)
    logs = sess.logs if sess else []
    return jsonify({'success': True, 'logs': list(reversed(logs[-100:]))})


@app.route('/api/brown-bot/risk-status', methods=['GET'])
@require_auth
def get_brown_bot_risk_status():
    """Return live risk snapshot: daily P&L, open positions, circuit breaker state."""
    current_user_id = request.user.get('id', 1)
    sess = _brown_sessions.get(current_user_id)

    if sess and sess.risk_manager is not None:
        with sess.lock:
            positions = dict(sess.active_positions)
        unrealized_total = sum(p.get('unrealized_pnl', 0) for p in positions.values())
        snapshot = sess.risk_manager.status(positions, unrealized_pnl=unrealized_total)
    else:
        # Bot not running for this user — return defaults from their config
        try:
            config = db_manager.get_brown_bot_config(current_user_id)
        except Exception:
            config = {}
        today = _last_trading_date()
        try:
            realized_pnl = db_manager.get_brown_daily_realized_pnl(today, user_id=current_user_id)
        except Exception:
            realized_pnl = 0.0
        unrealized_total = 0.0
        total_pnl = realized_pnl + unrealized_total
        max_loss = float(config.get('max_daily_loss', -500.0))
        snapshot = {
            'daily_pnl':          round(total_pnl, 2),
            'realized_pnl':       round(realized_pnl, 2),
            'unrealized_pnl':     round(unrealized_total, 2),
            'max_daily_loss':     max_loss,
            'open_day':           0,
            'max_concurrent_day': int(config.get('max_concurrent_day', 3)),
            'open_swing':         0,
            'max_concurrent_swing': int(config.get('max_concurrent_swing', 5)),
            'circuit_breaker_open': total_pnl <= max_loss,
        }
    # Per-ticker P&L breakdown for today
    try:
        _today = _last_trading_date()
        snapshot['pnl_by_ticker'] = db_manager.get_brown_positions_pnl_by_ticker(_today, user_id=current_user_id)
    except Exception:
        snapshot['pnl_by_ticker'] = []

    return jsonify({'success': True, 'risk': snapshot})


@app.route('/api/admin/bots/status', methods=['GET'])
@require_auth
@require_role('super_admin', 'dev_master', 'bot_admin')
def admin_bots_status():
    """Admin view: return a summary of every active BrownBot session across all users."""
    sessions_out = []
    with _brown_sessions_lock:
        snapshot = dict(_brown_sessions)
    for uid, sess in snapshot.items():
        if not sess.running:
            continue
        # Fetch username from DB for display
        try:
            user_row = db_manager.get_user_by_id(uid)
            username = (user_row.get('username') or user_row.get('email') or f'uid:{uid}') if user_row else f'uid:{uid}'
        except Exception:
            username = f'uid:{uid}'
        with sess.lock:
            pos_count   = len(sess.active_positions)
            unrealized  = round(sum(p.get('unrealized_pnl', 0) for p in sess.active_positions.values()), 2)
            entry_count = sum(sess.entry_counts.values())
        broker_name = sess.broker.name if sess.broker else None
        sessions_out.append({
            'user_id':          uid,
            'username':         username,
            'broker':           broker_name,
            'active_positions': pos_count,
            'unrealized_pnl':   unrealized,
            'entries_today':    entry_count,
            'stats':            dict(sess.stats),
        })
    return jsonify({'success': True, 'sessions': sessions_out, 'count': len(sessions_out)})


# ==============================================================================
# Broker abstraction layer — /api/broker/*
# ==============================================================================

@app.route('/api/broker/supported', methods=['GET'])
def get_supported_brokers():
    """Return list of all supported broker names and their required config keys."""
    try:
        from bot.broker import get_supported_brokers as _get_brokers
        return jsonify({'success': True, 'brokers': _get_brokers()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/configs', methods=['GET'])
@require_auth
def list_broker_configs():
    """Return all saved broker configs for the current user (no secrets in response)."""
    user_id = request.user.get('id', 1)
    configs = db_manager.get_broker_configs(user_id)
    return jsonify({'success': True, 'configs': configs})


@app.route('/api/broker/config/<broker_name>', methods=['POST'])
@require_auth
def save_broker_config(broker_name):
    """
    Save (upsert) a broker config.  Pass api_key / api_secret only when the user
    explicitly updates them — omitting them preserves the stored values.
    """
    user_id = request.user.get('id', 1)
    data = request.get_json() or {}
    ok, msg = db_manager.upsert_broker_config(broker_name, data, user_id)
    if ok:
        _invalidate_broker_cache(user_id)
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'error': msg}), 400


@app.route('/api/broker/activate/<broker_name>', methods=['PUT'])
@require_auth
def activate_broker(broker_name):
    """Switch the active broker without touching credentials."""
    user_id = request.user.get('id', 1)
    ok, msg = db_manager.activate_broker(broker_name, user_id)
    if ok:
        _invalidate_broker_cache(user_id)
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'error': msg}), 400


@app.route('/api/broker/config/<broker_name>', methods=['DELETE'])
@require_auth
def delete_broker_config(broker_name):
    """Remove a broker config (revoke access)."""
    user_id = request.user.get('id', 1)
    ok, msg = db_manager.delete_broker_config(broker_name, user_id)
    if ok:
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'error': msg}), 400


@app.route('/api/broker/test/<broker_name>', methods=['POST'])
@require_auth
def test_broker_connection(broker_name):
    """
    Attempt to connect with the stored credentials and return live account info.
    Used by the UI "Test Connection" button.
    """
    user_id = request.user.get('id', 1)
    row = db_manager.get_broker_config(broker_name, user_id)
    if not row:
        return jsonify({'success': False,
                        'error': f'No config saved for {broker_name}'}), 404
    try:
        from bot.broker import create_broker
        cfg = {
            'api_key':      row.get('api_key', ''),
            'api_secret':   row.get('api_secret', ''),
            'account_id':   row.get('account_id', ''),
            'paper':        bool(row.get('paper_trading', 1)),
            **row.get('extra_config', {}),
        }
        broker = create_broker(broker_name, cfg)
        connected = broker.connect()
        if connected:
            account = broker.get_account()
            return jsonify({
                'success':      True,
                'connected':    True,
                'broker':       broker.name,
                'account_id':   account.account_id,
                'equity':       account.equity,
                'buying_power': account.buying_power,
                'paper':        account.paper_trading,
            })
        return jsonify({'success': False, 'connected': False,
                        'error': 'Could not connect — check credentials'})
    except Exception as e:
        return jsonify({'success': False, 'connected': False, 'error': str(e)}), 500


@app.route('/api/broker/candidates', methods=['GET'])
def get_broker_candidates():
    """Alias kept for future use — see /api/broker/supported."""
    return get_supported_brokers()


@app.route('/api/brown-bot/swing-backtest', methods=['POST'])
@require_auth
def swing_backtest():
    """
    Run a swing trade backtest over collected screener history (Option B).

    Body params:
      start_date        YYYY-MM-DD
      end_date          YYYY-MM-DD
      grade_filter      'A' | 'AB' | 'ABC'  (default 'AB')
      bias_filter       'Bullish' | 'Any'   (default 'Bullish')
      profit_target_pct float  (default 15)
      stop_loss_pct     float  (default 7)
      max_hold_days     int    (default 20)
    """
    import requests as _req
    try:
        body = request.get_json(force=True) or {}
        start_date = body.get('start_date', '')
        end_date   = body.get('end_date', '')
        if not (start_date and end_date):
            return jsonify({'success': False, 'error': 'start_date and end_date required'}), 400

        grade_filter      = body.get('grade_filter', 'AB')
        bias_filter       = body.get('bias_filter', 'Bullish')
        profit_target_pct = float(body.get('profit_target_pct', 15.0))
        stop_loss_pct     = float(body.get('stop_loss_pct', 7.0))
        max_hold_days     = int(body.get('max_hold_days', 20))

        rows = db_manager.get_swing_screener_history(start_date, end_date)
        _data_source = 'screener_history'
        if not rows:
            # Fall back to swing_daily_picks (populated by Swing tab AI pipeline).
            # Picks have grade/bias but no price — the simulation will use next-day open.
            daily_picks = db_manager.get_swing_picks_range(start_date, end_date)
            if not daily_picks:
                return jsonify({'success': True, 'trades': [], 'stats': {},
                                'message': 'No screener history in this date range yet — '
                                           'data collection starts automatically when BrownBot runs.'})
            _data_source = 'daily_picks'
            for day_row in daily_picks:
                for pick in day_row.get('picks', []):
                    if not pick.get('ticker'):
                        continue
                    rows.append({
                        'date':        day_row['date'],
                        'ticker':      pick['ticker'],
                        'ai_grade':    pick.get('grade'),
                        'ai_bias':     pick.get('bias'),
                        'ai_summary':  pick.get('reason'),
                        'price':       None,
                        'entry_price': None,
                        'sector':      None,
                        'rsi14':       None,
                        'above_sma20': None,
                        'was_entered': False,
                    })

        # Filter by grade and bias
        valid_grades = list(grade_filter.upper())  # 'AB' → ['A','B']
        candidates = [
            r for r in rows
            if r.get('ai_grade') in valid_grades
            and (bias_filter == 'Any' or r.get('ai_bias') == bias_filter)
        ]

        if not candidates:
            return jsonify({'success': True, 'trades': [], 'stats': {},
                            'message': f'No candidates match grade={grade_filter} bias={bias_filter} in this period.'})

        # Fetch forward daily bars — check cache first, then Alpaca
        ak  = os.environ.get('ALPACA_API_KEY', '')
        aks = os.environ.get('ALPACA_API_SECRET', '')
        alpaca_hdrs = {'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': aks}

        def _get_forward_bars(ticker, from_date, n_days):
            """Return sorted daily bars from from_date + 1 trading day onward."""
            from datetime import date as _date, timedelta as _td
            import datetime as _dtmod
            end = (_dtmod.datetime.strptime(from_date, '%Y-%m-%d').date()
                   + _td(days=n_days * 2)).isoformat()  # buffer for weekends/holidays
            cached = db_manager.get_swing_daily_bars(ticker, from_date, end)
            forward = [b for b in cached if b['date'] > from_date]
            if forward:
                return forward

            if not (ak and aks):
                return []
            try:
                resp = _req.get(
                    f'https://data.alpaca.markets/v2/stocks/{ticker}/bars',
                    headers=alpaca_hdrs,
                    params={'timeframe': '1Day', 'start': from_date, 'end': end,
                            'limit': 60, 'adjustment': 'raw', 'feed': 'iex'},
                    timeout=15,
                )
                resp.raise_for_status()
                raw_bars = resp.json().get('bars') or []
                bars = [{'date': b['t'][:10], 'open': b['o'], 'high': b['h'],
                         'low': b['l'], 'close': b['c'], 'volume': b['v']}
                        for b in raw_bars]
                db_manager.cache_swing_daily_bars(ticker, bars)
                return [b for b in bars if b['date'] > from_date]
            except Exception as _e:
                app_logger.debug(f'swing_backtest: bar fetch failed {ticker}: {_e}')
                return []

        def _simulate_trade(entry_price, bars, profit_pct, stop_pct, max_hold):
            target = entry_price * (1 + profit_pct / 100)
            stop   = entry_price * (1 - stop_pct / 100)
            for i, bar in enumerate(bars[:max_hold]):
                if bar['low'] <= stop:
                    exit_price = stop
                    return exit_price, i + 1, 'stop'
                if bar['high'] >= target:
                    exit_price = target
                    return exit_price, i + 1, 'target'
            # max hold reached — exit at last bar close
            if bars[:max_hold]:
                last = bars[:max_hold][-1]
                return last['close'], min(len(bars), max_hold), 'max_hold'
            return None, 0, 'no_data'

        trades = []
        # Deduplicate: one entry per (date, ticker)
        seen = set()
        for row in candidates:
            key = (row['date'], row['ticker'])
            if key in seen:
                continue
            seen.add(key)

            entry_price = row.get('entry_price') or row.get('price') or None
            bars = _get_forward_bars(row['ticker'], row['date'], max_hold_days + 10)
            if not bars:
                continue
            if not entry_price:
                # daily_picks fallback: no intraday price stored — use next-day open
                entry_price = bars[0].get('open')
            if not entry_price:
                continue
            exit_price, days_held, exit_reason = _simulate_trade(
                entry_price, bars, profit_target_pct, stop_loss_pct, max_hold_days)

            if exit_price is None:
                continue

            pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2)
            trades.append({
                'date':        row['date'],
                'ticker':      row['ticker'],
                'grade':       row.get('ai_grade'),
                'bias':        row.get('ai_bias'),
                'sector':      row.get('sector'),
                'entry_price': round(entry_price, 2),
                'exit_price':  round(exit_price, 2),
                'pnl_pct':     pnl_pct,
                'days_held':   days_held,
                'exit_reason': exit_reason,
                'was_entered': bool(row.get('was_entered')),
                'rsi14':       row.get('rsi14'),
                'above_sma20': row.get('above_sma20'),
            })

        # Aggregate stats
        total   = len(trades)
        wins    = [t for t in trades if t['pnl_pct'] > 0]
        losses  = [t for t in trades if t['pnl_pct'] <= 0]
        win_rate = round(len(wins) / total * 100, 1) if total else 0
        avg_pnl  = round(sum(t['pnl_pct'] for t in trades) / total, 2) if total else 0
        avg_win  = round(sum(t['pnl_pct'] for t in wins) / len(wins), 2) if wins else 0
        avg_loss = round(sum(t['pnl_pct'] for t in losses) / len(losses), 2) if losses else 0
        by_reason = {}
        for t in trades:
            r = t['exit_reason']
            by_reason[r] = by_reason.get(r, 0) + 1

        stats = {
            'total_trades':   total,
            'wins':           len(wins),
            'losses':         len(losses),
            'win_rate_pct':   win_rate,
            'avg_pnl_pct':    avg_pnl,
            'avg_win_pct':    avg_win,
            'avg_loss_pct':   avg_loss,
            'total_pnl_pct':  round(sum(t['pnl_pct'] for t in trades), 2),
            'exit_breakdown': by_reason,
            'date_range':     f'{start_date} → {end_date}',
            'grade_filter':   grade_filter,
            'bias_filter':    bias_filter,
            'data_source':    _data_source,
        }

        return jsonify({'success': True, 'trades': trades, 'stats': stats})

    except Exception as e:
        app_logger.error(f'swing_backtest error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/candidates', methods=['GET'])
@require_auth
def get_brown_bot_candidates():
    """Return gap-up scanner results filtered by config thresholds, merged with watchlist."""
    try:
        config = db_manager.get_brown_bot_config(request.user.get('id', 1))
        min_gap = config.get('min_gap_pct', 10.0)
        min_price = config.get('min_price', 5.0)
        max_price = config.get('max_price', 500.0)
        min_vol_m = config.get('min_volume_m', 0.5)

        from gap_up_detector import get_gap_up_stocks_for_frontend
        raw = get_gap_up_stocks_for_frontend()

        scanner_hits = []
        for s in raw:
            if s.get('gap_percent', 0) < min_gap:
                continue
            price = s.get('price', 0)
            if price < min_price or price > max_price:
                continue
            vol_m = s.get('volume', 0) / 1_000_000
            if vol_m < min_vol_m:
                continue
            scanner_hits.append({**s, 'source': 'scanner', 'trade_type': 'day', 'note': ''})

        watchlist = db_manager.get_brown_watchlist(request.user.get('id', 1))
        wl_symbols = {w['symbol'] for w in watchlist}
        scanner_symbols = {s['ticker'] for s in scanner_hits}

        # Mark scanner hits that are also on the watchlist
        for s in scanner_hits:
            if s['ticker'] in wl_symbols:
                s['on_watchlist'] = True

        # Build watchlist entries (enrich with scanner data if available)
        # Skip symbols already shown in the scanner section to avoid double-counting.
        scanner_map = {s['ticker']: s for s in scanner_hits}
        wl_entries = []
        for w in watchlist:
            if w['symbol'] in scanner_symbols:
                continue  # already visible in scanner section with on_watchlist badge
            base = scanner_map.get(w['symbol'], {
                'ticker': w['symbol'], 'price': None, 'gap_percent': None,
                'volume': None, 'company_name': w['symbol']
            })
            wl_entries.append({
                **base,
                'source': 'watchlist',
                'trade_type': w.get('trade_type', 'day'),
                'note': w.get('note', ''),
                'on_watchlist': True,
            })

        return jsonify({'success': True, 'scanner': scanner_hits, 'watchlist': wl_entries})
    except Exception as e:
        app_logger.error(f'Error fetching BrownBot candidates: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/swing-candidates', methods=['GET'])
@require_auth
def get_brown_bot_swing_candidates():
    """Return the latest BrownBot swing scanner AI picks, enriched with technicals."""
    try:
        _uid_sc = request.user.get('id', 1)
        _sess_sc = _brown_sessions.get(_uid_sc)
        _ai_cache  = _sess_sc.swing_ai_picks_cache    if _sess_sc else {'ts': 0.0, 'picks': []}
        _cand_cache = _sess_sc.swing_candidates_cache if _sess_sc else {'ts': 0.0, 'candidates': []}
        picks = list(_ai_cache.get('picks', []))
        cands_by_ticker = {c['ticker']: c for c in _cand_cache.get('candidates', [])}
        result = []
        for p in picks:
            ticker = p.get('ticker', '')
            tech = cands_by_ticker.get(ticker, {})
            result.append({
                'ticker':       ticker,
                'grade':        p.get('grade', ''),
                'bias':         p.get('bias', ''),
                'reason':       p.get('reason', ''),
                'entry_zone':   p.get('entry_zone', ''),
                'watch_for':    p.get('watch_for', ''),
                'risk':         p.get('risk', ''),
                'price':        tech.get('price') or p.get('price'),
                'chg_pct':      tech.get('chg_pct'),
                'volume_m':     tech.get('volume_m'),
                'market_cap_m': tech.get('market_cap_m'),
                'sma20':        tech.get('sma20'),
                'rsi14':        tech.get('rsi'),   # candidate dict uses 'rsi', not 'rsi14'
                'rel_vol':      tech.get('rel_vol'),
            })
        cache_ts = _ai_cache.get('ts', 0)
        return jsonify({
            'success': True,
            'picks': result,
            'cached_at': cache_ts,
            'count': len(result),
        })
    except Exception as e:
        app_logger.error(f'Error fetching BrownBot swing candidates: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/candidate-signals', methods=['GET'])
@require_auth
def get_brown_bot_candidate_signals():
    """Run intraday trend checks for a comma-separated list of symbols."""
    symbols_param = request.args.get('symbols', '')
    symbols = [s.strip().upper() for s in symbols_param.split(',') if s.strip()]
    if not symbols:
        return jsonify({'success': False, 'error': 'symbols param required'}), 400

    config = db_manager.get_brown_bot_config(request.user.get('id', 1))

    # Batch-fetch prices for all symbols in one Alpaca snapshot call.
    # Per-symbol get_real_stock_data would fire N snapshot requests concurrently and hit 429.
    batch_prices = {}
    try:
        batch_prices = _alpaca_snapshots(symbols)
    except Exception:
        pass  # fall back to 0.0 per-symbol below

    results = {}
    for i, sym in enumerate(symbols):
        if i > 0:
            time.sleep(0.15)  # 150 ms between intraday-bar fetches to stay under rate limit
        try:
            price = float((batch_prices.get(sym) or {}).get('price') or 0.0)
            if not price:
                quote = get_real_stock_data(sym)
                price = float(quote['current_price']) if quote else 0.0
            ok, checks, reason = _check_day_entry_signal(sym, price, price, config)
            results[sym] = {'ok': ok, 'checks': checks, 'reason': reason, 'price': price}
        except Exception as e:
            results[sym] = {'ok': None, 'checks': [], 'reason': str(e), 'price': 0}
    return jsonify({'success': True, 'signals': results})


def _alpaca_snapshots(tickers: list) -> dict:
    """Fetch latest price + session VWAP for multiple tickers via Alpaca snapshots API."""
    import requests as _req
    key    = os.environ.get('ALPACA_API_KEY', '')
    secret = os.environ.get('ALPACA_API_SECRET', '')
    if not key or not secret or not tickers:
        return {}
    try:
        resp = _req.get(
            'https://data.alpaca.markets/v2/stocks/snapshots',
            headers={'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret},
            params={'symbols': ','.join(t.upper() for t in tickers), 'feed': 'sip'},
            timeout=10,
        )
        if resp.status_code != 200:
            app_logger.debug(f'Alpaca snapshots HTTP {resp.status_code}')
            return {}
        result = {}
        for ticker, snap in resp.json().items():
            latest_trade = snap.get('latestTrade') or {}
            daily_bar    = snap.get('dailyBar') or {}
            price = latest_trade.get('p') or daily_bar.get('c')
            vwap  = daily_bar.get('vw')
            result[ticker] = {
                'price': round(float(price), 2) if price else None,
                'vwap':  round(float(vwap),  2) if vwap  else None,
            }
        return result
    except Exception as e:
        app_logger.debug(f'Alpaca snapshots error: {e}')
        return {}


@app.route('/api/brown-bot/live-prices', methods=['GET'])
@require_auth
def get_brown_bot_live_prices():
    """Return current price + session VWAP for a comma-separated list of tickers."""
    symbols_param = request.args.get('symbols', '')
    symbols = [s.strip().upper() for s in symbols_param.split(',') if s.strip()]
    if not symbols:
        return jsonify({'success': False, 'error': 'symbols param required'}), 400
    prices = _alpaca_snapshots(symbols)
    return jsonify({'success': True, 'prices': prices})


@app.route('/api/brown-bot/watchlist', methods=['GET'])
@require_auth
def get_brown_bot_watchlist():
    """Return current BrownBot watchlist."""
    try:
        return jsonify({'success': True, 'watchlist': db_manager.get_brown_watchlist(request.user.get('id', 1))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/watchlist', methods=['POST'])
@require_auth
def add_brown_bot_watchlist():
    """Add a symbol to the BrownBot watchlist."""
    data = request.get_json() or {}
    symbol = (data.get('symbol') or '').strip().upper()
    if not symbol:
        return jsonify({'success': False, 'error': 'symbol is required'}), 400
    note = data.get('note', '')
    trade_type = data.get('trade_type', 'day')
    if trade_type not in ('day', 'swing', 'auto'):
        trade_type = 'day'
    try:
        db_manager.add_to_brown_watchlist(symbol, note, trade_type, request.user.get('id', 1))
        _add_brown_log('info', f'Added {symbol} ({trade_type}) to watchlist')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/watchlist/<symbol>', methods=['DELETE'])
@require_auth
def remove_brown_bot_watchlist(symbol):
    """Remove a symbol from the BrownBot watchlist."""
    symbol = symbol.strip().upper()
    try:
        db_manager.remove_from_brown_watchlist(symbol, request.user.get('id', 1))
        _add_brown_log('info', f'Removed {symbol} from watchlist')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/unsubscribe-stocks', methods=['POST'])
def unsubscribe_stocks():
    """Unsubscribe from stock updates"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        data = request.get_json()
        tickers = data.get('tickers', [])
        
        success_count = 0
        for ticker in tickers:
            if trading_bot.unsubscribe_stock(ticker):
                success_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Unsubscribed from {success_count} stocks',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error unsubscribing stocks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/positions', methods=['GET'])
def get_bot_positions():
    """Get current bot positions"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        # Get active positions snapshot (thread-safe copy via get_status)
        status = trading_bot.get_status()
        positions_data = status.get('active_positions', [])
        
        return jsonify({
            'success': True,
            'data': {
                'positions': positions_data,
                'count': len(positions_data)
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting bot positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/config', methods=['GET', 'POST'])
def manage_bot_config():
    """Get or update bot configuration"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        if request.method == 'GET':
            # Get current configuration
            config = {
                'profit_target_pct': trading_bot.profit_target_pct,
                'stop_loss_pct': trading_bot.stop_loss_pct,
                'monitor_interval': trading_bot.monitor_interval
            }
            
            return jsonify({
                'success': True,
                'data': config,
                'timestamp': datetime.now().isoformat()
            })
        
        elif request.method == 'POST':
            # Update configuration using the update_strategies method to ensure active positions are updated
            data = request.get_json()
            app_logger.info(f"🔄 Updating bot configuration: {data}")
            
            # Use the update_strategies method to ensure active positions are recalculated
            success = trading_bot.update_strategies(data)
            
            if success:
                app_logger.info(f"🎯 Current bot config - Profit: {trading_bot.profit_target_pct}%, Stop: {trading_bot.stop_loss_pct}%, Interval: {trading_bot.monitor_interval}s")
                
                return jsonify({
                    'success': True,
                    'message': 'Bot configuration updated successfully',
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update bot configuration'
                }), 500
            
    except Exception as e:
        app_logger.error(f"Error managing bot config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/validate-config', methods=['GET'])
def validate_bot_config():
    """Validate current bot configuration"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        config = {
            'profit_target_pct': trading_bot.profit_target_pct,
            'stop_loss_pct': trading_bot.stop_loss_pct,
            'monitor_interval': trading_bot.monitor_interval,
            'is_running': trading_bot.is_running,
            'monitoring': trading_bot.monitoring,
            'active_positions_count': trading_bot.active_positions_count
        }
        
        app_logger.info(f"🔍 Bot config validation: {config}")
        
        return jsonify({
            'success': True,
            'data': config,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app_logger.error(f"Error validating bot config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/discover-positions', methods=['POST'])
def discover_positions():
    """Manually trigger position discovery"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        # Trigger position discovery
        trading_bot.discover_existing_positions()
        
        return jsonify({
            'success': True,
            'message': 'Position discovery completed',
            'data': {
                'active_positions': trading_bot.active_positions_count
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error discovering positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/panic-exit', methods=['POST'])
def panic_exit_all_positions():
    """Emergency panic exit - close all positions at market price"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        app_logger.warning("🚨 PANIC EXIT REQUESTED VIA API")
        
        # Execute panic exit
        result = trading_bot.panic_exit_all_positions()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'data': result,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error during panic exit'),
                'data': result,
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error during panic exit: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bot/das-connection', methods=['GET', 'POST'])
def manage_das_connection():
    """Manage DAS connection - GET to check status, POST to force reconnect"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        if request.method == 'GET':
            # Check DAS connection status
            das_connected = trading_bot.connect_to_das()
            
            return jsonify({
                'success': True,
                'data': {
                    'das_connected': das_connected,
                    'message': 'DAS Connected' if das_connected else 'DAS Not Connected'
                },
                'timestamp': datetime.now().isoformat()
            })
        
        elif request.method == 'POST':
            # Force reconnection to DAS
            # app_logger.info("🔄 Force reconnecting to DAS...")

            success = trading_bot.force_reconnect_das()

            if success:
                pass  # app_logger.info("✅ Successfully reconnected to DAS")
                return jsonify({
                    'success': True,
                    'message': 'Successfully reconnected to DAS',
                    'data': {
                        'das_connected': True
                    },
                    'timestamp': datetime.now().isoformat()
                })
            else:
                pass  # app_logger.error("❌ Failed to reconnect to DAS")
                return jsonify({
                    'success': False,
                    'error': 'Failed to reconnect to DAS. Please ensure DAS Trader is running.',
                    'data': {
                        'das_connected': False
                    }
                }), 500
            
    except Exception as e:
        pass  # app_logger.error(f"Error managing DAS connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Trades endpoints - placeholder removed, see Trade History API endpoints below

# Cache endpoints
@app.route('/api/cache/invalidate-gap-ups', methods=['POST'])
def invalidate_gap_ups_cache():
    """Invalidate gap-ups cache"""
    try:
        # Import and call the actual cache invalidation function
        from gap_up_cache import invalidate_gap_up_cache
        invalidate_gap_up_cache()
        
        app_logger.info("🗑️ Gap-ups cache manually invalidated via API")
        
        return jsonify({
            'success': True,
            'message': 'Gap-ups cache invalidated successfully',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error invalidating cache: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/debug/config', methods=['GET'])
def debug_config():
    """Debug endpoint to check current config values"""
    try:
        import config as config_module
        import importlib
        
        # Get current config values
        current_threshold = getattr(config_module, 'GAP_UP_MIN_PERCENTAGE', 'NOT_FOUND')
        
        # Try to reload and get fresh values
        try:
            importlib.reload(config_module)
            reloaded_threshold = getattr(config_module, 'GAP_UP_MIN_PERCENTAGE', 'NOT_FOUND')
        except Exception as e:
            reloaded_threshold = f"ERROR: {e}"
        
        return jsonify({
            'success': True,
            'data': {
                'current_threshold': current_threshold,
                'reloaded_threshold': reloaded_threshold,
                'config_file_path': config_module.__file__,
                'config_attributes': [attr for attr in dir(config_module) if not attr.startswith('_')]
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error in debug config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# AI Agent endpoints
@app.route('/api/ai-agent/start-session', methods=['POST'])
@require_auth
def start_ai_session():
    """Start AI agent session"""
    if not AI_AGENT_AVAILABLE:
        return jsonify({'success': False, 'error': 'AI Agent not available. Check ANTHROPIC_API_KEY.'}), 500
    return jsonify({
        'success': True,
        'data': {'status': 'active', 'message': 'AI Agent ready'},
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/ai-agent/chat', methods=['POST'])
@require_auth
def ai_chat():
    """Handle AI chat messages"""
    if not AI_AGENT_AVAILABLE:
        return jsonify({'success': False, 'error': 'AI Agent not available. Check ANTHROPIC_API_KEY.'}), 500
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400

        user_id = str(request.user.get('id', request.user.get('username', 'unknown')))
        result = _ai_agent.process_message(message, user_id)

        if result['success']:
            return jsonify({
                'success': True,
                'data': {
                    'response': result['response'],
                    'tools_used': result.get('tools_used', []),
                    'user_id': user_id
                }
            })
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500

    except Exception as e:
        app_logger.error(f"Error in AI chat: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai-agent/history', methods=['GET'])
@require_auth
def get_ai_history():
    """Get AI conversation history for the current user"""
    if not AI_AGENT_AVAILABLE:
        return jsonify({'success': False, 'error': 'AI Agent not available.'}), 500
    try:
        user_id = str(request.user.get('id', request.user.get('username', 'unknown')))
        history = _ai_agent.get_conversation_history(user_id)
        return jsonify({
            'success': True,
            'data': {'history': history, 'user_id': user_id},
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting AI history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai-agent/clear-history', methods=['POST'])
@require_auth
def clear_ai_history():
    """Clear AI conversation history for the current user"""
    if not AI_AGENT_AVAILABLE:
        return jsonify({'success': False, 'error': 'AI Agent not available.'}), 500
    try:
        user_id = str(request.user.get('id', request.user.get('username', 'unknown')))
        success = _ai_agent.clear_conversation_history(user_id)
        return jsonify({
            'success': success,
            'data': {'message': 'Conversation history cleared' if success else 'Failed to clear history'},
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error clearing AI history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Strategies endpoints
@app.route('/api/strategies/get')
def get_strategies():
    """Get available strategies"""
    try:
        # Placeholder - implement actual strategy retrieval
        strategies = [
            {'id': 'gap_up', 'name': 'Gap Up Strategy', 'enabled': True},
            {'id': 'breakout', 'name': 'Breakout Strategy', 'enabled': False},
            {'id': 'momentum', 'name': 'Momentum Strategy', 'enabled': False}
        ]
        
        return jsonify({
            'success': True,
            'data': strategies,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting strategies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Trade History API endpoints
@app.route('/api/trades', methods=['GET'])
@require_auth
def get_trades():
    """Get trade history with optional filtering"""
    try:
        from database import db_manager
        current_user_id = request.user.get('id', 1)

        # Get query parameters
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))

        # Validate limit
        if limit > 1000:
            limit = 1000

        # Get trades from database
        trades = db_manager.get_trades(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            user_id=current_user_id,
        )

        # Get summary statistics
        summary = db_manager.get_trade_summary(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'trades': trades,
                'summary': summary
            },
            'timestamp': datetime.now().isoformat(),
            'count': len(trades)
        })
    except Exception as e:
        app_logger.error(f"Error getting trades: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trades', methods=['POST'])
def add_trade():
    """Add a new trade to the database"""
    try:
        from database import db_manager
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['trade_id', 'symbol', 'side', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Add trade to database
        success, message = db_manager.add_trade(data)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
    except Exception as e:
        app_logger.error(f"Error adding trade: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trades/import-das', methods=['POST'])
def import_das_trades():
    """Import trades from DAS trades data"""
    if not DAS_ENABLED:
        return jsonify({'success': False, 'error': 'DAS integration is disabled'}), 503

    try:
        from database import db_manager
        
        data = request.get_json()
        if not data or 'das_trades_text' not in data:
            return jsonify({
                'success': False,
                'error': 'No DAS trades data provided'
            }), 400
        
        # Parse DAS trades data
        trades = db_manager.parse_das_trades_data(data['das_trades_text'])
        
        if not trades:
            return jsonify({
                'success': False,
                'error': 'No valid trades found in the provided data'
            }), 400
        
        # Add trades to database
        added_count = 0
        errors = []
        
        for trade in trades:
            success, message = db_manager.add_trade(trade)
            if success:
                added_count += 1
            else:
                errors.append(f"Trade {trade['trade_id']}: {message}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {added_count} trades',
            'data': {
                'added_count': added_count,
                'total_trades': len(trades),
                'errors': errors
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        pass  # app_logger.error(f"Error importing DAS trades: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trades/summary', methods=['GET'])
def get_trade_summary():
    """Get trade summary statistics"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get summary from database
        summary = db_manager.get_trade_summary(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': summary,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting trade summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/pnl-history', methods=['GET'])
def get_positions_pnl_history():
    """Get positions-based PnL history for charting"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        
        # Validate limit
        if limit > 1000:
            limit = 1000
        
        # Get positions PnL history from database
        positions = db_manager.get_positions_pnl_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        # Get summary statistics
        summary = db_manager.get_positions_pnl_summary(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'positions': positions,
                'summary': summary
            },
            'timestamp': datetime.now().isoformat(),
            'count': len(positions)
        })
    except Exception as e:
        app_logger.error(f"Error getting positions PnL history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trades/recalculate-pnl', methods=['POST'])
def recalculate_trade_pnl():
    """Recalculate PnL for all existing trades in the database"""
    try:
        from database import db_manager
        
        app_logger.info("🔄 Starting PnL recalculation for all trades...")
        
        # Recalculate PnL for all trades
        success, message = db_manager.recalculate_pnl_for_existing_trades()
        
        if success:
            app_logger.info(f"✅ {message}")
            return jsonify({
                'success': True,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
        else:
            app_logger.error(f"❌ {message}")
            return jsonify({
                'success': False,
                'error': message
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error recalculating trade PnL: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trades/sync-das', methods=['POST'])
def sync_trades_from_das():
    """Sync trades from DAS Trader"""
    if not DAS_ENABLED:
        return jsonify({'success': False, 'error': 'DAS integration is disabled'}), 503

    try:
        from das_integration import das_trade_manager
        
        # Sync trades from DAS
        success, message, added_count = das_trade_manager.sync_trades_from_das()
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'data': {
                    'added_count': added_count,
                    'last_sync_time': das_trade_manager.last_sync_time.isoformat() if das_trade_manager.last_sync_time else None
                },
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
    except Exception as e:
        pass  # app_logger.error(f"Error syncing trades from DAS: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Scheduled DAS Sync endpoints
@app.route('/api/scheduled-sync/status', methods=['GET'])
def get_scheduled_sync_status():
    """Get scheduled sync service status"""
    try:
        if not SCHEDULED_SYNC_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Scheduled sync not available'
            }), 503
            
        status = get_sync_status()
        return jsonify({
            'success': True,
            'data': status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting scheduled sync status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/scheduled-sync/start', methods=['POST'])
def start_scheduled_sync_service():
    """Start the scheduled sync service"""
    try:
        if not SCHEDULED_SYNC_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Scheduled sync not available'
            }), 503
            
        start_scheduled_sync()
        return jsonify({
            'success': True,
            'message': 'Scheduled sync service started',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error starting scheduled sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/scheduled-sync/stop', methods=['POST'])
def stop_scheduled_sync_service():
    """Stop the scheduled sync service"""
    try:
        if not SCHEDULED_SYNC_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Scheduled sync not available'
            }), 503
            
        stop_scheduled_sync()
        return jsonify({
            'success': True,
            'message': 'Scheduled sync service stopped',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error stopping scheduled sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/scheduled-sync/manual', methods=['POST'])
def trigger_manual_sync():
    """Trigger a manual sync"""
    try:
        if not SCHEDULED_SYNC_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Scheduled sync not available'
            }), 503
            
        result = manual_sync()
        return jsonify({
            'success': result['success'],
            'message': result['message'],
            'data': {
                'synced_count': result['synced_count']
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error triggering manual sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Position Sync Status endpoint
@app.route('/api/positions/sync-status', methods=['GET'])
def get_position_sync_status():
    """Get position sync status"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'is_running': False,
                'is_market_hours': False,
                'current_time_et': datetime.now().strftime('%H:%M:%S'),
                'next_scheduled_run': None,
                'thread_alive': False,
                'sync_type': 'disabled',
                'update_interval': 'N/A',
                'reason': 'DAS integration is disabled'
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting position sync status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Position History API endpoints
# Daily Position History API endpoints
@app.route('/api/positions/daily', methods=['GET'])
@require_auth
def get_daily_positions():
    """Return consolidated closed positions for the Positions tab.

    Each row is one complete round-trip (all buys + exit) per symbol per session.
    FIFO-matched and consolidated across partial fills.
    """
    try:
        current_user_id = request.user.get('id', 1)
        symbol        = request.args.get('symbol')
        start_date    = request.args.get('start_date')
        end_date      = request.args.get('end_date')
        position_type = request.args.get('position_type')
        source        = request.args.get('source')
        limit         = min(int(request.args.get('limit', 1000)), 5000)

        positions = db_manager.get_consolidated_positions(
            symbol=symbol, start_date=start_date, end_date=end_date,
            position_type=position_type, source=source, limit=limit,
            user_id=current_user_id,
        )
        total_pnl = sum(p['pnl'] for p in positions)
        wins      = sum(1 for p in positions if p['pnl'] > 0)
        summary   = {
            'total_positions': len(positions),
            'total_pnl':       round(total_pnl, 2),
            'win_rate':        round((wins / len(positions)) * 100, 2) if positions else 0,
        }
        return jsonify({
            'success': True,
            'data':    {'positions': positions, 'summary': summary},
            'count':   len(positions),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        app_logger.error(f"Error getting consolidated positions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/daily/<date>', methods=['GET'])
def get_positions_by_date(date):
    """Get all positions for a specific date"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        type_filter = request.args.get('type')
        
        # Convert type_filter to int if provided
        if type_filter:
            try:
                type_filter = int(type_filter)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid type parameter. Must be a number.'
                }), 400
        
        # Validate date format (YYYY-MM-DD)
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD.'
            }), 400
        
        # Get positions for the specific date
        positions = db_manager.get_position_history_by_date(
            date=date,
            symbol=symbol,
            type_filter=type_filter
        )
        
        return jsonify({
            'success': True,
            'data': {
                'positions': positions,
                'date': date
            },
            'timestamp': datetime.now().isoformat(),
            'count': len(positions)
        })
    except Exception as e:
        app_logger.error(f"Error getting positions for date {date}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/daily/range', methods=['GET'])
def get_positions_by_date_range():
    """Get positions within a date range"""
    try:
        from database import db_manager
        
        # Get query parameters
        start_date    = request.args.get('start_date')
        end_date      = request.args.get('end_date')
        symbol        = request.args.get('symbol')
        position_type = request.args.get('position_type')

        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'start_date and end_date parameters are required'}), 400

        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

        positions = db_manager.get_closed_positions(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
            position_type=position_type,
        )
        return jsonify({
            'success': True,
            'data': {
                'positions': positions,
                'start_date': start_date,
                'end_date': end_date,
                'count': len(positions),
            },
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        app_logger.error(f"Error getting positions for date range: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/daily/dates', methods=['GET'])
def get_available_dates():
    """Get list of available dates in daily positions"""
    try:
        from database import db_manager
        
        dates = db_manager.get_available_dates()
        
        return jsonify({
            'success': True,
            'data': {
                'dates': dates,
                'count': len(dates)
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting available dates: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Entry Bot API endpoints
@app.route('/api/entry-bot/status', methods=['GET'])
def get_entry_bot_status():
    """Get Entry Bot status"""
    try:
        global entry_bot_running, entry_bot_stats, active_positions
        
        # Update active positions count
        entry_bot_stats['active_positions_count'] = len(active_positions)
        
        status = {
            'internal_running_state': entry_bot_running,
            'positions_entered': entry_bot_stats['positions_entered'],
            'active_positions_count': entry_bot_stats['active_positions_count']
        }
        
        return jsonify({
            'success': True,
            'data': status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting entry bot status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/entry-bot/start', methods=['POST'])
def start_entry_bot():
    """Start Entry Bot"""
    try:
        global entry_bot_running
        
        if entry_bot_running:
            return jsonify({
                'success': False,
                'error': 'Entry Bot is already running'
            }), 400
        
        entry_bot_running = True
        add_entry_bot_log('info', "🚀 Entry Bot started successfully")
        
        return jsonify({
            'success': True,
            'message': 'Entry Bot started successfully',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error starting entry bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/entry-bot/stop', methods=['POST'])
def stop_entry_bot():
    """Stop Entry Bot"""
    try:
        global entry_bot_running
        
        if not entry_bot_running:
            return jsonify({
                'success': False,
                'error': 'Entry Bot is not running'
            }), 400
        
        entry_bot_running = False
        add_entry_bot_log('info', "🛑 Entry Bot stopped successfully")
        
        return jsonify({
            'success': True,
            'message': 'Entry Bot stopped successfully',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error stopping entry bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/entry-bot/submit-parameters', methods=['POST'])
def submit_entry_parameters():
    """Submit Entry Bot parameters"""
    if not DAS_ENABLED:
        return jsonify({'success': False, 'error': 'DAS integration is disabled'}), 503

    try:
        global tracking_symbols
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        symbol = data.get('symbol', '').upper()
        total_volume = data.get('total_volume')
        dollar_volume = data.get('dollar_volume')
        entry_time = data.get('entry_time')
        position_type = data.get('position_type', 'day')  # 'day' | 'swing'

        # New DAS order parameters
        order_side = data.get('order_side', 'B')  # B for Buy, S for Sell
        route = data.get('route', 'SMAT')  # Default route
        quantity = data.get('quantity', 100)  # Default quantity
        order_type = data.get('order_type', 'MKT')  # MKT for Market, LIMIT for Limit orders
        limit_price = data.get('limit_price')  # Only used for LIMIT orders

        # Swing-specific optional fields
        swing_entry_reason = data.get('swing_entry_reason', '')
        max_hold_days = data.get('max_hold_days')

        # day trades require volume/time; swing trades only require symbol + order params
        if position_type == 'day' and not all([symbol, total_volume, dollar_volume, entry_time]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: symbol, total_volume, dollar_volume, entry_time'
            }), 400
        elif not symbol:
            return jsonify({'success': False, 'error': 'Missing required parameter: symbol'}), 400

        if position_type not in ('day', 'swing'):
            return jsonify({'success': False, 'error': "position_type must be 'day' or 'swing'"}), 400

        # Validate order parameters
        if order_side not in ['B', 'S']:
            return jsonify({
                'success': False,
                'error': 'Invalid order side. Must be B (Buy) or S (Sell)'
            }), 400
        
        if order_type not in ['MKT', 'LIMIT']:
            return jsonify({
                'success': False,
                'error': 'Invalid order type. Must be MKT (Market) or LIMIT'
            }), 400
        
        if order_type == 'LIMIT' and not limit_price:
            return jsonify({
                'success': False,
                'error': 'Limit price is required for LIMIT orders'
            }), 400
        
        if quantity <= 0:
            return jsonify({
                'success': False,
                'error': 'Quantity must be greater than 0'
            }), 400
        
        # Store the tracking parameters
        tracking_symbols[symbol] = {
            'symbol': symbol,
            'total_volume': float(total_volume) if total_volume else None,
            'dollar_volume': float(dollar_volume) if dollar_volume else None,
            'entry_time': entry_time,
            # DAS order parameters
            'order_side': order_side,
            'route': route,
            'quantity': int(quantity),
            'order_type': order_type,
            'limit_price': limit_price,
            'submitted_at': datetime.now().isoformat(),
            'status': 'tracking',
            # Trade style
            'position_type': position_type,
            'swing_entry_reason': swing_entry_reason,
            'max_hold_days': int(max_hold_days) if max_hold_days else None,
        }
        
        # Start continuous tracking if this is the first symbol
        if len(tracking_symbols) == 1:
            start_continuous_tracking()
        
        add_entry_bot_log('info', f"📝 Entry parameters submitted for {symbol}: Volume={total_volume}M, Dollar Volume={dollar_volume}M, Time={entry_time}")
        
        return jsonify({
            'success': True,
            'message': f'Entry parameters submitted for {symbol}',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error submitting entry parameters: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/entry-bot/tracking-status', methods=['GET'])
def get_tracking_status():
    """Get tracking status for all symbols"""
    try:
        global tracking_symbols
        
        tracking_status = []
        
        for symbol, params in tracking_symbols.items():
            # Get current market data for the symbol
            current_data = get_real_stock_data(symbol)
            
            # Handle case where no data is available
            if current_data is None:
                status_entry = {
                    'symbol': symbol,
                    'submitted_at': params['submitted_at'],
                    'entry_parameters': {
                        'total_volume': params['total_volume'],
                        'dollar_volume': params['dollar_volume'],
                        'entry_time': params['entry_time']
                    },
                    'order_parameters': {
                        'order_side': params.get('order_side', 'B'),
                        'route': params.get('route', 'SMAT'),
                        'quantity': params.get('quantity', 100),
                        'order_type': params.get('order_type', 'MKT'),
                        'limit_price': params.get('limit_price')
                    },
                    'current_data': {
                        'current_price': 'N/A',
                        'current_volume': 'N/A',
                        'current_dollar_volume': 'N/A',
                        'current_time': 'N/A'
                    },
                    'conditions': {
                        'conditions_met': False,
                        'volume_met': False,
                        'dollar_volume_met': False,
                        'time_met': False,
                        'error': 'No market data available'
                    },
                    'status': 'no_data'
                }
                tracking_status.append(status_entry)
                continue
            
            # Check if entry conditions are met
            conditions = check_entry_conditions(current_data, params)
            
            # Create tracking status entry
            status_entry = {
                'symbol': symbol,
                'submitted_at': params['submitted_at'],
                'entry_parameters': {
                    'total_volume': params['total_volume'],
                    'dollar_volume': params['dollar_volume'],
                    'entry_time': params['entry_time']
                },
                'order_parameters': {
                    'order_side': params.get('order_side', 'B'),
                    'route': params.get('route', 'SMAT'),
                    'quantity': params.get('quantity', 100),
                    'order_type': params.get('order_type', 'MKT'),
                    'limit_price': params.get('limit_price')
                },
                'current_data': {
                    'current_price': current_data['current_price'],
                    'current_volume': current_data['volume'],
                    'current_dollar_volume': current_data['dollar_volume'],
                    'current_time': current_data['timestamp']
                },
                'conditions': conditions,
                'status': params['status']
            }
            
            tracking_status.append(status_entry)
        
        return jsonify({
            'success': True,
            'tracking_symbols': tracking_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting tracking status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/entry-bot/stop-tracking', methods=['POST'])
def stop_tracking_symbol():
    """Stop tracking a specific symbol"""
    try:
        global tracking_symbols
        
        data = request.get_json()
        
        if not data or 'symbol' not in data:
            return jsonify({
                'success': False,
                'error': 'Symbol not provided'
            }), 400
        
        symbol = data['symbol'].upper()
        
        if symbol not in tracking_symbols:
            return jsonify({
                'success': False,
                'error': f'Symbol {symbol} is not being tracked'
            }), 404
        
        # Remove the symbol from tracking
        del tracking_symbols[symbol]
        
        # Stop continuous tracking if no symbols are left
        if len(tracking_symbols) == 0:
            stop_continuous_tracking()
        
        add_entry_bot_log('info', f"🛑 Stopped tracking for {symbol}")
        
        return jsonify({
            'success': True,
            'message': f'Stopped tracking {symbol}',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error stopping tracking: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/entry-bot/active-positions', methods=['GET'])
def get_active_positions():
    """Get active positions entered by the Entry Bot"""
    try:
        global active_positions
        
        # Convert positions to list format for frontend
        positions_list = []
        for position_id, position in active_positions.items():
            entry_params = position.get('entry_params', {})
            positions_list.append({
                'position_id': position_id,
                'symbol': position['symbol'],
                'entry_price': position['entry_price'],
                'entry_time': position['entry_time'],
                'quantity': position['quantity'],
                'status': position['status'],
                'position_type': entry_params.get('position_type', 'day'),
            })
        
        return jsonify({
            'success': True,
            'data': positions_list,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting active positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/entry-bot/debug-logs', methods=['GET'])
def get_debug_logs():
    """Get debug logs for Entry Bot"""
    try:
        global entry_bot_logs
        
        return jsonify({
            'success': True,
            'logs': entry_bot_logs,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting debug logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Positions-based API endpoints (replacing trades endpoints)

def _parse_stats_filters(req):
    """Extract date + advanced stats filters from request.args.
    Returns (start_date, end_date, price_min, price_max, day_of_week_list,
             time_start_utc, time_end_utc, utc_offset_mins).
    ET times are converted to UTC HH:MM strings for SQLite comparison.
    day_of_week_list uses SQLite %w convention (0=Sun, 1=Mon … 6=Sat).
    """
    import pytz as _pytz
    start_date    = req.args.get('start_date')
    end_date      = req.args.get('end_date')
    price_min     = req.args.get('price_min',  type=float)
    price_max     = req.args.get('price_max',  type=float)
    dow_param     = req.args.get('day_of_week', '')   # comma-sep ints e.g. "1,2,3"
    time_start_et = req.args.get('time_start', '')    # HH:MM ET
    time_end_et   = req.args.get('time_end',   '')    # HH:MM ET

    day_of_week = None
    if dow_param:
        try:
            day_of_week = [int(d) for d in dow_param.split(',') if d.strip()]
        except ValueError:
            pass

    time_start_utc = time_end_utc = None
    utc_offset_mins = -300  # default EST
    try:
        et_tz   = _pytz.timezone('US/Eastern')
        utc_tz  = _pytz.utc
        et_now  = datetime.now(et_tz)
        utc_offset_mins = int(et_now.utcoffset().total_seconds() / 60)
        today   = et_now.date()
        if time_start_et:
            h, m = map(int, time_start_et.split(':'))
            et_dt = et_tz.localize(datetime(today.year, today.month, today.day, h, m))
            time_start_utc = et_dt.astimezone(utc_tz).strftime('%H:%M')
        if time_end_et:
            h, m = map(int, time_end_et.split(':'))
            et_dt = et_tz.localize(datetime(today.year, today.month, today.day, h, m))
            time_end_utc = et_dt.astimezone(utc_tz).strftime('%H:%M')
    except Exception:
        pass

    return start_date, end_date, price_min, price_max, day_of_week, time_start_utc, time_end_utc, utc_offset_mins


@app.route('/api/positions/summary', methods=['GET'])
@require_auth
def get_positions_summary():
    """Return total_positions, total_pnl, and win_rate using the same FIFO-consolidated
    round-trip logic as the Positions tab, so Stats and Positions always agree."""
    try:
        current_user_id = request.user.get('id', 1)
        symbol        = request.args.get('symbol')
        position_type = request.args.get('position_type')
        source        = request.args.get('source')
        start_date, end_date, price_min, price_max, day_of_week, \
            time_start_utc, time_end_utc, _ = _parse_stats_filters(request)

        positions  = db_manager.get_consolidated_positions(
            symbol=symbol, start_date=start_date, end_date=end_date,
            position_type=position_type, source=source, limit=10_000,
            user_id=current_user_id,
            price_min=price_min, price_max=price_max,
            time_start_utc=time_start_utc, time_end_utc=time_end_utc,
            day_of_week=day_of_week,
        )
        total_pnl  = sum(p['pnl'] for p in positions)
        wins       = sum(1 for p in positions if p['pnl'] > 0)
        total      = len(positions)
        return jsonify({
            'success': True,
            'data': {
                'total_positions': total,
                'total_pnl':       round(total_pnl, 2),
                'win_rate':        round((wins / total * 100), 2) if total else 0,
            },
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        app_logger.error(f"Error getting positions summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/extended-stats', methods=['GET'])
@require_auth
def get_extended_stats():
    """Compute all Stats-tab metrics from the same FIFO-consolidated positions as the Positions tab."""
    try:
        current_user_id = request.user.get('id', 1)
        symbol        = request.args.get('symbol')
        position_type = request.args.get('position_type')
        source        = request.args.get('source')
        start_date, end_date, price_min, price_max, day_of_week, \
            time_start_utc, time_end_utc, _ = _parse_stats_filters(request)

        positions = db_manager.get_consolidated_positions(
            symbol=symbol, start_date=start_date, end_date=end_date,
            position_type=position_type, source=source, limit=10_000,
            user_id=current_user_id,
            price_min=price_min, price_max=price_max,
            time_start_utc=time_start_utc, time_end_utc=time_end_utc,
            day_of_week=day_of_week,
        )

        _empty = {
            'total_count': 0, 'win_count': 0, 'loss_count': 0, 'breakeven_count': 0,
            'gross_profit': 0, 'gross_loss': 0, 'profit_factor': 0,
            'avg_win': 0, 'avg_loss': 0, 'win_loss_ratio': 0, 'avg_pnl': 0,
            'best_trade': 0, 'best_trade_symbol': '', 'best_trade_date': '',
            'worst_trade': 0, 'worst_trade_symbol': '', 'worst_trade_date': '',
            'expectancy': 0, 'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
            'max_drawdown': 0, 'sharpe_ratio': None,
        }
        if not positions:
            return jsonify({'success': True, 'data': _empty})

        pnls   = [p['pnl'] for p in positions]
        wins   = [p for p in positions if p['pnl'] > 0]
        losses = [p for p in positions if p['pnl'] < 0]
        bes    = [p for p in positions if p['pnl'] == 0]

        gross_profit = sum(p['pnl'] for p in wins)
        gross_loss   = abs(sum(p['pnl'] for p in losses))
        avg_win      = round(gross_profit / len(wins), 2)   if wins   else 0
        avg_loss     = round(sum(p['pnl'] for p in losses) / len(losses), 2) if losses else 0

        best  = max(positions, key=lambda p: p['pnl'])
        worst = min(positions, key=lambda p: p['pnl'])

        win_rate  = len(wins)   / len(positions)
        loss_rate = len(losses) / len(positions)
        expectancy = round((win_rate * avg_win) + (loss_rate * avg_loss), 2)

        # Consecutive streaks — positions sorted newest-first, reverse for time order
        max_wins = max_losses = cur_wins = cur_losses = 0
        for p in reversed(positions):
            if p['pnl'] > 0:
                cur_wins  += 1; cur_losses = 0
            elif p['pnl'] < 0:
                cur_losses += 1; cur_wins = 0
            else:
                cur_wins = cur_losses = 0
            max_wins   = max(max_wins,   cur_wins)
            max_losses = max(max_losses, cur_losses)

        # Max Drawdown — peak-to-trough cumulative P&L (chronological order)
        chron = list(reversed(positions))   # positions list is newest-first
        cum_pnl = peak = 0.0
        max_drawdown = 0.0
        for p in chron:
            cum_pnl += p['pnl']
            if cum_pnl > peak:
                peak = cum_pnl
            dd = peak - cum_pnl
            if dd > max_drawdown:
                max_drawdown = dd

        # Sharpe Ratio — aggregate P&L by trading day, then annualise
        from collections import defaultdict
        import math
        daily = defaultdict(float)
        for p in chron:
            daily[p['exit_date']] += p['pnl']
        daily_vals = list(daily.values())
        sharpe_ratio = None
        if len(daily_vals) >= 2:
            n       = len(daily_vals)
            mean    = sum(daily_vals) / n
            std     = math.sqrt(sum((x - mean) ** 2 for x in daily_vals) / (n - 1))
            if std > 0:
                sharpe_ratio = round((mean / std) * math.sqrt(252), 2)

        return jsonify({'success': True, 'data': {
            'total_count':            len(positions),
            'win_count':              len(wins),
            'loss_count':             len(losses),
            'breakeven_count':        len(bes),
            'gross_profit':           round(gross_profit, 2),
            'gross_loss':             round(gross_loss, 2),
            'profit_factor':          round(gross_profit / gross_loss, 2) if gross_loss else 0,
            'avg_win':                avg_win,
            'avg_loss':               avg_loss,
            'win_loss_ratio':         round(avg_win / abs(avg_loss), 2) if avg_loss else 0,
            'avg_pnl':                round(sum(pnls) / len(pnls), 2),
            'best_trade':             round(best['pnl'], 2),
            'best_trade_symbol':      best['symbol'],
            'best_trade_date':        best.get('exit_date', ''),
            'worst_trade':            round(worst['pnl'], 2),
            'worst_trade_symbol':     worst['symbol'],
            'worst_trade_date':       worst.get('exit_date', ''),
            'expectancy':             expectancy,
            'max_consecutive_wins':   max_wins,
            'max_consecutive_losses': max_losses,
            'max_drawdown':           round(max_drawdown, 2),
            'sharpe_ratio':           sharpe_ratio,
        }})
    except Exception as e:
        app_logger.error(f"Error getting extended stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Keep old single-stat endpoints as thin shims so nothing else breaks
@app.route('/api/positions/total_positions', methods=['GET'])
def get_total_positions():
    return get_positions_summary()

@app.route('/api/positions/total_pnl', methods=['GET'])
def get_total_pnl():
    return get_positions_summary()

@app.route('/api/positions/winrate', methods=['GET'])
def get_winrate():
    return get_positions_summary()

@app.route('/api/positions/daily-pnl', methods=['GET'])
@require_auth
def get_daily_pnl():
    try:
        uid = request.user.get('id', 1)
        sd, ed, pmin, pmax, dow, ts_utc, te_utc, _ = _parse_stats_filters(request)
        data = db_manager.get_daily_pnl_data(
            start_date=sd, end_date=ed, user_id=uid,
            time_start_utc=ts_utc, time_end_utc=te_utc,
            price_min=pmin, price_max=pmax, day_of_week=dow)
        return jsonify({'success': True, 'data': {'daily_pnl': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting daily P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/cumulative-pnl', methods=['GET'])
@require_auth
def get_cumulative_pnl():
    try:
        uid = request.user.get('id', 1)
        sd, ed, pmin, pmax, dow, ts_utc, te_utc, _ = _parse_stats_filters(request)
        data = db_manager.get_cumulative_pnl_data(
            start_date=sd, end_date=ed, user_id=uid,
            time_start_utc=ts_utc, time_end_utc=te_utc,
            price_min=pmin, price_max=pmax, day_of_week=dow)
        return jsonify({'success': True, 'data': {'cumulative_pnl': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting cumulative P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/pie-chart/long-short', methods=['GET'])
@require_auth
def get_long_short_pnl():
    try:
        uid = request.user.get('id', 1)
        sd, ed, pmin, pmax, dow, ts_utc, te_utc, _ = _parse_stats_filters(request)
        data = db_manager.get_long_short_pnl_data(
            start_date=sd, end_date=ed, user_id=uid,
            time_start_utc=ts_utc, time_end_utc=te_utc,
            price_min=pmin, price_max=pmax, day_of_week=dow)
        return jsonify({'success': True, 'data': {'long_short_pnl': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting long/short P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/pie-chart/symbols', methods=['GET'])
@require_auth
def get_symbol_pnl():
    try:
        uid   = request.user.get('id', 1)
        limit = request.args.get('limit', 10, type=int)
        sd, ed, pmin, pmax, dow, ts_utc, te_utc, _ = _parse_stats_filters(request)
        data = db_manager.get_symbol_pnl_data(
            start_date=sd, end_date=ed, limit=limit, user_id=uid,
            time_start_utc=ts_utc, time_end_utc=te_utc,
            price_min=pmin, price_max=pmax, day_of_week=dow)
        return jsonify({'success': True, 'data': {'symbol_pnl': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting symbol P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/pie-chart/win-loss', methods=['GET'])
@require_auth
def get_win_loss_pnl():
    try:
        uid = request.user.get('id', 1)
        sd, ed, pmin, pmax, dow, ts_utc, te_utc, _ = _parse_stats_filters(request)
        data = db_manager.get_win_loss_pnl_data(
            start_date=sd, end_date=ed, user_id=uid,
            time_start_utc=ts_utc, time_end_utc=te_utc,
            price_min=pmin, price_max=pmax, day_of_week=dow)
        return jsonify({'success': True, 'data': {'win_loss_pnl': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting win/loss P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/pie-chart/monthly', methods=['GET'])
@require_auth
def get_monthly_pnl():
    try:
        uid = request.user.get('id', 1)
        sd, ed, pmin, pmax, dow, ts_utc, te_utc, _ = _parse_stats_filters(request)
        data = db_manager.get_monthly_pnl_data(
            start_date=sd, end_date=ed, user_id=uid,
            time_start_utc=ts_utc, time_end_utc=te_utc,
            price_min=pmin, price_max=pmax, day_of_week=dow)
        return jsonify({'success': True, 'data': {'monthly_pnl': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting monthly P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/time-of-day', methods=['GET'])
@require_auth
def get_time_of_day_pnl():
    """P&L grouped by exit hour (ET). Respects date, price, and day-of-week filters."""
    try:
        uid = request.user.get('id', 1)
        sd, ed, pmin, pmax, dow, _, _, utc_offset_mins = _parse_stats_filters(request)
        data = db_manager.get_time_of_day_pnl_data(
            start_date=sd, end_date=ed, user_id=uid,
            utc_offset_mins=utc_offset_mins,
            price_min=pmin, price_max=pmax, day_of_week=dow)
        return jsonify({'success': True, 'data': {'time_of_day': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting time-of-day P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/day-of-week', methods=['GET'])
@require_auth
def get_day_of_week_pnl():
    """P&L grouped by day of week (Mon–Fri ET). Respects date, price, and time filters."""
    try:
        uid = request.user.get('id', 1)
        sd, ed, pmin, pmax, _, ts_utc, te_utc, _ = _parse_stats_filters(request)
        data = db_manager.get_day_of_week_pnl_data(
            start_date=sd, end_date=ed, user_id=uid,
            time_start_utc=ts_utc, time_end_utc=te_utc,
            price_min=pmin, price_max=pmax)
        return jsonify({'success': True, 'data': {'day_of_week': data}, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        app_logger.error(f"Error getting day-of-week P&L data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions/open', methods=['GET'])
@require_auth
def get_open_positions():
    """Return live open positions from Alpaca.
    Priority: running BrownBot broker → DB config → ALPACA_API_KEY env var."""
    try:
        user_id = request.user.get('id', 1)  # matches pattern used by all other broker endpoints

        _sess_op = _brown_sessions.get(user_id)
        broker = _sess_op.broker if _sess_op else None
        if broker:
            app_logger.info('get_open_positions: using running BrownBot broker')
        else:
            broker = _get_broker(user_id)
            if broker:
                app_logger.info(f'get_open_positions: using DB broker config (user {user_id})')

        # Fallback: build AlpacaBroker directly from env vars
        if broker is None:
            import os as _os
            api_key    = _os.environ.get('ALPACA_API_KEY') or _os.environ.get('ALPACA_KEY')
            api_secret = _os.environ.get('ALPACA_API_SECRET')
            if api_key and api_secret:
                from bot.broker.alpaca import AlpacaBroker
                paper  = _os.environ.get('ALPACA_PAPER', 'true').lower() != 'false'
                broker = AlpacaBroker(api_key, api_secret, paper=paper)
                if not broker.connect():
                    broker = None
                    app_logger.warning('get_open_positions: env-var Alpaca credentials failed to connect')
                else:
                    app_logger.info('get_open_positions: using env-var Alpaca credentials')

        if broker is None:
            app_logger.info('get_open_positions: no broker available — DB config missing and no ALPACA_API_KEY env var')
            return jsonify({'success': True, 'data': [],
                            'message': 'No broker configured. Add Alpaca API keys in Account Settings.'})

        if not broker.is_connected():
            if not broker.connect():
                app_logger.warning(f'get_open_positions: {broker.name} failed to reconnect')
                return jsonify({'success': True, 'data': [],
                                'message': f'{broker.name} could not connect. Check API keys.'})

        raw_positions = broker.get_positions()
        app_logger.info(f'get_open_positions: got {len(raw_positions)} position(s) from {broker.name}')

        # Build symbol → position_type map from this user's BrownBot session.
        type_map = {}
        _sess_tm = _brown_sessions.get(user_id)
        if _sess_tm:
            with _sess_tm.lock:
                for bp in _sess_tm.active_positions.values():
                    sym = (bp.get('symbol') or '').upper()
                    if sym:
                        type_map[sym] = bp.get('position_type')
                for meta in _sess_tm.pending_orders.values():
                    if meta.get('type') == 'exit':
                        sym = (meta.get('symbol') or '').upper()
                        if sym and sym not in type_map:
                            type_map[sym] = meta.get('position_type')
        try:
            for bp in db_manager.get_brown_positions(user_id=user_id):
                sym = (bp.get('symbol') or '').upper()
                if sym and sym not in type_map:
                    type_map[sym] = bp.get('position_type')
        except Exception:
            pass

        result = []
        for pos in raw_positions:
            pnl_pct = None
            if pos.avg_entry_price and pos.avg_entry_price > 0:
                pnl_pct = round((pos.unrealized_pnl / (pos.avg_entry_price * pos.qty)) * 100, 2)
            result.append({
                'symbol':            pos.symbol,
                'qty':               pos.qty,
                'side':              pos.side,
                'position_type':     type_map.get(pos.symbol.upper()),  # 'day', 'swing', or None
                'avg_entry':         round(pos.avg_entry_price, 4),
                'current_price':     round(pos.current_price, 4),
                'unrealized_pnl':    round(pos.unrealized_pnl, 2),
                'unrealized_pnl_pct': pnl_pct,
                'market_value':      round(pos.market_value, 2),
                'broker':            broker.name,
                'status':            'open',
            })
        return jsonify({'success': True, 'data': result, 'broker': broker.name})
    except Exception as e:
        app_logger.error(f"get_open_positions error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# WebSocket events
_ws_client_count = 0  # tracks connected client count; websocket_connected = count > 0

@socketio.on('connect')
def handle_connect():
    global websocket_connected, _ws_client_count
    _ws_client_count += 1
    websocket_connected = True
    app_logger.info(f"WebSocket client connected ({_ws_client_count} total)")
    emit('status', {'message': 'Connected to gap-up detection server'})

@socketio.on('disconnect')
def handle_disconnect():
    global websocket_connected, _ws_client_count
    _ws_client_count = max(0, _ws_client_count - 1)
    websocket_connected = _ws_client_count > 0
    app_logger.info(f"WebSocket client disconnected ({_ws_client_count} remaining)")

# Note: Stock subscriptions are handled by DAS integration, not WebSocket
# WebSocket is only used for gap-up data broadcasts

def broadcast_gap_ups():
    """Broadcast real-time gap-up data to connected clients.
    socketio.emit() is a no-op when no clients are connected, so no guard needed.
    """
    if real_time_gap_ups:
        socketio.emit('gap_ups_update', {
            'data': real_time_gap_ups,
            'timestamp': datetime.now().isoformat()
        })

# Background task to update real-time gap-ups
def update_real_time_gap_ups():
    """
    Background task — continuously refreshes gap-up data and broadcasts to
    connected WebSocket clients. Interval adapts to market session:
      - market open  : 2 min  (catch new gappers quickly)
      - pre/after    : 5 min
      - closed       : 15 min (minimal polling, market is shut)
    """
    global real_time_gap_ups

    INTERVALS = {
        'open':        120,   # 2 minutes
        'pre_market':  300,   # 5 minutes
        'after_hours': 300,   # 5 minutes
        'closed':      900,   # 15 minutes
    }

    # Track which dates we've already saved a snapshot for this process run
    _snapshot_saved_dates = set()

    app_logger.info("🔄 [GapUpMonitor] Thread started")

    while True:
        try:
            if REAL_DATA_AVAILABLE:
                from gap_up_detector import check_market_timing
                import pytz as _pytz
                _et = _pytz.timezone('US/Eastern')
                _now_et = datetime.now(_et)
                market_status = check_market_timing()
                interval      = INTERVALS.get(market_status, 300)

                # Skip entire closed window (8 PM–4 AM ET) — no market activity
                if market_status == 'closed':
                    time.sleep(interval)
                    continue

                latest_gap_ups = get_gap_up_stocks_for_frontend()
                real_time_gap_ups = latest_gap_ups
                broadcast_gap_ups()

                # Save end-of-day snapshot once per day after 8 PM ET
                _today = _now_et.date().isoformat()
                if _now_et.hour >= 20 and _today not in _snapshot_saved_dates and latest_gap_ups:
                    try:
                        from database import db_manager as _db
                        saved = _db.save_gap_up_snapshot(_today, latest_gap_ups)
                        _snapshot_saved_dates.add(_today)
                        app_logger.info(f"📸 Gap-up snapshot saved for {_today}: {saved} stocks")

                        # Also populate historical_data_cache so the cache self-builds over time
                        from historical_data import cache_gap_up_day_for_tickers as _cache_gappers
                        _cache_thread = threading.Thread(
                            target=_cache_gappers,
                            args=(_today, latest_gap_ups),
                            daemon=True
                        )
                        _cache_thread.start()
                        app_logger.info(
                            f"📡 Background: caching {len(latest_gap_ups)} gappers "
                            f"in historical_data_cache for {_today}"
                        )
                    except Exception as snap_err:
                        app_logger.error(f"Error saving gap-up snapshot: {snap_err}")

                app_logger.info(
                    f"Gap-up monitor: {len(latest_gap_ups)} stocks "
                    f"(market={market_status}, next refresh in {interval}s)"
                )
            else:
                interval = 300
                app_logger.debug("[GapUpMonitor] Real data not available — sleeping 300s")

            time.sleep(interval)
        except Exception as e:
            app_logger.error(f"[GapUpMonitor] Unhandled error in gap-up monitor loop: {e}", exc_info=True)
            time.sleep(300)

# ─────────────────────────────────────────────────────────────────────────────
# Swing Trading endpoints
# ─────────────────────────────────────────────────────────────────────────────

_swing_cache: dict = {}
_SWING_TTL = 2 * 3600  # 2-hour TTL — intraday technicals change often

_daily_picks_cache: dict = {}  # keyed by YYYY-MM-DD, one entry per trading day


def _is_market_open() -> bool:
    """Rough check: US market open Mon-Fri 09:30-16:00 ET."""
    from datetime import timezone
    import zoneinfo
    try:
        et = datetime.now(zoneinfo.ZoneInfo('America/New_York'))
    except Exception:
        et = datetime.utcnow() - timedelta(hours=4)  # rough ET offset
    if et.weekday() >= 5:
        return False
    return time_class(9, 30) <= et.time() <= time_class(16, 0)


def _last_trading_date() -> str:
    """Return the most recent weekday as YYYY-MM-DD in US/Eastern time.
    Uses ET so the date key is identical on local and cloud (UTC) servers."""
    import pytz as _pytz
    d = datetime.now(_pytz.timezone('US/Eastern'))
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def _fetch_volume_surge_candidates(existing_tickers, min_surge=1.5, min_vol=300_000, limit=20):
    """
    Use Alpaca most-actives + snapshot to find stocks with volume >= min_surge × prev-day volume.
    These are institutional accumulation/distribution setups not visible in gainers/losers alone.
    """
    import requests as _req
    alpaca_key    = os.getenv('ALPACA_API_KEY', '')
    alpaca_secret = os.getenv('ALPACA_API_SECRET', '')
    if not alpaca_key or not alpaca_secret:
        return []

    hdrs = {'APCA-API-KEY-ID': alpaca_key, 'APCA-API-SECRET-KEY': alpaca_secret}

    # Step 1: top 100 most-active symbols by volume
    try:
        r = _req.get(
            'https://data.alpaca.markets/v1beta1/screener/stocks/most-actives',
            headers=hdrs, params={'top': 100, 'by': 'volume'}, timeout=12,
        )
        r.raise_for_status()
        active_syms = [item['symbol'] for item in r.json().get('most_actives', [])]
    except Exception as e:
        app_logger.debug(f'Most-actives fetch failed: {e}')
        return []

    active_syms = [s for s in active_syms
                   if s not in existing_tickers and _is_valid_swing_ticker(s)]
    if not active_syms:
        return []

    # Step 2: batch snapshot for prev-day volume and intraday price details
    try:
        r2 = _req.get(
            'https://data.alpaca.markets/v2/stocks/snapshots',
            headers=hdrs,
            params={'symbols': ','.join(active_syms[:200]), 'feed': 'sip'},
            timeout=12,
        )
        r2.raise_for_status()
        snaps = r2.json()
    except Exception as e:
        app_logger.debug(f'Snapshot batch fetch failed: {e}')
        return []

    surgers = []
    for sym in active_syms:
        snap = snaps.get(sym, {})
        if not snap:
            continue

        day_bar  = snap.get('dailyBar') or {}
        prev_bar = snap.get('prevDailyBar') or {}

        close    = day_bar.get('c', 0)
        vwap     = day_bar.get('vw', 0)
        hi       = day_bar.get('h', close)
        lo       = day_bar.get('l', close)
        price    = close or vwap or 0
        vol      = day_bar.get('v', 0)
        prev_vol = prev_bar.get('v', 0)
        prev_c   = prev_bar.get('c', 0)
        chg      = ((price - prev_c) / prev_c * 100) if prev_c else 0

        if not (10 <= price <= 700):
            continue
        if vol < min_vol or prev_vol <= 0:
            continue
        if (price * vol) < 3_000_000:
            continue
        ratio = vol / prev_vol
        if ratio < min_surge:
            continue
        if abs(chg) > 22:
            continue

        # ── Intraday trend quality filters ──────────────────────────────
        if chg < -3:
            continue

        range_size = hi - lo
        close_pos  = (close - lo) / range_size if range_size > 0 else 0.5
        if close_pos < 0.40:
            continue

        if vwap and close < vwap * 0.985:
            continue

        surgers.append({
            'ticker':       sym,
            'price':        round(price, 2),
            'chg_pct':      round(chg, 2),
            'volume_m':     round(vol / 1_000_000, 2),
            'dollar_vol_m': round(price * vol / 1_000_000, 1),
            'day_range':    round((hi - lo) / price * 100, 1) if price else 0,
            'close_pos':    round(close_pos, 2),
            'direction':    'vol-surge',
            'vol_ratio':    round(ratio, 1),
        })

    surgers.sort(key=lambda x: x['vol_ratio'], reverse=True)
    return surgers[:limit]


def _enrich_with_sma_trend(candidates, sma_period=10, max_workers=10):
    """
    Fetch the last ~15 daily bars for each candidate (parallel Alpaca calls),
    compute SMA-10, and drop stocks whose close is below SMA-10 by more than 3%.
    These are "broken pattern" stocks — multi-day downtrend, not safe for swing longs.

    Fail-open: if bars cannot be fetched for a ticker it stays in the list.
    Annotates each candidate with 'sma10' and 'above_sma10' for Claude context.
    """
    if not candidates:
        return candidates

    alpaca_key    = os.getenv('ALPACA_API_KEY', '')
    alpaca_secret = os.getenv('ALPACA_API_SECRET', '')
    if not alpaca_key or not alpaca_secret:
        return candidates

    import requests as _req2
    import datetime
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

    today   = datetime.date.today()
    from_dt = (today - datetime.timedelta(days=sma_period * 3)).strftime('%Y-%m-%d')
    to_dt   = today.strftime('%Y-%m-%d')
    _hdrs   = {'APCA-API-KEY-ID': alpaca_key, 'APCA-API-SECRET-KEY': alpaca_secret}

    def _fetch(sym):
        try:
            r = _req2.get(
                f'https://data.alpaca.markets/v2/stocks/{sym}/bars',
                headers=_hdrs,
                params={'timeframe': '1Day', 'start': from_dt, 'end': to_dt,
                        'limit': 50, 'adjustment': 'raw', 'feed': 'sip'},
                timeout=8,
            )
            if r.status_code != 200:
                return sym, None, None
            bars = r.json().get('bars', [])
            if len(bars) < 3:
                return sym, None, None
            closes = [b['c'] for b in bars]
            sma = sum(closes[-sma_period:]) / min(sma_period, len(closes))
            return sym, round(closes[-1], 2), round(sma, 2)
        except Exception:
            return sym, None, None

    sym_info = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_fetch, c['ticker']): c['ticker'] for c in candidates}
        for fut in _as_completed(futs):
            sym, last_close, sma = fut.result()
            if last_close is not None and sma is not None:
                sym_info[sym] = (last_close, sma)

    filtered = []
    for c in candidates:
        info = sym_info.get(c['ticker'])
        if info:
            last_close, sma = info
            above = last_close >= sma * 0.97   # allow 3% below SMA (consolidation)
            c['sma10']       = info[1]
            c['above_sma10'] = above
            if not above:
                app_logger.debug(f'Swing trend filter: {c["ticker"]} close {last_close} < SMA10 {sma:.2f} — dropped')
                continue  # broken pattern — below 10-day trend
        filtered.append(c)
    return filtered


import re as _re
# Pure alpha, 1-5 chars — rejects anything with digits, dots, slashes
_ONLY_ALPHA_RE = _re.compile(r'^[A-Z]{1,5}$')
# Preferred stock naming convention: 2+ char root then PR + optional series letter
# Catches: USBPR, WFCPR, KBSPRA, JPMPRA — but not AAPL, SHOP, COMP, TRUP, etc.
_PREFERRED_RE = _re.compile(r'^[A-Z]{2,}PR[A-Z]{0,2}$')


def _is_valid_swing_ticker(sym: str) -> bool:
    """Return False for preferred stocks and non-standard instrument tickers."""
    if not _ONLY_ALPHA_RE.match(sym):
        return False
    if _PREFERRED_RE.match(sym):
        return False
    return True


def _filter_candidates(all_movers, min_vol=300_000, min_chg=0.5, max_chg=22,
                       min_price=10.0, min_dollar_vol_m=3.0):
    """Filter a Polygon snapshot tickers list for swing-eligible stocks."""
    candidates = []
    seen = set()
    for t in all_movers:
        sym   = t.get('ticker', '')
        day   = t.get('day', {})
        close = day.get('c', 0)
        vwap  = day.get('vw', 0)
        hi    = day.get('h', close)
        lo    = day.get('l', close)
        price = close or vwap or 0
        vol   = day.get('v', 0)
        chg   = t.get('todaysChangePerc', 0)

        if sym in seen or not price:
            continue
        if not _is_valid_swing_ticker(sym):
            continue
        if price < min_price or price > 700:
            continue
        if vol < min_vol:
            continue
        if (price * vol) < (min_dollar_vol_m * 1_000_000):
            continue
        if abs(chg) < min_chg or abs(chg) > max_chg:
            continue

        range_size = hi - lo
        close_pos  = (close - lo) / range_size if range_size > 0 else 0.5

        # For gainers: require bullish close structure (not a rejection / sell-off candle).
        # Losers are passed through as-is — bearish close on a down day is expected
        # and Claude may grade them as mean-reversion or short candidates.
        if chg > 0:
            if close_pos < 0.35:
                continue
            if vwap and close < vwap * 0.985:
                continue

        day_range_pct = round(range_size / price * 100, 1) if price else 0
        candidates.append({
            'ticker':    sym,
            'price':     round(price, 2),
            'chg_pct':   round(chg, 2),
            'volume_m':  round(vol / 1_000_000, 2),
            'dollar_vol_m': round(price * vol / 1_000_000, 1),
            'day_range': day_range_pct,
            'close_pos': round(close_pos, 2),
            'direction': 'gainer' if chg > 0 else 'loser',
        })
        seen.add(sym)
        if len(candidates) >= 30:
            break
    return candidates


@app.route('/api/swing-daily-picks/latest')
def swing_daily_picks_latest():
    """
    Return the most recently stored swing picks instantly from DB — no computation.
    Used by the frontend on tab load to show the last known picks immediately.
    Includes 'is_today' flag so the UI can prompt a refresh on a new trading day.
    """
    market_open  = _is_market_open()
    session_date = _last_trading_date()
    app_logger.info(f'swing-daily-picks/latest: session_date={session_date} market_open={market_open}')

    # Seed memory cache from DB if cold start
    if session_date not in _daily_picks_cache:
        db_row = db_manager.get_swing_picks(session_date)
        app_logger.info(f'swing-daily-picks/latest: DB lookup date={session_date} → {"found" if db_row else "not found"}')
        if db_row:
            _daily_picks_cache[session_date] = {
                'success': True, 'date': session_date,
                'picks': db_row['picks'], 'market_note': db_row['market_note'],
                'candidates_scanned': db_row['candidates_scanned'],
                'source_counts': db_row['source_counts'],
                'sources_tickers': db_row['sources_tickers'],
            }
    else:
        app_logger.info(f'swing-daily-picks/latest: memory cache hit for {session_date}')

    if session_date in _daily_picks_cache:
        payload = dict(_daily_picks_cache[session_date])
        payload.update({'cached': True, 'is_today': True, 'market_open': market_open})
        return jsonify(payload)

    # Today not available — return latest from any previous session
    db_row = db_manager.get_swing_picks()  # most recent
    app_logger.info(f'swing-daily-picks/latest: most-recent fallback → {"found date=" + db_row["date"] if db_row else "no rows at all"}')
    if not db_row:
        return jsonify({'success': False, 'error': 'No picks stored yet'}), 404

    return jsonify({
        'success':            True,
        'picks':              db_row['picks'],
        'market_note':        db_row['market_note'],
        'date':               db_row['date'],
        'is_today':           False,
        'cached':             True,
        'market_open':        market_open,
        'candidates_scanned': db_row['candidates_scanned'],
        'source_counts':      db_row['source_counts'],
        'sources_tickers':    db_row['sources_tickers'],
    })


def _compute_and_save_swing_picks(session_date: str,
                                   market_open: bool = None) -> dict:
    """
    Full swing picks pipeline: fetch candidates → filter → SMA/cap/trend checks →
    Claude AI ranking → persist to DB → warm memory cache.
    Returns the result dict. Raises on error (caller should catch).
    Called by both the HTTP endpoint and the EOD scheduler thread.
    """
    import requests as _req
    import concurrent.futures as _cf

    if market_open is None:
        market_open = _is_market_open()

    alpaca_key    = os.getenv('ALPACA_API_KEY', '')
    alpaca_secret = os.getenv('ALPACA_API_SECRET', '')
    if not alpaca_key or not alpaca_secret:
        raise RuntimeError('ALPACA_API_KEY / ALPACA_API_SECRET not configured')
    _hdrs = {'APCA-API-KEY-ID': alpaca_key, 'APCA-API-SECRET-KEY': alpaca_secret}

    # ── Step 1: fetch gainers + losers from Alpaca movers ────────────────
    r_movers = _req.get(
        'https://data.alpaca.markets/v1beta1/screener/stocks/movers',
        headers=_hdrs, params={'top': 50}, timeout=12,
    )
    r_movers.raise_for_status()
    movers_data = r_movers.json()
    gainers_raw = movers_data.get('gainers', [])
    losers_raw  = movers_data.get('losers', [])

    # Build Polygon-compatible ticker dicts via snapshot (get h/l/vwap/prevDay)
    all_syms = list(dict.fromkeys(
        [g['symbol'] for g in gainers_raw] + [l['symbol'] for l in losers_raw]
    ))
    chg_pct_map = {g['symbol']: g.get('change_percent', 0) for g in gainers_raw}
    chg_pct_map.update({l['symbol']: l.get('change_percent', 0) for l in losers_raw})

    all_movers = []
    if all_syms:
        try:
            r_snap = _req.get(
                'https://data.alpaca.markets/v2/stocks/snapshots',
                headers=_hdrs,
                params={'symbols': ','.join(all_syms[:200]), 'feed': 'sip'},
                timeout=12,
            )
            if r_snap.status_code == 200:
                snaps = r_snap.json()
                for sym in all_syms:
                    snap = snaps.get(sym, {})
                    if not snap:
                        continue
                    db  = snap.get('dailyBar') or {}
                    pb  = snap.get('prevDailyBar') or {}
                    all_movers.append({
                        'ticker': sym,
                        'day':    {'c': db.get('c', 0), 'h': db.get('h', 0),
                                   'l': db.get('l', 0), 'v': db.get('v', 0),
                                   'vw': db.get('vw', 0)},
                        'prevDay': {'c': pb.get('c', 0), 'v': pb.get('v', 0)},
                        'todaysChangePerc': chg_pct_map.get(sym, 0),
                    })
        except Exception as e:
            app_logger.warning(f'Swing picks snapshot batch failed: {e}')

    # ── Step 2: filter movers — strict first, relax if thin ──────────────
    candidates = _filter_candidates(all_movers, min_vol=500_000, min_chg=1.0)
    if len(candidates) < 6:
        candidates = _filter_candidates(all_movers, min_vol=300_000, min_chg=0.3)

    known_tickers = {c['ticker'] for c in candidates}

    # ── Step 2b: gap-up stocks in memory (free) ──────────────────────────
    for g in list(real_time_gap_ups):
        sym = g.get('ticker', '')
        if sym in known_tickers or not _is_valid_swing_ticker(sym):
            continue
        price = g.get('price', 0)
        vol   = g.get('volume', 0)
        chg   = g.get('gap_percent', 0)
        if not (10 <= price <= 700 and vol >= 300_000 and 1.0 <= chg <= 22):
            continue
        if (price * vol) < 3_000_000:
            continue
        candidates.append({
            'ticker': sym, 'price': round(price, 2), 'chg_pct': round(chg, 2),
            'volume_m': round(vol / 1_000_000, 2),
            'dollar_vol_m': round(price * vol / 1_000_000, 1),
            'day_range': 0, 'direction': 'gap-up', 'vol_ratio': None,
        })
        known_tickers.add(sym)

    # ── Step 2c: volume-surge scan ────────────────────────────────────────
    candidates.extend(_fetch_volume_surge_candidates(
        known_tickers, min_surge=1.5, min_vol=300_000, limit=20))

    # ── Step 2d: market-cap enrichment + micro-cap filter (yfinance) ─────
    if candidates:
        try:
            import yfinance as yf

            def _get_mktcap(sym):
                try:
                    return sym, yf.Ticker(sym).fast_info.market_cap
                except Exception:
                    return sym, None

            with _cf.ThreadPoolExecutor(max_workers=10) as _p2:
                cap_results = list(_p2.map(_get_mktcap, [c['ticker'] for c in candidates]))

            cap_map = {sym: round(mc / 1_000_000, 0)
                       for sym, mc in cap_results if mc and mc > 0}
            filtered = []
            for c in candidates:
                mc_m = cap_map.get(c['ticker'])
                if mc_m is not None:
                    if mc_m < 300:
                        continue
                    c['market_cap_m'] = mc_m
                filtered.append(c)
            candidates = filtered
        except Exception:
            pass  # fail-open

    # ── Step 2e: SMA-10 trend filter ─────────────────────────────────────
    candidates = _enrich_with_sma_trend(candidates)

    if not candidates:
        return {
            'success': True, 'market_open': market_open, 'date': session_date,
            'picks': [], 'candidates_scanned': 0,
            'market_note': 'No qualifying candidates found for this session.',
            'source_counts': {}, 'sources_tickers': {}, 'cached': False,
        }

    # ── Step 3: SwingPicksAgent ranking ──────────────────────────────────────
    if not _swing_agent:
        raise RuntimeError('SwingPicksAgent not available — ANTHROPIC_API_KEY missing?')
    ai_result = _swing_agent.rank_candidates(candidates, session_date, market_open)

    ticker_source = {c['ticker']: c['direction'] for c in candidates}
    sources_tickers = {
        'movers':    [c['ticker'] for c in candidates if c['direction'] in ('gainer', 'loser')],
        'gap_ups':   [c['ticker'] for c in candidates if c['direction'] == 'gap-up'],
        'vol_surge': [c['ticker'] for c in candidates if c['direction'] == 'vol-surge'],
    }
    source_counts = {k: len(v) for k, v in sources_tickers.items()}

    picks = ai_result.get('picks', [])
    for p in picks:
        p['source'] = ticker_source.get(p.get('ticker', ''), 'unknown')

    result = {
        'success': True, 'market_open': market_open, 'date': session_date,
        'picks': picks, 'market_note': ai_result.get('market_note', ''),
        'candidates_scanned': len(candidates),
        'source_counts': source_counts, 'sources_tickers': sources_tickers,
        'cached': False,
    }

    # Persist and warm memory cache
    _daily_picks_cache[session_date] = result
    db_manager.save_swing_picks(
        date=session_date, picks=picks,
        market_note=ai_result.get('market_note', ''),
        candidates_scanned=len(candidates),
        source_counts=source_counts, sources_tickers=sources_tickers,
    )
    return result


@app.route('/api/swing-daily-picks')
def swing_daily_picks():
    """
    Return cached swing picks for today's session (memory → DB → compute).
    Computation is also triggered automatically by the EOD scheduler at 8 PM ET.
    """
    market_open  = _is_market_open()
    session_date = _last_trading_date()
    app_logger.info(f'swing-daily-picks: session_date={session_date} market_open={market_open} ai_available={AI_AGENT_AVAILABLE}')

    # 1. Memory cache
    if session_date in _daily_picks_cache:
        app_logger.info(f'swing-daily-picks: returning memory cache for {session_date}')
        payload = dict(_daily_picks_cache[session_date])
        payload.update({'cached': True, 'is_today': True, 'market_open': market_open})
        return jsonify(payload)

    # 2. DB cache (survives restarts)
    db_row = db_manager.get_swing_picks(session_date)
    app_logger.info(f'swing-daily-picks: DB lookup date={session_date} → {"found " + str(len(db_row.get("picks",[]))) + " picks" if db_row else "not found"}')
    if db_row:
        payload = {
            'success': True, 'cached': True, 'is_today': True,
            'market_open': market_open, 'date': session_date,
            'picks': db_row['picks'], 'market_note': db_row['market_note'],
            'candidates_scanned': db_row['candidates_scanned'],
            'source_counts': db_row['source_counts'],
            'sources_tickers': db_row['sources_tickers'],
        }
        _daily_picks_cache[session_date] = payload
        return jsonify(payload)

    # 3. Market is closed — return most recent row from any date rather than computing.
    #    Don't store in memory cache so the 8 PM EOD scheduler still runs for today.
    if not market_open:
        db_row = db_manager.get_swing_picks()  # most recent (any date)
        if db_row:
            app_logger.info(f'swing-daily-picks: market closed, serving last row date={db_row["date"]}')
            return jsonify({
                'success': True, 'cached': True, 'is_today': False,
                'market_open': False, 'date': db_row['date'],
                'picks': db_row['picks'], 'market_note': db_row['market_note'],
                'candidates_scanned': db_row['candidates_scanned'],
                'source_counts': db_row['source_counts'],
                'sources_tickers': db_row['sources_tickers'],
            })

    if not AI_AGENT_AVAILABLE:
        return jsonify({'success': False, 'error': 'AI not available'}), 503

    try:
        result = _compute_and_save_swing_picks(session_date, market_open)
        return jsonify(result)
    except json.JSONDecodeError as jde:
        return jsonify({'success': False, 'error': f'AI parse error: {jde}'}), 500
    except Exception as exc:
        app_logger.error(f'swing-daily-picks error: {exc}')
        return jsonify({'success': False, 'error': str(exc)}), 500


def _swing_picks_eod_scheduler():
    """
    Daemon thread: ensures swing picks are computed and saved to DB every trading
    day at 8 PM ET — after the market has been closed for 4 hours and all EOD
    data (bars, VWAP, SMA) is final.

    On startup: if today is a trading day, it's already past 4 PM ET, and today's
    picks are not yet in the DB, runs immediately to catch up.
    Then sleeps until the next 8 PM ET firing on each subsequent trading day.
    At 8 PM the cache is invalidated so the run fetches fresh EOD data, even if
    picks were computed earlier in the session.
    """
    import pytz as _pytz

    _et = _pytz.timezone('US/Eastern')
    app_logger.info('[SwingPicksEOD] Thread started')

    # ── Startup catch-up ─────────────────────────────────────────────────
    # If server restarted after market close and today's picks are missing, fill in now.
    try:
        now_et       = datetime.now(_et)
        session_date = _last_trading_date()
        today_str    = now_et.strftime('%Y-%m-%d')
        is_trading_day = (session_date == today_str)

        if (is_trading_day
                and now_et.hour >= 16
                and AI_AGENT_AVAILABLE
                and not db_manager.get_swing_picks(session_date)):
            app_logger.info(f'Swing picks scheduler: catch-up run for {session_date}')
            _compute_and_save_swing_picks(session_date)
            app_logger.info(f'Swing picks scheduler: catch-up saved for {session_date}')
    except Exception as _e:
        app_logger.error(f'[SwingPicksEOD] Catch-up run failed: {_e}', exc_info=True)

    # ── Daily 8 PM ET loop ───────────────────────────────────────────────
    while True:
        now_et = datetime.now(_et)
        target = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
        if now_et >= target:
            target = target + timedelta(days=1)

        wait_secs = (target - now_et).total_seconds()
        app_logger.debug(f'Swing picks scheduler: next EOD run in {wait_secs / 3600:.1f}h')
        time.sleep(wait_secs)

        now_et       = datetime.now(_et)
        session_date = _last_trading_date()
        today_str    = now_et.strftime('%Y-%m-%d')

        if session_date != today_str:
            app_logger.info(f'Swing picks scheduler: {today_str} is not a trading day — skip')
            continue

        if not AI_AGENT_AVAILABLE:
            app_logger.warning('Swing picks scheduler: AI not available — skip')
            continue

        try:
            app_logger.info(f'Swing picks scheduler: EOD run for {session_date}')
            _daily_picks_cache.pop(session_date, None)
            result = _compute_and_save_swing_picks(session_date, market_open=False)
            app_logger.info(
                f'Swing picks scheduler: saved {len(result.get("picks", []))} picks '
                f'for {session_date}')
        except Exception as _e:
            app_logger.error(f'Swing picks scheduler EOD run failed: {_e}', exc_info=True)


def _compute_technicals(bars: list) -> dict:
    """
    Given a list of Polygon aggregate bars (oldest→newest), compute swing
    trading indicators and return a flat dict.
    """
    import math

    closes = [b['c'] for b in bars]
    highs  = [b['h'] for b in bars]
    lows   = [b['l'] for b in bars]
    vols   = [b['v'] for b in bars]

    n = len(closes)
    if n < 30:
        return {'error': 'Not enough data'}

    # ── SMA / EMA helpers ────────────────────────────────────────────────────
    def sma(series, period):
        if len(series) < period:
            return None
        return sum(series[-period:]) / period

    def ema(series, period):
        if len(series) < period:
            return None
        k = 2 / (period + 1)
        e = series[0]
        for p in series[1:]:
            e = p * k + e * (1 - k)
        return e

    # ── RSI(14) ──────────────────────────────────────────────────────────────
    def rsi(series, period=14):
        if len(series) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(series)):
            d = series[i] - series[i - 1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    # ── MACD(12,26,9) ────────────────────────────────────────────────────────
    def macd_vals(series):
        if len(series) < 26:
            return None, None, None
        ema12 = ema(series[-50:], 12)
        ema26 = ema(series[-60:], 26)
        if ema12 is None or ema26 is None:
            return None, None, None
        macd_line = ema12 - ema26
        # Signal: 9-period EMA of macd — approximate with last 9 MACD values
        macd_series = []
        for i in range(9, 0, -1):
            sub = series[:-i] if i > 0 else series
            e12 = ema(sub[-50:], 12)
            e26 = ema(sub[-60:], 26)
            if e12 and e26:
                macd_series.append(e12 - e26)
        signal = ema(macd_series, 9) if len(macd_series) >= 9 else (sum(macd_series) / len(macd_series) if macd_series else 0)
        histogram = macd_line - signal if signal is not None else 0
        return round(macd_line, 4), round(signal, 4), round(histogram, 4)

    # ── Bollinger Bands(20, 2σ) ──────────────────────────────────────────────
    def bollinger(series, period=20, std_mult=2):
        if len(series) < period:
            return None, None, None
        s = series[-period:]
        mid = sum(s) / period
        variance = sum((x - mid) ** 2 for x in s) / period
        sd = math.sqrt(variance)
        return round(mid - std_mult * sd, 4), round(mid, 4), round(mid + std_mult * sd, 4)

    # ── ATR(14) ──────────────────────────────────────────────────────────────
    def atr(highs_s, lows_s, closes_s, period=14):
        if len(highs_s) < period + 1:
            return None
        trs = []
        for i in range(1, len(highs_s)):
            tr = max(
                highs_s[i] - lows_s[i],
                abs(highs_s[i] - closes_s[i - 1]),
                abs(lows_s[i] - closes_s[i - 1])
            )
            trs.append(tr)
        return round(sum(trs[-period:]) / period, 4)

    # ── Volume ratio (today vs 20-day avg) ───────────────────────────────────
    avg_vol_20 = sma(vols[:-1], 20)
    vol_ratio  = round(vols[-1] / avg_vol_20, 2) if avg_vol_20 else None

    # ── Support / Resistance (simple: 20-day low / high) ─────────────────────
    support    = round(min(lows[-20:]), 4)
    resistance = round(max(highs[-20:]), 4)

    # ── Compute all values ───────────────────────────────────────────────────
    price      = closes[-1]
    sma20_val  = sma(closes, 20)
    sma50_val  = sma(closes, 50)
    sma200_val = sma(closes, 200) if n >= 200 else None
    ema9_val   = ema(closes[-30:], 9)
    ema21_val  = ema(closes[-50:], 21)
    rsi_val    = rsi(closes)
    macd_line, macd_sig, macd_hist = macd_vals(closes)
    bb_lower, bb_mid, bb_upper     = bollinger(closes)
    atr_val    = atr(highs, lows, closes)

    # ── Active signals ───────────────────────────────────────────────────────
    signals = []
    if rsi_val is not None:
        if rsi_val < 30:
            signals.append({'label': 'RSI Oversold', 'type': 'bullish'})
        elif rsi_val > 70:
            signals.append({'label': 'RSI Overbought', 'type': 'bearish'})
    if macd_line is not None and macd_sig is not None:
        if macd_line > macd_sig and macd_hist and macd_hist > 0:
            signals.append({'label': 'MACD Bullish Cross', 'type': 'bullish'})
        elif macd_line < macd_sig and macd_hist and macd_hist < 0:
            signals.append({'label': 'MACD Bearish Cross', 'type': 'bearish'})
    if sma20_val and sma50_val:
        if sma20_val > sma50_val and closes[-2] < sma50_val:
            signals.append({'label': '20/50 Golden Cross forming', 'type': 'bullish'})
        elif sma20_val < sma50_val and closes[-2] > sma50_val:
            signals.append({'label': '20/50 Death Cross forming', 'type': 'bearish'})
    if sma200_val:
        if price > sma200_val:
            signals.append({'label': 'Above 200-SMA', 'type': 'bullish'})
        else:
            signals.append({'label': 'Below 200-SMA', 'type': 'bearish'})
    if bb_lower and bb_upper:
        bb_pct = (price - bb_lower) / (bb_upper - bb_lower) * 100 if (bb_upper - bb_lower) > 0 else 50
        if bb_pct < 10:
            signals.append({'label': 'Near BB Lower Band', 'type': 'bullish'})
        elif bb_pct > 90:
            signals.append({'label': 'Near BB Upper Band', 'type': 'bearish'})
    if vol_ratio and vol_ratio > 1.5:
        signals.append({'label': f'High Volume ({vol_ratio}x avg)', 'type': 'neutral'})

    # ── Price change % ───────────────────────────────────────────────────────
    chg_1d  = round((closes[-1] / closes[-2] - 1) * 100, 2) if n >= 2 else None
    chg_5d  = round((closes[-1] / closes[-6] - 1) * 100, 2) if n >= 6 else None
    chg_20d = round((closes[-1] / closes[-21] - 1) * 100, 2) if n >= 21 else None

    def _r(v):
        return round(v, 4) if v is not None else None

    return {
        'price':       round(price, 4),
        'chg_1d':      chg_1d,
        'chg_5d':      chg_5d,
        'chg_20d':     chg_20d,
        'rsi14':       rsi_val,
        'macd_line':   macd_line,
        'macd_signal': macd_sig,
        'macd_hist':   macd_hist,
        'sma20':       _r(sma20_val),
        'sma50':       _r(sma50_val),
        'sma200':      _r(sma200_val),
        'ema9':        _r(ema9_val),
        'ema21':       _r(ema21_val),
        'bb_lower':    bb_lower,
        'bb_mid':      bb_mid,
        'bb_upper':    bb_upper,
        'atr14':       atr_val,
        'vol_ratio':   vol_ratio,
        'support20d':  support,
        'resist20d':   resistance,
        'signals':     signals,
    }


@app.route('/api/swing-technicals/<ticker>')
def swing_technicals(ticker):
    """
    Return technical indicators + sector context for swing analysis.
    Uses 2-hour in-memory cache.
    """
    ticker = ticker.upper().strip()

    # Cache check
    cached = _cache_get(_swing_cache, ticker, _SWING_TTL)
    if cached:
        cached['cached'] = True
        return jsonify(cached)

    try:
        import requests as _req

        # ── Fetch ~300 days of daily bars from Alpaca ─────────────────────────
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=420)
        _hdrs = {
            'APCA-API-KEY-ID':     os.getenv('ALPACA_API_KEY', ''),
            'APCA-API-SECRET-KEY': os.getenv('ALPACA_API_SECRET', ''),
        }
        resp = _req.get(
            f'https://data.alpaca.markets/v2/stocks/{ticker}/bars',
            headers=_hdrs,
            params={'timeframe': '1Day',
                    'start': start_dt.strftime('%Y-%m-%d'),
                    'end':   end_dt.strftime('%Y-%m-%d'),
                    'limit': 500, 'adjustment': 'raw', 'feed': 'iex'},
            timeout=10,
        )
        resp.raise_for_status()
        bars = resp.json().get('bars', [])

        if len(bars) < 30:
            return jsonify({'success': False, 'error': 'Not enough price history'}), 422

        technicals = _compute_technicals(bars)
        if 'error' in technicals:
            return jsonify({'success': False, 'error': technicals['error']}), 422

        # ── Sector context ────────────────────────────────────────────────────
        try:
            sector_info, sector_perf = _get_sector_context(ticker)
        except Exception:
            sector_info, sector_perf = None, None

        result = {
            'success':      True,
            'ticker':       ticker,
            'technicals':   technicals,
            'sector_info':  sector_info,
            'sector_perf':  sector_perf,
            'bars_count':   len(bars),
            'cached':       False,
        }
        _cache_set(_swing_cache, ticker, result)
        return jsonify(result)

    except Exception as exc:
        app_logger.error(f"swing-technicals error for {ticker}: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/swing-recommendation/<ticker>', methods=['POST'])
def swing_recommendation(ticker):
    """
    Claude AI swing setup analysis.
    Reads technicals from cache (or fetches) + earnings from web search.
    POST body: { technicals: {...}, sector_info: {...}, sector_perf: {...} }
    """
    ticker = ticker.upper().strip()
    if not AI_AGENT_AVAILABLE:
        return jsonify({'success': False, 'error': 'AI not available'}), 503

    # Per-IP rate limit (reuse the same gate as historical analysis)
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
    allowed, retry_after = _check_rate_limit(client_ip)
    if not allowed:
        mins, secs = divmod(int(retry_after), 60)
        wait_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        return jsonify({'success': False, 'error': f'Rate limit: try again in {wait_str}'}), 429

    body        = request.get_json(silent=True) or {}
    technicals  = body.get('technicals', {})
    sector_info = body.get('sector_info', {})
    sector_perf = body.get('sector_perf', {})

    # ── Earnings history via web search ──────────────────────────────────────
    earnings_text = ''
    try:
        er_results = _ai_agent._web_search(f"{ticker} earnings history beat miss last 8 quarters EPS actual vs estimate")
        if er_results:
            earnings_text = er_results[:1200]
    except Exception:
        earnings_text = 'Earnings history unavailable.'

    # ── Build prompt ─────────────────────────────────────────────────────────
    t = technicals
    sector_block = ''
    if sector_info and sector_perf:
        sector_block = (
            f"\nSector: {sector_info.get('sector','?')} ({sector_info.get('etf','?')})\n"
            f"ETF 1d: {sector_perf.get('etf_1d_pct','?')}% | 5d: {sector_perf.get('etf_5d_pct','?')}%\n"
            f"SPY 1d: {sector_perf.get('spy_1d_pct','?')}%\n"
            f"Sector trend: {sector_perf.get('trend','?')}\n"
        )

    signals_txt = ', '.join(s['label'] for s in t.get('signals', [])) or 'none'

    prompt = f"""You are an expert swing trader. Analyse the following data for {ticker} and return ONLY a JSON object.

PRICE & MOMENTUM
Price: ${t.get('price','?')}
1d chg: {t.get('chg_1d','?')}% | 5d: {t.get('chg_5d','?')}% | 20d: {t.get('chg_20d','?')}%

TECHNICALS
RSI(14): {t.get('rsi14','?')}
MACD line: {t.get('macd_line','?')} | Signal: {t.get('macd_signal','?')} | Hist: {t.get('macd_hist','?')}
SMA20: {t.get('sma20','?')} | SMA50: {t.get('sma50','?')} | SMA200: {t.get('sma200','?')}
EMA9: {t.get('ema9','?')} | EMA21: {t.get('ema21','?')}
BB Lower: {t.get('bb_lower','?')} | BB Mid: {t.get('bb_mid','?')} | BB Upper: {t.get('bb_upper','?')}
ATR(14): {t.get('atr14','?')}
Volume ratio vs 20d avg: {t.get('vol_ratio','?')}x
20d Support: {t.get('support20d','?')} | 20d Resistance: {t.get('resist20d','?')}
Active signals: {signals_txt}
{sector_block}
RECENT EARNINGS / FUNDAMENTAL CONTEXT
{earnings_text}

Return ONLY this JSON (no markdown, no commentary):
{{
  "grade": "A|B|C|F",
  "bias": "Bullish|Bearish|Neutral",
  "summary": "2-3 sentence swing setup summary",
  "entry_zone": "price or price range string",
  "stop_loss": "price string",
  "target_1": "price string",
  "target_2": "price string (optional stretch target)",
  "risk_reward": "e.g. 1:2.5",
  "hold_period": "e.g. 3–10 days",
  "key_risks": ["risk1", "risk2"],
  "earnings_summary": "1-2 sentences on recent ER beat/miss pattern",
  "catalysts": ["catalyst1", "catalyst2"]
}}"""

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=600,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()
        rec = json.loads(raw)
        return jsonify({'success': True, 'ticker': ticker, 'recommendation': rec})
    except json.JSONDecodeError as jde:
        return jsonify({'success': False, 'error': f'AI response parse error: {jde}', 'raw': raw[:500]}), 500
    except Exception as exc:
        app_logger.error(f"swing-recommendation error for {ticker}: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


def _build_digest_html(date_str, name, movers, earnings_data, ai_summary, unsub_url):
    """Render the HTML body for the daily morning digest email."""
    # Premarket movers table rows
    movers_rows = ''
    for s in movers[:12]:
        gap_pct = s.get('gap_percent', 0)
        price   = s.get('price', 0)
        vol_m   = s.get('volume', 0) / 1_000_000
        ticker  = s.get('ticker', '')
        color   = '#4ade80' if gap_pct >= 15 else '#86efac' if gap_pct >= 10 else '#fde68a'
        movers_rows += (
            f'<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;font-weight:700;color:#fff;">{ticker}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;color:{color};font-weight:700;">+{gap_pct:.1f}%</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#e2e8f0;">${price:.2f}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#9ca3af;">{vol_m:.1f}M</td>'
            f'</tr>'
        )
    if not movers_rows:
        movers_rows = '<tr><td colspan="4" style="padding:12px;color:#6b7280;text-align:center;">No premarket movers available yet</td></tr>'

    # Earnings table rows
    earnings_rows = ''
    for e in (earnings_data.get('earnings_next_5_days') or [])[:12]:
        dt_label = e.get('date', '')
        try:
            from datetime import datetime as _dt2
            dt_label = _dt2.fromisoformat(e['date']).strftime('%a %b %d')
        except Exception:
            pass
        tl = (e.get('time') or '').lower()
        if 'before' in tl or 'bmo' in tl:
            tl = 'Pre-market'
        elif 'after' in tl or 'amc' in tl:
            tl = 'After close'
        else:
            tl = tl.title() or '—'
        earnings_rows += (
            f'<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;font-weight:700;color:#fff;">{e.get("symbol") or "—"}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#9ca3af;">{(e.get("company") or "—")[:28]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#e2e8f0;">{dt_label}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#fde68a;">{tl}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#86efac;">{e.get("eps_forecast") or "—"}</td>'
            f'</tr>'
        )
    if not earnings_rows:
        earnings_rows = '<tr><td colspan="5" style="padding:12px;color:#6b7280;text-align:center;">No earnings data available</td></tr>'

    unsub_section = (
        f'<tr><td style="padding:20px 40px;text-align:center;border-top:1px solid #21262d;">'
        f'<p style="color:#4b5563;font-size:11px;margin:0;">'
        f'You\'re receiving this because you have an active Accentor AI account.<br>'
        f'<a href="{unsub_url}" style="color:#6b7280;text-decoration:underline;">Unsubscribe from daily digest</a>'
        f'</p></td></tr>'
    ) if unsub_url else ''

    return f"""<html><body style="margin:0;padding:0;background:#0d1117;font-family:Arial,sans-serif;color:#e2e8f0;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:32px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">
  <tr><td style="background:linear-gradient(135deg,#1d4ed8,#7c3aed);padding:24px 40px;">
    <div style="font-size:24px;font-weight:800;color:#fff;">Accentor <span style="color:#93c5fd;">AI</span></div>
    <div style="color:#bfdbfe;font-size:12px;margin-top:2px;">Morning Trading Digest</div>
    <div style="color:#ddd6fe;font-size:13px;margin-top:6px;font-weight:600;">{date_str}</div>
  </td></tr>
  <tr><td style="padding:28px 40px 0;">
    <p style="color:#e2e8f0;font-size:15px;margin:0 0 4px;">Good morning, <strong>{name}</strong> &#128075;</p>
    <p style="color:#9ca3af;font-size:13px;margin:0;">Here's what's moving before the bell. Log in to act on these setups.</p>
  </td></tr>
  <tr><td style="padding:20px 40px 0;">
    <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px 20px;">
      <div style="font-size:11px;font-weight:700;color:#7c3aed;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;">Market Context</div>
      <p style="color:#d1d5db;font-size:13px;line-height:1.75;margin:0;">{ai_summary}</p>
    </div>
  </td></tr>
  <tr><td style="padding:20px 40px 0;">
    <div style="font-size:11px;font-weight:700;color:#4ade80;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">Premarket Top Movers</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #21262d;border-radius:8px;overflow:hidden;">
      <tr style="background:#0d1117;">
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Ticker</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Gap %</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Price</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Volume</th>
      </tr>
      {movers_rows}
    </table>
  </td></tr>
  <tr><td style="padding:20px 40px 28px;">
    <div style="font-size:11px;font-weight:700;color:#fbbf24;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">Earnings This Week</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #21262d;border-radius:8px;overflow:hidden;">
      <tr style="background:#0d1117;">
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Ticker</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Company</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Date</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">Time</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;">EPS Est.</th>
      </tr>
      {earnings_rows}
    </table>
  </td></tr>
  <tr><td style="padding:0 40px 28px;text-align:center;">
    <a href="https://accentorai.com/app"
       style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 32px;border-radius:8px;">
      Open Accentor AI →
    </a>
  </td></tr>
  {unsub_section}
</table>
</td></tr>
</table>
</body></html>"""


def _send_daily_digest():
    """Fetch premarket movers, earnings, generate Claude summary, email all digest recipients."""
    from_email   = os.getenv('CONTACT_EMAIL_FROM', '')
    app_password = os.getenv('GMAIL_APP_PASSWORD', '')

    app_logger.info('[DailyDigest] Building digest...')

    import pytz as _pytz
    _et      = _pytz.timezone('US/Eastern')
    now_et   = datetime.now(_et)
    date_str = now_et.strftime('%A, %B %d, %Y')

    # 1. Premarket movers — reuse existing gap-up detector
    premarket_movers = []
    try:
        from gap_up_detector import fetch_gap_up_stocks
        premarket_movers = sorted(
            fetch_gap_up_stocks(min_price=2.0) or [],
            key=lambda s: s.get('gap_percent', 0), reverse=True
        )[:15]
        app_logger.info(f'[DailyDigest] Got {len(premarket_movers)} premarket movers from scanner')
    except Exception as _e:
        app_logger.warning(f'[DailyDigest] Premarket scan failed ({_e}), falling back to DB snapshot')
        try:
            yesterday = (now_et.date() - timedelta(days=1)).isoformat()
            premarket_movers = sorted(
                db_manager.get_gap_up_snapshot(yesterday) or [],
                key=lambda s: s.get('gap_percent', 0), reverse=True
            )[:15]
        except Exception:
            pass

    # 2. Earnings calendar for this week (next 5 trading days)
    earnings_data = {}
    try:
        if _ai_agent:
            earnings_data = _ai_agent._get_earnings_calendar()
        else:
            import requests as _req
            hdrs = {'User-Agent': 'Mozilla/5.0'}
            rows = []
            for _delta in range(5):
                ds = (now_et.date() + timedelta(days=_delta)).isoformat()
                try:
                    _r = _req.get('https://api.nasdaq.com/api/calendar/earnings',
                                  params={'date': ds}, headers=hdrs, timeout=8)
                    if _r.status_code == 200:
                        for _row in (_r.json().get('data', {}).get('rows') or [])[:12]:
                            rows.append({'date': ds, 'symbol': _row.get('symbol'),
                                         'company': _row.get('name'), 'time': _row.get('time'),
                                         'eps_forecast': _row.get('epsForecast')})
                except Exception:
                    pass
            earnings_data = {'earnings_next_5_days': rows}
    except Exception as _e:
        app_logger.warning(f'[DailyDigest] Earnings fetch failed: {_e}')

    # 3. Claude AI market summary (Haiku — cheap and fast)
    ai_summary = 'Market summary temporarily unavailable.'
    try:
        import anthropic as _ant
        _ant_key = os.getenv('ANTHROPIC_API_KEY', '')
        if _ant_key:
            movers_text = '\n'.join(
                f"- {s.get('ticker')}: +{s.get('gap_percent',0):.1f}%, ${s.get('price',0):.2f}, vol {s.get('volume',0)/1e6:.1f}M"
                for s in premarket_movers[:10]
            ) or 'No premarket data available.'
            earnings_text = '\n'.join(
                f"- {e.get('symbol')} ({e.get('company','')}) on {e.get('date')} {e.get('time','')}"
                for e in (earnings_data.get('earnings_next_5_days') or [])[:10]
            ) or 'No earnings data available.'
            _client = _ant.Anthropic(api_key=_ant_key)
            _resp = _client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=350,
                messages=[{'role': 'user', 'content': (
                    f'You are a professional trading analyst. Today is {date_str}.\n'
                    f'Write a concise 3-4 sentence market context paragraph for day traders and swing traders '
                    f'starting their day. Cover overall market sentiment, key sector themes to watch, and how '
                    f'the current environment favors gap-up day trading or swing trading. '
                    f'Be specific and professional. No headers, no bullets — clean prose only.\n\n'
                    f'Premarket top movers:\n{movers_text}\n\n'
                    f'Earnings this week:\n{earnings_text}\n\n'
                    f'Write the paragraph:'
                )}]
            )
            ai_summary = _resp.content[0].text.strip()
            app_logger.info('[DailyDigest] Claude summary generated')
    except Exception as _e:
        app_logger.warning(f'[DailyDigest] Claude summary failed: {_e}')

    # 4. Send to all opted-in users
    recipients = db_manager.get_digest_recipients()
    app_logger.info(f'[DailyDigest] Sending to {len(recipients)} recipient(s)')

    if not from_email or not app_password:
        app_logger.warning('[DailyDigest] SMTP not configured — digest skipped')
        return

    subject = f'Your Morning Trading Digest — {now_et.strftime("%b %d, %Y")}'
    for user in recipients:
        _email = user.get('email', '')
        if not _email:
            continue
        _name      = user.get('first_name') or user.get('username', 'there')
        _token     = user.get('email_digest_unsubscribe_token', '')
        _unsub_url = f'https://accentorai.com/unsubscribe/{_token}' if _token else ''
        try:
            html = _build_digest_html(date_str, _name, premarket_movers, earnings_data, ai_summary, _unsub_url)
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From']    = from_email
            msg['To']      = _email
            msg.attach(MIMEText(html, 'html'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as _server:
                _server.login(from_email, app_password)
                _server.sendmail(from_email, _email, msg.as_string())
            app_logger.info(f'[DailyDigest] Sent to {_email}')
        except Exception as _e:
            app_logger.warning(f'[DailyDigest] Failed for {_email}: {_e}')


def _daily_digest_scheduler():
    """Daemon thread — fires _send_daily_digest() every day at 06:00 ET."""
    import pytz as _pytz
    _et = _pytz.timezone('US/Eastern')
    app_logger.info('[DailyDigest] Scheduler started')
    while True:
        try:
            now_et    = datetime.now(_et)
            target_et = now_et.replace(hour=6, minute=0, second=0, microsecond=0)
            if now_et >= target_et:
                target_et = target_et + timedelta(days=1)
            sleep_s = (target_et - now_et).total_seconds()
            app_logger.info(
                f'[DailyDigest] Next digest at {target_et.strftime("%Y-%m-%d %H:%M %Z")} '
                f'(in {sleep_s/3600:.1f}h)'
            )
            time.sleep(sleep_s)
            # Confirm we're in the right window before firing
            if datetime.now(_et).hour == 6:
                _send_daily_digest()
        except Exception as _exc:
            app_logger.error(f'[DailyDigest] Scheduler error: {_exc}', exc_info=True)
            time.sleep(3600)


def _send_trial_expiry_reminders():
    """
    Background loop — runs every hour, sends a reminder email to users whose
    trial expires in ~24 hours and haven't received the reminder yet.
    """
    from_email   = os.getenv('CONTACT_EMAIL_FROM', '')
    app_password = os.getenv('GMAIL_APP_PASSWORD', '')

    app_logger.info("📧 [TrialReminder] Thread started")

    while True:
        try:
            from database import db_manager as _db
            users = _db.get_trial_expiring_users(hours_from_now=24, window_hours=2)
            app_logger.debug(f"[TrialReminder] Hourly check: {len(users)} user(s) expiring in ~24h")

            for user in users:
                email      = user.get('email', '')
                first_name = user.get('first_name') or user.get('username', 'there')
                expires_at = user.get('trial_expires_at', '')

                # Format expiry to a readable date (e.g. "May 16, 2026")
                try:
                    exp_dt    = datetime.fromisoformat(str(expires_at))
                    exp_label = exp_dt.strftime('%B %d, %Y').replace(' 0', ' ')  # "May 9, 2026"
                except Exception:
                    exp_label = str(expires_at)[:10]

                app_logger.info(f"Sending trial-expiry reminder to {email} (expires {exp_label})")

                if from_email and app_password:
                    try:
                        msg = MIMEMultipart('alternative')
                        msg['Subject'] = 'Your Accentor AI free trial ends tomorrow'
                        msg['From']    = from_email
                        msg['To']      = email

                        html_body = f"""
<html><body style="margin:0;padding:0;background:#0d1117;font-family:Arial,sans-serif;color:#e2e8f0;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:40px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">
      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#1d4ed8,#7c3aed);padding:28px 40px;text-align:center;">
        <div style="font-size:26px;font-weight:800;color:#fff;">Accentor <span style="color:#93c5fd;">AI</span></div>
        <div style="color:#bfdbfe;font-size:12px;margin-top:4px;">AI-Powered Gap-Up Trading Intelligence</div>
      </td></tr>
      <!-- Body -->
      <tr><td style="padding:32px 40px;">
        <h2 style="color:#fff;font-size:19px;margin:0 0 10px;">Hey {first_name}, your trial ends tomorrow ⏰</h2>
        <p style="color:#9ca3af;font-size:14px;line-height:1.7;margin:0 0 6px;">
          Your 7-day free trial expires on <strong style="color:#fff;">{exp_label}</strong>.
        </p>
        <p style="color:#9ca3af;font-size:14px;line-height:1.7;margin:0 0 24px;">
          After that your account reverts to the free tier — you'll lose access to:
        </p>
        <!-- Feature list -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
          <tr><td style="padding:9px 0;border-bottom:1px solid #21262d;">
            <span style="color:#f87171;font-size:13px;">✗</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;">Historical gap-up data &amp; AI predictions</span>
          </td></tr>
          <tr><td style="padding:9px 0;border-bottom:1px solid #21262d;">
            <span style="color:#f87171;font-size:13px;">✗</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;">Swing Trading tab — daily hot picks &amp; technicals</span>
          </td></tr>
          <tr><td style="padding:9px 0;border-bottom:1px solid #21262d;">
            <span style="color:#f87171;font-size:13px;">✗</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;">Entry Bot &amp; Exit Bot automation</span>
          </td></tr>
          <tr><td style="padding:9px 0;">
            <span style="color:#f87171;font-size:13px;">✗</span>
            <span style="color:#d1d5db;font-size:13px;margin-left:10px;">Trade history, positions, stats &amp; backtesting</span>
          </td></tr>
        </table>
        <!-- Plans note -->
        <p style="color:#9ca3af;font-size:13px;line-height:1.7;margin:0 0 24px;">
          Keep your edge for as little as <strong style="color:#fff;">$5/month</strong> — or explore our full plans.
        </p>
        <!-- CTA -->
        <div style="text-align:center;margin-bottom:28px;">
          <a href="https://accentorai.com/app"
             style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;
                    font-weight:700;font-size:14px;padding:14px 36px;border-radius:10px;">
            Upgrade Now — Keep Full Access →
          </a>
        </div>
        <p style="color:#6b7280;font-size:12px;line-height:1.6;margin:0;">
          If you have questions, just reply to this email. We're happy to help.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

                        msg.attach(MIMEText(html_body, 'html'))
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                            server.login(from_email, app_password)
                            server.sendmail(from_email, email, msg.as_string())
                        app_logger.info(f"Trial reminder sent to {email}")
                    except Exception as mail_err:
                        app_logger.warning(f"Trial reminder email failed for {email}: {mail_err}")
                else:
                    app_logger.warning(f"SMTP not configured — skipping trial reminder for {email}")

                # Mark sent regardless of email success to avoid repeated attempts
                _db.mark_trial_reminder_sent(user['id'])

        except Exception as exc:
            app_logger.error(f"[TrialReminder] Unhandled error in reminder loop: {exc}", exc_info=True)

        app_logger.debug("[TrialReminder] Sleeping 1h until next check")
        time.sleep(3600)


def _historical_prefetch_daemon():
    """Pre-fetches historical gap-up data for today's gap-up tickers so the
    Historical tab responds instantly when the user selects a ticker."""
    if not REAL_DATA_AVAILABLE:
        app_logger.info("📚 Historical prefetch daemon: skipping (no real data API)")
        return

    try:
        from historical_data import get_historical_gap_up_data as _get_hist
    except Exception as e:
        app_logger.warning(f"📚 Historical prefetch daemon: cannot import historical_data: {e}")
        return

    import pytz as _pytz
    et_tz = _pytz.timezone('US/Eastern')
    app_logger.info("📚 Historical prefetch daemon started")

    while True:
        try:
            now_et = datetime.now(et_tz)
            today_str = now_et.date().isoformat()

            # Collect current gap-up tickers from session tracker + live list
            tickers = set()
            try:
                from gap_up_detector import _session_tracker as _st
                for t, v in _st.items():
                    if v.get('date') == today_str:
                        tickers.add(t)
            except Exception:
                pass
            for stock in real_time_gap_ups:
                if isinstance(stock, dict) and stock.get('ticker'):
                    tickers.add(stock['ticker'])

            # Tickers not yet successfully pre-fetched today
            with _hist_prefetch_lock:
                pending = [
                    t for t in sorted(tickers)
                    if _hist_prefetch_status.get(t, {}).get('date') != today_str
                    or _hist_prefetch_status.get(t, {}).get('error')
                ]

            if pending:
                app_logger.info(f"[HistoricalPrefetch] {len(pending)} new ticker(s) to pre-fetch: {pending[:8]}")
                for ticker in pending:
                    try:
                        data = _get_hist(ticker, days=365, use_cache=True, min_gap_percent=5)
                        with _hist_prefetch_lock:
                            _hist_prefetch_status[ticker] = {
                                'date': today_str,
                                'records': len(data) if data else 0,
                                'fetched_at': datetime.now().isoformat()
                            }
                        app_logger.info(f"[HistoricalPrefetch] {ticker} done — {len(data) if data else 0} gap-up days cached")
                    except Exception as e:
                        app_logger.error(f"[HistoricalPrefetch] Failed to pre-fetch {ticker}: {e}", exc_info=True)
                        with _hist_prefetch_lock:
                            _hist_prefetch_status[ticker] = {
                                'date': today_str,
                                'records': 0,
                                'error': str(e)[:120],
                                'fetched_at': datetime.now().isoformat()
                            }
                    time.sleep(2)  # be kind to the Polygon API
            else:
                app_logger.debug(f"[HistoricalPrefetch] All {len(tickers)} gap-up ticker(s) already cached — sleeping 90s")
        except Exception as e:
            app_logger.error(f"[HistoricalPrefetch] Unhandled error in prefetch loop: {e}", exc_info=True)

        time.sleep(90)  # poll for new tickers every 90 s


# Start background gap-up monitor — runs under both `python app.py` and gunicorn
_bg_thread_started = False
def _start_background_tasks():
    global _bg_thread_started
    if not _bg_thread_started:
        _bg_thread_started = True

        app_logger.info("━━━ Starting background daemon threads ━━━")

        update_thread = threading.Thread(
            target=update_real_time_gap_ups, daemon=True, name='GapUpMonitor')
        update_thread.start()
        app_logger.info("✅ [GapUpMonitor]       started — refreshes gap-ups every 2–15 min")

        reminder_thread = threading.Thread(
            target=_send_trial_expiry_reminders, daemon=True, name='TrialReminder')
        reminder_thread.start()
        app_logger.info("✅ [TrialReminder]      started — checks trial expiries every 1h")

        swing_sched_thread = threading.Thread(
            target=_swing_picks_eod_scheduler, daemon=True, name='SwingPicksEOD')
        swing_sched_thread.start()
        app_logger.info("✅ [SwingPicksEOD]      started — fires swing picks computation at 8 PM ET")

        digest_thread = threading.Thread(
            target=_daily_digest_scheduler, daemon=True, name='DailyDigest')
        digest_thread.start()
        app_logger.info("✅ [DailyDigest]        started — sends morning digest to users at 6 AM ET")

        prefetch_thread = threading.Thread(
            target=_historical_prefetch_daemon, daemon=True, name='HistoricalPrefetch')
        prefetch_thread.start()
        app_logger.info("✅ [HistoricalPrefetch] started — pre-fetches historical data for gap-up tickers every 90s")

        try:
            from ohlcv_fetcher import ohlcv_daemon
            ohlcv_thread = threading.Thread(
                target=ohlcv_daemon, daemon=True, name='OHLCVFetcher')
            ohlcv_thread.start()
            app_logger.info("✅ [OHLCVFetcher]       started — backfills gap_data bars, then fetches EOD bars daily at 4:30 PM ET")
        except Exception as _e:
            app_logger.warning(f"[OHLCVFetcher] failed to start: {_e}")

        app_logger.info("━━━ All background daemon threads launched ━━━")

_start_background_tasks()

# ---------------------------------------------------------------------------
# Explicit startup column guards — run AFTER db_manager is imported so these
# are visible in the container logs. Each ALTER TABLE is idempotent: SQLite
# raises OperationalError("duplicate column name") if the column already
# exists, which we catch and ignore.
# ---------------------------------------------------------------------------
def _ensure_schema_columns():
    _cols_to_add = [
        ('trades',         'user_id',  'INTEGER DEFAULT 1'),
        ('brown_positions','user_id',  'INTEGER DEFAULT 1'),
        ('brown_orders',   'user_id',  'INTEGER DEFAULT 1'),
    ]
    with db_manager.get_connection() as _sc:
        for _tbl, _col, _defn in _cols_to_add:
            try:
                _sc.execute(f'ALTER TABLE {_tbl} ADD COLUMN {_col} {_defn}')
                _sc.commit()
                app_logger.info(f'[Schema] Added column {_tbl}.{_col}')
            except Exception as _e:
                if 'duplicate column' in str(_e).lower():
                    app_logger.debug(f'[Schema] {_tbl}.{_col} already exists — OK')
                else:
                    app_logger.warning(f'[Schema] Could not add {_tbl}.{_col}: {_e}')

_ensure_schema_columns()

if __name__ == '__main__':
    
    # DAS Trader integration is disabled — skip DAS sync services
    if DAS_ENABLED:
        if SCHEDULED_SYNC_AVAILABLE:
            try:
                start_scheduled_sync()
                pass  # app_logger.info("✅ Scheduled DAS sync service started")
            except Exception as e:
                pass  # app_logger.error(f"❌ Failed to start scheduled DAS sync: {e}")
        else:
            pass  # app_logger.warning("⚠️ Scheduled DAS sync not available")

        start_position_sync_scheduler()
    else:
        pass  # app_logger.info("ℹ️ DAS integration disabled — skipping DAS sync services")

    app_logger.info("Starting Gap-Up Detection Web API...")
    app_logger.info("Server will be available at http://localhost:5000")
    
    try:
        # Run the Flask app
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        app_logger.info("🛑 Shutting down server...")
    finally:
        # Clean up DAS connection on shutdown
        close_das_connection()
        app_logger.info("✅ Server shutdown complete")