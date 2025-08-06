#!/usr/bin/env python3

import sys
import os

# Add parent directories to path to reach the bot module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bot.alpaca_client import AlpacaClient

def test_positions():
    """Test current position retrieval and formatting"""
    
    print("📊 Testing Position Retrieval")
    print("=" * 40)
    
    try:
        # Initialize Alpaca client
        alpaca_client = AlpacaClient()
        
        # Get account info
        account_info = alpaca_client.get_account_info()
        print(f"📈 Account Info:")
        print(f"   Portfolio Value: ${account_info.get('portfolio_value', 0):,.2f}")
        print(f"   Buying Power: ${account_info.get('buying_power', 0):,.2f}")
        print(f"   Cash: ${account_info.get('cash', 0):,.2f}")
        print()
        
        # Get current positions
        positions = alpaca_client.get_positions()
        print(f"📋 Current Positions ({len(positions)}):")
        
        if not positions:
            print("   No open positions")
        else:
            for position in positions:
                ticker = position.get('symbol', 'Unknown')
                quantity = position.get('qty', 0)
                avg_entry = position.get('avg_entry_price', 0)
                current_price = position.get('current_price', 0)
                market_value = position.get('market_value', 0)
                unrealized_pl = position.get('unrealized_pl', 0)
                unrealized_plpc = position.get('unrealized_plpc', 0)
                
                print(f"   {ticker}:")
                print(f"     Quantity: {quantity:,} shares")
                print(f"     Avg Entry: ${avg_entry:.2f}")
                print(f"     Current Price: ${current_price:.2f}")
                print(f"     Market Value: ${market_value:,.2f}")
                print(f"     Unrealized P&L: ${unrealized_pl:,.2f} ({unrealized_plpc:.2f}%)")
                print()
        
        # Test position formatting for frontend
        print("🖥️ Testing Frontend Position Formatting:")
        formatted_positions = []
        
        for position in positions:
            formatted_position = {
                'ticker': position.get('symbol', 'Unknown'),
                'quantity': int(float(position.get('qty', 0))),
                'avg_entry_price': float(position.get('avg_entry_price', 0)),
                'current_price': float(position.get('current_price', 0)),
                'market_value': float(position.get('market_value', 0)),
                'unrealized_pl': float(position.get('unrealized_pl', 0)),
                'unrealized_plpc': float(position.get('unrealized_plpc', 0))
            }
            formatted_positions.append(formatted_position)
        
        print(f"   Formatted {len(formatted_positions)} positions for frontend")
        
        # Test position validation
        print("\n🔍 Testing Position Validation:")
        for position in formatted_positions:
            ticker = position['ticker']
            quantity = position['quantity']
            market_value = position['market_value']
            
            # Basic validation
            is_valid = (
                quantity > 0 and 
                market_value > 0 and 
                position['current_price'] > 0
            )
            
            print(f"   {ticker}: {'✅ Valid' if is_valid else '❌ Invalid'}")
        
        print("\n✅ Position retrieval test completed!")
        
    except Exception as e:
        print(f"❌ Error testing positions: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_positions() 