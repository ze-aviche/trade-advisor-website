import asyncio
import time
import threading
from datetime import datetime
from typing import Dict, List
from api_helper.execute_trades_alpaca import (
    get_current_price, 
    place_market_order, 
    place_limit_order, 
    place_stop_order,
    log_trade_submission,
    update_trade_fill
)

class ContinuousTradeMonitor:
    """
    Standalone service for continuously monitoring and executing trades
    """
    
    def __init__(self):
        self.active_trades = {}
        self.monitoring = False
        self.monitor_thread = None
        
    def add_trade_to_monitor(self, trade_id: str, ticker: str, direction: str, 
                            quantity: int, entry_price: float, stop_loss: float, 
                            take_profit: float, entry_trigger: str = "market"):
        """
        Add a trade to the monitoring queue
        """
        self.active_trades[trade_id] = {
            'ticker': ticker,
            'direction': direction.lower(),
            'quantity': quantity,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_trigger': entry_trigger,
            'status': 'waiting_entry',
            'entry_order': None,
            'exit_order': None,
            'created_at': datetime.now()
        }
        
        print(f"📊 Added {ticker} to monitoring queue")
        print(f"Entry: ${entry_price}, Stop: ${stop_loss}, Target: ${take_profit}")
        
        # Start monitoring if not already running
        if not self.monitoring:
            self.start_monitoring()
    
    def start_monitoring(self):
        """
        Start the monitoring thread
        """
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            print("🔄 Continuous monitoring started")
    
    def stop_monitoring(self):
        """
        Stop the monitoring thread
        """
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("🛑 Continuous monitoring stopped")
    
    def _monitor_loop(self):
        """
        Main monitoring loop that runs in a separate thread
        """
        while self.monitoring:
            try:
                # Check each active trade
                for trade_id, trade in list(self.active_trades.items()):
                    self._check_trade(trade_id, trade)
                
                # Sleep for 10 seconds before next check
                time.sleep(10)
                
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _check_trade(self, trade_id: str, trade: Dict):
        """
        Check if a specific trade meets entry or exit criteria
        """
        try:
            current_price = get_current_price(trade['ticker'])
            if not current_price:
                return
            
            print(f"📊 {trade['ticker']} current price: ${current_price:.2f}")
            
            # Check entry criteria
            if trade['status'] == 'waiting_entry':
                if self._check_entry_criteria(current_price, trade):
                    print(f"🎯 Entry criteria met for {trade['ticker']} at ${current_price:.2f}")
                    self._execute_entry(trade_id, trade)
            
            # Check exit criteria
            elif trade['status'] == 'in_position':
                if self._check_exit_criteria(current_price, trade):
                    print(f"🎯 Exit criteria met for {trade['ticker']} at ${current_price:.2f}")
                    self._execute_exit(trade_id, trade)
                    
        except Exception as e:
            print(f"❌ Error checking trade {trade_id}: {e}")
    
    def _check_entry_criteria(self, current_price: float, trade: Dict) -> bool:
        """
        Check if entry criteria are met
        """
        entry_price = trade['entry_price']
        direction = trade['direction']
        
        if direction == 'long' and current_price >= entry_price:
            return True
        elif direction == 'short' and current_price <= entry_price:
            return True
        
        return False
    
    def _check_exit_criteria(self, current_price: float, trade: Dict) -> bool:
        """
        Check if exit criteria are met
        """
        stop_loss = trade['stop_loss']
        take_profit = trade['take_profit']
        direction = trade['direction']
        
        if direction == 'long':
            # Exit long position if price hits stop loss (below) or take profit (above)
            return current_price <= stop_loss or current_price >= take_profit
        else:
            # Exit short position if price hits stop loss (above) or take profit (below)
            return current_price >= stop_loss or current_price <= take_profit
    
    def _execute_entry(self, trade_id: str, trade: Dict):
        """
        Execute entry order
        """
        try:
            ticker = trade['ticker']
            direction = trade['direction']
            quantity = trade['quantity']
            entry_trigger = trade['entry_trigger']
            
            # Determine order side
            side = "buy" if direction == "long" else "sell"
            
            # Place entry order
            if entry_trigger.lower() == "market":
                result = place_market_order(ticker, quantity, side, direction)
            else:
                # For limit orders, use entry price as limit
                result = place_limit_order(ticker, quantity, trade['entry_price'], side, direction)
            
            if result and 'error' not in result:
                trade['status'] = 'in_position'
                trade['entry_order'] = result
                print(f"✅ Entry order executed for {ticker}: {result}")
            else:
                print(f"❌ Entry order failed for {ticker}: {result}")
                
        except Exception as e:
            print(f"❌ Error executing entry for {trade_id}: {e}")
    
    def _execute_exit(self, trade_id: str, trade: Dict):
        """
        Execute exit order
        """
        try:
            ticker = trade['ticker']
            direction = trade['direction']
            quantity = trade['quantity']
            
            # Determine order side (opposite of entry)
            side = "sell" if direction == "long" else "buy"
            
            # Place exit order (market order for immediate execution)
            result = place_market_order(ticker, quantity, side, direction)
            
            if result and 'error' not in result:
                trade['status'] = 'completed'
                trade['exit_order'] = result
                print(f"✅ Exit order executed for {ticker}: {result}")
                
                # Remove from active trades
                del self.active_trades[trade_id]
            else:
                print(f"❌ Exit order failed for {ticker}: {result}")
                
        except Exception as e:
            print(f"❌ Error executing exit for {trade_id}: {e}")
    
    def get_active_trades(self) -> Dict:
        """
        Get current active trades
        """
        return self.active_trades
    
    def remove_trade(self, trade_id: str):
        """
        Remove a trade from monitoring
        """
        if trade_id in self.active_trades:
            del self.active_trades[trade_id]
            print(f"🗑️ Removed trade {trade_id} from monitoring")

# Global monitor instance
trade_monitor = ContinuousTradeMonitor()

def start_continuous_monitoring():
    """
    Start the continuous monitoring service
    """
    trade_monitor.start_monitoring()
    return trade_monitor

def add_trade_for_monitoring(ticker: str, direction: str, quantity: int, 
                           entry_price: float, stop_loss: float, take_profit: float, 
                           entry_trigger: str = "market") -> str:
    """
    Add a trade to continuous monitoring
    """
    trade_id = f"{ticker}_{direction}_{int(time.time())}"
    trade_monitor.add_trade_to_monitor(trade_id, ticker, direction, quantity, 
                                     entry_price, stop_loss, take_profit, entry_trigger)
    return trade_id

def get_monitoring_status() -> Dict:
    """
    Get current monitoring status
    """
    return {
        'monitoring': trade_monitor.monitoring,
        'active_trades': len(trade_monitor.active_trades),
        'trades': trade_monitor.get_active_trades()
    }

def stop_continuous_monitoring():
    """
    Stop the continuous monitoring service
    """
    trade_monitor.stop_monitoring()

# Example usage
if __name__ == "__main__":
    # Start monitoring
    start_continuous_monitoring()
    
    # Add a test trade
    trade_id = add_trade_for_monitoring(
        ticker="AAPL",
        direction="long",
        quantity=10,
        entry_price=150.00,
        stop_loss=145.00,
        take_profit=160.00,
        entry_trigger="market"
    )
    
    print(f"Added trade {trade_id} to monitoring")
    
    # Keep running for a while
    try:
        while True:
            time.sleep(30)
            status = get_monitoring_status()
            print(f"Monitoring status: {status['active_trades']} active trades")
    except KeyboardInterrupt:
        print("Stopping monitoring...")
        stop_continuous_monitoring() 