#!/usr/bin/env python3
"""
Test script for pre-populating a small set of unique small cap stocks.
"""

import os
import sys
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_data import get_historical_gap_up_data
from historical_cache import historical_cache
from logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Unique small cap stocks (no duplicates)
TEST_SMALL_CAPS = [
    'WINT', 'HOLO', 'FTFT', 'SONN', 'XBP', 'LIDR', 'MULN', 'SNDL', 'HEXO', 'TLRY',
    'ACB', 'CGC', 'APHA', 'CRON', 'AUR', 'LAZR', 'VLDR', 'QS', 'NKLA', 'WKHS',
    'IDEX', 'SOLO', 'RIDE', 'GOEV', 'NIO', 'XPEV', 'LI', 'RIVN', 'LCID',
    'BNGO', 'OCGN', 'INO', 'VXRT', 'MRNA', 'BNTX', 'NVAX', 'SAVA', 'CTXR', 'ATOS',
    'ZOM', 'CIDM', 'SENS', 'GNUS', 'MARK', 'SHIP', 'TOPS', 'NAKD', 'CTRM',
    'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CLSK', 'ARBK', 'CIFR', 'BTBT', 'WULF',
    'HIVE', 'CAN', 'GME', 'AMC', 'BBBY', 'BB', 'NOK', 'KOSS', 'EXPR',
    'UWMC', 'RKT', 'COIN', 'HOOD', 'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL'
]

def process_stock(ticker, days=365):
    """Process a single stock and cache its gap-up data."""
    try:
        logger.info(f"🔄 Processing {ticker}...")
        start_time = time.time()
        
        # Get historical gap-up data
        result = get_historical_gap_up_data(ticker, days, use_cache=True)
        
        duration = time.time() - start_time
        
        if result:
            logger.info(f"✅ {ticker}: {len(result)} gap-up days in {duration:.2f}s")
            return {
                'ticker': ticker,
                'success': True,
                'gap_up_days': len(result),
                'duration': duration
            }
        else:
            logger.info(f"⚠️ {ticker}: No gap-up data found in {duration:.2f}s")
            return {
                'ticker': ticker,
                'success': False,
                'gap_up_days': 0,
                'duration': duration
            }
            
    except Exception as e:
        logger.error(f"❌ Error processing {ticker}: {e}")
        return {
            'ticker': ticker,
            'success': False,
            'error': str(e),
            'gap_up_days': 0,
            'duration': 0
        }

def main():
    """Main function to test small cap stock pre-population."""
    logger.info("🚀 Starting test small cap stock pre-population...")
    
    # Remove duplicates and get unique list
    unique_stocks = list(set(TEST_SMALL_CAPS))
    logger.info(f"📊 Processing {len(unique_stocks)} unique small cap stocks...")
    
    # Process stocks in parallel
    results = []
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all tasks
        future_to_ticker = {
            executor.submit(process_stock, ticker): ticker 
            for ticker in unique_stocks
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                results.append(result)
                
                if result['success']:
                    successful += 1
                else:
                    failed += 1
                    
                # Progress update
                completed = len(results)
                logger.info(f"📈 Progress: {completed}/{len(unique_stocks)} ({completed/len(unique_stocks)*100:.1f}%)")
                
            except Exception as e:
                logger.error(f"❌ Error processing {ticker}: {e}")
                failed += 1
    
    # Summary
    total_duration = sum(r['duration'] for r in results)
    total_gap_ups = sum(r['gap_up_days'] for r in results if r['success'])
    
    logger.info("🎯 Test Pre-population Summary:")
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Total gap-up days cached: {total_gap_ups}")
    logger.info(f"⏱️ Total processing time: {total_duration:.2f}s")
    logger.info(f"📈 Average time per stock: {total_duration/len(unique_stocks):.2f}s")
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"test_small_caps_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'total_stocks': len(unique_stocks),
            'successful': successful,
            'failed': failed,
            'total_gap_ups': total_gap_ups,
            'total_duration': total_duration,
            'results': results
        }, f, indent=2)
    
    logger.info(f"💾 Results saved to: {results_file}")
    logger.info("✅ Test small cap pre-population complete!")

if __name__ == "__main__":
    main() 