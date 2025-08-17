#!/usr/bin/env python3
"""
Test DAS Trader Connection
Simple script to test if DAS Trader is accessible
"""

import socket
import time

def test_das_connection():
    """Test connection to DAS Trader"""
    print("🧪 Testing DAS Trader Connection...")
    
    try:
        # Try to connect to DAS Trader
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        print("📡 Attempting to connect to DAS Trader (127.0.0.1:9800)...")
        sock.connect(('127.0.0.1', 9800))
        print("✅ Successfully connected to DAS Trader!")
        
        # Try to send a simple command
        print("📤 Sending test command...")
        sock.sendall(b'GET TRADES\r\n')
        time.sleep(0.5)
        
        # Try to read response
        try:
            response = sock.recv(1024).decode('ascii')
            print(f"📥 Received response: {response[:200]}...")
        except Exception as e:
            print(f"⚠️ Could not read response: {e}")
        
        sock.close()
        print("✅ DAS Trader connection test completed successfully!")
        return True
        
    except ConnectionRefusedError:
        print("❌ Connection refused - DAS Trader is not running or not listening on port 9800")
        print("💡 Make sure DAS Trader is running and CMD API is enabled")
        return False
        
    except socket.timeout:
        print("❌ Connection timeout - DAS Trader is not responding")
        return False
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    test_das_connection()
