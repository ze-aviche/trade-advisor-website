#!/usr/bin/env python3

import sys
import os
import asyncio
from datetime import datetime
sys.path.append(os.path.dirname(__file__))

from bot.risk_manager import risk_manager
from bot.alpaca_client import AlpacaClient
from bot.trading_database import TradingDatabase

async def test_real_trading_scenarios():
    """Test the new position sizing system with real market data"""
    
    print("🚀 Testing Advanced Position Sizing with Real Trading Scenarios")
    print("=" * 60)
    
    # Initialize components
    alpaca_client = AlpacaClient()
    trading_db = TradingDatabase()
    
    # Get real account information
    account_info = alpaca_client.get_account_info()
    available_capital = account_info.get('buying_power', 100000)
    portfolio_value = account_info.get('portfolio_value', 100000)
    
    print(f"📊 Account Information:")
    print(f"   Cash: ${account_info.get('cash', 0):,.2f}")
    print(f"   Portfolio Value: ${portfolio_value:,.2f}")
    print(f"   Buying Power: ${available_capital:,.2f}")
    print(f"   Equity: ${account_info.get('equity', 0):,.2f}")
    print()
    
    # Test scenarios with real stock prices
    test_scenarios = [
        {
            "ticker": "AAPL",
            "description": "High-priced tech stock",
            "strategy": "breakOut"
        },
        {
            "ticker": "TSLA", 
            "description": "Mid-priced EV stock",
            "strategy": "breakOut"
        },
        {
            "ticker": "PLTR",
            "description": "Low-mid priced tech stock", 
            "strategy": "gapUpShort"
        },
        {
            "ticker": "SNDL",
            "description": "Low-priced cannabis stock",
            "strategy": "gapUpShort"
        }
    ]
    
    print("📈 Position Sizing Analysis for Real Stocks:")
    print("-" * 50)
    
    for scenario in test_scenarios:
        ticker = scenario["ticker"]
        description = scenario["description"]
        strategy = scenario["strategy"]
        
        try:
            # Get current market data
            current_data = await get_market_data(ticker)
            if not current_data:
                print(f"❌ Could not get market data for {ticker}")
                continue
                
            current_price = current_data.get('current_price', 0)
            if current_price <= 0:
                print(f"❌ Invalid price for {ticker}: ${current_price}")
                continue
            
            # Calculate position sizing
            stop_loss_price = risk_manager.calculate_stop_loss_price(current_price)
            position_size = risk_manager.calculate_position_size(
                current_price, stop_loss_price, available_capital, ticker
            )
            
            # Calculate metrics
            position_value = current_price * position_size
            risk_per_share = abs(current_price - stop_loss_price)
            total_risk = risk_per_share * position_size
            risk_percentage = (total_risk / available_capital) * 100
            
            # Validate trade
            is_valid, validation_message = risk_manager.validate_trade_risk(
                ticker, current_price, position_size, stop_loss_price
            )
            
            print(f"📊 {ticker} ({description})")
            print(f"   Strategy: {strategy}")
            print(f"   Current Price: ${current_price:.2f}")
            print(f"   Stop Loss: ${stop_loss_price:.2f}")
            print(f"   Position Size: {position_size:,} shares")
            print(f"   Position Value: ${position_value:,.2f}")
            print(f"   Risk per Share: ${risk_per_share:.2f}")
            print(f"   Total Risk: ${total_risk:,.2f}")
            print(f"   Risk % of Portfolio: {risk_percentage:.2f}%")
            print(f"   Valid Trade: {'✅ Yes' if is_valid else '❌ No'}")
            if not is_valid:
                print(f"   Validation Message: {validation_message}")
            print()
            
        except Exception as e:
            print(f"❌ Error testing {ticker}: {e}")
            print()
    
    # Test portfolio concentration
    print("🔍 Portfolio Concentration Analysis:")
    print("-" * 40)
    
    # Simulate multiple positions
    simulated_positions = [
        {"ticker": "AAPL", "price": 150.00, "shares": 1},
        {"ticker": "TSLA", "price": 50.00, "shares": 10},
        {"ticker": "PLTR", "price": 15.00, "shares": 10},
        {"ticker": "SNDL", "price": 2.50, "shares": 10}
    ]
    
    total_portfolio_value = portfolio_value
    total_risk = 0
    
    for pos in simulated_positions:
        ticker = pos["ticker"]
        price = pos["price"]
        shares = pos["shares"]
        
        position_value = price * shares
        stop_loss = price * 0.85
        risk_per_share = price - stop_loss
        position_risk = risk_per_share * shares
        
        concentration = (position_value / total_portfolio_value) * 100
        risk_percentage = (position_risk / available_capital) * 100
        
        print(f"   {ticker}: {shares} shares @ ${price:.2f}")
        print(f"     Position Value: ${position_value:,.2f} ({concentration:.1f}% of portfolio)")
        print(f"     Position Risk: ${position_risk:,.2f} ({risk_percentage:.1f}% of capital)")
        
        total_risk += position_risk
    
    print(f"\n📊 Total Portfolio Risk: ${total_risk:,.2f} ({(total_risk/available_capital)*100:.1f}% of capital)")
    
    # Test daily loss limits
    print("\n🛡️ Daily Loss Limit Testing:")
    print("-" * 30)
    
    daily_loss_limit = risk_manager.max_daily_loss
    print(f"   Daily Loss Limit: ${daily_loss_limit:,.2f}")
    print(f"   Current Daily Loss: ${risk_manager.daily_loss:,.2f}")
    print(f"   Remaining Daily Loss: ${daily_loss_limit - risk_manager.daily_loss:,.2f}")
    
    # Test if we can take more trades
    can_trade = total_risk < (daily_loss_limit - risk_manager.daily_loss)
    print(f"   Can Take More Trades: {'✅ Yes' if can_trade else '❌ No'}")
    
    if not can_trade:
        print(f"   Reason: Total risk (${total_risk:,.2f}) exceeds remaining daily loss limit")

async def get_market_data(ticker):
    """Get current market data for a ticker"""
    try:
        # This would normally get real market data
        # For testing, we'll use mock data
        mock_data = {
            "AAPL": {"current_price": 150.00},
            "TSLA": {"current_price": 50.00},
            "PLTR": {"current_price": 15.00},
            "SNDL": {"current_price": 2.50}
        }
        
        return mock_data.get(ticker, {})
    except Exception as e:
        print(f"Error getting market data for {ticker}: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(test_real_trading_scenarios()) 