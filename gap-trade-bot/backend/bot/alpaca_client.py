"""
Alpaca Trading Client
Handles order execution, account management, and position tracking via Alpaca API
"""

import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from logging_config import get_logger
from bot.config import config as bot_config

logger = get_logger(__name__)

class AlpacaClient:
    """Alpaca Trading Client for order execution and account management"""
    
    def __init__(self):
        self.api_key = bot_config.BROKER_API_KEY
        self.secret_key = bot_config.BROKER_SECRET
        self.paper = True  # Use paper trading by default
        self.base_url = "https://paper-api.alpaca.markets" if self.paper else "https://api.alpaca.markets"
        
        # Initialize clients
        self.trading_client = None
        self.data_client = None
        
        # Account info
        self.account = None
        self.positions = {}
        
        # Initialize connection
        self._init_clients()
    
    def _init_clients(self):
        """Initialize Alpaca clients"""
        try:
            if not self.api_key or not self.secret_key:
                logger.warning("⚠️ Alpaca API credentials not configured")
                return False
            
            # Initialize trading client
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper
            )
            
            # Initialize data client
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key
            )
            
            # Test connection
            self.account = self.trading_client.get_account()
            logger.info(f"✅ Connected to Alpaca {'Paper' if self.paper else 'Live'} Trading")
            logger.info(f"💰 Account: {self.account.account_number}")
            logger.info(f"💵 Cash: ${float(self.account.cash):.2f}")
            logger.info(f"📈 Portfolio Value: ${float(self.account.portfolio_value):.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing Alpaca clients: {e}")
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            if not self.account:
                self.account = self.trading_client.get_account()
            
            return {
                'account_number': self.account.account_number,
                'cash': float(self.account.cash),
                'portfolio_value': float(self.account.portfolio_value),
                'buying_power': float(self.account.buying_power),
                'equity': float(self.account.equity),
                'daytrade_count': self.account.daytrade_count,
                'status': self.account.status,
                'currency': self.account.currency
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting account info: {e}")
            return {}
    
    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions"""
        try:
            positions = self.trading_client.get_all_positions()
            position_dict = {}
            
            for position in positions:
                position_dict[position.symbol] = {
                    'symbol': position.symbol,
                    'quantity': int(position.qty),
                    'side': position.side,
                    'market_value': float(position.market_value),
                    'unrealized_pl': float(position.unrealized_pl),
                    'unrealized_plpc': float(position.unrealized_plpc),
                    'avg_entry_price': float(position.avg_entry_price),
                    'current_price': float(position.current_price)
                }
            
            self.positions = position_dict
            return position_dict
            
        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
            return {}
    
    def place_market_order(self, symbol: str, quantity: int, side: str) -> Optional[Dict[str, Any]]:
        """Place a market order"""
        try:
            # Create order request
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            
            # Submit order
            order = self.trading_client.submit_order(order_data)
            
            # Wait for order to be processed
            order_status = self.trading_client.get_order_by_id(order.id)
            
            order_info = {
                'order_id': order.id,
                'symbol': order.symbol,
                'quantity': int(order.qty),
                'side': order.side,
                'type': order.type,
                'status': order.status,
                'filled_at': order.filled_at.isoformat() if order.filled_at else None,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                'created_at': order.created_at.isoformat(),
                'commission': float(order.commission) if order.commission else 0.0
            }
            
            logger.info(f"📋 Market order placed: {symbol} {quantity} shares {side} @ ${order_info.get('filled_avg_price', 'market')}")
            
            return order_info
            
        except Exception as e:
            logger.error(f"❌ Error placing market order: {e}")
            return None
    
    def place_limit_order(self, symbol: str, quantity: int, side: str, limit_price: float) -> Optional[Dict[str, Any]]:
        """Place a limit order"""
        try:
            # Round limit price to nearest cent to prevent sub-penny errors
            rounded_limit_price = round(limit_price, 2)
            
            # Create order request
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=rounded_limit_price
            )
            
            # Submit order
            order = self.trading_client.submit_order(order_data)
            
            order_info = {
                'order_id': order.id,
                'symbol': order.symbol,
                'quantity': int(order.qty),
                'side': order.side,
                'type': order.type,
                'status': order.status,
                'limit_price': float(order.limit_price),
                'created_at': order.created_at.isoformat()
            }
            
            logger.info(f"📋 Limit order placed: {symbol} {quantity} shares {side} @ ${rounded_limit_price:.2f}")
            
            return order_info
            
        except Exception as e:
            logger.error(f"❌ Error placing limit order: {e}")
            return None
    
    def place_stop_order(self, symbol: str, quantity: int, stop_price: float) -> Optional[Dict[str, Any]]:
        """Place a stop order"""
        try:
            # Round stop price to nearest cent to prevent sub-penny errors
            rounded_stop_price = round(stop_price, 2)
            
            # Create order request
            order_data = StopOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.SELL,  # Stop orders are typically sell orders
                time_in_force=TimeInForce.DAY,
                stop_price=rounded_stop_price
            )
            
            # Submit order
            order = self.trading_client.submit_order(order_data)
            
            order_info = {
                'order_id': order.id,
                'symbol': order.symbol,
                'quantity': int(order.qty),
                'side': order.side,
                'type': order.type,
                'status': order.status,
                'stop_price': float(order.stop_price),
                'created_at': order.created_at.isoformat()
            }
            
            logger.info(f"📋 Stop order placed: {symbol} {quantity} shares @ ${rounded_stop_price:.2f}")
            
            return order_info
            
        except Exception as e:
            logger.error(f"❌ Error placing stop order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"❌ Cancelled order: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status"""
        try:
            order = self.trading_client.get_order_by_id(order_id)
            
            return {
                'order_id': order.id,
                'symbol': order.symbol,
                'quantity': int(order.qty),
                'side': order.side,
                'type': order.type,
                'status': order.status,
                'filled_at': order.filled_at.isoformat() if order.filled_at else None,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                'created_at': order.created_at.isoformat(),
                'commission': float(order.commission) if order.commission else 0.0
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting order status: {e}")
            return None
    
    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders"""
        try:
            orders = self.trading_client.get_orders()
            pending_orders = []
            
            for order in orders:
                if order.status in ['new', 'partially_filled']:
                    order_info = {
                        'order_id': order.id,
                        'symbol': order.symbol,
                        'quantity': int(order.qty),
                        'side': order.side,
                        'type': order.type,
                        'status': order.status,
                        'created_at': order.created_at.isoformat()
                    }
                    
                    if hasattr(order, 'limit_price') and order.limit_price:
                        order_info['limit_price'] = float(order.limit_price)
                    if hasattr(order, 'stop_price') and order.stop_price:
                        order_info['stop_price'] = float(order.stop_price)
                    
                    pending_orders.append(order_info)
            
            return pending_orders
            
        except Exception as e:
            logger.error(f"❌ Error getting pending orders: {e}")
            return []
    
    def get_recent_trades(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trades for a symbol"""
        try:
            # Get recent bars data
            request_params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute(1),
                start=datetime.now(timezone.utc).replace(hour=9, minute=30, second=0, microsecond=0),
                end=datetime.now(timezone.utc)
            )
            
            bars = self.data_client.get_stock_bars(request_params)
            
            trades = []
            for bar in bars[symbol]:
                trades.append({
                    'timestamp': bar.timestamp.isoformat(),
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume)
                })
            
            return trades[-limit:] if len(trades) > limit else trades
            
        except Exception as e:
            logger.error(f"❌ Error getting recent trades: {e}")
            return []
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
            
        except Exception as e:
            logger.error(f"❌ Error checking market status: {e}")
            return False
    
    def get_market_status(self) -> Dict[str, Any]:
        """Get market status information"""
        try:
            clock = self.trading_client.get_clock()
            
            return {
                'is_open': clock.is_open,
                'next_open': clock.next_open.isoformat() if clock.next_open else None,
                'next_close': clock.next_close.isoformat() if clock.next_close else None,
                'timestamp': clock.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting market status: {e}")
            return {'is_open': False}

# Global Alpaca client instance
alpaca_client = AlpacaClient() 