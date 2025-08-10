#!/usr/bin/env python3
"""
DAS Trader FIX API Client
Implements FIX (Financial Information eXchange) protocol for DAS Trader
FIX is the industry standard protocol for electronic trading
"""

import os
import sys
import time
import socket
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config

logger = get_logger(__name__)

class FIXMessageType(Enum):
    """FIX message types"""
    LOGON = "A"
    LOGOUT = "5"
    HEARTBEAT = "0"
    TEST_REQUEST = "1"
    RESEND_REQUEST = "2"
    REJECT = "3"
    SEQUENCE_RESET = "4"
    NEW_ORDER_SINGLE = "D"
    ORDER_CANCEL_REQUEST = "F"
    ORDER_CANCEL_REPLACE_REQUEST = "G"
    ORDER_STATUS_REQUEST = "H"
    EXECUTION_REPORT = "8"
    ORDER_CANCEL_REJECT = "9"
    BUSINESS_MESSAGE_REJECT = "j"

class FIXTag(Enum):
    """FIX field tags"""
    BEGIN_STRING = "8"
    BODY_LENGTH = "9"
    MSG_TYPE = "35"
    SENDER_COMP_ID = "49"
    TARGET_COMP_ID = "56"
    MSG_SEQ_NUM = "34"
    SENDING_TIME = "52"
    CHECK_SUM = "10"
    
    # Logon fields
    ENCRYPT_METHOD = "98"
    HEART_BT_INT = "108"
    RESET_SEQ_NUM_FLAG = "141"
    
    # Order fields
    CL_ORD_ID = "11"
    HANDL_INST = "21"
    SYMBOL = "55"
    SIDE = "54"
    TRANSACT_TIME = "60"
    ORDER_QTY = "38"
    ORD_TYPE = "40"
    TIME_IN_FORCE = "59"
    PRICE = "44"
    STOP_PX = "99"
    
    # Execution fields
    ORDER_ID = "37"
    EXEC_ID = "17"
    EXEC_TYPE = "150"
    EXEC_STATUS = "39"
    LEAVES_QTY = "151"
    CUM_QTY = "14"
    AVG_PX = "6"
    LAST_QTY = "32"
    LAST_PX = "31"
    
    # Account fields
    ACCOUNT = "1"
    
    # Reject fields
    REF_SEQ_NUM = "45"
    REF_TAG_ID = "371"
    REF_MSG_TYPE = "372"
    TEXT = "58"

class FIXSide(Enum):
    """FIX order side"""
    BUY = "1"
    SELL = "2"

class FIXOrderType(Enum):
    """FIX order types"""
    MARKET = "1"
    LIMIT = "2"
    STOP = "3"
    STOP_LIMIT = "4"

class FIXTimeInForce(Enum):
    """FIX time in force"""
    DAY = "0"
    GTC = "1"
    IOC = "3"
    FOK = "4"

class FIXHandlingInstruction(Enum):
    """FIX handling instructions"""
    AUTOMATED_EXECUTION_ORDER_PRIVATE = "1"
    AUTOMATED_EXECUTION_ORDER_PUBLIC = "2"
    MANUAL_ORDER = "3"

class DASFIXClient:
    """DAS Trader FIX API Client"""
    
    def __init__(self, 
                 sender_comp_id: str = "TRADINGBOT",
                 target_comp_id: str = "DAS",
                 fix_host: str = "localhost",
                 fix_port: int = 5001,
                 username: str = "",
                 password: str = ""):
        
        # FIX Configuration
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.fix_host = fix_host
        self.fix_port = fix_port
        self.username = username
        self.password = password
        
        # Connection state
        self.socket = None
        self.is_connected = False
        self.is_logged_on = False
        
        # FIX session management
        self.msg_seq_num = 1
        self.incoming_seq_num = 1
        self.heartbeat_interval = 30  # seconds
        self.last_heartbeat = time.time()
        
        # Order tracking
        self.orders = {}
        self.executions = {}
        self.positions = {}
        
        # Callbacks
        self.order_callbacks = []
        self.execution_callbacks = []
        self.position_callbacks = []
        
        # Threading
        self.response_thread = None
        self.heartbeat_thread = None
        self.response_queue = queue.Queue()
        
        # Initialize connection
        self._init_connection()
    
    def _init_connection(self):
        """Initialize FIX connection to DAS Trader"""
        try:
            # Connect to DAS FIX server
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.fix_host, self.fix_port))
            self.is_connected = True
            
            # Start response listener thread
            self.response_thread = threading.Thread(target=self._listen_for_responses)
            self.response_thread.daemon = True
            self.response_thread.start()
            
            # Start heartbeat thread
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
            self.heartbeat_thread.daemon = True
            self.heartbeat_thread.start()
            
            logger.info(f"✅ FIX connection established to {self.fix_host}:{self.fix_port}")
            
            # Send logon message
            self._send_logon()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error connecting to DAS FIX: {e}")
            self.is_connected = False
            return False
    
    def _send_logon(self):
        """Send FIX logon message"""
        try:
            logon_msg = self._create_fix_message(
                msg_type=FIXMessageType.LOGON,
                fields={
                    FIXTag.ENCRYPT_METHOD: "0",  # None
                    FIXTag.HEART_BT_INT: str(self.heartbeat_interval),
                    FIXTag.RESET_SEQ_NUM_FLAG: "Y",
                    FIXTag.USERNAME: self.username,
                    FIXTag.PASSWORD: self.password
                }
            )
            
            self._send_fix_message(logon_msg)
            logger.info("📤 FIX Logon message sent")
            
        except Exception as e:
            logger.error(f"❌ Error sending logon: {e}")
    
    def _create_fix_message(self, msg_type: FIXMessageType, fields: Dict[FIXTag, str]) -> str:
        """Create a FIX message"""
        try:
            # Start with message type
            msg_parts = [f"{FIXTag.MSG_TYPE.value}={msg_type.value}"]
            
            # Add all fields
            for tag, value in fields.items():
                msg_parts.append(f"{tag.value}={value}")
            
            # Add standard header fields
            msg_parts.insert(0, f"{FIXTag.BEGIN_STRING.value}=FIX.4.2")
            msg_parts.insert(1, f"{FIXTag.SENDER_COMP_ID.value}={self.sender_comp_id}")
            msg_parts.insert(2, f"{FIXTag.TARGET_COMP_ID.value}={self.target_comp_id}")
            msg_parts.insert(3, f"{FIXTag.MSG_SEQ_NUM.value}={self.msg_seq_num}")
            msg_parts.insert(4, f"{FIXTag.SENDING_TIME.value}={datetime.now().strftime('%Y%m%d-%H:%M:%S.%f')[:-3]}")
            
            # Join message parts
            message = "|".join(msg_parts)
            
            # Calculate body length (everything between body length and checksum)
            body_length = len("|".join(msg_parts[2:]))  # Exclude begin string and body length
            msg_parts.insert(1, f"{FIXTag.BODY_LENGTH.value}={body_length}")
            
            # Rejoin and calculate checksum
            message = "|".join(msg_parts)
            checksum = sum(ord(c) for c in message) % 256
            message += f"|{FIXTag.CHECK_SUM.value}={checksum:03d}"
            
            # Increment sequence number
            self.msg_seq_num += 1
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error creating FIX message: {e}")
            return ""
    
    def _send_fix_message(self, message: str) -> bool:
        """Send FIX message to DAS Trader"""
        try:
            if not self.is_connected or not self.socket:
                logger.error("❌ Not connected to DAS FIX")
                return False
            
            # Add SOH (Start of Header) character
            message += chr(1)
            
            # Send message
            self.socket.send(message.encode('utf-8'))
            logger.debug(f"📤 FIX Message sent: {message}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending FIX message: {e}")
            return False
    
    def _listen_for_responses(self):
        """Listen for FIX responses from DAS Trader"""
        try:
            buffer = ""
            while self.is_connected:
                try:
                    # Receive data
                    data = self.socket.recv(4096)
                    if data:
                        buffer += data.decode('utf-8')
                        
                        # Process complete messages (separated by SOH)
                        while chr(1) in buffer:
                            message, buffer = buffer.split(chr(1), 1)
                            if message.strip():
                                self._process_fix_message(message.strip())
                except Exception as e:
                    if self.is_connected:
                        logger.error(f"❌ Error receiving FIX response: {e}")
                        break
        except Exception as e:
            logger.error(f"❌ FIX response listener error: {e}")
    
    def _process_fix_message(self, message: str):
        """Process incoming FIX message"""
        try:
            # Parse FIX message
            fields = {}
            for field in message.split('|'):
                if '=' in field:
                    tag, value = field.split('=', 1)
                    fields[tag] = value
            
            # Get message type
            msg_type = fields.get('35', '')
            
            logger.debug(f"📥 FIX Message received: {msg_type}")
            
            # Process based on message type
            if msg_type == FIXMessageType.LOGON.value:
                self._process_logon(fields)
            elif msg_type == FIXMessageType.LOGOUT.value:
                self._process_logout(fields)
            elif msg_type == FIXMessageType.HEARTBEAT.value:
                self._process_heartbeat(fields)
            elif msg_type == FIXMessageType.EXECUTION_REPORT.value:
                self._process_execution_report(fields)
            elif msg_type == FIXMessageType.ORDER_CANCEL_REJECT.value:
                self._process_order_cancel_reject(fields)
            elif msg_type == FIXMessageType.BUSINESS_MESSAGE_REJECT.value:
                self._process_business_reject(fields)
            elif msg_type == FIXMessageType.TEST_REQUEST.value:
                self._process_test_request(fields)
            else:
                logger.debug(f"📥 Unhandled FIX message type: {msg_type}")
            
        except Exception as e:
            logger.error(f"❌ Error processing FIX message: {e}")
    
    def _process_logon(self, fields: Dict[str, str]):
        """Process logon response"""
        try:
            self.is_logged_on = True
            logger.info("✅ FIX Logon successful")
            
            # Reset sequence numbers if requested
            if fields.get('141') == 'Y':
                self.msg_seq_num = 1
                self.incoming_seq_num = 1
            
        except Exception as e:
            logger.error(f"❌ Error processing logon: {e}")
    
    def _process_logout(self, fields: Dict[str, str]):
        """Process logout response"""
        try:
            self.is_logged_on = False
            text = fields.get('58', 'No reason provided')
            logger.warning(f"⚠️ FIX Logout: {text}")
            
        except Exception as e:
            logger.error(f"❌ Error processing logout: {e}")
    
    def _process_heartbeat(self, fields: Dict[str, str]):
        """Process heartbeat"""
        try:
            self.last_heartbeat = time.time()
            logger.debug("💓 FIX Heartbeat received")
            
        except Exception as e:
            logger.error(f"❌ Error processing heartbeat: {e}")
    
    def _process_execution_report(self, fields: Dict[str, str]):
        """Process execution report"""
        try:
            # Extract order information
            order_id = fields.get('37', '')
            cl_ord_id = fields.get('11', '')
            symbol = fields.get('55', '')
            side = fields.get('54', '')
            exec_type = fields.get('150', '')
            exec_status = fields.get('39', '')
            
            # Extract quantities and prices
            order_qty = float(fields.get('38', '0'))
            cum_qty = float(fields.get('14', '0'))
            leaves_qty = float(fields.get('151', '0'))
            avg_px = float(fields.get('6', '0'))
            last_qty = float(fields.get('32', '0'))
            last_px = float(fields.get('31', '0'))
            
            # Create execution data
            execution_data = {
                'order_id': order_id,
                'cl_ord_id': cl_ord_id,
                'symbol': symbol,
                'side': side,
                'exec_type': exec_type,
                'exec_status': exec_status,
                'order_qty': order_qty,
                'cum_qty': cum_qty,
                'leaves_qty': leaves_qty,
                'avg_px': avg_px,
                'last_qty': last_qty,
                'last_px': last_px,
                'timestamp': datetime.now().isoformat()
            }
            
            # Update order tracking
            if cl_ord_id in self.orders:
                self.orders[cl_ord_id].update(execution_data)
            
            # Log execution
            if exec_type == '0':  # New order
                logger.info(f"📋 FIX Order New: {symbol} {side} {order_qty} shares")
            elif exec_type == '1':  # Partial fill
                logger.info(f"💰 FIX Partial Fill: {symbol} {last_qty} @ ${last_px}")
            elif exec_type == '2':  # Fill
                logger.info(f"💰 FIX Fill: {symbol} {last_qty} @ ${last_px}")
            elif exec_type == '4':  # Canceled
                logger.info(f"❌ FIX Order Canceled: {symbol}")
            elif exec_type == '5':  # Replaced
                logger.info(f"🔄 FIX Order Replaced: {symbol}")
            
            # Notify callbacks
            for callback in self.execution_callbacks:
                try:
                    callback(execution_data)
                except Exception as e:
                    logger.error(f"❌ Error in execution callback: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing execution report: {e}")
    
    def _process_order_cancel_reject(self, fields: Dict[str, str]):
        """Process order cancel reject"""
        try:
            cl_ord_id = fields.get('11', '')
            order_id = fields.get('37', '')
            cxl_rej_reason = fields.get('102', '')
            text = fields.get('58', '')
            
            logger.error(f"❌ FIX Order Cancel Rejected: {cl_ord_id} - {cxl_rej_reason}: {text}")
            
        except Exception as e:
            logger.error(f"❌ Error processing order cancel reject: {e}")
    
    def _process_business_reject(self, fields: Dict[str, str]):
        """Process business message reject"""
        try:
            ref_seq_num = fields.get('45', '')
            ref_msg_type = fields.get('372', '')
            business_reject_reason = fields.get('380', '')
            text = fields.get('58', '')
            
            logger.error(f"❌ FIX Business Reject: {ref_msg_type} - {business_reject_reason}: {text}")
            
        except Exception as e:
            logger.error(f"❌ Error processing business reject: {e}")
    
    def _process_test_request(self, fields: Dict[str, str]):
        """Process test request"""
        try:
            test_req_id = fields.get('112', '')
            
            # Send heartbeat in response
            heartbeat_msg = self._create_fix_message(
                msg_type=FIXMessageType.HEARTBEAT,
                fields={FIXTag.TEST_REQ_ID: test_req_id}
            )
            
            self._send_fix_message(heartbeat_msg)
            logger.debug(f"💓 FIX Test request response sent: {test_req_id}")
            
        except Exception as e:
            logger.error(f"❌ Error processing test request: {e}")
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        try:
            while self.is_connected and self.is_logged_on:
                time.sleep(self.heartbeat_interval)
                
                if time.time() - self.last_heartbeat > self.heartbeat_interval * 2:
                    # Send heartbeat
                    heartbeat_msg = self._create_fix_message(
                        msg_type=FIXMessageType.HEARTBEAT,
                        fields={}
                    )
                    
                    self._send_fix_message(heartbeat_msg)
                    logger.debug("💓 FIX Heartbeat sent")
                    
        except Exception as e:
            logger.error(f"❌ Error in heartbeat loop: {e}")
    
    def add_execution_callback(self, callback: Callable):
        """Add callback for execution reports"""
        self.execution_callbacks.append(callback)
    
    def place_market_order(self, symbol: str, quantity: int, side: str, account: str = "") -> Optional[Dict[str, Any]]:
        """Place a market order via FIX API"""
        try:
            if not self.is_logged_on:
                logger.error("❌ Not logged on to FIX")
                return None
            
            # Create client order ID
            cl_ord_id = f"ORDER_{int(time.time() * 1000)}"
            
            # Create FIX order message
            order_msg = self._create_fix_message(
                msg_type=FIXMessageType.NEW_ORDER_SINGLE,
                fields={
                    FIXTag.CL_ORD_ID: cl_ord_id,
                    FIXTag.HANDL_INST: FIXHandlingInstruction.AUTOMATED_EXECUTION_ORDER_PRIVATE.value,
                    FIXTag.SYMBOL: symbol,
                    FIXTag.SIDE: FIXSide.BUY.value if side.upper() == 'BUY' else FIXSide.SELL.value,
                    FIXTag.TRANSACT_TIME: datetime.now().strftime('%Y%m%d-%H:%M:%S.%f')[:-3],
                    FIXTag.ORDER_QTY: str(quantity),
                    FIXTag.ORD_TYPE: FIXOrderType.MARKET.value,
                    FIXTag.TIME_IN_FORCE: FIXTimeInForce.DAY.value,
                    FIXTag.ACCOUNT: account
                }
            )
            
            if self._send_fix_message(order_msg):
                order_info = {
                    'cl_ord_id': cl_ord_id,
                    'symbol': symbol,
                    'quantity': quantity,
                    'side': side,
                    'type': 'market',
                    'status': 'submitted',
                    'created_at': datetime.now().isoformat()
                }
                
                # Track order
                self.orders[cl_ord_id] = order_info
                
                logger.info(f"📋 FIX market order sent: {symbol} {quantity} shares {side}")
                return order_info
            else:
                logger.error("❌ Failed to send FIX market order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error placing FIX market order: {e}")
            return None
    
    def place_limit_order(self, symbol: str, quantity: int, side: str, limit_price: float, account: str = "") -> Optional[Dict[str, Any]]:
        """Place a limit order via FIX API"""
        try:
            if not self.is_logged_on:
                logger.error("❌ Not logged on to FIX")
                return None
            
            # Create client order ID
            cl_ord_id = f"ORDER_{int(time.time() * 1000)}"
            
            # Create FIX order message
            order_msg = self._create_fix_message(
                msg_type=FIXMessageType.NEW_ORDER_SINGLE,
                fields={
                    FIXTag.CL_ORD_ID: cl_ord_id,
                    FIXTag.HANDL_INST: FIXHandlingInstruction.AUTOMATED_EXECUTION_ORDER_PRIVATE.value,
                    FIXTag.SYMBOL: symbol,
                    FIXTag.SIDE: FIXSide.BUY.value if side.upper() == 'BUY' else FIXSide.SELL.value,
                    FIXTag.TRANSACT_TIME: datetime.now().strftime('%Y%m%d-%H:%M:%S.%f')[:-3],
                    FIXTag.ORDER_QTY: str(quantity),
                    FIXTag.ORD_TYPE: FIXOrderType.LIMIT.value,
                    FIXTag.TIME_IN_FORCE: FIXTimeInForce.DAY.value,
                    FIXTag.PRICE: f"{limit_price:.2f}",
                    FIXTag.ACCOUNT: account
                }
            )
            
            if self._send_fix_message(order_msg):
                order_info = {
                    'cl_ord_id': cl_ord_id,
                    'symbol': symbol,
                    'quantity': quantity,
                    'side': side,
                    'type': 'limit',
                    'limit_price': limit_price,
                    'status': 'submitted',
                    'created_at': datetime.now().isoformat()
                }
                
                # Track order
                self.orders[cl_ord_id] = order_info
                
                logger.info(f"📋 FIX limit order sent: {symbol} {quantity} shares {side} @ ${limit_price}")
                return order_info
            else:
                logger.error("❌ Failed to send FIX limit order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error placing FIX limit order: {e}")
            return None
    
    def place_stop_order(self, symbol: str, quantity: int, stop_price: float, account: str = "") -> Optional[Dict[str, Any]]:
        """Place a stop order via FIX API"""
        try:
            if not self.is_logged_on:
                logger.error("❌ Not logged on to FIX")
                return None
            
            # Create client order ID
            cl_ord_id = f"ORDER_{int(time.time() * 1000)}"
            
            # Create FIX order message
            order_msg = self._create_fix_message(
                msg_type=FIXMessageType.NEW_ORDER_SINGLE,
                fields={
                    FIXTag.CL_ORD_ID: cl_ord_id,
                    FIXTag.HANDL_INST: FIXHandlingInstruction.AUTOMATED_EXECUTION_ORDER_PRIVATE.value,
                    FIXTag.SYMBOL: symbol,
                    FIXTag.SIDE: FIXSide.SELL.value,  # Stop orders are typically sell orders
                    FIXTag.TRANSACT_TIME: datetime.now().strftime('%Y%m%d-%H:%M:%S.%f')[:-3],
                    FIXTag.ORDER_QTY: str(quantity),
                    FIXTag.ORD_TYPE: FIXOrderType.STOP.value,
                    FIXTag.TIME_IN_FORCE: FIXTimeInForce.DAY.value,
                    FIXTag.STOP_PX: f"{stop_price:.2f}",
                    FIXTag.ACCOUNT: account
                }
            )
            
            if self._send_fix_message(order_msg):
                order_info = {
                    'cl_ord_id': cl_ord_id,
                    'symbol': symbol,
                    'quantity': quantity,
                    'side': 'sell',
                    'type': 'stop',
                    'stop_price': stop_price,
                    'status': 'submitted',
                    'created_at': datetime.now().isoformat()
                }
                
                # Track order
                self.orders[cl_ord_id] = order_info
                
                logger.info(f"📋 FIX stop order sent: {symbol} {quantity} shares @ ${stop_price}")
                return order_info
            else:
                logger.error("❌ Failed to send FIX stop order")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error placing FIX stop order: {e}")
            return None
    
    def cancel_order(self, cl_ord_id: str, symbol: str) -> bool:
        """Cancel an order via FIX API"""
        try:
            if not self.is_logged_on:
                logger.error("❌ Not logged on to FIX")
                return False
            
            # Create new client order ID for cancel
            cancel_cl_ord_id = f"CANCEL_{int(time.time() * 1000)}"
            
            # Create FIX cancel message
            cancel_msg = self._create_fix_message(
                msg_type=FIXMessageType.ORDER_CANCEL_REQUEST,
                fields={
                    FIXTag.ORIG_CL_ORD_ID: cl_ord_id,
                    FIXTag.CL_ORD_ID: cancel_cl_ord_id,
                    FIXTag.SYMBOL: symbol,
                    FIXTag.SIDE: FIXSide.BUY.value,  # Will be overridden by original order
                    FIXTag.TRANSACT_TIME: datetime.now().strftime('%Y%m%d-%H:%M:%S.%f')[:-3]
                }
            )
            
            if self._send_fix_message(cancel_msg):
                logger.info(f"❌ FIX cancel order sent: {cl_ord_id}")
                return True
            else:
                logger.error("❌ Failed to send FIX cancel order")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error cancelling FIX order: {e}")
            return False
    
    def get_order_status(self, cl_ord_id: str) -> Optional[Dict[str, Any]]:
        """Get order status via FIX API"""
        try:
            if not self.is_logged_on:
                logger.error("❌ Not logged on to FIX")
                return None
            
            # Create FIX order status request
            status_msg = self._create_fix_message(
                msg_type=FIXMessageType.ORDER_STATUS_REQUEST,
                fields={
                    FIXTag.CL_ORD_ID: cl_ord_id,
                    FIXTag.SYMBOL: self.orders.get(cl_ord_id, {}).get('symbol', ''),
                    FIXTag.SIDE: FIXSide.BUY.value  # Will be overridden by original order
                }
            )
            
            if self._send_fix_message(status_msg):
                logger.info(f"📊 FIX order status request sent: {cl_ord_id}")
                return self.orders.get(cl_ord_id)
            else:
                logger.error("❌ Failed to send FIX order status request")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting FIX order status: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from DAS FIX"""
        try:
            if self.is_logged_on:
                # Send logout message
                logout_msg = self._create_fix_message(
                    msg_type=FIXMessageType.LOGOUT,
                    fields={FIXTag.TEXT: "Trading bot shutdown"}
                )
                self._send_fix_message(logout_msg)
            
            self.is_connected = False
            self.is_logged_on = False
            
            if self.socket:
                self.socket.close()
            
            logger.info("🔌 FIX connection closed")
            
        except Exception as e:
            logger.error(f"❌ Error disconnecting FIX: {e}")

# Example usage
if __name__ == "__main__":
    # Create DAS FIX client
    das_client = DASFIXClient(
        sender_comp_id="TRADINGBOT",
        target_comp_id="DAS",
        fix_host="localhost",
        fix_port=5001,
        username="your_username",
        password="your_password"
    )
    
    try:
        # Wait for logon
        time.sleep(2)
        
        if das_client.is_logged_on:
            # Place a market order
            order = das_client.place_market_order("AAPL", 100, "BUY")
            print(f"Order placed: {order}")
            
            # Wait for execution
            time.sleep(5)
            
            # Get order status
            status = das_client.get_order_status(order['cl_ord_id'])
            print(f"Order status: {status}")
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        das_client.disconnect()
