#!/usr/bin/env python3
"""
Force sync positions from DAS to fix database sync issues
"""
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def force_sync_positions():
    """Force sync positions from DAS to database"""
    try:
        print("🔄 Starting forced position sync from DAS...")
        
        # Import required modules
        from das_integration import das_trade_manager
        from database import db_manager
        
        # Check DAS connection
        if not das_trade_manager.das_connection.connected:
            print("🔌 Connecting to DAS...")
            if not das_trade_manager.connect_to_das():
                print("❌ Failed to connect to DAS")
                return False
        
        # Get current positions from DAS
        print("📡 Fetching positions from DAS...")
        das_response = das_trade_manager.das_connection.get_positions()
        
        if not das_response:
            print("❌ No response from DAS")
            return False
        
        print(f"📊 Raw DAS response: {das_response[:200]}...")
        
        # Parse positions from DAS
        positions = das_trade_manager.parse_das_positions_response(das_response)
        
        if not positions:
            print("ℹ️ No positions found in DAS")
            return True
        
        print(f"📋 Found {len(positions)} positions in DAS:")
        for pos in positions:
            print(f"  - {pos['symbol']}: {pos['quantity']} @ ${pos['avg_cost']:.2f}")
        
        # Clear existing current positions only (preserve historical data)
        print("🗑️ Clearing existing current positions from database...")
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM positions")
            conn.commit()
            print("✅ Cleared existing current positions (preserved historical data)")
        
        # Sync positions to database
        print("💾 Syncing positions to database...")
        updated_count = 0
        errors = []
        
        for position in positions:
            success, message = db_manager.upsert_position(position)
            if success:
                updated_count += 1
                print(f"✅ Synced: {position['symbol']}")
            else:
                errors.append(f"Position {position['symbol']}: {message}")
                print(f"❌ Failed: {position['symbol']} - {message}")
        
        # Show results
        print(f"\n📊 Sync Results:")
        print(f"  ✅ Successfully synced: {updated_count} positions")
        if errors:
            print(f"  ❌ Errors: {len(errors)}")
            for error in errors:
                print(f"    - {error}")
        
        # Verify sync
        print("\n🔍 Verifying sync...")
        db_positions = db_manager.get_positions()
        print(f"📋 Database now contains {len(db_positions)} positions:")
        for pos in db_positions:
            print(f"  - {pos['symbol']}: {pos['quantity']} @ ${pos['avg_cost']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during force sync: {e}")
        return False

def main():
    """Main function"""
    print("🚀 DAS Position Force Sync Tool")
    print("=" * 40)
    
    success = force_sync_positions()
    
    if success:
        print("\n✅ Force sync completed successfully!")
    else:
        print("\n❌ Force sync failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
