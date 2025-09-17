#!/usr/bin/env python3
"""
DAS Pro Startup and Login Script
Automatically starts DAS Pro and establishes connection for trading operations
"""

import os
import sys
import time
import subprocess
import socket
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import json
from pathlib import Path

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logging_config import get_logger
from cmdapi.CMDAPI_PYTHON import Connection

logger = get_logger('das_startup')

class DASProManager:
    """Manages DAS Pro startup and connection"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "das_config.json"
        self.config = self.load_config()
        self.das_process = None
        self.connection = None
        self.is_connected = False
        
        # Default DAS Pro paths (Windows)
        self.default_das_paths = [
            r"C:\Program Files\DAS Trader Pro\DAS.exe",
            r"C:\Program Files (x86)\DAS Trader Pro\DAS.exe",
            r"C:\DAS\DAS.exe",
            r"C:\DAS Trader Pro\DAS.exe"
        ]
        
    def load_config(self) -> Dict[str, Any]:
        """Load DAS configuration from file or use defaults"""
        default_config = {
            "das_path": r"C:\DASTrader DEMO_x64\DasTrader64.exe",
            "host": "127.0.0.1",
            "port": 9800,
            "userid": "IDAS12181",
            "password": "Dastrader@2",
            "account": "TRIDAS12181",
            "startup_timeout": 30,
            "connection_timeout": 10,
            "retry_attempts": 3,
            "retry_delay": 2
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    default_config.update(config)
                    logger.info(f"✅ Loaded DAS config from {self.config_file}")
            else:
                logger.info(f"📝 Using default DAS config (file not found: {self.config_file})")
                self.save_config(default_config)
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}, using defaults")
            
        return default_config
    
    def save_config(self, config: Dict[str, Any] = None):
        """Save DAS configuration to file"""
        try:
            config_to_save = config or self.config
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=2)
            logger.info(f"💾 Saved DAS config to {self.config_file}")
        except Exception as e:
            logger.error(f"❌ Error saving config: {e}")
    
    def find_das_executable(self) -> Optional[str]:
        """Find DAS Pro executable on the system"""
        # Check if path is specified in config
        if self.config.get("das_path") and os.path.exists(self.config["das_path"]):
            # Check if it's a directory (shortcut folder) and look for DAS.exe inside
            if os.path.isdir(self.config["das_path"]):
                das_exe_path = os.path.join(self.config["das_path"], "DAS.exe")
                if os.path.exists(das_exe_path):
                    logger.info(f"✅ Found DAS executable at: {das_exe_path}")
                    return das_exe_path
                else:
                    logger.warning(f"⚠️ Directory found but no DAS.exe inside: {self.config['das_path']}")
            else:
                logger.info(f"✅ Found DAS at configured path: {self.config['das_path']}")
                return self.config["das_path"]
        
        # Search common installation paths
        for path in self.default_das_paths:
            if os.path.exists(path):
                logger.info(f"✅ Found DAS at: {path}")
                # Update config with found path
                self.config["das_path"] = path
                self.save_config()
                return path
        
        logger.error("❌ DAS Pro executable not found in common locations")
        logger.info("💡 Please specify the correct path in das_config.json")
        logger.info("💡 Try running: python -c \"from start_das_pro import DASProManager; DASProManager().find_das_executable()\"")
        return None
    
    def is_das_running(self) -> bool:
        """Check if DAS Pro is already running"""
        try:
            # Try to connect to DAS server
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(2)
            result = test_socket.connect_ex((self.config["host"], self.config["port"]))
            test_socket.close()
            
            if result == 0:
                logger.info("✅ DAS Pro is already running and accepting connections")
                return True
            else:
                logger.info("ℹ️ DAS Pro server not responding")
                return False
        except Exception as e:
            logger.debug(f"DAS connection test failed: {e}")
            return False
    
    def start_das_pro(self) -> bool:
        """Start DAS Pro application"""
        try:
            das_path = self.find_das_executable()
            if not das_path:
                return False
            
            if self.is_das_running():
                logger.info("✅ DAS Pro is already running")
                return True
            
            logger.info(f"🚀 Starting DAS Pro from: {das_path}")
            
            # Start DAS Pro process
            self.das_process = subprocess.Popen(
                [das_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            # Wait for DAS to start up
            startup_timeout = self.config.get("startup_timeout", 30)
            logger.info(f"⏳ Waiting for DAS Pro to start (timeout: {startup_timeout}s)...")
            
            for i in range(startup_timeout):
                time.sleep(1)
                if self.is_das_running():
                    logger.info(f"✅ DAS Pro started successfully after {i+1} seconds")
                    return True
                if i % 5 == 0 and i > 0:
                    logger.info(f"⏳ Still waiting for DAS Pro... ({i+1}/{startup_timeout}s)")
            
            logger.error(f"❌ DAS Pro failed to start within {startup_timeout} seconds")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error starting DAS Pro: {e}")
            return False
    
    def connect_to_das(self) -> bool:
        """Establish connection to DAS Pro"""
        try:
            if not self.is_das_running():
                logger.error("❌ Cannot connect - DAS Pro is not running")
                return False
            
            logger.info("🔌 Connecting to DAS Pro...")
            
            # Create connection
            self.connection = Connection()
            
            # Connect to server
            self.connection.ConnectToServer()
            
            # Test the connection
            if self.test_connection():
                self.is_connected = True
                logger.info("✅ Successfully connected to DAS Pro")
                return True
            else:
                logger.error("❌ Connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error connecting to DAS Pro: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test the DAS connection by sending a simple command"""
        try:
            if not self.connection:
                return False
            
            # Send a simple command to test connection
            test_script = "GET AccountInfo\r\n"
            response = self.connection.SendScript(bytearray(test_script, encoding="ascii"))
            
            if response and len(response.strip()) > 0:
                logger.info("✅ Connection test successful")
                logger.debug(f"Test response: {response[:100]}...")
                return True
            else:
                logger.warning("⚠️ Connection test returned empty response")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from DAS Pro"""
        try:
            if self.connection:
                self.connection.Disconnect()
                self.connection = None
                self.is_connected = False
                logger.info("✅ Disconnected from DAS Pro")
        except Exception as e:
            logger.error(f"❌ Error disconnecting: {e}")
    
    def stop_das_pro(self):
        """Stop DAS Pro process"""
        try:
            if self.das_process:
                self.das_process.terminate()
                self.das_process.wait(timeout=10)
                self.das_process = None
                logger.info("✅ DAS Pro process stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping DAS Pro: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current DAS Pro status"""
        return {
            "is_running": self.is_das_running(),
            "is_connected": self.is_connected,
            "config": {
                "host": self.config["host"],
                "port": self.config["port"],
                "userid": self.config["userid"],
                "account": self.config["account"]
            },
            "process_id": self.das_process.pid if self.das_process else None,
            "timestamp": datetime.now().isoformat()
        }
    
    def start_and_connect(self, retry_on_failure: bool = True) -> bool:
        """Complete startup sequence: start DAS Pro and connect"""
        try:
            logger.info("🚀 Starting DAS Pro startup sequence...")
            
            # Step 1: Start DAS Pro
            if not self.start_das_pro():
                if retry_on_failure:
                    logger.info("🔄 Retrying DAS Pro startup...")
                    time.sleep(5)
                    if not self.start_das_pro():
                        return False
                else:
                    return False
            
            # Step 2: Connect to DAS Pro
            retry_attempts = self.config.get("retry_attempts", 3)
            retry_delay = self.config.get("retry_delay", 2)
            
            for attempt in range(retry_attempts):
                if self.connect_to_das():
                    logger.info("🎉 DAS Pro startup and connection completed successfully!")
                    return True
                
                if attempt < retry_attempts - 1:
                    logger.warning(f"⚠️ Connection attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
            
            logger.error("❌ Failed to connect to DAS Pro after all retry attempts")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error in startup sequence: {e}")
            return False

def main():
    """Main function for standalone execution"""
    print("🚀 DAS Pro Startup Script")
    print("=" * 50)
    
    # Create DAS manager
    das_manager = DASProManager()
    
    try:
        # Show current status
        status = das_manager.get_status()
        print(f"📊 Current Status:")
        print(f"   DAS Running: {status['is_running']}")
        print(f"   Connected: {status['is_connected']}")
        print(f"   Host: {status['config']['host']}:{status['config']['port']}")
        print(f"   User: {status['config']['userid']}")
        print()
        
        # Start and connect
        if das_manager.start_and_connect():
            print("✅ DAS Pro is ready for trading!")
            
            # Show final status
            final_status = das_manager.get_status()
            print(f"📊 Final Status:")
            print(f"   DAS Running: {final_status['is_running']}")
            print(f"   Connected: {final_status['is_connected']}")
            print(f"   Process ID: {final_status['process_id']}")
            
            # Keep connection alive for testing
            print("\n⏳ Keeping connection alive for 30 seconds for testing...")
            print("   Press Ctrl+C to exit early")
            
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                print("\n👋 Exiting...")
            
        else:
            print("❌ Failed to start DAS Pro")
            return 1
            
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1
    finally:
        # Cleanup
        das_manager.disconnect()
        print("🧹 Cleanup completed")
    
    return 0

if __name__ == "__main__":
    exit(main())
