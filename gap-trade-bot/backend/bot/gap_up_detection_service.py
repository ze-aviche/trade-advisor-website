"""
Gap-Up Detection Service
Runs gap-up detection in a separate process to avoid blocking the main trading bot
"""

import asyncio
import time
import multiprocessing
import os
import signal
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

# Configure logging for the detection service
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'gap_up_detection.log')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

from bot.gap_up_db import gap_up_db
from gap_up_detector import get_gap_up_stocks_for_frontend

logger = logging.getLogger(__name__)

class GapUpDetectionService:
    """Background service for gap-up detection"""
    
    def __init__(self):
        self.is_running = False
        self.detection_interval = 300  # 5 minutes
        self.last_detection = None
        self.process = None
        
    def start_background_process(self):
        """Start gap-up detection as a separate process"""
        try:
            logger.info("🚀 Starting gap-up detection service as separate process...")
            
            # Start the detection process
            self.process = multiprocessing.Process(
                target=self._run_detection_process,
                name="GapUpDetectionService"
            )
            self.process.start()
            
            logger.info(f"✅ Gap-up detection service started (PID: {self.process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting gap-up detection service: {e}")
            return False
    
    def stop_background_process(self):
        """Stop the gap-up detection process"""
        try:
            if self.process and self.process.is_alive():
                logger.info("🛑 Stopping gap-up detection service...")
                self.process.terminate()
                self.process.join(timeout=10)
                
                if self.process.is_alive():
                    logger.warning("⚠️ Force killing gap-up detection service...")
                    self.process.kill()
                    self.process.join()
                
                logger.info("✅ Gap-up detection service stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping gap-up detection service: {e}")
    
    def _run_detection_process(self):
        """Run gap-up detection in a separate process"""
        try:
            # Set up logging for the process
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
                handlers=[
                    logging.FileHandler('logs/gap_up_detection.log'),
                    logging.StreamHandler()
                ]
            )
            
            logger.info("🔍 Gap-up detection process started")
            
            # Run initial detection after a short delay
            time.sleep(30)  # Wait 30 seconds before first detection
            
            while True:
                try:
                    self._run_detection()
                    time.sleep(self.detection_interval)
                except KeyboardInterrupt:
                    logger.info("🛑 Gap-up detection process interrupted")
                    break
                except Exception as e:
                    logger.error(f"❌ Error in gap-up detection process: {e}")
                    time.sleep(60)  # Wait 1 minute on error
                    
        except Exception as e:
            logger.error(f"❌ Error in gap-up detection process: {e}")
    
    def _run_detection(self):
        """Run gap-up detection and store results"""
        try:
            # Check if data is fresh
            if gap_up_db.is_data_fresh(max_age_minutes=30):
                logger.info("📊 Gap-up data is fresh, skipping detection")
                return
            
            logger.info("🔍 Running gap-up detection...")
            start_time = time.time()
            
            # Start detection session
            session_id = gap_up_db.start_detection_session()
            if not session_id:
                logger.error("❌ Failed to start detection session")
                return
            
            # Run gap-up detection
            gap_up_data = get_gap_up_stocks_for_frontend()
            
            if gap_up_data:
                # Store results in database
                gap_up_db.store_gap_up_results(session_id, gap_up_data)
                
                # End session
                gap_up_db.end_detection_session(session_id, len(gap_up_data), len(gap_up_data))
                
                detection_time = time.time() - start_time
                logger.info(f"✅ Gap-up detection completed in {detection_time:.1f}s: {len(gap_up_data)} stocks found")
            else:
                logger.warning("⚠️ No gap-up data found")
                gap_up_db.end_detection_session(session_id, 0, 0)
            
            self.last_detection = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Error running gap-up detection: {e}")
    
    def get_gap_up_stocks(self, min_gap_percent: float = 25.0) -> List[str]:
        """Get gap-up stocks from database"""
        return gap_up_db.get_gap_up_stocks(min_gap_percent)
    
    def get_gap_up_data(self, min_gap_percent: float = 25.0) -> List[Dict[str, Any]]:
        """Get full gap-up data from database"""
        return gap_up_db.get_gap_up_data(min_gap_percent)
    
    def is_data_available(self) -> bool:
        """Check if gap-up data is available"""
        return gap_up_db.is_data_fresh(max_age_minutes=60)
    
    def is_process_alive(self) -> bool:
        """Check if the detection process is alive"""
        return self.process and self.process.is_alive()

# Global instance
gap_up_detection_service = GapUpDetectionService() 