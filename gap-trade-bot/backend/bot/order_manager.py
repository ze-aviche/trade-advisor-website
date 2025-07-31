"""
Order Manager for Trading Bot
Handles order execution, order tracking, and broker integration
Uses broker client classes for all order operations and trading database for storage
"""

import sys
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from config import config
from broker_factory import broker_factory
from trading_database import trading_db

logger = get_logger(__name__)

class OrderManager:
    """Manages order execution and tracking using broker clients and trading database"""
    
    def __init__(self):
        self.pending_orders = {}  # Orders waiting to be executed
        self.executed_orders = []  # Completed orders
        self.failed_orders = []    # Failed orders
        
        # Get broker client
        self.broker_client = broker_factory.get_broker_client()
        self.broker_info = broker_factory.get_broker_info()
        
        # Determine if we can use real trading
        self.use_real_trading = self.broker_client is not None and self.broker_info['configured']
        self.mock_mode = not self.use_real_trading
        
        if self.use_real_trading:
            logger.info(f"✅ Using {self.broker_info['name']} for order execution")
        else:
            logger.info("⚠️ Using mock mode for order execution (no broker credentials)")
    
    def place_buy_order(self, ticker: str, quantity: int, price: float, 
                       order_type: str = 'market') -> Dict[str, Any]:
        """Place a buy order using broker client"""
        try:
            if self.use_real_trading and self.broker_client:
                # Use broker client for order execution
                if order_type == 'market':
                    order = self.broker_client.place_market_order(ticker, quantity, 'buy')
                elif order_type == 'limit':
                    order = self.broker_client.place_limit_order(ticker, quantity, 'buy', price)
                else:
                    logger.error(f"❌ Unsupported order type: {order_type}")
                    return {'error': f'Unsupported order type: {order_type}'}
                
                if order:
                    # Store order in database
                    order_data = {
                        'order_id': order.get('order_id', f"BUY_{ticker}_{int(time.time())}"),
                        'ticker': ticker,
                        'quantity': quantity,
                        'side': 'buy',
                        'order_type': order_type,
                        'status': 'submitted',
                        'price': price if order_type == 'limit' else None,
                        'limit_price': price if order_type == 'limit' else None,
                        'broker': self.broker_info['name'],
                        'strategy': 'break_out',
                        'notes': f"Buy order placed via {self.broker_info['name']}"
                    }
                    
                    trading_db.store_order(order_data)
                    self.executed_orders.append(order)
                    logger.info(f"✅ {self.broker_info['name']} BUY order executed: {ticker} {quantity} shares")
                    return order
                else:
                    return {'error': f'Failed to place {self.broker_info["name"]} order'}
            
            else:
                # Mock order execution
                order_id = f"BUY_{ticker}_{int(time.time())}"
                order = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'action': 'buy',
                    'quantity': quantity,
                    'price': price,
                    'order_type': order_type,
                    'status': 'executed',
                    'created_at': datetime.now().isoformat(),
                    'executed_at': datetime.now().isoformat(),
                    'executed_price': price,
                    'commission': self._calculate_commission(quantity, price)
                }
                
                # Store mock order in database
                order_data = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'quantity': quantity,
                    'side': 'buy',
                    'order_type': order_type,
                    'status': 'executed',
                    'price': price,
                    'broker': 'mock',
                    'strategy': 'break_out',
                    'notes': 'Mock order execution'
                }
                
                trading_db.store_order(order_data)
                self.executed_orders.append(order)
                logger.info(f"✅ Mock BUY order executed: {ticker} {quantity} shares @ ${price:.2f}")
                
                return order
            
        except Exception as e:
            logger.error(f"❌ Error placing buy order: {e}")
            return {'error': str(e)}
    
    def place_sell_order(self, ticker: str, quantity: int, price: float, 
                        order_type: str = 'market') -> Dict[str, Any]:
        """Place a sell order using broker client"""
        try:
            if self.use_real_trading and self.broker_client:
                # Use broker client for order execution
                if order_type == 'market':
                    order = self.broker_client.place_market_order(ticker, quantity, 'sell')
                elif order_type == 'limit':
                    order = self.broker_client.place_limit_order(ticker, quantity, 'sell', price)
                else:
                    logger.error(f"❌ Unsupported order type: {order_type}")
                    return {'error': f'Unsupported order type: {order_type}'}
                
                if order:
                    # Store order in database
                    order_data = {
                        'order_id': order.get('order_id', f"SELL_{ticker}_{int(time.time())}"),
                        'ticker': ticker,
                        'quantity': quantity,
                        'side': 'sell',
                        'order_type': order_type,
                        'status': 'submitted',
                        'price': price if order_type == 'limit' else None,
                        'limit_price': price if order_type == 'limit' else None,
                        'broker': self.broker_info['name'],
                        'strategy': 'break_out',
                        'notes': f"Sell order placed via {self.broker_info['name']}"
                    }
                    
                    trading_db.store_order(order_data)
                    self.executed_orders.append(order)
                    logger.info(f"✅ {self.broker_info['name']} SELL order executed: {ticker} {quantity} shares")
                    return order
                else:
                    return {'error': f'Failed to place {self.broker_info["name"]} order'}
            
            else:
                # Mock order execution
                order_id = f"SELL_{ticker}_{int(time.time())}"
                order = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'action': 'sell',
                    'quantity': quantity,
                    'price': price,
                    'order_type': order_type,
                    'status': 'executed',
                    'created_at': datetime.now().isoformat(),
                    'executed_at': datetime.now().isoformat(),
                    'executed_price': price,
                    'commission': self._calculate_commission(quantity, price)
                }
                
                # Store mock order in database
                order_data = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'quantity': quantity,
                    'side': 'sell',
                    'order_type': order_type,
                    'status': 'executed',
                    'price': price,
                    'broker': 'mock',
                    'strategy': 'break_out',
                    'notes': 'Mock order execution'
                }
                
                trading_db.store_order(order_data)
                self.executed_orders.append(order)
                logger.info(f"✅ Mock SELL order executed: {ticker} {quantity} shares @ ${price:.2f}")
                
                return order
            
        except Exception as e:
            logger.error(f"❌ Error placing sell order: {e}")
            return {'error': str(e)}
    
    def place_stop_order(self, ticker: str, quantity: int, stop_price: float) -> Dict[str, Any]:
        """Place a stop order using broker client"""
        try:
            if self.use_real_trading and self.broker_client:
                # Use broker client for stop order
                order = self.broker_client.place_stop_order(ticker, quantity, stop_price)
                
                if order:
                    # Store order in database
                    order_data = {
                        'order_id': order.get('order_id', f"STOP_{ticker}_{int(time.time())}"),
                        'ticker': ticker,
                        'quantity': quantity,
                        'side': 'sell',
                        'order_type': 'stop',
                        'status': 'submitted',
                        'stop_price': stop_price,
                        'broker': self.broker_info['name'],
                        'strategy': 'break_out',
                        'notes': f"Stop order placed via {self.broker_info['name']}"
                    }
                    
                    trading_db.store_order(order_data)
                    self.pending_orders[order.get('order_id', f"STOP_{ticker}")] = {
                        'ticker': ticker,
                        'type': 'stop',
                        'stop_price': stop_price,
                        'quantity': quantity,
                        'created_at': datetime.now().isoformat()
                    }
                    
                    logger.info(f"✅ {self.broker_info['name']} STOP order placed: {ticker} {quantity} shares @ ${stop_price:.2f}")
                    return order
                else:
                    return {'error': f'Failed to place {self.broker_info["name"]} stop order'}
            
            else:
                # Mock stop order
                order_id = f"STOP_{ticker}_{int(time.time())}"
                order = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'action': 'sell',
                    'quantity': quantity,
                    'stop_price': stop_price,
                    'order_type': 'stop',
                    'status': 'pending',
                    'created_at': datetime.now().isoformat()
                }
                
                # Store mock order in database
                order_data = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'quantity': quantity,
                    'side': 'sell',
                    'order_type': 'stop',
                    'status': 'pending',
                    'stop_price': stop_price,
                    'broker': 'mock',
                    'strategy': 'break_out',
                    'notes': 'Mock stop order'
                }
                
                trading_db.store_order(order_data)
                self.pending_orders[order_id] = {
                    'ticker': ticker,
                    'type': 'stop',
                    'stop_price': stop_price,
                    'quantity': quantity,
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"✅ Mock STOP order placed: {ticker} {quantity} shares @ ${stop_price:.2f}")
                return order
            
        except Exception as e:
            logger.error(f"❌ Error placing stop order: {e}")
            return {'error': str(e)}
    
    def place_limit_order(self, ticker: str, quantity: int, limit_price: float, 
                         action: str = 'buy') -> Dict[str, Any]:
        """Place a limit order using broker client"""
        try:
            if self.use_real_trading and self.broker_client:
                # Use broker client for limit order
                order = self.broker_client.place_limit_order(ticker, quantity, action, limit_price)
                
                if order:
                    # Store order in database
                    order_data = {
                        'order_id': order.get('order_id', f"LIMIT_{ticker}_{int(time.time())}"),
                        'ticker': ticker,
                        'quantity': quantity,
                        'side': action,
                        'order_type': 'limit',
                        'status': 'submitted',
                        'limit_price': limit_price,
                        'broker': self.broker_info['name'],
                        'strategy': 'break_out',
                        'notes': f"Limit order placed via {self.broker_info['name']}"
                    }
                    
                    trading_db.store_order(order_data)
                    self.pending_orders[order.get('order_id', f"LIMIT_{ticker}")] = {
                        'ticker': ticker,
                        'type': 'limit',
                        'limit_price': limit_price,
                        'action': action,
                        'quantity': quantity,
                        'created_at': datetime.now().isoformat()
                    }
                    
                    logger.info(f"✅ {self.broker_info['name']} LIMIT order placed: {ticker} {quantity} shares {action} @ ${limit_price:.2f}")
                    return order
                else:
                    return {'error': f'Failed to place {self.broker_info["name"]} limit order'}
            
            else:
                # Mock limit order
                order_id = f"LIMIT_{ticker}_{int(time.time())}"
                order = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'action': action,
                    'quantity': quantity,
                    'limit_price': limit_price,
                    'order_type': 'limit',
                    'status': 'pending',
                    'created_at': datetime.now().isoformat()
                }
                
                # Store mock order in database
                order_data = {
                    'order_id': order_id,
                    'ticker': ticker,
                    'quantity': quantity,
                    'side': action,
                    'order_type': 'limit',
                    'status': 'pending',
                    'limit_price': limit_price,
                    'broker': 'mock',
                    'strategy': 'break_out',
                    'notes': 'Mock limit order'
                }
                
                trading_db.store_order(order_data)
                self.pending_orders[order_id] = {
                    'ticker': ticker,
                    'type': 'limit',
                    'limit_price': limit_price,
                    'action': action,
                    'quantity': quantity,
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"✅ Mock LIMIT order placed: {ticker} {quantity} shares {action} @ ${limit_price:.2f}")
                return order
            
        except Exception as e:
            logger.error(f"❌ Error placing limit order: {e}")
            return {'error': str(e)}
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order using broker client"""
        try:
            if self.use_real_trading and self.broker_client:
                # Use broker client to cancel order
                success = self.broker_client.cancel_order(order_id)
                
                if success:
                    # Update order status in database
                    trading_db.update_order_status(order_id, 'cancelled')
                    
                    if order_id in self.pending_orders:
                        del self.pending_orders[order_id]
                    logger.info(f"✅ {self.broker_info['name']} order cancelled: {order_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to cancel {self.broker_info['name']} order: {order_id}")
                    return False
            
            else:
                # Mock order cancellation
                if order_id in self.pending_orders:
                    del self.pending_orders[order_id]
                    # Update order status in database
                    trading_db.update_order_status(order_id, 'cancelled')
                    logger.info(f"✅ Mock order cancelled: {order_id}")
                    return True
                else:
                    logger.warning(f"⚠️ Order not found for cancellation: {order_id}")
                    return False
            
        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            return False
    
    def check_stop_orders(self, current_prices: Dict[str, float]):
        """Check stop orders against current prices"""
        try:
            orders_to_cancel = []
            
            for order_id, order_info in self.pending_orders.items():
                if order_info['type'] == 'stop':
                    ticker = order_info['ticker']
                    stop_price = order_info['stop_price']
                    current_price = current_prices.get(ticker)
                    
                    if current_price and current_price <= stop_price:
                        logger.info(f"🛑 Stop order triggered: {ticker} @ ${current_price:.2f} <= ${stop_price:.2f}")
                        orders_to_cancel.append(order_id)
            
            # Cancel triggered stop orders
            for order_id in orders_to_cancel:
                self.cancel_order(order_id)
                
        except Exception as e:
            logger.error(f"❌ Error checking stop orders: {e}")
    
    def check_limit_orders(self, current_prices: Dict[str, float]):
        """Check limit orders against current prices"""
        try:
            orders_to_cancel = []
            
            for order_id, order_info in self.pending_orders.items():
                if order_info['type'] == 'limit':
                    ticker = order_info['ticker']
                    limit_price = order_info['limit_price']
                    action = order_info['action']
                    current_price = current_prices.get(ticker)
                    
                    if current_price:
                        if action == 'buy' and current_price <= limit_price:
                            logger.info(f"💰 Buy limit order triggered: {ticker} @ ${current_price:.2f} <= ${limit_price:.2f}")
                            orders_to_cancel.append(order_id)
                        elif action == 'sell' and current_price >= limit_price:
                            logger.info(f"💰 Sell limit order triggered: {ticker} @ ${current_price:.2f} >= ${limit_price:.2f}")
                            orders_to_cancel.append(order_id)
            
            # Cancel triggered limit orders
            for order_id in orders_to_cancel:
                self.cancel_order(order_id)
                
        except Exception as e:
            logger.error(f"❌ Error checking limit orders: {e}")
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status using broker client"""
        try:
            if self.use_real_trading and self.broker_client:
                # Use broker client to get order status
                return self.broker_client.get_order_status(order_id)
            else:
                # Get from database
                return trading_db.get_order(order_id)
            
        except Exception as e:
            logger.error(f"❌ Error getting order status: {e}")
            return None
    
    def get_pending_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get pending orders using broker client"""
        try:
            if self.use_real_trading and self.broker_client:
                # Use broker client to get pending orders
                orders = self.broker_client.get_pending_orders()
                return {order['order_id']: order for order in orders}
            else:
                # Return mock pending orders
                return self.pending_orders
            
        except Exception as e:
            logger.error(f"❌ Error getting pending orders: {e}")
            return {}
    
    def get_executed_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get executed orders from database"""
        try:
            # Get from database
            return trading_db.get_trade_history(limit=limit)
        except Exception as e:
            logger.error(f"❌ Error getting executed orders: {e}")
            return []
    
    def get_order_summary(self) -> Dict[str, Any]:
        """Get order execution summary"""
        try:
            # Get from database
            return trading_db.get_performance_summary()
        except Exception as e:
            logger.error(f"❌ Error getting order summary: {e}")
            return {}
    
    def _calculate_commission(self, quantity: int, price: float) -> float:
        """Calculate commission for mock orders"""
        # Mock commission calculation
        commission_rate = 0.005  # $0.005 per share
        return quantity * commission_rate 

# Global order manager instance
order_manager = OrderManager() 