#!/usr/bin/env python3
"""
Gap-Up Detection Cache Manager
Implements smart caching to reduce API calls and improve performance
"""

import os
import time
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from functools import lru_cache
import threading
import pytz
from logging_config import get_logger

logger = get_logger(__name__)

class GapUpCache:
    """Smart caching system for gap-up detection"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_hashes = {}
        self.lock = threading.RLock()
        
        # Cache configuration
        self.default_ttl = 300  # 5 minutes default
        self.max_cache_size = 1000
        self.cleanup_interval = 600  # 10 minutes
        
        # Cache keys
        self.GAP_UP_STOCKS_KEY = "gap_up_stocks"
        self.GAP_UP_FRONTEND_KEY = "gap_up_frontend"
        self.REAL_TIME_GAP_UPS_KEY = "real_time_gap_ups"
        self.MARKET_STATUS_KEY = "market_status"
        
        # Performance tracking
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls_saved = 0
        
        logger.info("✅ Gap-up cache initialized")
    
    def _generate_cache_key(self, function_name: str, **kwargs) -> str:
        """Generate a unique cache key based on function name and parameters"""
        key_parts = [function_name]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return hashlib.md5("_".join(key_parts).encode()).hexdigest()
    
    def _is_cache_fresh(self, cache_key: str, ttl: int = None) -> bool:
        """Check if cache entry is fresh"""
        if cache_key not in self.cache_timestamps:
            return False
        
        if ttl is None:
            ttl = self.default_ttl
        
        age = time.time() - self.cache_timestamps[cache_key]
        return age < ttl
    
    def _get_cache_ttl(self, cache_type: str) -> int:
        """Get TTL based on cache type and market conditions"""
        # Get current time in ET
        et_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(et_tz)
        current_hour = current_time.hour
        
        # Peak hours (9:30-11:30 AM ET and 3:00-5:00 PM ET)
        if (9 <= current_hour <= 11) or (15 <= current_hour <= 17):
            if cache_type == "real_time":
                return 30  # 30 seconds during peak hours
            else:
                return 120  # 2 minutes during peak hours
        
        # Market hours (9:30 AM - 4:00 PM ET)
        elif 9 <= current_hour <= 16:
            if cache_type == "real_time":
                return 60  # 1 minute during market hours
            else:
                return 300  # 5 minutes during market hours
        
        # Outside market hours
        else:
            if cache_type == "real_time":
                return 300  # 5 minutes outside market hours
            else:
                return 600  # 10 minutes outside market hours
    
    def get(self, cache_key: str, cache_type: str = "default") -> Optional[Any]:
        """Get data from cache if fresh"""
        with self.lock:
            if cache_key in self.cache and self._is_cache_fresh(cache_key, self._get_cache_ttl(cache_type)):
                self.cache_hits += 1
                logger.debug(f"✅ Cache HIT: {cache_key}")
                return self.cache[cache_key]
            else:
                self.cache_misses += 1
                logger.debug(f"❌ Cache MISS: {cache_key}")
                return None
    
    def set(self, cache_key: str, data: Any, cache_type: str = "default") -> None:
        """Set data in cache with timestamp"""
        with self.lock:
            # Clean up old entries if cache is full
            if len(self.cache) >= self.max_cache_size:
                self._cleanup_old_entries()
            
            self.cache[cache_key] = data
            self.cache_timestamps[cache_key] = time.time()
            
            # Generate hash for change detection
            data_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
            self.cache_hashes[cache_key] = data_hash
            
            logger.debug(f"💾 Cache SET: {cache_key} ({len(data) if isinstance(data, list) else 'data'})")
    
    def invalidate(self, cache_key: str) -> None:
        """Invalidate a specific cache entry"""
        with self.lock:
            if cache_key in self.cache:
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
                if cache_key in self.cache_hashes:
                    del self.cache_hashes[cache_key]
                logger.debug(f"🗑️ Cache INVALIDATED: {cache_key}")
    
    def invalidate_all(self) -> None:
        """Invalidate all cache entries"""
        with self.lock:
            self.cache.clear()
            self.cache_timestamps.clear()
            self.cache_hashes.clear()
            logger.info("🗑️ All cache entries invalidated")
    
    def _cleanup_old_entries(self) -> None:
        """Remove old cache entries"""
        current_time = time.time()
        keys_to_remove = []
        
        for key, timestamp in self.cache_timestamps.items():
            if current_time - timestamp > self.default_ttl * 2:  # Remove entries older than 2x TTL
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
            del self.cache_timestamps[key]
            if key in self.cache_hashes:
                del self.cache_hashes[key]
        
        if keys_to_remove:
            logger.debug(f"🧹 Cleaned up {len(keys_to_remove)} old cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self.lock:
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_rate_percent': round(hit_rate, 2),
                'api_calls_saved': self.api_calls_saved,
                'cache_size': len(self.cache),
                'max_cache_size': self.max_cache_size,
                'cache_keys': list(self.cache.keys())
            }
    
    def has_changed(self, cache_key: str, new_data: Any) -> bool:
        """Check if data has changed since last cache"""
        if cache_key not in self.cache_hashes:
            return True
        
        new_hash = hashlib.md5(json.dumps(new_data, sort_keys=True).encode()).hexdigest()
        return new_hash != self.cache_hashes[cache_key]

# Global cache instance
gap_up_cache = GapUpCache()

# Cached function decorators
def cached_gap_up_detection(ttl: int = None, cache_type: str = "default"):
    """Decorator for caching gap-up detection functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = gap_up_cache._generate_cache_key(func.__name__, *args, **kwargs)
            
            # Try to get from cache
            cached_result = gap_up_cache.get(cache_key, cache_type)
            if cached_result is not None:
                gap_up_cache.api_calls_saved += 1
                return cached_result
            
            # Call original function
            result = func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                gap_up_cache.set(cache_key, result, cache_type)
            
            return result
        return wrapper
    return decorator

def cached_real_time_detection(ttl: int = None):
    """Decorator for caching real-time detection functions"""
    return cached_gap_up_detection(ttl, "real_time")

# Specific cache functions for different use cases
def get_cached_gap_up_stocks() -> Optional[List[Dict[str, Any]]]:
    """Get gap-up stocks from cache"""
    return gap_up_cache.get(gap_up_cache.GAP_UP_STOCKS_KEY, "default")

def set_cached_gap_up_stocks(data: List[Dict[str, Any]]) -> None:
    """Set gap-up stocks in cache"""
    gap_up_cache.set(gap_up_cache.GAP_UP_STOCKS_KEY, data, "default")

def get_cached_frontend_gap_ups() -> Optional[List[Dict[str, Any]]]:
    """Get frontend gap-up data from cache"""
    return gap_up_cache.get(gap_up_cache.GAP_UP_FRONTEND_KEY, "default")

def set_cached_frontend_gap_ups(data: List[Dict[str, Any]]) -> None:
    """Set frontend gap-up data in cache"""
    gap_up_cache.set(gap_up_cache.GAP_UP_FRONTEND_KEY, data, "default")

def get_cached_real_time_gap_ups() -> Optional[List[Dict[str, Any]]]:
    """Get real-time gap-ups from cache"""
    return gap_up_cache.get(gap_up_cache.REAL_TIME_GAP_UPS_KEY, "real_time")

def set_cached_real_time_gap_ups(data: List[Dict[str, Any]]) -> None:
    """Set real-time gap-ups in cache"""
    gap_up_cache.set(gap_up_cache.REAL_TIME_GAP_UPS_KEY, data, "real_time")

def invalidate_gap_up_cache() -> None:
    """Invalidate all gap-up related cache entries"""
    gap_up_cache.invalidate(gap_up_cache.GAP_UP_STOCKS_KEY)
    gap_up_cache.invalidate(gap_up_cache.GAP_UP_FRONTEND_KEY)
    gap_up_cache.invalidate(gap_up_cache.REAL_TIME_GAP_UPS_KEY)
    logger.info("🗑️ Gap-up cache invalidated")

def get_cache_stats() -> Dict[str, Any]:
    """Get cache performance statistics"""
    return gap_up_cache.get_stats() 