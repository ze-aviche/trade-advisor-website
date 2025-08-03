#!/usr/bin/env python3
"""
Test script for enhanced pattern recognition data retrieval
"""

from polygon import RESTClient
from api_helper.polygon_api_get_historical_data import (
    analyze, get_intraday_volume_analysis, get_price_action_patterns,
    get_historical_pattern_analysis
)

def test_enhanced_analysis():
    """Test the enhanced analysis functions"""
    
    print("🧪 Testing Enhanced Pattern Recognition Data Retrieval")
    print("=" * 60)
    
    # Initialize Polygon client
    API_KEY = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
    polygon_client = RESTClient(API_KEY)
    
    # Test ticker
    test_ticker = "AAPL"
    test_date = "2024-01-15"  # Example date
    
    print(f"\n📊 Testing Comprehensive Analysis for {test_ticker}")
    print("-" * 50)
    
    # Test 1: Enhanced analyze function
    print("\n1. Testing Enhanced Analyze Function...")
    try:
        results = analyze([test_ticker], polygon_client)
        if test_ticker in results:
            ticker_data = results[test_ticker]
            print(f"✅ Enhanced analysis completed for {test_ticker}")
            print(f"   - Gap-up days found: {len(ticker_data['gap_up_days'])}")
            print(f"   - Historical patterns: {'Available' if ticker_data['historical_patterns'] else 'Not available'}")
            print(f"   - Detailed analysis: {len(ticker_data['detailed_analysis'])} days analyzed")
        else:
            print(f"❌ No data found for {test_ticker}")
    except Exception as e:
        print(f"❌ Error in enhanced analyze: {e}")
    
    # Test 2: Intraday volume analysis
    print("\n2. Testing Intraday Volume Analysis...")
    try:
        volume_analysis = get_intraday_volume_analysis(test_ticker, polygon_client, test_date)
        if volume_analysis:
            print(f"✅ Volume analysis completed for {test_ticker} on {test_date}")
            print(f"   - Morning volume: {volume_analysis['morning_volume']:,.0f}")
            print(f"   - Midday volume: {volume_analysis['midday_volume']:,.0f}")
            print(f"   - Afternoon volume: {volume_analysis['afternoon_volume']:,.0f}")
            print(f"   - Volume spikes: {volume_analysis['volume_spikes_count']}")
            print(f"   - Volume distribution: {volume_analysis['volume_distribution']}")
        else:
            print(f"❌ No volume data found for {test_ticker} on {test_date}")
    except Exception as e:
        print(f"❌ Error in volume analysis: {e}")
    
    # Test 3: Price action patterns
    print("\n3. Testing Price Action Pattern Analysis...")
    try:
        price_patterns = get_price_action_patterns(test_ticker, polygon_client, test_date)
        if price_patterns:
            print(f"✅ Price pattern analysis completed for {test_ticker} on {test_date}")
            print(f"   - Pattern type: {price_patterns['pattern_type']}")
            print(f"   - Open to close: {price_patterns['open_to_close_pct']:.2f}%")
            print(f"   - Open to high: {price_patterns['open_to_high_pct']:.2f}%")
            print(f"   - Volatility: {price_patterns['volatility']:.2f}%")
            print(f"   - High price: ${price_patterns['high_price']:.2f}")
            print(f"   - Low price: ${price_patterns['low_price']:.2f}")
        else:
            print(f"❌ No price pattern data found for {test_ticker} on {test_date}")
    except Exception as e:
        print(f"❌ Error in price pattern analysis: {e}")
    
    # Test 4: Historical pattern analysis
    print("\n4. Testing Historical Pattern Analysis...")
    try:
        historical_patterns = get_historical_pattern_analysis(test_ticker, polygon_client, 30)
        if historical_patterns:
            print(f"✅ Historical pattern analysis completed for {test_ticker}")
            print(f"   - Total days analyzed: {historical_patterns['total_days']}")
            print(f"   - Runner pattern: {historical_patterns['runner_count']} ({historical_patterns['runner_pct']:.1f}%)")
            print(f"   - Fader pattern: {historical_patterns['fader_count']} ({historical_patterns['fader_pct']:.1f}%)")
            print(f"   - Consolidation pattern: {historical_patterns['consolidation_count']} ({historical_patterns['consolidation_pct']:.1f}%)")
            print(f"   - High volume days: {historical_patterns['high_volume_count']} ({historical_patterns['high_volume_pct']:.1f}%)")
            print(f"   - Low volume days: {historical_patterns['low_volume_count']} ({historical_patterns['low_volume_pct']:.1f}%)")
            print(f"   - Average volume: {historical_patterns['avg_volume']:,.0f}")
        else:
            print(f"❌ No historical pattern data found for {test_ticker}")
    except Exception as e:
        print(f"❌ Error in historical pattern analysis: {e}")
    
    print("\n🎉 Enhanced Analysis Test Completed!")

def test_multiple_tickers():
    """Test analysis on multiple tickers"""
    
    print("\n🧪 Testing Multiple Ticker Analysis")
    print("=" * 50)
    
    API_KEY = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
    polygon_client = RESTClient(API_KEY)
    
    test_tickers = ["AAPL", "MSFT", "TSLA"]
    
    print(f"Testing comprehensive analysis for: {', '.join(test_tickers)}")
    
    try:
        results = analyze(test_tickers, polygon_client)
        
        for ticker in test_tickers:
            if ticker in results:
                ticker_data = results[ticker]
                print(f"\n📊 {ticker} Analysis Summary:")
                print(f"   - Gap-up days: {len(ticker_data['gap_up_days'])}")
                
                if ticker_data['historical_patterns']:
                    hist = ticker_data['historical_patterns']
                    print(f"   - Runner tendency: {hist['runner_pct']:.1f}%")
                    print(f"   - Fader tendency: {hist['fader_pct']:.1f}%")
                    print(f"   - High volume tendency: {hist['high_volume_pct']:.1f}%")
                
                print(f"   - Detailed analysis: {len(ticker_data['detailed_analysis'])} days")
            else:
                print(f"❌ No data available for {ticker}")
        
        print("\n✅ Multiple ticker analysis completed!")
        
    except Exception as e:
        print(f"❌ Error in multiple ticker analysis: {e}")

if __name__ == "__main__":
    test_enhanced_analysis()
    test_multiple_tickers() 