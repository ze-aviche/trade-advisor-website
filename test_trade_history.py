#!/usr/bin/env python3
"""
Test script for Trade History functionality
"""
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'gap-trade-bot', 'backend'))

def test_database_creation():
    """Test database table creation"""
    try:
        from database import db_manager
        
        print("✅ Database manager imported successfully")
        
        # Test adding a sample trade
        sample_trade = {
            'trade_id': 1,
            'symbol': 'AAPL',
            'side': 'B',
            'quantity': 100,
            'price': 150.25,
            'route': 'SMAT',
            'trade_time': '14:30:00',
            'order_id': 12345,
            'liquidity': 'M',
            'ecn_fee': 0.50,
            'pnl': 0.0,
            'trade_date': '2024-01-15'
        }
        
        success, message = db_manager.add_trade(sample_trade)
        if success:
            print(f"✅ Sample trade added: {message}")
        else:
            print(f"❌ Failed to add sample trade: {message}")
        
        # Test getting trades
        trades = db_manager.get_trades(limit=10)
        print(f"✅ Retrieved {len(trades)} trades from database")
        
        # Test getting summary
        summary = db_manager.get_trade_summary()
        if summary:
            print(f"✅ Trade summary: {summary}")
        else:
            print("⚠️ No trade summary available")
            
    except Exception as e:
        print(f"❌ Error testing database: {e}")

def test_das_parsing():
    """Test DAS trades data parsing"""
    try:
        from database import db_manager
        
        # Sample DAS trades data
        das_data = """#Trade id symb B/S qty price 
route time orderid Liq EcnFee PL 
%TRADE 1 MSFT B 100 28.3 
SMAT 18:00:31 3 
%TRADE 2 MSFT B 100 28.31 
SMAT 18:01:19 4 
%TRADE 3 DELL SS 100 14.75 
SMAT 18:02:17 5 
#TradeEnd"""
        
        trades = db_manager.parse_das_trades_data(das_data)
        print(f"✅ Parsed {len(trades)} trades from DAS data")
        
        for i, trade in enumerate(trades, 1):
            print(f"  Trade {i}: {trade['symbol']} {trade['side']} {trade['quantity']} @ {trade['price']}")
            
    except Exception as e:
        print(f"❌ Error testing DAS parsing: {e}")

def test_das_integration():
    """Test DAS integration (without actual connection)"""
    try:
        from das_integration import DASTradeManager
        
        manager = DASTradeManager()
        print("✅ DAS Trade Manager created successfully")
        
        # Test parsing without connection
        sample_response = """%TRADE 1 AAPL B 50 150.25
%TRADE 2 MSFT S 100 300.00
%TRADE 3 GOOGL B 25 2500.75"""
        
        trades = manager.parse_das_trades_response(sample_response)
        print(f"✅ Parsed {len(trades)} trades from sample response")
        
    except Exception as e:
        print(f"❌ Error testing DAS integration: {e}")

def main():
    """Run all tests"""
    print("🧪 Testing Trade History Functionality")
    print("=" * 50)
    
    print("\n1. Testing Database Creation...")
    test_database_creation()
    
    print("\n2. Testing DAS Data Parsing...")
    test_das_parsing()
    
    print("\n3. Testing DAS Integration...")
    test_das_integration()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main()
