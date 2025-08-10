#!/usr/bin/env python3
"""
Test DAS FIX API Client
Demonstrates how to use the DAS FIX API for order execution
"""

import os
import sys
import time
import signal
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config
from das_fix_client import DASFIXClient

logger = get_logger(__name__)

class DASFIXTester:
    """Test class for DAS FIX API"""
    
    def __init__(self):
        self.das_client = None
        self.test_orders = []
        
    def setup_client(self):
        """Setup DAS FIX client"""
        try:
            logger.info("🔧 Setting up DAS FIX client...")
            
            # Get DAS configuration
            das_config = bot_config.get_das_config_info()
            
            if not das_config['fix_configured']:
                logger.error("❌ DAS FIX not configured")
                logger.info("Please set the following environment variables:")
                logger.info("  DAS_FIX_HOST=localhost")
                logger.info("  DAS_FIX_PORT=5001")
                logger.info("  DAS_USERNAME=your_username")
                logger.info("  DAS_PASSWORD=your_password")
                return False
            
            # Create FIX client
            self.das_client = DASFIXClient(
                sender_comp_id=bot_config.DAS_SENDER_COMP_ID,
                target_comp_id=bot_config.DAS_TARGET_COMP_ID,
                fix_host=bot_config.DAS_FIX_HOST,
                fix_port=bot_config.DAS_FIX_PORT,
                username=bot_config.DAS_USERNAME,
                password=bot_config.DAS_PASSWORD
            )
            
            # Wait for logon
            logger.info("⏳ Waiting for FIX logon...")
            time.sleep(3)
            
            if self.das_client.is_logged_on:
                logger.info("✅ DAS FIX client setup successful")
                return True
            else:
                logger.error("❌ DAS FIX logon failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error setting up DAS FIX client: {e}")
            return False
    
    def test_market_order(self, symbol: str = "AAPL", quantity: int = 100):
        """Test market order placement"""
        try:
            if not self.das_client or not self.das_client.is_logged_on:
                logger.error("❌ DAS FIX client not ready")
                return None
            
            logger.info(f"📋 Testing market order: {symbol} {quantity} shares")
            
            # Place market order
            order = self.das_client.place_market_order(symbol, quantity, "BUY")
            
            if order:
                logger.info(f"✅ Market order placed: {order}")
                self.test_orders.append(order)
                return order
            else:
                logger.error("❌ Failed to place market order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error testing market order: {e}")
            return None
    
    def test_limit_order(self, symbol: str = "AAPL", quantity: int = 100, limit_price: float = 150.00):
        """Test limit order placement"""
        try:
            if not self.das_client or not self.das_client.is_logged_on:
                logger.error("❌ DAS FIX client not ready")
                return None
            
            logger.info(f"📋 Testing limit order: {symbol} {quantity} shares @ ${limit_price}")
            
            # Place limit order
            order = self.das_client.place_limit_order(symbol, quantity, "BUY", limit_price)
            
            if order:
                logger.info(f"✅ Limit order placed: {order}")
                self.test_orders.append(order)
                return order
            else:
                logger.error("❌ Failed to place limit order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error testing limit order: {e}")
            return None
    
    def test_stop_order(self, symbol: str = "AAPL", quantity: int = 100, stop_price: float = 140.00):
        """Test stop order placement"""
        try:
            if not self.das_client or not self.das_client.is_logged_on:
                logger.error("❌ DAS FIX client not ready")
                return None
            
            logger.info(f"📋 Testing stop order: {symbol} {quantity} shares @ ${stop_price}")
            
            # Place stop order
            order = self.das_client.place_stop_order(symbol, quantity, stop_price)
            
            if order:
                logger.info(f"✅ Stop order placed: {order}")
                self.test_orders.append(order)
                return order
            else:
                logger.error("❌ Failed to place stop order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error testing stop order: {e}")
            return None
    
    def test_order_cancel(self, cl_ord_id: str):
        """Test order cancellation"""
        try:
            if not self.das_client or not self.das_client.is_logged_on:
                logger.error("❌ DAS FIX client not ready")
                return False
            
            logger.info(f"❌ Testing order cancel: {cl_ord_id}")
            
            # Get order info
            order_info = self.das_client.orders.get(cl_ord_id)
            if not order_info:
                logger.error(f"❌ Order not found: {cl_ord_id}")
                return False
            
            # Cancel order
            success = self.das_client.cancel_order(cl_ord_id, order_info['symbol'])
            
            if success:
                logger.info(f"✅ Order cancel request sent: {cl_ord_id}")
                return True
            else:
                logger.error("❌ Failed to cancel order")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testing order cancel: {e}")
            return False
    
    def test_order_status(self, cl_ord_id: str):
        """Test order status request"""
        try:
            if not self.das_client or not self.das_client.is_logged_on:
                logger.error("❌ DAS FIX client not ready")
                return None
            
            logger.info(f"📊 Testing order status: {cl_ord_id}")
            
            # Get order status
            status = self.das_client.get_order_status(cl_ord_id)
            
            if status:
                logger.info(f"✅ Order status: {status}")
                return status
            else:
                logger.error("❌ Failed to get order status")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error testing order status: {e}")
            return None
    
    def add_execution_callback(self, execution_data):
        """Callback for execution reports"""
        logger.info(f"💰 Execution Report: {execution_data}")
    
    def run_comprehensive_test(self):
        """Run comprehensive FIX API test"""
        try:
            logger.info("🚀 Starting DAS FIX API comprehensive test")
            
            # Setup client
            if not self.setup_client():
                return False
            
            # Add execution callback
            self.das_client.add_execution_callback(self.add_execution_callback)
            
            # Test 1: Market Order
            logger.info("\n" + "="*50)
            logger.info("TEST 1: Market Order")
            logger.info("="*50)
            market_order = self.test_market_order("AAPL", 100)
            
            # Wait for execution
            time.sleep(2)
            
            # Test 2: Limit Order
            logger.info("\n" + "="*50)
            logger.info("TEST 2: Limit Order")
            logger.info("="*50)
            limit_order = self.test_limit_order("AAPL", 100, 150.00)
            
            # Wait for execution
            time.sleep(2)
            
            # Test 3: Stop Order
            logger.info("\n" + "="*50)
            logger.info("TEST 3: Stop Order")
            logger.info("="*50)
            stop_order = self.test_stop_order("AAPL", 100, 140.00)
            
            # Wait for execution
            time.sleep(2)
            
            # Test 4: Order Status
            if limit_order:
                logger.info("\n" + "="*50)
                logger.info("TEST 4: Order Status")
                logger.info("="*50)
                self.test_order_status(limit_order['cl_ord_id'])
            
            # Test 5: Order Cancel
            if stop_order:
                logger.info("\n" + "="*50)
                logger.info("TEST 5: Order Cancel")
                logger.info("="*50)
                self.test_order_cancel(stop_order['cl_ord_id'])
            
            # Wait for final executions
            logger.info("\n⏳ Waiting for final executions...")
            time.sleep(5)
            
            # Summary
            logger.info("\n" + "="*50)
            logger.info("TEST SUMMARY")
            logger.info("="*50)
            logger.info(f"Total orders placed: {len(self.test_orders)}")
            for i, order in enumerate(self.test_orders, 1):
                logger.info(f"  {i}. {order['cl_ord_id']}: {order['symbol']} {order['quantity']} {order['type']}")
            
            logger.info("✅ Comprehensive test completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in comprehensive test: {e}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.das_client:
                logger.info("🔌 Disconnecting DAS FIX client...")
                self.das_client.disconnect()
                
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

def signal_handler(signum, frame):
    """Handle interrupt signal"""
    logger.info("\n⚠️ Interrupt received, shutting down...")
    if tester:
        tester.cleanup()
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create tester
    tester = DASFIXTester()
    
    try:
        # Run comprehensive test
        success = tester.run_comprehensive_test()
        
        if success:
            logger.info("🎉 All tests passed!")
        else:
            logger.error("❌ Some tests failed")
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
    finally:
        # Cleanup
        tester.cleanup()
        logger.info("👋 Test completed")
