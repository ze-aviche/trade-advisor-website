#!/usr/bin/env python3
"""
Panic Exit Script
Emergency script to close all current positions at market price.
Use this only in emergency situations where you need to exit all positions immediately.
"""

import sys
import os
import time
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Add the src directory to the path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src')
sys.path.append(src_path)

# Import directly from the core module
sys.path.append(os.path.join(src_path, 'core'))
from CMDAPI_PYTHON import Connection, cmdAPI

# Create logs directory if it doesn't exist
logs_dir = os.path.join(project_root, 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Create logger
logger = logging.getLogger("panic_exit")
logger.setLevel(logging.INFO)

# Create formatters
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(console_formatter)

# Create file handler
log_filename = os.path.join(logs_dir, f'panic_exit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
file_handler = RotatingFileHandler(
    log_filename, 
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(file_formatter)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Log startup information
logger.info("="*80)
logger.info("🚨 PANIC EXIT STARTING - EMERGENCY POSITION CLOSURE")
logger.info(f"Log file: {log_filename}")
logger.info("="*80)

class PanicExit:
    """
    Panic Exit Handler
    - Connects to DAS server
    - Gets all current positions
    - Closes all positions at market price immediately
    - Logs all actions for audit trail
    """
    
    def __init__(self):
        self.connection = None
        self.cmd = cmdAPI()
        self.positions_to_close = []
        
    def connect_to_das(self):
        """Connect to DAS server"""
        try:
            print("🔌 Connecting to DAS server...")
            logger.info("Connecting to DAS server...")
            
            self.connection = Connection()
            self.connection.ConnectToServer()
            
            print("✅ Connected to DAS server!")
            logger.info("Successfully connected to DAS server")
            
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            logger.error(f"Failed to connect to DAS server: {e}")
            raise
    
    def disconnect_from_das(self):
        """Disconnect from DAS server"""
        if self.connection:
            try:
                self.connection.Disconnect()
                print("✅ Disconnected from DAS server")
                logger.info("Disconnected from DAS server")
            except Exception as e:
                print(f"⚠️  Disconnect warning: {e}")
                logger.warning(f"Disconnect warning: {e}")
    
    def get_current_positions(self):
        """Get current positions from DAS"""
        try:
            script = "GET POSITIONS\r\n"
            logger.info("Getting current positions from DAS...")
            result = self.connection.SendScript(bytearray(script, encoding="ascii"))
            
            logger.info(f"Positions result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting current positions: {e}")
            return ""
    
    def parse_positions(self, positions_raw: str):
        """Parse positions and identify those that need to be closed"""
        try:
            if not positions_raw or positions_raw.strip() == "":
                print("ℹ️  No positions found to close")
                logger.info("No positions found to close")
                return
            
            # Parse all position lines
            lines = positions_raw.split('\n')
            positions_to_close = []
            
            for line in lines:
                line = line.strip()
                if not line or not line.startswith('%POS'):
                    continue
                
                # Parse the position line
                parts = line.split()
                if len(parts) < 5:
                    continue
                
                try:
                    symbol = parts[1]  # Symbol is the second field
                    position_type_num = int(parts[2])  # Position type (2 for long, 3 for short)
                    quantity = int(parts[3])
                    avg_price = float(parts[4])
                    
                    # Only consider positions with quantity > 0
                    if quantity > 0 and avg_price > 0:
                        # Determine position type
                        if position_type_num == 2:
                            position_type = "LONG"
                        elif position_type_num == 3:
                            position_type = "SHORT"
                        else:
                            print(f"⚠️  Unknown position type {position_type_num} for {symbol}, skipping")
                            continue
                        
                        positions_to_close.append({
                            'symbol': symbol,
                            'type': position_type,
                            'quantity': quantity,
                            'avg_price': avg_price
                        })
                        
                        print(f"📊 Found {position_type} position: {symbol} {quantity} @ ${avg_price:.2f}")
                        logger.info(f"Found {position_type} position: {symbol} {quantity} @ ${avg_price:.2f}")
                    
                except (ValueError, IndexError) as e:
                    print(f"❌ Error parsing position line: {e}")
                    continue
            
            self.positions_to_close = positions_to_close
            
            if positions_to_close:
                print(f"\n📊 Total positions to close: {len(positions_to_close)}")
                logger.info(f"Total positions to close: {len(positions_to_close)}")
            else:
                print("ℹ️  No positions found to close")
                logger.info("No positions found to close")
                
        except Exception as e:
            print(f"❌ Error parsing positions: {e}")
            logger.error(f"Error parsing positions: {e}")
    
    def close_position_at_market(self, symbol: str, position_type: str, quantity: int):
        """Close a position at market price"""
        try:
            print(f"   🚪 Closing {position_type} position: {symbol} {quantity}")
            logger.info(f"Closing {position_type} position: {symbol} {quantity}")
            
            # Generate unique ID for the order
            unID = int(self.cmd.uniq)
            
            # Place market order to close position
            if position_type == "LONG":
                # Sell to close long position
                script = f"NEWORDER {unID} S {symbol.upper()} SMAT {quantity} MKT"
                print(f"      📋 Selling to close long position")
            else:
                # Buy to close short position
                script = f"NEWORDER {unID} B {symbol.upper()} SMAT {quantity} MKT"
                print(f"      📋 Buying to close short position")
            
            print(f"      📡 Sending command: {script}")
            logger.info(f"Sending command: {script}")
            
            result = self.connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
            print(f"      📋 Order result: {result}")
            logger.info(f"Order result: {result}")
            
            if "SUCCESS" in result.upper() or "ACCEPTED" in result.upper():
                print(f"      ✅ Position closed successfully!")
                logger.info(f"Position closed successfully: {symbol} {position_type}")
                return True
            else:
                print(f"      ❌ Order failed: {result}")
                logger.error(f"Order failed for {symbol}: {result}")
                return False
                
        except Exception as e:
            print(f"      ❌ Error closing position: {e}")
            logger.error(f"Error closing position for {symbol}: {e}")
            return False
    
    def execute_panic_exit(self):
        """Execute the panic exit - close all positions at market"""
        try:
            print("\n🚨 EXECUTING PANIC EXIT")
            print("="*50)
            logger.info("Executing panic exit - closing all positions at market")
            
            if not self.positions_to_close:
                print("ℹ️  No positions to close")
                logger.info("No positions to close")
                return
            
            print(f"📊 Closing {len(self.positions_to_close)} positions...")
            
            successful_closes = 0
            failed_closes = 0
            
            for i, position in enumerate(self.positions_to_close, 1):
                print(f"\n[{i}/{len(self.positions_to_close)}] Processing {position['symbol']}...")
                
                success = self.close_position_at_market(
                    position['symbol'],
                    position['type'],
                    position['quantity']
                )
                
                if success:
                    successful_closes += 1
                else:
                    failed_closes += 1
                
                # Small delay between orders to avoid overwhelming the system
                time.sleep(0.5)
            
            print(f"\n📊 Panic exit completed!")
            print(f"   ✅ Successfully closed: {successful_closes}")
            print(f"   ❌ Failed to close: {failed_closes}")
            print(f"   📊 Total processed: {len(self.positions_to_close)}")
            
            logger.info(f"Panic exit completed - Success: {successful_closes}, Failed: {failed_closes}")
            
        except Exception as e:
            print(f"❌ Error during panic exit: {e}")
            logger.error(f"Error during panic exit: {e}")
    
    def run(self):
        """Main execution method"""
        try:
            # Step 1: Connect to DAS
            self.connect_to_das()
            
            # Step 2: Get current positions
            positions_raw = self.get_current_positions()
            
            # Step 3: Parse positions
            self.parse_positions(positions_raw)
            
            # Step 4: Execute panic exit
            self.execute_panic_exit()
            
        except KeyboardInterrupt:
            print("\n🛑 Panic exit interrupted by user")
            logger.info("Panic exit interrupted by user")
        except Exception as e:
            print(f"\n❌ Error in panic exit: {e}")
            logger.error(f"Error in panic exit: {e}")
        finally:
            self.disconnect_from_das()

def main():
    """Main function to run the panic exit"""
    print("🚨 PANIC EXIT - EMERGENCY POSITION CLOSURE")
    print("="*80)
    print("This script will:")
    print("1. Connect to DAS server")
    print("2. Get all current positions")
    print("3. Close ALL positions at market price immediately")
    print("4. Log all actions for audit trail")
    print("="*80)
    print("⚠️  WARNING: This action cannot be undone!")
    print("="*80)
    
    try:
        # Create and run the panic exit
        panic_exit = PanicExit()
        panic_exit.run()
        
    except Exception as e:
        logger.error(f"Error running panic exit: {e}")
        print(f"\n❌ FATAL ERROR: {e}")
        print("The panic exit has encountered an error and will exit.")
    
    print("\n🎉 Panic exit completed!")
    print("Check the log file for detailed results.")

if __name__ == "__main__":
    main()
