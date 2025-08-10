#!/usr/bin/env python3
"""
Enhanced Order Manager
Handles both DEMO and live trading with proper error handling and behavioral differences
"""

import os
import sys
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config
from bot.broker_factory import broker_factory

logger = get_logger(__name__)

class TradingMode(Enum):
    """Trading mode enumeration"""
    DEMO = "demo"
    LIVE = "live"
    PAPER = "paper"

class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class EnhancedOrderManager:
    """Enhanced order manager with DEMO/live mode handling"""
    
    def __init__(self):
        self.broker_client = None
        self.trading_mode = self._detect_trading_mode()
        self.orders = {}
        self.executions = {}
        self.rejected_orders = []
        self.order_callbacks = []
        
        # Initialize broker client
        self._init_broker_client()
        
        # Mode-specific settings
        self._setup_mode_settings()
    
    def _detect_trading_mode(self) -> TradingMode:
        """Detect current trading mode"""
        try:
            broker_type = bot_config.BROKER_TYPE.lower()
            
            if broker_type == 'alpaca':
                if bot_config.ALPACA_PAPER:
                    return TradingMode.PAPER
                else:
                    return TradingMode.LIVE
            
            elif broker_type == 'das':
                # Check if DAS is configured for live trading
                if (bot_config.DAS_FIX_HOST and bot_config.DAS_FIX_PORT and 
                    bot_config.DAS_USERNAME and bot_config.DAS_PASSWORD):
                    return TradingMode.LIVE
                else:
                    return TradingMode.DEMO
            
            else:
                return TradingMode.DEMO
                
        except Exception as e:
            logger.error(f"Error detecting trading mode: {e}")
            return TradingMode.DEMO
    
    def _init_broker_client(self):
        """Initialize broker client"""
        try:
            self.broker_client = broker_factory.get_broker_client()
            
            if self.broker_client:
                logger.info(f"✅ Broker client initialized for {self.trading_mode.value} mode")
                
                # Add execution callbacks
                if hasattr(self.broker_client, 'add_execution_callback'):
                    self.broker_client.add_execution_callback(self._handle_execution)
                
                if hasattr(self.broker_client, 'add_order_callback'):
                    self.broker_client.add_order_callback(self._handle_order_update)
                    
            else:
                logger.error("❌ Failed to initialize broker client")
                
        except Exception as e:
            logger.error(f"Error initializing broker client: {e}")
    
    def _setup_mode_settings(self):
        """Setup mode-specific settings"""
        if self.trading_mode == TradingMode.DEMO:
            logger.warning("⚠️ DEMO MODE: Orders will be simulated - no real trading")
            logger.warning("⚠️ DEMO MODE: Perfect fills, no slippage, no rejections")
            
            # DEMO mode settings
            self.max_order_size = 10000  # Large orders for testing
            self.min_order_size = 1      # Small orders for testing
            self.max_slippage = 0.0      # No slippage in DEMO
            self.execution_delay = 0.1   # Fast execution in DEMO
            
        elif self.trading_mode == TradingMode.PAPER:
            logger.info("📊 PAPER TRADING: Using paper trading account")
            
            # Paper trading settings
            self.max_order_size = 1000
            self.min_order_size = 1
            self.max_slippage = 0.02     # 2% max slippage
            self.execution_delay = 1.0   # Realistic delays
            
        else:  # LIVE mode
            logger.warning("🔥 LIVE TRADING: Real money at risk!")
            logger.warning("🔥 LIVE TRADING: Use extreme caution")
            
            # Live trading settings
            self.max_order_size = 100    # Conservative order sizes
            self.min_order_size = 1
            self.max_slippage = 0.01     # 1% max slippage
            self.execution_delay = 2.0   # Conservative delays
    
    def add_order_callback(self, callback: Callable):
        """Add callback for order updates"""
        self.order_callbacks.append(callback)
    
    def _handle_execution(self, execution_data: Dict[str, Any]):
        """Handle execution reports"""
        try:
            logger.info(f"💰 Execution: {execution_data}")
            
            # Store execution
            execution_id = execution_data.get('exec_id', f"exec_{int(time.time() * 1000)}")
            self.executions[execution_id] = execution_data
            
            # Update order status
            cl_ord_id = execution_data.get('cl_ord_id')
            if cl_ord_id and cl_ord_id in self.orders:
                order = self.orders[cl_ord_id]
                
                # Update order with execution data
                order.update({
                    'last_execution': execution_data,
                    'cum_qty': execution_data.get('cum_qty', 0),
                    'avg_price': execution_data.get('avg_px', 0),
                    'leaves_qty': execution_data.get('leaves_qty', 0),
                    'last_updated': datetime.now().isoformat()
                })
                
                # Determine order status
                if order['leaves_qty'] == 0:
                    order['status'] = OrderStatus.FILLED.value
                elif order['cum_qty'] > 0:
                    order['status'] = OrderStatus.PARTIALLY_FILLED.value
                
                logger.info(f"📊 Order {cl_ord_id} updated: {order['status']}")
            
            # Notify callbacks
            for callback in self.order_callbacks:
                try:
                    callback(execution_data)
                except Exception as e:
                    logger.error(f"Error in execution callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling execution: {e}")
    
    def _handle_order_update(self, order_data: Dict[str, Any]):
        """Handle order updates"""
        try:
            logger.info(f"📋 Order Update: {order_data}")
            
            # Update order status
            cl_ord_id = order_data.get('cl_ord_id')
            if cl_ord_id and cl_ord_id in self.orders:
                self.orders[cl_ord_id].update(order_data)
                
                # Handle rejections
                if order_data.get('status') == OrderStatus.REJECTED.value:
                    self.rejected_orders.append(order_data)
                    logger.error(f"❌ Order rejected: {order_data}")
            
            # Notify callbacks
            for callback in self.order_callbacks:
                try:
                    callback(order_data)
                except Exception as e:
                    logger.error(f"Error in order callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling order update: {e}")
    
    def _validate_order(self, symbol: str, quantity: int, side: str, order_type: str, price: float = None) -> bool:
        """Validate order before placement"""
        try:
            # Basic validation
            if not symbol or not quantity or not side:
                logger.error("❌ Invalid order parameters")
                return False
            
            if quantity <= 0:
                logger.error("❌ Invalid quantity")
                return False
            
            if quantity > self.max_order_size:
                logger.error(f"❌ Order size {quantity} exceeds maximum {self.max_order_size}")
                return False
            
            if quantity < self.min_order_size:
                logger.error(f"❌ Order size {quantity} below minimum {self.min_order_size}")
                return False
            
            # Price validation for limit orders
            if order_type == OrderType.LIMIT.value and (price is None or price <= 0):
                logger.error("❌ Invalid limit price")
                return False
            
            # Live trading additional checks
            if self.trading_mode == TradingMode.LIVE:
                # Check account balance (if available)
                if hasattr(self.broker_client, 'get_account'):
                    try:
                        account = self.broker_client.get_account()
                        if account:
                            buying_power = account.get('buying_power', 0)
                            order_value = quantity * (price or 100)  # Estimate
                            
                            if order_value > buying_power:
                                logger.error(f"❌ Insufficient buying power: ${buying_power} < ${order_value}")
                                return False
                    except Exception as e:
                        logger.warning(f"Could not check account balance: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating order: {e}")
            return False
    
    def _simulate_demo_execution(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate execution in DEMO mode"""
        try:
            # Simulate execution delay
            time.sleep(self.execution_delay)
            
            # Create simulated execution
            execution_data = {
                'exec_id': f"DEMO_EXEC_{int(time.time() * 1000)}",
                'cl_ord_id': order['cl_ord_id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'quantity': order['quantity'],
                'price': order.get('limit_price', 150.00),  # Simulated price
                'exec_type': '2',  # Fill
                'exec_status': '2',  # Filled
                'cum_qty': order['quantity'],
                'leaves_qty': 0,
                'avg_px': order.get('limit_price', 150.00),
                'timestamp': datetime.now().isoformat(),
                'demo_mode': True
            }
            
            # Trigger execution callback
            self._handle_execution(execution_data)
            
            return execution_data
            
        except Exception as e:
            logger.error(f"Error simulating DEMO execution: {e}")
            return {}
    
    async def place_market_order(self, symbol: str, quantity: int, side: str, account: str = "") -> Optional[Dict[str, Any]]:
        """Place a market order with enhanced error handling"""
        try:
            logger.info(f"📋 Placing market order: {symbol} {quantity} shares {side}")
            
            # Validate order
            if not self._validate_order(symbol, quantity, side, OrderType.MARKET.value):
                return None
            
            # Create order info
            order_info = {
                'cl_ord_id': f"ORDER_{int(time.time() * 1000)}",
                'symbol': symbol,
                'quantity': quantity,
                'side': side,
                'type': OrderType.MARKET.value,
                'status': OrderStatus.PENDING.value,
                'created_at': datetime.now().isoformat(),
                'trading_mode': self.trading_mode.value
            }
            
            # Place order with broker
            if self.broker_client and hasattr(self.broker_client, 'place_market_order'):
                try:
                    result = self.broker_client.place_market_order(symbol, quantity, side, account)
                    
                    if result:
                        order_info.update(result)
                        order_info['status'] = OrderStatus.SUBMITTED.value
                        
                        # Store order
                        self.orders[order_info['cl_ord_id']] = order_info
                        
                        logger.info(f"✅ Market order submitted: {order_info['cl_ord_id']}")
                        
                        # Simulate execution in DEMO mode
                        if self.trading_mode == TradingMode.DEMO:
                            await asyncio.sleep(self.execution_delay)
                            self._simulate_demo_execution(order_info)
                        
                        return order_info
                    else:
                        logger.error("❌ Failed to place market order")
                        return None
                        
                except Exception as e:
                    logger.error(f"❌ Error placing market order: {e}")
                    return None
            else:
                logger.error("❌ Broker client not available or doesn't support market orders")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in place_market_order: {e}")
            return None
    
    async def place_limit_order(self, symbol: str, quantity: int, side: str, limit_price: float, account: str = "") -> Optional[Dict[str, Any]]:
        """Place a limit order with enhanced error handling"""
        try:
            logger.info(f"📋 Placing limit order: {symbol} {quantity} shares {side} @ ${limit_price}")
            
            # Validate order
            if not self._validate_order(symbol, quantity, side, OrderType.LIMIT.value, limit_price):
                return None
            
            # Create order info
            order_info = {
                'cl_ord_id': f"ORDER_{int(time.time() * 1000)}",
                'symbol': symbol,
                'quantity': quantity,
                'side': side,
                'type': OrderType.LIMIT.value,
                'limit_price': limit_price,
                'status': OrderStatus.PENDING.value,
                'created_at': datetime.now().isoformat(),
                'trading_mode': self.trading_mode.value
            }
            
            # Place order with broker
            if self.broker_client and hasattr(self.broker_client, 'place_limit_order'):
                try:
                    result = self.broker_client.place_limit_order(symbol, quantity, side, limit_price, account)
                    
                    if result:
                        order_info.update(result)
                        order_info['status'] = OrderStatus.SUBMITTED.value
                        
                        # Store order
                        self.orders[order_info['cl_ord_id']] = order_info
                        
                        logger.info(f"✅ Limit order submitted: {order_info['cl_ord_id']}")
                        
                        # Simulate execution in DEMO mode (with some probability)
                        if self.trading_mode == TradingMode.DEMO:
                            await asyncio.sleep(self.execution_delay)
                            # 50% chance of immediate fill in DEMO
                            if time.time() % 2 == 0:
                                self._simulate_demo_execution(order_info)
                        
                        return order_info
                    else:
                        logger.error("❌ Failed to place limit order")
                        return None
                        
                except Exception as e:
                    logger.error(f"❌ Error placing limit order: {e}")
                    return None
            else:
                logger.error("❌ Broker client not available or doesn't support limit orders")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in place_limit_order: {e}")
            return None
    
    async def place_stop_order(self, symbol: str, quantity: int, stop_price: float, account: str = "") -> Optional[Dict[str, Any]]:
        """Place a stop order with enhanced error handling"""
        try:
            logger.info(f"📋 Placing stop order: {symbol} {quantity} shares @ ${stop_price}")
            
            # Validate order
            if not self._validate_order(symbol, quantity, "SELL", OrderType.STOP.value, stop_price):
                return None
            
            # Create order info
            order_info = {
                'cl_ord_id': f"ORDER_{int(time.time() * 1000)}",
                'symbol': symbol,
                'quantity': quantity,
                'side': 'SELL',
                'type': OrderType.STOP.value,
                'stop_price': stop_price,
                'status': OrderStatus.PENDING.value,
                'created_at': datetime.now().isoformat(),
                'trading_mode': self.trading_mode.value
            }
            
            # Place order with broker
            if self.broker_client and hasattr(self.broker_client, 'place_stop_order'):
                try:
                    result = self.broker_client.place_stop_order(symbol, quantity, stop_price, account)
                    
                    if result:
                        order_info.update(result)
                        order_info['status'] = OrderStatus.SUBMITTED.value
                        
                        # Store order
                        self.orders[order_info['cl_ord_id']] = order_info
                        
                        logger.info(f"✅ Stop order submitted: {order_info['cl_ord_id']}")
                        return order_info
                    else:
                        logger.error("❌ Failed to place stop order")
                        return None
                        
                except Exception as e:
                    logger.error(f"❌ Error placing stop order: {e}")
                    return None
            else:
                logger.error("❌ Broker client not available or doesn't support stop orders")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in place_stop_order: {e}")
            return None
    
    def cancel_order(self, cl_ord_id: str) -> bool:
        """Cancel an order"""
        try:
            logger.info(f"❌ Cancelling order: {cl_ord_id}")
            
            if cl_ord_id not in self.orders:
                logger.error(f"❌ Order not found: {cl_ord_id}")
                return False
            
            order = self.orders[cl_ord_id]
            
            # Cancel with broker
            if self.broker_client and hasattr(self.broker_client, 'cancel_order'):
                try:
                    success = self.broker_client.cancel_order(cl_ord_id, order['symbol'])
                    
                    if success:
                        order['status'] = OrderStatus.CANCELLED.value
                        order['cancelled_at'] = datetime.now().isoformat()
                        logger.info(f"✅ Order cancelled: {cl_ord_id}")
                        return True
                    else:
                        logger.error("❌ Failed to cancel order")
                        return False
                        
                except Exception as e:
                    logger.error(f"❌ Error cancelling order: {e}")
                    return False
            else:
                logger.error("❌ Broker client not available or doesn't support order cancellation")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in cancel_order: {e}")
            return False
    
    def get_order_status(self, cl_ord_id: str) -> Optional[Dict[str, Any]]:
        """Get order status"""
        try:
            if cl_ord_id in self.orders:
                return self.orders[cl_ord_id]
            else:
                logger.error(f"❌ Order not found: {cl_ord_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting order status: {e}")
            return None
    
    def get_trading_mode_info(self) -> Dict[str, Any]:
        """Get trading mode information"""
        return {
            'mode': self.trading_mode.value,
            'max_order_size': self.max_order_size,
            'min_order_size': self.min_order_size,
            'max_slippage': self.max_slippage,
            'execution_delay': self.execution_delay,
            'total_orders': len(self.orders),
            'total_executions': len(self.executions),
            'rejected_orders': len(self.rejected_orders)
        }

# Global order manager instance
order_manager = EnhancedOrderManager() 