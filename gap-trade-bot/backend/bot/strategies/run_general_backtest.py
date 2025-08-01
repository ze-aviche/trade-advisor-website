#!/usr/bin/env python3
"""
Generalized Backtest Runner
Can run backtests for any strategy using the base framework
"""

import sys
import os
import argparse
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from logging_config import get_logger
from base_backtest import BaseBacktest
from historical_data import get_historical_gap_up_data
from break_out import BreakOutStrategy
from gap_up_db import GapUpDB

logger = get_logger(__name__)

# Strategy implementations directly in this file
class BreakoutBacktest(BaseBacktest):
    """Break-out strategy backtest implementation"""
    
    def __init__(self):
        strategy = BreakOutStrategy()
        super().__init__(strategy, "break_out")
        self.min_gap_percentage = 25.0  # Minimum gap percentage
        self.gap_up_db = GapUpDB()
    
    def get_stocks_for_date(self, date: datetime) -> List[str]:
        """Get gap-up stocks for a specific date from database"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            logger.info(f"🔍 Getting gap-up stocks from database for {date_str}")
            
            # Check if database exists and has data
            if not self.gap_up_db.check_database_exists():
                logger.warning(f"⚠️ Gap-up database not found or empty for {date_str}")
                logger.warning("Run fetch_gap_up_history.py first to populate the database")
                return []
            
            # Get gap-up stocks from database
            gap_up_stocks = self.gap_up_db.get_gap_up_stocks_for_date(date, self.min_gap_percentage)
            
            logger.info(f"📊 Found {len(gap_up_stocks)} gap-up stocks for {date_str}")
            return gap_up_stocks
            
        except Exception as e:
            logger.error(f"❌ Error getting gap-up stocks for {date}: {e}")
            return []
    
    def get_market_data_for_stock(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        """Get additional market data specific to break-out strategy"""
        try:
            # Get gap-up data from database
            gap_data = self.gap_up_db.get_gap_up_data_for_stock(ticker, date)
            if gap_data:
                return {
                    'gap_percent': gap_data.get('gap_percent', 0),
                    'prev_close': gap_data.get('prev_close', 0),
                    'open_price': gap_data.get('open_price', 0)
                }
            
            # Fallback to pre-market data calculation if not in database
            premarket_data = self.get_premarket_data(ticker, date)
            return {
                'gap_percent': premarket_data.get('gap_percent', 0),
                'prev_close': premarket_data.get('prev_close', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting market data for {ticker}: {e}")
            return None
    
    def get_premarket_data(self, ticker: str, date: datetime) -> Dict[str, Any]:
        """Get pre-market data to calculate gap percentage"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            prev_date = date - timedelta(days=1)
            prev_date_str = prev_date.strftime('%Y-%m-%d')
            
            prev_daily = self.polygon_client.get_daily_open_close_agg(
                ticker=ticker, date=prev_date_str
            )
            prev_close = prev_daily.close
            
            # Get pre-market data (4:00 AM to 9:30 AM)
            est_timezone = timezone(timedelta(hours=-5))
            premarket_start = date.replace(hour=4, minute=0, second=0, microsecond=0)
            premarket_start = premarket_start.replace(tzinfo=est_timezone)
            market_open = date.replace(hour=9, minute=30, second=0, microsecond=0)
            market_open = market_open.replace(tzinfo=est_timezone)
            
            start_timestamp = int(premarket_start.timestamp() * 1000)
            end_timestamp = int(market_open.timestamp() * 1000)
            
            premarket_bars = self.polygon_client.list_aggs(
                ticker=ticker, multiplier=1, timespan='minute',
                from_=start_timestamp, to=end_timestamp, limit=50000
            )
            
            premarket_list = list(premarket_bars)
            
            if premarket_list:
                opening_price = premarket_list[-1].close
                gap_percent = ((opening_price - prev_close) / prev_close) * 100
            else:
                daily_data = self.polygon_client.get_daily_open_close_agg(
                    ticker=ticker, date=date_str
                )
                opening_price = daily_data.open
                gap_percent = ((opening_price - prev_close) / prev_close) * 100
            
            return {
                'prev_close': prev_close,
                'opening_price': opening_price,
                'gap_percent': gap_percent
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting pre-market data for {ticker}: {e}")
            return {'prev_close': 0, 'opening_price': 0, 'gap_percent': 0}
    
    def add_strategy_specific_metrics(self, trade_result: Dict[str, Any], entry_data: Dict[str, Any], analysis: Dict[str, Any]):
        """Add break-out specific metrics to trade result"""
        trade_result.update({
            'gap_percent': entry_data.get('gap_percent', 0),
            'volume_ratio': entry_data.get('forecasted_volume', 0) / entry_data.get('avg_volume', 1),
            'confidence': analysis.get('confidence', 0)
        })
    
    def add_strategy_specific_performance_metrics(self, metrics: Dict[str, Any], df: pd.DataFrame):
        """Add break-out specific performance metrics"""
        try:
            if 'gap_percent' in df.columns:
                gap_analysis = df.groupby(pd.cut(df['gap_percent'], bins=[0, 25, 50, 75, 100, 200]))['net_pnl'].agg(['count', 'mean', 'sum'])
                metrics['gap_analysis'] = gap_analysis.to_dict()
            
            if 'volume_ratio' in df.columns:
                volume_analysis = df.groupby(pd.cut(df['volume_ratio'], bins=[0, 1, 2, 3, 5, 10]))['net_pnl'].agg(['count', 'mean', 'sum'])
                metrics['volume_analysis'] = volume_analysis.to_dict()
            
        except Exception as e:
            logger.error(f"❌ Error adding strategy-specific metrics: {e}")

class TemplateBacktest(BaseBacktest):
    """Template strategy for new implementations"""
    
    def __init__(self):
        # You would import your strategy here
        # from your_strategy import YourStrategy
        # strategy = YourStrategy()
        # super().__init__(strategy, "your_strategy")
        
        # For now, using a placeholder
        super().__init__(None, "template")
    
    def get_stocks_for_date(self, date: datetime) -> List[str]:
        """Get stocks for a specific date - implement your logic here"""
        logger.info(f"🔍 Template: Scanning for stocks on {date.strftime('%Y-%m-%d')}")
        # Implement your stock selection logic
        return []
    
    def get_market_data_for_stock(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        """Get additional market data - implement your logic here"""
        # Implement your data collection logic
        return {}

def get_strategy_backtest(strategy_name: str):
    """Get the appropriate backtest class for a strategy"""
    strategy_map = {
        'break_out': BreakoutBacktest,
        'template': TemplateBacktest,
        #'day_one_short': BreakOutWithVolumeBacktest
        #'day_one_long': BreakOutWithVolumeBacktest
        #'day_two_short': BreakOutWithVolumeBacktest

    }
    
    if strategy_name in strategy_map:
        return strategy_map[strategy_name]
    else:
        raise ValueError(f"Strategy '{strategy_name}' not implemented. Available strategies: {list(strategy_map.keys())}")

def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='Run Strategy Backtest')
    parser.add_argument('--strategy', type=str, required=True,
                       help='Strategy name (e.g., break_out, your_strategy)')
    parser.add_argument('--days', type=int, default=730, 
                       help='Number of days to backtest (default: 730 = 2 years)')
    parser.add_argument('--capital', type=int, default=100000,
                       help='Initial capital in dollars (default: 100000)')
    parser.add_argument('--position-size', type=int, default=1000,
                       help='Number of shares per trade (default: 1000)')
    parser.add_argument('--commission', type=float, default=0.005,
                       help='Commission per trade in dollars (default: 5.00)')
    parser.add_argument('--max-positions', type=int, default=10,
                       help='Maximum concurrent positions (default: 10)')
    parser.add_argument('--output-dir', type=str, default='backtest_reports',
                       help='Output directory for reports (default: backtest_reports)')
    
    args = parser.parse_args()
    
    try:
        logger.info(f"🚀 Starting {args.strategy} Strategy Backtest")
        logger.info(f"📅 Days to test: {args.days}")
        logger.info(f"💰 Initial Capital: ${args.capital:,}")
        logger.info(f"📊 Position Size: {args.position_size} shares")
        logger.info(f"💸 Commission: ${args.commission:.2f} per trade")
        logger.info(f"🎯 Max Positions: {args.max_positions}")
        
        # Get the strategy backtest class
        try:
            BacktestClass = get_strategy_backtest(args.strategy)
            logger.info(f"✅ Strategy class loaded: {BacktestClass.__name__}")
        except Exception as e:
            logger.error(f"❌ Error loading strategy class: {e}")
            return 1
        
        # Initialize backtest with custom parameters
        try:
            backtest = BacktestClass()
            logger.info(f"✅ Backtest initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing backtest: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return 1
        backtest.start_date = datetime.now() - timedelta(days=args.days)
        backtest.initial_capital = args.capital
        backtest.position_size = args.position_size
        backtest.commission_rate = args.commission
        backtest.max_positions = args.max_positions
        
        # Run backtest
        try:
            results = backtest.run_full_backtest()
            
            if 'error' in results:
                logger.error(f"❌ Backtest failed: {results['error']}")
                return 1
        except Exception as e:
            logger.error(f"❌ Error during backtest execution: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return 1
        
        # Print summary
        performance = results['performance']
        logger.info("\n" + "="*50)
        logger.info(f"📊 {args.strategy.upper()} BACKTEST RESULTS SUMMARY")
        logger.info("="*50)
        logger.info(f"Total Trades: {performance.get('total_trades', 0):,}")
        logger.info(f"Winning Trades: {performance.get('winning_trades', 0):,}")
        logger.info(f"Losing Trades: {performance.get('losing_trades', 0):,}")
        logger.info(f"Win Rate: {performance.get('win_rate', 0):.2f}%")
        logger.info(f"Total P&L: ${performance.get('total_pnl', 0):,.2f}")
        logger.info(f"Total Return: {performance.get('total_return', 0):.2f}%")
        logger.info(f"Average P&L per Trade: ${performance.get('avg_pnl', 0):.2f}")
        logger.info(f"Sharpe Ratio: {performance.get('sharpe_ratio', 0):.2f}")
        logger.info(f"Maximum Drawdown: {performance.get('max_drawdown', 0):.2f}%")
        logger.info(f"Max Profit: ${performance.get('max_profit', 0):.2f}")
        logger.info(f"Max Loss: ${performance.get('max_loss', 0):.2f}")
        logger.info("="*50)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("⏹️ Backtest interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Error running backtest: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 