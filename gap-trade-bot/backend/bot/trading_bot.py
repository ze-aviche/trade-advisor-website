#!/usr/bin/env python3
"""
Enhanced Trading Bot Module
Integrates position monitoring, DAS connection, and automated exit management
"""

import time
import logging
import threading
import socket
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Data class for position information"""
    symbol: str
    type: str  # "LONG" or "SHORT"
    size: int
    entry_price: float
    profit_target: float
    stop_loss: float
    entry_time: float
    position_id: str

@dataclass
class PriceData:
    """Data class for price information"""
    ask: float = 0.0
    bid: float = 0.0
    last: float = 0.0
    timestamp: float = 0.0

class DASConnection:
    """DAS Trader Connection Class"""
    
    def __init__(self):
        self.s = socket.socket()
        self.connected = False
        self.last_connection_attempt = 0
        self.connection_retry_interval = 5  # Retry every 5 seconds
    
    def ConnectToServer(self):
        """Connect to DAS server"""
        try:
            self.s.settimeout(2)
            self.s.connect(("127.0.0.1", 9800))
            time.sleep(0.1)
            
            # Login
            login_data = bytearray("LOGIN IDAS12181 Dastrader@2 TRIDAS12181\r\n", encoding="ascii")
            self.s.sendall(login_data)
            time.sleep(0.1)
            
            response = self.s.recv(1024*1024).decode("ascii")
            logger.info(f"DAS login response: {response}")
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to DAS: {e}")
            self.connected = False
            return False
    
    def try_reconnect(self):
        """Attempt to reconnect to DAS server"""
        current_time = time.time()
        
        # Only retry if enough time has passed since last attempt
        if current_time - self.last_connection_attempt < self.connection_retry_interval:
            return False
        
        self.last_connection_attempt = current_time
        logger.info("🔄 Attempting to reconnect to DAS server...")
        
        # Close existing socket if any
        try:
            self.s.close()
        except:
            pass
        
        # Create new socket
        self.s = socket.socket()
        
        return self.ConnectToServer()
    
    def check_connection(self):
        """Check if connection is still alive by sending a simple command"""
        try:
            if not self.connected:
                return False
            
            # Send a simple command to test connection
            test_script = "GET ACCOUNT\r\n"
            result = self.SendScript(bytearray(test_script, encoding="ascii"))
            
            # If we get any response, connection is alive
            if result and len(result.strip()) > 0:
                return True
            else:
                logger.warning("DAS connection appears to be dead")
                self.connected = False
                return False
                
        except Exception as e:
            logger.warning(f"DAS connection check failed: {e}")
            self.connected = False
            return False
    
    def Disconnect(self):
        """Disconnect from DAS server"""
        try:
            if self.connected:
                self.s.sendall(b'QUIT\r\n')
                self.s.close()
                self.connected = False
        except Exception as e:
            logger.error(f"Error disconnecting from DAS: {e}")
    
    def recvall(self):
        """Receive all available data"""
        data = b''
        bufsize = 4096
        while True:
            packet = self.s.recv(bufsize)
            data += packet
            if len(packet) < bufsize:
                break
        return data
    
    def SendScript(self, script):
        """Send script to DAS"""
        try:
            if not self.connected:
                logger.error("Not connected to DAS")
                return ""
            
            self.s.sendall(script)
            
            # Determine sleep time based on command type
            script_str = script.decode("ascii")
            if script_str.startswith("GET") or script_str.startswith("NEWORDER") or script_str.startswith("SL"):
                time.sleep(0.1)
            elif "REPLACE" in script_str or "COMPLEXORDER" in script_str:
                time.sleep(0.2)
            else:
                time.sleep(0.0005)
            
            data = self.recvall()
            return data.decode("ascii").strip()
            
        except Exception as e:
            logger.error(f"Error sending script to DAS: {e}")
            self.connected = False  # Mark as disconnected on error
            return ""

class PositionParser:
    """Handles parsing of position data from DAS"""
    
    @staticmethod
    def parse_position_line(line: str) -> Optional[Dict]:
        """Parse a single position line from DAS"""
        try:
            line = line.strip()
            if not line or not line.startswith('%POS'):
                return None
            
            parts = line.split()
            if len(parts) < 5:
                return None
            
            symbol = parts[1]
            position_type_num = int(parts[2])
            quantity = int(parts[3])
            avg_price = float(parts[4])
            
            # Validate position type
            if position_type_num == 2:
                position_type = "LONG"
            elif position_type_num == 3:
                position_type = "SHORT"
            else:
                return None
            
            # Only return valid positions
            if quantity > 0 and avg_price > 0:
                return {
                    'symbol': symbol,
                    'type': position_type,
                    'quantity': quantity,
                    'avg_price': avg_price
                }
            
            return None
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Error parsing position line: {e}")
            return None
    
    @staticmethod
    def parse_positions_raw(positions_raw: str) -> List[Dict]:
        """Parse raw positions data from DAS"""
        positions = []
        
        if not positions_raw or positions_raw.strip() == "":
            return positions
        
        lines = positions_raw.split('\n')
        for line in lines:
            position = PositionParser.parse_position_line(line)
            if position:
                positions.append(position)
        
        return positions

class PriceManager:
    """Handles price data management and Level 1 subscriptions"""
    
    def __init__(self, connection: DASConnection):
        self.connection = connection
        self.subscribed_symbols = set()
        self.price_cache: Dict[str, PriceData] = {}
        self._level1_format_set = False
    
    def set_level1_format(self):
        """Set Level 1 data format (only once)"""
        if not self._level1_format_set:
            try:
                format_script = "ReturnFullLv1 YES\r\n"
                result = self.connection.SendScript(bytearray(format_script, encoding="ascii"))
                logger.info(f"Set Level 1 format: {result}")
                self._level1_format_set = True
            except Exception as e:
                logger.error(f"Error setting Level 1 format: {e}")
                raise
    
    def subscribe_to_symbol(self, symbol: str) -> bool:
        """Subscribe to Level 1 data for a symbol"""
        try:
            symbol_upper = symbol.upper()
            if symbol_upper not in self.subscribed_symbols:
                self.set_level1_format()
                
                subscribe_script = f"SB {symbol_upper} Lv1\r\n"
                result = self.connection.SendScript(bytearray(subscribe_script, encoding="ascii"))
                logger.info(f"Subscription result for {symbol}: {result}")
                
                self.subscribed_symbols.add(symbol_upper)
                logger.info(f"Successfully subscribed to {symbol} Level 1 data")
                return True
            else:
                logger.debug(f"Already subscribed to {symbol} Level 1 data")
                return True
            
        except Exception as e:
            logger.error(f"Error subscribing to {symbol}: {e}")
            return False
    
    def unsubscribe_from_symbol(self, symbol: str) -> bool:
        """Unsubscribe from Level 1 data for a symbol"""
        try:
            symbol_upper = symbol.upper()
            if symbol_upper in self.subscribed_symbols:
                unsubscribe_script = f"UNSB {symbol_upper} Lv1\r\n"
                result = self.connection.SendScript(bytearray(unsubscribe_script, encoding="ascii"))
                logger.info(f"Unsubscription result for {symbol}: {result}")
                self.subscribed_symbols.remove(symbol_upper)
                logger.info(f"Successfully unsubscribed from {symbol} Level 1 data")
                return True
            else:
                logger.debug(f"Already unsubscribed from {symbol} Level 1 data")
                return True
        except Exception as e:
            logger.error(f"Error unsubscribing from {symbol}: {e}")
            return False
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol from cached data - use bid for exits"""
        try:
            symbol_upper = symbol.upper()
            
            # Check if we have cached data
            if symbol_upper in self.price_cache:
                price_data = self.price_cache[symbol_upper]
                logger.debug(f"Found cached price data for {symbol}: Ask=${price_data.ask:.2f}, Bid=${price_data.bid:.2f}, Last=${price_data.last:.2f}")
                
                # For exits, use bid price (what we can actually sell for)
                if price_data.bid > 0:
                    return price_data.bid
                elif price_data.ask > 0:
                    return price_data.ask
                elif price_data.last > 0:
                    return price_data.last
                else:
                    logger.warning(f"Cached price data for {symbol} has no valid prices")
            else:
                logger.debug(f"No cached price data found for {symbol}")
            
            # For now, return None if no cached data
            # In a full implementation, you would update price data here
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None

class ExitConditionChecker:
    """Handles exit condition checking logic"""
    
    @staticmethod
    def check_exit_conditions(symbol: str, position: Position, current_price: float) -> Tuple[bool, str]:
        """Check if position should be closed"""
        logger.info(f"Exit condition check for {symbol}: {position.type} position, current: ${current_price:.2f}, profit target: ${position.profit_target:.2f}, stop loss: ${position.stop_loss:.2f}")
        
        if position.type == "LONG":
            if current_price >= position.profit_target:
                logger.info(f"LONG position {symbol} profit target hit: ${current_price:.2f} >= ${position.profit_target:.2f}")
                return True, "PROFIT_TARGET"
            elif current_price <= position.stop_loss:
                logger.info(f"LONG position {symbol} stop loss hit: ${current_price:.2f} <= ${position.stop_loss:.2f}")
                return True, "STOP_LOSS"
        else:  # SHORT
            if current_price <= position.profit_target:
                logger.info(f"SHORT position {symbol} profit target hit: ${current_price:.2f} <= ${position.profit_target:.2f}")
                return True, "PROFIT_TARGET"
            elif current_price >= position.stop_loss:
                logger.info(f"SHORT position {symbol} stop loss hit: ${current_price:.2f} >= ${position.stop_loss:.2f}")
                return True, "STOP_LOSS"
        
        logger.info(f"No exit conditions met for {symbol}: current price ${current_price:.2f} is within target range")
        return False, ""

class OrderManager:
    """Handles order placement and management"""
    
    def __init__(self, connection: DASConnection):
        self.connection = connection
        self.uniq = str(uuid.uuid4())
    
    def close_position(self, symbol: str, position: Position, current_price: float, exit_reason: str) -> bool:
        """Close a position using proper CMDAPI format"""
        try:
            logger.info(f"🚪 Closing {position.type} position for {symbol}")
            logger.info(f"   Exit reason: {exit_reason}")
            logger.info(f"   Current price: ${current_price:.2f}")
            
            # Generate unique ID for the order
            unID = int(uuid.uuid4().hex[:8], 16)
            
            # Place exit order using proper CMDAPI format
            if position.type == "LONG":
                # Sell to close long position
                script = f"NEWORDER {unID} S {symbol.upper()} SMAT {position.size} MKT"
            else:
                # Buy to close short position
                script = f"NEWORDER {unID} B {symbol.upper()} SMAT {position.size} MKT"
            
            logger.info(f"Sending command: {script}")
            result = self.connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
            logger.info(f"Exit order result: {result}")
            
            if "SUCCESS" in result.upper() or "ACCEPTED" in result.upper():
                # Calculate P&L
                if position.type == "LONG":
                    pnl = (current_price - position.entry_price) * position.size
                else:
                    pnl = (position.entry_price - current_price) * position.size
                
                logger.info(f"✅ Position closed: {symbol} {position.type}")
                logger.info(f"   P&L: ${pnl:.2f}")
                return True
            else:
                logger.error(f"❌ Exit order failed for {symbol}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            return False

class TradingBot:
    """Enhanced trading bot with position monitoring capabilities"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.is_running = False
        self.subscribed_stocks = set()
        self.positions = []
        self.active_positions: Dict[str, Position] = {}
        self.active_positions_count = 0
        self.last_update = None
        
        # DAS Connection components
        self.das_connection: Optional[DASConnection] = None
        self.price_manager: Optional[PriceManager] = None
        self.order_manager: Optional[OrderManager] = None
        
        # Configuration
        self.config = config or {}
        self.profit_target_pct = self.config.get('profit_target_pct', 5.0)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 2.5)
        self.monitor_interval = self.config.get('monitor_interval', 1)
        
        # Enhanced monitoring intervals
        self.price_check_interval = 1  # Check prices every 1 second (critical for exits)
        self.position_discovery_interval = 30  # Check for new positions every 30 seconds
        self.config_check_interval = 300  # Check config changes every 5 minutes
        
        # Monitoring timestamps
        self.last_position_discovery = 0
        self.last_config_check = 0
        
        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitoring = False
        
    def check_and_establish_das_connection(self) -> bool:
        """Check if DAS is connected, try to connect if not"""
        try:
            # If we have a connection, check if it's still alive
            if self.das_connection and self.das_connection.connected:
                if self.das_connection.check_connection():
                    logger.debug("✅ DAS connection is alive")
                    return True
                else:
                    logger.warning("⚠️ DAS connection is dead, will attempt reconnect")
            
            # Try to establish connection
            logger.info("🔌 Attempting to establish DAS connection...")
            return self.connect_to_das()
            
        except Exception as e:
            logger.error(f"❌ Error checking/establishing DAS connection: {e}")
            return False
    
    def connect_to_das(self) -> bool:
        """Connect to DAS Trader"""
        try:
            logger.info("Connecting to DAS server...")
            self.das_connection = DASConnection()
            
            if self.das_connection.ConnectToServer():
                # Initialize components after connection
                self.price_manager = PriceManager(self.das_connection)
                self.order_manager = OrderManager(self.das_connection)
                
                logger.info("✅ Successfully connected to DAS server")
                return True
            else:
                logger.error("❌ Failed to connect to DAS server")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error connecting to DAS: {e}")
            return False
    
    def disconnect_from_das(self):
        """Disconnect from DAS Trader"""
        if self.das_connection:
            try:
                # Unsubscribe from all symbols before disconnecting
                if self.price_manager:
                    for symbol in list(self.price_manager.subscribed_symbols):
                        self.price_manager.unsubscribe_from_symbol(symbol)
                
                self.das_connection.Disconnect()
                logger.info("✅ Disconnected from DAS server")
            except Exception as e:
                logger.error(f"⚠️ Disconnect warning: {e}")
    
    def get_current_positions(self) -> str:
        """Get current positions from DAS - returns raw string data"""
        try:
            if not self.das_connection:
                return ""
            
            script = "GET POSITIONS\r\n"
            logger.info("Getting current positions from DAS...")
            result = self.das_connection.SendScript(bytearray(script, encoding="ascii"))
            
            # Filter and log only positions with qty > 0
            filtered_result = self._filter_positions_with_quantity(result)
            logger.info(f"Positions result (qty > 0 only): {filtered_result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting current positions: {e}")
            return ""
    
    def _filter_positions_with_quantity(self, positions_raw: str) -> str:
        """Filter positions to only show those with quantity > 0"""
        try:
            if not positions_raw or positions_raw.strip() == "":
                return positions_raw
            
            lines = positions_raw.split('\n')
            filtered_lines = []
            
            for line in lines:
                line = line.strip()
                if not line or not line.startswith('%POS'):
                    filtered_lines.append(line)
                    continue
                
                # Parse the position line to check quantity
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        quantity = int(parts[3])
                        if quantity > 0:
                            filtered_lines.append(line)
                    except (ValueError, IndexError):
                        # If we can't parse quantity, include the line
                        filtered_lines.append(line)
                else:
                    # If line doesn't have enough parts, include it
                    filtered_lines.append(line)
            
            return '\n'.join(filtered_lines)
            
        except Exception as e:
            logger.error(f"Error filtering positions: {e}")
            return positions_raw
    
    def _calculate_exit_targets(self, position_type: str, avg_price: float) -> Tuple[float, float]:
        """Calculate profit target and stop loss based on position type and entry price"""
        if position_type == "LONG":
            profit_target = avg_price * (1 + self.profit_target_pct / 100)
            stop_loss = avg_price * (1 - self.stop_loss_pct / 100)
        else:  # SHORT
            profit_target = avg_price * (1 - self.profit_target_pct / 100)
            stop_loss = avg_price * (1 + self.stop_loss_pct / 100)
        
        return profit_target, stop_loss
    
    def _create_position_object(self, position_data: Dict) -> Position:
        """Create a Position object from position data"""
        profit_target, stop_loss = self._calculate_exit_targets(
            position_data['type'], 
            position_data['avg_price']
        )
        
        return Position(
            symbol=position_data['symbol'],
            type=position_data['type'],
            size=position_data['quantity'],
            entry_price=position_data['avg_price'],
            profit_target=profit_target,
            stop_loss=stop_loss,
            entry_time=time.time(),
            position_id=f"POS_{position_data['symbol']}_{position_data['quantity']}"
        )
    
    def discover_existing_positions(self):
        """Discover and track all existing positions in the account"""
        logger.info("🔍 Discovering existing positions...")
        
        try:
            # Get current positions from DAS
            positions_raw = self.get_current_positions()
            
            if not positions_raw or positions_raw.strip() == "":
                logger.info("ℹ️ No existing positions found in account")
                return
            
            # Parse positions
            discovered_positions = PositionParser.parse_positions_raw(positions_raw)
            
            # Track discovered positions
            for pos_data in discovered_positions:
                symbol = pos_data['symbol']
                if symbol not in self.active_positions:
                    logger.info(f"📊 Adding {symbol} to active positions tracking...")
                    
                    # Create position object
                    position = self._create_position_object(pos_data)
                    self.active_positions[symbol] = position
                    
                    # Subscribe to Level 1 data for this symbol
                    if self.price_manager:
                        self.price_manager.subscribe_to_symbol(symbol)
                    
                    logger.info(f"✅ Added {symbol} to tracking: {position.type} {position.size} @ ${position.entry_price:.2f}, profit target: ${position.profit_target:.2f}, stop loss: ${position.stop_loss:.2f}")
                else:
                    logger.info(f"ℹ️ {symbol} already in active positions, skipping")
            
            self.active_positions_count = len(self.active_positions)
            logger.info(f"📊 Total discovered positions: {len(discovered_positions)}")
            logger.info(f"📊 Total active positions after discovery: {self.active_positions_count}")
            
        except Exception as e:
            logger.error(f"❌ Error discovering existing positions: {e}")
    
    def check_for_new_positions(self):
        """Check for new positions that might have been opened manually"""
        try:
            # Get current positions from DAS
            positions_raw = self.get_current_positions()
            
            if not positions_raw or positions_raw.strip() == "":
                return
            
            # Parse positions
            current_positions = PositionParser.parse_positions_raw(positions_raw)
            current_symbols = set()
            new_positions_found = []
            
            for pos_data in current_positions:
                symbol = pos_data['symbol']
                current_symbols.add(symbol.upper())
                
                # Check if this is a new position not in our tracking
                if symbol.upper() not in self.active_positions:
                    logger.info(f"Found new position: {symbol}")
                    
                    # Create position object
                    position = self._create_position_object(pos_data)
                    self.active_positions[symbol.upper()] = position
                    
                    # Subscribe to Level 1 data for this symbol
                    if self.price_manager:
                        self.price_manager.subscribe_to_symbol(symbol)
                    
                    new_positions_found.append(pos_data)
            
            # Log new positions found
            if new_positions_found:
                logger.info(f"🆕 Found {len(new_positions_found)} new position(s):")
                for pos in new_positions_found:
                    logger.info(f"   {pos['symbol']} {pos['type']} {pos['quantity']} @ ${pos['avg_price']:.2f}")
            
            self.active_positions_count = len(self.active_positions)
                    
        except Exception as e:
            logger.warning(f"Error checking for new positions: {e}")
    
    def _check_position_exists_in_das(self, positions_raw: str, symbol: str) -> bool:
        """Check if a position exists in DAS by properly parsing the positions data"""
        try:
            if not positions_raw or positions_raw.strip() == "":
                return False
            
            # Parse all position lines
            lines = positions_raw.split('\n')
            
            for line in lines:
                position = PositionParser.parse_position_line(line)
                if position and position['symbol'].upper() == symbol.upper():
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if position exists for {symbol}: {e}")
            return False
    
    def monitor_positions_loop(self):
        """Main position monitoring loop with multi-tier intervals"""
        logger.info("👀 Starting enhanced position monitoring loop...")
        logger.info(f"📊 Monitoring intervals - Price: {self.price_check_interval}s, Position Discovery: {self.position_discovery_interval}s, Config: {self.config_check_interval}s")
        
        while self.monitoring and self.is_running:
            try:
                # Check if DAS is still connected before proceeding
                if not self.das_connection or not self.das_connection.connected:
                    logger.warning("⚠️ DAS connection lost, pausing monitoring...")
                    time.sleep(5)  # Wait 5 seconds before checking again
                    continue
                
                # Verify connection is still alive
                if not self.das_connection.check_connection():
                    logger.warning("⚠️ DAS connection appears dead, pausing monitoring...")
                    time.sleep(5)  # Wait 5 seconds before checking again
                    continue
                
                current_time = time.time()
                
                # Always check prices and exit conditions (critical for trading)
                if self.active_positions:
                    logger.debug(f"🔄 Price monitoring cycle. Active positions: {len(self.active_positions)}")
                    
                    for symbol, position in list(self.active_positions.items()):
                        logger.debug(f"📊 Checking {symbol} price...")
                        
                        # Get current price
                        current_price = None
                        if self.price_manager:
                            current_price = self.price_manager.get_current_price(symbol)
                        
                        if current_price:
                            logger.debug(f"💰 Current price for {symbol}: ${current_price:.2f}")
                            
                            # Check exit conditions
                            should_exit, exit_reason = ExitConditionChecker.check_exit_conditions(
                                symbol, position, current_price
                            )
                            
                            if should_exit:
                                logger.info(f"🚪 Exit condition met for {symbol}: {exit_reason}")
                                
                                if self.order_manager:
                                    success = self.order_manager.close_position(symbol, position, current_price, exit_reason)
                                    if success:
                                        del self.active_positions[symbol]
                                        if self.price_manager:
                                            self.price_manager.unsubscribe_from_symbol(symbol)
                            else:
                                logger.debug(f"✅ No exit conditions met for {symbol}")
                        else:
                            logger.warning(f"⚠️ Could not get current price for {symbol}")
                
                # Check for new positions (less frequent)
                if current_time - self.last_position_discovery >= self.position_discovery_interval:
                    logger.info("🔍 Checking for new positions...")
                    self.check_for_new_positions()
                    self.last_position_discovery = current_time
                
                # Check for position closures (less frequent)
                if current_time - self.last_position_discovery >= self.position_discovery_interval:
                    current_positions_raw = self.get_current_positions()
                    
                    for symbol, position in list(self.active_positions.items()):
                        position_exists = self._check_position_exists_in_das(current_positions_raw, symbol)
                        
                        if not position_exists:
                            logger.info(f"❌ Position {symbol} no longer exists in DAS, removing from tracking")
                            del self.active_positions[symbol]
                            if self.price_manager:
                                self.price_manager.unsubscribe_from_symbol(symbol)
                
                # Check for config changes (least frequent)
                if current_time - self.last_config_check >= self.config_check_interval:
                    logger.debug("⚙️ Checking for config changes...")
                    # Note: Config changes are currently handled via API, but we could add
                    # file monitoring or other config sources here if needed
                    self.last_config_check = current_time
                
                # Update position count
                self.active_positions_count = len(self.active_positions)
                
                # Wait before next price check (most frequent operation)
                time.sleep(self.price_check_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in position monitoring loop: {e}")
                time.sleep(30)  # Wait longer on error
    
    def start(self) -> bool:
        """Start the trading bot"""
        try:
            self.is_running = True
            self.last_update = datetime.now()
            
            # Connect to DAS
            if not self.check_and_establish_das_connection():
                logger.error("❌ Failed to connect to DAS, cannot start bot")
                logger.error("💡 Please ensure DAS Trader is running and the connection is established")
                return False
            
            # Discover existing positions
            self.discover_existing_positions()
            
            # Start position monitoring in a separate thread
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_positions_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info("✅ Trading bot started with position monitoring")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the trading bot"""
        try:
            self.is_running = False
            self.monitoring = False
            self.last_update = datetime.now()
            
            # Wait for monitoring thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            
            # Disconnect from DAS
            self.disconnect_from_das()
            
            logger.info("✅ Trading bot stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")
            return False
    
    def force_reconnect_das(self) -> bool:
        """Force a reconnection to DAS"""
        try:
            logger.info("🔄 Force reconnecting to DAS...")
            
            # Disconnect if currently connected
            if self.das_connection:
                self.das_connection.Disconnect()
            
            # Try to establish new connection
            return self.check_and_establish_das_connection()
            
        except Exception as e:
            logger.error(f"❌ Error force reconnecting to DAS: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get bot status"""
        # Check DAS connection status
        das_connected = False
        if self.das_connection:
            das_connected = self.das_connection.connected and self.das_connection.check_connection()
        
        # Bot cannot be truly "running" without DAS connection
        # Even if is_running is True, if DAS is disconnected, the bot is effectively stopped
        effective_running = self.is_running and das_connected
        effective_monitoring = self.monitoring and das_connected
        
        return {
            'running': effective_running,
            'monitoring': effective_monitoring,
            'subscribed_stocks': list(self.subscribed_stocks),
            'positions': self.positions,
            'active_positions': self.active_positions_count,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'profit_target_pct': self.profit_target_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'monitor_interval': self.monitor_interval,
            'price_check_interval': self.price_check_interval,
            'position_discovery_interval': self.position_discovery_interval,
            'config_check_interval': self.config_check_interval,
            'das_connected': das_connected,
            'internal_running_state': self.is_running,  # Keep track of internal state
            'internal_monitoring_state': self.monitoring  # Keep track of internal state
        }
    
    def subscribe_stock(self, ticker: str) -> bool:
        """Subscribe to a stock"""
        try:
            self.subscribed_stocks.add(ticker.upper())
            logger.info(f"✅ Subscribed to {ticker.upper()}")
            return True
        except Exception as e:
            logger.error(f"❌ Error subscribing to {ticker}: {e}")
            return False
    
    def unsubscribe_stock(self, ticker: str) -> bool:
        """Unsubscribe from a stock"""
        try:
            if ticker.upper() in self.subscribed_stocks:
                self.subscribed_stocks.remove(ticker.upper())
                logger.info(f"✅ Unsubscribed from {ticker.upper()}")
            return True
        except Exception as e:
            logger.error(f"❌ Error unsubscribing from {ticker}: {e}")
            return False
    
    def update_strategies(self, strategies: Dict) -> bool:
        """Update bot strategies"""
        try:
            logger.info(f"✅ Strategies updated: {strategies}")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating strategies: {e}")
            return False

    def panic_exit_all_positions(self) -> Dict:
        """
        Emergency panic exit - close all positions at market price immediately
        Returns a dictionary with results of the operation
        """
        try:
            logger.warning("🚨 PANIC EXIT INITIATED - CLOSING ALL POSITIONS AT MARKET")
            
            if not self.das_connection or not self.das_connection.connected:
                logger.error("❌ Not connected to DAS - cannot execute panic exit")
                return {
                    'success': False,
                    'error': 'Not connected to DAS server',
                    'positions_closed': 0,
                    'positions_failed': 0,
                    'details': []
                }
            
            # Get current positions
            positions_raw = self.get_current_positions()
            positions = PositionParser.parse_positions_raw(positions_raw)
            
            if not positions:
                logger.info("ℹ️ No positions found to close")
                return {
                    'success': True,
                    'message': 'No positions found to close',
                    'positions_closed': 0,
                    'positions_failed': 0,
                    'details': []
                }
            
            logger.info(f"📊 Found {len(positions)} positions to close")
            
            successful_closes = 0
            failed_closes = 0
            details = []
            
            for i, position in enumerate(positions, 1):
                logger.info(f"[{i}/{len(positions)}] Closing {position['symbol']} {position['type']} {position['quantity']}")
                
                try:
                    # Generate unique order ID
                    unID = int(time.time() * 1000) % 1000000  # Simple unique ID
                    
                    # Determine order side based on position type
                    if position['type'] == "LONG":
                        # Sell to close long position
                        script = f"NEWORDER {unID} S {position['symbol'].upper()} SMAT {position['quantity']} MKT"
                        order_side = "SELL"
                    else:
                        # Buy to close short position
                        script = f"NEWORDER {unID} B {position['symbol'].upper()} SMAT {position['quantity']} MKT"
                        order_side = "BUY"
                    
                    logger.info(f"Sending order: {script}")
                    result = self.das_connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
                    
                    if "SUCCESS" in result.upper() or "ACCEPTED" in result.upper():
                        successful_closes += 1
                        status = "SUCCESS"
                        logger.info(f"✅ Successfully closed {position['symbol']} {position['type']}")
                    else:
                        failed_closes += 1
                        status = "FAILED"
                        logger.error(f"❌ Failed to close {position['symbol']}: {result}")
                    
                    details.append({
                        'symbol': position['symbol'],
                        'type': position['type'],
                        'quantity': position['quantity'],
                        'avg_price': position['avg_price'],
                        'order_side': order_side,
                        'status': status,
                        'result': result
                    })
                    
                    # Small delay between orders
                    time.sleep(0.5)
                    
                except Exception as e:
                    failed_closes += 1
                    logger.error(f"❌ Error closing {position['symbol']}: {e}")
                    details.append({
                        'symbol': position['symbol'],
                        'type': position['type'],
                        'quantity': position['quantity'],
                        'avg_price': position['avg_price'],
                        'order_side': 'UNKNOWN',
                        'status': 'ERROR',
                        'result': str(e)
                    })
            
            # Update local position tracking
            self.active_positions.clear()
            self.active_positions_count = 0
            
            result = {
                'success': True,
                'message': f'Panic exit completed - {successful_closes} closed, {failed_closes} failed',
                'positions_closed': successful_closes,
                'positions_failed': failed_closes,
                'total_positions': len(positions),
                'details': details,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.warning(f"🚨 PANIC EXIT COMPLETED: {successful_closes} closed, {failed_closes} failed")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error during panic exit: {e}")
            return {
                'success': False,
                'error': str(e),
                'positions_closed': 0,
                'positions_failed': 0,
                'details': []
            }

# Global bot instance
trading_bot = TradingBot()
