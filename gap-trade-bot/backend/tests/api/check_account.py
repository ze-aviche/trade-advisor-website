#!/usr/bin/env python3
"""Check Alpaca account information"""

from bot.alpaca_client import AlpacaClient

def main():
    client = AlpacaClient()
    
    print("=== Alpaca Account Information ===")
    
    # Get account info
    account = client.get_account_info()
    print(f"Cash: ${account.get('cash', 0):.2f}")
    print(f"Portfolio Value: ${account.get('portfolio_value', 0):.2f}")
    print(f"Equity: ${account.get('equity', 0):.2f}")
    print(f"Buying Power: ${account.get('buying_power', 0):.2f}")
    
    # Get positions
    positions = client.get_positions()
    print(f"\n=== Current Positions ({len(positions)}) ===")
    for ticker, pos in positions.items():
        print(f"{ticker}: {pos['quantity']} shares @ ${pos['avg_entry_price']:.2f} (P&L: ${pos['unrealized_pl']:.2f})")
    
    # Get orders
    orders = client.trading_client.get_orders() if client.trading_client else []
    print(f"\n=== Current Orders ({len(orders)}) ===")
    for order in orders:
        print(f"{order.symbol}: {order.qty} {order.side} @ ${order.limit_price or 'market'} ({order.status})")

if __name__ == "__main__":
    main() 