#!/usr/bin/env python3
"""
Import DAS Trades Script
Demonstrates how to import trades from DAS Trader
"""
import sys
import os

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_manager
from das_integration import das_trade_manager

def import_sample_das_data():
    """Import sample DAS trades data"""
    print("📊 Importing Sample DAS Trades Data")
    print("=" * 50)
    
    # Sample DAS trades data (you can replace this with actual data from DAS)
    sample_das_data = """#Trade id symb B/S qty price 
route time orderid Liq EcnFee PL 
%TRADE 1 MSFT B 100 28.3 
SMAT 18:00:31 3 
%TRADE 2 MSFT B 100 28.31 
SMAT 18:01:19 4 
%TRADE 3 DELL SS 100 14.75 
SMAT 18:02:17 5 
%TRADE 4 AAPL B 50 150.25
SMAT 14:30:15 6
%TRADE 5 GOOGL S 25 2500.75
SMAT 15:45:22 7
#TradeEnd"""
    
    print("Sample DAS data:")
    print(sample_das_data)
    print()
    
    # Import the data
    success, message, added_count = das_trade_manager.import_das_trades_text(sample_das_data)
    
    if success:
        print(f"✅ {message}")
        print(f"📈 Added {added_count} trades to database")
    else:
        print(f"❌ Import failed: {message}")
    
    return success

def sync_from_das():
    """Sync trades from DAS Trader (requires DAS to be running)"""
    print("\n🔄 Syncing Trades from DAS Trader")
    print("=" * 50)
    
    print("⚠️  This requires DAS Trader to be running and connected")
    print("⚠️  Make sure DAS Trader is open and you're logged in")
    
    response = input("\nDo you want to attempt to sync from DAS? (y/n): ").lower()
    
    if response == 'y':
        try:
            success, message, added_count = das_trade_manager.sync_trades_from_das()
            
            if success:
                print(f"✅ {message}")
                if added_count > 0:
                    print(f"📈 Synced {added_count} trades from DAS")
                else:
                    print("ℹ️  No new trades found in DAS")
            else:
                print(f"❌ Sync failed: {message}")
                print("💡 Make sure DAS Trader is running and you're connected")
        except Exception as e:
            print(f"❌ Error syncing from DAS: {e}")
    else:
        print("⏭️  Skipping DAS sync")

def view_trade_history():
    """View current trade history"""
    print("\n📋 Current Trade History")
    print("=" * 50)
    
    trades = db_manager.get_trades(limit=20)
    
    if not trades:
        print("No trades found in database")
        return
    
    print(f"Found {len(trades)} trades:")
    print()
    print(f"{'ID':<4} {'Symbol':<8} {'Side':<4} {'Qty':<6} {'Price':<10} {'Date':<12} {'Time':<10}")
    print("-" * 70)
    
    for trade in trades:
        print(f"{trade['trade_id']:<4} {trade['symbol']:<8} {trade['side']:<4} "
              f"{trade['quantity']:<6} ${trade['price']:<9} {trade['trade_date']:<12} {trade['trade_time']:<10}")

def view_trade_summary():
    """View trade summary statistics"""
    print("\n📊 Trade Summary Statistics")
    print("=" * 50)
    
    summary = db_manager.get_trade_summary()
    
    if not summary:
        print("No trade data available for summary")
        return
    
    print(f"Total Trades: {summary['total_trades']}")
    print(f"Total Buy Quantity: {summary['total_buy_quantity']}")
    print(f"Total Sell Quantity: {summary['total_sell_quantity']}")
    print(f"Net Quantity: {summary['net_quantity']}")
    print(f"Total Buy Value: ${summary['total_buy_value']:.2f}")
    print(f"Total Sell Value: ${summary['total_sell_value']:.2f}")
    print(f"Net Value: ${summary['net_value']:.2f}")
    print(f"Total P&L: ${summary['total_pnl']:.2f}")
    print(f"Total Fees: ${summary['total_fees']:.2f}")
    
    if summary['total_buy_quantity'] > 0:
        print(f"Average Buy Price: ${summary['avg_buy_price']:.2f}")
    if summary['total_sell_quantity'] > 0:
        print(f"Average Sell Price: ${summary['avg_sell_price']:.2f}")

def main():
    """Main function"""
    print("🚀 DAS Trades Import Tool")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. Import sample DAS data")
        print("2. Sync from DAS Trader (requires DAS to be running)")
        print("3. View trade history")
        print("4. View trade summary")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == '1':
            import_sample_das_data()
        elif choice == '2':
            sync_from_das()
        elif choice == '3':
            view_trade_history()
        elif choice == '4':
            view_trade_summary()
        elif choice == '5':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-5.")

if __name__ == "__main__":
    main()
