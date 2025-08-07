#!/usr/bin/env python3
"""
Test script for position sync functionality
"""
import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

def test_position_sync():
    """Test position sync from Alpaca to local database"""
    try:
        print("🧪 Testing Position Sync")
        print("=" * 50)
        
        # Import required modules
        from bot.trading_database import TradingDatabase
        from bot.alpaca_client import AlpacaClient
        
        # Initialize clients
        trading_db = TradingDatabase()
        alpaca_client = AlpacaClient()
        
        if not alpaca_client.trading_client:
            print("❌ Alpaca client not initialized")
            return False
        
        print("✅ Alpaca client initialized")
        
        # Get current positions from Alpaca
        try:
            alpaca_positions = alpaca_client.get_positions()
            print(f"📊 Found {len(alpaca_positions)} positions in Alpaca")
            
            for symbol, pos in alpaca_positions.items():
                print(f"   - {symbol}: {pos['quantity']} shares @ ${pos['avg_entry_price']}")
                
        except Exception as e:
            print(f"❌ Error getting positions from Alpaca: {e}")
            return False
        
        # Get positions from local database before sync
        db_positions_before = trading_db.get_all_positions()
        print(f"📊 Found {len(db_positions_before)} positions in local database before sync")
        
        # Sync positions from Alpaca
        print("🔄 Syncing positions from Alpaca...")
        sync_result = trading_db.sync_trades_from_alpaca(alpaca_client)
        
        if sync_result['success']:
            print(f"✅ Sync completed: {sync_result['synced_count']} new trades/positions")
            print(f"   Skipped: {sync_result['skipped_count']}, Errors: {sync_result['error_count']}")
        else:
            print(f"❌ Sync failed: {sync_result.get('error', 'Unknown error')}")
            return False
        
        # Get positions from local database after sync
        db_positions_after = trading_db.get_all_positions()
        print(f"📊 Found {len(db_positions_after)} positions in local database after sync")
        
        # Show the positions
        for pos in db_positions_after:
            print(f"   - {pos['ticker']}: {pos['quantity']} shares @ ${pos['entry_price']} ({pos['side']})")
        
        print("\n✅ Position sync test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error in position sync test: {e}")
        return False

def test_bot_status_endpoint():
    """Test the bot status endpoint"""
    try:
        print("\n🧪 Testing Bot Status Endpoint")
        print("=" * 50)
        
        # Import the Flask app
        from app import app
        
        with app.test_client() as client:
            response = client.get('/api/bot/status')
            
            if response.status_code == 200:
                data = response.get_json()
                positions = data.get('positions', [])
                print(f"📊 Bot status endpoint returned {len(positions)} positions")
                
                for pos in positions:
                    print(f"   - {pos['ticker']}: {pos['quantity']} shares @ ${pos['entryPrice']} (P&L: ${pos['pnl']})")
                
                print("✅ Bot status endpoint test completed successfully!")
                return True
            else:
                print(f"❌ Bot status endpoint failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Error in bot status endpoint test: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Position Sync and Bot Status")
    print("=" * 60)
    
    # Test position sync
    if not test_position_sync():
        return False
    
    # Test bot status endpoint
    if not test_bot_status_endpoint():
        return False
    
    print("\n🎉 All tests passed! Position sync is working correctly.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 