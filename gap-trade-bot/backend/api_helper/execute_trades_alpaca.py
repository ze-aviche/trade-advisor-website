import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopOrderRequest, LimitOrderRequest
from alpaca.trading import enums
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from polygon import RESTClient
import os
from db.trades_db import log_trade_submission, update_trade_fill, update_trade_status

# Configuration
ALPACA_API_KEY = 'PK0L4QA147CVM8AGHBDQ'
ALPACA_SECRET_KEY = 'y2gfGTPxypHTkfXVn8dKJWkq23zKiPhrWxFW4xdZ'
POLYGON_API_KEY = '5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT'

# Initialize clients
trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
alpaca_account = trading_client.get_account()
data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
polygon_client = RESTClient(POLYGON_API_KEY)

# Active trades tracking
active_trades = {}
monitoring = False

def get_current_price(ticker: str) -> float:
    """
    Get current price of a stock using Polygon API
    """
    try:
        # Get latest quote
        latest_quote = polygon_client.get_last_quote(ticker)
        if latest_quote:
            return latest_quote.ask_price or latest_quote.bid_price
        else:
            # Fallback to last trade
            last_trade = polygon_client.get_last_trade(ticker)
            if last_trade:
                return last_trade.price
            else:
                print(f"Could not get current price for {ticker}")
                return None
    except Exception as e:
        print(f"Error getting current price for {ticker}: {e}")
        return None

def place_market_order(ticker: str, qty: int, side: str = "buy", direction: str = "long") -> Dict:
    """
    Place a market order and log it to database
    """
    try:
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=enums.OrderSide.BUY if side.lower() == "buy" else enums.OrderSide.SELL,
            time_in_force=enums.TimeInForce.DAY
        )
        
        order = trading_client.submit_order(order_data=order_data)
        print(f"✅ Market order placed: {side.upper()} {qty} shares of {ticker}")
        print(f"Order ID: {order.id}")
        
        # Log trade to database
        trade_id = log_trade_submission(
            ticker=ticker,
            direction=direction,
            action=side,
            order_type="market",
            quantity=qty,
            order_id=order.id,
            notes=f"Market order - {side.upper()} {qty} shares"
        )
        
        # Track the order
        active_trades[order.id] = {
            'ticker': ticker,
            'qty': qty,
            'side': side,
            'direction': direction,
            'order_type': 'market',
            'entry_time': datetime.now(),
            'status': 'submitted',
            'trade_id': trade_id
        }
        
        return {
            'order_id': order.id,
            'trade_id': trade_id,
            'status': 'submitted',
            'ticker': ticker,
            'qty': qty,
            'side': side,
            'direction': direction
        }
        
    except Exception as e:
        print(f"❌ Error placing market order for {ticker}: {e}")
        return {'error': str(e)}

def place_stop_order(ticker: str, qty: int, stop_price: float, side: str = "sell", direction: str = "long") -> Dict:
    """
    Place a stop order for exit and log it to database
    """
    try:
        order_data = StopOrderRequest(
            symbol=ticker,
            qty=qty,
            side=enums.OrderSide.SELL if side.lower() == "sell" else enums.OrderSide.BUY,
            stop_price=stop_price,
            time_in_force=enums.TimeInForce.GTC
        )
        
        order = trading_client.submit_order(order_data=order_data)
        print(f"✅ Stop order placed: {side.upper()} {qty} shares of {ticker} at ${stop_price}")
        print(f"Order ID: {order.id}")
        
        # Log trade to database
        trade_id = log_trade_submission(
            ticker=ticker,
            direction=direction,
            action=side,
            order_type="stop",
            quantity=qty,
            stop_price=stop_price,
            order_id=order.id,
            notes=f"Stop order - {side.upper()} {qty} shares at ${stop_price}"
        )
        
        return {
            'order_id': order.id,
            'trade_id': trade_id,
            'status': 'submitted',
            'ticker': ticker,
            'qty': qty,
            'side': side,
            'direction': direction,
            'stop_price': stop_price
        }
        
    except Exception as e:
        print(f"❌ Error placing stop order for {ticker}: {e}")
        return {'error': str(e)}

def place_limit_order(ticker: str, qty: int, limit_price: float, side: str = "buy", direction: str = "long") -> Dict:
    """
    Place a limit order and log it to database
    """
    try:
        order_data = LimitOrderRequest(
            symbol=ticker,
            qty=qty,
            side=enums.OrderSide.BUY if side.lower() == "buy" else enums.OrderSide.SELL,
            limit_price=limit_price,
            time_in_force=enums.TimeInForce.DAY
        )
        
        order = trading_client.submit_order(order_data=order_data)
        print(f"✅ Limit order placed: {side.upper()} {qty} shares of {ticker} at ${limit_price}")
        print(f"Order ID: {order.id}")
        
        # Log trade to database
        trade_id = log_trade_submission(
            ticker=ticker,
            direction=direction,
            action=side,
            order_type="limit",
            quantity=qty,
            price=limit_price,
            limit_price=limit_price,
            order_id=order.id,
            notes=f"Limit order - {side.upper()} {qty} shares at ${limit_price}"
        )
        
        return {
            'order_id': order.id,
            'trade_id': trade_id,
            'status': 'submitted',
            'ticker': ticker,
            'qty': qty,
            'side': side,
            'direction': direction,
            'limit_price': limit_price
        }
        
    except Exception as e:
        print(f"❌ Error placing limit order for {ticker}: {e}")
        return {'error': str(e)}

def check_order_status(order_id: str) -> Dict:
    """
    Check the status of an order and update database if filled
    """
    try:
        order = trading_client.get_order_by_id(order_id)
        
        # If order is filled, update the database
        if order.status == 'filled' and order.filled_qty > 0:
            # Find the trade_id from active_trades
            trade_id = None
            for active_order_id, trade_info in active_trades.items():
                if active_order_id == order_id:
                    trade_id = trade_info.get('trade_id')
                    break
            
            if trade_id:
                # Update the trade record with fill information
                update_trade_fill(
                    trade_id=trade_id,
                    filled_price=float(order.filled_avg_price),
                    filled_quantity=int(order.filled_qty),
                    order_id=order_id
                )
        
        return {
            'order_id': order.id,
            'status': order.status,
            'filled_qty': order.filled_qty,
            'filled_avg_price': order.filled_avg_price,
            'side': order.side,
            'symbol': order.symbol
        }
    except Exception as e:
        print(f"Error checking order status: {e}")
        return {'error': str(e)}

def monitor_and_execute(ticker: str, entry_criteria: Dict, exit_criteria: Dict) -> Dict:
    """
    Monitor stock price and execute trades based on criteria from planning agent
    """
    print(f"🔍 Starting monitoring for {ticker}")
    print(f"Entry criteria: {entry_criteria}")
    print(f"Exit criteria: {exit_criteria}")
    
    # Validate required fields
    if 'direction' not in entry_criteria:
        return {'error': 'Direction is required in entry criteria'}
    
    if 'qty' not in entry_criteria:
        return {'error': 'Quantity is required in entry criteria'}
    
    # Ensure exit criteria has the same direction and quantity
    exit_criteria['direction'] = entry_criteria['direction']
    exit_criteria['qty'] = entry_criteria['qty']
    
    direction = entry_criteria['direction'].lower()
    qty = entry_criteria['qty']
    
    print(f"📈 Trade Direction: {direction.upper()}")
    print(f"📊 Quantity: {qty} shares")
    
    global monitoring
    monitoring = True
    entry_executed = False
    exit_executed = False
    entry_order = None
    exit_order = None
    
    while monitoring and not exit_executed:
        try:
            # Get current price
            current_price = get_current_price(ticker)
            if not current_price:
                print(f"Could not get price for {ticker}, retrying...")
                time.sleep(5)
                continue
            
            print(f"📊 {ticker} current price: ${current_price:.2f}")
            
            # Check entry criteria
            if not entry_executed:
                if _check_entry_criteria(current_price, entry_criteria):
                    print(f"🎯 Entry criteria met for {ticker} at ${current_price:.2f}")
                    entry_order = _execute_entry(ticker, entry_criteria)
                    if entry_order and 'error' not in entry_order:
                        entry_executed = True
                        print(f"✅ Entry order executed: {entry_order}")
                    else:
                        print(f"❌ Entry order failed: {entry_order}")
            
            # Check exit criteria (if entry was successful)
            if entry_executed and not exit_executed:
                if _check_exit_criteria(current_price, exit_criteria):
                    print(f"🎯 Exit criteria met for {ticker} at ${current_price:.2f}")
                    exit_order = _execute_exit(ticker, exit_criteria)
                    if exit_order and 'error' not in exit_order:
                        exit_executed = True
                        print(f"✅ Exit order executed: {exit_order}")
                        monitoring = False
                    else:
                        print(f"❌ Exit order failed: {exit_order}")
            
            # Wait before next check
            time.sleep(10)  # Check every 10 seconds
            
        except KeyboardInterrupt:
            print("🛑 Monitoring stopped by user")
            monitoring = False
            break
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            time.sleep(5)
    
    return {
        'entry_order': entry_order,
        'exit_order': exit_order,
        'entry_executed': entry_executed,
        'exit_executed': exit_executed,
        'direction': direction,
        'quantity': qty
    }

# ADK-Compatible Wrapper Functions (using primitive types)
def execute_trade_simple(ticker: str, direction: str, quantity: int, entry_price: float, 
                        stop_loss: float, take_profit: float, entry_trigger: str = "market") -> str:
    """
    Simple trade execution function for ADK compatibility
    Uses primitive types instead of Dict parameters
    """
    try:
        print(f"🚀 Executing trade for {ticker}")
        print(f"Direction: {direction}")
        print(f"Quantity: {quantity}")
        print(f"Entry Price: ${entry_price}")
        print(f"Stop Loss: ${stop_loss}")
        print(f"Take Profit: ${take_profit}")
        print(f"Entry Trigger: {entry_trigger}")
        
        # Create entry criteria
        entry_criteria = {
            'direction': direction.lower(),
            'qty': quantity,
            'entry_price': entry_price,
            'entry_trigger': entry_trigger
        }
        
        # Create exit criteria
        exit_criteria = {
            'direction': direction.lower(),
            'qty': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
        
        # Execute the trade
        result = monitor_and_execute(ticker, entry_criteria, exit_criteria)
        
        if 'error' in result:
            return f"❌ Trade execution failed: {result['error']}"
        else:
            return f"✅ Trade executed successfully: {result}"
            
    except Exception as e:
        return f"❌ Error executing trade: {str(e)}"

def place_simple_market_order(ticker: str, direction: str, quantity: int) -> str:
    """
    Place a simple market order for ADK compatibility
    """
    try:
        side = "buy" if direction.lower() == "long" else "sell"
        result = place_market_order(ticker, quantity, side, direction)
        
        if 'error' in result:
            return f"❌ Market order failed: {result['error']}"
        else:
            return f"✅ Market order placed: {side.upper()} {quantity} shares of {ticker}"
            
    except Exception as e:
        return f"❌ Error placing market order: {str(e)}"

def place_simple_limit_order(ticker: str, direction: str, quantity: int, limit_price: float) -> str:
    """
    Place a simple limit order for ADK compatibility
    """
    try:
        side = "buy" if direction.lower() == "long" else "sell"
        result = place_limit_order(ticker, quantity, limit_price, side, direction)
        
        if 'error' in result:
            return f"❌ Limit order failed: {result['error']}"
        else:
            return f"✅ Limit order placed: {side.upper()} {quantity} shares of {ticker} at ${limit_price}"
            
    except Exception as e:
        return f"❌ Error placing limit order: {str(e)}"

def place_simple_stop_order(ticker: str, direction: str, quantity: int, stop_price: float) -> str:
    """
    Place a simple stop order for ADK compatibility
    """
    try:
        side = "sell" if direction.lower() == "long" else "buy"
        result = place_stop_order(ticker, quantity, stop_price, side, direction)
        
        if 'error' in result:
            return f"❌ Stop order failed: {result['error']}"
        else:
            return f"✅ Stop order placed: {side.upper()} {quantity} shares of {ticker} at ${stop_price}"
            
    except Exception as e:
        return f"❌ Error placing stop order: {str(e)}"

def get_current_price_simple(ticker: str) -> str:
    """
    Get current price as string for ADK compatibility
    """
    try:
        price = get_current_price(ticker)
        if price:
            return f"${price:.2f}"
        else:
            return f"Could not get price for {ticker}"
    except Exception as e:
        return f"Error getting price for {ticker}: {str(e)}"

def _check_entry_criteria(current_price: float, criteria: Dict) -> bool:
    """
    Check if entry criteria are met
    """
    if 'entry_price' in criteria:
        entry_price = criteria['entry_price']
        if criteria.get('direction') == 'long' and current_price >= entry_price:
            return True
        elif criteria.get('direction') == 'short' and current_price <= entry_price:
            return True
    
    if 'percentage_change' in criteria:
        # This would need previous price data
        pass
    
    return False

def _check_exit_criteria(current_price: float, criteria: Dict) -> bool:
    """
    Check if exit criteria are met
    """
    if 'stop_loss' in criteria:
        if criteria.get('direction') == 'long' and current_price <= criteria['stop_loss']:
            return True
        elif criteria.get('direction') == 'short' and current_price >= criteria['stop_loss']:
            return True
    
    if 'take_profit' in criteria:
        if criteria.get('direction') == 'long' and current_price >= criteria['take_profit']:
            return True
        elif criteria.get('direction') == 'short' and current_price <= criteria['take_profit']:
            return True
    
    if 'time_limit' in criteria:
        # Check if time limit exceeded
        pass
    
    return False

def _execute_entry(ticker: str, criteria: Dict) -> Dict:
    """
    Execute entry order based on criteria from planning agent
    """
    qty = criteria.get('qty', 1)
    direction = criteria.get('direction', 'long').lower()
    order_type = criteria.get('order_type', 'market')
    
    # Determine side based on direction
    if direction == 'long':
        side = 'buy'
    elif direction == 'short':
        side = 'sell'
    else:
        return {'error': f'Invalid direction: {direction}. Must be "long" or "short"'}
    
    if order_type == 'market':
        return place_market_order(ticker, qty, side, direction)
    elif order_type == 'limit':
        limit_price = criteria.get('limit_price')
        if not limit_price:
            return {'error': 'Limit price required for limit orders'}
        return place_limit_order(ticker, qty, limit_price, side, direction)
    
    return {'error': 'Invalid order type'}

def _execute_exit(ticker: str, criteria: Dict) -> Dict:
    """
    Execute exit order based on criteria from planning agent
    """
    qty = criteria.get('qty', 1)
    direction = criteria.get('direction', 'long').lower()
    
    # Determine exit side based on direction
    if direction == 'long':
        exit_side = 'sell'  # Exit long position by selling
    elif direction == 'short':
        exit_side = 'buy'   # Exit short position by buying
    else:
        return {'error': f'Invalid direction: {direction}. Must be "long" or "short"'}
    
    if 'stop_loss' in criteria:
        return place_stop_order(ticker, qty, criteria['stop_loss'], exit_side, direction)
    elif 'take_profit' in criteria:
        return place_limit_order(ticker, qty, criteria['take_profit'], exit_side, direction)
    else:
        return place_market_order(ticker, qty, exit_side, direction)

def stop_monitoring():
    """
    Stop the monitoring process
    """
    global monitoring
    monitoring = False
    print("🛑 Monitoring stopped")

# Example usage
def example_execution():
    """
    Example showing the format expected from planning agent
    """
    # Example trade criteria from planning agent
    entry_criteria = {
        'entry_price': 150.0,
        'direction': 'long',  # or 'short'
        'qty': 10,
        'order_type': 'market'  # or 'limit'
    }
    
    exit_criteria = {
        'stop_loss': 145.0,
        'take_profit': 160.0
        # direction and qty will be copied from entry_criteria
    }
    
    print("📋 Example Trade Plan from Planning Agent:")
    print("Ticker: AAPL")
    print("Direction: LONG")
    print("Entry Price: $150.00")
    print("Stop Loss: $145.00")
    print("Take Profit: $160.00")
    print("Quantity: 10 shares")
    print()
    
    # Start monitoring
    result = monitor_and_execute('AAPL', entry_criteria, exit_criteria)
    print(f"Execution result: {result}")
    
    # Example for short position
    print("\n📋 Example Short Trade:")
    short_entry_criteria = {
        'entry_price': 150.0,
        'direction': 'short',
        'qty': 10,
        'order_type': 'market'
    }
    
    short_exit_criteria = {
        'stop_loss': 155.0,  # Higher price for short stop-loss
        'take_profit': 140.0  # Lower price for short take-profit
    }
    
    print("Direction: SHORT")
    print("Entry Price: $150.00")
    print("Stop Loss: $155.00 (higher price)")
    print("Take Profit: $140.00 (lower price)")
    print("Quantity: 10 shares")

if __name__ == "__main__":
    example_execution()

def add_trade_to_continuous_monitoring(ticker: str, direction: str, quantity: int, 
                                     entry_price: float, stop_loss: float, take_profit: float, 
                                     entry_trigger: str = "market") -> str:
    """
    Add a trade to continuous monitoring service for ADK compatibility
    """
    try:
        from api_helper.continuous_monitor import add_trade_for_monitoring
        
        trade_id = add_trade_for_monitoring(
            ticker=ticker,
            direction=direction,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_trigger=entry_trigger
        )
        
        return f"✅ Trade added to continuous monitoring with ID: {trade_id}"
        
    except Exception as e:
        return f"❌ Error adding trade to monitoring: {str(e)}"

def get_continuous_monitoring_status() -> str:
    """
    Get status of continuous monitoring for ADK compatibility
    """
    try:
        from api_helper.continuous_monitor import get_monitoring_status
        
        status = get_monitoring_status()
        
        result = f"📊 Monitoring Status:\n"
        result += f"- Active: {status['monitoring']}\n"
        result += f"- Active Trades: {status['active_trades']}\n"
        
        if status['trades']:
            result += f"- Trades:\n"
            for trade_id, trade in status['trades'].items():
                result += f"  • {trade['ticker']} ({trade['direction']}) - {trade['status']}\n"
        
        return result
        
    except Exception as e:
        return f"❌ Error getting monitoring status: {str(e)}"
