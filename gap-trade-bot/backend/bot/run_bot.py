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
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trading_bot import trading_bot
from logging_config import get_logger

logger = get_logger(__name__)

class BotRunner:
    """Simple bot runner with signal handling"""
    
    def __init__(self):
        self.running = False
        
    async def start_bot(self):
        """Start the trading bot"""
        try:
            logger.info("🚀 Starting Trading Bot...")
            logger.info("📊 Strategy: Buy Over HOD")
            logger.info("💰 Volume: 1000 shares per trade")
            logger.info("🛑 Stop Loss: 15%")
            logger.info("🎯 Target: 50% profit")
            
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
    print("🤖 Gap Trade Bot")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📊 Strategy: Buy Over HOD")
    print("💰 Volume: 1000 shares per trade")
    print("🛑 Stop Loss: 15%")
    print("🎯 Target: 50% profit")
    print("=" * 50)
    
    # Run the bot
    asyncio.run(main()) 