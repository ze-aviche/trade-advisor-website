#!/usr/bin/env python3
"""
Scheduled DAS Sync Service
Automatically syncs trades from DAS Trader on a schedule
"""

import threading
import time
import schedule
import pytz
from datetime import datetime, time as time_class
from logging_config import get_logger

logger = get_logger('scheduled_das_sync')

class ScheduledDASSync:
    """Manages scheduled DAS trade synchronization"""
    
    def __init__(self):
        self.scheduler_thread = None
        self.is_running = False
        self.eastern_tz = pytz.timezone('US/Eastern')
        self.last_sync_time = None
        
    def start_scheduler(self):
        """Start the scheduled sync service"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return False
            
        try:
            # Schedule sync every hour during market hours
            schedule.every().hour.at(":00").do(self.sync_trades_if_market_hours)
            
            # Start position sync scheduler (every 10 seconds)
            self.start_position_sync_scheduler()
            
            # Start the scheduler in a separate thread
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
            self.is_running = True
            logger.info("✅ Scheduled DAS sync service started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start scheduled sync: {e}")
            return False
    
    def stop_scheduler(self):
        """Stop the scheduled sync service"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return False
            
        try:
            schedule.clear()
            self.is_running = False
            logger.info("✅ Scheduled DAS sync service stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop scheduled sync: {e}")
            return False
    
    def is_market_hours(self):
        """Check if it's currently market hours (8 AM - 8 PM ET, weekdays only)"""
        try:
            now = datetime.now(self.eastern_tz)
            
            # Check if it's a weekday (Monday = 0, Sunday = 6)
            if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
                logger.info(f"⏰ Weekend detected ({now.strftime('%A')}), market is closed")
                return False
            
            # Check if it's within market hours (8 AM - 8 PM ET)
            market_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
            market_end = now.replace(hour=20, minute=0, second=0, microsecond=0)
            
            is_open = market_start <= now <= market_end
            logger.info(f"⏰ Market hours check: {now.strftime('%A %I:%M %p ET')} - {'OPEN' if is_open else 'CLOSED'}")
            return is_open
            
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False
    
    def sync_trades_if_market_hours(self):
        """Sync trades only if it's market hours"""
        if self.is_market_hours():
            logger.info("🔄 Market hours detected, syncing trades from DAS...")
            try:
                from das_integration import das_trade_manager
                success, message, added_count = das_trade_manager.sync_trades_from_das()
                
                if success:
                    self.last_sync_time = datetime.now()
                    logger.info(f"✅ Scheduled sync completed: {message}")
                else:
                    logger.error(f"❌ Scheduled sync failed: {message}")
                    
            except ImportError as e:
                logger.error(f"❌ Error importing DAS integration: {e}")
            except Exception as e:
                logger.error(f"❌ Error during scheduled sync: {e}")
        else:
            logger.info("⏰ Outside market hours, skipping scheduled sync")
    
    def sync_positions_if_bot_running(self):
        """Sync positions every 10 seconds if bot is running"""
        try:
            # Check if bot is running by importing the trading bot
            from bot.trading_bot import trading_bot
            
            if trading_bot.running:
                logger.debug("🤖 Bot is running, syncing positions from DAS...")
                try:
                    from das_integration import das_trade_manager
                    success, message, updated_count = das_trade_manager.sync_positions_from_das()
                    
                    if success:
                        logger.debug(f"✅ Position sync completed: {message}")
                    else:
                        logger.warning(f"⚠️ Position sync failed: {message}")
                        
                except ImportError as e:
                    logger.error(f"❌ Error importing DAS integration: {e}")
            else:
                logger.debug("🤖 Bot is not running, skipping position sync")
                
        except ImportError as e:
            logger.debug(f"🤖 Bot not available: {e}")
        except Exception as e:
            logger.error(f"❌ Error checking bot status: {e}")
    
    def start_position_sync_scheduler(self):
        """Start the position sync scheduler (every 10 seconds)"""
        try:
            # Schedule position sync every 10 seconds
            schedule.every(10).seconds.do(self.sync_positions_if_bot_running)
            logger.info("✅ Position sync scheduler started (every 10 seconds)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start position sync scheduler: {e}")
            return False
    
    def manual_sync_now(self):
        """Trigger a manual sync immediately"""
        logger.info("🔄 Manual sync triggered...")
        try:
            from das_integration import das_trade_manager
            success, message, added_count = das_trade_manager.sync_trades_from_das()
            
            if success:
                self.last_sync_time = datetime.now()
                logger.info(f"✅ Manual sync completed: {message}")
                return {
                    'success': True,
                    'message': message,
                    'synced_count': added_count
                }
            else:
                logger.error(f"❌ Manual sync failed: {message}")
                return {
                    'success': False,
                    'message': message,
                    'synced_count': 0
                }
                
        except ImportError as e:
            logger.error(f"❌ Error importing DAS integration: {e}")
            return {
                'success': False,
                'message': 'DAS integration module not available',
                'synced_count': 0
            }
        except Exception as e:
            logger.error(f"❌ Error during manual sync: {e}")
            return {
                'success': False,
                'message': f'Error during manual sync: {str(e)}',
                'synced_count': 0
            }
    
    def get_status(self):
        """Get current sync service status"""
        return {
            'is_running': self.is_running,
            'is_market_hours': self.is_market_hours(),
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'next_sync': self._get_next_sync_time()
        }
    
    def _get_next_sync_time(self):
        """Get the next scheduled sync time"""
        try:
            next_job = schedule.next_run()
            if next_job:
                return next_job.isoformat()
            return None
        except Exception as e:
            logger.error(f"Error getting next sync time: {e}")
            return None
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        logger.info("🔄 Starting scheduler loop...")
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)

# Global instance
scheduled_sync = ScheduledDASSync()

# Convenience functions for the API
def start_scheduled_sync():
    """Start the scheduled sync service"""
    return scheduled_sync.start_scheduler()

def stop_scheduled_sync():
    """Stop the scheduled sync service"""
    return scheduled_sync.stop_scheduler()

def get_sync_status():
    """Get the current sync status"""
    return scheduled_sync.get_status()

def manual_sync():
    """Trigger a manual sync"""
    return scheduled_sync.manual_sync_now()

if __name__ == "__main__":
    # Test the scheduled sync service
    print("🧪 Testing Scheduled DAS Sync Service...")
    
    # Test market hours check
    print(f"Market hours: {scheduled_sync.is_market_hours()}")
    
    # Test status
    status = scheduled_sync.get_status()
    print(f"Status: {status}")
    
    # Test manual sync
    result = scheduled_sync.manual_sync_now()
    print(f"Manual sync result: {result}")
