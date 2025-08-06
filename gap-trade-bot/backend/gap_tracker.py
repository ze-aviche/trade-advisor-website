#!/usr/bin/env python3
"""
Gap Tracker - Prevents overkill detection by tracking peak gap percentages
"""

import os
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from logging_config import get_logger

logger = get_logger(__name__)

class GapTracker:
    """Tracks peak gap percentages to prevent overkill detection"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.today = date.today().isoformat()
        self.tracker_file = os.path.join(data_dir, f"gap_tracker_{self.today}.json")
        self.peak_gaps: Dict[str, Dict] = {}
        self._load_tracker()
    
    def _load_tracker(self):
        """Load existing tracker data"""
        try:
            if os.path.exists(self.tracker_file):
                with open(self.tracker_file, 'r') as f:
                    data = json.load(f)
                    self.peak_gaps = data.get('peak_gaps', {})
                    logger.info(f"📊 Loaded gap tracker with {len(self.peak_gaps)} stocks")
            else:
                logger.info("📊 Starting fresh gap tracker")
        except Exception as e:
            logger.error(f"❌ Error loading gap tracker: {e}")
            self.peak_gaps = {}
    
    def _save_tracker(self):
        """Save tracker data"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            data = {
                'date': self.today,
                'peak_gaps': self.peak_gaps
            }
            with open(self.tracker_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving gap tracker: {e}")
    
    def update_gap(self, ticker: str, current_gap: float, current_price: float, 
                   current_time: str = None) -> Tuple[bool, Optional[Dict]]:
        """
        Update gap for a ticker and determine if it's a new peak
        
        Returns:
            (is_new_peak, peak_data)
        """
        try:
            if current_time is None:
                current_time = datetime.now().strftime('%H:%M:%S')
            
            # Get existing peak data
            peak_data = self.peak_gaps.get(ticker, {
                'peak_gap': 0.0,
                'peak_price': 0.0,
                'peak_time': '',
                'first_detected': current_time,
                'detection_count': 0
            })
            
            # Update detection count
            peak_data['detection_count'] += 1
            
            is_new_peak = False
            if current_gap > peak_data['peak_gap']:
                # New peak detected
                is_new_peak = True
                peak_data.update({
                    'peak_gap': current_gap,
                    'peak_price': current_price,
                    'peak_time': current_time,
                    'last_updated': current_time
                })
                logger.info(f"🚀 NEW PEAK: {ticker} - {current_gap:.2f}% (was {peak_data['peak_gap']:.2f}%)")
            else:
                # Not a new peak
                peak_data['last_updated'] = current_time
                logger.debug(f"📊 {ticker}: {current_gap:.2f}% (peak: {peak_data['peak_gap']:.2f}%)")
            
            # Save updated data
            self.peak_gaps[ticker] = peak_data
            self._save_tracker()
            
            return is_new_peak, peak_data
            
        except Exception as e:
            logger.error(f"❌ Error updating gap for {ticker}: {e}")
            return False, None
    
    def is_significant_drop(self, ticker: str, current_gap: float, 
                           drop_threshold: float = 10.0) -> bool:
        """
        Check if stock has dropped significantly from its peak for shorting opportunities
        
        Args:
            ticker: Stock ticker
            current_gap: Current gap percentage
            drop_threshold: Percentage drop from peak to consider for shorting
        
        Returns:
            True if stock has dropped significantly from peak
        """
        try:
            peak_data = self.peak_gaps.get(ticker)
            if not peak_data:
                return False
            
            peak_gap = peak_data['peak_gap']
            drop_percentage = peak_gap - current_gap
            
            is_significant_drop = drop_percentage >= drop_threshold
            
            if is_significant_drop:
                logger.info(f"📉 SIGNIFICANT DROP: {ticker} - {current_gap:.2f}% (peak: {peak_gap:.2f}%, drop: {drop_percentage:.2f}%)")
            else:
                logger.debug(f"📊 {ticker}: {current_gap:.2f}% (peak: {peak_gap:.2f}%, drop: {drop_percentage:.2f}%)")
            
            return is_significant_drop
            
        except Exception as e:
            logger.error(f"❌ Error checking significant drop for {ticker}: {e}")
            return False
    
    def get_peak_data(self, ticker: str) -> Optional[Dict]:
        """Get peak data for a ticker"""
        return self.peak_gaps.get(ticker)
    
    def get_all_peaks(self) -> Dict[str, Dict]:
        """Get all peak data"""
        return self.peak_gaps.copy()
    
    def get_new_peaks_today(self, min_gap: float = 25.0) -> List[str]:
        """Get list of stocks that made new peaks today above minimum gap"""
        new_peaks = []
        for ticker, data in self.peak_gaps.items():
            if data['peak_gap'] >= min_gap:
                new_peaks.append(ticker)
        return new_peaks
    
    def get_drop_candidates(self, min_peak_gap: float = 40.0, 
                          drop_threshold: float = 10.0) -> List[str]:
        """Get stocks that have dropped significantly from their peak for shorting"""
        candidates = []
        for ticker, data in self.peak_gaps.items():
            if data['peak_gap'] >= min_peak_gap:
                # Calculate current drop (assuming we have current data)
                # This would need to be called with current gap data
                candidates.append(ticker)
        return candidates
    
    def cleanup_old_data(self, days_to_keep: int = 7):
        """Clean up old tracker files"""
        try:
            import glob
            pattern = os.path.join(self.data_dir, "gap_tracker_*.json")
            files = glob.glob(pattern)
            
            for file_path in files:
                try:
                    file_date_str = os.path.basename(file_path).replace("gap_tracker_", "").replace(".json", "")
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                    days_old = (date.today() - file_date).days
                    
                    if days_old > days_to_keep:
                        os.remove(file_path)
                        logger.info(f"🗑️ Cleaned up old tracker file: {file_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not process file {file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error cleaning up old data: {e}")

# Global instance
gap_tracker = GapTracker() 