#!/usr/bin/env python3
"""
Test script to verify enhanced position parsing with realized PnL
"""
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.trading_bot import PositionParser

def test_position_parsing():
    """Test the enhanced position parsing with realized PnL"""
    print("=== Testing Enhanced Position Parsing ===")
    
    # Test cases with different DAS position formats
    test_cases = [
        # Basic position line
        "%POS TSLA 2 10 324.42",
        
        # Position line with realized PnL
        "%POS TSLA 2 10 324.42 10 324.42 10.80 1234567890 0.50",
        
        # Position line with realized and unrealized PnL
        "%POS PLTR 2 10 25.00 10 25.00 -0.60 1234567890 0.25",
        
        # Short position with PnL
        "%POS NVDA 3 5 150.00 5 150.00 25.50 1234567890 -2.00",
        
        # Empty line
        "",
        
        # Invalid line
        "INVALID LINE"
    ]
    
    for i, test_line in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_line}")
        
        try:
            result = PositionParser.parse_position_line(test_line)
            if result:
                print(f"  ✅ Parsed successfully:")
                print(f"     Symbol: {result['symbol']}")
                print(f"     Type: {result['type']}")
                print(f"     Quantity: {result['quantity']}")
                print(f"     Avg Price: ${result['avg_price']:.2f}")
                print(f"     Realized PnL: ${result.get('realized_pnl', 0.0):.2f}")
                print(f"     Unrealized PnL: ${result.get('unrealized_pnl', 0.0):.2f}")
            else:
                print(f"  ❌ Failed to parse (expected for invalid lines)")
        except Exception as e:
            print(f"  ❌ Error parsing: {e}")

def test_raw_positions_parsing():
    """Test parsing raw positions data"""
    print("\n=== Testing Raw Positions Parsing ===")
    
    # Simulate raw DAS positions data
    raw_positions = """#POS symb type qty avgcost initqty initprice Realized CreatTime Unrealized
%POS TSLA 2 10 324.42 10 324.42 10.80 1234567890 0.50
%POS PLTR 2 10 25.00 10 25.00 -0.60 1234567890 0.25
%POS NVDA 3 5 150.00 5 150.00 25.50 1234567890 -2.00
#POSEND"""
    
    print("Raw positions data:")
    print(raw_positions)
    
    try:
        positions = PositionParser.parse_positions_raw(raw_positions)
        print(f"\n✅ Parsed {len(positions)} positions:")
        
        for i, position in enumerate(positions, 1):
            print(f"  {i}. {position['symbol']} {position['type']} {position['quantity']} @ ${position['avg_price']:.2f}")
            print(f"     Realized PnL: ${position.get('realized_pnl', 0.0):.2f}")
            print(f"     Unrealized PnL: ${position.get('unrealized_pnl', 0.0):.2f}")
            
    except Exception as e:
        print(f"❌ Error parsing raw positions: {e}")

if __name__ == "__main__":
    test_position_parsing()
    test_raw_positions_parsing()
