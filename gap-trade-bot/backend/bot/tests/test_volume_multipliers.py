#!/usr/bin/env python3
"""
Test different volume multipliers to find optimal settings
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from data_manager import DataManager
from strategies.break_out import BreakOutStrategy
from logging_config import get_logger

logger = get_logger(__name__)

def test_volume_multipliers():
    """Test different volume multipliers with sample data"""
    
    # Sample stock data for testing
    sample_stocks = [
        {
            'ticker': 'WINT',
            'current_volume': 2500000,
            'avg_volume': 800000,
            'gap_percent': 35,
            'current_price': 15.50,
            'day_high': 15.00,
            'vwap': 14.80,
            'market_status': 'open'
        },
        {
            'ticker': 'TSLA',
            'current_volume': 15000000,
            'avg_volume': 12000000,
            'gap_percent': 25,
            'current_price': 250.00,
            'day_high': 248.00,
            'vwap': 245.00,
            'market_status': 'open'
        },
        {
            'ticker': 'NVDA',
            'current_volume': 8000000,
            'avg_volume': 10000000,
            'gap_percent': 30,
            'current_price': 500.00,
            'day_high': 495.00,
            'vwap': 490.00,
            'market_status': 'open'
        }
    ]
    
    # Test different multipliers
    multipliers = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    
    print("📊 Testing Volume Multipliers")
    print("=" * 50)
    
    for multiplier in multipliers:
        print(f"\n🔍 Testing Multiplier: {multiplier}x")
        print("-" * 30)
        
        # Create strategy with this multiplier
        strategy = BreakOutStrategy()
        strategy.volume_multiplier = multiplier
        
        signals_found = 0
        total_stocks = 0
        
        for stock_data in sample_stocks:
            ticker = stock_data['ticker']
            current_volume = stock_data['current_volume']
            avg_volume = stock_data['avg_volume']
            
            # Calculate volume ratio
            volume_ratio = current_volume / avg_volume
            has_breakout_volume = volume_ratio >= multiplier
            
            print(f"  {ticker}:")
            print(f"    Current Volume: {current_volume:,}")
            print(f"    Average Volume: {avg_volume:,}")
            print(f"    Volume Ratio: {volume_ratio:.2f}x")
            print(f"    Breakout Volume: {'✅' if has_breakout_volume else '❌'}")
            
            total_stocks += 1
            if has_breakout_volume:
                signals_found += 1
        
        # Calculate signal rate
        signal_rate = (signals_found / total_stocks) * 100
        
        print(f"\n📈 Results for {multiplier}x multiplier:")
        print(f"  Signals Found: {signals_found}/{total_stocks}")
        print(f"  Signal Rate: {signal_rate:.1f}%")
        
        # Recommendations
        if signal_rate > 80:
            print(f"  ⚠️  Too many signals ({signal_rate:.1f}%) - consider higher multiplier")
        elif signal_rate < 20:
            print(f"  ⚠️  Too few signals ({signal_rate:.1f}%) - consider lower multiplier")
        else:
            print(f"  ✅ Good signal rate ({signal_rate:.1f}%)")

def analyze_market_conditions():
    """Analyze current market conditions for multiplier adjustment"""
    
    print("\n📊 Market Conditions Analysis")
    print("=" * 50)
    
    # Get current market data
    data_manager = DataManager()
    
    # Check market status
    market_status = data_manager.get_market_status()
    print(f"Market Status: {market_status}")
    
    # Get gap-up stocks
    gap_ups = data_manager.get_gap_up_stocks()
    print(f"Gap-Up Stocks Found: {len(gap_ups)}")
    
    # Recommendations based on market conditions
    if market_status == 'open':
        if len(gap_ups) > 10:
            print("📈 High Activity Market - Consider 2.5x multiplier")
        elif len(gap_ups) > 5:
            print("📊 Normal Activity Market - Use 2.0x multiplier")
        else:
            print("📉 Low Activity Market - Consider 1.5x multiplier")
    else:
        print("🔒 Market Closed - No trading signals")

def get_recommended_multiplier():
    """Get recommended volume multiplier based on analysis"""
    
    print("\n🎯 Recommended Volume Multiplier")
    print("=" * 50)
    
    # Conservative approach
    print("1. Conservative (2.0x):")
    print("   ✅ Good for beginners")
    print("   ✅ Fewer false signals")
    print("   ❌ May miss some opportunities")
    
    # Moderate approach
    print("\n2. Moderate (2.5x):")
    print("   ✅ Balanced approach")
    print("   ✅ Good signal quality")
    print("   ✅ Suitable for most markets")
    
    # Aggressive approach
    print("\n3. Aggressive (1.5x):")
    print("   ✅ More trading opportunities")
    print("   ❌ Higher false signal risk")
    print("   ❌ Requires careful risk management")
    
    print("\n💡 Recommendation: Start with 2.0x and adjust based on performance")

if __name__ == "__main__":
    print("🧪 Volume Multiplier Testing Tool")
    print("=" * 50)
    
    # Test different multipliers
    test_volume_multipliers()
    
    # Analyze market conditions
    analyze_market_conditions()
    
    # Get recommendations
    get_recommended_multiplier()
    
    print("\n✅ Testing complete!") 