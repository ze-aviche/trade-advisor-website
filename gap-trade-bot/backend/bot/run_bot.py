#!/usr/bin/env python3
"""
Trading Bot Runner
Simple script to start and manage the trading bot
"""

import asyncio
import sys
import os
import signal
import time
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path for backend imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trading_bot import trading_bot
from logging_config import setup_logging, get_logger

# Setup bot logging
setup_logging(log_level='INFO', log_dir='logs')

logger = get_logger(__name__)

class BotRunner:
    """Simple bot runner with signal handling and PID management"""
    
    def __init__(self):
        self.running = False
        self.pid_file = Path(__file__).parent / "bot.pid"
        self.status_file = Path(__file__).parent / "bot_status.json"
        
    def write_pid_file(self):
        """Write PID to file for external management"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            logger.info(f"📝 PID file written: {self.pid_file}")
        except Exception as e:
            logger.error(f"❌ Error writing PID file: {e}")
    
    def remove_pid_file(self):
        """Remove PID file"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.info("🗑️ PID file removed")
        except Exception as e:
            logger.error(f"❌ Error removing PID file: {e}")
    
    def write_status_file(self, status: dict):
        """Write bot status to file"""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error writing status file: {e}")
        
    async def start_bot(self):
        """Start the trading bot"""
        try:
            logger.info("🚀 Starting Trading Bot...")
            logger.info("📊 Strategy: Break Out")
            logger.info("💰 Volume: 1000 shares per trade")
            logger.info("🛑 Stop Loss: 15%")
            logger.info("🎯 Target: 50% profit")
            
            # Write PID file
            self.write_pid_file()
            
            # Write initial status
            self.write_status_file({
                'status': 'running',
                'started_at': datetime.now().isoformat(),
                'pid': os.getpid()
            })
            
            # Start the bot
            await trading_bot.start()
            
        except KeyboardInterrupt:
            logger.info("⚠️ Received interrupt signal")
            await self.stop_bot()
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            await self.stop_bot()
    
    async def stop_bot(self):
        """Stop the trading bot"""
        try:
            logger.info("🛑 Stopping Trading Bot...")
            
            # Update status
            self.write_status_file({
                'status': 'stopping',
                'stopped_at': datetime.now().isoformat()
            })
            
            await trading_bot.stop()
            
            # Print final statistics
            status = trading_bot.get_bot_status()
            logger.info("📊 Final Statistics:")
            logger.info(f"   Total Trades: {status.get('total_trades', 0)}")
            logger.info(f"   Winning Trades: {status.get('winning_trades', 0)}")
            logger.info(f"   Losing Trades: {status.get('losing_trades', 0)}")
            logger.info(f"   Win Rate: {status.get('win_rate', 0)}%")
            
            position_summary = status.get('position_summary', {})
            logger.info(f"   Active Positions: {position_summary.get('active_positions', 0)}")
            logger.info(f"   Total P&L: ${position_summary.get('total_pnl', 0):.2f}")
            
            # Update final status
            self.write_status_file({
                'status': 'stopped',
                'stopped_at': datetime.now().isoformat(),
                'final_stats': status
            })
            
            # Remove PID file
            self.remove_pid_file()
            
            logger.info("✅ Trading Bot stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle interrupt signals"""
        logger.info(f"📡 Received signal {signum}")
        self.running = False
    
    async def run(self):
        """Main run method"""
        try:
            # Set up signal handlers
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            self.running = True
            
            # Start the bot
            await self.start_bot()
            
        except Exception as e:
            logger.error(f"❌ Error in bot runner: {e}")
        finally:
            await self.stop_bot()

async def main():
    """Main function"""
    runner = BotRunner()
    await runner.run()

if __name__ == "__main__":
    logger.info("🤖 Gap Trade Bot")
    logger.info("=" * 50)
    logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📝 PID file: {Path(__file__).parent / 'bot.pid'}")
    logger.info("🛑 To stop: kill $(cat bot.pid) or use stop_bot.sh")
    logger.info("=" * 50)
    
    asyncio.run(main()) 