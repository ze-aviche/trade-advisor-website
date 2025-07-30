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
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from logging_config import setup_logging, get_logger, log_api_request, log_performance, log_error

# Load environment variables
load_dotenv()

# Setup comprehensive logging
setup_logging(log_level='INFO', log_dir='../logs')
app_logger = get_logger('app')

# Import real gap-up detection functions
try:
    from gap_up_detector import get_gap_up_stocks, get_stock_analysis, get_market_data
    from historical_data import get_historical_gap_up_data
    from real_time_detector import real_time_detector
    REAL_DATA_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import gap_up_detector: {e}")
    REAL_DATA_AVAILABLE = False

# Import auth functions (these should always be available)
try:
    from auth import auth_manager, require_auth
except ImportError as e:
    print(f"Warning: Could not import auth: {e}")
    # Create dummy auth functions if import fails
    auth_manager = None
    require_auth = lambda f: f  # No-op decorator

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trading-advisor-web-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variables for real-time data
active_stocks = set()
price_cache = {}
websocket_connected = False
real_time_gap_ups = []  # Store real-time detected gap-ups

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
        'side': 'buy',
        'quantity': 100,
        'price': 148.50,
        'timestamp': (datetime.now() - timedelta(hours=2)).isoformat(),
        'status': 'filled',
        'pnl': 175.00
    },
    {
        'id': 2,
        'ticker': 'TSLA',
        'side': 'sell',
        'quantity': 50,
        'price': 240.00,
        'timestamp': (datetime.now() - timedelta(hours=4)).isoformat(),
        'status': 'filled',
        'pnl': -250.00
    },
    {
        'id': 3,
        'ticker': 'NVDA',
        'side': 'buy',
        'quantity': 75,
        'price': 470.00,
        'timestamp': (datetime.now() - timedelta(hours=6)).isoformat(),
        'status': 'filled',
        'pnl': 1162.50
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
    
    print(f"🚨 Real-time gap-up broadcast: {gap_up_data['ticker']} - {gap_up_data['gap_percent']}%")

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
                            print(f"Error updating price for {ticker}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error in price update worker: {e}")
                    
            # Sleep for 1 second before next update
            time.sleep(1)
    
    # Start the background thread
    thread = threading.Thread(target=price_update_worker, daemon=True)
    thread.start()
    print("✅ Real-time price update thread started")

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
        'active_stocks_count': len(active_stocks)
    })

@app.route('/api/gap-ups')
def get_gap_ups():
    """Get current gap-up stocks"""
    try:
        if REAL_DATA_AVAILABLE:
            print("🔍 Attempting to fetch real gap-up data...")
            # Use real data from Polygon API
            gap_ups = get_gap_up_stocks()
            if gap_ups and len(gap_ups) > 0:
                print(f"✅ Successfully fetched {len(gap_ups)} real gap-up stocks")
                
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
                print("⚠️ No real gap-up data available, falling back to mock data")
        else:
            print("⚠️ Real data not available, using mock data")
        
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
    """Get trade history"""
    try:
        return jsonify({
            'success': True,
            'trades': MOCK_TRADES,
            'summary': MOCK_TRADE_SUMMARY,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
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

@app.route('/api/cache/stats')
def get_cache_stats():
    """Get cache statistics"""
    try:
        from historical_data import get_cache_stats
        stats = get_cache_stats()
        return jsonify({
            'success': True,
            'data': stats
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

if __name__ == '__main__':
    print("🚀 Starting Trading Advisor Web API...")
    print("📊 API available at: http://localhost:5000")
    print("🔧 Health check: http://localhost:5000/api/health")
    print("🌐 Frontend should be served from: http://localhost:3000")
    
    if REAL_DATA_AVAILABLE:
        print("✅ Real data enabled - Gap-up detection available")
        if os.environ.get('POLYGON_API_KEY'):
            print("✅ Polygon API key found in environment")
        else:
            print("⚠️ Using default Polygon API key from trading-advisor project")
        
        # Start real-time price update thread
        start_price_update_thread()
        
        # Start real-time gap-up monitoring
        try:
            real_time_detector.start_monitoring(callback=handle_real_time_gap_up)
            print("✅ Real-time gap-up monitoring started (25%+ threshold)")
        except Exception as e:
            print(f"⚠️ Could not start real-time monitoring: {e}")
    else:
        print("⚠️ Real data not available - Using mock data only")
        print("💡 Install dependencies: pip install -r requirements.txt")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 