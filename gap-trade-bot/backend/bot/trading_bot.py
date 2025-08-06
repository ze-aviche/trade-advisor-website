"""
Main Trading Bot Orchestrator
Coordinates all trading bot components and manages the trading process
"""

import asyncio
import time
import sys
import os
import json
import pickle
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import threading

# Add parent directory to path for backend imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from bot.config import config as bot_config
from bot.data_manager import data_manager
from bot.websocket_client import websocket_client
from bot.position_manager import position_manager
from bot.risk_manager import risk_manager
from bot.order_manager import order_manager
from bot.strategies import BreakOutStrategy
from bot.strategies import GapUpShortStrategy

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
        
        # Market status tracking
        self.last_market_status = None
        self.market_status_check_interval = 60  # Check every 60 seconds
        self.last_market_close_check = None
        self.market_close_time = "20:00"  # 8 PM ET (after-hours included)
        self.subscribed_today = set()  # Track stocks subscribed today
        
        # Subscription persistence
        self.persistence_file = os.path.join(os.path.dirname(__file__), 'subscription_state.pkl')
        
        # Initialize components
        self._init_components()
        
        # Load persisted subscription state
        self._load_subscription_state()
    
    def _init_components(self):
        """Initialize all trading bot components"""
        try:
            # Validate configuration
            if not bot_config.validate_config():
                logger.error("❌ Configuration validation failed")
                return False
            
            logger.info("✅ Trading bot components initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing components: {e}")
            return False
    
    def _save_subscription_state(self):
        """Save current subscription state to file"""
        try:
            subscription_state = {
                'tracked_symbols': list(self.tracked_symbols),
                'subscribed_today': list(self.subscribed_today),
                'last_market_close_check': self.last_market_close_check.isoformat() if self.last_market_close_check else None,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(self.persistence_file, 'wb') as f:
                pickle.dump(subscription_state, f)
            
            logger.info(f"💾 Saved subscription state: {len(self.tracked_symbols)} tracked symbols")
            
        except Exception as e:
            logger.error(f"❌ Error saving subscription state: {e}")
    
    def _load_subscription_state(self):
        """Load subscription state from file"""
        try:
            if not os.path.exists(self.persistence_file):
                logger.info("📁 No previous subscription state found - starting fresh")
                return
            
            with open(self.persistence_file, 'rb') as f:
                subscription_state = pickle.load(f)
            
            # Check if the saved state is from today
            saved_at = datetime.fromisoformat(subscription_state.get('saved_at', '2000-01-01T00:00:00'))
            today = datetime.now().date()
            
            if saved_at.date() == today:
                # Load today's state
                self.tracked_symbols = set(subscription_state.get('tracked_symbols', []))
                self.subscribed_today = set(subscription_state.get('subscribed_today', []))
                
                # Load last market close check
                last_check_str = subscription_state.get('last_market_close_check')
                if last_check_str:
                    self.last_market_close_check = datetime.fromisoformat(last_check_str).date()
                else:
                    self.last_market_close_check = None
                
                logger.info(f"📁 Loaded subscription state: {len(self.tracked_symbols)} tracked symbols")
                logger.info(f"📊 Tracked symbols: {', '.join(sorted(self.tracked_symbols))}")
            else:
                logger.info("📁 Previous subscription state is from a different day - starting fresh")
                # Clear old state for new day
                self.tracked_symbols.clear()
                self.subscribed_today.clear()
                self.last_market_close_check = None
                
        except Exception as e:
            logger.error(f"❌ Error loading subscription state: {e}")
            # Start fresh if loading fails
            self.tracked_symbols.clear()
            self.subscribed_today.clear()
            self.last_market_close_check = None
    
    def clear_subscription_state(self):
        """Clear persisted subscription state (for testing or manual reset)"""
        try:
            if os.path.exists(self.persistence_file):
                os.remove(self.persistence_file)
                logger.info("🗑️ Cleared persisted subscription state")
            
            self.tracked_symbols.clear()
            self.subscribed_today.clear()
            self.last_market_close_check = None
            
        except Exception as e:
            logger.error(f"❌ Error clearing subscription state: {e}")
    
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
            
            # Initialize market status tracking
            self.last_market_status = data_manager.get_market_status()
            if self.last_market_close_check is None:
                self.last_market_close_check = datetime.now().date()
            logger.info(f"📊 Initial market status: {self.last_market_status}")
            
            # Check if we have persisted subscriptions to restore
            if self.tracked_symbols:
                logger.info(f"📁 Restoring {len(self.tracked_symbols)} persisted subscriptions")
                logger.info(f"📊 Persisted symbols: {', '.join(sorted(self.tracked_symbols))}")
                
                # Re-subscribe to persisted symbols if market is active
                if self.last_market_status in ['open', 'pre_market', 'after_hours']:
                    await websocket_client.subscribe_to_symbols(list(self.tracked_symbols))
                    logger.info(f"📡 Re-subscribed to {len(self.tracked_symbols)} persisted symbols")
                    # Save the restored state
                    self._save_subscription_state()
                else:
                    logger.info("🛑 Market is closed - keeping persisted subscriptions but not re-subscribing")
            else:
                # No persisted subscriptions - get new gap-up stocks
                gap_up_stocks = data_manager.get_gap_up_stocks()
                logger.info(f"📊 Found {len(gap_up_stocks)} gap-up stocks")
                
                # Subscribe to real-time data only if market is open, pre-market, or after-hours
                if (self.last_market_status in ['open', 'pre_market', 'after_hours']) and gap_up_stocks:
                    await websocket_client.subscribe_to_symbols(gap_up_stocks)
                    self.tracked_symbols.update(gap_up_stocks)
                    self.subscribed_today.update(gap_up_stocks)  # Track today's subscriptions
                    logger.info(f"📡 Subscribed to {len(gap_up_stocks)} new gap-up stocks: {', '.join(gap_up_stocks)}")
                    # Save the new subscription state
                    self._save_subscription_state()
                elif self.last_market_status == 'closed':
                    logger.info("🛑 Market is closed - not subscribing to any stocks")
                else:
                    logger.info("📊 No gap-up stocks found to subscribe")
            
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
            loop_count = 0
            while self.is_running:
                try:
                    if self.is_paused:
                        await asyncio.sleep(1)
                        continue
                    
                    loop_count += 1
                    
                    # Check if we should stop trading due to risk
                    if risk_manager.should_stop_trading():
                        logger.warning("⚠️ Stopping trading due to risk limits")
                        break
                    
                    # Log trading loop status every 10 iterations
                    if loop_count % 10 == 0:
                        await self._log_trading_status()
                        await self._log_subscription_status()
                    
                    # Check market status only at 8 PM ET (after-hours included)
                    current_time = datetime.now()
                    et_time = current_time.replace(tzinfo=timezone(timedelta(hours=-5)))
                    current_time_str = et_time.strftime("%H:%M")
                    
                    if current_time_str == self.market_close_time:
                        await self._check_market_status()
                    
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
            # Check if market is open before updating data
            current_market_status = data_manager.get_market_status()
            if current_market_status not in ['open', 'pre_market', 'after_hours']:
                logger.debug(f"📊 Market is {current_market_status} - skipping market data updates")
                return
            
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
            # Check if market is open before analyzing
            current_market_status = data_manager.get_market_status()
            if current_market_status not in ['open', 'pre_market', 'after_hours']:
                logger.debug(f"📊 Market is {current_market_status} - skipping trading analysis")
                return
            
            gap_up_stocks = data_manager.get_gap_up_stocks()
            logger.info(f"🔍 Analyzing {len(gap_up_stocks)} gap-up stocks for BOTH strategies...")
            
            for ticker in gap_up_stocks:
                # Get real-time data
                try:
                    current_data = data_manager.get_real_time_data(ticker)
                    if not current_data:
                        logger.debug(f"⚠️ No real-time data available for {ticker}")
                        continue
                except Exception as e:
                    logger.warning(f"⚠️ Error processing {ticker}: {e}")
                    continue
                
                logger.info(f"📊 Analyzing {ticker} - Price: ${current_data.get('current_price', 0):.2f}, Volume: {current_data.get('volume', 0):,}")
                
                # Analyze for BOTH strategies simultaneously
                gap_percent = current_data.get('gap_percent', 0)
                current_time = current_data.get('current_time', datetime.now().time())
                
                # Strategy 1: Break Out Strategy (always available)
                break_out_strategy = BreakOutStrategy()
                break_out_analysis = break_out_strategy.analyze_entry_conditions(ticker, current_data)
                
                # Strategy 2: Gap Up Short Strategy (available after 10 AM for high gaps)
                gap_up_short_analysis = None
                from datetime import time
                ten_am = time(10, 0)
                
                if current_time >= ten_am and gap_percent >= 40:
                    gap_up_short_strategy = GapUpShortStrategy()
                    gap_up_short_analysis = gap_up_short_strategy.analyze_entry_conditions(ticker, current_data)
                
                # Log analysis results for both strategies
                logger.info(f"🎯 {ticker} Analysis Results:")
                
                # Break Out Analysis
                bo_confidence = break_out_analysis.get('confidence', 0)
                bo_should_enter = break_out_strategy.should_enter_position(break_out_analysis)
                logger.info(f"   📈 Break Out Strategy:")
                logger.info(f"      📊 Entry Signal: {'✅ YES' if bo_should_enter else '❌ NO'}")
                logger.info(f"      📊 Confidence: {bo_confidence:.1f}%")
                
                # Gap Up Short Analysis (if applicable)
                if gap_up_short_analysis:
                    gus_confidence = gap_up_short_analysis.get('confidence', 0)
                    gus_should_enter = gap_up_short_strategy.should_enter_position(gap_up_short_analysis)
                    logger.info(f"   📉 Gap Up Short Strategy:")
                    logger.info(f"      📊 Entry Signal: {'✅ YES' if gus_should_enter else '❌ NO'}")
                    logger.info(f"      📊 Confidence: {gus_confidence:.1f}%")
                else:
                    logger.info(f"   📉 Gap Up Short Strategy: Not applicable (Time: {current_time.strftime('%H:%M')}, Gap: {gap_percent:.2f}%)")
                
                # Execute the BEST strategy (highest confidence with entry signal)
                best_strategy = None
                best_analysis = None
                best_confidence = 0
                
                if bo_should_enter and bo_confidence > best_confidence:
                    best_strategy = break_out_strategy
                    best_analysis = break_out_analysis
                    best_confidence = bo_confidence
                    logger.info(f"🎯 Selected Break Out strategy for {ticker} (Confidence: {bo_confidence:.1f}%)")
                
                if gap_up_short_analysis and gap_up_short_strategy.should_enter_position(gap_up_short_analysis):
                    gus_conf = gap_up_short_analysis.get('confidence', 0)
                    if gus_conf > best_confidence:
                        best_strategy = gap_up_short_strategy
                        best_analysis = gap_up_short_analysis
                        best_confidence = gus_conf
                        logger.info(f"🎯 Selected Gap Up Short strategy for {ticker} (Confidence: {gus_conf:.1f}%)")
                
                # Execute the best strategy if found
                if best_strategy and best_analysis:
                    await self._execute_strategy_entry(ticker, best_strategy, current_data)
                else:
                    logger.info(f"📊 No entry signals for {ticker} from either strategy")
                
        except Exception as e:
            logger.error(f"❌ Error in trading analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _execute_strategy_entry(self, ticker: str, strategy: Any, current_data: Dict[str, Any]):
        """Execute strategy entry"""
        try:
            current_price = current_data.get('current_price', 0)
            day_high = current_data.get('day_high', 0)
            
            logger.info(f"🚀 EXECUTING ENTRY FOR {ticker}")
            logger.info(f"   📊 Entry Price: ${current_price:.2f}")
            logger.info(f"   📈 Day High: ${day_high:.2f}")
            
            # Calculate position size using real account capital
            stop_loss_price = risk_manager.calculate_stop_loss_price(current_price)
            available_capital = risk_manager.get_available_capital()
            position_size = risk_manager.calculate_position_size(
                current_price, stop_loss_price, available_capital, ticker
            )
            
            logger.info(f"   💰 Position Size: {position_size:,} shares")
            logger.info(f"   🛑 Stop Loss: ${stop_loss_price:.2f}")
            
            # Validate trade risk
            risk_valid, risk_message = risk_manager.validate_trade_risk(
                ticker, current_price, position_size, stop_loss_price
            )
            
            if not risk_valid:
                logger.warning(f"⚠️ Risk validation failed for {ticker}: {risk_message}")
                return
            
            logger.info(f"   ✅ Risk validation passed")
            
            # Execute entry order
            entry_order = strategy.execute_entry(ticker, current_price, day_high)
            if 'error' in entry_order:
                logger.error(f"❌ Entry execution failed for {ticker}: {entry_order['error']}")
                return
            
            logger.info(f"   📋 Strategy entry executed")
            
            # Place buy order
            order = order_manager.place_buy_order(ticker, position_size, current_price)
            if 'error' in order:
                logger.error(f"❌ Order placement failed for {ticker}: {order['error']}")
                return
            
            logger.info(f"   📈 Buy order placed: {position_size:,} shares @ ${current_price:.2f}")
            
            # Open position
            if position_manager.open_position(ticker, position_size, 'buy', current_price):
                logger.info(f"📈 Position opened: {ticker} @ ${current_price:.2f}")
                
                # Place stop-loss order
                stop_order = order_manager.place_stop_order(ticker, position_size, stop_loss_price)
                logger.info(f"   🛑 Stop-loss order placed @ ${stop_loss_price:.2f}")
                
                # Place target order (optional)
                target_price = strategy.calculate_target_price(current_price)
                target_order = order_manager.place_limit_order(ticker, position_size, target_price, 'sell')
                logger.info(f"   🎯 Target order placed @ ${target_price:.2f}")
                
                self.total_trades += 1
                logger.info(f"   ✅ Trade #{self.total_trades} executed successfully")
            else:
                logger.warning(f"⚠️ Failed to open position for {ticker}")
            
        except Exception as e:
            logger.error(f"❌ Error executing strategy entry: {e}")
    
    async def _check_positions(self):
        """Check existing positions for exit conditions"""
        try:
            positions = position_manager.get_all_positions()
            if not positions:
                logger.debug("📊 No active positions to check")
                return
            
            logger.info(f"🔍 Checking {len(positions)} active positions for exit conditions...")
            current_prices = {}
            
            # Get current prices for all positions
            for position in positions:
                ticker = position['ticker']
                price = websocket_client.get_current_price(ticker)
                if price:
                    current_prices[ticker] = price
                    logger.info(f"📊 {ticker} - Current Price: ${price:.2f}")
                else:
                    logger.warning(f"⚠️ No current price available for {ticker}")
            
            # Check each position
            for position in positions:
                ticker = position['ticker']
                entry_price = position.get('entry_price', 0)
                quantity = position.get('quantity', 0)
                current_price = current_prices.get(ticker)
                
                if not current_price:
                    logger.warning(f"⚠️ Skipping {ticker} - No current price available")
                    continue
                
                # Calculate current P&L
                pnl = (current_price - entry_price) * quantity
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
                
                logger.info(f"📊 {ticker} Position Status:")
                logger.info(f"   📈 Entry Price: ${entry_price:.2f}")
                logger.info(f"   📊 Current Price: ${current_price:.2f}")
                logger.info(f"   📦 Quantity: {quantity:,}")
                logger.info(f"   💰 P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)")
                
                # Update position with current price
                exit_signal = position_manager.update_position_prices({ticker: current_price})
                
                if exit_signal and exit_signal.get('exit_signal'):
                    exit_reason = exit_signal.get('exit_reason', 'Unknown')
                    logger.info(f"🚨 Exit signal triggered for {ticker}: {exit_reason}")
                    await self._execute_position_exit(ticker, current_price, exit_reason)
                else:
                    logger.debug(f"📊 {ticker} - No exit signal (P&L: ${pnl:.2f})")
            
        except Exception as e:
            logger.error(f"❌ Error checking positions: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error checking positions: {e}")
    
    async def _execute_position_exit(self, ticker: str, current_price: float, exit_reason: str):
        """Execute position exit"""
        try:
            position = position_manager.get_position(ticker)
            if not position:
                logger.warning(f"⚠️ No position found for {ticker} during exit")
                return
            
            entry_price = position.get('entry_price', 0)
            quantity = position.get('quantity', 0)
            entry_time = position.get('entry_time', '')
            
            logger.info(f"🚨 EXECUTING EXIT FOR {ticker}")
            logger.info(f"   📊 Entry Price: ${entry_price:.2f}")
            logger.info(f"   📊 Exit Price: ${current_price:.2f}")
            logger.info(f"   📦 Quantity: {quantity:,} shares")
            logger.info(f"   📅 Exit Reason: {exit_reason}")
            
            # Calculate P&L
            pnl = (current_price - entry_price) * quantity
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            
            logger.info(f"   💰 P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)")
            
            # Place sell order
            order = order_manager.place_sell_order(ticker, quantity, current_price)
            if 'error' in order:
                logger.error(f"❌ Exit order failed for {ticker}: {order['error']}")
                return
            
            logger.info(f"   📉 Sell order placed: {quantity:,} shares @ ${current_price:.2f}")
            
            # Close position
            exit_order = {
                'exit_price': current_price,
                'exit_time': datetime.now().isoformat(),
                'exit_reason': exit_reason,
                'holding_time': str(datetime.now() - datetime.fromisoformat(entry_time)) if entry_time else 'N/A'
            }
            
            if position_manager.close_position(ticker, exit_order):
                # Update trade statistics
                if pnl > 0:
                    self.winning_trades += 1
                    logger.info(f"   ✅ WINNING TRADE")
                else:
                    self.losing_trades += 1
                    logger.info(f"   ❌ LOSING TRADE")
                
                # Update risk manager
                risk_manager.update_daily_loss(abs(pnl) if pnl < 0 else 0)
                
                logger.info(f"📉 Position closed: {ticker} | P&L: ${pnl:.2f} | Win Rate: {self.winning_trades}/{self.total_trades}")
            
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
    
    async def _check_market_status(self):
        """Check market status and manage WebSocket subscriptions"""
        try:
            current_time = datetime.now()
            current_market_status = data_manager.get_market_status()
            
            # Check if it's market close time (4 PM ET)
            et_time = current_time.replace(tzinfo=timezone(timedelta(hours=-5)))
            current_time_str = et_time.strftime("%H:%M")
            
            # Only check for market close at 8 PM ET (includes after-hours)
            if current_time_str == self.market_close_time:
                if self.last_market_close_check != current_time.date():
                    logger.info(f"🕐 After-hours close time reached ({current_time_str} ET) - checking for unsubscription")
                    
                    # Check for open positions before unsubscribing
                    open_positions = position_manager.get_all_positions()
                    positions_with_subscriptions = []
                    
                    for position in open_positions:
                        ticker = position['ticker']
                        if ticker in self.tracked_symbols:
                            positions_with_subscriptions.append(ticker)
                    
                    if positions_with_subscriptions:
                        logger.warning(f"⚠️ Found {len(positions_with_subscriptions)} open positions with active subscriptions:")
                        for ticker in positions_with_subscriptions:
                            position = position_manager.get_position(ticker)
                            entry_price = position.get('entry_price', 0)
                            quantity = position.get('quantity', 0)
                            logger.warning(f"   📊 {ticker}: {quantity:,} shares @ ${entry_price:.2f} - KEEPING SUBSCRIPTION")
                        
                        # Don't unsubscribe from stocks with open positions
                        stocks_to_unsubscribe = [s for s in self.tracked_symbols if s not in positions_with_subscriptions]
                        
                        if stocks_to_unsubscribe:
                            logger.info(f"📡 Unsubscribing from {len(stocks_to_unsubscribe)} stocks without open positions")
                            await websocket_client.unsubscribe_from_symbols(stocks_to_unsubscribe)
                            for stock in stocks_to_unsubscribe:
                                self.tracked_symbols.discard(stock)
                            logger.info(f"✅ Unsubscribed from: {', '.join(stocks_to_unsubscribe)}")
                            # Save the updated subscription state
                            self._save_subscription_state()
                        else:
                            logger.info("📊 All subscribed stocks have open positions - keeping all subscriptions")
                    else:
                        # No open positions - unsubscribe from all
                        if self.tracked_symbols:
                            logger.info(f"📡 No open positions found - unsubscribing from all {len(self.tracked_symbols)} stocks")
                            await websocket_client.unsubscribe_from_symbols(list(self.tracked_symbols))
                            logger.info(f"✅ Unsubscribed from: {', '.join(self.tracked_symbols)}")
                            self.tracked_symbols.clear()
                            # Save the updated subscription state
                            self._save_subscription_state()
                        else:
                            logger.info("📊 No active subscriptions to unsubscribe")
                    
                    self.last_market_close_check = current_time.date()
                    logger.info("✅ After-hours close check completed")
            
            # Check for market open (new day, new gap-up stocks)
            if current_market_status in ['open', 'pre_market', 'after_hours'] and self.last_market_status == 'closed':
                logger.info("🚀 Market just opened - checking for new gap-up stocks")
                
                # Clear today's subscription tracking (new day)
                self.subscribed_today.clear()
                
                # Get new gap-up stocks for today
                gap_up_stocks = data_manager.get_gap_up_stocks()
                logger.info(f"📊 Found {len(gap_up_stocks)} new gap-up stocks for today")
                
                if gap_up_stocks:
                    # Subscribe to new gap-up stocks
                    await websocket_client.subscribe_to_symbols(gap_up_stocks)
                    self.tracked_symbols.update(gap_up_stocks)
                    self.subscribed_today.update(gap_up_stocks)
                    logger.info(f"📡 Subscribed to new gap-up stocks: {', '.join(gap_up_stocks)}")
                    # Save the updated subscription state
                    self._save_subscription_state()
                else:
                    logger.info("📊 No new gap-up stocks found for today")
            
            self.last_market_status = current_market_status
            
        except Exception as e:
            logger.error(f"❌ Error checking market status: {e}")
    
    async def _log_subscription_status(self):
        """Log current subscription status"""
        try:
            open_positions = position_manager.get_all_positions()
            position_tickers = {pos['ticker'] for pos in open_positions}
            
            logger.info("📊 SUBSCRIPTION STATUS:")
            logger.info(f"   📡 Total Subscribed: {len(self.tracked_symbols)}")
            logger.info(f"   📈 Open Positions: {len(open_positions)}")
            logger.info(f"   🔗 Subscribed with Positions: {len(self.tracked_symbols.intersection(position_tickers))}")
            
            if self.tracked_symbols:
                logger.info(f"   📋 Subscribed Stocks: {', '.join(sorted(self.tracked_symbols))}")
            
            if open_positions:
                logger.info(f"   📋 Position Stocks: {', '.join(sorted(position_tickers))}")
            
        except Exception as e:
            logger.error(f"❌ Error logging subscription status: {e}")
    
    async def _log_trading_status(self):
        """Log comprehensive trading status"""
        try:
            positions = position_manager.get_all_positions()
            total_positions = len(positions)
            
            # Calculate total P&L
            total_pnl = 0
            position_details = []
            
            for position in positions:
                ticker = position['ticker']
                entry_price = position.get('entry_price', 0)
                quantity = position.get('quantity', 0)
                current_price = websocket_client.get_current_price(ticker)
                
                if current_price:
                    pnl = (current_price - entry_price) * quantity
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    
                    position_details.append({
                        'ticker': ticker,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'quantity': quantity,
                        'pnl': pnl,
                        'pnl_percent': pnl_percent
                    })
            
            # Log trading status
            logger.info("=" * 60)
            logger.info("📊 TRADING BOT STATUS SUMMARY")
            logger.info("=" * 60)
            logger.info(f"🤖 Bot Status: {'🟢 RUNNING' if self.is_running else '🔴 STOPPED'}")
            logger.info(f"⏸️ Paused: {'Yes' if self.is_paused else 'No'}")
            logger.info(f"📈 Active Positions: {total_positions}")
            logger.info(f"💰 Total P&L: ${total_pnl:.2f}")
            logger.info(f"📊 Total Trades: {self.total_trades}")
            logger.info(f"✅ Winning Trades: {self.winning_trades}")
            logger.info(f"❌ Losing Trades: {self.losing_trades}")
            
            if self.total_trades > 0:
                win_rate = (self.winning_trades / self.total_trades) * 100
                logger.info(f"📈 Win Rate: {win_rate:.1f}%")
            
            # Log position details
            if position_details:
                logger.info("📊 ACTIVE POSITIONS:")
                for pos in position_details:
                    status_emoji = "🟢" if pos['pnl'] > 0 else "🔴"
                    logger.info(f"   {status_emoji} {pos['ticker']}: ${pos['entry_price']:.2f} → ${pos['current_price']:.2f} ({pos['pnl_percent']:+.2f}%) | P&L: ${pos['pnl']:.2f}")
            else:
                logger.info("📊 No active positions")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error logging trading status: {e}")
    
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
