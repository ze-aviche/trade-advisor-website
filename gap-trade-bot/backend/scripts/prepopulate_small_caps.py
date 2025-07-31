#!/usr/bin/env python3
"""
Pre-populate database with small cap stocks (market cap < $500M) gap-up data.
This script fetches historical data for small cap stocks and stores it in the cache
to make future queries much faster.
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_data import get_historical_gap_up_data, get_polygon_client
from historical_cache import historical_cache
from logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Small cap stocks with market cap < $500M
SMALL_CAP_STOCKS = [
    # Technology
    'WINT', 'HOLO', 'FTFT', 'SONN', 'XBP', 'LIDR', 'MULN', 'SNDL', 'HEXO', 'TLRY',
    'ACB', 'CGC', 'APHA', 'CRON', 'AUR', 'LAZR', 'VLDR', 'QS', 'NKLA', 'WKHS',
    'IDEX', 'SOLO', 'RIDE', 'GOEV', 'NIO', 'XPEV', 'LI', 'TSLA', 'RIVN', 'LCID',
    
    # Biotech/Healthcare
    'BNGO', 'OCGN', 'INO', 'VXRT', 'MRNA', 'BNTX', 'NVAX', 'SAVA', 'CTXR', 'ATOS',
    'ZOM', 'CIDM', 'SENS', 'GNUS', 'MARK', 'SHIP', 'TOPS', 'NAKD', 'CTRM', 'ZOM',
    
    # Energy/Materials
    'CEI', 'WISH', 'CLOV', 'WISH', 'SENS', 'ZOM', 'GNUS', 'MARK', 'SHIP', 'TOPS',
    'NAKD', 'CTRM', 'IDEX', 'SOLO', 'RIDE', 'GOEV', 'WKHS', 'NKLA', 'QS', 'VLDR',
    
    # Finance/Real Estate
    'UWMC', 'RKT', 'COIN', 'HOOD', 'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL',
    
    # Retail/Consumer
    'GME', 'AMC', 'BBBY', 'BB', 'NOK', 'KOSS', 'EXPR', 'NAKD', 'SNDL', 'HEXO',
    
    # Additional Small Caps
    'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CLSK', 'ARBK', 'CIFR', 'BTBT', 'WULF',
    'HIVE', 'CAN', 'APHA', 'CRON', 'TLRY', 'HEXO', 'ACB', 'CGC', 'SNDL', 'OGI',
    'JUSHF', 'TCNNF', 'GTBIF', 'MMNFF', 'TWMJF', 'CURLF', 'VRNOF', 'KSHB', 'CBWTF',
    'LBUY', 'LDSR', 'LDSR', 'LDSR', 'LDSR', 'LDSR', 'LDSR', 'LDSR', 'LDSR', 'LDSR'
]

def get_market_cap(ticker):
    """Get market cap for a ticker using Polygon API."""
    try:
        polygon_client = get_polygon_client()
        
        # Get company info
        company_info = polygon_client.get_ticker_details(ticker)
        if company_info and hasattr(company_info, 'market_cap'):
            return company_info.market_cap
        return None
    except Exception as e:
        logger.warning(f"Could not get market cap for {ticker}: {e}")
        return None

def filter_small_caps(stocks, max_market_cap=500_000_000):
    """Filter stocks to only include those with market cap < $500M."""
    small_caps = []
    
    logger.info(f"🔍 Filtering {len(stocks)} stocks for market cap < ${max_market_cap:,}")
    
    for ticker in stocks:
        market_cap = get_market_cap(ticker)
        if market_cap and market_cap < max_market_cap:
            small_caps.append(ticker)
            logger.info(f"✅ {ticker}: ${market_cap:,} (small cap)")
        elif market_cap:
            logger.info(f"❌ {ticker}: ${market_cap:,} (too large)")
        else:
            logger.info(f"⚠️ {ticker}: Market cap unknown")
    
    logger.info(f"📊 Found {len(small_caps)} small cap stocks out of {len(stocks)}")
    return small_caps

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
    """Main function to pre-populate small cap stocks."""
    logger.info("🚀 Starting small cap stock pre-population...")
    
    # Clear existing cache
    logger.info("🗑️ Clearing existing cache...")
    historical_cache.clear_cache()
    
    # Filter for small caps
    small_caps = filter_small_caps(SMALL_CAP_STOCKS)
    
    if not small_caps:
        logger.error("❌ No small cap stocks found!")
        return
    
    logger.info(f"📊 Processing {len(small_caps)} small cap stocks...")
    
    # Process stocks in parallel
    results = []
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all tasks
        future_to_ticker = {
            executor.submit(process_stock, ticker): ticker 
            for ticker in small_caps
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
                logger.info(f"📈 Progress: {completed}/{len(small_caps)} ({completed/len(small_caps)*100:.1f}%)")
                
            except Exception as e:
                logger.error(f"❌ Error processing {ticker}: {e}")
                failed += 1
    
    # Summary
    total_duration = sum(r['duration'] for r in results)
    total_gap_ups = sum(r['gap_up_days'] for r in results if r['success'])
    
    logger.info("🎯 Pre-population Summary:")
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Total gap-up days cached: {total_gap_ups}")
    logger.info(f"⏱️ Total processing time: {total_duration:.2f}s")
    logger.info(f"📈 Average time per stock: {total_duration/len(small_caps):.2f}s")
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"prepopulate_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'total_stocks': len(small_caps),
            'successful': successful,
            'failed': failed,
            'total_gap_ups': total_gap_ups,
            'total_duration': total_duration,
            'results': results
        }, f, indent=2)
    
    logger.info(f"💾 Results saved to: {results_file}")
    logger.info("✅ Small cap pre-population complete!")

if __name__ == "__main__":
    main() 