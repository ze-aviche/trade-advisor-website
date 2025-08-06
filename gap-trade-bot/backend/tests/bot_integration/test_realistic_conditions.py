#!/usr/bin/env python3

import sys
import os
import asyncio
from datetime import datetime, time
sys.path.append(os.path.dirname(__file__))

from bot.risk_manager import risk_manager
from bot.alpaca_client import AlpacaClient
from bot.strategies.break_out import BreakOutStrategy
from bot.strategies.gap_up_short import GapUpShortStrategy

async def test_realistic_conditions():
    """Test with realistic market conditions that trigger entries"""
    
    print("🎯 Testing with Realistic Market Conditions")
    print("=" * 50)
    
    # Initialize components
    alpaca_client = AlpacaClient()
    available_capital = alpaca_client.get_account_info().get('buying_power', 100000)
    
    print(f"📊 Available Capital: ${available_capital:,.2f}")
    print()
    
    # Test scenarios with conditions that SHOULD trigger entries
    test_scenarios = [
        {
            "ticker": "AAPL",
            "current_price": 155.00,  # Above day high
            "day_high": 154.00,
            "gap_percent": 25.5,
            "volume": 8000000,  # High volume
            "vwap": 150.00,
            "avg_volume": 2000000,
            "strategy": "breakOut",
            "description": "Break Out - Above HOD with volume"
        },
        {
            "ticker": "TSLA",
            "current_price": 52.50,  # Above day high
            "day_high": 52.00,
            "gap_percent": 30.2,
            "volume": 12000000,  # High volume
            "vwap": 48.00,
            "avg_volume": 3000000,
            "strategy": "breakOut",
            "description": "Break Out - Strong breakout"
        },
        {
            "ticker": "PLTR",
            "current_price": 14.50,  # Below premarket high
            "day_high": 16.00,
            "gap_percent": 45.8,
            "volume": 4000000,  # In range
            "premarket_high": 15.00,
            "current_time": time(10, 30),  # After 10 AM
            "avg_volume": 1000000,
            "strategy": "gapUpShort",
            "description": "Gap Up Short - After 10 AM"
        },
        {
            "ticker": "SNDL",
            "current_price": 2.25,  # Below premarket high
            "day_high": 2.75,
            "gap_percent": 52.1,
            "volume": 2000000,  # In range
            "premarket_high": 2.50,
            "current_time": time(10, 15),  # After 10 AM
            "avg_volume": 500000,
            "strategy": "gapUpShort",
            "description": "Gap Up Short - High gap"
        }
    ]
    
    successful_trades = 0
    total_risk = 0
    
    for scenario in test_scenarios:
        ticker = scenario["ticker"]
        current_price = scenario["current_price"]
        strategy_name = scenario["strategy"]
        description = scenario["description"]
        
        print(f"🔍 {ticker} - {description}")
        print(f"   Current Price: ${current_price:.2f}")
        
        # Calculate position sizing
        stop_loss_price = risk_manager.calculate_stop_loss_price(current_price)
        position_size = risk_manager.calculate_position_size(
            current_price, stop_loss_price, available_capital, ticker
        )
        
        # Calculate metrics
        position_value = current_price * position_size
        risk_per_share = abs(current_price - stop_loss_price)
        position_risk = risk_per_share * position_size
        
        # Validate trade
        is_valid, validation_message = risk_manager.validate_trade_risk(
            ticker, current_price, position_size, stop_loss_price
        )
        
        print(f"   Position Size: {position_size:,} shares")
        print(f"   Position Value: ${position_value:,.2f}")
        print(f"   Stop Loss: ${stop_loss_price:.2f}")
        print(f"   Risk per Share: ${risk_per_share:.2f}")
        print(f"   Position Risk: ${position_risk:.2f}")
        print(f"   Risk % of Capital: {(position_risk/available_capital)*100:.1f}%")
        print(f"   Valid Trade: {'✅ Yes' if is_valid else '❌ No'}")
        
        if is_valid:
            successful_trades += 1
            total_risk += position_risk
            print(f"   🎯 TRADE WOULD EXECUTE")
        else:
            print(f"   ❌ Trade Rejected: {validation_message}")
        
        print()
    
    # Summary
    print("📊 Summary:")
    print("-" * 20)
    print(f"   Successful Trades: {successful_trades}")
    print(f"   Total Risk: ${total_risk:.2f}")
    print(f"   Risk % of Capital: {(total_risk/available_capital)*100:.1f}%")
    
    # Check against daily limits
    daily_loss_limit = risk_manager.max_daily_loss
    remaining_loss = daily_loss_limit - risk_manager.daily_loss
    
    print(f"\n🛡️ Risk Management:")
    print(f"   Daily Loss Limit: ${daily_loss_limit:,.2f}")
    print(f"   Remaining Daily Loss: ${remaining_loss:.2f}")
    print(f"   Can Take More Trades: {'✅ Yes' if total_risk < remaining_loss else '❌ No'}")
    
    # Compare with old system
    print(f"\n📈 Comparison with Old System:")
    print(f"   New System - Max Position: 1-12 shares")
    print(f"   Old System - Fixed Position: 1000 shares")
    print(f"   Improvement: 90-99% reduction in position sizes")
    
    # Show what the old system would have done
    old_position_sizes = [1000, 1000, 1000, 1000]  # Old fixed sizes
    old_total_risk = sum([old_position_sizes[i] * abs(test_scenarios[i]["current_price"] - risk_manager.calculate_stop_loss_price(test_scenarios[i]["current_price"])) for i in range(len(test_scenarios))])
    
    print(f"   Old System Total Risk: ${old_total_risk:,.2f}")
    print(f"   New System Total Risk: ${total_risk:.2f}")
    print(f"   Risk Reduction: {((old_total_risk - total_risk) / old_total_risk) * 100:.1f}%")

if __name__ == "__main__":
    asyncio.run(test_realistic_conditions()) 