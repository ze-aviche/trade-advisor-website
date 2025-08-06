#!/usr/bin/env python3

import sys
import os

# Add parent directories to path to reach the bot module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bot.trading_bot import TradingBot
from bot.strategies.break_out import BreakOutStrategy
from bot.strategies.gap_up_short import GapUpShortStrategy
from bot.risk_manager import RiskManager

def test_bot_integration():
    """Test complete bot integration workflow"""
    
    print("🤖 Testing Bot Integration Workflow")
    print("=" * 50)
    
    try:
        # Initialize components
        trading_bot = TradingBot()
        break_out_strategy = BreakOutStrategy()
        gap_up_short_strategy = GapUpShortStrategy()
        risk_manager = RiskManager()
        
        print("✅ Components initialized successfully")
        
        # Mock stock data for testing
        mock_stock_data = {
            'ticker': 'AAPL',
            'current_price': 150.0,
            'previous_close': 140.0,
            'gap_percent': 7.14,
            'volume': 1000000,
            'market_status': 'open',
            'day_high': 155.0,
            'premarket_high': 152.0,
            'vwap': 148.0
        }
        
        print(f"📊 Testing with mock data: {mock_stock_data['ticker']}")
        
        # Test strategy analysis
        print("\n🎯 Testing Strategy Analysis:")
        
        # Break Out strategy analysis
        break_out_analysis = break_out_strategy.analyze_entry_conditions('AAPL', mock_stock_data)
        print(f"   Break Out Analysis: {break_out_analysis is not None}")
        
        if break_out_analysis:
            conditions_met = break_out_analysis.get('conditions_met', {})
            confidence = break_out_analysis.get('confidence', 0)
            print(f"   Conditions Met: {sum(conditions_met.values())}/{len(conditions_met)}")
            print(f"   Confidence: {confidence:.1f}%")
        
        # Gap Up Short strategy analysis
        gap_up_short_analysis = gap_up_short_strategy.analyze_entry_conditions('AAPL', mock_stock_data)
        print(f"   Gap Up Short Analysis: {gap_up_short_analysis is not None}")
        
        if gap_up_short_analysis:
            conditions_met = gap_up_short_analysis.get('conditions_met', {})
            confidence = gap_up_short_analysis.get('confidence', 0)
            print(f"   Conditions Met: {sum(conditions_met.values())}/{len(conditions_met)}")
            print(f"   Confidence: {confidence:.1f}%")
        
        # Test entry signal validation
        print("\n🔍 Testing Entry Signal Validation:")
        
        if break_out_analysis:
            should_enter = break_out_strategy.should_enter_position(break_out_analysis)
            print(f"   Break Out Entry Signal: {'✅ YES' if should_enter else '❌ NO'}")
        
        if gap_up_short_analysis:
            should_enter = gap_up_short_strategy.should_enter_position(gap_up_short_analysis)
            print(f"   Gap Up Short Entry Signal: {'✅ YES' if should_enter else '❌ NO'}")
        
        # Test position sizing integration
        print("\n📊 Testing Position Sizing Integration:")
        
        entry_price = mock_stock_data['current_price']
        stop_loss_price = entry_price * 0.85  # 15% stop loss
        available_capital = 100000  # Mock capital
        
        position_size = risk_manager.calculate_position_size(
            ticker='AAPL',
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            available_capital=available_capital
        )
        
        print(f"   Entry Price: ${entry_price:.2f}")
        print(f"   Stop Loss: ${stop_loss_price:.2f}")
        print(f"   Position Size: {position_size:,} shares")
        print(f"   Position Value: ${(entry_price * position_size):,.2f}")
        
        # Test risk validation
        print("\n⚠️ Testing Risk Validation:")
        
        is_valid, message = risk_manager.validate_trade_risk(
            ticker='AAPL',
            position_size=position_size,
            entry_price=entry_price,
            available_capital=available_capital
        )
        
        print(f"   Trade Valid: {'✅ YES' if is_valid else '❌ NO'}")
        print(f"   Message: {message}")
        
        print("\n✅ Bot integration test completed!")
        
    except Exception as e:
        print(f"❌ Error testing bot integration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bot_integration() 