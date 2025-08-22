#!/usr/bin/env python3
"""
DAS Trader Integration Module
Handles connection to DAS Trader and trade data retrieval
"""
import socket
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
from database import db_manager

logger = logging.getLogger(__name__)

class DASConnection:
    """Connection to DAS Trader"""
    
    def __init__(self, host="127.0.0.1", port=9800, userid="IDAS12181", password="Dastrader@2", account="TRIDAS12181"):
        self.host = host
        self.port = port
        self.userid = userid
        self.password = password
        self.account = account
        self.socket = None
        self.connected = False
    
    def connect(self):
        """Connect to DAS Trader"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((self.host, self.port))
            
            # Login
            login_data = f"LOGIN {self.userid} {self.password} {self.account}\r\n"
            self.socket.sendall(login_data.encode('ascii'))
            time.sleep(0.1)
            
            # Read response
            response = self.socket.recv(1024).decode('ascii')
            logger.info(f"DAS login response: {response}")
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to DAS: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from DAS Trader"""
        try:
            if self.socket:
                self.socket.sendall(b'QUIT\r\n')
                self.socket.close()
                self.socket = None
                self.connected = False
        except Exception as e:
            logger.error(f"Error disconnecting from DAS: {e}")
    
    def send_command(self, command: str) -> str:
        """Send command to DAS and get response"""
        if not self.connected:
            logger.error("Not connected to DAS")
            return ""
        
        try:
            # Send command
            self.socket.sendall(f"{command}\r\n".encode('ascii'))
            time.sleep(0.1)
            
            # Read response
            data = b''
            while True:
                chunk = self.socket.recv(4096)
                data += chunk
                if len(chunk) < 4096:
                    break
            
            return data.decode('ascii').strip()
            
        except Exception as e:
            logger.error(f"Error sending command to DAS: {e}")
            return ""
    
    def get_trades(self) -> str:
        """Get current trades from DAS"""
        return self.send_command("GET TRADES")
    
    def get_positions(self) -> str:
        """Get current positions from DAS"""
        return self.send_command("GET POSITIONS")
    
    def get_orders(self) -> str:
        """Get current orders from DAS"""
        return self.send_command("GET ORDERS")

class DASTradeManager:
    """Manages DAS trade data and database integration"""
    
    def __init__(self):
        self.das_connection = DASConnection()
        self.last_sync_time = None
    
    def connect_to_das(self) -> bool:
        """Connect to DAS Trader"""
        return self.das_connection.connect()
    
    def disconnect_from_das(self):
        """Disconnect from DAS Trader"""
        self.das_connection.disconnect()
    
    def parse_trade_line(self, line: str) -> Optional[Dict]:
        """Parse a single trade line from DAS response"""
        line = line.strip()
        
        # Match pattern: %TRADE 1 MSFT B 100 28.3
        trade_pattern = r'%TRADE\s+(\d+)\s+(\w+)\s+([BSS]+)\s+(\d+)\s+([\d.]+)'
        match = re.match(trade_pattern, line)
        
        if match:
            trade_id, symbol, side, quantity, price = match.groups()
            
            return {
                'trade_id': int(trade_id),
                'symbol': symbol.upper(),
                'side': side,
                'quantity': int(quantity),
                'price': float(price),
                'route': 'SMAT',  # Default route
                'trade_time': datetime.now().strftime('%H:%M:%S'),
                'order_id': None,
                'liquidity': '',
                'ecn_fee': 0.0,
                'pnl': 0.0,
                'trade_date': datetime.now().date().isoformat()
            }
        
        return None
    
    def parse_das_trades_response(self, response: str) -> List[Dict]:
        """Parse complete DAS trades response"""
        trades = []
        lines = response.strip().split('\n')
        
        for line in lines:
            trade = self.parse_trade_line(line)
            if trade:
                trades.append(trade)
        
        return trades
    
    def parse_position_line(self, line: str) -> Optional[Dict]:
        """Parse a single position line from DAS response"""
        line = line.strip()
        
        # Match pattern: %POSITION MSFT 100 28.3 0.0 0.0
        # Format: %POSITION symbol quantity avg_price realized_pnl unrealized_pnl
        position_pattern = r'%POSITION\s+(\w+)\s+(-?\d+)\s+([\d.]+)\s+([\d.-]+)\s+([\d.-]+)'
        match = re.match(position_pattern, line)
        
        if match:
            symbol, quantity, avg_price, realized_pnl, unrealized_pnl = match.groups()
            
            # Determine position type based on quantity
            position_type = 'LONG' if int(quantity) > 0 else 'SHORT'
            
            # Calculate additional fields
            quantity_abs = abs(int(quantity))
            cost_basis = quantity_abs * float(avg_price)
            market_value = cost_basis + float(unrealized_pnl)
            unrealized_pnl_pct = (float(unrealized_pnl) / cost_basis * 100) if cost_basis > 0 else 0.0
            
            return {
                'symbol': symbol.upper(),
                'quantity': int(quantity),
                'avg_price': float(avg_price),
                'current_price': float(avg_price),  # Will be updated with real-time price
                'position_type': position_type,
                'realized_pnl': float(realized_pnl),
                'unrealized_pnl': float(unrealized_pnl),
                'unrealized_pnl_pct': unrealized_pnl_pct,
                'market_value': market_value,
                'cost_basis': cost_basis,
                'profit_target': 0.0,  # Will be set by bot configuration
                'stop_loss': 0.0       # Will be set by bot configuration
            }
        
        return None
    
    def parse_das_positions_response(self, response: str) -> List[Dict]:
        """Parse complete DAS positions response"""
        positions = []
        lines = response.strip().split('\n')
        
        for line in lines:
            position = self.parse_position_line(line)
            if position:
                positions.append(position)
        
        return positions
    
    def sync_trades_from_das(self) -> Tuple[bool, str, int]:
        """Sync trades from DAS to database"""
        try:
            if not self.das_connection.connected:
                if not self.connect_to_das():
                    return False, "Failed to connect to DAS", 0
            
            # Get trades from DAS
            das_response = self.das_connection.get_trades()
            
            if not das_response:
                return False, "No response from DAS", 0
            
            # Parse trades
            trades = self.parse_das_trades_response(das_response)
            
            if not trades:
                return True, "No trades found", 0
            
            # Add trades to database
            added_count = 0
            errors = []
            
            for trade in trades:
                success, message = db_manager.add_trade(trade)
                if success:
                    added_count += 1
                else:
                    errors.append(f"Trade {trade['trade_id']}: {message}")
            
            self.last_sync_time = datetime.now()
            
            if errors:
                logger.warning(f"Some trades failed to sync: {errors}")
            
            return True, f"Successfully synced {added_count} trades", added_count
            
        except Exception as e:
            logger.error(f"Error syncing trades from DAS: {e}")
            return False, str(e), 0
    
    def sync_positions_from_das(self) -> Tuple[bool, str, int]:
        """Sync positions from DAS to database"""
        try:
            if not self.das_connection.connected:
                if not self.connect_to_das():
                    return False, "Failed to connect to DAS", 0
            
            # Get positions from DAS
            das_response = self.das_connection.get_positions()
            
            if not das_response:
                return False, "No response from DAS", 0
            
            # Parse positions
            positions = self.parse_das_positions_response(das_response)
            
            if not positions:
                return True, "No positions found", 0
            
            # Upsert positions to database
            updated_count = 0
            errors = []
            
            for position in positions:
                success, message = db_manager.upsert_position(position)
                if success:
                    updated_count += 1
                else:
                    errors.append(f"Position {position['symbol']}: {message}")
            
            self.last_sync_time = datetime.now()
            
            if errors:
                logger.warning(f"Some positions failed to sync: {errors}")
            
            return True, f"Successfully synced {updated_count} positions", updated_count
            
        except Exception as e:
            logger.error(f"Error syncing positions from DAS: {e}")
            return False, str(e), 0
    
    def get_trade_history(self, symbol: Optional[str] = None, 
                         start_date: Optional[str] = None, 
                         end_date: Optional[str] = None, 
                         limit: int = 100) -> List[Dict]:
        """Get trade history from database"""
        return db_manager.get_trades(symbol, start_date, end_date, limit)
    
    def get_trade_summary(self, symbol: Optional[str] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> Optional[Dict]:
        """Get trade summary from database"""
        return db_manager.get_trade_summary(symbol, start_date, end_date)
    
    def get_position_history(self, symbol: Optional[str] = None, 
                           position_type: Optional[str] = None, 
                           limit: int = 100) -> List[Dict]:
        """Get position history from database"""
        return db_manager.get_positions(symbol, position_type, limit)
    
    def get_position_summary(self, symbol: Optional[str] = None,
                           position_type: Optional[str] = None) -> Optional[Dict]:
        """Get position summary from database"""
        return db_manager.get_position_summary(symbol, position_type)
    
    def import_das_trades_text(self, das_trades_text: str) -> Tuple[bool, str, int]:
        """Import trades from DAS trades text"""
        try:
            trades = db_manager.parse_das_trades_data(das_trades_text)
            
            if not trades:
                return False, "No valid trades found", 0
            
            added_count = 0
            errors = []
            
            for trade in trades:
                success, message = db_manager.add_trade(trade)
                if success:
                    added_count += 1
                else:
                    errors.append(f"Trade {trade['trade_id']}: {message}")
            
            if errors:
                logger.warning(f"Some trades failed to import: {errors}")
            
            return True, f"Successfully imported {added_count} trades", added_count
            
        except Exception as e:
            logger.error(f"Error importing DAS trades: {e}")
            return False, str(e), 0

# Global DAS trade manager instance
das_trade_manager = DASTradeManager()

def sync_trades_from_das():
    """Convenience function to sync trades from DAS"""
    return das_trade_manager.sync_trades_from_das()

def get_trade_history(symbol=None, start_date=None, end_date=None, limit=100):
    """Convenience function to get trade history"""
    return das_trade_manager.get_trade_history(symbol, start_date, end_date, limit)

def get_trade_summary(symbol=None, start_date=None, end_date=None):
    """Convenience function to get trade summary"""
    return das_trade_manager.get_trade_summary(symbol, start_date, end_date)

def sync_positions_from_das():
    """Convenience function to sync positions from DAS"""
    return das_trade_manager.sync_positions_from_das()

def get_position_history(symbol=None, position_type=None, limit=100):
    """Convenience function to get position history"""
    return das_trade_manager.get_position_history(symbol, position_type, limit)

def get_position_summary(symbol=None, position_type=None):
    """Convenience function to get position summary"""
    return das_trade_manager.get_position_summary(symbol, position_type)
