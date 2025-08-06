"""
DAS Trading Platform Client
Adapter for DAS Trading platform with Centerpoint Securities
Note: DAS uses TCP-based CMD API for order placement (not REST API)
Requires: DAS Trader Pro running on same machine
"""

import sys
import os
import time
import socket
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config

logger = get_logger(__name__)

class DASClient:
    """DAS Trading Platform Client using TCP CMD API"""
    
    def __init__(self):
        # DAS Configuration
        self.das_host = "localhost"  # DAS Trader Pro runs locally
        self.das_port = 8080  # Default DAS CMD API port
        self.is_connected = False
        self.socket = None
        
        # Order tracking
        self.orders = {}
        self.positions = {}
        self.order_callbacks = []
        
        # Threading for async operations
        self.response_thread = None
        self.response_queue = {}
        
        # Initialize connection
        self._init_connection()
    
    def _init_connection(self):
        """Initialize DAS TCP connection"""
        try:
            # Connect to DAS Trader Pro via TCP
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.das_host, self.das_port))
            self.is_connected = True
            
            # Start response listener thread
            self.response_thread = threading.Thread(target=self._listen_for_responses)
            self.response_thread.daemon = True
            self.response_thread.start()
            
            logger.info("✅ DAS TCP connection established")
            logger.info("📡 Connected to DAS Trader Pro via CMD API")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error connecting to DAS: {e}")
            logger.error("⚠️ Make sure DAS Trader Pro is running on localhost:8080")
            self.is_connected = False
            return False
    
    def _listen_for_responses(self):
        """Listen for responses from DAS Trader Pro"""
        try:
            while self.is_connected:
                try:
                    # Receive data from DAS
                    data = self.socket.recv(4096)
                    if data:
                        response = data.decode('utf-8')
                        self._process_das_response(response)
                except Exception as e:
                    if self.is_connected:
                        logger.error(f"❌ Error receiving DAS response: {e}")
                        break
        except Exception as e:
            logger.error(f"❌ DAS response listener error: {e}")
    
    def _process_das_response(self, response: str):
        """Process response from DAS Trader Pro"""
        try:
            # Parse DAS response format
            lines = response.strip().split('\n')
            
            for line in lines:
                if line.startswith('ORDER_UPDATE'):
                    self._process_order_update(line)
                elif line.startswith('FILL_UPDATE'):
                    self._process_fill_update(line)
                elif line.startswith('POSITION_UPDATE'):
                    self._process_position_update(line)
                elif line.startswith('ACCOUNT_UPDATE'):
                    self._process_account_update(line)
                elif line.startswith('ERROR'):
                    self._process_error(line)
                else:
                    # Store response for request matching
                    self._store_response(line)
            
        except Exception as e:
            logger.error(f"❌ Error processing DAS response: {e}")
    
    def _process_order_update(self, line: str):
        """Process order update from DAS"""
        try:
            # Parse DAS order update format
            # Example: ORDER_UPDATE|order_id|symbol|side|quantity|status|filled_qty|avg_price
            parts = line.split('|')
            if len(parts) >= 8:
                order_data = {
                    'order_id': parts[1],
                    'symbol': parts[2],
                    'side': parts[3],
                    'quantity': int(parts[4]),
                    'status': parts[5],
                    'filled_qty': int(parts[6]),
                    'avg_price': float(parts[7]) if parts[7] != 'N/A' else None,
                    'timestamp': datetime.now().isoformat(),
                    'event': 'order_update'
                }
                
                self.orders[order_data['order_id']] = order_data
                logger.info(f"📊 DAS Order Update: {order_data['symbol']} {order_data['side']} {order_data['status']}")
                
                # Notify callbacks
                for callback in self.order_callbacks:
                    try:
                        callback(order_data)
                    except Exception as e:
                        logger.error(f"❌ Error in order callback: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing order update: {e}")
    
    def _process_fill_update(self, line: str):
        """Process fill update from DAS"""
        try:
            # Parse DAS fill update format
            # Example: FILL_UPDATE|order_id|symbol|side|quantity|price|timestamp
            parts = line.split('|')
            if len(parts) >= 7:
                fill_data = {
                    'order_id': parts[1],
                    'symbol': parts[2],
                    'side': parts[3],
                    'quantity': int(parts[4]),
                    'price': float(parts[5]),
                    'timestamp': parts[6],
                    'event': 'fill'
                }
                
                logger.info(f"💰 DAS Fill: {fill_data['symbol']} {fill_data['side']} {fill_data['quantity']} @ ${fill_data['price']}")
                
                # Notify callbacks
                for callback in self.order_callbacks:
                    try:
                        callback(fill_data)
                    except Exception as e:
                        logger.error(f"❌ Error in fill callback: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing fill update: {e}")
    
    def _process_position_update(self, line: str):
        """Process position update from DAS"""
        try:
            # Parse DAS position update format
            # Example: POSITION_UPDATE|symbol|quantity|avg_price|market_value|unrealized_pl
            parts = line.split('|')
            if len(parts) >= 6:
                position_data = {
                    'symbol': parts[1],
                    'quantity': int(parts[2]),
                    'avg_price': float(parts[3]),
                    'market_value': float(parts[4]),
                    'unrealized_pl': float(parts[5]),
                    'timestamp': datetime.now().isoformat(),
                    'event': 'position_update'
                }
                
                self.positions[position_data['symbol']] = position_data
                logger.info(f"📈 DAS Position Update: {position_data['symbol']} Qty: {position_data['quantity']} P&L: ${position_data['unrealized_pl']}")
            
        except Exception as e:
            logger.error(f"❌ Error processing position update: {e}")
    
    def _process_account_update(self, line: str):
        """Process account update from DAS"""
        try:
            # Parse DAS account update format
            # Example: ACCOUNT_UPDATE|cash|buying_power|equity|daytrade_count
            parts = line.split('|')
            if len(parts) >= 5:
                account_data = {
                    'cash': float(parts[1]),
                    'buying_power': float(parts[2]),
                    'equity': float(parts[3]),
                    'daytrade_count': int(parts[4]),
                    'timestamp': datetime.now().isoformat(),
                    'event': 'account_update'
                }
                
                logger.info(f"💵 DAS Account Update: Cash: ${account_data['cash']} BP: ${account_data['buying_power']}")
            
        except Exception as e:
            logger.error(f"❌ Error processing account update: {e}")
    
    def _process_error(self, line: str):
        """Process error from DAS"""
        try:
            # Parse DAS error format
            # Example: ERROR|error_code|error_message
            parts = line.split('|')
            if len(parts) >= 3:
                error_code = parts[1]
                error_message = parts[2]
                logger.error(f"❌ DAS Error {error_code}: {error_message}")
            
        except Exception as e:
            logger.error(f"❌ Error processing DAS error: {e}")
    
    def _store_response(self, response: str):
        """Store response for request matching"""
        try:
            # Store response for async request handling
            self.response_queue[response] = datetime.now()
        except Exception as e:
            logger.error(f"❌ Error storing response: {e}")
    
    def _send_command(self, command: str) -> bool:
        """Send command to DAS Trader Pro"""
        try:
            if not self.is_connected or not self.socket:
                logger.error("❌ Not connected to DAS")
                return False
            
            # Send command via TCP
            self.socket.send(command.encode('utf-8'))
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending command to DAS: {e}")
            return False
    
    def add_order_callback(self, callback):
        """Add callback for order updates"""
        self.order_callbacks.append(callback)
    
    def place_market_order(self, symbol: str, quantity: int, side: str) -> Optional[Dict[str, Any]]:
        """Place a market order via DAS CMD API"""
        try:
            # DAS CMD format for market order
            # Format: PLACE_ORDER|symbol|quantity|side|order_type|time_in_force
            command = f"PLACE_ORDER|{symbol}|{quantity}|{side.lower()}|market|day"
            
            if self._send_command(command):
                order_info = {
                    'symbol': symbol,
                    'quantity': quantity,
                    'side': side,
                    'type': 'market',
                    'status': 'submitted',
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"📋 DAS market order sent: {symbol} {quantity} shares {side}")
                return order_info
            else:
                logger.error("❌ Failed to send market order to DAS")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error placing market order: {e}")
            return None
    
    def place_limit_order(self, symbol: str, quantity: int, side: str, limit_price: float) -> Optional[Dict[str, Any]]:
        """Place a limit order via DAS CMD API"""
        try:
            # DAS CMD format for limit order
            # Format: PLACE_ORDER|symbol|quantity|side|order_type|limit_price|time_in_force
            command = f"PLACE_ORDER|{symbol}|{quantity}|{side.lower()}|limit|{limit_price}|day"
            
            if self._send_command(command):
                order_info = {
                    'symbol': symbol,
                    'quantity': quantity,
                    'side': side,
                    'type': 'limit',
                    'limit_price': limit_price,
                    'status': 'submitted',
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"📋 DAS limit order sent: {symbol} {quantity} shares {side} @ ${limit_price}")
                return order_info
            else:
                logger.error("❌ Failed to send limit order to DAS")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error placing limit order: {e}")
            return None
    
    def place_stop_order(self, symbol: str, quantity: int, stop_price: float) -> Optional[Dict[str, Any]]:
        """Place a stop order via DAS CMD API"""
        try:
            # DAS CMD format for stop order
            # Format: PLACE_ORDER|symbol|quantity|sell|order_type|stop_price|time_in_force
            command = f"PLACE_ORDER|{symbol}|{quantity}|sell|stop|{stop_price}|day"
            
            if self._send_command(command):
                order_info = {
                    'symbol': symbol,
                    'quantity': quantity,
                    'side': 'sell',
                    'type': 'stop',
                    'stop_price': stop_price,
                    'status': 'submitted',
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"📋 DAS stop order sent: {symbol} {quantity} shares @ ${stop_price}")
                return order_info
            else:
                logger.error("❌ Failed to send stop order to DAS")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error placing stop order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order via DAS CMD API"""
        try:
            # DAS CMD format for cancel order
            # Format: CANCEL_ORDER|order_id
            command = f"CANCEL_ORDER|{order_id}"
            
            if self._send_command(command):
                logger.info(f"❌ DAS cancel order sent: {order_id}")
                return True
            else:
                logger.error("❌ Failed to send cancel order to DAS")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status from DAS (from local cache)"""
        try:
            # Return cached order status
            return self.orders.get(order_id)
            
        except Exception as e:
            logger.error(f"❌ Error getting order status: {e}")
            return None
    
    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions from DAS (from local cache)"""
        try:
            # Return cached positions
            return self.positions
            
        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
            return {}
    
    def get_pending_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get pending orders from DAS (from local cache)"""
        try:
            # Return cached pending orders
            pending_orders = {}
            for order_id, order_data in self.orders.items():
                if order_data.get('status') in ['submitted', 'pending', 'partial']:
                    pending_orders[order_id] = order_data
            
            return pending_orders
            
        except Exception as e:
            logger.error(f"❌ Error getting pending orders: {e}")
            return {}
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information from DAS"""
        try:
            # DAS CMD format for account info
            # Format: GET_ACCOUNT_INFO
            command = "GET_ACCOUNT_INFO"
            
            if self._send_command(command):
                # Account info will be received via response listener
                return {
                    'status': 'requested',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.error("❌ Failed to request account info from DAS")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Error getting account info: {e}")
            return {}
    
    def is_market_open(self) -> bool:
        """Check if market is open via DAS"""
        try:
            # DAS CMD format for market status
            # Format: GET_MARKET_STATUS
            command = "GET_MARKET_STATUS"
            
            if self._send_command(command):
                # Market status will be received via response listener
                return True  # Assume open for now
            else:
                logger.error("❌ Failed to request market status from DAS")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking market status: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from DAS"""
        try:
            self.is_connected = False
            if self.socket:
                self.socket.close()
                logger.info("🔌 DAS TCP connection closed")
        except Exception as e:
            logger.error(f"❌ Error disconnecting from DAS: {e}")

# Global DAS client instance
das_client = DASClient() 