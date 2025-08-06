#!/usr/bin/env python3
"""
Test script to check web API analysis results
"""

import requests
import json

def test_bot_status():
    """Test the bot status endpoint"""
    try:
        response = requests.get('http://localhost:5000/api/bot/status')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Response received")
            
            # Check analysis results
            analysis_results = data.get('analysis_results', [])
            print(f"📊 Analysis Results: {len(analysis_results)} stocks")
            
            # Show first result in detail
            if analysis_results:
                first_result = analysis_results[0]
                print(f"\n🔍 First Result Details:")
                print(f"Ticker: {first_result.get('ticker')}")
                print(f"Best Strategy: {first_result.get('bestStrategy')}")
                print(f"Best Confidence: {first_result.get('bestConfidence')}")
                
                strategies = first_result.get('strategies', {})
                bo = strategies.get('breakOut', {})
                gus = strategies.get('gapUpShort', {})
                
                print(f"\nBreak Out Strategy:")
                print(f"  Entry Signal: {bo.get('entrySignal')}")
                print(f"  Confidence: {bo.get('confidence')}")
                print(f"  Applicable: {bo.get('applicable')}")
                
                print(f"\nGap Up Short Strategy:")
                print(f"  Entry Signal: {gus.get('entrySignal')}")
                print(f"  Confidence: {gus.get('confidence')}")
                print(f"  Applicable: {gus.get('applicable')}")
                
                # Show raw data for debugging
                print(f"\n📊 Raw Data Keys: {list(first_result.keys())}")
                
        else:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error testing API: {e}")

if __name__ == "__main__":
    test_bot_status() 