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
    from auth import auth_manager, require_auth
except ImportError as e:
    app_logger.warning(f"Warning: Could not import auth: {e}")
    # Create dummy auth functions if import fails
    auth_manager = None
    require_auth = lambda f: f  # No-op decorator

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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gap-up-detection-web-2024'
CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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

def get_mock_stock_data(symbol):
    """Get mock stock data for demonstration purposes"""
    # This would be replaced with real market data API calls
    import random
    
    # Generate realistic mock data
    base_price = random.uniform(50, 200)
    current_price = base_price + random.uniform(-5, 5)
    volume = random.uniform(1, 10)  # in millions
    dollar_volume = volume * current_price
    
    return {
        'symbol': symbol,
        'current_price': round(current_price, 2),
        'volume': round(volume, 2),  # in millions
        'dollar_volume': round(dollar_volume, 2),  # in millions
        'timestamp': datetime.now().isoformat()
    }

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

def enter_position(symbol, entry_price, entry_params):
    """Enter a position for a symbol at the given price"""
    global active_positions, entry_bot_stats
    
    try:
        # Generate a unique position ID
        position_id = f"ENTRY_{symbol}_{int(time.time())}"
        
        # Mock position entry (in real implementation, this would be a market order)
        position = {
            'position_id': position_id,
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': datetime.now().isoformat(),
            'quantity': 100,  # Mock quantity - in real implementation this would be calculated based on risk
            'entry_params': entry_params,
            'status': 'active'
        }
        
        # Store the position
        active_positions[position_id] = position
        
        # Update bot statistics
        entry_bot_stats['positions_entered'] += 1
        entry_bot_stats['active_positions_count'] = len(active_positions)
        
        add_entry_bot_log('info', f"✅ Position entered for {symbol} at ${entry_price} - Position ID: {position_id}")
        
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
                
                # Check each symbol's conditions
                for symbol, params in tracking_symbols.items():
                    try:
                        # Skip if we already have an active position for this symbol
                        if any(pos['symbol'] == symbol for pos in active_positions.values()):
                            continue
                        
                        # Get current market data
                        current_data = get_mock_stock_data(symbol)
                        
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

# Simple auth endpoints for frontend compatibility
@app.route('/api/auth/profile', methods=['GET', 'OPTIONS'])
def get_auth_profile():
    """Get user profile - dummy endpoint for frontend compatibility"""
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    try:
        # Return dummy user data for now
        user_data = {
            'id': 1,
            'username': 'demo_user',
            'email': 'demo@example.com',
            'role': 'user',
            'authenticated': True
        }
        
        return jsonify({
            'success': True,
            'data': user_data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app_logger.error(f"Error getting auth profile: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
    """Get or set gap-up configuration"""
    try:
        if request.method == 'GET':
            # Get current configuration
            import config as config_module
            min_percentage = getattr(config_module, 'GAP_UP_MIN_PERCENTAGE', 15.0)
            
            return jsonify({
                'success': True,
                'data': {
                    'min_percentage': min_percentage
                }
            })
        else:
            # POST - Update configuration
            data = request.get_json()
            min_percentage = data.get('min_percentage', 25.0)
            
            # Validate input
            if not isinstance(min_percentage, (int, float)) or min_percentage < 0:
                return jsonify({
                    'success': False,
                    'error': 'Invalid min_percentage value'
                }), 400
            
            # Update configuration file
            config_path = os.path.join(os.path.dirname(__file__), 'config.py')
            
            # Read current config
            with open(config_path, 'r') as f:
                config_content = f.read()
            
            # Update the GAP_UP_MIN_PERCENTAGE line
            import re
            pattern = r'GAP_UP_MIN_PERCENTAGE\s*=\s*[\d.]+'
            replacement = f'GAP_UP_MIN_PERCENTAGE = {min_percentage}'
            
            if re.search(pattern, config_content):
                new_config_content = re.sub(pattern, replacement, config_content)
            else:
                # Add the line if it doesn't exist
                new_config_content = config_content + f'\nGAP_UP_MIN_PERCENTAGE = {min_percentage}'
            
            # Write updated config
            with open(config_path, 'w') as f:
                f.write(new_config_content)
            
            # Force reload the config module to pick up the new value
            try:
                import importlib
                import config as config_module
                importlib.reload(config_module)
                app_logger.info(f"🔄 Config module reloaded, new threshold: {getattr(config_module, 'GAP_UP_MIN_PERCENTAGE', 'unknown')}%")
            except Exception as reload_error:
                app_logger.warning(f"⚠️ Could not reload config module: {reload_error}")
            
            # Invalidate gap-up cache to ensure fresh data with new threshold
            try:
                from gap_up_cache import invalidate_gap_up_cache
                invalidate_gap_up_cache()
                app_logger.info("🗑️ Gap-up cache invalidated after config update")
            except Exception as cache_error:
                app_logger.warning(f"⚠️ Could not invalidate cache: {cache_error}")
            
            app_logger.info(f"✅ Gap-up configuration updated: min_percentage = {min_percentage}%")
            
            return jsonify({
                'success': True,
                'message': f'Configuration updated: min_percentage = {min_percentage}% (cache cleared)'
            })
            
    except Exception as e:
        app_logger.error(f"Error in gap-ups config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
def start_ai_session():
    """Start AI agent session"""
    try:
        # Import AI agent
        try:
            from ai_agent import GoogleAIAgent
            ai_agent = GoogleAIAgent()
            session_id = 'session_' + str(int(time.time()))
            
            return jsonify({
                'success': True,
                'data': {
                    'session_id': session_id,
                    'status': 'active',
                    'message': 'AI Agent session started successfully'
                },
                'timestamp': datetime.now().isoformat()
            })
        except ImportError as e:
            app_logger.error(f"AI Agent module not available: {e}")
            return jsonify({
                'success': False,
                'error': 'AI Agent module not available. Please check dependencies.'
            }), 500
        except ValueError as e:
            app_logger.error(f"AI Agent configuration error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error starting AI session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-agent/chat', methods=['POST'])
def ai_chat():
    """Handle AI chat messages"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        session_id = data.get('session_id', '')
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        # Import and use AI agent
        try:
            from ai_agent import GoogleAIAgent
            ai_agent = GoogleAIAgent()
            
            # Process the message
            result = ai_agent.process_message(message, session_id)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'data': {
                        'response': result['response'],
                        'session_id': session_id,
                        'tools_used': result.get('tools_used', []),
                        'symbols_analyzed': result.get('symbols_analyzed', [])
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'session_id': session_id
                }), 500
                
        except ImportError as e:
            app_logger.error(f"AI Agent module not available: {e}")
            return jsonify({
                'success': False,
                'error': 'AI Agent module not available. Please check dependencies.'
            }), 500
        except ValueError as e:
            app_logger.error(f"AI Agent configuration error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error in AI chat: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-agent/history', methods=['GET'])
def get_ai_history():
    """Get AI conversation history"""
    try:
        session_id = request.args.get('session_id', '')
        
        try:
            from ai_agent import GoogleAIAgent
            ai_agent = GoogleAIAgent()
            history = ai_agent.get_conversation_history(session_id)
            
            return jsonify({
                'success': True,
                'data': {
                    'history': history,
                    'session_id': session_id
                },
                'timestamp': datetime.now().isoformat()
            })
        except ImportError as e:
            app_logger.error(f"AI Agent module not available: {e}")
            return jsonify({
                'success': False,
                'error': 'AI Agent module not available. Please check dependencies.'
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error getting AI history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-agent/clear-history', methods=['POST'])
def clear_ai_history():
    """Clear AI conversation history"""
    try:
        data = request.get_json()
        session_id = data.get('session_id', '')
        
        try:
            from ai_agent import GoogleAIAgent
            ai_agent = GoogleAIAgent()
            success = ai_agent.clear_conversation_history(session_id)
            
            return jsonify({
                'success': success,
                'data': {
                    'session_id': session_id,
                    'message': 'Conversation history cleared successfully' if success else 'Failed to clear history'
                },
                'timestamp': datetime.now().isoformat()
            })
        except ImportError as e:
            app_logger.error(f"AI Agent module not available: {e}")
            return jsonify({
                'success': False,
                'error': 'AI Agent module not available. Please check dependencies.'
            }), 500
            
    except Exception as e:
        app_logger.error(f"Error clearing AI history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        # Since we have automatic position sync running in app.py, always return running
        return jsonify({
            'success': True,
            'data': {
                'is_running': True,
                'is_market_hours': True,  # Assume market hours for now
                'current_time_et': datetime.now().strftime('%H:%M:%S'),
                'next_scheduled_run': None,  # Continuous sync
                'thread_alive': True,
                'sync_type': 'automatic',
                'update_interval': '10 seconds'
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
        
        if not all([symbol, total_volume, dollar_volume, entry_time]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: symbol, total_volume, dollar_volume, entry_time'
            }), 400
        
        # Store the tracking parameters
        tracking_symbols[symbol] = {
            'symbol': symbol,
            'total_volume': float(total_volume),
            'dollar_volume': float(dollar_volume),
            'entry_time': entry_time,
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
            current_data = get_mock_stock_data(symbol)
            
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
    Background task to update gap-up data using delayed data
    Optimized for early morning gap-up detection to reduce API costs
    Uses 15-minute delayed data instead of real-time data
    """
    global real_time_gap_ups
    
    # Gap-up configuration
    GAP_UP_UPDATE_INTERVAL = 300  # 5 minutes
    DELAYED_DATA_DESCRIPTION = '15-minute delayed data for cost optimization'
    
    while True:
        try:
            if REAL_DATA_AVAILABLE:
                # Get latest gap-up data using delayed data
                latest_gap_ups = get_gap_up_stocks_for_frontend()
                real_time_gap_ups = latest_gap_ups
                
                # Broadcast to connected clients
                broadcast_gap_ups()
                
            # Use configurable update interval to reduce API calls
            # This is sufficient for early morning gap-up detection
            app_logger.info(f"⏰ Next gap-up update in {GAP_UP_UPDATE_INTERVAL} seconds ({DELAYED_DATA_DESCRIPTION})")
            time.sleep(GAP_UP_UPDATE_INTERVAL)
        except Exception as e:
            app_logger.error(f"Error updating gap-ups: {e}")
            time.sleep(GAP_UP_UPDATE_INTERVAL)  # Use same interval on error

# Start background task
if __name__ == '__main__':
    # Start background task in a separate thread
    update_thread = threading.Thread(target=update_real_time_gap_ups, daemon=True)
    update_thread.start()
    
    # Start scheduled DAS sync service
    if SCHEDULED_SYNC_AVAILABLE:
        try:
            start_scheduled_sync()
            app_logger.info("✅ Scheduled DAS sync service started")
        except Exception as e:
            app_logger.error(f"❌ Failed to start scheduled DAS sync: {e}")
    else:
        app_logger.warning("⚠️ Scheduled DAS sync not available")
    
    # Start automatic position sync scheduler
    start_position_sync_scheduler()

    app_logger.info("Starting Gap-Up Detection Web API...")
    app_logger.info("Server will be available at http://localhost:5000")
    
    # Run the Flask app
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)