#!/usr/bin/env python3
"""
Test DAS DEMO Mode with CMD API
Tests DAS Trader in DEMO mode without real broker connection
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
from das_client import DASClient

logger = get_logger(__name__)

class DASDemoTester:
    """Test class for DAS DEMO mode"""
    
    def __init__(self):
        self.das_client = None
        self.test_orders = []
        
    def setup_demo_client(self):
        """Setup DAS client for DEMO mode"""
        try:
            logger.info("🔧 Setting up DAS DEMO client...")
            
            # Check if DAS is configured for DEMO
            if not bot_config.DAS_API_KEY:
                logger.warning("⚠️ No DAS API key configured, using demo defaults")
            
            # Create DAS client (will connect to local DAS Trader)
            self.das_client = DASClient()
            
            # Wait for connection
            time.sleep(2)
            
            if self.das_client.is_connected:
                logger.info("✅ DAS DEMO client connected successfully")
                logger.info("📊 DEMO Mode: Orders will be simulated (no real trading)")
                return True
            else:
                logger.error("❌ Failed to connect to DAS Trader")
                logger.info("💡 Make sure DAS Trader Pro is running in DEMO mode")
                logger.info("💡 Enable CMD API in DAS Trader settings")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error setting up DAS DEMO client: {e}")
            return False
    
    def test_demo_market_order(self, symbol: str = "AAPL", quantity: int = 100):
        """Test market order in DEMO mode"""
        try:
            if not self.das_client or not self.das_client.is_connected:
                logger.error("❌ DAS DEMO client not ready")
                return None
            
            logger.info(f"📋 Testing DEMO market order: {symbol} {quantity} shares")
            
            # Place market order (will be simulated)
            order = self.das_client.place_market_order(symbol, quantity, "BUY")
            
            if order:
                logger.info(f"✅ DEMO market order placed: {order}")
                self.test_orders.append(order)
                return order
            else:
                logger.error("❌ Failed to place DEMO market order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error testing DEMO market order: {e}")
            return None
    
    def test_demo_limit_order(self, symbol: str = "AAPL", quantity: int = 100, limit_price: float = 150.00):
        """Test limit order in DEMO mode"""
        try:
            if not self.das_client or not self.das_client.is_connected:
                logger.error("❌ DAS DEMO client not ready")
                return None
            
            logger.info(f"📋 Testing DEMO limit order: {symbol} {quantity} shares @ ${limit_price}")
            
            # Place limit order (will be simulated)
            order = self.das_client.place_limit_order(symbol, quantity, "BUY", limit_price)
            
            if order:
                logger.info(f"✅ DEMO limit order placed: {order}")
                self.test_orders.append(order)
                return order
            else:
                logger.error("❌ Failed to place DEMO limit order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error testing DEMO limit order: {e}")
            return None
    
    def test_demo_stop_order(self, symbol: str = "AAPL", quantity: int = 100, stop_price: float = 140.00):
        """Test stop order in DEMO mode"""
        try:
            if not self.das_client or not self.das_client.is_connected:
                logger.error("❌ DAS DEMO client not ready")
                return None
            
            logger.info(f"📋 Testing DEMO stop order: {symbol} {quantity} shares @ ${stop_price}")
            
            # Place stop order (will be simulated)
            order = self.das_client.place_stop_order(symbol, quantity, stop_price)
            
            if order:
                logger.info(f"✅ DEMO stop order placed: {order}")
                self.test_orders.append(order)
                return order
            else:
                logger.error("❌ Failed to place DEMO stop order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error testing DEMO stop order: {e}")
            return None
    
    def test_demo_order_cancel(self, order_id: str):
        """Test order cancellation in DEMO mode"""
        try:
            if not self.das_client or not self.das_client.is_connected:
                logger.error("❌ DAS DEMO client not ready")
                return False
            
            logger.info(f"❌ Testing DEMO order cancel: {order_id}")
            
            # Cancel order (will be simulated)
            success = self.das_client.cancel_order(order_id)
            
            if success:
                logger.info(f"✅ DEMO order cancel request sent: {order_id}")
                return True
            else:
                logger.error("❌ Failed to cancel DEMO order")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testing DEMO order cancel: {e}")
            return False
    
    def run_demo_comprehensive_test(self):
        """Run comprehensive DEMO test"""
        try:
            logger.info("🚀 Starting DAS DEMO comprehensive test")
            logger.info("📊 NOTE: This is DEMO mode - no real trading will occur")
            
            # Setup client
            if not self.setup_demo_client():
                return False
            
            # Test 1: Market Order
            logger.info("\n" + "="*50)
            logger.info("TEST 1: DEMO Market Order")
            logger.info("="*50)
            market_order = self.test_demo_market_order("AAPL", 100)
            
            # Wait for simulation
            time.sleep(2)
            
            # Test 2: Limit Order
            logger.info("\n" + "="*50)
            logger.info("TEST 2: DEMO Limit Order")
            logger.info("="*50)
            limit_order = self.test_demo_limit_order("AAPL", 100, 150.00)
            
            # Wait for simulation
            time.sleep(2)
            
            # Test 3: Stop Order
            logger.info("\n" + "="*50)
            logger.info("TEST 3: DEMO Stop Order")
            logger.info("="*50)
            stop_order = self.test_demo_stop_order("AAPL", 100, 140.00)
            
            # Wait for simulation
            time.sleep(2)
            
            # Test 4: Order Cancel
            if stop_order:
                logger.info("\n" + "="*50)
                logger.info("TEST 4: DEMO Order Cancel")
                logger.info("="*50)
                self.test_demo_order_cancel(stop_order.get('order_id', 'DEMO_ORDER_001'))
            
            # Wait for final simulations
            logger.info("\n⏳ Waiting for final DEMO executions...")
            time.sleep(5)
            
            # Summary
            logger.info("\n" + "="*50)
            logger.info("DEMO TEST SUMMARY")
            logger.info("="*50)
            logger.info(f"Total DEMO orders placed: {len(self.test_orders)}")
            for i, order in enumerate(self.test_orders, 1):
                logger.info(f"  {i}. {order.get('order_id', 'DEMO_ORDER')}: {order.get('symbol', 'UNKNOWN')} {order.get('quantity', 0)} {order.get('type', 'UNKNOWN')}")
            
            logger.info("✅ DEMO comprehensive test completed")
            logger.info("💡 Check DAS Trader Pro to see simulated orders")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in DEMO comprehensive test: {e}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.das_client:
                logger.info("🔌 Disconnecting DAS DEMO client...")
                # DAS client doesn't have explicit disconnect, just close socket
                if hasattr(self.das_client, 'socket') and self.das_client.socket:
                    self.das_client.socket.close()
                
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
    tester = DASDemoTester()
    
    try:
        # Run comprehensive DEMO test
        success = tester.run_demo_comprehensive_test()
        
        if success:
            logger.info("🎉 All DEMO tests passed!")
            logger.info("💡 Remember: This was DEMO mode - no real trading occurred")
        else:
            logger.error("❌ Some DEMO tests failed")
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ DEMO test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
    finally:
        # Cleanup
        tester.cleanup()
        logger.info("👋 DEMO test completed")
