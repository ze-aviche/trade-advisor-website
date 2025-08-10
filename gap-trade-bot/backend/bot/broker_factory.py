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
                # Try FIX client first, fallback to CMD client
                try:
                    from das_fix_client import DASFIXClient
                    logger.info("🔧 Using DAS FIX broker client")
                    
                    # Create FIX client with configuration
                    das_fix_client = DASFIXClient(
                        sender_comp_id=bot_config.DAS_SENDER_COMP_ID or "TRADINGBOT",
                        target_comp_id=bot_config.DAS_TARGET_COMP_ID or "DAS",
                        fix_host=bot_config.DAS_FIX_HOST or "localhost",
                        fix_port=bot_config.DAS_FIX_PORT or 5001,
                        username=bot_config.DAS_USERNAME or "",
                        password=bot_config.DAS_PASSWORD or ""
                    )
                    
                    return das_fix_client
                    
                except ImportError:
                    # Fallback to CMD client
                    try:
                        from das_client import das_client
                        logger.info("🔧 Using DAS CMD broker client (fallback)")
                        return das_client
                    except ImportError:
                        logger.error("❌ Neither DAS FIX nor CMD client available")
                        return None
            
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
                # Check DAS FIX configuration
                if (bot_config.DAS_FIX_HOST and bot_config.DAS_FIX_PORT and 
                    bot_config.DAS_USERNAME and bot_config.DAS_PASSWORD):
                    logger.info("✅ DAS FIX configuration valid")
                    return True
                # Check DAS CMD configuration (fallback)
                elif bot_config.DAS_API_KEY and bot_config.DAS_SECRET_KEY:
                    logger.info("✅ DAS CMD configuration valid (fallback)")
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
                    'protocol': 'REST API',
                    'paper_trading': bot_config.ALPACA_PAPER,
                    'endpoint': bot_config.BROKER_ENDPOINT,
                    'configured': bool(bot_config.BROKER_API_KEY and bot_config.BROKER_SECRET)
                }
            
            elif broker_type == 'das':
                # Check if FIX is configured
                if (bot_config.DAS_FIX_HOST and bot_config.DAS_FIX_PORT and 
                    bot_config.DAS_USERNAME and bot_config.DAS_PASSWORD):
                    return {
                        'type': 'das',
                        'name': 'DAS Trading Platform',
                        'protocol': 'FIX API',
                        'paper_trading': False,  # DAS typically doesn't have paper trading
                        'endpoint': f"{bot_config.DAS_FIX_HOST}:{bot_config.DAS_FIX_PORT}",
                        'configured': True
                    }
                # Fallback to CMD
                elif bot_config.DAS_API_KEY and bot_config.DAS_SECRET_KEY:
                    return {
                        'type': 'das',
                        'name': 'DAS Trading Platform',
                        'protocol': 'CMD API',
                        'paper_trading': False,
                        'endpoint': bot_config.DAS_BASE_URL,
                        'configured': True
                    }
                else:
                    return {
                        'type': 'das',
                        'name': 'DAS Trading Platform',
                        'protocol': 'Not Configured',
                        'paper_trading': False,
                        'endpoint': 'N/A',
                        'configured': False
                    }
            
            else:
                return {
                    'type': 'unknown',
                    'name': 'Unknown Broker',
                    'protocol': 'N/A',
                    'paper_trading': False,
                    'endpoint': 'N/A',
                    'configured': False
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting broker info: {e}")
            return {
                'type': 'error',
                'name': 'Error',
                'protocol': 'N/A',
                'paper_trading': False,
                'endpoint': 'N/A',
                'configured': False
            }
    
    @staticmethod
    def test_broker_connection():
        """Test broker connection"""
        try:
            broker_type = bot_config.BROKER_TYPE.lower()
            
            if broker_type == 'alpaca':
                # Test Alpaca connection
                try:
                    account = alpaca_client.get_account()
                    if account:
                        logger.info("✅ Alpaca connection test successful")
                        return True
                    else:
                        logger.error("❌ Alpaca connection test failed")
                        return False
                except Exception as e:
                    logger.error(f"❌ Alpaca connection test error: {e}")
                    return False
            
            elif broker_type == 'das':
                # Test DAS FIX connection
                try:
                    from das_fix_client import DASFIXClient
                    
                    das_client = DASFIXClient(
                        sender_comp_id=bot_config.DAS_SENDER_COMP_ID or "TRADINGBOT",
                        target_comp_id=bot_config.DAS_TARGET_COMP_ID or "DAS",
                        fix_host=bot_config.DAS_FIX_HOST or "localhost",
                        fix_port=bot_config.DAS_FIX_PORT or 5001,
                        username=bot_config.DAS_USERNAME or "",
                        password=bot_config.DAS_PASSWORD or ""
                    )
                    
                    # Wait for logon
                    import time
                    time.sleep(3)
                    
                    if das_client.is_logged_on:
                        logger.info("✅ DAS FIX connection test successful")
                        das_client.disconnect()
                        return True
                    else:
                        logger.error("❌ DAS FIX connection test failed")
                        das_client.disconnect()
                        return False
                        
                except Exception as e:
                    logger.error(f"❌ DAS FIX connection test error: {e}")
                    return False
            
            else:
                logger.warning(f"⚠️ Unknown broker type for connection test: {broker_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testing broker connection: {e}")
            return False

# Global broker factory instance
broker_factory = BrokerFactory() 