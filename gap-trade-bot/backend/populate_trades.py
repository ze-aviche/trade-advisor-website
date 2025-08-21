#!/usr/bin/env python3
"""
Dedicated script to poll DAS every 10 seconds and populate trades database
with position data including Realized and Unrealized PnL values
"""
import sys
import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.trading_bot import Connection, PositionParser
from database import db_manager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('populate_trades.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradePopulator:
    """Dedicated class to poll DAS and populate trades database"""
    
    def __init__(self):
        self.connection: Optional[Connection] = None
        self.poll_interval = 10  # Poll every 10 seconds
        self.is_running = False
        
        # Track last known realized PnL per symbol to detect changes
        self.last_realized_pnl: Dict[str, float] = {}
        
        # Track position history to detect new positions
        self.position_history: Dict[str, Dict] = {}
    
    def connect_to_das(self) -> bool:
        """Connect to DAS Trader"""
        try:
            logger.info("Connecting to DAS server...")
            self.connection = Connection()
            success = self.connection.ConnectToServer()
            
            if success:
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
        if self.connection:
            try:
                self.connection.Disconnect()
                logger.info("✅ Disconnected from DAS server")
            except Exception as e:
                logger.error(f"⚠️ Disconnect warning: {e}")
            finally:
                self.connection = None
    
    def get_current_positions(self) -> str:
        """Get current positions from DAS"""
        try:
            if not self.connection:
                return ""
            
            script = "GET POSITIONS\r\n"
            result = self.connection.SendScript(bytearray(script, encoding="ascii"))
            return result
            
        except Exception as e:
            logger.error(f"Error getting current positions: {e}")
            return ""
    
    def detect_trade_changes(self, current_positions: List[Dict]) -> List[Dict]:
        """Detect changes in realized PnL and position status"""
        changes = []
        
        # Create a set of current symbols (including those with quantity = 0 for realized PnL tracking)
        current_symbols = {pos['symbol'].upper() for pos in current_positions}
        
        # Check for realized PnL changes in current positions (including closed positions)
        for position in current_positions:
            symbol = position['symbol'].upper()
            current_realized_pnl = position.get('realized_pnl', 0.0)
            
            # Check if we have a previous realized PnL for this symbol
            if symbol in self.last_realized_pnl:
                previous_realized_pnl = self.last_realized_pnl[symbol]
                
                # If realized PnL has changed, a trade occurred
                if abs(current_realized_pnl - previous_realized_pnl) > 0.01:  # Small threshold
                    pnl_change = current_realized_pnl - previous_realized_pnl
                    changes.append({
                        'type': 'realized_pnl_change',
                        'symbol': symbol,
                        'pnl_change': pnl_change,
                        'current_realized': current_realized_pnl,
                        'previous_realized': previous_realized_pnl,
                        'position': position
                    })
                    logger.info(f"Detected realized PnL change for {symbol}: ${pnl_change:.2f}")
            
            # Update the last known realized PnL (even for closed positions)
            self.last_realized_pnl[symbol] = current_realized_pnl
        
        # Check for closed positions (symbols that were in history but not in current)
        for symbol in list(self.position_history.keys()):
            if symbol not in current_symbols:
                # Position was closed
                old_position = self.position_history[symbol]
                changes.append({
                    'type': 'position_closed',
                    'symbol': symbol,
                    'old_position': old_position
                })
                logger.info(f"Detected position closed for {symbol}")
                
                # Remove from history
                del self.position_history[symbol]
        
        # Check for new positions (only those with quantity > 0)
        for position in current_positions:
            symbol = position['symbol'].upper()
            quantity = position.get('quantity', 0)
            
            # Only track as new position if quantity > 0 (active position)
            if quantity > 0 and symbol not in self.position_history:
                # New position
                changes.append({
                    'type': 'new_position',
                    'symbol': symbol,
                    'position': position
                })
                logger.info(f"Detected new position for {symbol}")
                
                # Add to history
                self.position_history[symbol] = position.copy()
        
        return changes
    
    def save_trade_change(self, change: Dict):
        """Save a detected trade change to the database"""
        try:
            if change['type'] == 'realized_pnl_change':
                # Create trade record for realized PnL change
                trade_data = {
                    'trade_id': int(time.time() * 1000) % 1000000,
                    'symbol': change['symbol'],
                    'side': 'S',  # Use 'S' for realized PnL changes (sell side)
                    'quantity': change['position'].get('quantity', 0),
                    'price': change['position'].get('avg_price', 0.0),
                    'route': 'SMAT',
                    'trade_time': datetime.now().strftime('%H:%M:%S'),
                    'order_id': 0,  # No specific order ID for detected trades
                    'liquidity': '',
                    'ecn_fee': 0.0,
                    'pnl': round(change['pnl_change'], 2),
                    'trade_date': datetime.now().date().isoformat()
                }
                
                success, message = db_manager.add_trade(trade_data)
                if success:
                    logger.info(f"💾 Saved realized PnL change trade: {change['symbol']} PnL: ${change['pnl_change']:.2f}")
                else:
                    logger.error(f"❌ Failed to save trade: {message}")
            
            elif change['type'] == 'position_closed':
                # Position was closed - could create a summary record
                logger.info(f"📊 Position closed: {change['symbol']}")
            
            elif change['type'] == 'new_position':
                # New position opened - could create an entry record
                logger.info(f"📊 New position opened: {change['symbol']}")
                
        except Exception as e:
            logger.error(f"❌ Error saving trade change: {e}")
    
    def initialize_position_tracking(self):
        """Initialize position tracking with current positions"""
        try:
            logger.info("Initializing position tracking...")
            
            # Get current positions
            positions_raw = self.get_current_positions()
            if not positions_raw or positions_raw.strip() == "":
                logger.info("No positions found during initialization")
                return
            
            # Parse positions (including those with quantity = 0 for realized PnL tracking)
            positions = PositionParser.parse_positions_raw(positions_raw)
            
            # Initialize tracking for all positions (including closed ones)
            for position in positions:
                symbol = position['symbol'].upper()
                realized_pnl = position.get('realized_pnl', 0.0)
                quantity = position.get('quantity', 0)
                
                # Always track realized PnL
                self.last_realized_pnl[symbol] = realized_pnl
                
                # Only add to position history if quantity > 0 (active position)
                if quantity > 0:
                    self.position_history[symbol] = position.copy()
                    logger.info(f"Initialized tracking for {symbol}: Active position, Realized PnL ${realized_pnl:.2f}")
                else:
                    logger.info(f"Initialized tracking for {symbol}: Closed position, Realized PnL ${realized_pnl:.2f}")
            
            logger.info(f"Position tracking initialized for {len(positions)} symbols")
            
        except Exception as e:
            logger.error(f"Error initializing position tracking: {e}")
    
    def poll_and_populate(self):
        """Main polling loop"""
        logger.info("🔄 Starting trade population polling...")
        
        while self.is_running:
            try:
                # Get current positions from DAS
                positions_raw = self.get_current_positions()
                
                if positions_raw and positions_raw.strip():
                    # Parse positions
                    positions = PositionParser.parse_positions_raw(positions_raw)
                    
                    # Detect changes
                    changes = self.detect_trade_changes(positions)
                    
                    # Save any detected changes
                    for change in changes:
                        self.save_trade_change(change)
                    
                    # Log current status
                    if positions:
                        logger.info(f"📊 Current positions: {len(positions)}")
                        for pos in positions:
                            symbol = pos['symbol']
                            realized = pos.get('realized_pnl', 0.0)
                            unrealized = pos.get('unrealized_pnl', 0.0)
                            logger.info(f"   {symbol}: Realized ${realized:.2f}, Unrealized ${unrealized:.2f}")
                    else:
                        logger.info("📊 No active positions")
                
                # Wait before next poll
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in polling loop: {e}")
                time.sleep(self.poll_interval)
    
    def start(self) -> bool:
        """Start the trade populator"""
        try:
            # Connect to DAS
            if not self.connect_to_das():
                logger.error("❌ Failed to connect to DAS, cannot start populator")
                return False
            
            # Initialize position tracking
            self.initialize_position_tracking()
            
            # Start polling
            self.is_running = True
            logger.info("✅ Trade populator started")
            
            # Start polling in main thread
            self.poll_and_populate()
            
        except KeyboardInterrupt:
            logger.info("🛑 Trade populator stopped by user")
        except Exception as e:
            logger.error(f"❌ Error starting trade populator: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the trade populator"""
        self.is_running = False
        self.disconnect_from_das()
        logger.info("✅ Trade populator stopped")

def main():
    """Main function to run the trade populator"""
    print("=== DAS Trade Populator ===")
    print("This script will poll DAS every 10 seconds to populate trades database")
    print("Press Ctrl+C to stop")
    print()
    
    populator = TradePopulator()
    populator.start()

if __name__ == "__main__":
    main()
