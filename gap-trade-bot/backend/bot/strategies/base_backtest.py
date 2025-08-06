#!/usr/bin/env python3
"""
Base Backtesting Framework
Generalized backtesting engine that can work with any strategy
"""

import sys
import os
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any, Protocol
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
import seaborn as sns
from abc import ABC, abstractmethod

# Add parent directories to path for backend imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from logging_config import get_logger
from bot.config import config as bot_config
from historical_data import get_polygon_client, get_historical_gap_up_data

logger = get_logger(__name__)

class StrategyInterface(Protocol):
    """Protocol defining required methods for any strategy"""
    
    def analyze_entry_conditions(self, ticker: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if entry conditions are met"""
        ...
    
    def should_enter_position(self, analysis: Dict[str, Any]) -> bool:
        """Determine if we should enter a position"""
        ...
    
    def should_exit_position(self, current_price: float, entry_price: float, 
                           target_price: float, stop_loss_price: float) -> Tuple[bool, str]:
        """Determine if we should exit the position"""
        ...
    
    def calculate_entry_price(self, current_price: float, day_high: float) -> float:
        """Calculate optimal entry price"""
        ...
    
    def calculate_target_price(self, entry_price: float) -> float:
        """Calculate target price for profit taking"""
        ...
    
    def calculate_stop_loss_price(self, entry_price: float) -> float:
        """Calculate stop loss price"""
        ...

class BaseBacktest(ABC):
    """Base backtesting engine that can work with any strategy"""
    
    def __init__(self, strategy: StrategyInterface, strategy_name: str = "unknown"):
        self.strategy = strategy
        self.strategy_name = strategy_name
        self.polygon_client = get_polygon_client()
        self.results = []
        self.daily_stats = []
        self.start_date = datetime.now() - timedelta(days=730)  # 2 years ago
        self.end_date = datetime.now()
        
        # Backtest configuration
        self.initial_capital = 100000  # $100k starting capital
        self.position_size = 1000  # 1000 shares per trade
        self.max_positions = 10  # Maximum concurrent positions
        self.commission_rate = 0.005  # $5 per trade
        
        # Performance tracking
        self.current_capital = self.initial_capital
        self.open_positions = {}
        self.closed_positions = []
        self.daily_pnl = {}
        
        logger.info(f"🚀 {strategy_name} Backtest initialized")
        logger.info(f"📅 Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        logger.info(f"💰 Initial Capital: ${self.initial_capital:,}")
    
    @abstractmethod
    def get_stocks_for_date(self, date: datetime) -> List[str]:
        """Get stocks to test for a specific date - must be implemented by subclass"""
        pass
    
    @abstractmethod
    def get_market_data_for_stock(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        """Get market data for a stock on a specific date - must be implemented by subclass"""
        pass
    
    def get_intraday_data(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        """Get intraday data for a ticker on a specific date"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # Get 1-minute bars for the entire trading day
            start_time = date.replace(hour=9, minute=30, second=0, microsecond=0)
            end_time = date.replace(hour=16, minute=0, second=0, microsecond=0)
            
            start_timestamp = int(start_time.timestamp() * 1000)
            end_timestamp = int(end_time.timestamp() * 1000)
            
            # Fetch intraday data
            aggs_data = self.polygon_client.list_aggs(
                ticker=ticker,
                multiplier=1,
                timespan='minute',
                from_=start_timestamp,
                to=end_timestamp,
                limit=50000
            )
            
            bars = list(aggs_data)
            if not bars:
                logger.warning(f"⚠️ No intraday data for {ticker} on {date_str}")
                return None
            
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame([{
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'vwap': bar.vwap
            } for bar in bars])
            
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('datetime')
            
            return {
                'ticker': ticker,
                'date': date_str,
                'data': df,
                'bars': bars
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting intraday data for {ticker} on {date}: {e}")
            return None
    
    def simulate_market_data(self, ticker: str, date: datetime, intraday_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Simulate market data points throughout the trading day"""
        try:
            df = intraday_data['data']
            market_data_points = []
            
            # Get additional data for the stock
            additional_data = self.get_market_data_for_stock(ticker, date)
            
            # Calculate average volume for the day
            avg_volume = df['volume'].mean()
            
            # Simulate data points every 1 minute for accurate price capture
            for i in range(0, len(df), 1):
                if i >= len(df):
                    break
                    
                bar = df.iloc[i]
                current_time = bar['datetime']
                
                # Calculate cumulative volume up to this point
                cumulative_volume = df.iloc[:i+1]['volume'].sum()
                
                # Forecast full day volume
                hours_elapsed = (current_time - df.iloc[0]['datetime']).total_seconds() / 3600
                hours_remaining = 6.5 - hours_elapsed  # 6.5 hour trading day
                
                if hours_remaining > 0:
                    forecasted_volume = cumulative_volume + (cumulative_volume / hours_elapsed * hours_remaining)
                else:
                    forecasted_volume = cumulative_volume
                
                # Calculate VWAP up to this point
                vwap = (df.iloc[:i+1]['close'] * df.iloc[:i+1]['volume']).sum() / df.iloc[:i+1]['volume'].sum()
                
                # Get day high up to this point
                day_high = df.iloc[:i+1]['high'].max()
                
                # Base market data
                market_data = {
                    'ticker': ticker,
                    'current_price': bar['close'],
                    'day_high': day_high,
                    'market_status': 'open',
                    'current_volume': cumulative_volume,
                    'forecasted_volume': forecasted_volume,
                    'avg_volume': avg_volume,
                    'vwap': vwap,
                    'current_time': current_time.strftime('%H:%M'),
                    'hours_remaining': hours_remaining
                }
                
                # Add strategy-specific data
                if additional_data:
                    market_data.update(additional_data)
                
                market_data_points.append(market_data)
            
            return market_data_points
            
        except Exception as e:
            logger.error(f"❌ Error simulating market data for {ticker}: {e}")
            return []
    
    def run_backtest_for_date(self, date: datetime) -> List[Dict[str, Any]]:
        """Run backtest for a specific date"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            logger.info(f"📅 Running {self.strategy_name} backtest for {date_str}")
            
            # Skip weekends
            if date.weekday() >= 5:
                logger.info(f"⏭️ Skipping weekend: {date_str}")
                return []
            
            # Get stocks for the date
            stocks = self.get_stocks_for_date(date)
            
            if not stocks:
                logger.info(f"📊 No stocks found for {date_str}")
                return []
            
            daily_results = []
            
            # Test each stock
            for ticker in stocks:
                try:
                    # Get intraday data
                    intraday_data = self.get_intraday_data(ticker, date)
                    if not intraday_data:
                        continue
                    
                    # Simulate market data points
                    market_data_points = self.simulate_market_data(ticker, date, intraday_data)
                    
                    if not market_data_points:
                        continue
                    
                    # Test strategy on each data point
                    trade_result = self.test_strategy_on_stock(ticker, market_data_points, date)
                    
                    if trade_result:
                        daily_results.append(trade_result)
                        
                except Exception as e:
                    logger.error(f"❌ Error testing {ticker} on {date_str}: {e}")
                    continue
            
            return daily_results
            
        except Exception as e:
            logger.error(f"❌ Error running backtest for {date}: {e}")
            return []
    
    def test_strategy_on_stock(self, ticker: str, market_data_points: List[Dict[str, Any]], date: datetime) -> Optional[Dict[str, Any]]:
        """Test the strategy on a single stock"""
        try:
            entry_signal = False
            entry_data = None
            entry_time = None
            exit_data = None
            exit_time = None
            exit_reason = None
            
            # Test each market data point for entry signal
            for i, data_point in enumerate(market_data_points):
                # Analyze entry conditions
                analysis = self.strategy.analyze_entry_conditions(ticker, data_point)
                
                if analysis.get('entry_signal', False):
                    entry_signal = True
                    entry_data = data_point
                    entry_time = data_point['current_time']
                    
                    # Calculate entry parameters
                    entry_price = self.strategy.calculate_entry_price(
                        data_point['current_price'], 
                        data_point['day_high']
                    )
                    target_price = self.strategy.calculate_target_price(entry_price)
                    stop_loss_price = self.strategy.calculate_stop_loss_price(entry_price)
                    
                    # Test exit conditions on remaining data points
                    for j in range(i + 1, len(market_data_points)):
                        exit_point = market_data_points[j]
                        current_price = exit_point['current_price']
                        
                        should_exit, reason = self.strategy.should_exit_position(
                            current_price, entry_price, target_price, stop_loss_price
                        )
                        
                        if should_exit:
                            exit_data = exit_point
                            exit_time = exit_point['current_time']
                            exit_reason = reason
                            break
                    
                    # If no exit during the day, use end-of-day price
                    if not exit_data and market_data_points:
                        last_point = market_data_points[-1]
                        exit_data = last_point
                        exit_time = last_point['current_time']
                        exit_reason = 'end_of_day'
                    
                    break
            
            if entry_signal and exit_data:
                # Calculate trade results
                entry_price = entry_data['current_price']
                exit_price = exit_data['current_price']
                price_change = exit_price - entry_price
                price_change_percent = (price_change / entry_price) * 100
                
                # Calculate P&L
                shares = self.position_size
                gross_pnl = price_change * shares
                commission = self.commission_rate * 2  # Entry and exit
                net_pnl = gross_pnl - commission
                
                trade_result = {
                    'ticker': ticker,
                    'strategy': self.strategy_name,
                    'date': date.strftime('%Y-%m-%d'),
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'target_price': target_price,
                    'stop_loss_price': stop_loss_price,
                    'price_change': price_change,
                    'price_change_percent': price_change_percent,
                    'gross_pnl': gross_pnl,
                    'commission': commission,
                    'net_pnl': net_pnl,
                    'exit_reason': exit_reason,
                    'shares': shares,
                    'confidence': analysis.get('confidence', 0)
                }
                
                # Add strategy-specific metrics
                self.add_strategy_specific_metrics(trade_result, entry_data, analysis)
                
                return trade_result
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error testing strategy on {ticker}: {e}")
            return None
    
    def add_strategy_specific_metrics(self, trade_result: Dict[str, Any], entry_data: Dict[str, Any], analysis: Dict[str, Any]):
        """Add strategy-specific metrics to trade result - can be overridden by subclasses"""
        pass
    
    def run_full_backtest(self) -> Dict[str, Any]:
        """Run the full backtest over the specified period"""
        try:
            logger.info(f"🚀 Starting full {self.strategy_name} backtest...")
            
            # Generate date range
            current_date = self.start_date
            all_results = []
            
            while current_date <= self.end_date:
                daily_results = self.run_backtest_for_date(current_date)
                all_results.extend(daily_results)
                current_date += timedelta(days=1)
            
            # Calculate performance metrics
            performance = self.calculate_performance_metrics(all_results)
            
            # Save results
            self.save_results(all_results, performance)
            
            # Generate reports
            self.generate_reports(all_results, performance)
            
            return {
                'results': all_results,
                'performance': performance
            }
            
        except Exception as e:
            logger.error(f"❌ Error in full backtest: {e}")
            return {'error': str(e)}
    
    def calculate_performance_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        try:
            if not results:
                return {'error': 'No results to analyze'}
            
            df = pd.DataFrame(results)
            
            # Basic metrics
            total_trades = len(df)
            winning_trades = len(df[df['net_pnl'] > 0])
            losing_trades = len(df[df['net_pnl'] < 0])
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
            
            # P&L metrics
            total_pnl = df['net_pnl'].sum()
            avg_pnl = df['net_pnl'].mean()
            max_profit = df['net_pnl'].max()
            max_loss = df['net_pnl'].min()
            
            # Risk metrics
            std_pnl = df['net_pnl'].std()
            sharpe_ratio = avg_pnl / std_pnl if std_pnl > 0 else 0
            
            # Return metrics
            total_return = (total_pnl / self.initial_capital) * 100
            avg_return_per_trade = (avg_pnl / self.initial_capital) * 100
            
            # Exit reason analysis
            exit_reasons = df['exit_reason'].value_counts()
            
            # Monthly performance
            df['date'] = pd.to_datetime(df['date'])
            df['month'] = df['date'].dt.to_period('M')
            monthly_performance = df.groupby('month')['net_pnl'].agg(['count', 'sum', 'mean'])
            
            # Drawdown calculation
            cumulative_pnl = df['net_pnl'].cumsum()
            running_max = cumulative_pnl.expanding().max()
            drawdown = (cumulative_pnl - running_max) / running_max * 100
            max_drawdown = drawdown.min()
            
            metrics = {
                'strategy_name': self.strategy_name,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'std_pnl': std_pnl,
                'sharpe_ratio': sharpe_ratio,
                'total_return': total_return,
                'avg_return_per_trade': avg_return_per_trade,
                'max_drawdown': max_drawdown,
                'exit_reasons': exit_reasons.to_dict(),
                'monthly_performance': monthly_performance.to_dict()
            }
            
            # Add strategy-specific metrics
            self.add_strategy_specific_performance_metrics(metrics, df)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error calculating performance metrics: {e}")
            return {'error': str(e)}
    
    def add_strategy_specific_performance_metrics(self, metrics: Dict[str, Any], df: pd.DataFrame):
        """Add strategy-specific performance metrics - can be overridden by subclasses"""
        pass
    
    def save_results(self, results: List[Dict[str, Any]], performance: Dict[str, Any]):
        """Save backtest results to file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.strategy_name}_backtest_results_{timestamp}.json"
            filepath = os.path.join(os.path.dirname(__file__), filename)
            
            output = {
                'backtest_info': {
                    'strategy': self.strategy_name,
                    'start_date': self.start_date.strftime('%Y-%m-%d'),
                    'end_date': self.end_date.strftime('%Y-%m-%d'),
                    'initial_capital': self.initial_capital,
                    'position_size': self.position_size,
                    'commission_rate': self.commission_rate
                },
                'results': results,
                'performance': performance,
                'timestamp': timestamp
            }
            
            with open(filepath, 'w') as f:
                json.dump(output, f, indent=2, default=str)
            
            logger.info(f"💾 Results saved to {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Error saving results: {e}")
    
    def generate_reports(self, results: List[Dict[str, Any]], performance: Dict[str, Any]):
        """Generate comprehensive reports and visualizations"""
        try:
            if not results:
                logger.warning("⚠️ No results to generate reports for")
                return
            
            df = pd.DataFrame(results)
            
            # Create reports directory
            reports_dir = os.path.join(os.path.dirname(__file__), 'backtest_reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 1. Summary Report
            self.generate_summary_report(performance, reports_dir, timestamp)
            
            # 2. Trade Analysis Report
            self.generate_trade_analysis_report(df, reports_dir, timestamp)
            
            # 3. Visualizations
            self.generate_visualizations(df, performance, reports_dir, timestamp)
            
            logger.info(f"📊 Reports generated in {reports_dir}")
            
        except Exception as e:
            logger.error(f"❌ Error generating reports: {e}")
    
    def generate_summary_report(self, performance: Dict[str, Any], reports_dir: str, timestamp: str):
        """Generate summary report"""
        try:
            report_path = os.path.join(reports_dir, f'{self.strategy_name}_summary_report_{timestamp}.txt')
            
            with open(report_path, 'w') as f:
                f.write(f"{self.strategy_name.upper()} STRATEGY BACKTEST SUMMARY\n")
                f.write("=" * 50 + "\n\n")
                
                f.write(f"Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}\n")
                f.write(f"Initial Capital: ${self.initial_capital:,}\n")
                f.write(f"Position Size: {self.position_size} shares\n\n")
                
                f.write("PERFORMANCE METRICS\n")
                f.write("-" * 20 + "\n")
                f.write(f"Total Trades: {performance.get('total_trades', 0):,}\n")
                f.write(f"Winning Trades: {performance.get('winning_trades', 0):,}\n")
                f.write(f"Losing Trades: {performance.get('losing_trades', 0):,}\n")
                f.write(f"Win Rate: {performance.get('win_rate', 0):.2f}%\n")
                f.write(f"Total P&L: ${performance.get('total_pnl', 0):,.2f}\n")
                f.write(f"Average P&L per Trade: ${performance.get('avg_pnl', 0):.2f}\n")
                f.write(f"Total Return: {performance.get('total_return', 0):.2f}%\n")
                f.write(f"Sharpe Ratio: {performance.get('sharpe_ratio', 0):.2f}\n")
                f.write(f"Maximum Drawdown: {performance.get('max_drawdown', 0):.2f}%\n")
                f.write(f"Max Profit: ${performance.get('max_profit', 0):.2f}\n")
                f.write(f"Max Loss: ${performance.get('max_loss', 0):.2f}\n\n")
                
                f.write("EXIT REASON ANALYSIS\n")
                f.write("-" * 20 + "\n")
                exit_reasons = performance.get('exit_reasons', {})
                for reason, count in exit_reasons.items():
                    f.write(f"{reason}: {count} trades\n")
                
        except Exception as e:
            logger.error(f"❌ Error generating summary report: {e}")
    
    def generate_trade_analysis_report(self, df: pd.DataFrame, reports_dir: str, timestamp: str):
        """Generate detailed trade analysis report"""
        try:
            report_path = os.path.join(reports_dir, f'{self.strategy_name}_trade_analysis_{timestamp}.txt')
            
            with open(report_path, 'w') as f:
                f.write(f"DETAILED {self.strategy_name.upper()} TRADE ANALYSIS\n")
                f.write("=" * 30 + "\n\n")
                
                # Top performing trades
                f.write("TOP 10 PROFITABLE TRADES\n")
                f.write("-" * 25 + "\n")
                top_trades = df.nlargest(10, 'net_pnl')[['ticker', 'date', 'net_pnl', 'price_change_percent', 'exit_reason']]
                f.write(top_trades.to_string(index=False))
                f.write("\n\n")
                
                # Worst performing trades
                f.write("TOP 10 LOSING TRADES\n")
                f.write("-" * 20 + "\n")
                worst_trades = df.nsmallest(10, 'net_pnl')[['ticker', 'date', 'net_pnl', 'price_change_percent', 'exit_reason']]
                f.write(worst_trades.to_string(index=False))
                f.write("\n\n")
                
                # Monthly breakdown
                f.write("MONTHLY PERFORMANCE\n")
                f.write("-" * 20 + "\n")
                monthly = df.groupby(df['date'].dt.to_period('M'))['net_pnl'].agg(['count', 'sum', 'mean'])
                f.write(monthly.to_string())
                
        except Exception as e:
            logger.error(f"❌ Error generating trade analysis report: {e}")
    
    def generate_visualizations(self, df: pd.DataFrame, performance: Dict[str, Any], reports_dir: str, timestamp: str):
        """Generate performance visualizations"""
        try:
            # Set style
            plt.style.use('seaborn-v0_8')
            
            # 1. Cumulative P&L
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            
            # Cumulative P&L
            df['cumulative_pnl'] = df['net_pnl'].cumsum()
            axes[0, 0].plot(df.index, df['cumulative_pnl'])
            axes[0, 0].set_title(f'{self.strategy_name} - Cumulative P&L')
            axes[0, 0].set_ylabel('P&L ($)')
            axes[0, 0].grid(True)
            
            # P&L Distribution
            axes[0, 1].hist(df['net_pnl'], bins=50, alpha=0.7)
            axes[0, 1].set_title(f'{self.strategy_name} - P&L Distribution')
            axes[0, 1].set_xlabel('P&L ($)')
            axes[0, 1].set_ylabel('Frequency')
            
            # Win Rate by Month
            monthly_wins = df.groupby(df['date'].dt.to_period('M')).apply(
                lambda x: (x['net_pnl'] > 0).sum() / len(x) * 100
            )
            axes[1, 0].bar(range(len(monthly_wins)), monthly_wins.values)
            axes[1, 0].set_title(f'{self.strategy_name} - Win Rate by Month')
            axes[1, 0].set_ylabel('Win Rate (%)')
            axes[1, 0].set_xticks(range(len(monthly_wins)))
            axes[1, 0].set_xticklabels([str(m) for m in monthly_wins.index], rotation=45)
            
            # Exit Reasons
            exit_reasons = df['exit_reason'].value_counts()
            axes[1, 1].pie(exit_reasons.values, labels=exit_reasons.index, autopct='%1.1f%%')
            axes[1, 1].set_title(f'{self.strategy_name} - Exit Reasons')
            
            plt.tight_layout()
            plt.savefig(os.path.join(reports_dir, f'{self.strategy_name}_performance_charts_{timestamp}.png'), dpi=300, bbox_inches='tight')
            plt.close()
            
        except Exception as e:
            logger.error(f"❌ Error generating visualizations: {e}") 