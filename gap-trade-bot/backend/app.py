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
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from logging_config import setup_logging, get_logger, log_api_request, log_performance, log_error

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
    from gap_up_detector import get_gap_up_stocks, get_gap_up_stocks_for_frontend
    from historical_data import get_historical_gap_up_data
    REAL_DATA_AVAILABLE = True
except ImportError as e:
    app_logger.warning(f"Warning: Could not import gap_up_detector: {e}")
    REAL_DATA_AVAILABLE = False

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
    app_logger.warning(f"Warning: Could not import scheduled_das_sync: {e}")
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

# Import Claude AI Agent
try:
    from ai_agent import ClaudeAIAgent
    _ai_agent = ClaudeAIAgent()
    AI_AGENT_AVAILABLE = True
except Exception as e:
    app_logger.warning(f"Warning: Could not initialize Claude AI Agent: {e}")
    _ai_agent = None
    AI_AGENT_AVAILABLE = False

# Feature flag: controls DAS Trader integration.
# Set DAS_ENABLED=true in .env (or environment) to enable for local/mock testing.
DAS_ENABLED = os.environ.get('DAS_ENABLED', 'false').lower() == 'true'
if not DAS_ENABLED:
    BOT_AVAILABLE = False
    SCHEDULED_SYNC_AVAILABLE = False

app_logger.info(f"[STARTUP] DAS_ENABLED={DAS_ENABLED}  BOT_AVAILABLE={BOT_AVAILABLE}  SCHEDULED_SYNC={SCHEDULED_SYNC_AVAILABLE}")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gap-up-detection-web-2024')

_cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5000').split(',')
CORS(app, origins=_cors_origins)
# eventlet doesn't support Python 3.13 — fall back to threading for local dev
_async_mode = 'eventlet'
try:
    import eventlet  # noqa: F401
    eventlet.green.thread.start_joinable_thread  # probe the broken attribute
except (ImportError, AttributeError):
    _async_mode = 'threading'
socketio = SocketIO(app, cors_allowed_origins=_cors_origins, async_mode=_async_mode)

# Tag each request with the authenticated user so Sentry errors show who was affected
@app.before_request
def _set_sentry_user():
    if _sentry_dsn:
        token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.cookies.get('session_token')
        if token and auth_manager:
            user = auth_manager.get_user_by_session(token)
            if user:
                sentry_sdk.set_user({'id': user.get('id'), 'username': user.get('username'), 'email': user.get('email')})

# Global variables for real-time data
active_stocks = set()
price_cache = {}
websocket_connected = False
real_time_gap_ups = []  # Store real-time detected gap-ups

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

# BrownBot global state
_brown_bot_running = False
_brown_bot_thread = None
_brown_bot_logs = []
_brown_bot_log_id = 0
_brown_bot_stats = {'day_entered': 0, 'swing_entered': 0, 'day_exited': 0, 'swing_exited': 0}
_brown_bot_active_positions = {}  # position_id -> position dict
_brown_bot_lock = threading.Lock()
_brown_risk_manager = None  # instantiated on start from config
_brown_exit_thread = None


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
                    app_logger.warning(f"DAS direct socket error (attempt {attempt + 1}): {e}")
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
    _entry_bot_log_id += 1
    timestamp = datetime.now().isoformat()
    log_entry = {
        'id': _entry_bot_log_id,
        'timestamp': timestamp,
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


def _add_brown_log(level: str, message: str):
    """Add a log entry to the BrownBot activity log."""
    global _brown_bot_logs, _brown_bot_log_id
    _brown_bot_log_id += 1
    _brown_bot_logs.append({
        'id': _brown_bot_log_id,
        'timestamp': datetime.now().isoformat(),
        'level': level,
        'message': message,
    })
    if len(_brown_bot_logs) > 200:
        _brown_bot_logs = _brown_bot_logs[-200:]
    if level == 'error':
        app_logger.error(f"BrownBot: {message}")
    elif level == 'warning':
        app_logger.warning(f"BrownBot: {message}")
    else:
        app_logger.info(f"BrownBot: {message}")


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
                app_logger.info("✅ DAS connection established")
            except Exception as e:
                app_logger.error(f"❌ Failed to establish DAS connection: {e}")
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
                app_logger.info("🛑 DAS connection closed")
            except Exception as e:
                app_logger.error(f"❌ Error closing DAS connection: {e}")
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
        app_logger.error(f"_das_direct failed for script '{script.strip()}': {e}")

    return ""


def get_real_stock_data(symbol):
    """Get real stock data via DAS Level 1 subscription."""
    if not DAS_ENABLED:
        return None

    result = _send_das_script(f"SB {symbol.upper()} Lv1\r\n")
    if result:
        quote_data = _parse_das_level1_response(result, symbol.upper())
        if quote_data:
            app_logger.info(
                f"Level 1 {symbol}: ${quote_data['current_price']} "
                f"Vol={quote_data['volume']}M DolVol=${quote_data['dollar_volume']}M"
            )
            return quote_data

    app_logger.warning(f"No Level 1 data available for {symbol}")
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
                app_logger.debug(f"Parsing DAS Level 1 line: {line}")
                
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
                    app_logger.warning(f"No valid price found in DAS Level 1 data for {symbol}")
                    return None
                
                # Convert volume from shares to millions
                if volume and volume > 0:
                    volume_millions = volume / 1_000_000
                else:
                    app_logger.warning(f"No valid volume found in DAS Level 1 data for {symbol}")
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
        
        app_logger.warning(f"No valid Level 1 line found for {symbol} in response")
        return None
        
    except Exception as e:
        app_logger.error(f"Error parsing DAS Level 1 response for {symbol}: {e}")
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

    add_entry_bot_log('info', f"Sending DAS order: {script.strip()}")

    result = _send_das_script(script)
    add_entry_bot_log('info', f"DAS order result: {result.strip() if result else '(no response)'}")

    if result and ("SUCCESS" in result.upper() or "ACCEPTED" in result.upper()):
        return True, unID, result

    add_entry_bot_log('error', f"Order rejected or no response: {result.strip() if result else '(no response)'}")
    return False, None, result or "No response from DAS"


def enter_position(symbol, entry_price, entry_params):
    """Enter a position for a symbol at the given price using DAS"""
    global active_positions, entry_bot_stats
    
    try:
        # Extract order parameters from entry_params
        order_side = entry_params.get('order_side', 'B')
        route = entry_params.get('route', 'SMAT')
        quantity = entry_params.get('quantity', 100)
        order_type = entry_params.get('order_type', 'MKT')
        limit_price = entry_params.get('limit_price')
        
        # Place the actual order in DAS
        success, order_id, result = place_das_order(
            symbol, order_side, route, quantity, order_type, limit_price
        )
        
        if not success:
            add_entry_bot_log('error', f"❌ Failed to place DAS order for {symbol}")
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
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/login')
def serve_login():
    return send_from_directory(FRONTEND_DIR, 'login.html')


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
        # Always return success to prevent email enumeration
        generic_ok = jsonify({'success': True, 'message': 'If that email is registered, a reset link has been sent.'})
        if not user or not user.get('is_active', 1):
            return generic_ok
        token = _secrets.token_urlsafe(32)
        expires_at = _dt.now() + _td(hours=1)
        db_manager.set_reset_token(user['id'], token, expires_at)
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

        return generic_ok
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
        db_manager.update_user_password(user['id'], password_hash)
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
            app_logger.warning(f"⚠️ No historical data returned for {ticker}")
            return jsonify({
                'success': False,
                'error': f'No historical data available for {ticker}'
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
_RATE_MAX        = 5            # max AI Predict clicks
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


def _get_sector_context(ticker, polygon_api_key):
    """
    Fetch sector classification and recent sector ETF + SPY performance from Polygon.
    Returns (sector_info dict, perf dict).  Safe — never raises.
    """
    import requests as _req

    sector_info = {'sector': 'Unknown', 'etf': 'SPY',
                   'sic_code': '', 'sic_description': '', 'company_name': ticker}
    perf = {}

    if not polygon_api_key:
        return sector_info, perf

    # Step 1: reference data → sector/SIC
    try:
        r = _req.get(
            f"https://api.polygon.io/v3/reference/tickers/{ticker.upper()}",
            params={"apiKey": polygon_api_key}, timeout=8
        )
        if r.status_code == 200:
            d = r.json().get('results', {})
            sic_code = str(d.get('sic_code', '') or '')
            sic_desc = d.get('sic_description', '') or ''
            sector, etf = _sic_to_sector_etf(sic_code, sic_desc)
            sector_info = {'sector': sector, 'etf': etf,
                           'sic_code': sic_code, 'sic_description': sic_desc,
                           'company_name': d.get('name', ticker)}
    except Exception as e:
        app_logger.warning(f"Sector ref lookup failed for {ticker}: {e}")

    # Step 2: sector ETF + SPY performance — check cache first (4 h TTL)
    etf_sym = sector_info['etf']
    cached_perf = _cache_get(_sector_etf_cache, etf_sym, _SECTOR_ETF_TTL)
    if cached_perf is not None:
        app_logger.info(f"Sector ETF cache HIT for {etf_sym}")
        return sector_info, cached_perf

    end_dt = datetime.now().strftime('%Y-%m-%d')
    start_dt = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
    agg_params = {"adjusted": "true", "sort": "asc", "limit": 15, "apiKey": polygon_api_key}

    def _bars(sym):
        try:
            r = _req.get(
                f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/day/{start_dt}/{end_dt}",
                params=agg_params, timeout=8
            )
            return r.json().get('results', []) if r.status_code == 200 else []
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

        # ── Rate limit: 5 calls per IP per hour ───────────────────────────────
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

        body = request.get_json(force=True) or {}
        stats = body.get('stats', {})

        # ── Analysis cache: keyed by ticker + params + calendar date ─────────
        today = datetime.now().strftime('%Y-%m-%d')
        cache_key = f"{ticker.upper()}|{stats.get('period', '')}|{stats.get('minGap', '')}|{today}"
        cached_result = _cache_get(_analysis_cache, cache_key, _ANALYSIS_TTL)
        if cached_result is not None:
            app_logger.info(f"Analysis cache HIT for {cache_key}")
            cached_result['cached'] = True
            return jsonify(cached_result)

        # Fetch sector context from Polygon (best-effort, won't block if it fails)
        polygon_key = os.getenv('POLYGON_API_KEY')
        sector_info, sector_perf = _get_sector_context(ticker, polygon_key)

        # Build sector context block for the prompt
        etf_data = sector_perf.get('sector_etf', {})
        spy_data = sector_perf.get('spy', {})
        rel_str = sector_perf.get('relative_strength', 'unknown')
        sector_block = f"""
SECTOR CONTEXT ({sector_info['sector']} — {sector_info['sic_description'] or 'N/A'}):
- Sector ETF: {sector_info['etf']} | 1-day: {etf_data.get('change_1d_pct', 'N/A')}% | 5-day: {etf_data.get('change_5d_pct', 'N/A')}% | Trend: {etf_data.get('trend_5d', 'N/A')}
- S&P 500 (SPY): 1-day: {spy_data.get('change_1d_pct', 'N/A')}% | 5-day: {spy_data.get('change_5d_pct', 'N/A')}%
- Sector is {rel_str} the broader market by {abs(sector_perf.get('sector_vs_market_5d', 0))}% over 5 days
- Use this to judge whether gap-up moves in {ticker.upper()} are more likely to hold (sector tailwind) or fade (sector headwind)"""

        prompt = f"""You are analyzing historical gap-up trading data for {ticker.upper()} ({sector_info['company_name']}). Based on the statistics and live sector context below, predict how this stock will likely behave on its NEXT gap-up day and give actionable trading guidance.

HISTORICAL GAP-UP STATISTICS ({stats.get('period', 'N/A')}, {stats.get('minGap', 0)}%+ gaps only):
- Total gap-up events: {stats.get('totalDays', 0)}
- Runner days (closed above open): {stats.get('runnerDays', 0)} ({stats.get('runnerPct', 0)}%)
- Fader days (closed below open): {stats.get('faderDays', 0)} ({stats.get('faderPct', 0)}%)
- Neutral days: {stats.get('neutralDays', 0)} ({stats.get('neutralPct', 0)}%)
- Average gap-up %: {stats.get('avgGap', 0)}%
- Average day high %: {stats.get('avgDayHigh', 0)}% (from prev close)
- Average closing %: {stats.get('avgClose', 0)}% (from prev close)
- Average premarket volume: {stats.get('avgPremarketVol', 0)}M shares
- Most common day high time: {stats.get('commonHighTime', 'N/A')} EST
- Gap size distribution: {stats.get('gapDistribution', {})}
- RECENT TREND (last 30 days): runner rate {stats.get('recent30RunnerPct', 0)}% vs full-period {stats.get('runnerPct', 0)}%
- High-volume runner rate (top 50% vol days): {stats.get('highVolRunnerPct', 0)}%
{sector_block}

Respond ONLY with valid JSON. No markdown, no explanation outside the JSON:
{{
  "outlook": "Bullish" | "Bearish" | "Mixed" | "Neutral",
  "confidence": "High" | "Medium" | "Low",
  "summary": "One concise sentence predicting next gap-up day behavior, referencing sector if relevant",
  "regime_note": "One sentence comparing recent 30-day trend vs full-period trend — is behavior shifting?",
  "sector_impact": "One sentence on how the current {sector_info['sector']} sector trend ({etf_data.get('trend_5d', 'N/A')}) affects the prediction — tailwind, headwind, or neutral?",
  "entry": {{
    "signal": "e.g. Buy at open / Wait for first pullback / Short bias — avoid long",
    "price_context": "brief context referencing sector momentum if relevant",
    "conditions": ["specific condition 1 (may include sector/market alignment)", "specific condition 2"]
  }},
  "exit": {{
    "target": "+X% from open (based on avg day high of {stats.get('avgDayHigh', 0)}%)",
    "timing": "typical exit time based on common high time {stats.get('commonHighTime', 'N/A')} EST",
    "conditions": ["exit condition 1", "exit condition 2"]
  }},
  "caution": {{
    "level": "High" | "Medium" | "Low",
    "factors": ["risk factor 1 (consider sector headwind if applicable)", "risk factor 2"]
  }},
  "insights": ["data-backed pattern insight 1", "data-backed pattern insight 2", "sector-aware insight 3"]
}}"""

        response = _ai_agent.process_message(prompt, user_id=f"hist_analysis_{ticker.upper()}")
        if not response.get('success'):
            return jsonify({'success': False, 'error': response.get('error', 'AI analysis failed')}), 500

        import re
        text = response.get('response', '')
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            analysis = json.loads(json_match.group(0))
        else:
            analysis = {'summary': text, 'outlook': 'Mixed', 'confidence': 'Low',
                        'regime_note': '', 'sector_impact': '', 'entry': {}, 'exit': {},
                        'caution': {}, 'insights': []}

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
    polygon_key = os.getenv('POLYGON_API_KEY')

    # Primary: Polygon news API
    if polygon_key:
        try:
            r = _req.get(
                'https://api.polygon.io/v2/reference/news',
                params={'ticker': ticker, 'limit': 8, 'sort': 'published_utc',
                        'order': 'desc', 'apiKey': polygon_key},
                timeout=8
            )
            if r.status_code == 200:
                for item in r.json().get('results', []):
                    articles.append({
                        'title':       item.get('title', ''),
                        'url':         item.get('article_url', ''),
                        'source':      (item.get('publisher') or {}).get('name', ''),
                        'published':   item.get('published_utc', ''),
                        'description': (item.get('description') or '')[:220],
                    })
        except Exception as e:
            app_logger.warning(f"Polygon news failed for {ticker}: {e}")

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
        return jsonify({
            'success': True,
            'data': status,
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
            app_logger.warning("start_bot called but BOT_AVAILABLE=False (DAS_ENABLED may be False or bot import failed)")
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503

        app_logger.info("start_bot: calling trading_bot.start()...")
        success = trading_bot.start()
        if success:
            return jsonify({
                'success': True,
                'message': 'Bot started successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            # Enhanced error message for DAS connection issues
            return jsonify({
                'success': False,
                'error': 'Failed to start bot: DAS Trader is not connected. Please ensure DAS Trader is running and connected.',
                'details': 'The bot requires a connection to DAS Trader to function. Please check that DAS Trader is running and the connection is established.'
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

def _check_swing_signal(symbol, config):
    """
    Two-stage swing entry filter.
    Stage 1 (cheap): SMA20 price rule + volume surge.
    Stage 2 (expensive): Claude AI tiebreaker for borderline candidates.
    Returns (enter: bool, reason: str, score: float).
    """
    if not AI_AGENT_AVAILABLE or not _ai_agent:
        return False, 'AI agent not available', 0.0
    try:
        tech = _ai_agent._get_technical_analysis(symbol)
    except Exception as e:
        return False, f'Technical analysis failed: {e}', 0.0
    if 'error' in tech:
        return False, f'Tech data error: {tech["error"]}', 0.0

    sma10 = tech.get('sma10', 0)
    sma20 = tech.get('sma20', 0)
    latest_close = tech.get('latest_close', 0)
    recent_bars = tech.get('recent_bars', [])

    if not (sma20 and latest_close):
        return False, 'Insufficient price data', 0.0

    above_sma20 = latest_close > sma20
    if not above_sma20:
        return False, f'Price ${latest_close:.2f} below SMA20 ${sma20:.2f}', 0.0

    # Volume surge: latest bar vs average of preceding bars
    vols = [b.get('v', 0) for b in recent_bars if b.get('v')]
    avg_vol = sum(vols[:-1]) / max(len(vols) - 1, 1) if len(vols) > 1 else 0
    latest_vol = vols[-1] if vols else 0
    vol_surge = avg_vol > 0 and latest_vol > avg_vol * 1.5

    score = 0.6 + (0.15 if vol_surge else 0.0)
    reason_parts = [f'close ${latest_close:.2f} > SMA20 ${sma20:.2f}']
    if vol_surge:
        reason_parts.append(f'vol surge ({latest_vol:,} vs avg {avg_vol:,.0f})')

    # Stage 2: Claude AI tiebreaker for borderline candidates
    if score < 0.8:
        try:
            prompt = (
                f"BrownBot swing check for {symbol}. "
                f"Close ${latest_close:.2f}, SMA10 ${sma10:.2f}, SMA20 ${sma20:.2f}. "
                f"{'Volume surge detected. ' if vol_surge else ''}"
                f"Should I enter a swing trade on {symbol}? Reply BUY or HOLD with one sentence reason."
            )
            ai_result = _ai_agent.process_message(prompt, user_id='brown_bot_swing')
            if ai_result.get('success'):
                reply = ai_result['response'].upper()
                snippet = ai_result['response'][:80]
                if 'BUY' in reply:
                    score = 0.85
                    reason_parts.append(f'AI: BUY — {snippet}')
                else:
                    score = 0.45
                    reason_parts.append(f'AI: HOLD — {snippet}')
        except Exception as e:
            _add_brown_log('warning', f'AI tiebreaker failed for {symbol}: {e}')

    return score >= 0.7, ', '.join(reason_parts), score


def _brown_enter_position(symbol, position_type, config, approx_price):
    """Place a BUY order for BrownBot and record the position in memory."""
    global _brown_bot_active_positions, _brown_bot_stats
    quantity = 100
    success, order_id, result = place_das_order(symbol, 'B', 'SMAT', quantity, 'MKT')
    if not success:
        _add_brown_log('error', f'Order rejected for {symbol}: {result}')
        return

    if position_type == 'day':
        tgt_pct = float(config.get('day_profit_target_pct', 5.0))
        stp_pct = float(config.get('day_stop_loss_pct', 2.5))
    else:
        tgt_pct = float(config.get('swing_profit_target_pct', 15.0))
        stp_pct = float(config.get('swing_stop_loss_pct', 7.0))

    price = float(approx_price or 0)
    profit_target = round(price * (1 + tgt_pct / 100), 2) if price else None
    stop_loss = round(price * (1 - stp_pct / 100), 2) if price else None
    position_id = f"BROWN_{symbol}_{int(time.time())}"

    position = {
        'position_id': position_id,
        'symbol': symbol,
        'position_type': position_type,
        'entry_price': price,
        'quantity': quantity,
        'profit_target': profit_target,
        'profit_target_pct': tgt_pct,
        'stop_loss': stop_loss,
        'stop_loss_pct': stp_pct,
        'entry_time': datetime.now().isoformat(),
        'unrealized_pnl': 0.0,
    }
    with _brown_bot_lock:
        _brown_bot_active_positions[position_id] = position

    if position_type == 'day':
        _brown_bot_stats['day_entered'] += 1
    else:
        _brown_bot_stats['swing_entered'] += 1

    _add_brown_log(
        'info',
        f"ENTERED {position_type.upper()} {symbol} ~${price:.2f} | "
        f"target ${profit_target} (+{tgt_pct}%) | stop ${stop_loss} (-{stp_pct}%)"
    )


def _brown_bot_scan_and_enter():
    """One iteration of the BrownBot entry loop: scan, filter, gate, order."""
    global _brown_bot_running, _brown_risk_manager

    import pytz as _pytz
    _et = _pytz.timezone('US/Eastern')
    now_et = datetime.now(_et)

    config = db_manager.get_brown_bot_config()

    # Fetch scanner candidates
    from gap_up_detector import get_gap_up_stocks_for_frontend
    try:
        raw_gaps = get_gap_up_stocks_for_frontend()
    except Exception as e:
        _add_brown_log('warning', f'Gap-up fetch failed: {e}')
        raw_gaps = []

    min_gap = float(config.get('min_gap_pct', 10.0))
    min_price = float(config.get('min_price', 5.0))
    max_price = float(config.get('max_price', 500.0))
    min_vol_m = float(config.get('min_volume_m', 0.5))

    scanner_hits = {
        s['ticker']: s for s in raw_gaps
        if s.get('gap_percent', 0) >= min_gap
        and min_price <= s.get('price', 0) <= max_price
        and s.get('volume', 0) / 1_000_000 >= min_vol_m
    }

    # Snapshot active state under lock
    with _brown_bot_lock:
        active_symbols = {p['symbol'] for p in _brown_bot_active_positions.values()}
        active_copy = dict(_brown_bot_active_positions)

    # Day time gate: 09:35–10:30 ET
    day_open = now_et.replace(hour=9, minute=35, second=0, microsecond=0)
    day_close = now_et.replace(hour=10, minute=30, second=0, microsecond=0)
    day_window_open = day_open <= now_et <= day_close

    # ── Process auto-scanned gap-up candidates (day trade) ──
    for symbol, s in scanner_hits.items():
        if not _brown_bot_running:
            return
        if symbol in active_symbols:
            continue
        if not day_window_open:
            continue
        if _brown_risk_manager:
            allowed, reason = _brown_risk_manager.can_enter(symbol, 'day', active_copy)
            if not allowed:
                _add_brown_log('warning', f'SKIP {symbol} (day): {reason}')
                continue
        _add_brown_log('info', f'Entering DAY {symbol} — gap {s["gap_percent"]:.1f}%')
        _brown_enter_position(symbol, 'day', config, s.get('price', 0))
        # Refresh active state after entry
        with _brown_bot_lock:
            active_symbols.add(symbol)
            active_copy = dict(_brown_bot_active_positions)

    # ── Process manual watchlist candidates ──
    try:
        watchlist = db_manager.get_brown_watchlist()
    except Exception as e:
        _add_brown_log('warning', f'Watchlist fetch failed: {e}')
        watchlist = []

    for w in watchlist:
        if not _brown_bot_running:
            return
        symbol = w['symbol']
        if symbol in active_symbols:
            continue

        trade_type = w.get('trade_type', 'day')
        # 'auto': use day if gap-up scanned, else skip (swing requires explicit selection)
        if trade_type == 'auto':
            trade_type = 'day' if symbol in scanner_hits else None
        if not trade_type:
            continue

        if trade_type == 'day':
            if not day_window_open:
                continue
        elif trade_type == 'swing':
            enter, reason, score = _check_swing_signal(symbol, config)
            if not enter:
                _add_brown_log('info', f'SKIP {symbol} swing: {reason} (score={score:.2f})')
                continue
            _add_brown_log('info', f'Swing signal OK for {symbol}: {reason} (score={score:.2f})')

        if _brown_risk_manager:
            allowed, reason = _brown_risk_manager.can_enter(symbol, trade_type, active_copy)
            if not allowed:
                _add_brown_log('warning', f'SKIP {symbol} ({trade_type}): {reason}')
                continue

        approx_price = scanner_hits.get(symbol, {}).get('price', 0)
        _add_brown_log('info', f'Entering {trade_type.upper()} {symbol} from watchlist')
        _brown_enter_position(symbol, trade_type, config, approx_price)
        with _brown_bot_lock:
            active_symbols.add(symbol)
            active_copy = dict(_brown_bot_active_positions)


def _brown_bot_scanner_loop():
    """BrownBot daemon thread: scans and enters every 30 seconds."""
    global _brown_bot_running
    _add_brown_log('info', 'BrownBot scanner loop started')
    while _brown_bot_running:
        try:
            _brown_bot_scan_and_enter()
        except Exception as e:
            logger.error(f'BrownBot scanner error: {e}', exc_info=True)
            _add_brown_log('error', f'Scanner loop error: {e}')
        # Sleep 30 s in 1-second ticks for clean shutdown
        for _ in range(30):
            if not _brown_bot_running:
                break
            time.sleep(1)
    _add_brown_log('info', 'BrownBot scanner loop stopped')


def _brown_get_current_price(symbol):
    """Fetch current price for an open BrownBot position via DAS Level 1."""
    if not DAS_ENABLED:
        return None
    try:
        data = get_real_stock_data(symbol)
        if data and data.get('current_price'):
            return float(data['current_price'])
    except Exception as e:
        logger.debug(f'BrownBot price fetch failed for {symbol}: {e}')
    return None


def _brown_close_position(position_id, position, exit_reason):
    """Place a SELL market order, record the trade, and remove from active positions."""
    global _brown_bot_active_positions, _brown_bot_stats
    symbol = position['symbol']
    quantity = int(position.get('quantity', 100))
    current_price = position.get('_current_price') or position.get('entry_price', 0)
    entry_price = float(position.get('entry_price', 0))
    position_type = position.get('position_type', 'day')

    success, order_id, result = place_das_order(symbol, 'S', 'SMAT', quantity, 'MKT')
    if not success:
        _add_brown_log('error', f'SELL order failed for {symbol}: {result}')
        return False

    realized_pnl = round((float(current_price) - entry_price) * quantity, 2) if entry_price else 0.0

    # Calculate days held for swing trades
    days_held = None
    entry_time_str = position.get('entry_time', '')
    if entry_time_str:
        try:
            entry_dt = datetime.fromisoformat(entry_time_str)
            days_held = (datetime.now() - entry_dt).days
        except Exception:
            pass

    # Write the closing trade to DB
    try:
        import uuid as _uuid
        trade_data = {
            'trade_id': f'BROWN_EXIT_{symbol}_{int(time.time())}',
            'symbol': symbol,
            'side': 'S',
            'quantity': quantity,
            'price': float(current_price),
            'route': 'SMAT',
            'trade_time': datetime.now().isoformat(),
            'order_id': str(order_id) if order_id else None,
            'liquidity': None,
            'ecn_fee': 0.0,
            'pnl': realized_pnl,
            'trade_date': datetime.now().strftime('%Y-%m-%d'),
            'position_type': position_type,
            'days_held': days_held,
        }
        db_manager.add_trade(trade_data)
    except Exception as e:
        _add_brown_log('warning', f'DB trade write failed for {symbol}: {e}')

    with _brown_bot_lock:
        _brown_bot_active_positions.pop(position_id, None)

    if position_type == 'day':
        _brown_bot_stats['day_exited'] += 1
    else:
        _brown_bot_stats['swing_exited'] += 1

    pnl_str = f'+${realized_pnl:.2f}' if realized_pnl >= 0 else f'-${abs(realized_pnl):.2f}'
    _add_brown_log('info', f'EXITED {position_type.upper()} {symbol} [{exit_reason}] P&L {pnl_str}')
    return True


def _brown_bot_check_exits(check_swing_specific=False):
    """Evaluate all open BrownBot positions for exit conditions."""
    import pytz as _pytz
    _et = _pytz.timezone('US/Eastern')
    now_et = datetime.now(_et)

    config = db_manager.get_brown_bot_config()

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
            logger.debug(f'Earnings calendar fetch failed: {e}')

    with _brown_bot_lock:
        positions_snapshot = dict(_brown_bot_active_positions)

    for position_id, position in positions_snapshot.items():
        if not _brown_bot_running:
            return
        symbol = position['symbol']
        position_type = position.get('position_type', 'day')

        current_price = _brown_get_current_price(symbol)
        if current_price is None:
            continue

        entry_price = float(position.get('entry_price', 0))
        quantity = int(position.get('quantity', 0))
        unrealized_pnl = round((current_price - entry_price) * quantity, 2) if entry_price else 0.0

        # Update unrealized P&L and current price in shared state
        with _brown_bot_lock:
            if position_id in _brown_bot_active_positions:
                _brown_bot_active_positions[position_id]['unrealized_pnl'] = unrealized_pnl
                _brown_bot_active_positions[position_id]['_current_price'] = current_price

        profit_target = position.get('profit_target')
        stop_loss = position.get('stop_loss')

        # Breakeven stop: move stop to entry once price reaches halfway to target
        if (not position.get('_at_breakeven')
                and profit_target and entry_price
                and profit_target > entry_price):
            breakeven_pct = float(config.get(f'{position_type}_breakeven_trigger_pct', 50.0))
            progress = (current_price - entry_price) / (profit_target - entry_price) * 100
            if progress >= breakeven_pct:
                with _brown_bot_lock:
                    if position_id in _brown_bot_active_positions:
                        _brown_bot_active_positions[position_id]['stop_loss'] = entry_price
                        _brown_bot_active_positions[position_id]['_at_breakeven'] = True
                stop_loss = entry_price
                _add_brown_log('info', f'{symbol}: stop moved to breakeven ${entry_price:.2f} ({progress:.0f}% to target)')

        # ── Exit condition checks ──
        exit_reason = None

        if profit_target and current_price >= profit_target:
            exit_reason = 'PROFIT_TARGET'
        elif stop_loss and current_price <= stop_loss:
            exit_reason = 'STOP_LOSS'
        elif position_type == 'day' and now_et >= eod_time:
            exit_reason = f'EOD_FLATTEN ({eod_str} ET)'
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
            _brown_close_position(position_id, position_with_price, exit_reason)


def _brown_bot_exit_loop():
    """BrownBot exit daemon: checks open positions for exit conditions every 2 seconds."""
    global _brown_bot_running
    _add_brown_log('info', 'BrownBot exit loop started')
    tick = 0
    while _brown_bot_running:
        try:
            # Check swing-specific conditions (hold days, earnings) every 30 ticks (60 s)
            _brown_bot_check_exits(check_swing_specific=(tick % 30 == 0))
            tick += 1
        except Exception as e:
            logger.error(f'BrownBot exit loop error: {e}', exc_info=True)
            _add_brown_log('error', f'Exit loop error: {e}')
        time.sleep(2)
    _add_brown_log('info', 'BrownBot exit loop stopped')


# ── BrownBot API endpoints ─────────────────────────────────────────────────

@app.route('/api/brown-bot/status', methods=['GET'])
def get_brown_bot_status():
    """Return BrownBot running state, stats, and active position count."""
    global _brown_bot_running, _brown_bot_stats, _brown_bot_active_positions
    das_ok = DAS_ENABLED and _das_direct is not None
    with _brown_bot_lock:
        active_count = len(_brown_bot_active_positions)
        positions_list = list(_brown_bot_active_positions.values())
    return jsonify({
        'success': True,
        'running': _brown_bot_running,
        'das_enabled': DAS_ENABLED,
        'das_connected': das_ok,
        'stats': _brown_bot_stats,
        'active_positions_count': active_count,
        'active_positions': positions_list,
    })


@app.route('/api/brown-bot/start', methods=['POST'])
@require_auth
def start_brown_bot():
    """Start BrownBot — instantiates RiskManager from current config."""
    global _brown_bot_running, _brown_bot_thread, _brown_risk_manager
    if _brown_bot_running:
        return jsonify({'success': False, 'error': 'BrownBot is already running'})
    # Instantiate risk manager from saved config
    if RISK_MANAGER_AVAILABLE:
        try:
            config = db_manager.get_brown_bot_config()
            _brown_risk_manager = RiskManager(config)
            _add_brown_log('info', f'RiskManager ready — max daily loss ${config.get("max_daily_loss", -500)}, '
                                   f'day limit {config.get("max_concurrent_day", 3)}, '
                                   f'swing limit {config.get("max_concurrent_swing", 5)}')
        except Exception as e:
            _add_brown_log('warning', f'RiskManager init failed: {e}')
    _brown_bot_running = True
    _brown_bot_thread = threading.Thread(
        target=_brown_bot_scanner_loop, daemon=True, name='BrownBotScanner'
    )
    _brown_bot_thread.start()
    _brown_exit_thread = threading.Thread(
        target=_brown_bot_exit_loop, daemon=True, name='BrownBotExits'
    )
    _brown_exit_thread.start()
    _add_brown_log('info', 'BrownBot scanner + exit loops launched')
    return jsonify({'success': True, 'message': 'BrownBot started'})


@app.route('/api/brown-bot/stop', methods=['POST'])
@require_auth
def stop_brown_bot():
    """Stop BrownBot — clears the running flag and joins both threads."""
    global _brown_bot_running, _brown_bot_thread, _brown_exit_thread
    if not _brown_bot_running:
        return jsonify({'success': False, 'error': 'BrownBot is not running'})
    _brown_bot_running = False
    if _brown_bot_thread and _brown_bot_thread.is_alive():
        _brown_bot_thread.join(timeout=35)
    if _brown_exit_thread and _brown_exit_thread.is_alive():
        _brown_exit_thread.join(timeout=10)
    _brown_bot_thread = None
    _brown_exit_thread = None
    _add_brown_log('info', 'BrownBot stopped')
    return jsonify({'success': True, 'message': 'BrownBot stopped'})


@app.route('/api/brown-bot/config', methods=['GET'])
@require_auth
def get_brown_bot_config_endpoint():
    """Return current BrownBot config."""
    try:
        cfg = db_manager.get_brown_bot_config()
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
        ok, msg = db_manager.update_brown_bot_config(data)
        if not ok:
            return jsonify({'success': False, 'error': msg}), 500
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/logs', methods=['GET'])
@require_auth
def get_brown_bot_logs():
    """Return recent BrownBot activity logs."""
    return jsonify({'success': True, 'logs': list(reversed(_brown_bot_logs[-100:]))})


@app.route('/api/brown-bot/risk-status', methods=['GET'])
@require_auth
def get_brown_bot_risk_status():
    """Return live risk snapshot: daily P&L, open positions, circuit breaker state."""
    global _brown_risk_manager, _brown_bot_active_positions
    with _brown_bot_lock:
        positions = dict(_brown_bot_active_positions)
    if _brown_risk_manager is not None:
        snapshot = _brown_risk_manager.status(positions)
    else:
        # Risk manager not started — return defaults from config
        try:
            config = db_manager.get_brown_bot_config()
        except Exception:
            config = {}
        from datetime import datetime as _dt
        today = _dt.now().strftime('%Y-%m-%d')
        try:
            summary = db_manager.get_trade_summary(start_date=today, end_date=today)
            daily_pnl = float(summary.get('total_pnl', 0.0)) if summary else 0.0
        except Exception:
            daily_pnl = 0.0
        max_loss = float(config.get('max_daily_loss', -500.0))
        snapshot = {
            'daily_pnl': round(daily_pnl, 2),
            'max_daily_loss': max_loss,
            'open_day': 0,
            'max_concurrent_day': int(config.get('max_concurrent_day', 3)),
            'open_swing': 0,
            'max_concurrent_swing': int(config.get('max_concurrent_swing', 5)),
            'circuit_breaker_open': daily_pnl <= max_loss,
        }
    return jsonify({'success': True, 'risk': snapshot})


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
    user_id = getattr(request.user, 'id', 1)
    configs = db_manager.get_broker_configs(user_id)
    return jsonify({'success': True, 'configs': configs})


@app.route('/api/broker/config/<broker_name>', methods=['POST'])
@require_auth
def save_broker_config(broker_name):
    """
    Save (upsert) a broker config.  Pass api_key / api_secret only when the user
    explicitly updates them — omitting them preserves the stored values.
    """
    user_id = getattr(request.user, 'id', 1)
    data = request.get_json() or {}
    ok, msg = db_manager.upsert_broker_config(broker_name, data, user_id)
    if ok:
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'error': msg}), 400


@app.route('/api/broker/config/<broker_name>', methods=['DELETE'])
@require_auth
def delete_broker_config(broker_name):
    """Remove a broker config (revoke access)."""
    user_id = getattr(request.user, 'id', 1)
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
    user_id = getattr(request.user, 'id', 1)
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


@app.route('/api/brown-bot/candidates', methods=['GET'])
@require_auth
def get_brown_bot_candidates():
    """Return gap-up scanner results filtered by config thresholds, merged with watchlist."""
    try:
        config = db_manager.get_brown_bot_config()
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

        watchlist = db_manager.get_brown_watchlist()
        wl_symbols = {w['symbol'] for w in watchlist}
        scanner_symbols = {s['ticker'] for s in scanner_hits}

        # Mark scanner hits that are also on the watchlist
        for s in scanner_hits:
            if s['ticker'] in wl_symbols:
                s['on_watchlist'] = True

        # Build watchlist entries (enrich with scanner data if available)
        scanner_map = {s['ticker']: s for s in scanner_hits}
        wl_entries = []
        for w in watchlist:
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
        logger.error(f'Error fetching BrownBot candidates: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brown-bot/watchlist', methods=['GET'])
@require_auth
def get_brown_bot_watchlist():
    """Return current BrownBot watchlist."""
    try:
        return jsonify({'success': True, 'watchlist': db_manager.get_brown_watchlist()})
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
        db_manager.add_to_brown_watchlist(symbol, note, trade_type)
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
        db_manager.remove_from_brown_watchlist(symbol)
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
            app_logger.info("🔄 Force reconnecting to DAS...")
            
            success = trading_bot.force_reconnect_das()
            
            if success:
                app_logger.info("✅ Successfully reconnected to DAS")
                return jsonify({
                    'success': True,
                    'message': 'Successfully reconnected to DAS',
                    'data': {
                        'das_connected': True
                    },
                    'timestamp': datetime.now().isoformat()
                })
            else:
                app_logger.error("❌ Failed to reconnect to DAS")
                return jsonify({
                    'success': False,
                    'error': 'Failed to reconnect to DAS. Please ensure DAS Trader is running.',
                    'data': {
                        'das_connected': False
                    }
                }), 500
            
    except Exception as e:
        app_logger.error(f"Error managing DAS connection: {e}")
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
def get_trades():
    """Get trade history with optional filtering"""
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
        
        # Get trades from database
        trades = db_manager.get_trades(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit
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
        app_logger.error(f"Error importing DAS trades: {e}")
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

@app.route('/api/positions/summary', methods=['GET'])
def get_positions_summary():
    """Get positions-based summary statistics for dashboard"""
    try:
        from database import db_manager
        
        # Get positions summary from database
        summary = db_manager.get_positions_summary()
        
        if summary:
            return jsonify({
                'success': True,
                'data': summary,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No positions data found'
            }), 404
    except Exception as e:
        app_logger.error(f"Error getting positions summary: {e}")
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
        app_logger.error(f"Error syncing trades from DAS: {e}")
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
@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get position history with optional filtering"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        type_filter = request.args.get('type')
        limit = int(request.args.get('limit', 100))
        
        # Validate limit
        if limit > 1000:
            limit = 1000
        
        # Convert type_filter to int if provided
        if type_filter:
            try:
                type_filter = int(type_filter)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid type parameter. Must be a number.'
                }), 400
        
        # Get positions from database
        positions = db_manager.get_positions(
            symbol=symbol,
            type_filter=type_filter,
            limit=limit
        )
        
        # Get summary statistics
        summary = db_manager.get_position_summary(
            symbol=symbol,
            type_filter=type_filter
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
        app_logger.error(f"Error getting positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/sync-das', methods=['POST'])
def sync_positions_from_das():
    """Sync positions from DAS to database"""
    if not DAS_ENABLED:
        return jsonify({'success': False, 'error': 'DAS integration is disabled'}), 503

    try:
        from das_integration import sync_positions_from_das
        
        success, message, count = sync_positions_from_das()
        
        return jsonify({
            'success': success,
            'message': message,
            'data': {
                'synced_count': count
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error syncing positions from DAS: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/upsert', methods=['POST'])
def upsert_position():
    """Upsert a position to the database"""
    try:
        from database import db_manager
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['symbol', 'quantity', 'avg_price', 'position_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Upsert position to database
        success, message = db_manager.upsert_position(data)
        
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
        app_logger.error(f"Error upserting position: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Daily Position History API endpoints
@app.route('/api/positions/daily', methods=['GET'])
def get_daily_positions():
    """Get daily position history with optional filtering"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        type_filter = request.args.get('type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 1000))
        
        # Validate limit
        if limit > 5000:
            limit = 5000
        
        # Convert type_filter to int if provided
        if type_filter:
            try:
                type_filter = int(type_filter)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid type parameter. Must be a number.'
                }), 400
        
        # Get daily positions from database
        positions = db_manager.get_daily_positions(
            symbol=symbol,
            type_filter=type_filter,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        # Get summary statistics
        summary = db_manager.get_daily_position_summary(
            symbol=symbol,
            type_filter=type_filter,
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
        app_logger.error(f"Error getting daily positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        symbol = request.args.get('symbol')
        type_filter = request.args.get('type')
        
        # Validate required parameters
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'error': 'start_date and end_date parameters are required'
            }), 400
        
        # Validate date format (YYYY-MM-DD)
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD.'
            }), 400
        
        # Convert type_filter to int if provided
        if type_filter:
            try:
                type_filter = int(type_filter)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid type parameter. Must be a number.'
                }), 400
        
        # Get positions for the date range
        positions = db_manager.get_daily_positions(
            symbol=symbol,
            type_filter=type_filter,
            start_date=start_date,
            end_date=end_date,
            limit=1000
        )
        
        return jsonify({
            'success': True,
            'data': {
                'positions': positions,
                'start_date': start_date,
                'end_date': end_date,
                'count': len(positions)
            },
            'timestamp': datetime.now().isoformat()
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
@app.route('/api/positions/total_positions', methods=['GET'])
def get_total_positions():
    """Get total count of positions"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get total positions count from database
        total_count = db_manager.get_total_positions_count(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'total_positions': total_count
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting total positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/total_pnl', methods=['GET'])
def get_total_pnl():
    """Get total P&L from realized positions"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get total P&L from database
        total_pnl = db_manager.get_total_positions_pnl(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'total_pnl': total_pnl
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting total P&L: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/winrate', methods=['GET'])
def get_winrate():
    """Get win rate from positions"""
    try:
        from database import db_manager
        
        # Get query parameters
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get win rate from database
        win_rate = db_manager.get_positions_winrate(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'win_rate': win_rate
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting win rate: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/daily-pnl', methods=['GET'])
def get_daily_pnl():
    """Get daily P&L data for charting"""
    try:
        from database import db_manager
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get daily P&L data from database
        daily_data = db_manager.get_daily_pnl_data(
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'daily_pnl': daily_data
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting daily P&L data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/cumulative-pnl', methods=['GET'])
def get_cumulative_pnl():
    """Get cumulative P&L data for growth tracking"""
    try:
        from database import db_manager
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get cumulative P&L data from database
        cumulative_data = db_manager.get_cumulative_pnl_data(
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'cumulative_pnl': cumulative_data
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting cumulative P&L data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/pie-chart/long-short', methods=['GET'])
def get_long_short_pnl():
    """Get P&L breakdown by long vs short positions for pie chart"""
    try:
        from database import db_manager
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get long/short P&L data from database
        long_short_data = db_manager.get_long_short_pnl_data(
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'long_short_pnl': long_short_data
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting long/short P&L data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/pie-chart/symbols', methods=['GET'])
def get_symbol_pnl():
    """Get P&L breakdown by symbol for pie chart"""
    try:
        from database import db_manager
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 10, type=int)
        
        # Get symbol P&L data from database
        symbol_data = db_manager.get_symbol_pnl_data(
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'data': {
                'symbol_pnl': symbol_data
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting symbol P&L data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/pie-chart/win-loss', methods=['GET'])
def get_win_loss_pnl():
    """Get P&L breakdown by winning vs losing trades for pie chart"""
    try:
        from database import db_manager
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get win/loss P&L data from database
        win_loss_data = db_manager.get_win_loss_pnl_data(
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'win_loss_pnl': win_loss_data
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting win/loss P&L data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/positions/pie-chart/monthly', methods=['GET'])
def get_monthly_pnl():
    """Get P&L breakdown by month for pie chart"""
    try:
        from database import db_manager
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get monthly P&L data from database
        monthly_data = db_manager.get_monthly_pnl_data(
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'data': {
                'monthly_pnl': monthly_data
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting monthly P&L data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    global websocket_connected
    websocket_connected = True
    app_logger.info("WebSocket client connected")
    emit('status', {'message': 'Connected to gap-up detection server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    global websocket_connected
    websocket_connected = False
    app_logger.info("WebSocket client disconnected")

# Note: Stock subscriptions are handled by DAS integration, not WebSocket
# WebSocket is only used for gap-up data broadcasts

def broadcast_gap_ups():
    """Broadcast real-time gap-up data to connected clients"""
    if websocket_connected and real_time_gap_ups:
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

    while True:
        try:
            if REAL_DATA_AVAILABLE:
                from gap_up_detector import check_market_timing
                import pytz as _pytz
                _et = _pytz.timezone('US/Eastern')
                _now_et = datetime.now(_et)
                market_status = check_market_timing()
                interval      = INTERVALS.get(market_status, 300)

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

            time.sleep(interval)
        except Exception as e:
            app_logger.error(f"Error updating gap-ups: {e}")
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
    """Return the most recent weekday as YYYY-MM-DD (skips weekends)."""
    d = datetime.now()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def _filter_candidates(all_movers, min_vol=300_000, min_chg=0.5, max_chg=22):
    """Filter a Polygon snapshot tickers list for swing-eligible stocks."""
    candidates = []
    seen = set()
    for t in all_movers:
        sym   = t.get('ticker', '')
        day   = t.get('day', {})
        price = day.get('c') or day.get('vw') or 0
        vol   = day.get('v', 0)
        chg   = t.get('todaysChangePerc', 0)
        hi    = day.get('h', price)
        lo    = day.get('l', price)

        if sym in seen or not price:
            continue
        if price < 8 or price > 700:
            continue
        if vol < min_vol:
            continue
        if len(sym) > 5 or '/' in sym or '.' in sym:
            continue
        if abs(chg) < min_chg or abs(chg) > max_chg:
            continue

        day_range_pct = round((hi - lo) / price * 100, 1) if price else 0
        candidates.append({
            'ticker':    sym,
            'price':     round(price, 2),
            'chg_pct':   round(chg, 2),
            'volume_m':  round(vol / 1_000_000, 2),
            'day_range': day_range_pct,
            'direction': 'gainer' if chg > 0 else 'loser',
        })
        seen.add(sym)
        if len(candidates) >= 30:
            break
    return candidates


@app.route('/api/swing-daily-picks')
def swing_daily_picks():
    """
    Daily swing trade hot picks across the whole market.
    Fetches Polygon's top gainers + losers, filters for swing-eligible candidates,
    sends the shortlist to Claude which returns 6-8 ranked picks with reasoning.
    Cached per trading day. When market is closed, returns last session's picks
    (or a curated fallback) with a clear 'market_closed' flag.
    """
    import requests as _req

    polygon_key = os.environ.get('POLYGON_API_KEY', '')
    market_open  = _is_market_open()
    session_date = _last_trading_date()  # last weekday, even if today is weekend/after-hours

    # Return cached result for today's session if available
    if session_date in _daily_picks_cache:
        payload = dict(_daily_picks_cache[session_date])
        payload['cached'] = True
        payload['market_open'] = market_open
        return jsonify(payload)

    if not AI_AGENT_AVAILABLE:
        return jsonify({'success': False, 'error': 'AI not available'}), 503

    try:
        # ── Step 1: fetch gainers + losers snapshots ───────────────────────
        def _fetch_movers(direction):
            url = (
                f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/{direction}"
                f"?apiKey={polygon_key}"
            )
            r = _req.get(url, timeout=12)
            r.raise_for_status()
            return r.json().get('tickers', [])

        gainers = _fetch_movers('gainers')
        losers  = _fetch_movers('losers')
        all_movers = gainers + losers

        # ── Step 2: filter — try strict first, fall back to looser thresholds ─
        candidates = _filter_candidates(all_movers, min_vol=500_000, min_chg=1.0)
        if len(candidates) < 6:
            # Market may be closed / pre-market — relax filters
            candidates = _filter_candidates(all_movers, min_vol=300_000, min_chg=0.3)

        if not candidates:
            # Nothing at all from Polygon — market is definitely closed / weekend
            return jsonify({
                'success':      True,
                'market_open':  False,
                'market_closed_msg': 'US markets are currently closed. Picks will refresh on the next trading day.',
                'picks':        [],
                'market_note':  '',
                'date':         session_date,
                'cached':       False,
            })

        # ── Step 3: send to Claude for ranking ────────────────────────────
        rows = '\n'.join(
            f"{c['ticker']:6s}  ${c['price']:>7.2f}  {'+' if c['chg_pct']>0 else ''}{c['chg_pct']:>6.2f}%"
            f"  vol {c['volume_m']:.1f}M  range {c['day_range']}%  ({c['direction']})"
            for c in candidates
        )

        market_ctx = (
            "Note: this data is from the most recent completed trading session (market is currently closed)."
            if not market_open else ""
        )

        prompt = f"""You are an expert swing trader scanning for the best setups on {session_date}.
{market_ctx}

Below are market movers that passed the liquidity filter.
Pick the 6-8 BEST swing trading candidates for a 3-10 day hold.
Prefer: strong volume confirmation, clear technical structure, reasonable day range.
Avoid: pump-and-dump patterns, thin float, pure speculation.

CANDIDATES
{rows}

Return ONLY a JSON object — no markdown, no commentary:
{{
  "picks": [
    {{
      "ticker": "SYM",
      "grade": "A|B|C",
      "bias": "Bullish|Bearish",
      "reason": "One sentence on why this is a swing candidate",
      "entry_zone": "price or range string",
      "watch_for": "one short condition (e.g. hold above $X, volume > Y)",
      "risk": "key stop or invalidation level"
    }}
  ],
  "market_note": "1-2 sentence overall market context for swing traders"
}}"""

        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=700,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()

        ai_result = json.loads(raw)

        result = {
            'success':            True,
            'market_open':        market_open,
            'date':               session_date,
            'picks':              ai_result.get('picks', []),
            'market_note':        ai_result.get('market_note', ''),
            'candidates_scanned': len(candidates),
            'cached':             False,
        }
        _daily_picks_cache[session_date] = result
        return jsonify(result)

    except json.JSONDecodeError as jde:
        return jsonify({'success': False, 'error': f'AI parse error: {jde}'}), 500
    except Exception as exc:
        app_logger.error(f"swing-daily-picks error: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


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
    polygon_key = os.environ.get('POLYGON_API_KEY', '')

    # Cache check
    cached = _cache_get(_swing_cache, ticker, _SWING_TTL)
    if cached:
        cached['cached'] = True
        return jsonify(cached)

    try:
        import requests as _req

        # ── Fetch ~300 days of daily bars ────────────────────────────────────
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=420)  # extra buffer for weekends/holidays
        url = (
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/"
            f"{start_dt.strftime('%Y-%m-%d')}/{end_dt.strftime('%Y-%m-%d')}"
            f"?adjusted=true&sort=asc&limit=300&apiKey={polygon_key}"
        )
        resp = _req.get(url, timeout=10)
        resp.raise_for_status()
        poly_data = resp.json()
        bars = poly_data.get('results', [])

        if len(bars) < 30:
            return jsonify({'success': False, 'error': 'Not enough price history'}), 422

        technicals = _compute_technicals(bars)
        if 'error' in technicals:
            return jsonify({'success': False, 'error': technicals['error']}), 422

        # ── Sector context ────────────────────────────────────────────────────
        try:
            sector_info, sector_perf = _get_sector_context(ticker, polygon_key)
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


def _send_trial_expiry_reminders():
    """
    Background loop — runs every hour, sends a reminder email to users whose
    trial expires in ~24 hours and haven't received the reminder yet.
    """
    from_email   = os.getenv('CONTACT_EMAIL_FROM', '')
    app_password = os.getenv('GMAIL_APP_PASSWORD', '')

    while True:
        try:
            from database import db_manager as _db
            users = _db.get_trial_expiring_users(hours_from_now=24, window_hours=2)

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
            app_logger.error(f"Trial reminder loop error: {exc}")

        # Check once per hour
        time.sleep(3600)


# Start background gap-up monitor — runs under both `python app.py` and gunicorn
_bg_thread_started = False
def _start_background_tasks():
    global _bg_thread_started
    if not _bg_thread_started:
        _bg_thread_started = True
        update_thread = threading.Thread(target=update_real_time_gap_ups, daemon=True)
        update_thread.daemon = True
        update_thread.start()
        app_logger.info("✅ Gap-up background monitor started")

        reminder_thread = threading.Thread(target=_send_trial_expiry_reminders, daemon=True)
        reminder_thread.start()
        app_logger.info("✅ Trial expiry reminder service started")

_start_background_tasks()

if __name__ == '__main__':
    
    # DAS Trader integration is disabled — skip DAS sync services
    if DAS_ENABLED:
        if SCHEDULED_SYNC_AVAILABLE:
            try:
                start_scheduled_sync()
                app_logger.info("✅ Scheduled DAS sync service started")
            except Exception as e:
                app_logger.error(f"❌ Failed to start scheduled DAS sync: {e}")
        else:
            app_logger.warning("⚠️ Scheduled DAS sync not available")

        start_position_sync_scheduler()
    else:
        app_logger.info("ℹ️ DAS integration disabled — skipping DAS sync services")

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