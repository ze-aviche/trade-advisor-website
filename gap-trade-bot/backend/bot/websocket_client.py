"""
WebSocket Client for Real-time Data
Handles real-time price, volume, and market data via WebSocket
"""

import asyncio
import json
import websockets
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from config import config

logger = get_logger(__name__)

class WebSocketClient:
    """WebSocket client for real-time market data"""
    
    def __init__(self):
        self.websocket = None
        self.is_connected = False
        self.reconnect_count = 0
        self.subscribed_symbols = set()
        self.data_callbacks = []
        self.polygon_api_key = config.POLYGON_API_KEY
        
        # Real-time data storage
        self.price_data = {}
        self.volume_data = {}
        self.vwap_data = {}
        
    async def connect(self):
        """Connect to Polygon WebSocket"""
        try:
            # Polygon WebSocket URL
            ws_url = f"wss://delayed.polygon.io/stocks"
            
            logger.info(f"🔌 Connecting to Polygon WebSocket: {ws_url}")
            
            self.websocket = await websockets.connect(ws_url)
            self.is_connected = True
            self.reconnect_count = 0
            
            # Send authentication
            auth_message = {
                "action": "auth",
                "params": self.polygon_api_key
            }
            await self.websocket.send(json.dumps(auth_message))
            
            logger.info("✅ WebSocket connected successfully")
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            self.is_connected = False
    
    async def subscribe_to_symbols(self, symbols: List[str]):
        """Subscribe to real-time data for symbols"""
        try:
            if not self.is_connected:
                await self.connect()
            
            # Subscribe to T (trades) and A (second aggregates) for each symbol
            for symbol in symbols:
                subscribe_message = {
                    "action": "subscribe",
                    "params": f"T.{symbol},A.{symbol}"
                }
                await self.websocket.send(json.dumps(subscribe_message))
                self.subscribed_symbols.add(symbol)
                logger.info(f"📡 Subscribed to {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to symbols: {e}")
    
    async def unsubscribe_from_symbols(self, symbols: List[str]):
        """Unsubscribe from symbols"""
        try:
            for symbol in symbols:
                unsubscribe_message = {
                    "action": "unsubscribe",
                    "params": f"T.{symbol},A.{symbol}"
                }
                await self.websocket.send(json.dumps(unsubscribe_message))
                self.subscribed_symbols.discard(symbol)
                logger.info(f"📡 Unsubscribed from {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Error unsubscribing from symbols: {e}")
    
    def add_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for real-time data"""
        self.data_callbacks.append(callback)
    
    async def listen_for_data(self):
        """Listen for real-time data"""
        try:
            while self.is_connected:
                try:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    
                    # Process different message types
                    if 'ev' in data:  # Event type
                        await self._process_message(data)
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("⚠️ WebSocket connection closed")
                    await self._reconnect()
                except Exception as e:
                    logger.error(f"❌ Error processing WebSocket message: {e}")
                    
        except Exception as e:
            logger.error(f"❌ WebSocket listen error: {e}")
    
    async def _process_message(self, data: Dict[str, Any]):
        """Process incoming WebSocket message"""
        try:
            event_type = data.get('ev')
            
            if event_type == 'T':  # Trade
                await self._process_trade(data)
            elif event_type == 'A':  # Second aggregate
                await self._process_aggregate(data)
            elif event_type == 'status':
                logger.info(f"📊 WebSocket status: {data}")
            
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
    
    async def _process_trade(self, data: Dict[str, Any]):
        """Process trade data"""
        try:
            symbol = data.get('sym', '')
            price = data.get('p', 0)
            volume = data.get('s', 0)
            timestamp = data.get('t', 0)
            
            # Update price data
            if symbol not in self.price_data:
                self.price_data[symbol] = []
            
            trade_data = {
                'symbol': symbol,
                'price': price,
                'volume': volume,
                'timestamp': timestamp,
                'type': 'trade'
            }
            
            self.price_data[symbol].append(trade_data)
            
            # Keep only last 100 trades per symbol
            if len(self.price_data[symbol]) > 100:
                self.price_data[symbol] = self.price_data[symbol][-100:]
            
            # Notify callbacks
            for callback in self.data_callbacks:
                try:
                    callback(trade_data)
                except Exception as e:
                    logger.error(f"❌ Error in data callback: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing trade: {e}")
    
    async def _process_aggregate(self, data: Dict[str, Any]):
        """Process aggregate data"""
        try:
            symbol = data.get('sym', '')
            open_price = data.get('o', 0)
            high_price = data.get('h', 0)
            low_price = data.get('l', 0)
            close_price = data.get('c', 0)
            volume = data.get('v', 0)
            vwap = data.get('vw', 0)
            timestamp = data.get('t', 0)
            
            # Update aggregate data
            aggregate_data = {
                'symbol': symbol,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
                'vwap': vwap,
                'timestamp': timestamp,
                'type': 'aggregate'
            }
            
            self.vwap_data[symbol] = vwap
            
            # Notify callbacks
            for callback in self.data_callbacks:
                try:
                    callback(aggregate_data)
                except Exception as e:
                    logger.error(f"❌ Error in data callback: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing aggregate: {e}")
    
    async def _reconnect(self):
        """Reconnect to WebSocket"""
        try:
            if self.reconnect_count < config.WEBSOCKET_MAX_RECONNECTS:
                self.reconnect_count += 1
                logger.info(f"🔄 Attempting to reconnect ({self.reconnect_count}/{config.WEBSOCKET_MAX_RECONNECTS})")
                
                await asyncio.sleep(config.WEBSOCKET_RECONNECT_DELAY)
                await self.connect()
                
                # Resubscribe to symbols
                if self.subscribed_symbols:
                    await self.subscribe_to_symbols(list(self.subscribed_symbols))
                
            else:
                logger.error("❌ Max reconnection attempts reached")
                self.is_connected = False
                
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
            self.is_connected = False
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        if symbol in self.price_data and self.price_data[symbol]:
            return self.price_data[symbol][-1]['price']
        return None
    
    def get_current_vwap(self, symbol: str) -> Optional[float]:
        """Get current VWAP for a symbol"""
        return self.vwap_data.get(symbol)
    
    def get_price_history(self, symbol: str, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent price history for a symbol"""
        if symbol in self.price_data:
            return self.price_data[symbol][-count:]
        return []
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        try:
            if self.websocket:
                await self.websocket.close()
            self.is_connected = False
            logger.info("🔌 WebSocket disconnected")
        except Exception as e:
            logger.error(f"❌ Error disconnecting WebSocket: {e}")

# Global WebSocket client instance
websocket_client = WebSocketClient() 