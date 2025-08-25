#!/usr/bin/env python3
"""
Reset positions database and resync from DAS
Use this when positions are completely out of sync
"""
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def reset_positions_database():
    """Reset positions database and resync from DAS"""
    try:
        print("🔄 Starting positions database reset and resync...")
        
        # Import required modules
        from database import db_manager
        from das_integration import das_trade_manager
        
        # Backup current positions (optional)
        print("💾 Backing up current positions...")
        current_positions = db_manager.get_positions()
        if current_positions:
            print(f"📋 Found {len(current_positions)} current positions to backup")
            for pos in current_positions:
                print(f"  - {pos['symbol']}: {pos['quantity']} @ ${pos['avg_cost']:.2f}")
        
        # Reset only current positions table (preserve historical data)
        print("🗑️ Resetting current positions table only...")
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Clear only current positions table
            cursor.execute("DELETE FROM positions")
            
            # Reset auto-increment counter for positions only
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='positions'")
            
            conn.commit()
            print("✅ Current positions table reset successfully (historical data preserved)")
        
        # Verify tables are empty
        print("🔍 Verifying tables are empty...")
        empty_positions = db_manager.get_positions()
        if not empty_positions:
            print("✅ Positions table is now empty")
        else:
            print(f"⚠️ Positions table still has {len(empty_positions)} records")
        
        # Connect to DAS
        print("🔌 Connecting to DAS...")
        if not das_trade_manager.das_connection.connected:
            if not das_trade_manager.connect_to_das():
                print("❌ Failed to connect to DAS")
                return False
        
        # Get fresh positions from DAS
        print("📡 Fetching fresh positions from DAS...")
        das_response = das_trade_manager.das_connection.get_positions()
        
        if not das_response:
            print("❌ No response from DAS")
            return False
        
        # Parse positions
        positions = das_trade_manager.parse_das_positions_response(das_response)
        
        if not positions:
            print("ℹ️ No positions found in DAS")
            return True
        
        print(f"📋 Found {len(positions)} positions in DAS:")
        for pos in positions:
            print(f"  - {pos['symbol']}: {pos['quantity']} @ ${pos['avg_cost']:.2f}")
        
        # Sync fresh positions to database
        print("💾 Syncing fresh positions to database...")
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
        
        # Show final results
        print(f"\n📊 Final Results:")
        print(f"  ✅ Successfully synced: {updated_count} positions")
        if errors:
            print(f"  ❌ Errors: {len(errors)}")
            for error in errors:
                print(f"    - {error}")
        
        # Final verification
        print("\n🔍 Final verification...")
        final_positions = db_manager.get_positions()
        print(f"📋 Database now contains {len(final_positions)} positions:")
        for pos in final_positions:
            print(f"  - {pos['symbol']}: {pos['quantity']} @ ${pos['avg_cost']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during database reset: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Current Positions Reset and Resync Tool")
    print("=" * 50)
    print("⚠️  This will reset your current positions only!")
    print("⚠️  Historical position data will be preserved!")
    
    response = input("\n❓ Are you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    success = reset_positions_database()
    
    if success:
        print("\n✅ Database reset and resync completed successfully!")
    else:
        print("\n❌ Database reset and resync failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
