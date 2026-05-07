"""
Configuration settings for the trading advisor web API
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'trading-advisor-web-2024'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # API Keys (for future use)
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY')
    ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY')
    POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY')
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///trades.db')
    
    # CORS
    CORS_ORIGINS = [
        "http://localhost:3000",  # Vue.js dev server
        "http://localhost:8080",  # Alternative Vue.js port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080"
    ]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '60'))
    RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', '1000'))
    
    # Cache
    CACHE_TTL = int(os.environ.get('CACHE_TTL', '3600'))  # 1 hour
    
    # WebSocket
    SOCKETIO_ASYNC_MODE = 'threading'
    
    @staticmethod
    def init_app(app):
        """Initialize app with configuration"""
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to stderr in production
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 

# Clear alias for main backend config
web_config = config 

# Gap-Up Detection Configuration (Cost Optimized)
# Use delayed data instead of real-time data to reduce API costs

# Note: Stock list removed - system will use alternative methods for gap-up detection

# Gap-up detection settings
GAP_UP_MIN_PRICE = 0.75     # Minimum stock price to consider (penny stock filter)
GAP_UP_UPDATE_INTERVAL = 300  # Background refresh interval in seconds

# Data source configuration
USE_DELAYED_DATA = True       # Use 15-minute delayed data instead of real-time
DELAYED_DATA_DESCRIPTION = "15-minute delayed data for cost optimization"

# Make these available as module-level attributes
__all__ = [
    'GAP_UP_MIN_PRICE',
    'GAP_UP_UPDATE_INTERVAL',
    'USE_DELAYED_DATA',
    'DELAYED_DATA_DESCRIPTION'
] 