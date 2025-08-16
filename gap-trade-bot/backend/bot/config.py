"""
Trading Bot Configuration
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv
from logging_config import get_logger

logger = get_logger(__name__)

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

class TradingBotConfig:
    """Configuration for the trading bot"""
    
    # Trading Parameters
    DEFAULT_VOLUME = 1000  # Number of shares per trade
    STOP_LOSS_PERCENTAGE = 15.0  # Stop loss percentage
    MAX_POSITIONS = 10  # Maximum concurrent positions
    
    # Data Parameters
    PREMARKET_START = "04:00"
    MARKET_OPEN = "09:30"
    MARKET_CLOSE = "16:00"
    AFTERHOURS_END = "20:00"
    
    # Historical Data Parameters
    HISTORICAL_DAYS = 730  # Days of historical data to analyze
    
    # WebSocket Parameters
    WEBSOCKET_RECONNECT_DELAY = 5  # seconds
    WEBSOCKET_MAX_RECONNECTS = 10
    
    # Risk Management
    MAX_DAILY_LOSS = 1000.0  # Maximum daily loss in dollars
    MAX_PORTFOLIO_RISK = 0.02  # Maximum 2% portfolio risk per trade
    
    # Broker Configuration
    # DAS Settings
    # DAS CMD API (legacy)
    DAS_API_KEY = os.getenv('DAS_API_KEY', '')
    DAS_SECRET_KEY = os.getenv('DAS_SECRET_KEY', '')
    DAS_BASE_URL = os.getenv('DAS_BASE_URL', 'https://api.dastrading.com')
    
    # DAS FIX API (preferred)
    DAS_FIX_HOST = os.getenv('DAS_FIX_HOST', 'localhost')
    DAS_FIX_PORT_STR = os.getenv('DAS_FIX_PORT', '5001')
    DAS_FIX_PORT = int(DAS_FIX_PORT_STR) if DAS_FIX_PORT_STR else 5001
    DAS_USERNAME = os.getenv('DAS_USERNAME', '')
    DAS_PASSWORD = os.getenv('DAS_PASSWORD', '')
    DAS_SENDER_COMP_ID = os.getenv('DAS_SENDER_COMP_ID', 'TRADINGBOT')
    DAS_TARGET_COMP_ID = os.getenv('DAS_TARGET_COMP_ID', 'DAS')
    
    # Broker Selection
    BROKER_TYPE = os.getenv('BROKER_TYPE', 'das')  # 'das' only
    
    # Polygon API Settings
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    
    # Database Settings
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'trading_advisor.db')
    
    # Logging Settings
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'trading_bot.log'
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """Get configuration for a specific strategy - deprecated, use strategy-specific config"""
        logger.warning(f"⚠️ get_strategy_config is deprecated. Configure {strategy_name} strategy directly.")
        return {}
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate that all required configuration is present"""
        required_env_vars = ['POLYGON_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {missing_vars}")
            return False
        
        # Check broker configuration
        broker_type = cls.BROKER_TYPE.lower()
        
        if broker_type == 'das':
            # Check DAS FIX configuration first (preferred)
            if (cls.DAS_FIX_HOST and cls.DAS_FIX_PORT and 
                cls.DAS_USERNAME and cls.DAS_PASSWORD and
                cls.DAS_USERNAME.strip() and cls.DAS_PASSWORD.strip()):
                logger.info("✅ DAS FIX credentials found - will use DAS FIX trading")
                logger.info(f"   FIX Host: {cls.DAS_FIX_HOST}:{cls.DAS_FIX_PORT}")
                logger.info(f"   Sender: {cls.DAS_SENDER_COMP_ID}")
                logger.info(f"   Target: {cls.DAS_TARGET_COMP_ID}")
            # Check DAS CMD configuration (fallback)
            elif cls.DAS_API_KEY and cls.DAS_SECRET_KEY and cls.DAS_API_KEY.strip() and cls.DAS_SECRET_KEY.strip():
                logger.info("✅ DAS CMD credentials found - will use DAS CMD trading (fallback)")
            else:
                logger.warning("⚠️ No DAS credentials found - will use mock mode")
                logger.info("   To use DAS FIX API, set: DAS_FIX_HOST, DAS_FIX_PORT, DAS_USERNAME, DAS_PASSWORD")
                logger.info("   To use DAS CMD API, set: DAS_API_KEY, DAS_SECRET_KEY")
        
        else:
            logger.warning(f"⚠️ Unknown broker type: {broker_type} - will use mock mode")
        
        return True
    
    @classmethod
    def get_das_config_info(cls) -> Dict[str, Any]:
        """Get DAS configuration information"""
        return {
            'fix_configured': bool(cls.DAS_FIX_HOST and cls.DAS_FIX_PORT and 
                                  cls.DAS_USERNAME and cls.DAS_PASSWORD and
                                  cls.DAS_USERNAME.strip() and cls.DAS_PASSWORD.strip()),
            'cmd_configured': bool(cls.DAS_API_KEY and cls.DAS_SECRET_KEY and
                                 cls.DAS_API_KEY.strip() and cls.DAS_SECRET_KEY.strip()),
            'fix_host': cls.DAS_FIX_HOST,
            'fix_port': cls.DAS_FIX_PORT,
            'sender_comp_id': cls.DAS_SENDER_COMP_ID,
            'target_comp_id': cls.DAS_TARGET_COMP_ID,
            'username_configured': bool(cls.DAS_USERNAME and cls.DAS_USERNAME.strip()),
            'password_configured': bool(cls.DAS_PASSWORD and cls.DAS_PASSWORD.strip())
        }

# Global config instance
config = TradingBotConfig() 