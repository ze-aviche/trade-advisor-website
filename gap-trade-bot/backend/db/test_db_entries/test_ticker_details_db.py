import sqlite3
import os
from datetime import datetime
from ticker_details_db import init_ticker_details_db, insert_or_update_ticker, get_ticker_details_from_db, get_db_path

def test_ticker_details_db():
    print("=" * 50)
    print("TESTING TICKER DETAILS DATABASE")
    print("=" * 50)
    
    # Initialize the database
    init_ticker_details_db()
    print("✅ Database initialized")
    
    # Test data
    test_details = {
        'ticker': 'AAPL',
        'name': 'Apple Inc.',
        'market_cap': 3000000000000,
        'sic_description': 'Computer Manufacturing',
        'list_date': '1980-12-12',
        'shares_outstanding': 15700000000,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Insert test data
    insert_or_update_ticker(test_details)
    print("✅ Test data inserted")
    
    # Query and validate the data
    retrieved_data = get_ticker_details_from_db('AAPL')
    
    if retrieved_data:
        print("\n📊 RETRIEVED DATA:")
        print(f"Ticker: {retrieved_data.get('ticker')}")
        print(f"Name: {retrieved_data.get('name')}")
        print(f"Market Cap: {retrieved_data.get('market_cap')}")
        print(f"SIC Description: {retrieved_data.get('sic_description')}")
        print(f"List Date: {retrieved_data.get('list_date')}")
        print(f"Shares Outstanding: {retrieved_data.get('share_class_shares_outstanding')}")
        print(f"Date: {retrieved_data.get('date')}")
        
        # Validate that all columns exist
        expected_columns = ['ticker', 'name', 'market_cap', 'sic_description', 'list_date', 'share_class_shares_outstanding', 'date']
        missing_columns = [col for col in expected_columns if col not in retrieved_data]
        
        if missing_columns:
            print(f"\n❌ Missing columns: {missing_columns}")
        else:
            print("\n✅ All columns present and data retrieved successfully!")
    else:
        print("❌ Failed to retrieve data")
    
    # Test with another ticker
    test_details2 = {
        'ticker': 'MSFT',
        'name': 'Microsoft Corporation',
        'market_cap': 2500000000000,
        'sic_description': 'Software Publishers',
        'list_date': '1986-03-13',
        'shares_outstanding': 7500000000,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    insert_or_update_ticker(test_details2)
    print("\n✅ Second test data inserted")
    
    # Query all data to see table structure
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('SELECT * FROM ticker_details')
    rows = c.fetchall()
    c.execute('PRAGMA table_info(ticker_details)')
    columns = c.fetchall()
    conn.close()
    
    print(f"\n📋 TABLE STRUCTURE:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    print(f"\n📊 TOTAL RECORDS: {len(rows)}")
    for row in rows:
        print(f"  {row}")

if __name__ == "__main__":
    test_ticker_details_db() 