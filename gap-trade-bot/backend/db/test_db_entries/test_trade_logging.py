#!/usr/bin/env python3
"""
Test script for trade logging functionality
"""

from db.trades_db import (
    log_trade_submission, 
    update_trade_fill, 
    update_trade_status,
    get_trade_history,
    get_trades_by_status,
    get_trade_summary
)

def test_trade_logging():
    """Test the trade logging functionality"""
    
    print("🧪 Testing Trade Logging Functionality")
    print("=" * 50)
    
    # Test 1: Log a market order submission
    print("\n1. Logging Market Order Submission...")
    trade_id_1 = log_trade_submission(
        ticker="AAPL",
        direction="long",
        action="buy",
        order_type="market",
        quantity=10,
        notes="Test market order"
    )
    print(f"✅ Trade logged with ID: {trade_id_1}")
    
    # Test 2: Log a limit order submission
    print("\n2. Logging Limit Order Submission...")
    trade_id_2 = log_trade_submission(
        ticker="MSFT",
        direction="short",
        action="sell",
        order_type="limit",
        quantity=5,
        price=300.50,
        limit_price=300.50,
        notes="Test limit order"
    )
    print(f"✅ Trade logged with ID: {trade_id_2}")
    
    # Test 3: Log a stop order submission
    print("\n3. Logging Stop Order Submission...")
    trade_id_3 = log_trade_submission(
        ticker="TSLA",
        direction="long",
        action="sell",
        order_type="stop",
        quantity=8,
        stop_price=250.00,
        notes="Test stop loss order"
    )
    print(f"✅ Trade logged with ID: {trade_id_3}")
    
    # Test 4: Update trade fill
    print("\n4. Updating Trade Fill...")
    success = update_trade_fill(
        trade_id=trade_id_1,
        filled_price=150.25,
        filled_quantity=10,
        commission=1.00
    )
    print(f"✅ Trade fill updated: {success}")
    
    # Test 5: Update trade status
    print("\n5. Updating Trade Status...")
    success = update_trade_status(
        trade_id=trade_id_2,
        status="cancelled",
        notes="Order cancelled by user"
    )
    print(f"✅ Trade status updated: {success}")
    
    # Test 6: Get trade history
    print("\n6. Getting Trade History...")
    history = get_trade_history(limit=10)
    print(f"✅ Found {len(history)} trades in history")
    
    for trade in history[:3]:  # Show first 3 trades
        print(f"   - {trade['ticker']}: {trade['action']} {trade['quantity']} @ ${trade.get('filled_price', 'PENDING')}")
    
    # Test 7: Get trades by status
    print("\n7. Getting Trades by Status...")
    submitted_trades = get_trades_by_status("submitted")
    filled_trades = get_trades_by_status("filled")
    print(f"✅ Submitted trades: {len(submitted_trades)}")
    print(f"✅ Filled trades: {len(filled_trades)}")
    
    # Test 8: Get trade summary
    print("\n8. Getting Trade Summary...")
    summary = get_trade_summary()
    print(f"✅ Trade Summary:")
    print(f"   - Total trades: {summary.get('total_trades', 0)}")
    print(f"   - Filled trades: {summary.get('filled_trades', 0)}")
    print(f"   - Pending trades: {summary.get('pending_trades', 0)}")
    print(f"   - Total volume: ${summary.get('total_volume', 0):.2f}")
    print(f"   - Total commission: ${summary.get('total_commission', 0):.2f}")
    
    print("\n🎉 Trade Logging Test Completed Successfully!")

def test_specific_ticker():
    """Test getting trade history for a specific ticker"""
    print("\n🧪 Testing Specific Ticker History")
    print("=" * 40)
    
    # Get AAPL trade history
    aapl_trades = get_trade_history(ticker="AAPL")
    print(f"✅ AAPL trades: {len(aapl_trades)}")
    
    # Get AAPL summary
    aapl_summary = get_trade_summary(ticker="AAPL")
    print(f"✅ AAPL Summary:")
    print(f"   - Total trades: {aapl_summary.get('total_trades', 0)}")
    print(f"   - Filled trades: {aapl_summary.get('filled_trades', 0)}")
    print(f"   - Average fill price: ${aapl_summary.get('avg_fill_price', 0):.2f}")

if __name__ == "__main__":
    test_trade_logging()
    test_specific_ticker() 