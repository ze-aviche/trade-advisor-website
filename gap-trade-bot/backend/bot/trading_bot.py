#!/usr/bin/env python3
"""
Enhanced Trading Bot Module
Integrates position monitoring, DAS connection, and automated exit management
Based on working implementation from accentor-trading-bot
"""

import time
import logging
import threading
import socket
import uuid
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
import sys
import os

# Add the parent directory to the path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db_manager

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

class Connection:
    """DAS Trader Connection Class - Working implementation"""
    
    def __init__(self):
        self.s = socket.socket()
    
    def Connect(self, host, port):
        self.s.settimeout(2)
        self.s.connect(tuple([host, port]))
        time.sleep(0.1)

    def Login(self, logindata):
        self.s.sendall(logindata)
        time.sleep(0.1)
        print((self.s.recv(1024*1024)).decode("ascii"))

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
            
            # Set a short timeout for the connection check
            original_timeout = self.s.gettimeout()
            self.s.settimeout(2)  # 2 second timeout for connection check
            
            try:
                # Send a simple command to test connection
                test_script = "GET ACCOUNT\r\n"
                self.s.sendall(bytearray(test_script, encoding="ascii"))
                
                # Try to receive response with timeout
                response = self.s.recv(1024).decode("ascii")
                
                # If we get any response, connection is alive
                if response and len(response.strip()) > 0:
                    return True
                else:
                    logger.warning("DAS connection appears to be dead (no response)")
                    self.connected = False
                    return False
                    
            finally:
                # Restore original timeout
                self.s.settimeout(original_timeout)
                
        except socket.timeout:
            logger.warning("DAS connection check timed out")
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
        data = b''
        bufsize = 4096
        while True:
            packet = self.s.recv(bufsize)
            data += packet
            if len(packet) < bufsize:
                break
        return data
    
    def SendScript(self, script):
        try:
            self.s.sendall(script)
        except socket.gaierror as e:
            logger.error(f"Address-related error: {e}")
        except socket.herror as e:
            logger.error(f"Host-related error: {e}")
        except socket.timeout as e:
            logger.error(f"Timeout error: {e}")
        except socket.error as e:
            logger.error(f"General socket error: {e}")
        finally: 
            getCMD = script[:3]
            newordCMD = script[:8]
            shortCMD = script[:2]
        
            if(getCMD.decode("ascii") == "GET" or newordCMD.decode("ascii") == "NEWORDER" or shortCMD.decode("ascii") == "SL" or "MINCHART" in script.decode("ascii") or "DAYCHART" in script.decode("ascii")):
                time.sleep(.1)
            elif("REPLACE" in script.decode("ascii") or "COMPLEXORDER" in script.decode("ascii")):
                time.sleep(.2)
            else:
                time.sleep(.0005)

        try:
            data = self.recvall()
        except socket.timeout:
            return ""
        return data.decode("ascii").strip()

    def Disconnect(self):
        try:
            self.s.sendall(b'QUIT\r\n')
        except:
            pass
        finally:
            try:
                self.s.close()
            except:
                pass

class cmdAPI:
    """CMD API helper class"""
    def __init__(self):
        self.uniq = uuid.uuid4()

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
    
    def __init__(self, connection: Connection):
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
                unsub_script = f"UNSB {symbol_upper} Lv1\r\n"
                result = self.connection.SendScript(bytearray(unsub_script, encoding="ascii"))
                
                self.subscribed_symbols.discard(symbol_upper)
                if symbol_upper in self.price_cache:
                    del self.price_cache[symbol_upper]
                
                logger.info(f"Unsubscribed from {symbol} Level 1 data")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error unsubscribing from {symbol}: {e}")
            return False
    
    def update_price_data(self, symbol: str) -> Optional[PriceData]:
        """Update price data for a symbol using Level 1 data"""
        try:
            # First ensure we're subscribed to Level 1 data for this symbol
            if symbol.upper() not in self.subscribed_symbols:
                logger.info(f"Subscribing to Level 1 data for {symbol}")
                self.subscribe_to_symbol(symbol)
                # Give a moment for subscription to take effect
                time.sleep(0.5)
            
            # Get the data stream for the subscribed symbol (same as subscription command)
            data_script = f"SB {symbol.upper()} Lv1\r\n"
            result = self.connection.SendScript(bytearray(data_script, encoding="ascii"))
            
            # Log the raw result for debugging
            logger.debug(f"Raw Level 1 result for {symbol}: {result}")
            
            # Parse Level 1 data response
            lines = result.split('\n')
            first_line = None
            
            # Find the first line that contains our symbol
            for line in lines:
                line = line.strip()
                if line and symbol.upper() in line.upper():
                    first_line = line
                    break
            
            if first_line:
                parts = first_line.split()
                logger.debug(f"Found Level 1 line for {symbol}: {parts}")
                
                # Parse Level 1 data format: $Quote SYMBOL A:ASK Asz:ASKSIZE B:BID Bsz:BIDSIZE ...
                ask_price = None
                bid_price = None
                last_price = None
                
                for part in parts:
                    # Look for Ask price (A:PRICE)
                    if part.startswith('A:') and len(part) > 2:
                        try:
                            ask_price = float(part[2:])  # Remove 'A:' prefix
                        except ValueError:
                            continue
                    
                    # Look for Bid price (B:PRICE)
                    elif part.startswith('B:') and len(part) > 2:
                        try:
                            bid_price = float(part[2:])  # Remove 'B:' prefix
                        except ValueError:
                            continue
                    
                    # Look for Last price (L:PRICE)
                    elif part.startswith('L:') and len(part) > 2:
                        try:
                            last_price = float(part[2:])  # Remove 'L:' prefix
                        except ValueError:
                            continue
                
                # Validate prices are reasonable
                if ask_price and 0.01 <= ask_price <= 10000:
                    if bid_price and 0.01 <= bid_price <= 10000:
                        if last_price and 0.01 <= last_price <= 10000:
                            price_data = PriceData(
                                ask=ask_price,
                                bid=bid_price,
                                last=last_price,
                                timestamp=time.time()
                            )
                            
                            self.price_cache[symbol.upper()] = price_data
                            logger.info(f"Updated price data for {symbol}: Ask=${ask_price:.2f}, Bid=${bid_price:.2f}, Last=${last_price:.2f}")
                            return price_data
                        else:
                            # Use ask and bid only
                            price_data = PriceData(
                                ask=ask_price,
                                bid=bid_price,
                                last=0.0,
                                timestamp=time.time()
                            )
                            
                            self.price_cache[symbol.upper()] = price_data
                            logger.info(f"Updated price data for {symbol}: Ask=${ask_price:.2f}, Bid=${bid_price:.2f}")
                            return price_data
                    else:
                        # Use ask only
                        price_data = PriceData(
                            ask=ask_price,
                            bid=0.0,
                            last=0.0,
                            timestamp=time.time()
                        )
                        
                        self.price_cache[symbol.upper()] = price_data
                        logger.info(f"Updated price data for {symbol}: Ask=${ask_price:.2f}")
                        return price_data
                elif bid_price and 0.01 <= bid_price <= 10000:
                    # Use bid only
                    price_data = PriceData(
                        ask=0.0,
                        bid=bid_price,
                        last=0.0,
                        timestamp=time.time()
                    )
                    
                    self.price_cache[symbol.upper()] = price_data
                    logger.info(f"Updated price data for {symbol}: Bid=${bid_price:.2f}")
                    return price_data
                elif last_price and 0.01 <= last_price <= 10000:
                    # Use last only
                    price_data = PriceData(
                        ask=0.0,
                        bid=0.0,
                        last=last_price,
                        timestamp=time.time()
                    )
                    
                    self.price_cache[symbol.upper()] = price_data
                    logger.info(f"Updated price data for {symbol}: Last=${last_price:.2f}")
                    return price_data
                else:
                    logger.warning(f"No valid prices found for {symbol} in Level 1 data")
            else:
                logger.warning(f"No Level 1 data line found for {symbol} in response: {result}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating price data for {symbol}: {e}")
            return None
    
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
            
            # If no cached data or invalid data, try to update it
            logger.info(f"Attempting to update price data for {symbol}")
            updated_data = self.update_price_data(symbol)
            if updated_data:
                if updated_data.bid > 0:
                    return updated_data.bid
                elif updated_data.ask > 0:
                    return updated_data.ask
                elif updated_data.last > 0:
                    return updated_data.last
            
            logger.warning(f"Could not get current price for {symbol} - no valid price data available")
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def _fetch_current_price_from_das(self, symbol: str) -> Optional[float]:
        """Fetch current price directly from DAS using GET QUOTE command"""
        try:
            symbol_upper = symbol.upper()
            
            # Use GET QUOTE command to get current price
            quote_script = f"GET QUOTE {symbol_upper}\r\n"
            result = self.connection.SendScript(bytearray(quote_script, encoding="ascii"))
            
            if result and result.strip():
                # Parse the quote response
                price = self._parse_quote_response(result, symbol_upper)
                if price:
                    logger.debug(f"Fetched current price for {symbol}: ${price:.2f}")
                    return price
            
            logger.warning(f"Could not fetch price for {symbol} from DAS")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching price for {symbol} from DAS: {e}")
            return None
    
    def _parse_quote_response(self, response: str, symbol: str) -> Optional[float]:
        """Parse DAS quote response to extract price"""
        try:
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('%QUOTE') and symbol in line:
                    # Parse quote line: %QUOTE SYMBOL BID ASK LAST
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            bid = float(parts[2])
                            ask = float(parts[3])
                            last = float(parts[4])
                            
                            # Use bid price for exits (what we can actually sell for)
                            if bid > 0:
                                return bid
                            elif ask > 0:
                                return ask
                            elif last > 0:
                                return last
                        except (ValueError, IndexError):
                            continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing quote response for {symbol}: {e}")
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
    
    def __init__(self, connection: Connection):
        self.connection = connection
        self.cmd = cmdAPI()
    
    def close_position(self, symbol: str, position: Position, current_price: float, exit_reason: str) -> bool:
        """Close a position using proper CMDAPI format"""
        try:
            logger.info(f"🚪 Closing {position.type} position for {symbol}")
            logger.info(f"   Exit reason: {exit_reason}")
            logger.info(f"   Current price: ${current_price:.2f}")
            
            # Generate unique ID for the order
            unID = int(self.cmd.uniq)
            
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
                
                # Save trade to database
                try:
                    # Determine trade side for database
                    if position.type == "LONG":
                        trade_side = "S"  # Sell to close long position
                    else:
                        trade_side = "B"  # Buy to close short position
                    
                    # Create trade data for database
                    trade_data = {
                        'trade_id': int(time.time() * 1000) % 1000000,  # Generate unique trade ID
                        'symbol': symbol.upper(),
                        'side': trade_side,
                        'quantity': position.size,
                        'price': current_price,
                        'route': 'SMAT',
                        'trade_time': datetime.now().strftime('%H:%M:%S'),
                        'order_id': unID,
                        'liquidity': '',
                        'ecn_fee': 0.0,
                        'pnl': pnl,
                        'trade_date': datetime.now().date().isoformat()
                    }
                    
                    # Save to database
                    success, message = db_manager.add_trade(trade_data)
                    if success:
                        logger.info(f"💾 Trade saved to database: {symbol} {trade_side} {position.size} @ ${current_price:.2f}, P&L: ${pnl:.2f}")
                    else:
                        logger.error(f"❌ Failed to save trade to database: {message}")
                        
                except Exception as e:
                    logger.error(f"❌ Error saving trade to database: {e}")
                
                return True
            else:
                logger.error(f"❌ Exit order failed for {symbol}: {result}")
                
                # Check for SSR (Short Sale Restriction) error
                if "SSR" in result.upper() or "SHORT MARKET ORDER DISABLED" in result.upper():
                    logger.warning(f"SSR detected for {symbol}, will retry in next cycle")
                    return False  # Don't remove from tracking, let it retry
                else:
                    logger.warning(f"Removing {symbol} from position tracking due to order failure")
                    return False  # Remove from tracking
                
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
        self.connection: Optional[Connection] = None
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
        self.connection_check_interval = 10  # Check connection every 10 seconds (less frequent)
        
        # Monitoring timestamps
        self.last_position_discovery = 0
        self.last_config_check = 0
        self.last_connection_check = 0
        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitoring = False
        
        # Thread safety lock for active_positions
        self._positions_lock = threading.Lock()
        
    def connect_to_das(self) -> bool:
        """Connect to DAS Trader"""
        try:
            logger.info("Connecting to DAS server...")
            self.connection = Connection()
            self.connection.ConnectToServer()
            
            # Initialize components after connection
            self.price_manager = PriceManager(self.connection)
            self.order_manager = OrderManager(self.connection)
            
            logger.info("✅ Successfully connected to DAS server")
            return True
                
        except Exception as e:
            logger.error(f"❌ Error connecting to DAS: {e}")
            return False
    
    def force_reconnect_das(self) -> bool:
        """Force reconnection to DAS Trader"""
        try:
            logger.info("🔄 Force reconnecting to DAS server...")
            
            # Disconnect if already connected
            if self.connection:
                try:
                    self.disconnect_from_das()
                except Exception as e:
                    logger.warning(f"Warning during disconnect: {e}")
            
            # Connect again
            return self.connect_to_das()
                
        except Exception as e:
            logger.error(f"❌ Error force reconnecting to DAS: {e}")
            return False
    
    def disconnect_from_das(self):
        """Disconnect from DAS Trader"""
        if self.connection:
            try:
                # Unsubscribe from all symbols before disconnecting
                if self.price_manager:
                    for symbol in list(self.price_manager.subscribed_symbols):
                        self.price_manager.unsubscribe_from_symbol(symbol)
                
                self.connection.Disconnect()
                logger.info("✅ Disconnected from DAS server")
            except Exception as e:
                logger.error(f"⚠️ Disconnect warning: {e}")
            finally:
                # Clear the connection reference
                self.connection = None
    
    def get_current_positions(self) -> str:
        """Get current positions from DAS - returns raw string data"""
        try:
            if not self.connection:
                return ""
            
            script = "GET POSITIONS\r\n"
            logger.info("Getting current positions from DAS...")
            result = self.connection.SendScript(bytearray(script, encoding="ascii"))
            
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
            with self._positions_lock:
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
            
            with self._positions_lock:
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
        """Main position monitoring loop"""
        logger.info("👀 Starting position monitoring loop...")
        
        while self.monitoring and self.is_running:
            try:
                logger.info(f"Starting position monitoring cycle. Active positions: {len(self.active_positions)}")
                
                # Update price data for all subscribed symbols
                if self.price_manager:
                    with self._positions_lock:
                        symbols_to_check = list(self.active_positions.keys())
                    for symbol in symbols_to_check:
                        if symbol.upper() in self.price_manager.subscribed_symbols:
                            self.price_manager.update_price_data(symbol)
                
                # Get current positions from DAS
                current_positions_raw = self.get_current_positions()
                
                # Get a copy of active positions to iterate over
                with self._positions_lock:
                    active_positions_copy = dict(self.active_positions)
                
                for symbol, position in active_positions_copy.items():
                    logger.info(f"Checking position: {symbol} ({position.type} {position.size} @ ${position.entry_price:.2f}, profit target: ${position.profit_target:.2f}, stop loss: ${position.stop_loss:.2f})")
                    
                    # Check if position still exists in DAS using proper parsing
                    position_exists = self._check_position_exists_in_das(current_positions_raw, symbol)
                    
                    if not position_exists:
                        logger.info(f"Position {symbol} no longer exists in DAS, removing from tracking")
                        with self._positions_lock:
                            if symbol in self.active_positions:
                                del self.active_positions[symbol]
                                self.active_positions_count = len(self.active_positions)
                        # Unsubscribe from the symbol since position is closed
                        if self.price_manager:
                            self.price_manager.unsubscribe_from_symbol(symbol)
                        continue
                    
                    current_price = None
                    if self.price_manager:
                        current_price = self.price_manager.get_current_price(symbol)
                    
                    if current_price:
                        logger.info(f"Current price for {symbol}: ${current_price:.2f}")
                        
                        # Check exit conditions
                        should_exit, exit_reason = ExitConditionChecker.check_exit_conditions(
                            symbol, position, current_price
                        )
                        
                        if should_exit:
                            logger.info(f"Exit condition met for {symbol}: {exit_reason} at ${current_price:.2f}")
                            
                            if self.order_manager:
                                success = self.order_manager.close_position(symbol, position, current_price, exit_reason)
                                if success:
                                    with self._positions_lock:
                                        if symbol in self.active_positions:
                                            del self.active_positions[symbol]
                                            self.active_positions_count = len(self.active_positions)
                                    if self.price_manager:
                                        self.price_manager.unsubscribe_from_symbol(symbol)
                        else:
                            logger.info(f"No exit conditions met for {symbol} at ${current_price:.2f}")
                    else:
                        logger.warning(f"Could not get current price for {symbol}")
                
                # Check for new positions that might have been opened manually
                self.check_for_new_positions()
                
                # Wait before next check
                logger.info(f"Position monitoring cycle completed. Active positions: {len(self.active_positions)}")
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                time.sleep(30)
    
    def start(self) -> bool:
        """Start the trading bot"""
        try:
            self.is_running = True
            self.last_update = datetime.now()
            
            # Connect to DAS
            if not self.connect_to_das():
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
    
    def get_status(self) -> Dict:
        """Get bot status"""
        # Convert active positions to a format suitable for frontend
        positions_data = []
        
        # Use lock to safely access active_positions
        with self._positions_lock:
            # Create a copy of the active positions to avoid iteration issues
            active_positions_copy = dict(self.active_positions)
            positions_count = self.active_positions_count
        
        # Process the copy outside the lock to avoid blocking
        for symbol, position in active_positions_copy.items():
            # Get current price for P&L calculation
            current_price = self.price_manager.get_current_price(symbol) if self.price_manager else position.entry_price
            
            # Ensure current_price is not None before calculating P&L
            if current_price is None:
                current_price = position.entry_price
                unrealized_pnl = 0.0
                unrealized_pnl_pct = 0.0
            else:
                # Calculate P&L
                if position.type == "LONG":
                    unrealized_pnl = (current_price - position.entry_price) * position.size
                    unrealized_pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                else:  # SHORT
                    unrealized_pnl = (position.entry_price - current_price) * position.size
                    unrealized_pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
            
            positions_data.append({
                'symbol': position.symbol,
                'type': position.type,
                'size': position.size,
                'entry_price': position.entry_price,
                'current_price': current_price,
                'profit_target': position.profit_target,
                'stop_loss': position.stop_loss,
                'entry_time': position.entry_time,
                'position_id': position.position_id,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': unrealized_pnl_pct
            })
        
        return {
            'running': self.is_running,
            'monitoring': self.monitoring,
            'active_positions': positions_data,  # Return active positions data directly
            'active_positions_count': positions_count,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'profit_target_pct': self.profit_target_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'monitor_interval': self.monitor_interval,
            'price_check_interval': self.price_check_interval,
            'position_discovery_interval': self.position_discovery_interval,
            'config_check_interval': self.config_check_interval,
            'connection_check_interval': self.connection_check_interval,
            'das_connected': self.connection is not None
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
        """Update bot strategies and recalculate exit targets for existing positions"""
        try:
            logger.info(f"🔄 Updating bot strategies: {strategies}")
            
            # Store old values for logging
            old_profit_target = self.profit_target_pct
            old_stop_loss = self.stop_loss_pct
            old_monitor_interval = self.monitor_interval
            
            # Update configuration values
            if 'profit_target_pct' in strategies:
                self.profit_target_pct = float(strategies['profit_target_pct'])
                logger.info(f"📊 Profit target updated: {old_profit_target}% → {self.profit_target_pct}%")
            
            if 'stop_loss_pct' in strategies:
                self.stop_loss_pct = float(strategies['stop_loss_pct'])
                logger.info(f"📊 Stop loss updated: {old_stop_loss}% → {self.stop_loss_pct}%")
            
            if 'monitor_interval' in strategies:
                self.monitor_interval = int(strategies['monitor_interval'])
                logger.info(f"📊 Monitor interval updated: {old_monitor_interval}s → {self.monitor_interval}s")
            
            # Recalculate exit targets for all existing positions
            positions_updated = 0
            with self._positions_lock:
                for symbol, position in self.active_positions.items():
                    old_profit_target_val = position.profit_target
                    old_stop_loss_val = position.stop_loss
                    
                    # Recalculate exit targets with new percentages
                    new_profit_target, new_stop_loss = self._calculate_exit_targets(
                        position.type, 
                        position.entry_price
                    )
                    
                    # Update the position object
                    position.profit_target = new_profit_target
                    position.stop_loss = new_stop_loss
                    
                    logger.info(f"🔄 Updated {symbol} exit targets:")
                    logger.info(f"   Profit target: ${old_profit_target_val:.2f} → ${new_profit_target:.2f}")
                    logger.info(f"   Stop loss: ${old_stop_loss_val:.2f} → ${new_stop_loss:.2f}")
                    
                    positions_updated += 1
            
            logger.info(f"✅ Strategies updated successfully. {positions_updated} positions recalculated.")
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
            
            if not self.connection:
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
                    result = self.connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
                    
                    if "SUCCESS" in result.upper() or "ACCEPTED" in result.upper():
                        successful_closes += 1
                        status = "SUCCESS"
                        logger.info(f"✅ Successfully closed {position['symbol']} {position['type']}")
                        
                        # Save trade to database
                        try:
                            # Calculate P&L (approximate since we don't have current price)
                            # For panic exit, we'll use the average price as current price (P&L will be 0)
                            current_price = position['avg_price']
                            if position['type'] == "LONG":
                                pnl = 0.0  # Approximate for panic exit
                            else:
                                pnl = 0.0  # Approximate for panic exit
                            
                            # Create trade data for database
                            trade_data = {
                                'trade_id': int(time.time() * 1000) % 1000000,  # Generate unique trade ID
                                'symbol': position['symbol'].upper(),
                                'side': "S" if position['type'] == "LONG" else "B",  # Sell to close long, Buy to close short
                                'quantity': position['quantity'],
                                'price': current_price,
                                'route': 'SMAT',
                                'trade_time': datetime.now().strftime('%H:%M:%S'),
                                'order_id': unID,
                                'liquidity': '',
                                'ecn_fee': 0.0,
                                'pnl': pnl,
                                'trade_date': datetime.now().date().isoformat()
                            }
                            
                            # Save to database
                            success, message = db_manager.add_trade(trade_data)
                            if success:
                                logger.info(f"💾 Panic exit trade saved to database: {position['symbol']} {position['type']} {position['quantity']} @ ${current_price:.2f}")
                            else:
                                logger.error(f"❌ Failed to save panic exit trade to database: {message}")
                                
                        except Exception as e:
                            logger.error(f"❌ Error saving panic exit trade to database: {e}")
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
            with self._positions_lock:
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
