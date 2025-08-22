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
    

    
    def parse_position_line(self, line: str) -> Optional[Dict]:
        """Parse a single position line from DAS response"""
        line = line.strip()
        
        # Match pattern: %POS AAPL 3 100 117.34 0 0 0 2022/04/07-09:56:43 -245
        # Format: %POS symbol type qty avgcost initqty initprice Realized CreateTime Unrealized
        position_pattern = r'%POS\s+(\w+)\s+(\d+)\s+(-?\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+([\d.-]+)\s+([\d/]+-\d+:\d+:\d+)\s+([\d.-]+)'
        match = re.match(position_pattern, line)
        
        if match:
            symbol, type_val, quantity, avg_cost, init_quantity, init_price, realized, create_time, unrealized = match.groups()
            
            # Extract date from create_time (format: 2022/04/07-09:56:43)
            date_part = create_time.split('-')[0] if '-' in create_time else create_time.split(' ')[0]
            
            return {
                'symbol': symbol.upper(),
                'type': int(type_val),
                'quantity': int(quantity),
                'avg_cost': float(avg_cost),
                'init_quantity': int(init_quantity),
                'init_price': float(init_price),
                'realized': float(realized),
                'create_time': create_time,
                'date': date_part,
                'unrealized': float(unrealized)
            }
        
        return None
    
    def parse_das_positions_response(self, response: str) -> List[Dict]:
        """Parse complete DAS positions response"""
        positions = []
        lines = response.strip().split('\n')
        
        for line in lines:
            # Skip header and footer lines
            if line.startswith('#POS') or line.startswith('#POSEND'):
                continue
            
            position = self.parse_position_line(line)
            if position:
                positions.append(position)
        
        return positions
    

    
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
    

    
    def get_position_history(self, symbol: Optional[str] = None, 
                            type_filter: Optional[int] = None, 
                            limit: int = 100) -> List[Dict]:
        """Get position history from database"""
        return db_manager.get_positions(symbol, type_filter, limit)
    
    def get_position_summary(self, symbol: Optional[str] = None,
                            type_filter: Optional[int] = None) -> Optional[Dict]:
        """Get position summary from database"""
        return db_manager.get_position_summary(symbol, type_filter)
    


# Global DAS trade manager instance
das_trade_manager = DASTradeManager()



def sync_positions_from_das():
    """Convenience function to sync positions from DAS"""
    return das_trade_manager.sync_positions_from_das()

def get_position_history(symbol=None, type_filter=None, limit=100):
    """Convenience function to get position history"""
    return das_trade_manager.get_position_history(symbol, type_filter, limit)

def get_position_summary(symbol=None, type_filter=None):
    """Convenience function to get position summary"""
    return das_trade_manager.get_position_summary(symbol, type_filter)
