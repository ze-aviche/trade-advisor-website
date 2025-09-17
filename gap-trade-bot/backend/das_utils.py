#!/usr/bin/env python3
"""
DAS Pro Utility Functions
Helper functions for DAS Pro operations and management
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logging_config import get_logger
from start_das_pro import DASProManager

logger = get_logger('das_utils')

class DASUtils:
    """Utility functions for DAS Pro operations"""
    
    def __init__(self):
        self.das_manager = DASProManager()
    
    def quick_start(self) -> bool:
        """Quick start DAS Pro with minimal output"""
        try:
            logger.info("🚀 Quick starting DAS Pro...")
            return self.das_manager.start_and_connect()
        except Exception as e:
            logger.error(f"❌ Quick start failed: {e}")
            return False
    
    def check_das_status(self) -> Dict[str, Any]:
        """Check current DAS Pro status"""
        status = self.das_manager.get_status()
        
        # Add additional status information
        status.update({
            "timestamp": datetime.now().isoformat(),
            "config_file_exists": os.path.exists(self.das_manager.config_file),
            "config_file_path": self.das_manager.config_file
        })
        
        return status
    
    def get_account_info(self) -> Optional[str]:
        """Get account information from DAS Pro"""
        try:
            if not self.das_manager.is_connected:
                logger.error("❌ Not connected to DAS Pro")
                return None
            
            script = "GET AccountInfo\r\n"
            response = self.das_manager.connection.SendScript(bytearray(script, encoding="ascii"))
            return response
        except Exception as e:
            logger.error(f"❌ Error getting account info: {e}")
            return None
    
    def get_positions(self) -> Optional[str]:
        """Get current positions from DAS Pro"""
        try:
            if not self.das_manager.is_connected:
                logger.error("❌ Not connected to DAS Pro")
                return None
            
            script = "GET POSITIONS\r\n"
            response = self.das_manager.connection.SendScript(bytearray(script, encoding="ascii"))
            return response
        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
            return None
    
    def get_orders(self) -> Optional[str]:
        """Get current orders from DAS Pro"""
        try:
            if not self.das_manager.is_connected:
                logger.error("❌ Not connected to DAS Pro")
                return None
            
            script = "GET ORDERS\r\n"
            response = self.das_manager.connection.SendScript(bytearray(script, encoding="ascii"))
            return response
        except Exception as e:
            logger.error(f"❌ Error getting orders: {e}")
            return None
    
    def get_trades(self) -> Optional[str]:
        """Get recent trades from DAS Pro"""
        try:
            if not self.das_manager.is_connected:
                logger.error("❌ Not connected to DAS Pro")
                return None
            
            script = "GET TRADES\r\n"
            response = self.das_manager.connection.SendScript(bytearray(script, encoding="ascii"))
            return response
        except Exception as e:
            logger.error(f"❌ Error getting trades: {e}")
            return None
    
    def get_buying_power(self) -> Optional[str]:
        """Get buying power from DAS Pro"""
        try:
            if not self.das_manager.is_connected:
                logger.error("❌ Not connected to DAS Pro")
                return None
            
            script = "GET BP\r\n"
            response = self.das_manager.connection.SendScript(bytearray(script, encoding="ascii"))
            return response
        except Exception as e:
            logger.error(f"❌ Error getting buying power: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test DAS Pro connection"""
        try:
            if not self.das_manager.is_connected:
                logger.error("❌ Not connected to DAS Pro")
                return False
            
            return self.das_manager.test_connection()
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def restart_das(self) -> bool:
        """Restart DAS Pro (stop and start)"""
        try:
            logger.info("🔄 Restarting DAS Pro...")
            
            # Disconnect and stop
            self.das_manager.disconnect()
            self.das_manager.stop_das_pro()
            
            # Wait a moment
            time.sleep(3)
            
            # Start and connect again
            return self.das_manager.start_and_connect()
        except Exception as e:
            logger.error(f"❌ Error restarting DAS Pro: {e}")
            return False
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """Update DAS configuration"""
        try:
            # Merge with existing config
            self.das_manager.config.update(new_config)
            self.das_manager.save_config()
            logger.info("✅ Configuration updated successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating configuration: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get current DAS configuration"""
        return self.das_manager.config.copy()
    
    def export_status_report(self, filename: Optional[str] = None) -> str:
        """Export a comprehensive status report"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"das_status_report_{timestamp}.json"
            
            report = {
                "timestamp": datetime.now().isoformat(),
                "status": self.check_das_status(),
                "account_info": self.get_account_info(),
                "positions": self.get_positions(),
                "orders": self.get_orders(),
                "trades": self.get_trades(),
                "buying_power": self.get_buying_power(),
                "connection_test": self.test_connection()
            }
            
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"✅ Status report exported to: {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ Error exporting status report: {e}")
            return ""

def main():
    """Main function for utility operations"""
    print("🔧 DAS Pro Utility Functions")
    print("=" * 50)
    
    utils = DASUtils()
    
    while True:
        print("\nSelect an operation:")
        print("1. Check DAS Status")
        print("2. Quick Start DAS Pro")
        print("3. Get Account Info")
        print("4. Get Positions")
        print("5. Get Orders")
        print("6. Get Trades")
        print("7. Get Buying Power")
        print("8. Test Connection")
        print("9. Restart DAS Pro")
        print("10. Export Status Report")
        print("11. Update Configuration")
        print("0. Exit")
        
        choice = input("\nEnter your choice (0-11): ").strip()
        
        try:
            if choice == "1":
                status = utils.check_das_status()
                print(f"\n📊 DAS Status:")
                print(json.dumps(status, indent=2))
                
            elif choice == "2":
                if utils.quick_start():
                    print("✅ DAS Pro started successfully!")
                else:
                    print("❌ Failed to start DAS Pro")
                    
            elif choice == "3":
                info = utils.get_account_info()
                if info:
                    print(f"\n📋 Account Info:\n{info}")
                else:
                    print("❌ Failed to get account info")
                    
            elif choice == "4":
                positions = utils.get_positions()
                if positions:
                    print(f"\n📈 Positions:\n{positions}")
                else:
                    print("❌ Failed to get positions")
                    
            elif choice == "5":
                orders = utils.get_orders()
                if orders:
                    print(f"\n📝 Orders:\n{orders}")
                else:
                    print("❌ Failed to get orders")
                    
            elif choice == "6":
                trades = utils.get_trades()
                if trades:
                    print(f"\n💼 Trades:\n{trades}")
                else:
                    print("❌ Failed to get trades")
                    
            elif choice == "7":
                bp = utils.get_buying_power()
                if bp:
                    print(f"\n💰 Buying Power:\n{bp}")
                else:
                    print("❌ Failed to get buying power")
                    
            elif choice == "8":
                if utils.test_connection():
                    print("✅ Connection test successful!")
                else:
                    print("❌ Connection test failed")
                    
            elif choice == "9":
                if utils.restart_das():
                    print("✅ DAS Pro restarted successfully!")
                else:
                    print("❌ Failed to restart DAS Pro")
                    
            elif choice == "10":
                filename = utils.export_status_report()
                if filename:
                    print(f"✅ Status report exported to: {filename}")
                else:
                    print("❌ Failed to export status report")
                    
            elif choice == "11":
                print("\nCurrent configuration:")
                config = utils.get_config()
                print(json.dumps(config, indent=2))
                
                print("\nEnter new configuration (JSON format):")
                new_config_str = input("> ")
                try:
                    new_config = json.loads(new_config_str)
                    if utils.update_config(new_config):
                        print("✅ Configuration updated!")
                    else:
                        print("❌ Failed to update configuration")
                except json.JSONDecodeError:
                    print("❌ Invalid JSON format")
                    
            elif choice == "0":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice, please try again")
                
        except KeyboardInterrupt:
            print("\n👋 Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
