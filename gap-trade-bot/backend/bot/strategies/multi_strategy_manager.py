#!/usr/bin/env python3
"""
Multi-Strategy Manager
Manages multiple trading strategies and evaluates stocks against all strategies
"""

import sys
import os
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any
import asyncio

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from logging_config import get_logger
from break_out import BreakOutStrategy
from gap_up_short import GapUpShortStrategy

logger = get_logger(__name__)

class MultiStrategyManager:
    """Manages multiple trading strategies and evaluates stocks against all strategies"""
    
    def __init__(self):
        self.name = "multi_strategy_manager"
        self.description = "Manages break_out and gap_up_short strategies"
        
        # Initialize strategies
        self.strategies = {
            'break_out': BreakOutStrategy(),
            'gap_up_short': GapUpShortStrategy()
        }
        
        # Strategy configuration
        self.config = {
            'min_gap_percentage': 25,  # Minimum gap to consider for any strategy
            'max_concurrent_positions': 5,  # Maximum concurrent positions per strategy
            'strategy_weights': {
                'break_out': 1.0,
                'gap_up_short': 1.0
            }
        }
        
        # Active positions tracking
        self.active_positions = {
            'break_out': [],
            'gap_up_short': []
        }
        
        # Strategy states
        self.strategy_states = {}
        
    def get_min_gap_threshold(self) -> float:
        """Get the minimum gap percentage to consider for any strategy"""
        return self.config['min_gap_percentage']
    
    def evaluate_stock_for_all_strategies(self, ticker: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a stock against all strategies"""
        try:
            logger.info(f"🔍 Evaluating {ticker} against all strategies...")
            
            # Check if stock meets minimum gap threshold
            gap_percent = current_data.get('gap_percent', 0)
            if gap_percent < self.config['min_gap_percentage']:
                logger.info(f"❌ {ticker} gap {gap_percent:.2f}% below minimum threshold {self.config['min_gap_percentage']}%")
                return {
                    'ticker': ticker,
                    'meets_minimum_threshold': False,
                    'gap_percent': gap_percent,
                    'strategies': {}
                }
            
            # Evaluate against each strategy
            strategy_results = {}
            total_confidence = 0
            valid_strategies = 0
            
            for strategy_name, strategy in self.strategies.items():
                try:
                    logger.info(f"📊 Evaluating {ticker} for {strategy_name} strategy...")
                    
                    # Analyze entry conditions for this strategy
                    analysis = strategy.analyze_entry_conditions(ticker, current_data)
                    
                    if 'error' in analysis:
                        logger.error(f"❌ Error analyzing {ticker} for {strategy_name}: {analysis['error']}")
                        strategy_results[strategy_name] = {
                            'analysis': analysis,
                            'should_enter': False,
                            'confidence': 0,
                            'error': analysis['error']
                        }
                        continue
                    
                    # Check if we should enter position
                    should_enter = strategy.should_enter_position(analysis)
                    confidence = analysis.get('confidence', 0)
                    
                    # Check if we have room for more positions
                    can_add_position = len(self.active_positions[strategy_name]) < self.config['max_concurrent_positions']
                    
                    strategy_results[strategy_name] = {
                        'analysis': analysis,
                        'should_enter': should_enter and can_add_position,
                        'confidence': confidence,
                        'can_add_position': can_add_position,
                        'active_positions_count': len(self.active_positions[strategy_name])
                    }
                    
                    if should_enter and can_add_position:
                        total_confidence += confidence * self.config['strategy_weights'][strategy_name]
                        valid_strategies += 1
                        logger.info(f"✅ {ticker} qualifies for {strategy_name} - Confidence: {confidence:.1f}%")
                    else:
                        if not should_enter:
                            logger.info(f"❌ {ticker} does not qualify for {strategy_name} - Confidence: {confidence:.1f}%")
                        if not can_add_position:
                            logger.info(f"⚠️ {ticker} cannot be added to {strategy_name} - Max positions reached")
                
                except Exception as e:
                    logger.error(f"❌ Error evaluating {ticker} for {strategy_name}: {e}")
                    strategy_results[strategy_name] = {
                        'analysis': {'error': str(e)},
                        'should_enter': False,
                        'confidence': 0,
                        'error': str(e)
                    }
            
            # Calculate overall results
            avg_confidence = total_confidence / valid_strategies if valid_strategies > 0 else 0
            best_strategy = self._get_best_strategy(strategy_results)
            
            result = {
                'ticker': ticker,
                'meets_minimum_threshold': True,
                'gap_percent': gap_percent,
                'strategies': strategy_results,
                'best_strategy': best_strategy,
                'avg_confidence': avg_confidence,
                'valid_strategies_count': valid_strategies
            }
            
            logger.info(f"📊 {ticker} evaluation complete - Best strategy: {best_strategy}, Avg confidence: {avg_confidence:.1f}%")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error evaluating {ticker} for all strategies: {e}")
            return {
                'ticker': ticker,
                'meets_minimum_threshold': False,
                'error': str(e),
                'strategies': {}
            }
    
    def _get_best_strategy(self, strategy_results: Dict[str, Any]) -> Optional[str]:
        """Get the best strategy based on confidence and conditions"""
        best_strategy = None
        best_confidence = 0
        
        for strategy_name, result in strategy_results.items():
            if result.get('should_enter', False) and result.get('confidence', 0) > best_confidence:
                best_strategy = strategy_name
                best_confidence = result['confidence']
        
        return best_strategy
    
    def execute_strategy_entry(self, ticker: str, strategy_name: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute entry for a specific strategy"""
        try:
            if strategy_name not in self.strategies:
                logger.error(f"❌ Strategy {strategy_name} not found")
                return {'error': f'Strategy {strategy_name} not found'}
            
            strategy = self.strategies[strategy_name]
            current_price = current_data.get('current_price', 0)
            day_high = current_data.get('day_high', 0)
            
            # Execute entry
            entry_result = strategy.execute_entry(ticker, current_price, day_high)
            
            if 'error' not in entry_result:
                # Add to active positions
                position_info = {
                    'ticker': ticker,
                    'strategy': strategy_name,
                    'entry_price': entry_result['entry_price'],
                    'entry_time': entry_result['entry_time'],
                    'target_price': entry_result['target_price'],
                    'stop_loss_price': entry_result['stop_loss_price'],
                    'position_size': entry_result['position_size']
                }
                
                self.active_positions[strategy_name].append(position_info)
                
                logger.info(f"📈 ENTRY EXECUTED - {ticker} for {strategy_name}")
                logger.info(f"   Entry Price: ${entry_result['entry_price']:.2f}")
                logger.info(f"   Target: ${entry_result['target_price']:.2f}")
                logger.info(f"   Stop Loss: ${entry_result['stop_loss_price']:.2f}")
                logger.info(f"   Active positions for {strategy_name}: {len(self.active_positions[strategy_name])}")
            
            return entry_result
            
        except Exception as e:
            logger.error(f"❌ Error executing entry for {ticker} on {strategy_name}: {e}")
            return {'error': str(e)}
    
    def check_exits_for_all_positions(self, current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check if any positions should be exited"""
        exits = []
        
        for strategy_name, positions in self.active_positions.items():
            strategy = self.strategies[strategy_name]
            current_price = current_data.get('current_price', 0)
            
            for position in positions[:]:  # Copy list to avoid modification during iteration
                ticker = position['ticker']
                entry_price = position['entry_price']
                target_price = position['target_price']
                stop_loss_price = position['stop_loss_price']
                
                should_exit, exit_reason = strategy.should_exit_position(
                    current_price, entry_price, target_price, stop_loss_price
                )
                
                if should_exit:
                    # Execute exit
                    exit_result = strategy.execute_exit(ticker, current_price, exit_reason)
                    
                    if 'error' not in exit_result:
                        # Remove from active positions
                        self.active_positions[strategy_name].remove(position)
                        
                        logger.info(f"📉 EXIT EXECUTED - {ticker} for {strategy_name}")
                        logger.info(f"   Exit Reason: {exit_reason}")
                        logger.info(f"   P&L: ${exit_result.get('pnl_dollars', 0):.2f} ({exit_result.get('pnl_percent', 0):.2f}%)")
                        logger.info(f"   Active positions for {strategy_name}: {len(self.active_positions[strategy_name])}")
                    
                    exits.append(exit_result)
        
        return exits
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get status of all strategies"""
        status = {
            'manager_name': self.name,
            'description': self.description,
            'min_gap_threshold': self.config['min_gap_percentage'],
            'max_concurrent_positions': self.config['max_concurrent_positions'],
            'strategies': {}
        }
        
        for strategy_name, strategy in self.strategies.items():
            status['strategies'][strategy_name] = {
                'name': strategy.name,
                'description': strategy.description,
                'config': strategy.config,
                'active_positions_count': len(self.active_positions[strategy_name]),
                'active_positions': self.active_positions[strategy_name],
                'strategy_status': strategy.get_strategy_status()
            }
        
        return status
    
    def get_total_active_positions(self) -> int:
        """Get total number of active positions across all strategies"""
        total = 0
        for positions in self.active_positions.values():
            total += len(positions)
        return total
    
    def can_add_position(self, strategy_name: str) -> bool:
        """Check if we can add a position for a specific strategy"""
        return len(self.active_positions[strategy_name]) < self.config['max_concurrent_positions']
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available strategies"""
        return list(self.strategies.keys())

def main():
    """Test the multi-strategy manager"""
    manager = MultiStrategyManager()
    
    # Test data
    test_data = {
        'current_price': 15.50,
        'day_high': 18.00,
        'day_low': 14.00,
        'gap_percent': 45.0,
        'current_volume': 8000000,
        'avg_volume': 1000000,
        'current_time': time(10, 30),
        'premarket_high': 16.50,
        'market_status': 'open',
        'vwap': 15.25
    }
    
    # Test evaluation
    result = manager.evaluate_stock_for_all_strategies('TEST', test_data)
    print("Multi-Strategy Evaluation:", result)
    
    # Test status
    status = manager.get_strategy_status()
    print("Strategy Status:", status)

if __name__ == "__main__":
    main() 