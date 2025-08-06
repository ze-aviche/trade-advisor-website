#!/usr/bin/env python3
"""Test trades API"""

import requests
import json

def main():
    response = requests.get("http://localhost:5000/api/trades?period=30")
    data = response.json()
    
    print("=== Trade History ===")
    print(f"Success: {data.get('success')}")
    print(f"Trades found: {len(data.get('trades', []))}")
    
    for trade in data.get('trades', [])[:5]:
        print(f"{trade['ticker']}: {trade['quantity']} {trade['direction']} @ ${trade['price']} (P&L: ${trade.get('pnl', 0)})")

if __name__ == "__main__":
    main() 