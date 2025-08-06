#!/usr/bin/env python3

import sys
import os

# Add parent directories to path to reach the bot module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bot.risk_manager import risk_manager

def test_position_sizing():
    """Test the new position sizing system with different scenarios"""
    
    print("🚀 Testing Advanced Position Sizing System")
    print("=" * 50)
    
    # Test scenarios
    test_cases = [
        {"ticker": "AAPL", "price": 150.00, "description": "High-priced stock"},
        {"ticker": "TSLA", "price": 50.00, "description": "Mid-priced stock"},
        {"ticker": "PLTR", "price": 15.00, "description": "Low-mid priced stock"},
        {"ticker": "SNDL", "price": 2.50, "description": "Low-priced stock"},
        {"ticker": "PENN", "price": 0.75, "description": "Very low-priced stock"},
        {"ticker": "AMZN", "price": 3000.00, "description": "Very expensive stock"}
    ]
    
    # Get real account capital
    available_capital = risk_manager.get_available_capital()
    print(f"📊 Available Capital: ${available_capital:,.2f}")
    print()
    
    for case in test_cases:
        ticker = case["ticker"]
        price = case["price"]
        description = case["description"]
        
        # Calculate stop loss (15% below entry for long)
        stop_loss = price * 0.85
        
        # Calculate position size
        position_size = risk_manager.calculate_position_size(
            price, stop_loss, available_capital, ticker
        )
        
        # Calculate position value
        position_value = price * position_size
        
        # Calculate risk
        risk_per_share = price - stop_loss
        total_risk = risk_per_share * position_size
        
        # Show detailed calculations
        max_risk_amount = available_capital * 0.02  # 2% risk
        max_shares_by_risk = int(max_risk_amount / risk_per_share)
        
        max_position_value = available_capital * 0.02  # 2% of portfolio
        max_shares_by_value = int(max_position_value / price)
        
        if available_capital < 10000:  # Small account
            max_position_value = available_capital * 0.01  # 1% of portfolio
            max_shares_by_value = int(max_position_value / price)
        
        max_shares_by_price = risk_manager._get_price_based_limit(price)
        
        print(f"📈 {ticker} ({description})")
        print(f"   Entry Price: ${price:.2f}")
        print(f"   Stop Loss: ${stop_loss:.2f}")
        print(f"   Risk per Share: ${risk_per_share:.2f}")
        print(f"   Max Risk Amount: ${max_risk_amount:.2f}")
        print(f"   Max Shares by Risk: {max_shares_by_risk}")
        print(f"   Max Position Value: ${max_position_value:.2f}")
        print(f"   Max Shares by Value: {max_shares_by_value}")
        print(f"   Max Shares by Price: {max_shares_by_price}")
        print(f"   Final Position Size: {position_size:,} shares")
        print(f"   Position Value: ${position_value:,.2f}")
        print(f"   Total Risk: ${total_risk:,.2f}")
        print(f"   Risk % of Portfolio: {(total_risk/available_capital)*100:.2f}%")
        print()
    
    # Test risk validation
    print("🔍 Testing Risk Validation")
    print("=" * 30)
    
    # Test a valid trade
    valid_ticker = "AAPL"
    valid_price = 150.00
    valid_quantity = 50
    valid_stop_loss = 127.50
    
    is_valid, message = risk_manager.validate_trade_risk(
        valid_ticker, valid_price, valid_quantity, valid_stop_loss
    )
    
    print(f"Valid Trade Test ({valid_ticker}):")
    print(f"   Price: ${valid_price:.2f}")
    print(f"   Quantity: {valid_quantity:,} shares")
    print(f"   Stop Loss: ${valid_stop_loss:.2f}")
    print(f"   Valid: {is_valid}")
    print(f"   Message: {message}")
    print()
    
    # Test an invalid trade (too large)
    invalid_ticker = "TSLA"
    invalid_price = 50.00
    invalid_quantity = 10000  # Too many shares
    invalid_stop_loss = 42.50
    
    is_valid, message = risk_manager.validate_trade_risk(
        invalid_ticker, invalid_price, invalid_quantity, invalid_stop_loss
    )
    
    print(f"Invalid Trade Test ({invalid_ticker}):")
    print(f"   Price: ${invalid_price:.2f}")
    print(f"   Quantity: {invalid_quantity:,} shares")
    print(f"   Stop Loss: ${invalid_stop_loss:.2f}")
    print(f"   Valid: {is_valid}")
    print(f"   Message: {message}")
    print()
    
    print("✅ Position sizing test completed!")

if __name__ == "__main__":
    test_position_sizing() 