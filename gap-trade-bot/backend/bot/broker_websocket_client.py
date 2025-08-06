"""
Broker WebSocket Client
Handles real-time order updates, fill notifications, and account updates via WebSocket
Note: Orders are placed via REST API, WebSocket provides real-time updates only
Currently supports: Alpaca WebSocket for order updates
DAS: Uses REST API only (no WebSocket support for order placement)
"""

import asyncio
import json
import websockets
import time
import ssl
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config

logger = get_logger(__name__)

class BrokerWebSocketClient:
    """WebSocket client for broker order updates and real-time notifications"""
    
    def __init__(self, broker_type: str = 'alpaca'):
        self.broker_type = broker_type
        self.websocket = None
        self.is_connected = False
        self.reconnect_count = 0
        self.order_callbacks = []
        self.fill_callbacks = []
        self.position_callbacks = []
        self.account_callbacks = []
        
        # Real-time data storage
        self.order_status = {}      # Order status updates
        self.fills = {}             # Fill notifications
        self.positions = {}         # Position updates
        self.account_updates = {}   # Account balance updates
        
        # Broker-specific configuration
        self._init_broker_config()
    
    def _init_broker_config(self):
        """Initialize broker-specific configuration"""
        if self.broker_type == 'alpaca':
            # Alpaca WebSocket URL for trade updates (not order placement)
            self.ws_url = "wss://paper-api.alpaca.markets/v2/iex" if bot_config.ALPACA_PAPER else "wss://api.alpaca.markets/v2/iex"
            self.api_key = bot_config.BROKER_API_KEY
            self.secret_key = bot_config.BROKER_SECRET
        elif self.broker_type == 'das':
            # DAS doesn't support WebSocket order placement
            logger.warning("⚠️ DAS doesn't support WebSocket order placement - using REST API only")
            self.ws_url = None
            self.api_key = None
            self.secret_key = None
        else:
            raise ValueError(f"Unsupported broker type: {self.broker_type}")
    
    async def connect(self):
        """Connect to broker WebSocket for real-time updates"""
        try:
            if self.broker_type == 'das':
                logger.warning("⚠️ DAS doesn't support WebSocket - using REST API only")
                return False
            
            logger.info(f"🔌 Connecting to {self.broker_type.upper()} WebSocket for trade updates: {self.ws_url}")
            
            # Create SSL context that handles certificate issues on macOS
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.websocket = await websockets.connect(self.ws_url, ssl=ssl_context)
            self.is_connected = True
            self.reconnect_count = 0
            
            # Send authentication
            if self.broker_type == 'alpaca':
                await self._alpaca_auth()
            
            logger.info(f"✅ {self.broker_type.upper()} WebSocket connected successfully")
            logger.info(f"📡 WebSocket will provide real-time order updates (orders placed via REST API)")
            
        except Exception as e:
            logger.error(f"❌ {self.broker_type.upper()} WebSocket connection failed: {e}")
            self.is_connected = False
    
    async def _alpaca_auth(self):
        """Authenticate with Alpaca WebSocket for trade updates"""
        auth_message = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.secret_key
        }
        await self.websocket.send(json.dumps(auth_message))
        
        # Wait for auth response
        response = await self.websocket.recv()
        auth_data = json.loads(response)
        
        if auth_data.get('T') == 'success':
            logger.info("✅ Alpaca WebSocket authenticated for trade updates")
        else:
            raise Exception(f"Alpaca authentication failed: {auth_data}")
    
    def add_order_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for order status updates"""
        self.order_callbacks.append(callback)
    
    def add_fill_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for fill notifications"""
        self.fill_callbacks.append(callback)
    
    def add_position_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for position updates"""
        self.position_callbacks.append(callback)
    
    def add_account_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for account updates"""
        self.account_callbacks.append(callback)
    
    async def listen_for_updates(self):
        """Listen for real-time broker updates (order status, fills, positions)"""
        try:
            if self.broker_type == 'das':
                logger.warning("⚠️ DAS doesn't support WebSocket - no real-time updates available")
                return
            
            while self.is_connected:
                try:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    
                    # Process different message types
                    await self._process_broker_message(data)
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"⚠️ {self.broker_type.upper()} WebSocket connection closed")
                    await self._reconnect()
                except Exception as e:
                    logger.error(f"❌ Error processing {self.broker_type.upper()} message: {e}")
                    
        except Exception as e:
            logger.error(f"❌ {self.broker_type.upper()} WebSocket listen error: {e}")
    
    async def _process_broker_message(self, data: Dict[str, Any]):
        """Process incoming broker WebSocket message"""
        try:
            if self.broker_type == 'alpaca':
                await self._process_alpaca_message(data)
            elif self.broker_type == 'das':
                logger.warning("⚠️ DAS doesn't support WebSocket messages")
            
        except Exception as e:
            logger.error(f"❌ Error processing broker message: {e}")
    
    async def _process_alpaca_message(self, data: Dict[str, Any]):
        """Process Alpaca WebSocket message (trade updates only)"""
        try:
            message_type = data.get('T')  # Alpaca message type
            
            if message_type == 'order_update':
                # Order status update (from REST API order)
                order_data = {
                    'order_id': data.get('i'),
                    'symbol': data.get('S'),
                    'side': data.get('s'),
                    'quantity': data.get('q'),
                    'filled_quantity': data.get('z'),
                    'status': data.get('X'),
                    'limit_price': data.get('l'),
                    'stop_price': data.get('p'),
                    'timestamp': data.get('t'),
                    'event': 'order_update'
                }
                
                self.order_status[order_data['order_id']] = order_data
                
                logger.info(f"📊 Order Update: {order_data['symbol']} {order_data['side']} {order_data['status']}")
                
                # Notify order callbacks
                for callback in self.order_callbacks:
                    try:
                        callback(order_data)
                    except Exception as e:
                        logger.error(f"❌ Error in order callback: {e}")
            
            elif message_type == 'fill':
                # Fill notification (from REST API order)
                fill_data = {
                    'order_id': data.get('i'),
                    'symbol': data.get('S'),
                    'side': data.get('s'),
                    'quantity': data.get('z'),
                    'price': data.get('p'),
                    'timestamp': data.get('t'),
                    'event': 'fill'
                }
                
                self.fills[fill_data['order_id']] = fill_data
                
                logger.info(f"💰 Fill: {fill_data['symbol']} {fill_data['side']} {fill_data['quantity']} @ ${fill_data['price']}")
                
                # Notify fill callbacks
                for callback in self.fill_callbacks:
                    try:
                        callback(fill_data)
                    except Exception as e:
                        logger.error(f"❌ Error in fill callback: {e}")
            
            elif message_type == 'position_update':
                # Position update
                position_data = {
                    'symbol': data.get('S'),
                    'quantity': data.get('q'),
                    'market_value': data.get('mv'),
                    'unrealized_pl': data.get('up'),
                    'timestamp': data.get('t'),
                    'event': 'position_update'
                }
                
                self.positions[position_data['symbol']] = position_data
                
                logger.info(f"📈 Position Update: {position_data['symbol']} Qty: {position_data['quantity']} P&L: ${position_data['unrealized_pl']}")
                
                # Notify position callbacks
                for callback in self.position_callbacks:
                    try:
                        callback(position_data)
                    except Exception as e:
                        logger.error(f"❌ Error in position callback: {e}")
            
            elif message_type == 'account_update':
                # Account update
                account_data = {
                    'cash': data.get('c'),
                    'buying_power': data.get('bp'),
                    'equity': data.get('e'),
                    'daytrade_count': data.get('dtc'),
                    'timestamp': data.get('t'),
                    'event': 'account_update'
                }
                
                self.account_updates = account_data
                
                logger.info(f"💵 Account Update: Cash: ${account_data['cash']} BP: ${account_data['buying_power']}")
                
                # Notify account callbacks
                for callback in self.account_callbacks:
                    try:
                        callback(account_data)
                    except Exception as e:
                        logger.error(f"❌ Error in account callback: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing Alpaca message: {e}")
    
    async def _reconnect(self):
        """Reconnect to broker WebSocket"""
        if self.broker_type == 'das':
            logger.warning("⚠️ DAS doesn't support WebSocket - no reconnection needed")
            return
        
        if self.reconnect_count < bot_config.WEBSOCKET_MAX_RECONNECTS:
            self.reconnect_count += 1
            logger.info(f"🔄 Attempting to reconnect to {self.broker_type.upper()} ({self.reconnect_count}/{bot_config.WEBSOCKET_MAX_RECONNECTS})")
            
            await asyncio.sleep(bot_config.WEBSOCKET_RECONNECT_DELAY)
            await self.connect()
            
        else:
            logger.error(f"❌ Max reconnection attempts reached for {self.broker_type.upper()}")
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get current order status from WebSocket cache"""
        return self.order_status.get(order_id)
    
    def get_fill_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get fill information for an order from WebSocket cache"""
        return self.fills.get(order_id)
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current position for a symbol from WebSocket cache"""
        return self.positions.get(symbol)
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get current account information from WebSocket cache"""
        return self.account_updates
    
    async def disconnect(self):
        """Disconnect from broker WebSocket"""
        try:
            if self.broker_type == 'das':
                logger.info("ℹ️ DAS doesn't use WebSocket - no disconnection needed")
                return
            
            if self.websocket:
                await self.websocket.close()
                self.is_connected = False
                logger.info(f"🔌 {self.broker_type.upper()} WebSocket disconnected")
        except Exception as e:
            logger.error(f"❌ Error disconnecting {self.broker_type.upper()} WebSocket: {e}")

# Global broker WebSocket client instances
alpaca_websocket = BrokerWebSocketClient('alpaca')
# Note: DAS doesn't support WebSocket - use REST API only 