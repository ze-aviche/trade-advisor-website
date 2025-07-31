#!/usr/bin/env python3
"""
Test script to verify ticker validation and filtering
"""

import sys
import os

# Add backend/bot to path
sys.path.append('backend/bot')

from data_manager import data_manager

def test_ticker_validation():
    """Test ticker validation"""
    print("🔍 Testing ticker validation...")
    
    # Test valid tickers
    valid_tickers = ['AAPL', 'MSFT', 'TSLA']
    print("\n✅ Testing valid tickers:")
    for ticker in valid_tickers:
        is_valid = data_manager._validate_ticker(ticker)
        print(f"   {ticker}: {'✅ Valid' if is_valid else '❌ Invalid'}")
    
    # Test invalid tickers
    invalid_tickers = ['BRR', 'INVALID', 'XYZ123']
    print("\n❌ Testing invalid tickers:")
    for ticker in invalid_tickers:
        is_valid = data_manager._validate_ticker(ticker)
        print(f"   {ticker}: {'✅ Valid' if is_valid else '❌ Invalid'}")
    
    # Test gap-up stock filtering
    print("\n📊 Testing gap-up stock filtering:")
    gap_up_stocks = data_manager.get_gap_up_stocks()
    print(f"   Found {len(gap_up_stocks)} valid gap-up stocks")
    if gap_up_stocks:
        print(f"   Valid tickers: {', '.join(gap_up_stocks)}")
    
    return True

if __name__ == "__main__":
    test_ticker_validation() 