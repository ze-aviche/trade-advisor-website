"""
Trading Bot Configuration
"""

import os
from typing import Dict, Any

class TradingBotConfig:
    """Configuration for the trading bot"""
    
    # Trading Parameters
    DEFAULT_VOLUME = 1000  # Number of shares per trade
    STOP_LOSS_PERCENTAGE = 15.0  # Stop loss percentage
    MAX_POSITIONS = 10  # Maximum concurrent positions
    
    # Strategy Parameters
    BUY_OVER_HOD = {
        'name': 'buy_over_hod',
        'description': 'Buy when price breaks above day high',
        'entry_condition': 'price > day_high',
        'exit_condition': 'price < entry_price * 0.85 or price > target_price',
        'target_multiplier': 1.5,  # 50% profit target
        'stop_loss_multiplier': 0.85,  # 15% stop loss
    }
    
    # Data Parameters
    PREMARKET_START = "04:00"
    MARKET_OPEN = "09:30"
    MARKET_CLOSE = "16:00"
    AFTERHOURS_END = "20:00"
    
    # Historical Data Parameters
    HISTORICAL_DAYS = 730  # Days of historical data to analyze
    MIN_GAP_PERCENTAGE = 25.0  # Minimum gap percentage to consider
    
    # WebSocket Parameters
    WEBSOCKET_RECONNECT_DELAY = 5  # seconds
    WEBSOCKET_MAX_RECONNECTS = 10
    
    # Risk Management
    MAX_DAILY_LOSS = 1000.0  # Maximum daily loss in dollars
    MAX_PORTFOLIO_RISK = 0.02  # Maximum 2% portfolio risk per trade
    
    # Broker Configuration
    # Alpaca Settings
    BROKER_API_KEY = os.getenv('ALPACA_API_KEY', '')
    BROKER_SECRET = os.getenv('ALPACA_SECRET_KEY', '')
    BROKER_ENDPOINT = os.getenv('ALPACA_ENDPOINT', 'https://paper-api.alpaca.markets')
    ALPACA_PAPER = True  # Use paper trading by default
    
    # DAS Settings (for future use)
    DAS_API_KEY = os.getenv('DAS_API_KEY', '')
    DAS_SECRET_KEY = os.getenv('DAS_SECRET_KEY', '')
    DAS_BASE_URL = os.getenv('DAS_BASE_URL', 'https://api.dastrading.com')
    DAS_FIX_HOST = os.getenv('DAS_FIX_HOST', '')
    DAS_FIX_PORT = int(os.getenv('DAS_FIX_PORT', '0'))
    
    # Broker Selection
    BROKER_TYPE = os.getenv('BROKER_TYPE', 'alpaca')  # 'alpaca' or 'das'
    
    # Polygon API Settings
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    
    # Database Settings
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'trading_advisor.db')
    
    # Logging Settings
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'trading_bot.log'
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """Get configuration for a specific strategy"""
        strategies = {
            'break_out': {
                'target_multiplier': 1.5,  # 50% profit target
                'stop_loss_multiplier': 0.85,  # 15% stop loss
                'min_gap_percentage': 25,  # Minimum gap percentage
                'volume_threshold': 500000,  # Minimum volume
                'confidence_threshold': 60  # Minimum confidence
            }
        }
        return strategies.get(strategy_name, {})
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate that all required configuration is present"""
        required_env_vars = ['POLYGON_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"❌ Missing required environment variables: {missing_vars}")
            return False
        
        # Check broker configuration
        broker_type = cls.BROKER_TYPE.lower()
        
        if broker_type == 'alpaca':
            if cls.BROKER_API_KEY and cls.BROKER_SECRET:
                print("✅ Alpaca credentials found - will use Alpaca trading")
            else:
                print("⚠️ No Alpaca credentials found - will use mock mode")
        
        elif broker_type == 'das':
            if cls.DAS_API_KEY and cls.DAS_SECRET_KEY:
                print("✅ DAS credentials found - will use DAS trading")
            else:
                print("⚠️ No DAS credentials found - will use mock mode")
        
        else:
            print(f"⚠️ Unknown broker type: {broker_type} - will use mock mode")
        
        return True

# Global config instance
config = TradingBotConfig() 