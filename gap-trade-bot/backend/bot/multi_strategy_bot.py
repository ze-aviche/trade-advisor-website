#!/usr/bin/env python3
"""
Multi-Strategy Trading Bot
Trading bot that implements both break_out and gap_up_short strategies
"""

import sys
import os
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from strategies.multi_strategy_manager import MultiStrategyManager
from data_manager import DataManager
from polygon import RESTClient

logger = get_logger(__name__)

class MultiStrategyTradingBot:
    """Trading bot that implements multiple strategies"""
    
    def __init__(self):
        self.name = "multi_strategy_bot"
        self.description = "Trading bot with break_out and gap_up_short strategies"
        
        # Initialize components
        self.strategy_manager = MultiStrategyManager()
        self.data_manager = DataManager()
        self.polygon_client = self._get_polygon_client()
        
        # Bot configuration
        self.config = {
            'min_gap_percentage': 25,  # Minimum gap to consider
            'check_interval': 30,  # Check for new opportunities every 30 seconds
            'max_positions_per_strategy': 5,
            'enable_live_trading': False,  # Set to True for live trading
            'enable_notifications': True
        }
        
        # Bot state
        self.is_running = False
        self.subscribed_tickers = set()
        self.gap_up_stocks = []
        self.last_check_time = None
        
        # Performance tracking
        self.stats = {
            'total_evaluations': 0,
            'total_entries': 0,
            'total_exits': 0,
            'total_pnl': 0.0,
            'winning_trades': 0,
            'losing_trades': 0
        }
    
    def _get_polygon_client(self):
        """Get Polygon API client"""
        api_key = os.environ.get('POLYGON_API_KEY')
        if not api_key:
            api_key = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
            logger.warning("Using default Polygon API key")
        
        if not api_key:
            raise ValueError("POLYGON_API_KEY environment variable is required")
        
        return RESTClient(api_key)
    
    async def start(self):
        """Start the multi-strategy trading bot"""
        try:
            logger.info("🚀 Starting Multi-Strategy Trading Bot...")
            self.is_running = True
            
            # Initialize data manager
            await self.data_manager.initialize()
            
            # Start main loop
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            self.is_running = False
    
    async def stop(self):
        """Stop the trading bot"""
        logger.info("🛑 Stopping Multi-Strategy Trading Bot...")
        self.is_running = False
    
    async def _main_loop(self):
        """Main trading loop"""
        logger.info("🔄 Starting main trading loop...")
        
        while self.is_running:
            try:
                current_time = datetime.now()
                
                # Check if market is open
                if not self._is_market_open():
                    logger.info("📅 Market is closed, waiting...")
                    await asyncio.sleep(60)  # Wait 1 minute
                    continue
                
                # Find gap up stocks
                await self._find_gap_up_stocks()
                
                # Evaluate existing positions for exits
                await self._check_exits()
                
                # Evaluate new opportunities
                await self._evaluate_opportunities()
                
                # Update stats
                self._update_stats()
                
                # Wait before next check
                await asyncio.sleep(self.config['check_interval'])
                
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                await asyncio.sleep(10)  # Wait 10 seconds before retrying
    
    async def _find_gap_up_stocks(self):
        """Find stocks with gap ups above minimum threshold"""
        try:
            logger.info("🔍 Finding gap up stocks...")
            
            # Get today's date
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Get grouped daily data for today
            grouped_data = self.polygon_client.get_grouped_daily_aggs(
                today,
                adjusted="true"
            )
            
            gap_up_stocks = []
            
            for result in grouped_data:
                if hasattr(result, 'ticker'):
                    ticker = result.ticker
                    
                    # Get gap percentage
                    try:
                        # Get previous day's close
                        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                        prev_daily = self.polygon_client.get_daily_open_close_agg(
                            ticker=ticker, date=yesterday
                        )
                        prev_close = prev_daily.close
                        
                        # Get today's open
                        daily_data = self.polygon_client.get_daily_open_close_agg(
                            ticker=ticker, date=today
                        )
                        open_price = daily_data.open
                        
                        # Calculate gap percentage
                        gap_percent = ((open_price - prev_close) / prev_close) * 100
                        
                        # Check if it meets minimum threshold
                        if gap_percent >= self.config['min_gap_percentage']:
                            gap_up_stocks.append({
                                'ticker': ticker,
                                'gap_percent': gap_percent,
                                'open_price': open_price,
                                'prev_close': prev_close
                            })
                            
                            logger.info(f"📈 Found gap up: {ticker} - {gap_percent:.2f}%")
                        
                    except Exception as e:
                        logger.debug(f"⚠️ Could not get gap data for {ticker}: {e}")
                        continue
            
            self.gap_up_stocks = gap_up_stocks
            logger.info(f"📊 Found {len(gap_up_stocks)} stocks with gap >= {self.config['min_gap_percentage']}%")
            
        except Exception as e:
            logger.error(f"❌ Error finding gap up stocks: {e}")
    
    async def _evaluate_opportunities(self):
        """Evaluate gap up stocks for trading opportunities"""
        try:
            logger.info("📊 Evaluating trading opportunities...")
            
            for stock in self.gap_up_stocks:
                ticker = stock['ticker']
                
                # Get current market data
                current_data = await self._get_current_market_data(ticker)
                
                if not current_data:
                    continue
                
                # Evaluate against all strategies
                evaluation = self.strategy_manager.evaluate_stock_for_all_strategies(ticker, current_data)
                
                if evaluation.get('meets_minimum_threshold', False):
                    best_strategy = evaluation.get('best_strategy')
                    
                    if best_strategy:
                        logger.info(f"🎯 {ticker} qualifies for {best_strategy} strategy")
                        
                        # Execute entry if live trading is enabled
                        if self.config['enable_live_trading']:
                            entry_result = self.strategy_manager.execute_strategy_entry(
                                ticker, best_strategy, current_data
                            )
                            
                            if 'error' not in entry_result:
                                self.stats['total_entries'] += 1
                                logger.info(f"✅ Entry executed for {ticker} using {best_strategy}")
                            else:
                                logger.error(f"❌ Entry failed for {ticker}: {entry_result['error']}")
                        else:
                            logger.info(f"📝 Paper trade: Would enter {ticker} using {best_strategy}")
                
                self.stats['total_evaluations'] += 1
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"❌ Error evaluating opportunities: {e}")
    
    async def _check_exits(self):
        """Check if any positions should be exited"""
        try:
            logger.info("🔍 Checking for exits...")
            
            # Get current data for all active positions
            all_positions = []
            for strategy_name, positions in self.strategy_manager.active_positions.items():
                for position in positions:
                    all_positions.append({
                        'ticker': position['ticker'],
                        'strategy': strategy_name,
                        'entry_price': position['entry_price']
                    })
            
            # Check exits for each position
            for position in all_positions:
                ticker = position['ticker']
                current_data = await self._get_current_market_data(ticker)
                
                if current_data:
                    exits = self.strategy_manager.check_exits_for_all_positions(current_data)
                    
                    for exit_result in exits:
                        if 'error' not in exit_result:
                            self.stats['total_exits'] += 1
                            pnl = exit_result.get('pnl_dollars', 0)
                            self.stats['total_pnl'] += pnl
                            
                            if pnl > 0:
                                self.stats['winning_trades'] += 1
                            else:
                                self.stats['losing_trades'] += 1
                            
                            logger.info(f"📉 Exit executed for {ticker}: ${pnl:.2f}")
                
                await asyncio.sleep(0.1)  # Small delay
            
        except Exception as e:
            logger.error(f"❌ Error checking exits: {e}")
    
    async def _get_current_market_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get current market data for a ticker"""
        try:
            # Get real-time data
            current_data = self.data_manager.get_real_time_data(ticker)
            
            if not current_data:
                return None
            
            # Add additional data needed for strategies
            current_data['current_time'] = datetime.now().time()
            current_data['market_status'] = 'open'  # Simplified for now
            
            return current_data
            
        except Exception as e:
            logger.error(f"❌ Error getting market data for {ticker}: {e}")
            return None
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now()
        
        # Simplified market hours check (9:30 AM - 4:00 PM ET, weekdays)
        if now.weekday() >= 5:  # Weekend
            return False
        
        current_time = now.time()
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        return market_open <= current_time <= market_close
    
    def _update_stats(self):
        """Update and log statistics"""
        if self.stats['total_exits'] > 0:
            win_rate = (self.stats['winning_trades'] / self.stats['total_exits']) * 100
            avg_pnl = self.stats['total_pnl'] / self.stats['total_exits']
            
            logger.info(f"📊 Stats - Evaluations: {self.stats['total_evaluations']}, "
                       f"Entries: {self.stats['total_entries']}, "
                       f"Exits: {self.stats['total_exits']}, "
                       f"Win Rate: {win_rate:.1f}%, "
                       f"Avg P&L: ${avg_pnl:.2f}")
    
    def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return {
            'name': self.name,
            'description': self.description,
            'is_running': self.is_running,
            'config': self.config,
            'stats': self.stats,
            'gap_up_stocks_count': len(self.gap_up_stocks),
            'total_active_positions': self.strategy_manager.get_total_active_positions(),
            'strategy_status': self.strategy_manager.get_strategy_status()
        }

def main():
    """Test the multi-strategy bot"""
    bot = MultiStrategyTradingBot()
    
    # Test bot status
    status = bot.get_bot_status()
    logger.info(f"Bot Status: {status}")
    
    # Test strategy manager
    manager_status = bot.strategy_manager.get_strategy_status()
    logger.info(f"Strategy Manager Status: {manager_status}")

if __name__ == "__main__":
    main() 