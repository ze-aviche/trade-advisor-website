"""
Main Trading Bot Orchestrator
Coordinates all trading bot components and manages the trading process
"""

import asyncio
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from config import config
from data_manager import data_manager
from websocket_client import websocket_client
from position_manager import position_manager
from risk_manager import risk_manager
from order_manager import order_manager
from strategies import BreakOutStrategy

logger = get_logger(__name__)

class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.strategies = {
            'break_out': BreakOutStrategy()
        }
        self.active_strategies = ['break_out']
        self.tracked_symbols = set()
        self.last_analysis = {}
        
        # Performance tracking
        self.start_time = None
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Initialize components
        self._init_components()
    
    def _init_components(self):
        """Initialize all trading bot components"""
        try:
            # Validate configuration
            if not config.validate_config():
                logger.error("❌ Configuration validation failed")
                return False
            
            logger.info("✅ Trading bot components initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing components: {e}")
            return False
    
    async def start(self):
        """Start the trading bot"""
        try:
            if self.is_running:
                logger.warning("⚠️ Trading bot is already running")
                return
            
            logger.info("🚀 Starting trading bot...")
            self.is_running = True
            self.start_time = datetime.now()
            
            # Connect to WebSocket
            await websocket_client.connect()
            
            # Get gap-up stocks
            gap_up_stocks = data_manager.get_gap_up_stocks()
            logger.info(f"📊 Found {len(gap_up_stocks)} gap-up stocks")
            
            # Subscribe to real-time data
            if gap_up_stocks:
                await websocket_client.subscribe_to_symbols(gap_up_stocks)
                self.tracked_symbols.update(gap_up_stocks)
            
            # Add data callback
            websocket_client.add_data_callback(self._on_market_data)
            
            # Start main trading loop
            await self._trading_loop()
            
        except Exception as e:
            logger.error(f"❌ Error starting trading bot: {e}")
            self.is_running = False
    
    async def stop(self):
        """Stop the trading bot"""
        try:
            logger.info("🛑 Stopping trading bot...")
            self.is_running = False
            
            # Disconnect WebSocket
            await websocket_client.disconnect()
            
            # Close all positions (optional)
            # await self._close_all_positions()
            
            logger.info("✅ Trading bot stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping trading bot: {e}")
    
    async def pause(self):
        """Pause the trading bot"""
        self.is_paused = True
        logger.info("⏸️ Trading bot paused")
    
    async def resume(self):
        """Resume the trading bot"""
        self.is_paused = False
        logger.info("▶️ Trading bot resumed")
    
    async def _trading_loop(self):
        """Main trading loop"""
        try:
            while self.is_running:
                try:
                    if self.is_paused:
                        await asyncio.sleep(1)
                        continue
                    
                    # Check if we should stop trading due to risk
                    if risk_manager.should_stop_trading():
                        logger.warning("⚠️ Stopping trading due to risk limits")
                        break
                    
                    # Update real-time data for tracked symbols
                    await self._update_market_data()
                    
                    # Analyze trading opportunities
                    await self._analyze_trading_opportunities()
                    
                    # Check existing positions
                    await self._check_positions()
                    
                    # Check pending orders
                    await self._check_pending_orders()
                    
                    # Wait before next iteration
                    await asyncio.sleep(1)  # 1 second delay
                    
                except Exception as e:
                    logger.error(f"❌ Error in trading loop: {e}")
                    await asyncio.sleep(5)  # Wait longer on error
            
        except Exception as e:
            logger.error(f"❌ Error in main trading loop: {e}")
    
    async def _update_market_data(self):
        """Update market data for tracked symbols"""
        try:
            for symbol in self.tracked_symbols:
                # Get real-time data
                real_time_data = data_manager.get_real_time_data(symbol)
                if real_time_data:
                    data_manager.update_real_time_data(symbol)
                    
        except Exception as e:
            logger.error(f"❌ Error updating market data: {e}")
    
    async def _analyze_trading_opportunities(self):
        """Analyze current market for trading opportunities"""
        try:
            gap_up_stocks = data_manager.get_gap_up_stocks()
            
            for ticker in gap_up_stocks:
                # Get real-time data
                current_data = data_manager.get_real_time_data(ticker)
                if not current_data:
                    continue
                
                # Analyze with break out strategy
                strategy = BreakOutStrategy()
                analysis = strategy.analyze_entry_conditions(ticker, current_data)
                
                if analysis.get('entry_signal', False):
                    logger.info(f"🎯 Break out signal detected for {ticker}")
                    logger.info(f"📊 Confidence: {analysis.get('confidence', 0):.1f}%")
                    
                    # Check if we should enter position
                    if strategy.should_enter_position(analysis):
                        await self._execute_strategy_entry(ticker, strategy, current_data)
                
        except Exception as e:
            logger.error(f"❌ Error analyzing trading opportunities: {e}")
    
    async def _execute_strategy_entry(self, ticker: str, strategy: Any, current_data: Dict[str, Any]):
        """Execute strategy entry"""
        try:
            current_price = current_data.get('current_price', 0)
            day_high = current_data.get('day_high', 0)
            
            # Calculate position size
            stop_loss_price = risk_manager.calculate_stop_loss_price(current_price)
            position_size = risk_manager.calculate_position_size(
                current_price, stop_loss_price, 100000  # $100k available capital
            )
            
            # Validate trade risk
            risk_valid, risk_message = risk_manager.validate_trade_risk(
                ticker, current_price, position_size, stop_loss_price
            )
            
            if not risk_valid:
                logger.warning(f"⚠️ Risk validation failed for {ticker}: {risk_message}")
                return
            
            # Execute entry order
            entry_order = strategy.execute_entry(ticker, current_price, day_high)
            if 'error' in entry_order:
                logger.error(f"❌ Entry execution failed for {ticker}: {entry_order['error']}")
                return
            
            # Place buy order
            order = order_manager.place_buy_order(ticker, position_size, current_price)
            if 'error' in order:
                logger.error(f"❌ Order placement failed for {ticker}: {order['error']}")
                return
            
            # Open position
            if position_manager.open_position(ticker, position_size, 'buy', current_price):
                logger.info(f"📈 Position opened: {ticker} @ ${current_price:.2f}")
                
                # Place stop-loss order
                stop_order = order_manager.place_stop_order(ticker, position_size, stop_loss_price)
                
                # Place target order (optional)
                target_price = strategy.calculate_target_price(current_price)
                target_order = order_manager.place_limit_order(ticker, position_size, target_price, 'sell')
                
                self.total_trades += 1
            else:
                logger.warning(f"⚠️ Failed to open position for {ticker}")
            
        except Exception as e:
            logger.error(f"❌ Error executing strategy entry: {e}")
    
    async def _check_positions(self):
        """Check existing positions for exit conditions"""
        try:
            positions = position_manager.get_all_positions()
            if not positions:
                return
                
            current_prices = {}
            
            # Get current prices for all positions
            for position in positions:
                ticker = position['ticker']
                price = websocket_client.get_current_price(ticker)
                if price:
                    current_prices[ticker] = price
            
            # Check each position
            for position in positions:
                ticker = position['ticker']
                current_price = current_prices.get(ticker)
                if not current_price:
                    continue
                
                # Update position with current price
                exit_signal = position_manager.update_position_prices({ticker: current_price})
                
                if exit_signal and exit_signal.get('exit_signal'):
                    await self._execute_position_exit(ticker, current_price, exit_signal.get('exit_reason'))
            
        except Exception as e:
            logger.error(f"❌ Error checking positions: {e}")
    
    async def _execute_position_exit(self, ticker: str, current_price: float, exit_reason: str):
        """Execute position exit"""
        try:
            position = position_manager.get_position(ticker)
            if not position:
                return
            
            # Place sell order
            order = order_manager.place_sell_order(ticker, position['quantity'], current_price)
            if 'error' in order:
                logger.error(f"❌ Exit order failed for {ticker}: {order['error']}")
                return
            
            # Close position
            exit_order = {
                'exit_price': current_price,
                'exit_time': datetime.now().isoformat(),
                'exit_reason': exit_reason,
                'holding_time': str(datetime.now() - datetime.fromisoformat(position['entry_time']))
            }
            
            if position_manager.close_position(ticker, exit_order):
                # Update trade statistics
                pnl = exit_order.get('pnl', 0)
                if pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                # Update risk manager
                risk_manager.update_daily_loss(abs(pnl) if pnl < 0 else 0)
                
                logger.info(f"📉 Position closed: {ticker} | P&L: ${pnl:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Error executing position exit: {e}")
    
    async def _check_pending_orders(self):
        """Check pending orders for execution"""
        try:
            # Get current prices
            current_prices = {}
            for ticker in self.tracked_symbols:
                price = websocket_client.get_current_price(ticker)
                if price:
                    current_prices[ticker] = price
            
            # Check stop orders
            triggered_stops = order_manager.check_stop_orders(current_prices)
            
            # Check limit orders
            triggered_limits = order_manager.check_limit_orders(current_prices)
            
            # Process triggered orders
            all_triggered = (triggered_stops or []) + (triggered_limits or [])
            for order_id in all_triggered:
                order = order_manager.get_order_status(order_id)
                if order and order['status'] == 'executed':
                    await self._process_executed_order(order)
            
        except Exception as e:
            logger.error(f"❌ Error checking pending orders: {e}")
    
    async def _process_executed_order(self, order: Dict[str, Any]):
        """Process an executed order"""
        try:
            ticker = order['ticker']
            action = order['action']
            executed_price = order['executed_price']
            
            if action == 'sell':
                # Check if we have a position to close
                position = position_manager.get_position(ticker)
                if position:
                    exit_order = {
                        'exit_price': executed_price,
                        'exit_time': order['executed_at'],
                        'exit_reason': 'order_executed',
                        'holding_time': 'N/A'
                    }
                    
                    position_manager.close_position(ticker, exit_order)
            
        except Exception as e:
            logger.error(f"❌ Error processing executed order: {e}")
    
    def _on_market_data(self, data: Dict[str, Any]):
        """Callback for real-time market data"""
        try:
            symbol = data.get('symbol', '')
            data_type = data.get('type', '')
            
            if data_type == 'trade':
                # Process trade data
                price = data.get('price', 0)
                volume = data.get('volume', 0)
                
                # Update data manager
                if symbol in self.tracked_symbols:
                    data_manager.update_real_time_data(symbol)
            
        except Exception as e:
            logger.error(f"❌ Error processing market data: {e}")
    
    def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        try:
            uptime = None
            if self.start_time:
                uptime = str(datetime.now() - self.start_time)
            
            return {
                'is_running': self.is_running,
                'is_paused': self.is_paused,
                'uptime': uptime,
                'tracked_symbols': len(self.tracked_symbols),
                'active_strategies': self.active_strategies,
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': round((self.winning_trades / self.total_trades) * 100, 2) if self.total_trades > 0 else 0,
                'position_summary': position_manager.get_position_summary(),
                'risk_summary': risk_manager.get_risk_summary(),
                'order_summary': order_manager.get_order_summary()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting bot status: {e}")
            return {}

# Global trading bot instance
trading_bot = TradingBot()
