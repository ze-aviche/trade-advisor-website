#!/usr/bin/env python3
"""
NASDAQ Gainer Scanner
Retrieves top gaining NASDAQ stocks from DAS Trader using TOPLIST command
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
import re

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logging_config import get_logger
from start_das_pro import DASProManager

logger = get_logger('nasgain_scanner')

class NASGainScanner:
    """Scanner for NASDAQ gaining stocks using DAS Trader"""
    
    def __init__(self):
        self.das_manager = DASProManager()
        self.connection = None
        self.is_connected = False
    
    def connect_to_das(self) -> bool:
        """Connect to DAS Trader Pro"""
        try:
            logger.info("🔌 Connecting to DAS Trader Pro...")
            success = self.das_manager.start_and_connect()
            if success:
                self.connection = self.das_manager.connection
                self.is_connected = True
                logger.info("✅ Successfully connected to DAS Trader Pro")
                return True
            else:
                logger.error("❌ Failed to connect to DAS Trader Pro")
                return False
        except Exception as e:
            logger.error(f"❌ Error connecting to DAS: {e}")
            return False
    
    def disconnect_from_das(self):
        """Disconnect from DAS Trader Pro"""
        try:
            if self.das_manager:
                self.das_manager.disconnect()
            self.is_connected = False
            logger.info("🔌 Disconnected from DAS Trader Pro")
        except Exception as e:
            logger.error(f"❌ Error disconnecting: {e}")

    def _fetch_toplist(self, attempts: int = 8, delay_seconds: float = 0.25) -> str:
        """Poll the DAS TOPLIST stream multiple times to accumulate data."""
        if not self.connection:
            return ""
        buffer = ""
        last_len = 0
        for _ in range(attempts):
            chunk = self.connection.SendScript(bytearray("SB TopList\r\n", encoding="ascii")) or ""
            if chunk:
                buffer += chunk
                # Look for the specific DAS TopList format: $TopLst NASActive/NASGain
                if "$TopLst" in buffer:
                    break
            # Stop if buffer stops growing
            if len(buffer) == last_len:
                time.sleep(delay_seconds)
            else:
                last_len = len(buffer)
                time.sleep(delay_seconds)
        return buffer

    def get_toplist_lines(self) -> List[str]:
        """Send SB TopList and poll for data, return raw output as non-empty lines."""
        if not self.is_connected:
            if not self.connect_to_das():
                return []
        response = self._fetch_toplist()
        try:
            self.connection.SendScript(bytearray("UNSB TopList\r\n", encoding="ascii"))
        except Exception:
            pass
        return [line for line in response.splitlines() if line.strip()]


def get_toplist() -> List[str]:
    """Return raw SB TopList output as a list of lines (no parsing)."""
    scanner = NASGainScanner()
    try:
        return scanner.get_toplist_lines()
    finally:
        scanner.disconnect_from_das()


def parse_nasgain_from_lines(lines: List[str]) -> List[str]:
    """
    Parse NASGain stocks from raw TopList lines
    
    Args:
        lines: List of lines from get_toplist_lines()
        
    Returns:
        List of NASGain stock symbols
    """
    for line in lines:
        if line.startswith('$TopLst NASGain'):
            parts = line.split()
            if len(parts) > 2:  # $TopLst NASGain [symbols...]
                return [s.upper() for s in parts[2:] if s.isalpha() and 1 <= len(s) <= 5]
    return []


def parse_nasactive_from_lines(lines: List[str]) -> List[str]:
    """
    Parse NASActive stocks from raw TopList lines
    
    Args:
        lines: List of lines from get_toplist_lines()
        
    Returns:
        List of NASActive stock symbols
    """
    for line in lines:
        if line.startswith('$TopLst NASActive'):
            parts = line.split()
            if len(parts) > 2:  # $TopLst NASActive [symbols...]
                return [s.upper() for s in parts[2:] if s.isalpha() and 1 <= len(s) <= 5]
    return []


def parse_naslost_from_lines(lines: List[str]) -> List[str]:
    """
    Parse NASLost stocks from raw TopList lines
    
    Args:
        lines: List of lines from get_toplist_lines()
        
    Returns:
        List of NASLost stock symbols
    """
    for line in lines:
        if line.startswith('$TopLst NASLost'):
            parts = line.split()
            if len(parts) > 2:  # $TopLst NASLost [symbols...]
                return [s.upper() for s in parts[2:] if s.isalpha() and 1 <= len(s) <= 5]
    return []


def fetch_historical_data_for_nasgain_stocks(nasgain_stocks: List[str], days: int = 365, use_cache: bool = True) -> Dict[str, List[Dict]]:
    """
    Fetch historical gap-up data for all NASGain stocks
    
    Args:
        nasgain_stocks: List of stock symbols from NASGain
        days: Number of days to fetch historical data for (default: 365)
        use_cache: Whether to use caching (default: True)
        
    Returns:
        Dictionary with ticker as key and historical data as value
    """
    try:
        # Import historical_data functions
        from historical_data import get_historical_gap_up_data, fetch_multiple_stocks_parallel
        
        logger.info(f"📊 Fetching historical data for {len(nasgain_stocks)} NASGain stocks")
        logger.info(f"📅 Fetching {days} days of historical data")
        logger.info(f"💾 Using cache: {use_cache}")
        
        # Use parallel processing for better performance
        results = fetch_multiple_stocks_parallel(nasgain_stocks, days=days, use_cache=use_cache)
        
        # Filter out None results and log summary
        valid_results = {ticker: data for ticker, data in results.items() if data is not None}
        failed_tickers = [ticker for ticker, data in results.items() if data is None]
        
        logger.info(f"✅ Successfully fetched data for {len(valid_results)} tickers")
        if failed_tickers:
            logger.warning(f"⚠️ Failed to fetch data for {len(failed_tickers)} tickers: {failed_tickers}")
        
        # Log summary for each ticker
        for ticker, data in valid_results.items():
            if data:
                logger.info(f"📈 {ticker}: Found {len(data)} gap-up days (25%+)")
            else:
                logger.info(f"📊 {ticker}: No gap-up days found in the specified period")
        
        return valid_results
        
    except ImportError as e:
        logger.error(f"❌ Error importing historical_data module: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Error fetching historical data for NASGain stocks: {e}")
        return {}


def get_nasgain_with_historical_data(days: int = 365, use_cache: bool = True) -> Dict[str, List[Dict]]:
    """
    Get NASGain stocks and their historical data in one call
    
    Args:
        days: Number of days to fetch historical data for (default: 365)
        use_cache: Whether to use caching (default: True)
        
    Returns:
        Dictionary with ticker as key and historical data as value
    """
    try:
        # Get NASGain stocks
        lines = get_toplist()
        nasgain_stocks = parse_nasgain_from_lines(lines)
        
        if not nasgain_stocks:
            logger.warning("⚠️ No NASGain stocks found")
            return {}
        
        logger.info(f"📈 Found {len(nasgain_stocks)} NASGain stocks: {nasgain_stocks}")
        
        # Fetch historical data for all NASGain stocks
        historical_data = fetch_historical_data_for_nasgain_stocks(nasgain_stocks, days, use_cache)
        
        return historical_data
        
    except Exception as e:
        logger.error(f"❌ Error getting NASGain stocks with historical data: {e}")
        return {}


def main():
    """Main function for testing the NASGain scanner"""
    print("📈 NASDAQ Gainer Scanner with Historical Data")
    print("=" * 60)
    
    try:
        # Get raw TopList data using standalone function
        print("\n🔍 Getting raw SB TopList output...")
        lines = get_toplist()
        if lines:
            print(f"✅ Received {len(lines)} lines from TopList:")
            for line in lines:
                print(line)
        else:
            print("⚠️ No data returned from SB TopList")
            return
        
        # Parse NASGain stocks from the lines
        print("\n📈 Parsing NASGain stocks from lines...")
        nasgain_stocks = parse_nasgain_from_lines(lines)
        
        if nasgain_stocks:
            print(f"✅ Found {len(nasgain_stocks)} NASGain stocks:")
            for i, stock in enumerate(nasgain_stocks, 1):
                print(f"  {i:2d}. {stock}")
        else:
            print("❌ No NASGain stocks found")
            return
        
        # Fetch historical data for NASGain stocks
        print(f"\n📊 Fetching historical data for {len(nasgain_stocks)} NASGain stocks...")
        print("⏳ This may take a few moments...")
        
        historical_data = fetch_historical_data_for_nasgain_stocks(nasgain_stocks, days=30, use_cache=True)
        
        if historical_data:
            print(f"\n✅ Successfully fetched historical data for {len(historical_data)} stocks:")
            print("-" * 60)
            
            for ticker, data in historical_data.items():
                if data:
                    print(f"📈 {ticker}: {len(data)} gap-up days (25%+)")
                    # Show first few gap-up days
                    for i, day_data in enumerate(data[:3], 1):
                        gap_percent = day_data.get('gap up % at open', 'N/A')
                        date = day_data.get('date', 'N/A')
                        print(f"    {i}. {date}: {gap_percent}% gap")
                    if len(data) > 3:
                        print(f"    ... and {len(data) - 3} more gap-up days")
                else:
                    print(f"📊 {ticker}: No gap-up days found in the last 30 days")
                print()
        else:
            print("❌ No historical data retrieved")
        
        # Parse other stock types for completeness
        # print("\n📊 Parsing NASActive stocks from lines...")
        # nasactive_stocks = parse_nasactive_from_lines(lines)
        
        # if nasactive_stocks:
        #     print(f"✅ Found {len(nasactive_stocks)} NASActive stocks:")
        #     for i, stock in enumerate(nasactive_stocks[:10], 1):  # Show first 10
        #         print(f"  {i:2d}. {stock}")
        #     if len(nasactive_stocks) > 10:
        #         print(f"  ... and {len(nasactive_stocks) - 10} more")
        # else:
        #     print("❌ No NASActive stocks found")
        
        # # Parse NASLost stocks from the lines
        # print("\n📉 Parsing NASLost stocks from lines...")
        # naslost_stocks = parse_naslost_from_lines(lines)
        
        # if naslost_stocks:
        #     print(f"✅ Found {len(naslost_stocks)} NASLost stocks:")
        #     for i, stock in enumerate(naslost_stocks[:10], 1):  # Show first 10
        #         print(f"  {i:2d}. {stock}")
        #     if len(naslost_stocks) > 10:
        #         print(f"  ... and {len(naslost_stocks) - 10} more")
        # else:
        #     print("❌ No NASLost stocks found")
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()