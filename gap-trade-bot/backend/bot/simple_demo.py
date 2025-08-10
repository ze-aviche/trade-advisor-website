#!/usr/bin/env python3
"""
Simple DEMO vs Live Trading Demonstration
Shows the critical differences without any dependencies
"""

import time
import random
from datetime import datetime

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_section(title):
    print(f"\n{'-'*40}")
    print(f"📋 {title}")
    print(f"{'-'*40}")

class SimpleTradingSimulator:
    """Simple trading simulator"""
    
    def __init__(self, mode: str = "demo"):
        self.mode = mode
        self.orders = []
        self.executions = []
        self.rejections = []
        
        # Mode-specific settings
        if mode == "demo":
            self.fill_rate = 1.0      # 100% fill rate
            self.slippage = 0.0       # No slippage
            self.rejection_rate = 0.0 # No rejections
            self.execution_delay = 0.1 # Fast execution
            print(f"🎭 DEMO MODE: Perfect execution, no risks")
        else:  # realistic/live
            self.fill_rate = 0.85     # 85% fill rate
            self.slippage = 0.02      # 2% slippage
            self.rejection_rate = 0.08 # 8% rejection rate
            self.execution_delay = 2.0 # Realistic delay
            print(f"🔥 LIVE MODE: Realistic market conditions")
    
    def place_order(self, symbol: str, quantity: int, side: str, order_type: str = "market", price: float = None):
        """Place an order and simulate execution"""
        
        order_id = f"ORDER_{int(time.time() * 1000)}"
        print(f"\n📋 Placing {order_type} order: {symbol} {quantity} shares {side}")
        
        # Simulate execution delay
        print(f"⏳ Processing order...")
        time.sleep(self.execution_delay)
        
        # Check for rejection
        if random.random() < self.rejection_rate:
            reason = random.choice(['insufficient_funds', 'invalid_order', 'market_closed', 'network_error'])
            print(f"❌ Order REJECTED: {reason}")
            self.rejections.append({'order_id': order_id, 'reason': reason})
            return {'status': 'rejected', 'reason': reason}
        
        # Check for fill
        if random.random() < self.fill_rate:
            # Calculate fill price with slippage
            base_price = self._get_market_price(symbol)
            if side.upper() == 'BUY':
                fill_price = base_price * (1 + self.slippage)
            else:
                fill_price = base_price * (1 - self.slippage)
            
            print(f"✅ Order FILLED: {symbol} {quantity} @ ${fill_price:.2f}")
            if self.slippage > 0:
                print(f"   💸 Slippage: {self.slippage:.1%}")
            
            self.executions.append({'order_id': order_id, 'fill_price': fill_price})
            return {'status': 'filled', 'fill_price': fill_price}
        else:
            print(f"⏳ Order PENDING: {symbol}")
            return {'status': 'pending'}
    
    def _get_market_price(self, symbol: str) -> float:
        """Get simulated market price"""
        base_prices = {
            'AAPL': 150.0,
            'TSLA': 200.0,
            'MSFT': 300.0,
            'GOOGL': 2500.0,
            'AMZN': 3000.0
        }
        return base_prices.get(symbol, 100.0)
    
    def get_stats(self):
        """Get trading statistics"""
        total_orders = len(self.orders)
        total_fills = len(self.executions)
        total_rejections = len(self.rejections)
        
        fill_rate = total_fills / total_orders if total_orders > 0 else 0
        rejection_rate = total_rejections / total_orders if total_orders > 0 else 0
        
        return {
            'mode': self.mode,
            'total_orders': total_orders,
            'total_fills': total_fills,
            'total_rejections': total_rejections,
            'fill_rate': fill_rate,
            'rejection_rate': rejection_rate,
            'avg_slippage': self.slippage
        }

def main():
    """Main demonstration function"""
    
    print_header("DEMO vs LIVE TRADING COMPARISON")
    print("This demonstrates why DEMO mode can be misleading!")
    
    # Test scenarios
    test_orders = [
        {'symbol': 'AAPL', 'quantity': 100, 'side': 'BUY', 'order_type': 'market'},
        {'symbol': 'TSLA', 'quantity': 50, 'side': 'BUY', 'order_type': 'limit', 'price': 200.0},
        {'symbol': 'MSFT', 'quantity': 75, 'side': 'SELL', 'order_type': 'market'},
        {'symbol': 'GOOGL', 'quantity': 25, 'side': 'BUY', 'order_type': 'limit', 'price': 2500.0},
        {'symbol': 'AMZN', 'quantity': 30, 'side': 'SELL', 'order_type': 'market'}
    ]
    
    # Test DEMO mode
    print_section("TESTING DEMO MODE")
    demo_sim = SimpleTradingSimulator("demo")
    
    for i, order_spec in enumerate(test_orders, 1):
        print(f"\n--- Order {i} ---")
        result = demo_sim.place_order(**order_spec)
    
    demo_stats = demo_sim.get_stats()
    
    # Test Live mode
    print_section("TESTING LIVE MODE")
    live_sim = SimpleTradingSimulator("live")
    
    for i, order_spec in enumerate(test_orders, 1):
        print(f"\n--- Order {i} ---")
        result = live_sim.place_order(**order_spec)
    
    live_stats = live_sim.get_stats()
    
    # Comparison
    print_header("COMPARISON RESULTS")
    
    print(f"DEMO MODE:")
    print(f"  Fill Rate: {demo_stats['fill_rate']:.1%}")
    print(f"  Rejection Rate: {demo_stats['rejection_rate']:.1%}")
    print(f"  Slippage: {demo_stats['avg_slippage']:.1%}")
    print(f"  Execution: Instant")
    
    print(f"\nLIVE MODE:")
    print(f"  Fill Rate: {live_stats['fill_rate']:.1%}")
    print(f"  Rejection Rate: {live_stats['rejection_rate']:.1%}")
    print(f"  Slippage: {live_stats['avg_slippage']:.1%}")
    print(f"  Execution: {live_sim.execution_delay}s delay")
    
    # Key insights
    print_header("CRITICAL INSIGHTS")
    print("1. 🎭 DEMO gives false confidence")
    print("2. 🔥 Live trading has real risks")
    print("3. 📊 Fill rates vary significantly")
    print("4. ❌ Rejections are common in live trading")
    print("5. 💸 Slippage affects profitability")
    
    # Recommendations
    print_header("RECOMMENDATIONS")
    print("1. Test with realistic conditions")
    print("2. Start with small position sizes")
    print("3. Monitor fill rates and rejections")
    print("4. Use proper risk management")
    print("5. Consider Windows for DAS Trader")
    
    # Windows recommendation
    print_header("WINDOWS REQUIREMENT")
    print("⚠️  DAS Trader Pro only runs on Windows!")
    print("Options:")
    print("  • Windows machine (recommended)")
    print("  • Windows VM on Mac")
    print("  • Windows server/cloud")
    print("  • Alternative brokers (Alpaca, IB, etc.)")

if __name__ == "__main__":
    main()
