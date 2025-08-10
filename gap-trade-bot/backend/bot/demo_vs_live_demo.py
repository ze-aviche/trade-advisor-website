#!/usr/bin/env python3
"""
DEMO vs Live Trading Demonstration
Shows the critical differences without requiring broker connection
"""

import os
import sys
import time
import random
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger

logger = get_logger(__name__)

class TradingSimulator:
    """Simple trading simulator to demonstrate DEMO vs Live differences"""
    
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
        else:  # realistic/live
            self.fill_rate = 0.85     # 85% fill rate
            self.slippage = 0.02      # 2% slippage
            self.rejection_rate = 0.08 # 8% rejection rate
            self.execution_delay = 2.0 # Realistic delay
    
    def place_order(self, symbol: str, quantity: int, side: str, type: str = "market", price: float = None) -> Dict[str, Any]:
        """Place an order and simulate execution"""
        
        order_id = f"ORDER_{int(time.time() * 1000)}"
        order = {
            'order_id': order_id,
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'type': type,
            'price': price,
            'timestamp': datetime.now().isoformat(),
            'mode': self.mode
        }
        
        self.orders.append(order)
        
        # Simulate execution delay
        time.sleep(self.execution_delay)
        
        # Check for rejection
        if random.random() < self.rejection_rate:
            rejection = {
                'order_id': order_id,
                'status': 'rejected',
                'reason': random.choice(['insufficient_funds', 'invalid_order', 'market_closed', 'network_error']),
                'timestamp': datetime.now().isoformat()
            }
            self.rejections.append(rejection)
            logger.warning(f"❌ Order rejected: {rejection['reason']}")
            return rejection
        
        # Check for fill
        if random.random() < self.fill_rate:
            # Calculate fill price with slippage
            base_price = self._get_market_price(symbol)
            if side.upper() == 'BUY':
                fill_price = base_price * (1 + self.slippage)
            else:
                fill_price = base_price * (1 - self.slippage)
            
            execution = {
                'order_id': order_id,
                'status': 'filled',
                'fill_price': round(fill_price, 2),
                'fill_quantity': quantity,
                'slippage': self.slippage,
                'timestamp': datetime.now().isoformat()
            }
            self.executions.append(execution)
            logger.info(f"✅ Order filled: {symbol} {quantity} @ ${fill_price:.2f}")
            return execution
        else:
            # Order pending
            pending = {
                'order_id': order_id,
                'status': 'pending',
                'timestamp': datetime.now().isoformat()
            }
            logger.info(f"⏳ Order pending: {symbol}")
            return pending
    
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics"""
        total_orders = len(self.orders)
        total_fills = len([e for e in self.executions if e['status'] == 'filled'])
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

def run_demo_vs_live_comparison():
    """Run comparison between DEMO and Live trading"""
    
    logger.info("🧪 DEMO vs LIVE TRADING COMPARISON")
    logger.info("=" * 60)
    
    # Test scenarios
    test_orders = [
        {'symbol': 'AAPL', 'quantity': 100, 'side': 'BUY', 'type': 'market'},
        {'symbol': 'TSLA', 'quantity': 50, 'side': 'BUY', 'type': 'limit', 'price': 200.0},
        {'symbol': 'MSFT', 'quantity': 75, 'side': 'SELL', 'type': 'market'},
        {'symbol': 'GOOGL', 'quantity': 25, 'side': 'BUY', 'type': 'limit', 'price': 2500.0},
        {'symbol': 'AMZN', 'quantity': 30, 'side': 'SELL', 'type': 'market'}
    ]
    
    # Test DEMO mode
    logger.info("\n🎭 TESTING DEMO MODE")
    logger.info("-" * 30)
    demo_sim = TradingSimulator("demo")
    
    for i, order_spec in enumerate(test_orders, 1):
        logger.info(f"\n📋 Order {i}: {order_spec['symbol']} {order_spec['quantity']} {order_spec['side']}")
        result = demo_sim.place_order(**order_spec)
        logger.info(f"   Result: {result['status']}")
    
    demo_stats = demo_sim.get_stats()
    
    # Test Live mode
    logger.info("\n🔥 TESTING LIVE MODE")
    logger.info("-" * 30)
    live_sim = TradingSimulator("live")
    
    for i, order_spec in enumerate(test_orders, 1):
        logger.info(f"\n📋 Order {i}: {order_spec['symbol']} {order_spec['quantity']} {order_spec['side']}")
        result = live_sim.place_order(**order_spec)
        logger.info(f"   Result: {result['status']}")
        if result['status'] == 'filled':
            logger.info(f"   Fill Price: ${result['fill_price']}")
    
    live_stats = live_sim.get_stats()
    
    # Comparison
    logger.info("\n📊 COMPARISON RESULTS")
    logger.info("=" * 60)
    
    logger.info(f"DEMO MODE:")
    logger.info(f"  Fill Rate: {demo_stats['fill_rate']:.1%}")
    logger.info(f"  Rejection Rate: {demo_stats['rejection_rate']:.1%}")
    logger.info(f"  Slippage: {demo_stats['avg_slippage']:.1%}")
    logger.info(f"  Execution: Instant")
    
    logger.info(f"\nLIVE MODE:")
    logger.info(f"  Fill Rate: {live_stats['fill_rate']:.1%}")
    logger.info(f"  Rejection Rate: {live_stats['rejection_rate']:.1%}")
    logger.info(f"  Slippage: {live_stats['avg_slippage']:.1%}")
    logger.info(f"  Execution: {live_sim.execution_delay}s delay")
    
    # Key insights
    logger.info(f"\n⚠️ CRITICAL INSIGHTS:")
    logger.info(f"  1. DEMO gives false confidence")
    logger.info(f"  2. Live trading has real risks")
    logger.info(f"  3. Fill rates vary significantly")
    logger.info(f"  4. Rejections are common in live trading")
    logger.info(f"  5. Slippage affects profitability")
    
    # Recommendations
    logger.info(f"\n💡 RECOMMENDATIONS:")
    logger.info(f"  1. Test with realistic conditions")
    logger.info(f"  2. Start with small position sizes")
    logger.info(f"  3. Monitor fill rates and rejections")
    logger.info(f"  4. Use proper risk management")
    logger.info(f"  5. Consider Windows for DAS Trader")

if __name__ == "__main__":
    run_demo_vs_live_comparison()
