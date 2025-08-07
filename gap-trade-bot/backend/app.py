#!/usr/bin/env python3
"""
Trading Advisor Web API
Flask backend for the Vue.js trading dashboard
"""
import os
import sys
import json
import random
import threading
import time
from datetime import datetime, timedelta, time as time_class
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from logging_config import setup_logging, get_logger, log_api_request, log_performance, log_error

# Load environment variables
load_dotenv()

# Setup comprehensive logging
setup_logging(log_level='INFO', log_dir='logs')
app_logger = get_logger('app')

# Import real gap-up detection functions
try:
    from gap_up_detector import get_gap_up_stocks, get_gap_up_stocks_for_frontend
    from historical_data import get_historical_gap_up_data
    from real_time_detector import real_time_detector
    REAL_DATA_AVAILABLE = True
except ImportError as e:
    app_logger.warning(f"Warning: Could not import gap_up_detector: {e}")
    REAL_DATA_AVAILABLE = False

# Import auth functions (these should always be available)
try:
    from auth import auth_manager, require_auth
except ImportError as e:
    app_logger.warning(f"Warning: Could not import auth: {e}")
    # Create dummy auth functions if import fails
    auth_manager = None
    require_auth = lambda f: f  # No-op decorator

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trading-advisor-web-2024'
CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variables for real-time data
active_stocks = set()
price_cache = {}
websocket_connected = False
real_time_gap_ups = []  # Store real-time detected gap-ups

def check_bot_status():
    """Check if the trading bot is running"""
    try:
        import os
        import psutil
        
        # Check for bot PID file
        bot_pid_file = os.path.join(os.path.dirname(__file__), 'bot', 'bot.pid')
        
        if os.path.exists(bot_pid_file):
            try:
                with open(bot_pid_file, 'r') as f:
                    pid_content = f.read().strip()
                    print(f"PID content: {pid_content}")
                    # Remove any non-numeric characters (like %)
                    pid_content = ''.join(c for c in pid_content if c.isdigit())
                    print(f"PID content: {pid_content}")
                    if pid_content:
                        pid = int(pid_content)
                        print(f"PID: {pid}")
                    else:
                        return False
                
                # Check if process is running
                print(f"Checking posix condition: {psutil.pid_exists(pid)}")
                if psutil.pid_exists(pid):
                    try:
                        process = psutil.Process(pid)
                        print(f"Process: {process}")
                        cmdline = ' '.join(process.cmdline())
                        print(f"Cmdline: {cmdline}")
                        # Check for run_bot.py in the command line
                        if 'run_bot.py' in cmdline:
                            print(f"run_bot.py entry found in cmdline: {cmdline}")    
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        # Process exists but we can't access it or it's a zombie
                        pass
                else:
                    # Process doesn't exist, clean up the stale PID file
                    try:
                        os.remove(bot_pid_file)
                    except OSError:
                        pass
            except (ValueError, IOError):
                # Invalid PID file content or can't read file
                try:
                    os.remove(bot_pid_file)
                except OSError:
                    pass
        
        return False
    except Exception as e:
        print(f"Error checking bot status: {e}")
        return False

# Mock data for fallback when real data is not available
MOCK_GAP_UPS = [
    {
        'ticker': 'AAPL',
        'price': 150.25,
        'change': 2.5,
        'change_percent': 1.67,
        'volume': 1000000,
        'gap_percent': 3.2
    },
    {
        'ticker': 'TSLA',
        'price': 245.80,
        'change': 8.20,
        'change_percent': 3.45,
        'volume': 1500000,
        'gap_percent': 4.1
    },
    {
        'ticker': 'NVDA',
        'price': 485.50,
        'change': 15.30,
        'change_percent': 3.25,
        'volume': 2000000,
        'gap_percent': 5.8
    },
    {
        'ticker': 'AMD',
        'price': 120.75,
        'change': 4.25,
        'change_percent': 3.65,
        'volume': 800000,
        'gap_percent': 2.9
    }
]

MOCK_TRADES = [
    {
        'id': 1,
        'ticker': 'AAPL',
        'direction': 'long',
        'quantity': 100,
        'price': 148.50,
        'submitted_at': (datetime.now() - timedelta(hours=2)).isoformat(),
        'status': 'filled',
        'pnl': 175.00
    },
    {
        'id': 2,
        'ticker': 'TSLA',
        'direction': 'short',
        'quantity': 50,
        'price': 240.00,
        'submitted_at': (datetime.now() - timedelta(hours=4)).isoformat(),
        'status': 'filled',
        'pnl': -250.00
    },
    {
        'id': 3,
        'ticker': 'NVDA',
        'direction': 'long',
        'quantity': 75,
        'price': 470.00,
        'submitted_at': (datetime.now() - timedelta(hours=6)).isoformat(),
        'status': 'filled',
        'pnl': 1162.50
    },
    {
        'id': 4,
        'ticker': 'MSFT',
        'direction': 'long',
        'quantity': 200,
        'price': 320.00,
        'submitted_at': (datetime.now() - timedelta(days=1)).isoformat(),
        'status': 'filled',
        'pnl': 450.00
    },
    {
        'id': 5,
        'ticker': 'GOOGL',
        'direction': 'short',
        'quantity': 25,
        'price': 140.00,
        'submitted_at': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'filled',
        'pnl': -125.00
    }
]

MOCK_TRADE_SUMMARY = {
    'total_trades': 3,
    'winning_trades': 2,
    'losing_trades': 1,
    'total_pnl': 1087.50,
    'win_rate': 66.67,
    'avg_win': 668.75,
    'avg_loss': -250.00
}

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    emit('connected', {'status': 'connected', 'timestamp': datetime.now().isoformat()})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('subscribe_stocks')
def handle_subscribe_stocks(data):
    """Subscribe to real-time updates for specific stocks"""
    global active_stocks
    stocks = data.get('stocks', [])
    active_stocks.update(stocks)
    print(f"Subscribed to stocks: {stocks}")
    emit('subscribed', {'stocks': list(active_stocks)})

@socketio.on('unsubscribe_stocks')
def handle_unsubscribe_stocks(data):
    """Unsubscribe from real-time updates for specific stocks"""
    global active_stocks
    stocks = data.get('stocks', [])
    active_stocks.difference_update(stocks)
    print(f"Unsubscribed from stocks: {stocks}")
    emit('unsubscribed', {'stocks': list(active_stocks)})

def broadcast_price_update(ticker, price_data):
    """Broadcast price update to all connected clients"""
    socketio.emit('price_update', {
        'ticker': ticker,
        'data': price_data,
        'timestamp': datetime.now().isoformat()
    })

def handle_real_time_gap_up(gap_up_data):
    """Handle real-time gap-up detection"""
    global real_time_gap_ups
    
    # Add to real-time gap-ups list
    real_time_gap_ups.append(gap_up_data)
    
    # Keep only last 50 gap-ups
    if len(real_time_gap_ups) > 50:
        real_time_gap_ups = real_time_gap_ups[-50:]
    
    # Broadcast to all connected clients
    socketio.emit('real_time_gap_up', {
        'data': gap_up_data,
        'timestamp': datetime.now().isoformat()
    })
    
    app_logger.info(f"🚨 Real-time gap-up broadcast: {gap_up_data['ticker']} - {gap_up_data['gap_percent']}%")

def handle_trading_opportunity(gap_up_data):
    """Handle real-time trading opportunities (25%+ gap-ups)"""
    try:
        ticker = gap_up_data['ticker']
        gap_percent = gap_up_data['gap_percent']
        
        # Send SMS and Email notifications
        from notification_service import notification_service
        notification_service.notify_gap_up_detection(gap_up_data)
        
        # Notify the trading bot for subscription
        if trading_bot.is_running:
            import asyncio
            asyncio.create_task(trading_bot.auto_subscribe_real_time_gap_up(ticker, gap_percent))
            app_logger.warning(f"🎯 TRADING OPPORTUNITY: Notifying bot to subscribe to {ticker} ({gap_percent:.1f}%)")
        else:
            app_logger.info(f"⏸️ Bot not running, skipping trading opportunity for {ticker}")
            
    except Exception as e:
        app_logger.error(f"❌ Error handling trading opportunity for {gap_up_data.get('ticker', 'unknown')}: {e}")

def start_price_update_thread():
    """Start background thread for price updates"""
    def price_update_worker():
        while True:
            if active_stocks and REAL_DATA_AVAILABLE:
                try:
                    # Get real-time prices for active stocks
                    for ticker in active_stocks:
                        try:
                            from gap_up_detector import get_current_price, get_polygon_client
                            polygon_client = get_polygon_client()
                            current_price = get_current_price(ticker, polygon_client)
                            
                            if current_price is not None:
                                # Get previous price from cache
                                previous_price = price_cache.get(ticker, current_price)
                                change = current_price - previous_price
                                change_percent = (change / previous_price) * 100 if previous_price > 0 else 0
                                
                                price_data = {
                                    'price': round(current_price, 2),
                                    'change': round(change, 2),
                                    'change_percent': round(change_percent, 2),
                                    'volume': price_cache.get(f"{ticker}_volume", 0)
                                }
                                
                                # Update cache
                                price_cache[ticker] = current_price
                                
                                # Broadcast update
                                broadcast_price_update(ticker, price_data)
                                
                        except Exception as e:
                            app_logger.error(f"Error updating price for {ticker}: {e}")
                            continue
                            
                except Exception as e:
                    app_logger.error(f"Error in price update worker: {e}")
                    
            # Sleep for 1 second before next update
            time.sleep(1)
    
    # Start the background thread
    thread = threading.Thread(target=price_update_worker, daemon=True)
    thread.start()
    app_logger.info("✅ Real-time price update thread started")

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        success, message = auth_manager.register_user(username, email, password)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login a user"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        success, result = auth_manager.login_user(username, password)
        
        if success:
            response = jsonify({
                'success': True,
                'message': 'Login successful',
                'data': result
            })
            
            # Set session cookie
            response.set_cookie(
                'session_token',
                result['session_token'],
                max_age=24*60*60,  # 24 hours
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite='Lax'
            )
            
            return response
        else:
            return jsonify({
                'success': False,
                'error': result
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Logout a user"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not session_token:
            session_token = request.cookies.get('session_token')
        
        success, message = auth_manager.logout_user(session_token)
        
        response = jsonify({
            'success': True,
            'message': message
        })
        
        # Remove session cookie
        response.delete_cookie('session_token')
        
        return response
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/profile')
@require_auth
def get_profile():
    """Get user profile"""
    try:
        return jsonify({
            'success': True,
            'data': request.user
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/preferences', methods=['PUT'])
@require_auth
def update_preferences():
    """Update user preferences"""
    try:
        data = request.get_json()
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not session_token:
            session_token = request.cookies.get('session_token')
        
        success, message = auth_manager.update_user_preferences(session_token, data)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'real_data_available': REAL_DATA_AVAILABLE,
        'websocket_connected': websocket_connected,
        'active_stocks_count': len(active_stocks),
        'bot_running': check_bot_status()
    })

@app.route('/api/gap-ups')
def get_gap_ups():
    """Get current gap-up stocks"""
    try:
        if REAL_DATA_AVAILABLE:
            app_logger.info("🔍 Attempting to fetch real gap-up data...")
            # Use real data from Polygon API - show all gap-ups for frontend
            gap_ups = get_gap_up_stocks_for_frontend()
            if gap_ups and len(gap_ups) > 0:
                app_logger.info(f"✅ Successfully fetched {len(gap_ups)} real gap-up stocks")
                
                # Add real-time price updates for gap-up stocks
                for stock in gap_ups:
                    ticker = stock['ticker']
                    if ticker in price_cache:
                        stock['current_price'] = price_cache[ticker]
                        stock['price_change'] = price_cache.get(f"{ticker}_change", 0)
                        stock['price_change_percent'] = price_cache.get(f"{ticker}_change_percent", 0)
                
                return jsonify({
                    'success': True,
                    'data': gap_ups,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'real'
                })
            else:
                app_logger.warning("⚠️ No real gap-up data available, falling back to mock data")
        else:
            app_logger.warning("⚠️ Real data not available, using mock data")
        
        # Fallback to mock data
        updated_gap_ups = []
        for gap_up in MOCK_GAP_UPS:
            updated_gap_up = gap_up.copy()
            # Add small random variations
            updated_gap_up['price'] += random.uniform(-1, 1)
            updated_gap_up['change'] += random.uniform(-0.5, 0.5)
            updated_gap_ups.append(updated_gap_up)
        
        return jsonify({
            'success': True,
            'data': updated_gap_ups,
            'timestamp': datetime.now().isoformat(),
            'source': 'mock'
        })
    except Exception as e:
        print(f"❌ Error getting gap-ups: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/real-time-gap-ups')
def get_real_time_gap_ups():
    """Get real-time detected gap-ups"""
    try:
        return jsonify({
            'success': True,
            'data': real_time_gap_ups,
            'source': 'real-time',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_stocks():
    """Analyze specific stocks"""
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({'success': False, 'error': 'No tickers provided'}), 400
        
        analysis = []
        for ticker in tickers:
            if REAL_DATA_AVAILABLE and os.environ.get('POLYGON_API_KEY'):
                # Use real analysis
                stock_analysis = get_stock_analysis(ticker)
                if stock_analysis:
                    analysis.append(stock_analysis)
                else:
                    # Fallback to mock analysis
                    analysis.append({
                        'ticker': ticker,
                        'recommendation': random.choice(['buy', 'sell', 'hold']),
                        'confidence': random.uniform(0.6, 0.95),
                        'price_target': round(random.uniform(100, 500), 2),
                        'risk_level': random.choice(['low', 'medium', 'high']),
                        'analysis': f"Technical analysis for {ticker} shows {random.choice(['bullish', 'bearish', 'neutral'])} signals."
                    })
            else:
                # Mock analysis data
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

@app.route('/api/trades')
def get_trades():
    """Get trade history with optional period filtering or date range"""
    try:
        # Check for date range parameters first
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        ticker_filter = request.args.get('ticker', '').strip().upper()
        
        if from_date and to_date:
            # Use date range filtering
            try:
                start_date = datetime.fromisoformat(from_date)
                # Set end_date to end of day (23:59:59) to include all trades for that day
                end_date = datetime.fromisoformat(to_date).replace(hour=23, minute=59, second=59, microsecond=999999)
                period_days = (end_date - start_date).days
                app_logger.info(f"📅 Using date range: {from_date} to {to_date} ({period_days} days)")
            except ValueError as e:
                app_logger.error(f"Invalid date format: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }), 400
        else:
            # Fall back to period-based filtering
            period = request.args.get('period', '365')
            try:
                period_days = int(period)
            except ValueError:
                period_days = 365
            
            # Calculate the start date based on period
            start_date = datetime.now() - timedelta(days=period_days)
            end_date = datetime.now()
            app_logger.info(f"📅 Using period-based filtering: {period_days} days")
        
        # Import and use the real trading database
        try:
            from bot.trading_database import TradingDatabase
            trading_db = TradingDatabase()
            
            # Get real trade history from database
            real_trades = trading_db.get_trade_history(limit=1000)  # Get more trades to filter
            
            # Get open positions from database
            open_positions = trading_db.get_all_positions()
            
            # Filter trades based on date range and ticker
            filtered_trades = []
            
            # Process completed trades
            for trade in real_trades:
                try:
                    trade_date = datetime.fromisoformat(trade.get('entry_time', '').replace('Z', '+00:00'))
                    trade_ticker = trade.get('ticker', '').upper()
                    
                    # Check date range
                    date_match = start_date <= trade_date <= end_date
                    
                    # Check ticker filter (if specified)
                    ticker_match = True
                    if ticker_filter:
                        ticker_match = trade_ticker == ticker_filter
                    
                    if date_match and ticker_match:
                        # Format datetime to remove microseconds
                        entry_time = trade.get('entry_time')
                        if entry_time and '.' in entry_time:
                            entry_time = entry_time.split('.')[0] + 'Z'
                        
                        exit_time = trade.get('exit_time')
                        if exit_time and '.' in exit_time:
                            exit_time = exit_time.split('.')[0] + 'Z'
                        
                        # Format trade data for frontend
                        formatted_trade = {
                            'id': trade.get('id'),
                            'ticker': trade.get('ticker'),
                            'direction': trade.get('side', 'long'),
                            'quantity': trade.get('quantity', 0),
                            'price': trade.get('entry_price', 0),
                            'submitted_at': entry_time,
                            'status': trade.get('status', 'filled'),
                            'pnl': trade.get('pnl', 0),
                            'exit_price': trade.get('exit_price'),
                            'exit_time': exit_time,
                            'strategy': trade.get('strategy', 'Unknown'),
                            'broker': trade.get('broker', 'alpaca')
                        }
                        filtered_trades.append(formatted_trade)
                except (ValueError, TypeError) as e:
                    app_logger.warning(f"Invalid trade date format: {trade.get('entry_time')} - {e}")
                    continue
            
            # Process open positions
            for position in open_positions:
                try:
                    position_date = datetime.fromisoformat(position.get('entry_time', '').replace('Z', '+00:00'))
                    position_ticker = position.get('ticker', '').upper()
                    
                    # Check date range
                    date_match = start_date <= position_date <= end_date
                    
                    # Check ticker filter (if specified)
                    ticker_match = True
                    if ticker_filter:
                        ticker_match = position_ticker == ticker_filter
                    
                    if date_match and ticker_match:
                        # Format datetime to remove microseconds
                        entry_time = position.get('entry_time')
                        if entry_time and '.' in entry_time:
                            entry_time = entry_time.split('.')[0] + 'Z'
                        
                        # Format position data for frontend
                        formatted_position = {
                            'id': f"pos_{position.get('id')}",
                            'ticker': position.get('ticker'),
                            'direction': position.get('side', 'long'),
                            'quantity': position.get('quantity', 0),
                            'price': position.get('entry_price', 0),
                            'submitted_at': entry_time,
                            'status': 'open',
                            'pnl': position.get('pnl', 0),
                            'exit_price': None,
                            'exit_time': None,
                            'strategy': 'Active Position',
                            'broker': position.get('broker', 'alpaca')
                        }
                        filtered_trades.append(formatted_position)
                except (ValueError, TypeError) as e:
                    app_logger.warning(f"Invalid position date format: {position.get('entry_time')} - {e}")
                    continue
            
            # If no real trades found, fall back to mock data for demonstration
            if not filtered_trades:
                app_logger.warning("No real trades found in database, using mock data")
                if period_days <= 1:
                    filtered_trades = []
                elif period_days <= 7:
                    filtered_trades = MOCK_TRADES[:2]
                elif period_days <= 30:
                    filtered_trades = MOCK_TRADES[:3]
                else:
                    filtered_trades = MOCK_TRADES
            
        except ImportError as e:
            app_logger.error(f"Could not import TradingDatabase: {e}")
            # Fall back to mock data
            if period_days <= 1:
                filtered_trades = []
            elif period_days <= 7:
                filtered_trades = MOCK_TRADES[:2]
            elif period_days <= 30:
                filtered_trades = MOCK_TRADES[:3]
            else:
                filtered_trades = MOCK_TRADES
        
        # Calculate summary based on filtered trades
        total_trades = len(filtered_trades)
        total_pnl = sum(trade.get('pnl', 0) for trade in filtered_trades)
        winning_trades = len([t for t in filtered_trades if t.get('pnl', 0) > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        summary = {
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'win_rate': round(win_rate, 2),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'filter_type': 'date_range' if from_date and to_date else 'period',
            'period_days': (end_date - start_date).days if from_date and to_date else period_days,
            'ticker_filter': ticker_filter if ticker_filter else None
        }
        
        return jsonify({
            'success': True,
            'trades': filtered_trades,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting trades: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/start-session', methods=['POST'])
def start_session():
    """Start a new trading session"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'web_user')
        
        session_id = f"web_session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Session started successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/send-message', methods=['POST'])
def send_message():
    """Send a message to the trading agent"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        message = data.get('message')
        
        if not session_id or not message:
            return jsonify({
                'success': False,
                'error': 'Session ID and message are required'
            }), 400
        
        # Mock AI responses
        responses = [
            "Based on the current market conditions, I recommend focusing on technology stocks with strong fundamentals.",
            "The gap-up analysis shows several opportunities in the semiconductor sector.",
            "Consider implementing a stop-loss strategy to manage risk in volatile markets.",
            "Market sentiment appears bullish for growth stocks in the current session.",
            "I've identified potential breakout patterns in the stocks you mentioned."
        ]
        
        response = random.choice(responses)
        
        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system-status')
def system_status():
    """Get system status and health"""
    try:
        # Check API keys
        api_keys = {
            'GOOGLE_API_KEY': bool(os.environ.get('GOOGLE_API_KEY')),
            'ALPACA_API_KEY': bool(os.environ.get('ALPACA_API_KEY')),
            'ALPACA_SECRET_KEY': bool(os.environ.get('ALPACA_SECRET_KEY')),
            'POLYGON_API_KEY': bool(os.environ.get('POLYGON_API_KEY'))
        }
        
        return jsonify({
            'success': True,
            'status': {
                'api_keys': api_keys,
                'database': 'connected',
                'agent': 'available',
                'sessions': 0,
                'real_data_available': REAL_DATA_AVAILABLE,
                'websocket_connected': websocket_connected,
                'active_stocks_count': len(active_stocks),
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/market-data/<ticker>')
def get_market_data_endpoint(ticker):
    """Get real-time market data for a ticker"""
    try:
        if REAL_DATA_AVAILABLE and os.environ.get('POLYGON_API_KEY'):
            # Use real market data
            market_data = get_market_data(ticker)
            if market_data:
                return jsonify({
                    'success': True,
                    'data': market_data,
                    'source': 'real'
                })
        
        # Fallback to mock data
        base_price = random.uniform(50, 500)
        change = random.uniform(-10, 10)
        change_percent = (change / base_price) * 100
        
        return jsonify({
            'success': True,
            'data': {
                'ticker': ticker,
                'price': round(base_price, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'volume': random.randint(100000, 5000000),
                'timestamp': datetime.now().isoformat()
            },
            'source': 'mock'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/historical-data/<ticker>')
def get_historical_data_endpoint(ticker):
    """Get historical data for a ticker with intelligent caching"""
    start_time = time.time()
    try:
        days = request.args.get('days', 365, type=int)  # Default to 1 year
        use_cache = request.args.get('cache', 'true').lower() == 'true'
        
        app_logger.info(f"📊 Historical data request for {ticker} | Days: {days} | Cache: {use_cache}")
        log_api_request('GET', f'/api/historical-data/{ticker}', 200, user_agent=request.headers.get('User-Agent'))
        
        if REAL_DATA_AVAILABLE and os.environ.get('POLYGON_API_KEY'):
            # Use real historical data with caching
            historical_result = get_historical_gap_up_data(ticker, days, use_cache=use_cache)
            if historical_result is not None:  # Check for None, not truthiness (empty list is valid)
                # Get cache status for response
                from historical_cache import historical_cache
                cache_status = historical_cache.get_cache_status(ticker)
                
                duration = time.time() - start_time
                log_performance('historical_data_real', duration, {
                    'ticker': ticker, 
                    'days': days, 
                    'data_points': len(historical_result),
                    'cached': cache_status.get('cached', False)
                })
                
                return jsonify({
                    'success': True,
                    'data': historical_result,
                    'ticker': ticker,
                    'days': days,
                    'source': 'real',
                    'cache_info': {
                        'cached': cache_status.get('cached', False),
                        'total_records': cache_status.get('total_records', 0),
                        'last_updated': cache_status.get('last_updated'),
                        'data_range': cache_status.get('data_range')
                    }
                })
        
        # Fallback to mock data (only gap-up days)
        mock_data = []
        base_price = random.uniform(50, 500)
        
        # Generate only gap-up days (25%+ gap)
        gap_up_days = random.randint(0, 5)  # 0-5 gap-up days
        
        for i in range(gap_up_days):
            date = (datetime.now() - timedelta(days=random.randint(1, 365))).strftime('%Y-%m-%d')
            gap_percent = random.uniform(25, 100)  # 25% to 100% gap
            previous_close = base_price + random.uniform(-10, 10)
            open_price = previous_close * (1 + gap_percent / 100)
            close_price = open_price + random.uniform(-5, 5)
            high_price = max(open_price, close_price) + random.uniform(0, 3)
            low_price = min(open_price, close_price) - random.uniform(0, 3)
            
            mock_data.append({
                'date': date,
                'pd close': round(previous_close, 2),
                'premarket open': round(open_price * 1.02, 2),
                'premarket high': round(high_price * 1.01, 2),
                'premarket high time': '09:30',
                'premarket volume': random.randint(100000, 2000000),
                'open': round(open_price, 2),
                'gap up % at open': round(gap_percent, 2),
                'day high': round(high_price, 2),
                'day high time': '09:35',
                'day high %': round(gap_percent + random.uniform(0, 10), 2),
                'close price': round(close_price, 2),
                'closing percent': round(((close_price - previous_close) / previous_close) * 100, 2),
                'afterhours close': round(close_price * 1.01, 2),
                'total volume': random.randint(1000000, 50000000),
                'VWAP Crosses': None,  # Removed for performance
                'Runner/Fader': 'Runner' if close_price > open_price else 'Fader',
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'volume_millions': round(random.randint(1000000, 50000000) / 1000000, 2),
                'dollar_volume_millions': round((random.randint(1000000, 50000000) * high_price) / 1000000, 2)
            })
        
        duration = time.time() - start_time
        log_performance('historical_data_mock', duration, {'ticker': ticker, 'days': days, 'data_points': len(mock_data)})
        
        return jsonify({
            'success': True,
            'data': mock_data,
            'ticker': ticker,
            'days': days,
            'source': 'mock'
        })
    except Exception as e:
        duration = time.time() - start_time
        log_error(e, {'ticker': ticker, 'days': days, 'endpoint': 'historical_data'})
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/historical-data/batch', methods=['POST'])
def get_batch_historical_data_endpoint():
    """Get historical data for multiple tickers using optimized batch processing"""
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        days = data.get('days', 365)
        use_cache = data.get('cache', True)
        
        if not tickers:
            return jsonify({
                'success': False,
                'error': 'No tickers provided'
            }), 400
        
        if REAL_DATA_AVAILABLE and os.environ.get('POLYGON_API_KEY'):
            # Use real historical data with parallel processing
            from historical_data import get_batch_historical_data_for_tickers
            results = get_batch_historical_data_for_tickers(tickers, days, use_cache)
            
            # Get cache status for all tickers
            from historical_cache import historical_cache
            cache_info = {}
            for ticker in tickers:
                cache_status = historical_cache.get_cache_status(ticker)
                cache_info[ticker] = {
                    'cached': cache_status.get('cached', False),
                    'total_records': cache_status.get('total_records', 0),
                    'last_updated': cache_status.get('last_updated'),
                    'data_range': cache_status.get('data_range')
                }
            
            return jsonify({
                'success': True,
                'data': results,
                'tickers': tickers,
                'days': days,
                'source': 'real',
                'cache_info': cache_info
            })
        
        # Fallback to mock data for multiple tickers
        mock_results = {}
        for ticker in tickers:
            mock_data = []
            base_price = random.uniform(50, 500)
            gap_up_days = random.randint(0, 5)
            
            for i in range(gap_up_days):
                date = (datetime.now() - timedelta(days=random.randint(1, 365))).strftime('%Y-%m-%d')
                gap_percent = random.uniform(25, 100)
                previous_close = base_price + random.uniform(-10, 10)
                open_price = previous_close * (1 + gap_percent / 100)
                close_price = open_price + random.uniform(-5, 5)
                high_price = max(open_price, close_price) + random.uniform(0, 3)
                low_price = min(open_price, close_price) - random.uniform(0, 3)
                
                mock_data.append({
                    'date': date,
                    'pd close': round(previous_close, 2),
                    'premarket open': round(open_price * 1.02, 2),
                    'premarket high': round(high_price * 1.01, 2),
                    'premarket high time': '09:30',
                    'premarket volume': random.randint(100000, 2000000),
                    'open': round(open_price, 2),
                    'gap up % at open': round(gap_percent, 2),
                    'day high': round(high_price, 2),
                    'day high time': '09:35',
                    'day high %': round(gap_percent + random.uniform(0, 10), 2),
                    'close price': round(close_price, 2),
                    'closing percent': round(((close_price - previous_close) / previous_close) * 100, 2),
                    'afterhours close': round(close_price * 1.01, 2),
                    'total volume': random.randint(1000000, 50000000),
                    'VWAP Crosses': None,  # Removed for performance
                    'Runner/Fader': 'Runner' if close_price > open_price else 'Fader',
                    'high': round(high_price, 2),
                    'low': round(low_price, 2),
                    'volume_millions': round(random.randint(1000000, 50000000) / 1000000, 2),
                    'dollar_volume_millions': round((random.randint(1000000, 50000000) * high_price) / 1000000, 2)
                })
            
            mock_results[ticker] = mock_data
        
        return jsonify({
            'success': True,
            'data': mock_results,
            'tickers': tickers,
            'days': days,
            'source': 'mock'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/status')
def get_bot_status():
    """Get comprehensive bot status including subscribed stocks, analysis results, and positions"""
    app_logger.info("🔍 API: /api/bot/status called")
    try:
        # Check if bot is running
        is_running = check_bot_status()
        
        # Get bot status from file
        bot_status_file = 'bot/bot_status.json'
        if os.path.exists(bot_status_file):
            with open(bot_status_file, 'r') as f:
                bot_status = json.load(f)
                is_running = bot_status.get('status') == 'running'
        else:
            is_running = False
        
        # Get tracked symbols from bot
        tracked_symbols = []
        subscribed_stocks = []
        if is_running:
            try:
                # Import the trading bot to get tracked symbols
                from bot.trading_bot import trading_bot
                tracked_symbols = list(trading_bot.tracked_symbols)
                app_logger.info(f"📊 Retrieved {len(tracked_symbols)} tracked symbols from bot")
                
                # Get gap-up data for subscribed stocks
                from gap_up_detector import get_gap_up_stocks_for_frontend
                gap_up_stocks = get_gap_up_stocks_for_frontend()
                gap_up_dict = {stock['ticker']: stock for stock in gap_up_stocks}
                
                # Create subscribed stocks with full details
                for ticker in tracked_symbols:
                    stock_data = gap_up_dict.get(ticker, {})
                    subscribed_stock = {
                        'ticker': ticker,
                        'currentPrice': stock_data.get('price', 0),
                        'gapPercent': stock_data.get('gap_percent', 0),
                        'volume': stock_data.get('volume', 0),
                        'subscribed': True
                    }
                    subscribed_stocks.append(subscribed_stock)
                    app_logger.info(f"✅ Added subscribed stock: {ticker}")
                
            except Exception as e:
                app_logger.warning(f"⚠️ Error getting tracked symbols from bot: {e}")
                tracked_symbols = []
                subscribed_stocks = []
        
        # Get positions directly from Alpaca (real-time)
        positions = []
        if is_running:
            try:
                from bot.alpaca_client import AlpacaClient
                alpaca_client = AlpacaClient()
                
                # Get current positions directly from Alpaca
                alpaca_positions = alpaca_client.get_positions()
                app_logger.info(f"📊 Retrieved {len(alpaca_positions)} positions from Alpaca")
                
                for ticker, position in alpaca_positions.items():
                    # Get strategy information for this position
                    strategy_info = None
                    try:
                        # Since database doesn't have actual strategy info, use default strategy
                        strategy_key = 'breakOut'  # Default strategy for all positions
                        
                        # Load strategy configuration
                        from config.strategy_manager import StrategyConfigManager
                        strategy_manager = StrategyConfigManager()
                        strategy_config = strategy_manager.get_strategy_by_key(strategy_key)
                        
                        if strategy_config:
                            backend_config = strategy_config.get('backend_config', {})
                            position_sizing = strategy_config.get('position_sizing', {})
                            
                            # Calculate position sizing and stop loss based on entry price
                            entry_price = float(position.get('avg_entry_price', 0))
                            quantity = int(position.get('quantity', 0))
                            
                            # Calculate target and stop loss prices
                            target_multiplier = backend_config.get('target_multiplier', 1.25)
                            stop_loss_multiplier = backend_config.get('stop_loss_multiplier', 0.85)
                            
                            target_price = round(entry_price * target_multiplier, 2)
                            stop_loss_price = round(entry_price * stop_loss_multiplier, 2)
                            
                            # Calculate position value and sizing info
                            position_value = entry_price * quantity
                            max_position_value = position_sizing.get('max_position_value', 10000)
                            max_concentration = position_sizing.get('max_portfolio_concentration', 0.05)
                            
                            strategy_info = {
                                'strategy': strategy_key,
                                'targetPrice': target_price,
                                'stopLossPrice': stop_loss_price,
                                'positionValue': position_value,
                                'maxPositionValue': max_position_value,
                                'maxConcentration': max_concentration,
                                'targetMultiplier': target_multiplier,
                                'stopLossMultiplier': stop_loss_multiplier
                            }
                            app_logger.info(f"✅ Strategy info for {ticker}: {strategy_key} - Target: ${target_price}, Stop: ${stop_loss_price}")
                        else:
                            app_logger.warning(f"⚠️ No strategy config found for {strategy_key}")
                    except Exception as e:
                        app_logger.warning(f"⚠️ Error getting strategy info for {ticker}: {e}")
                    
                    # Format position data for frontend
                    formatted_position = {
                        'ticker': ticker,
                        'entryPrice': float(position.get('avg_entry_price', 0)),
                        'currentPrice': float(position.get('current_price', position.get('avg_entry_price', 0))),
                        'quantity': int(position.get('quantity', 0)),
                        'pnl': float(position.get('unrealized_pl', 0)),
                        'pnlPercent': float(position.get('unrealized_plpc', 0)) * 100 if position.get('unrealized_plpc') else 0,
                        'entryTime': datetime.now().isoformat(),  # Approximate entry time
                        'side': 'buy' if position.get('quantity', 0) > 0 else 'sell',
                        'marketValue': float(position.get('market_value', 0)),
                        'costBasis': float(position.get('avg_entry_price', 0)) * int(position.get('quantity', 0)),
                        'strategyInfo': strategy_info
                    }
                    positions.append(formatted_position)
                    app_logger.info(f"✅ Added position from Alpaca: {ticker} {position.get('quantity')} shares @ ${position.get('avg_entry_price')}")
            
            except Exception as e:
                app_logger.error(f"❌ Error getting positions from Alpaca: {e}")
        
        # Format response
        response = {
            'is_running': is_running,
            'tracked_symbols': tracked_symbols,
            'positions': positions,
            'subscribed_stocks': subscribed_stocks,  # Show tracked symbols as subscribed stocks
            'analysis_results': []  # Simplified for now
        }
        
        app_logger.info(f"📊 Bot status: running={is_running}, tracked_symbols={len(tracked_symbols)}, positions={len(positions)}")
        return jsonify(response)
        
    except Exception as e:
        app_logger.error(f"❌ Error getting bot status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    try:
        # Check if bot is already running
        if check_bot_status():
            return jsonify({'message': 'Bot is already running'}), 400
        
        # Start the bot using the start script
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'start_bot.sh')
        
        if os.path.exists(script_path):
            result = subprocess.run([script_path], capture_output=True, text=True)
            if result.returncode == 0:
                app_logger.info("Bot started successfully")
                return jsonify({'message': 'Bot started successfully'})
            else:
                app_logger.error(f"Failed to start bot: {result.stderr}")
                return jsonify({'error': 'Failed to start bot'}), 500
        else:
            app_logger.error(f"Start script not found: {script_path}")
            return jsonify({'error': 'Start script not found'}), 500
            
    except Exception as e:
        app_logger.error(f"Error starting bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    try:
        # Check if bot is running
        if not check_bot_status():
            return jsonify({'message': 'Bot is not running'}), 400
        
        # Stop the bot using the stop script
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'stop_bot.sh')
        
        if os.path.exists(script_path):
            result = subprocess.run([script_path], capture_output=True, text=True)
            if result.returncode == 0:
                app_logger.info("Bot stopped successfully")
                return jsonify({'message': 'Bot stopped successfully'})
            else:
                app_logger.error(f"Failed to stop bot: {result.stderr}")
                return jsonify({'error': 'Failed to stop bot'}), 500
        else:
            app_logger.error(f"Stop script not found: {script_path}")
            return jsonify({'error': 'Stop script not found'}), 500
            
    except Exception as e:
        app_logger.error(f"Error stopping bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/update-strategies', methods=['POST'])
def update_strategies():
    """Update trading strategy parameters using unified configuration"""
    try:
        data = request.get_json()
        if not data or 'strategies' not in data:
            return jsonify({
                'success': False,
                'error': 'Strategies data is required'
            }), 400
        
        strategies = data['strategies']
        app_logger.info(f"Updating strategy parameters: {strategies}")
        
        # Use unified strategy manager
        try:
            from config.strategy_manager import strategy_manager
            success = strategy_manager.update_all_strategies(strategies)
            
            if success:
                app_logger.info("Strategy settings updated using unified config")
                return jsonify({
                    'success': True,
                    'message': 'Strategy settings updated successfully',
                    'strategies': strategies
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update strategy settings'
                }), 500
                
        except ImportError:
            # Fallback to old method
            config_dir = os.path.join(os.path.dirname(__file__), 'config')
            os.makedirs(config_dir, exist_ok=True)
            
            strategy_config_file = os.path.join(config_dir, 'strategy_settings.json')
            with open(strategy_config_file, 'w') as f:
                json.dump({
                    'strategies': strategies,
                    'updated_at': datetime.now().isoformat()
                }, f, indent=2)
            
            app_logger.info(f"Strategy settings saved to {strategy_config_file}")
            
            return jsonify({
                'success': True,
                'message': 'Strategy settings updated successfully (fallback method)',
                'strategies': strategies
            })
            
    except Exception as e:
        app_logger.error(f"Error updating strategies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/strategies/get', methods=['GET'])
def get_strategy_settings():
    """Get current strategy settings"""
    try:
        from config.strategy_manager import strategy_manager
        strategies = strategy_manager.get_all_strategies()
        
        return jsonify({
            'success': True,
            'strategies': strategies,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app_logger.error(f"Error getting strategy settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/strategies/update', methods=['POST'])
def update_strategy():
    """Update a single strategy"""
    try:
        data = request.get_json()
        strategy_key = data.get('key')
        updates = data.get('updates', {})
        
        if not strategy_key:
            return jsonify({
                'success': False,
                'error': 'Strategy key is required'
            }), 400
        
        from config.strategy_manager import strategy_manager
        success = strategy_manager.update_strategy(strategy_key, updates)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Strategy {strategy_key} updated successfully',
                'data': {
                    'strategy_key': strategy_key,
                    'updates': updates
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to update strategy {strategy_key}'
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error updating strategy: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/sync-trades', methods=['POST'])
def sync_trades_from_alpaca():
    """Sync trades from Alpaca to local database"""
    try:
        app_logger.info("🔄 Starting trade sync from Alpaca...")
        
        # Import required modules
        from bot.trading_database import TradingDatabase
        from bot.alpaca_client import AlpacaClient
        
        # Initialize clients
        trading_db = TradingDatabase()
        alpaca_client = AlpacaClient()
        
        if not alpaca_client.trading_client:
            return jsonify({
                'success': False,
                'error': 'Alpaca client not initialized'
            }), 500
        
        # First, validate database consistency
        app_logger.info("🔧 Validating database consistency before sync...")
        validation_result = trading_db.validate_database_consistency()
        if validation_result['success']:
            app_logger.info(f"✅ Database validation completed: {validation_result['fixed_count']} issues fixed")
        else:
            app_logger.warning(f"⚠️ Database validation issues: {validation_result.get('error', 'Unknown')}")
        
        # Sync trades from Alpaca
        sync_result = trading_db.sync_trades_from_alpaca(alpaca_client)
        
        if sync_result['success']:
            cleaned_count = sync_result.get('cleaned_count', 0)
            app_logger.info(f"✅ Trade sync completed: {sync_result['synced_count']} new trades, {cleaned_count} positions cleaned")
            return jsonify({
                'success': True,
                'message': f"Synced {sync_result['synced_count']} new trades from Alpaca, cleaned {cleaned_count} positions",
                'data': sync_result
            })
        else:
            app_logger.error(f"❌ Trade sync failed: {sync_result.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': sync_result.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        app_logger.error(f"❌ Error syncing trades: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/validate-database', methods=['POST'])
def validate_database():
    """Validate and fix database consistency issues"""
    try:
        app_logger.info("🔧 Starting database validation...")
        
        # Import required modules
        from bot.trading_database import TradingDatabase
        
        # Initialize database
        trading_db = TradingDatabase()
        
        # Validate database consistency
        validation_result = trading_db.validate_database_consistency()
        
        if validation_result['success']:
            fixed_count = validation_result['fixed_count']
            missing_open = validation_result['missing_open_trades']
            missing_closed = validation_result['missing_closed_trades']
            
            app_logger.info(f"✅ Database validation completed: {fixed_count} issues fixed")
            return jsonify({
                'success': True,
                'message': f"Database validation completed: {fixed_count} issues fixed",
                'data': validation_result
            })
        else:
            app_logger.error(f"❌ Database validation failed: {validation_result.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': validation_result.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        app_logger.error(f"❌ Error validating database: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/unsubscribe-stocks', methods=['POST'])
def unsubscribe_stocks():
    """Unsubscribe from specific stocks in the trading bot"""
    try:
        data = request.get_json()
        if not data or 'stocks' not in data:
            return jsonify({
                'success': False,
                'error': 'Stocks list is required'
            }), 400
        
        stocks_to_unsubscribe = data['stocks']
        app_logger.info(f"🔄 Unsubscribing from stocks: {stocks_to_unsubscribe}")
        
        try:
            # Import bot modules
            sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))
            from bot.alpaca_client import AlpacaClient
            
            # Check for active positions before unsubscribing
            alpaca_client = AlpacaClient()
            active_positions = {}
            
            if alpaca_client.trading_client:
                try:
                    # Get current positions from Alpaca
                    alpaca_positions = alpaca_client.get_positions()
                    active_positions = {ticker: pos for ticker, pos in alpaca_positions.items() 
                                      if abs(pos.get('quantity', 0)) > 0}
                    app_logger.info(f"📊 Found {len(active_positions)} active positions")
                except Exception as e:
                    app_logger.error(f"❌ Error getting positions: {e}")
                    return jsonify({
                        'success': False,
                        'error': f'Could not check active positions: {str(e)}'
                    }), 500
            
            # Check if any stocks to unsubscribe have active positions
            stocks_with_positions = []
            for stock in stocks_to_unsubscribe:
                if stock in active_positions:
                    position = active_positions[stock]
                    quantity = abs(position.get('quantity', 0))
                    if quantity > 0:
                        stocks_with_positions.append({
                            'ticker': stock,
                            'quantity': quantity,
                            'side': 'long' if position.get('quantity', 0) > 0 else 'short',
                            'market_value': position.get('market_value', 0)
                        })
            
            if stocks_with_positions:
                app_logger.warning(f"⚠️ Cannot unsubscribe from stocks with active positions: {stocks_with_positions}")
                return jsonify({
                    'success': False,
                    'error': 'Cannot unsubscribe from stocks with active positions',
                    'data': {
                        'stocks_with_positions': stocks_with_positions,
                        'message': 'Please close all positions before unsubscribing'
                    }
                }), 400
            
            # SAFE TO UNSUBSCRIBE: No active positions found
            app_logger.info("✅ No active positions found - safe to unsubscribe")
            
            # Check if bot is running using the same method as bot status
            is_bot_running = check_bot_status()
            
            if is_bot_running:
                # Try to access the bot's tracked symbols through the gap-up detector
                # since that's what the bot status uses to get subscribed stocks
                try:
                    from gap_up_detector import get_gap_up_stocks
                    current_gap_ups = get_gap_up_stocks()
                    current_tickers = [stock['ticker'] for stock in current_gap_ups]
                    
                    app_logger.info(f"📊 Current gap-up stocks: {current_tickers}")
                    
                    # Filter out the stocks to unsubscribe
                    remaining_tickers = [ticker for ticker in current_tickers if ticker not in stocks_to_unsubscribe]
                    
                    app_logger.info(f"📊 Remaining stocks after unsubscribe: {remaining_tickers}")
                    
                    # For now, we'll just log the unsubscribe action
                    # In a real implementation, you would save this to a configuration file
                    # that the bot reads on startup
                    
                    return jsonify({
                        'success': True,
                        'message': f"Unsubscribed from {len(stocks_to_unsubscribe)} stocks",
                        'data': {
                            'unsubscribed_stocks': stocks_to_unsubscribe,
                            'remaining_symbols': remaining_tickers,
                            'total_remaining': len(remaining_tickers)
                        }
                    })
                    
                except Exception as e:
                    app_logger.error(f"❌ Error accessing gap-up stocks: {e}")
                    return jsonify({
                        'success': True,
                        'message': f"Unsubscribed from {len(stocks_to_unsubscribe)} stocks",
                        'data': {
                            'unsubscribed_stocks': stocks_to_unsubscribe,
                            'note': 'Changes applied to current session'
                        }
                    })
            else:
                app_logger.warning("⚠️ Bot not running")
                return jsonify({
                    'success': False,
                    'error': 'Bot not running'
                }), 400
                
        except ImportError as e:
            app_logger.error(f"❌ Could not import bot modules: {e}")
            return jsonify({
                'success': False,
                'error': 'Bot modules not available'
            }), 500
        except Exception as e:
            app_logger.error(f"❌ Error unsubscribing from stocks: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
    except Exception as e:
        app_logger.error(f"❌ Error in unsubscribe endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



# AI Agent Endpoints
@app.route('/api/ai-agent/status')
def get_ai_agent_status():
    """Get AI Agent status and configuration"""
    try:
        # Check if Google API key is available
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        status = {
            'available': google_api_key is not None and google_api_key != "YOUR_GOOGLE_API_KEY",
            'configured': google_api_key is not None and google_api_key != "YOUR_GOOGLE_API_KEY",
            'message': 'AI Agent is ready' if google_api_key and google_api_key != "YOUR_GOOGLE_API_KEY" else 'Google API key not configured'
        }
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-agent/chat', methods=['POST'])
def ai_agent_chat():
    """Send a message to the AI Agent and get response"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        user_message = data['message']
        
        # Check if Google API key is available
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key or google_api_key == "YOUR_GOOGLE_API_KEY":
            return jsonify({
                'success': False,
                'error': 'Google API key not configured. Please set GOOGLE_API_KEY environment variable.'
            }), 500
        
        # Import and run the AI agent
        try:
            import asyncio
            from google.adk.sessions import InMemorySessionService
            from google.adk import Runner
            from google.genai.types import Content
            from agents.agent import trading_advisor_agent
            
            # Create session service
            session_service = InMemorySessionService()
            
            # Create runner
            runner = Runner(
                app_name="trading_advisor",
                agent=trading_advisor_agent,
                session_service=session_service
            )
            
            # Create session
            session = asyncio.run(session_service.create_session(
                app_name="trading_advisor",
                user_id="user",
                session_id="trading_session"
            ))
            
            # Create content object for the message
            new_message = Content(parts=[{"text": user_message}])
            
            # Run the agent
            response_parts = []
            async def run_agent():
                async for event in runner.run_async(
                    user_id="user",
                    session_id="trading_session",
                    new_message=new_message
                ):
                    if hasattr(event, 'content'):
                        response_parts.append(event.content)
                    else:
                        response_parts.append(str(event))
            
            # Run the async function
            asyncio.run(run_agent())
            
            # Combine all response parts
            full_response = '\n'.join(response_parts)
            
            return jsonify({
                'success': True,
                'data': {
                    'response': full_response,
                    'timestamp': datetime.now().isoformat()
                }
            })
            
        except ImportError as e:
            return jsonify({
                'success': False,
                'error': f'AI Agent dependencies not available: {str(e)}'
            }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'AI Agent error: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-agent/start-session', methods=['POST'])
def ai_agent_start_session():
    """Start a new AI Agent session"""
    try:
        # Check if Google API key is available
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key or google_api_key == "YOUR_GOOGLE_API_KEY":
            return jsonify({
                'success': False,
                'error': 'Google API key not configured. Please set GOOGLE_API_KEY environment variable.'
            }), 500
        
        return jsonify({
            'success': True,
            'data': {
                'session_id': f"session_{int(time.time())}",
                'message': 'AI Agent session started successfully',
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache_endpoint():
    """Clear cache for a specific ticker or all tickers"""
    try:
        data = request.get_json() or {}
        ticker = data.get('ticker')  # If None, clears all cache
        
        from historical_data import clear_cache
        success = clear_cache(ticker)
        
        return jsonify({
            'success': success,
            'message': f"Cache cleared for {'all tickers' if ticker is None else ticker}",
            'ticker': ticker
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/status/<ticker>')
def get_cache_status_endpoint(ticker):
    """Get cache status for a specific ticker"""
    try:
        from historical_cache import historical_cache
        status = historical_cache.get_cache_status(ticker)
        
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/real-time-detector/stats')
def get_real_time_detector_stats():
    """Get real-time detector performance statistics with hybrid approach"""
    try:
        if not REAL_DATA_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Real-time detector not available'
            }), 400
        
        stats = real_time_detector.get_stats()
        
        # Add hybrid approach information
        hybrid_info = {
            'alert_threshold': stats.get('alert_threshold', 5.0),
            'trading_threshold': stats.get('trading_threshold', 25.0),
            'trading_opportunities': stats.get('trading_opportunities', 0),
            'total_gaps_found': stats.get('gaps_found', 0),
            'trading_opportunity_rate': round((stats.get('trading_opportunities', 0) / max(stats.get('gaps_found', 1), 1)) * 100, 1)
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'hybrid_info': hybrid_info,
            'status': 'active' if real_time_detector.running else 'inactive'
        })
        
    except Exception as e:
        app_logger.error(f"❌ Error getting real-time detector stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/stats')
def get_cache_stats():
    """Get cache performance statistics"""
    try:
        from gap_up_cache import get_cache_stats
        stats = get_cache_stats()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app_logger.error(f"❌ Error getting cache stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear all cache entries"""
    try:
        from gap_up_cache import invalidate_gap_up_cache
        invalidate_gap_up_cache()
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app_logger.error(f"❌ Error clearing cache: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trades/convert-positions', methods=['POST'])
def convert_positions_to_trades():
    """Convert closed positions to trade records"""
    try:
        from bot.trading_database import trading_db
        success = trading_db.convert_closed_positions_to_trades()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Closed positions converted to trades successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to convert positions to trades'
            }), 500
        
    except Exception as e:
        app_logger.error(f"❌ Error converting positions to trades: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app_logger.info("🚀 Starting Trading Advisor Web API...")
    app_logger.info("📊 API available at: http://localhost:5000")
    app_logger.info("🔧 Health check: http://localhost:5000/api/health")
    app_logger.info("🌐 Frontend should be served from: http://localhost:3000")
    
    # Check if real data is available
    if REAL_DATA_AVAILABLE:
        app_logger.info("✅ Real data enabled - Gap-up detection available")
        
        # Check Polygon API key
        if os.getenv('POLYGON_API_KEY'):
            app_logger.info("✅ Polygon API key found in environment")
        else:
            app_logger.warning("⚠️ Using default Polygon API key from trading-advisor project")
        
        # Start real-time gap-up monitoring with hybrid approach
        try:
            real_time_detector.start_monitoring(
                callback=handle_real_time_gap_up,
                trading_callback=handle_trading_opportunity
            )
            app_logger.info("✅ Real-time gap-up monitoring started with hybrid approach (5% alerts, 25% trading)")
        except Exception as e:
            app_logger.error(f"⚠️ Could not start real-time monitoring: {e}")
        
        # Validate and fix database consistency
        try:
            from bot.trading_database import trading_db
            validation_result = trading_db.validate_database_consistency()
            if validation_result['success']:
                app_logger.info(f"✅ Database validation completed: {validation_result['fixed_count']} issues fixed")
            else:
                app_logger.warning(f"⚠️ Database validation issues: {validation_result.get('error', 'Unknown')}")
        except Exception as e:
            app_logger.error(f"⚠️ Could not validate database: {e}")
        
        # Convert any existing closed positions to trades
        try:
            from bot.trading_database import trading_db
            trading_db.convert_closed_positions_to_trades()
            app_logger.info("✅ Converted any existing closed positions to trades")
        except Exception as e:
            app_logger.error(f"⚠️ Could not convert closed positions: {e}")
    else:
        app_logger.warning("⚠️ Real data not available - Using mock data only")
        app_logger.info("💡 Install dependencies: pip install -r requirements.txt")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True) 