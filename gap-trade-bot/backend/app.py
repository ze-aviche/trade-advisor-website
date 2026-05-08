#!/usr/bin/env python3
"""
Gap-Up Detection Web API
Flask backend for the gap-up detection dashboard
"""
import os
import sys
import json
import random
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

# Feature flag: set to True to re-enable DAS Trader integration
DAS_ENABLED = False
if not DAS_ENABLED:
    BOT_AVAILABLE = False
    SCHEDULED_SYNC_AVAILABLE = False

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gap-up-detection-web-2024')

_cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5000').split(',')
CORS(app, origins=_cors_origins)
socketio = SocketIO(app, cors_allowed_origins=_cors_origins, async_mode='eventlet')

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
tracking_thread = None  # Background thread for continuous tracking
tracking_active = False  # Flag to control tracking thread
active_positions = {}  # Store active positions entered by the bot

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
    global entry_bot_logs
    timestamp = datetime.now().isoformat()
    log_entry = {
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

def get_real_stock_data(symbol):
    """Get real stock data using DAS CMDAPI Level 1 subscription"""
    if not DAS_ENABLED:
        return None

    try:
        from datetime import datetime

        # Get the shared DAS connection
        connection = get_das_connection()
        if connection is None:
            app_logger.error(f"❌ No DAS connection available for {symbol}")
            return None
        
        # Subscribe to Level 1 data for the symbol
        subscribe_script = f"SB {symbol.upper()} Lv1\r\n"
        result = connection.SendScript(bytearray(subscribe_script, encoding="ascii"))
        
        if result and result.strip():
            # Parse the Level 1 response
            quote_data = _parse_das_level1_response(result, symbol.upper())
            if quote_data:
                app_logger.info(f"✅ DAS Level 1 data for {symbol}: Price=${quote_data['current_price']}, Volume={quote_data['volume']}M, Dollar Vol=${quote_data['dollar_volume']}M")
                return quote_data
        
        app_logger.warning(f"No DAS Level 1 data available for {symbol}")
        return None
        
    except Exception as e:
        app_logger.error(f"Error in get_real_stock_data for {symbol}: {e}")
        # If there's a connection error, try to reset the connection
        if "already connected" in str(e) or "10056" in str(e):
            app_logger.warning("🔄 Resetting DAS connection due to connection error")
            close_das_connection()
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
    """Check if entry conditions are met for a symbol"""
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
    """Place an order in DAS using CMDAPI"""
    if not DAS_ENABLED:
        return False, None, "DAS integration is disabled"

    try:
        # Import CMDAPI classes
        from cmdapi.CMDAPI_PYTHON import cmdAPI
        import uuid
        
        # Get the shared DAS connection
        connection = get_das_connection()
        if connection is None:
            add_entry_bot_log('error', f"❌ No DAS connection available for order placement")
            return False, None, "No DAS connection available"
        
        # Generate unique order ID
        unID = int(uuid.uuid4())
        
        # Build the NEWORDER command based on order type
        if order_type == 'MKT':
            # Market order: NEWORDER token b/s symbol route share MKT TIF=DAY
            script = f"NEWORDER {unID} {order_side} {symbol.upper()} {route} {quantity} MKT TIF=DAY"
        elif order_type == 'LIMIT':
            # Limit order: NEWORDER token b/s symbol route share price TIF=DAY
            script = f"NEWORDER {unID} {order_side} {symbol.upper()} {route} {quantity} {limit_price} TIF=DAY"
        else:
            raise ValueError(f"Unsupported order type: {order_type}")
        
        add_entry_bot_log('info', f"📡 Sending DAS order: {script}")
        
        # Send order to DAS
        result = connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
        
        add_entry_bot_log('info', f"📋 DAS order result: {result}")
        
        # Check if order was successful
        if "SUCCESS" in result.upper() or "ACCEPTED" in result.upper():
            add_entry_bot_log('info', f"✅ DAS order placed successfully for {symbol}")
            return True, unID, result
        else:
            add_entry_bot_log('error', f"❌ DAS order failed for {symbol}: {result}")
            return False, None, result
            
    except Exception as e:
        add_entry_bot_log('error', f"❌ Error placing DAS order for {symbol}: {e}")
        # If there's a connection error, try to reset the connection
        if "already connected" in str(e) or "10056" in str(e):
            add_entry_bot_log('warning', "🔄 Resetting DAS connection due to connection error")
            close_das_connection()
        return False, None, str(e)

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

        success, message = auth_manager.register_user(
            data.get('username', ''),
            data.get('email', ''),
            data.get('password', ''),
            first_name=(data.get('first_name') or '').strip() or None,
            last_name=(data.get('last_name') or '').strip() or None,
            address=(data.get('address') or '').strip() or None,
            profession=(data.get('profession') or '').strip() or None,
            annual_income_range=(data.get('annual_income_range') or '').strip() or None,
        )
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app_logger.error(f"Error registering user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
        safe_user = {
            'id': user.get('id'),
            'username': user.get('username'),
            'email': user.get('email'),
            'system_role': user.get('system_role'),
            'subscription_tier': user.get('subscription_tier', 'basic'),
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
        
        app_logger.info(f"📊 Fetching historical data for {ticker} - {days} days, cache: {use_cache}")
        
        # Add timeout protection for historical data fetching using threading
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def fetch_data():
            try:
                app_logger.info(f"🔄 Starting data fetch for {ticker}")
                data = get_historical_gap_up_data(ticker, days=days, use_cache=use_cache)
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
        
        return jsonify({
            'success': True,
            'data': historical_data,
            'ticker': ticker,
            'days': days,
            'count': len(historical_data),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app_logger.error(f"❌ Unexpected error getting historical data for {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }), 500

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
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
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
    """Update bot strategies"""
    try:
        if not BOT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Bot not available'
            }), 503
        
        data = request.get_json()
        success = trading_bot.update_strategies(data)
        if success:
            return jsonify({
                'success': True,
                'message': 'Strategies updated successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update strategies'
            }), 500
    except Exception as e:
        app_logger.error(f"Error updating strategies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        
        # Get active positions from bot
        active_positions = trading_bot.active_positions
        
        # Convert positions to serializable format
        positions_data = []
        for symbol, position in active_positions.items():
            positions_data.append({
                'symbol': position.symbol,
                'type': position.type,
                'size': position.size,
                'entry_price': position.entry_price,
                'profit_target': position.profit_target,
                'stop_loss': position.stop_loss,
                'entry_time': position.entry_time,
                'position_id': position.position_id
            })
        
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
        
        # New DAS order parameters
        order_side = data.get('order_side', 'B')  # B for Buy, S for Sell
        route = data.get('route', 'SMAT')  # Default route
        quantity = data.get('quantity', 100)  # Default quantity
        order_type = data.get('order_type', 'MKT')  # MKT for Market, LIMIT for Limit orders
        limit_price = data.get('limit_price')  # Only used for LIMIT orders
        
        if not all([symbol, total_volume, dollar_volume, entry_time]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: symbol, total_volume, dollar_volume, entry_time'
            }), 400
        
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
            'total_volume': float(total_volume),
            'dollar_volume': float(dollar_volume),
            'entry_time': entry_time,
            # DAS order parameters
            'order_side': order_side,
            'route': route,
            'quantity': int(quantity),
            'order_type': order_type,
            'limit_price': limit_price,
            'submitted_at': datetime.now().isoformat(),
            'status': 'tracking'
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
            positions_list.append({
                'position_id': position_id,
                'symbol': position['symbol'],
                'entry_price': position['entry_price'],
                'entry_time': position['entry_time'],
                'quantity': position['quantity'],
                'status': position['status']
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