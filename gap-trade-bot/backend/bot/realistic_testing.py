#!/usr/bin/env python3
"""
Realistic Testing Framework
Bridges the gap between DEMO and live trading with realistic market simulation
"""

import os
import sys
import time
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config
from market_simulator import MarketSimulator, MarketCondition
from order_manager import EnhancedOrderManager

logger = get_logger(__name__)

class RealisticTester:
    """Realistic testing framework"""
    
    def __init__(self):
        self.market_simulator = MarketSimulator("realistic")
        self.order_manager = EnhancedOrderManager()
        self.test_scenarios = []
        self.test_results = []
        
        # Test configuration
        self.test_symbols = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
        self.test_quantities = [100, 500, 1000, 2000]
        self.test_prices = [150.0, 200.0, 300.0, 500.0]
        
        logger.info("🧪 Realistic testing framework initialized")
    
    def add_test_scenario(self, name: str, market_condition: MarketCondition, orders: List[Dict[str, Any]]):
        """Add a test scenario"""
        scenario = {
            'name': name,
            'market_condition': market_condition,
            'orders': orders,
            'expected_results': []
        }
        self.test_scenarios.append(scenario)
        logger.info(f"📋 Added test scenario: {name}")
    
    def create_basic_scenarios(self):
        """Create basic test scenarios"""
        
        # Scenario 1: Normal Market
        normal_orders = [
            {'type': 'market', 'symbol': 'AAPL', 'quantity': 100, 'side': 'BUY'},
            {'type': 'limit', 'symbol': 'TSLA', 'quantity': 50, 'side': 'BUY', 'price': 200.0},
            {'type': 'stop', 'symbol': 'MSFT', 'quantity': 75, 'side': 'SELL', 'price': 280.0}
        ]
        self.add_test_scenario("Normal Market", MarketCondition.NORMAL, normal_orders)
        
        # Scenario 2: Volatile Market
        volatile_orders = [
            {'type': 'market', 'symbol': 'AAPL', 'quantity': 500, 'side': 'BUY'},
            {'type': 'market', 'symbol': 'TSLA', 'quantity': 200, 'side': 'SELL'},
            {'type': 'limit', 'symbol': 'GOOGL', 'quantity': 25, 'side': 'BUY', 'price': 2500.0}
        ]
        self.add_test_scenario("Volatile Market", MarketCondition.VOLATILE, volatile_orders)
        
        # Scenario 3: Gapping Market
        gapping_orders = [
            {'type': 'market', 'symbol': 'AAPL', 'quantity': 1000, 'side': 'BUY'},
            {'type': 'stop', 'symbol': 'TSLA', 'quantity': 300, 'side': 'SELL', 'price': 180.0},
            {'type': 'limit', 'symbol': 'AMZN', 'quantity': 50, 'side': 'BUY', 'price': 2900.0}
        ]
        self.add_test_scenario("Gapping Market", MarketCondition.GAPPING, gapping_orders)
        
        # Scenario 4: Fast Market
        fast_orders = [
            {'type': 'market', 'symbol': 'AAPL', 'quantity': 200, 'side': 'BUY'},
            {'type': 'market', 'symbol': 'TSLA', 'quantity': 100, 'side': 'BUY'},
            {'type': 'market', 'symbol': 'MSFT', 'quantity': 150, 'side': 'SELL'}
        ]
        self.add_test_scenario("Fast Market", MarketCondition.FAST, fast_orders)
        
        # Scenario 5: Slow Market
        slow_orders = [
            {'type': 'limit', 'symbol': 'AAPL', 'quantity': 100, 'side': 'BUY', 'price': 145.0},
            {'type': 'limit', 'symbol': 'TSLA', 'quantity': 50, 'side': 'BUY', 'price': 195.0},
            {'type': 'limit', 'symbol': 'MSFT', 'quantity': 75, 'side': 'SELL', 'price': 305.0}
        ]
        self.add_test_scenario("Slow Market", MarketCondition.SLOW, slow_orders)
    
    async def run_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test scenario"""
        try:
            scenario_name = scenario['name']
            market_condition = scenario['market_condition']
            orders = scenario['orders']
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🧪 Running Scenario: {scenario_name}")
            logger.info(f"📊 Market Condition: {market_condition.value}")
            logger.info(f"📋 Orders to Test: {len(orders)}")
            logger.info(f"{'='*60}")
            
            # Set market condition
            self.market_simulator.set_market_condition(market_condition)
            
            # Reset simulation
            self.market_simulator.reset_simulation()
            
            # Execute orders
            results = []
            for i, order_spec in enumerate(orders, 1):
                logger.info(f"\n📋 Order {i}/{len(orders)}: {order_spec}")
                
                try:
                    if order_spec['type'] == 'market':
                        result = await self.order_manager.place_market_order(
                            order_spec['symbol'],
                            order_spec['quantity'],
                            order_spec['side']
                        )
                    elif order_spec['type'] == 'limit':
                        result = await self.order_manager.place_limit_order(
                            order_spec['symbol'],
                            order_spec['quantity'],
                            order_spec['side'],
                            order_spec['price']
                        )
                    elif order_spec['type'] == 'stop':
                        result = await self.order_manager.place_stop_order(
                            order_spec['symbol'],
                            order_spec['quantity'],
                            order_spec['price']
                        )
                    else:
                        logger.error(f"❌ Unknown order type: {order_spec['type']}")
                        result = None
                    
                    if result:
                        # Simulate execution
                        execution = self.market_simulator.simulate_order_execution(result)
                        result['execution'] = execution
                        
                        logger.info(f"✅ Order executed: {execution.get('status', 'unknown')}")
                    else:
                        logger.error("❌ Order failed to place")
                        result = {'error': 'Order placement failed'}
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"❌ Error executing order: {e}")
                    results.append({'error': str(e)})
                
                # Wait between orders
                await asyncio.sleep(1)
            
            # Get final statistics
            account_info = self.market_simulator.get_account_info()
            simulation_stats = self.market_simulator.get_simulation_stats()
            
            scenario_result = {
                'scenario_name': scenario_name,
                'market_condition': market_condition.value,
                'orders_executed': len(results),
                'results': results,
                'account_info': account_info,
                'simulation_stats': simulation_stats,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"\n📊 Scenario Results:")
            logger.info(f"   Orders: {len(results)}")
            logger.info(f"   Fill Rate: {simulation_stats['fill_rate']:.2%}")
            logger.info(f"   Rejection Rate: {simulation_stats['rejection_rate']:.2%}")
            logger.info(f"   Buying Power: ${account_info['buying_power']:.2f}")
            logger.info(f"   Positions: {account_info['total_positions']}")
            
            return scenario_result
            
        except Exception as e:
            logger.error(f"❌ Error running scenario: {e}")
            return {'error': str(e)}
    
    async def run_all_scenarios(self) -> List[Dict[str, Any]]:
        """Run all test scenarios"""
        try:
            logger.info("🚀 Starting comprehensive realistic testing")
            
            # Create scenarios if none exist
            if not self.test_scenarios:
                self.create_basic_scenarios()
            
            all_results = []
            
            for scenario in self.test_scenarios:
                result = await self.run_scenario(scenario)
                all_results.append(result)
                
                # Wait between scenarios
                await asyncio.sleep(2)
            
            # Generate summary report
            await self.generate_summary_report(all_results)
            
            return all_results
            
        except Exception as e:
            logger.error(f"❌ Error running all scenarios: {e}")
            return []
    
    async def generate_summary_report(self, results: List[Dict[str, Any]]):
        """Generate summary report"""
        try:
            logger.info(f"\n{'='*80}")
            logger.info("📊 COMPREHENSIVE TESTING SUMMARY REPORT")
            logger.info(f"{'='*80}")
            
            total_scenarios = len(results)
            successful_scenarios = len([r for r in results if 'error' not in r])
            
            logger.info(f"📋 Total Scenarios: {total_scenarios}")
            logger.info(f"✅ Successful: {successful_scenarios}")
            logger.info(f"❌ Failed: {total_scenarios - successful_scenarios}")
            
            # Market condition analysis
            condition_stats = {}
            for result in results:
                if 'error' not in result:
                    condition = result['market_condition']
                    if condition not in condition_stats:
                        condition_stats[condition] = {'scenarios': 0, 'total_orders': 0, 'fill_rate': 0}
                    
                    condition_stats[condition]['scenarios'] += 1
                    condition_stats[condition]['total_orders'] += result['orders_executed']
                    condition_stats[condition]['fill_rate'] += result['simulation_stats']['fill_rate']
            
            logger.info(f"\n📊 Market Condition Analysis:")
            for condition, stats in condition_stats.items():
                avg_fill_rate = stats['fill_rate'] / stats['scenarios'] if stats['scenarios'] > 0 else 0
                logger.info(f"   {condition.upper()}:")
                logger.info(f"     Scenarios: {stats['scenarios']}")
                logger.info(f"     Total Orders: {stats['total_orders']}")
                logger.info(f"     Avg Fill Rate: {avg_fill_rate:.2%}")
            
            # Risk assessment
            logger.info(f"\n⚠️ RISK ASSESSMENT:")
            logger.info(f"   DEMO vs Live Differences:")
            logger.info(f"     • DEMO: Perfect fills, no slippage, no rejections")
            logger.info(f"     • Live: Variable fills, slippage, rejections, delays")
            logger.info(f"     • Recommendation: Test extensively in realistic mode")
            
            # Recommendations
            logger.info(f"\n💡 RECOMMENDATIONS:")
            logger.info(f"   1. Use realistic testing before live trading")
            logger.info(f"   2. Start with small position sizes")
            logger.info(f"   3. Monitor fill rates and rejections")
            logger.info(f"   4. Test error handling thoroughly")
            logger.info(f"   5. Use proper risk management")
            
            logger.info(f"\n{'='*80}")
            
        except Exception as e:
            logger.error(f"❌ Error generating summary report: {e}")
    
    async def stress_test(self, duration_minutes: int = 5):
        """Run stress test for specified duration"""
        try:
            logger.info(f"🔥 Starting stress test for {duration_minutes} minutes")
            
            start_time = time.time()
            end_time = start_time + (duration_minutes * 60)
            
            orders_placed = 0
            orders_filled = 0
            orders_rejected = 0
            
            while time.time() < end_time:
                # Randomly select market condition
                condition = random.choice(list(MarketCondition))
                self.market_simulator.set_market_condition(condition)
                
                # Place random order
                symbol = random.choice(self.test_symbols)
                quantity = random.choice(self.test_quantities)
                side = random.choice(['BUY', 'SELL'])
                order_type = random.choice(['market', 'limit'])
                
                try:
                    if order_type == 'market':
                        result = await self.order_manager.place_market_order(symbol, quantity, side)
                    else:
                        price = random.choice(self.test_prices)
                        result = await self.order_manager.place_limit_order(symbol, quantity, side, price)
                    
                    if result:
                        orders_placed += 1
                        
                        # Simulate execution
                        execution = self.market_simulator.simulate_order_execution(result)
                        
                        if execution.get('status') == 'filled':
                            orders_filled += 1
                        elif execution.get('status') == 'rejected':
                            orders_rejected += 1
                    
                except Exception as e:
                    logger.error(f"Stress test error: {e}")
                
                # Wait random interval
                await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Stress test results
            duration = time.time() - start_time
            fill_rate = orders_filled / orders_placed if orders_placed > 0 else 0
            rejection_rate = orders_rejected / orders_placed if orders_placed > 0 else 0
            
            logger.info(f"\n🔥 STRESS TEST RESULTS:")
            logger.info(f"   Duration: {duration:.1f} seconds")
            logger.info(f"   Orders Placed: {orders_placed}")
            logger.info(f"   Orders Filled: {orders_filled}")
            logger.info(f"   Orders Rejected: {orders_rejected}")
            logger.info(f"   Fill Rate: {fill_rate:.2%}")
            logger.info(f"   Rejection Rate: {rejection_rate:.2%}")
            logger.info(f"   Orders/Second: {orders_placed/duration:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Error in stress test: {e}")

# Global realistic tester instance
realistic_tester = RealisticTester()

async def main():
    """Main testing function"""
    try:
        logger.info("🧪 Starting realistic testing framework")
        
        # Run comprehensive scenarios
        results = await realistic_tester.run_all_scenarios()
        
        # Run stress test
        await realistic_tester.stress_test(duration_minutes=2)
        
        logger.info("✅ Realistic testing completed")
        
    except Exception as e:
        logger.error(f"❌ Error in main testing: {e}")

if __name__ == "__main__":
    # Run the realistic testing
    asyncio.run(main())
