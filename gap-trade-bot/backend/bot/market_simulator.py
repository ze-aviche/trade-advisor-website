#!/usr/bin/env python3
"""
Market Simulator
Simulates realistic market conditions for testing bot behavior
"""

import os
import sys
import time
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger

logger = get_logger(__name__)

class MarketCondition(Enum):
    """Market condition enumeration"""
    NORMAL = "normal"
    VOLATILE = "volatile"
    SLOW = "slow"
    FAST = "fast"
    GAPPING = "gapping"

class OrderRejectionReason(Enum):
    """Order rejection reason enumeration"""
    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_ORDER = "invalid_order"
    MARKET_CLOSED = "market_closed"
    SYMBOL_NOT_FOUND = "symbol_not_found"
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    QUANTITY_TOO_LARGE = "quantity_too_large"
    QUANTITY_TOO_SMALL = "quantity_too_small"
    NETWORK_ERROR = "network_error"
    BROKER_ERROR = "broker_error"

class MarketSimulator:
    """Market simulator for realistic testing"""
    
    def __init__(self, mode: str = "realistic"):
        self.mode = mode
        self.current_condition = MarketCondition.NORMAL
        self.simulation_running = False
        
        # Market conditions
        self.conditions = {
            MarketCondition.NORMAL: {
                'fill_probability': 0.95,
                'slippage_range': (0.0, 0.01),
                'execution_delay': (0.5, 2.0),
                'rejection_probability': 0.02,
                'partial_fill_probability': 0.1
            },
            MarketCondition.VOLATILE: {
                'fill_probability': 0.85,
                'slippage_range': (0.01, 0.05),
                'execution_delay': (1.0, 5.0),
                'rejection_probability': 0.08,
                'partial_fill_probability': 0.25
            },
            MarketCondition.SLOW: {
                'fill_probability': 0.98,
                'slippage_range': (0.0, 0.005),
                'execution_delay': (2.0, 8.0),
                'rejection_probability': 0.01,
                'partial_fill_probability': 0.05
            },
            MarketCondition.FAST: {
                'fill_probability': 0.90,
                'slippage_range': (0.0, 0.02),
                'execution_delay': (0.1, 1.0),
                'rejection_probability': 0.05,
                'partial_fill_probability': 0.15
            },
            MarketCondition.GAPPING: {
                'fill_probability': 0.70,
                'slippage_range': (0.02, 0.10),
                'execution_delay': (0.5, 3.0),
                'rejection_probability': 0.15,
                'partial_fill_probability': 0.40
            }
        }
        
        # Simulation state
        self.order_history = []
        self.execution_history = []
        self.rejection_history = []
        
        # Account simulation
        self.account_balance = 100000.0
        self.buying_power = 100000.0
        self.positions = {}
        
        logger.info(f"🎭 Market simulator initialized in {mode} mode")
    
    def set_market_condition(self, condition: MarketCondition):
        """Set current market condition"""
        self.current_condition = condition
        logger.info(f"📊 Market condition changed to: {condition.value}")
    
    def simulate_order_execution(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate realistic order execution"""
        try:
            condition = self.conditions[self.current_condition]
            
            # Check for rejection
            if random.random() < condition['rejection_probability']:
                return self._simulate_order_rejection(order)
            
            # Simulate execution delay
            delay = random.uniform(*condition['execution_delay'])
            time.sleep(delay)
            
            # Check for fill
            if random.random() < condition['fill_probability']:
                return self._simulate_order_fill(order, condition)
            else:
                return self._simulate_order_pending(order)
                
        except Exception as e:
            logger.error(f"Error simulating order execution: {e}")
            return self._simulate_order_rejection(order, OrderRejectionReason.BROKER_ERROR)
    
    def _simulate_order_rejection(self, order: Dict[str, Any], reason: OrderRejectionReason = None) -> Dict[str, Any]:
        """Simulate order rejection"""
        if reason is None:
            reasons = list(OrderRejectionReason)
            reason = random.choice(reasons)
        
        rejection = {
            'order_id': order.get('cl_ord_id', 'UNKNOWN'),
            'symbol': order.get('symbol', 'UNKNOWN'),
            'status': 'rejected',
            'rejection_reason': reason.value,
            'rejection_time': datetime.now().isoformat(),
            'original_order': order
        }
        
        self.rejection_history.append(rejection)
        logger.warning(f"❌ Order rejected: {reason.value}")
        
        return rejection
    
    def _simulate_order_fill(self, order: Dict[str, Any], condition: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate order fill"""
        try:
            symbol = order.get('symbol', 'UNKNOWN')
            quantity = order.get('quantity', 0)
            side = order.get('side', 'BUY')
            order_type = order.get('type', 'market')
            
            # Calculate fill price with slippage
            base_price = self._get_current_price(symbol)
            slippage = random.uniform(*condition['slippage_range'])
            
            if side.upper() == 'BUY':
                fill_price = base_price * (1 + slippage)
            else:
                fill_price = base_price * (1 - slippage)
            
            # Check for partial fill
            if random.random() < condition['partial_fill_probability']:
                fill_quantity = random.randint(1, quantity - 1)
                leaves_quantity = quantity - fill_quantity
                avg_price = fill_price
                
                execution = {
                    'exec_id': f"EXEC_{int(time.time() * 1000)}",
                    'cl_ord_id': order.get('cl_ord_id', 'UNKNOWN'),
                    'symbol': symbol,
                    'side': side,
                    'quantity': fill_quantity,
                    'price': fill_price,
                    'exec_type': '1',  # Partial fill
                    'exec_status': '1',  # Partially filled
                    'cum_qty': fill_quantity,
                    'leaves_qty': leaves_quantity,
                    'avg_px': avg_price,
                    'timestamp': datetime.now().isoformat(),
                    'simulated': True
                }
                
                logger.info(f"💰 Partial fill: {symbol} {fill_quantity} @ ${fill_price:.2f}")
                
            else:
                # Full fill
                execution = {
                    'exec_id': f"EXEC_{int(time.time() * 1000)}",
                    'cl_ord_id': order.get('cl_ord_id', 'UNKNOWN'),
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': fill_price,
                    'exec_type': '2',  # Fill
                    'exec_status': '2',  # Filled
                    'cum_qty': quantity,
                    'leaves_qty': 0,
                    'avg_px': fill_price,
                    'timestamp': datetime.now().isoformat(),
                    'simulated': True
                }
                
                logger.info(f"💰 Full fill: {symbol} {quantity} @ ${fill_price:.2f}")
            
            # Update account
            self._update_account(execution)
            
            # Store execution
            self.execution_history.append(execution)
            
            return execution
            
        except Exception as e:
            logger.error(f"Error simulating order fill: {e}")
            return self._simulate_order_rejection(order, OrderRejectionReason.BROKER_ERROR)
    
    def _simulate_order_pending(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate pending order"""
        pending = {
            'order_id': order.get('cl_ord_id', 'UNKNOWN'),
            'symbol': order.get('symbol', 'UNKNOWN'),
            'status': 'pending',
            'pending_time': datetime.now().isoformat(),
            'original_order': order
        }
        
        logger.info(f"⏳ Order pending: {order.get('symbol', 'UNKNOWN')}")
        
        return pending
    
    def _get_current_price(self, symbol: str) -> float:
        """Get current price for symbol (simulated)"""
        # Simulate realistic prices
        base_prices = {
            'AAPL': 150.0,
            'TSLA': 200.0,
            'MSFT': 300.0,
            'GOOGL': 2500.0,
            'AMZN': 3000.0,
            'NFLX': 400.0,
            'META': 300.0,
            'NVDA': 500.0,
            'AMD': 100.0,
            'INTC': 50.0
        }
        
        base_price = base_prices.get(symbol, 100.0)
        
        # Add some price movement
        movement = random.uniform(-0.02, 0.02)  # ±2% movement
        current_price = base_price * (1 + movement)
        
        return round(current_price, 2)
    
    def _update_account(self, execution: Dict[str, Any]):
        """Update account after execution"""
        try:
            symbol = execution.get('symbol')
            quantity = execution.get('quantity', 0)
            price = execution.get('price', 0)
            side = execution.get('side', 'BUY')
            
            execution_value = quantity * price
            
            if side.upper() == 'BUY':
                # Buying - reduce buying power
                self.buying_power -= execution_value
                
                # Update position
                if symbol not in self.positions:
                    self.positions[symbol] = {'quantity': 0, 'avg_price': 0}
                
                current_pos = self.positions[symbol]
                new_quantity = current_pos['quantity'] + quantity
                new_avg_price = ((current_pos['quantity'] * current_pos['avg_price']) + execution_value) / new_quantity
                
                self.positions[symbol] = {
                    'quantity': new_quantity,
                    'avg_price': new_avg_price
                }
                
            else:
                # Selling - increase buying power
                self.buying_power += execution_value
                
                # Update position
                if symbol in self.positions:
                    current_pos = self.positions[symbol]
                    new_quantity = current_pos['quantity'] - quantity
                    
                    if new_quantity <= 0:
                        del self.positions[symbol]
                    else:
                        self.positions[symbol]['quantity'] = new_quantity
            
            logger.debug(f"💰 Account updated: BP=${self.buying_power:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating account: {e}")
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get current account information"""
        return {
            'balance': self.account_balance,
            'buying_power': self.buying_power,
            'positions': self.positions,
            'total_positions': len(self.positions),
            'total_executions': len(self.execution_history),
            'total_rejections': len(self.rejection_history)
        }
    
    def get_simulation_stats(self) -> Dict[str, Any]:
        """Get simulation statistics"""
        total_orders = len(self.order_history)
        total_executions = len(self.execution_history)
        total_rejections = len(self.rejection_history)
        
        if total_orders > 0:
            fill_rate = total_executions / total_orders
            rejection_rate = total_rejections / total_orders
        else:
            fill_rate = 0
            rejection_rate = 0
        
        return {
            'total_orders': total_orders,
            'total_executions': total_executions,
            'total_rejections': total_rejections,
            'fill_rate': fill_rate,
            'rejection_rate': rejection_rate,
            'current_condition': self.current_condition.value,
            'simulation_mode': self.mode
        }
    
    def reset_simulation(self):
        """Reset simulation state"""
        self.order_history = []
        self.execution_history = []
        self.rejection_history = []
        self.account_balance = 100000.0
        self.buying_power = 100000.0
        self.positions = {}
        
        logger.info("🔄 Simulation reset")

# Global market simulator instance
market_simulator = MarketSimulator()
