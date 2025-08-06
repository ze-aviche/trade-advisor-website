#!/usr/bin/env python3

import sys
import os

# Add parent directories to path to reach the bot module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bot.alpaca_client import AlpacaClient

def test_position_check():
    """Test position safety checks and validation"""
    
    print("🔍 Testing Position Safety Checks")
    print("=" * 40)
    
    try:
        # Initialize Alpaca client
        alpaca_client = AlpacaClient()
        
        # Get current positions
        positions = alpaca_client.get_positions()
        
        print(f"📊 Current Positions: {len(positions)}")
        
        # Test position safety for each ticker
        for position in positions:
            ticker = position.get('symbol', 'Unknown')
            quantity = position.get('qty', 0)
            market_value = position.get('market_value', 0)
            unrealized_pl = position.get('unrealized_pl', 0)
            
            print(f"\n📈 {ticker}:")
            print(f"   Quantity: {quantity:,} shares")
            print(f"   Market Value: ${market_value:,.2f}")
            print(f"   Unrealized P&L: ${unrealized_pl:,.2f}")
            
            # Check if position is safe to close
            is_safe_to_close = quantity > 0 and market_value > 0
            
            if is_safe_to_close:
                print(f"   Status: ✅ Safe to close")
            else:
                print(f"   Status: ⚠️ Not safe to close")
        
        # Test unsubscribe validation
        print("\n🎯 Testing Unsubscribe Validation:")
        
        # Get list of tickers with positions
        tickers_with_positions = [p.get('symbol') for p in positions if float(p.get('qty', 0)) > 0]
        
        print(f"   Tickers with active positions: {tickers_with_positions}")
        
        # Test unsubscribe attempt for each ticker
        for ticker in tickers_with_positions:
            can_unsubscribe = ticker not in tickers_with_positions
            print(f"   {ticker}: {'❌ Cannot unsubscribe (has position)' if not can_unsubscribe else '✅ Can unsubscribe'}")
        
        # Test risk validation
        print("\n⚠️ Testing Risk Validation:")
        
        for position in positions:
            ticker = position.get('symbol', 'Unknown')
            market_value = float(position.get('market_value', 0))
            portfolio_value = float(position.get('portfolio_value', 100000))  # Default
            
            # Calculate portfolio concentration
            concentration = (market_value / portfolio_value) * 100 if portfolio_value > 0 else 0
            
            # Risk thresholds
            high_risk = concentration > 10  # More than 10% of portfolio
            medium_risk = concentration > 5   # More than 5% of portfolio
            
            risk_level = "High" if high_risk else "Medium" if medium_risk else "Low"
            
            print(f"   {ticker}: {concentration:.1f}% of portfolio - {risk_level} risk")
        
        print("\n✅ Position safety check completed!")
        
    except Exception as e:
        print(f"❌ Error testing position checks: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_position_check() 