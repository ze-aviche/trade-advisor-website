#!/usr/bin/env python3
"""Test unsubscribe functionality"""

import requests
import json

def main():
    print("🔄 Testing unsubscribe functionality...")
    
    # Test 1: Check current bot status
    print("\n=== Test 1: Current Bot Status ===")
    response1 = requests.get("http://localhost:5000/api/bot/status")
    data1 = response1.json()
    subscribed_stocks = [stock['ticker'] for stock in data1.get('subscribed_stocks', [])]
    print(f"Currently subscribed stocks: {subscribed_stocks}")
    
    if not subscribed_stocks:
        print("❌ No stocks to unsubscribe from")
        return
    
    # Test 2: Unsubscribe from first stock
    test_stock = subscribed_stocks[0]
    print(f"\n=== Test 2: Unsubscribe from {test_stock} ===")
    response2 = requests.post("http://localhost:5000/api/bot/unsubscribe-stocks", 
                             json={"stocks": [test_stock]})
    data2 = response2.json()
    print(f"Unsubscribe result: {data2.get('success')}")
    print(f"Message: {data2.get('message')}")
    
    # Test 3: Check updated bot status
    print(f"\n=== Test 3: Updated Bot Status ===")
    response3 = requests.get("http://localhost:5000/api/bot/status")
    data3 = response3.json()
    updated_stocks = [stock['ticker'] for stock in data3.get('subscribed_stocks', [])]
    print(f"Updated subscribed stocks: {updated_stocks}")
    
    # Test 4: Unsubscribe from multiple stocks
    if len(subscribed_stocks) > 1:
        test_stocks = subscribed_stocks[1:3]  # Take next 2 stocks
        print(f"\n=== Test 4: Unsubscribe from multiple stocks {test_stocks} ===")
        response4 = requests.post("http://localhost:5000/api/bot/unsubscribe-stocks", 
                                 json={"stocks": test_stocks})
        data4 = response4.json()
        print(f"Multiple unsubscribe result: {data4.get('success')}")
        print(f"Message: {data4.get('message')}")
    
    print("\n✅ Unsubscribe test completed!")

if __name__ == "__main__":
    main() 