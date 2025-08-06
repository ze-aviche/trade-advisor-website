"""
Broker Factory
Handles multiple broker integrations (Alpaca, DAS, etc.)
"""

import sys
import os
from typing import Optional, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config
from bot.alpaca_client import alpaca_client

logger = get_logger(__name__)

class BrokerFactory:
    """Factory for creating broker clients"""
    
    @staticmethod
    def get_broker_client():
        """Get the appropriate broker client based on configuration"""
        try:
            broker_type = bot_config.BROKER_TYPE.lower()
            
            if broker_type == 'alpaca':
                logger.info("🔧 Using Alpaca broker client")
                return alpaca_client
            
            elif broker_type == 'das':
                from das_client import das_client
                logger.info("🔧 Using DAS broker client")
                return das_client
            
            else:
                logger.warning(f"⚠️ Unknown broker type: {broker_type}, using mock mode")
                return None
                
        except ImportError as e:
            logger.error(f"❌ Error importing broker client: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting broker client: {e}")
            return None
    
    @staticmethod
    def validate_broker_config():
        """Validate broker configuration"""
        try:
            broker_type = bot_config.BROKER_TYPE.lower()
            
            if broker_type == 'alpaca':
                # Check Alpaca credentials
                if bot_config.BROKER_API_KEY and bot_config.BROKER_SECRET:
                    logger.info("✅ Alpaca configuration valid")
                    return True
                else:
                    logger.warning("⚠️ Alpaca credentials not configured")
                    return False
            
            elif broker_type == 'das':
                # Check DAS credentials
                if bot_config.DAS_API_KEY and bot_config.DAS_SECRET_KEY:
                    logger.info("✅ DAS configuration valid")
                    return True
                else:
                    logger.warning("⚠️ DAS credentials not configured")
                    return False
            
            else:
                logger.warning(f"⚠️ Unknown broker type: {broker_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error validating broker config: {e}")
            return False
    
    @staticmethod
    def get_broker_info():
        """Get information about the configured broker"""
        try:
            broker_type = bot_config.BROKER_TYPE.lower()
            
            if broker_type == 'alpaca':
                return {
                    'type': 'alpaca',
                    'name': 'Alpaca Markets',
                    'paper_trading': bot_config.ALPACA_PAPER,
                    'endpoint': bot_config.BROKER_ENDPOINT,
                    'configured': bool(bot_config.BROKER_API_KEY and bot_config.BROKER_SECRET)
                }
            
            elif broker_type == 'das':
                return {
                    'type': 'das',
                    'name': 'DAS Trading Platform',
                    'paper_trading': False,  # DAS typically doesn't have paper trading
                    'endpoint': bot_config.DAS_BASE_URL,
                    'configured': bool(bot_config.DAS_API_KEY and bot_config.DAS_SECRET_KEY)
                }
            
            else:
                return {
                    'type': 'unknown',
                    'name': 'Unknown Broker',
                    'paper_trading': False,
                    'endpoint': 'N/A',
                    'configured': False
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting broker info: {e}")
            return {
                'type': 'error',
                'name': 'Error',
                'paper_trading': False,
                'endpoint': 'N/A',
                'configured': False
            }

# Global broker factory instance
broker_factory = BrokerFactory() 