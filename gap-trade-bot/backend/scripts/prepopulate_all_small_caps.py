#!/usr/bin/env python3
"""
Pre-populate database with ALL stocks under $1B market cap.
This script fetches historical data for a comprehensive list of small cap stocks
and stores it in the cache to make future queries much faster.
"""

import os
import sys
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from historical_data import get_historical_gap_up_data, get_polygon_client
from historical_cache import historical_cache
from logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Comprehensive list of stocks under $1B market cap
ALL_SMALL_CAPS = [
    # High Volume Small Caps
    'WINT', 'HOLO', 'FTFT', 'SONN', 'XBP', 'LIDR', 'MULN', 'SNDL', 'HEXO', 'TLRY',
    'ACB', 'CGC', 'APHA', 'CRON', 'AUR', 'LAZR', 'VLDR', 'QS', 'NKLA', 'WKHS',
    'IDEX', 'SOLO', 'RIDE', 'GOEV', 'NIO', 'XPEV', 'LI', 'RIVN', 'LCID',
    
    # Biotech/Healthcare
    'BNGO', 'OCGN', 'INO', 'VXRT', 'MRNA', 'BNTX', 'NVAX', 'SAVA', 'CTXR', 'ATOS',
    'ZOM', 'CIDM', 'SENS', 'GNUS', 'MARK', 'SHIP', 'TOPS', 'NAKD', 'CTRM',
    
    # Crypto/Mining
    'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CLSK', 'ARBK', 'CIFR', 'BTBT', 'WULF',
    'HIVE', 'CAN', 'COIN', 'HOOD', 'SQ', 'PYPL',
    
    # Meme/Retail
    'GME', 'AMC', 'BBBY', 'BB', 'NOK', 'KOSS', 'EXPR',
    
    # Finance/Tech
    'UWMC', 'RKT', 'SOFI', 'LC', 'UPST', 'AFRM',
    
    # Additional Small Caps
    'AAL', 'UAL', 'DAL', 'JBLU', 'SAVE', 'ALK', 'HA', 'SKYW', 'SNCY', 'ULCC',
    'JETS', 'XLE', 'XOP', 'USO', 'BNO', 'UGA', 'UNG', 'SLV', 'GLD', 'GDX',
    'GDXJ', 'JNUG', 'JDST', 'NUGT', 'DUST', 'LABU', 'LABD', 'TQQQ', 'SQQQ',
    'SPXL', 'SPXS', 'TMF', 'TMV', 'TLT', 'TBT', 'UUP', 'UDN', 'FXY', 'FXE',
    'FXC', 'FXB', 'FXF', 'FXA', 'FXY', 'FXE', 'FXC', 'FXB', 'FXF', 'FXA',
    
    # Penny Stocks
    'CEI', 'WISH', 'CLOV', 'SENS', 'ZOM', 'GNUS', 'MARK', 'SHIP', 'TOPS', 'NAKD',
    'CTRM', 'IDEX', 'SOLO', 'RIDE', 'GOEV', 'WKHS', 'NKLA', 'QS', 'VLDR', 'LAZR',
    'AUR', 'CRON', 'APHA', 'CGC', 'HEXO', 'SNDL', 'TLRY', 'ACB', 'MULN', 'LIDR',
    'XBP', 'SONN', 'FTFT', 'HOLO', 'WINT', 'BNGO', 'OCGN', 'INO', 'VXRT', 'MRNA',
    'BNTX', 'NVAX', 'SAVA', 'CTXR', 'ATOS', 'ZOM', 'CIDM', 'SENS', 'GNUS', 'MARK',
    'SHIP', 'TOPS', 'NAKD', 'CTRM', 'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CLSK',
    'ARBK', 'CIFR', 'BTBT', 'WULF', 'HIVE', 'CAN', 'GME', 'AMC', 'BBBY', 'BB',
    'NOK', 'KOSS', 'EXPR', 'UWMC', 'RKT', 'COIN', 'HOOD', 'SOFI', 'LC', 'UPST',
    'AFRM', 'SQ', 'PYPL',
    
    # Additional Small Caps
    'PLTR', 'RBLX', 'HOOD', 'COIN', 'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL',
    'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CLSK', 'ARBK', 'CIFR', 'BTBT', 'WULF',
    'HIVE', 'CAN', 'GME', 'AMC', 'BBBY', 'BB', 'NOK', 'KOSS', 'EXPR', 'UWMC',
    'RKT', 'COIN', 'HOOD', 'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL',
    
    # More Small Caps
    'SNAP', 'PINS', 'TWTR', 'UBER', 'LYFT', 'DASH', 'ABNB', 'RBLX', 'PLTR', 'HOOD',
    'COIN', 'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL', 'MSTR', 'RIOT', 'MARA',
    'HUT', 'BITF', 'CLSK', 'ARBK', 'CIFR', 'BTBT', 'WULF', 'HIVE', 'CAN', 'GME',
    'AMC', 'BBBY', 'BB', 'NOK', 'KOSS', 'EXPR', 'UWMC', 'RKT', 'COIN', 'HOOD',
    'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL',
    
    # Additional Penny Stocks
    'CEI', 'WISH', 'CLOV', 'SENS', 'ZOM', 'GNUS', 'MARK', 'SHIP', 'TOPS', 'NAKD',
    'CTRM', 'IDEX', 'SOLO', 'RIDE', 'GOEV', 'WKHS', 'NKLA', 'QS', 'VLDR', 'LAZR',
    'AUR', 'CRON', 'APHA', 'CGC', 'HEXO', 'SNDL', 'TLRY', 'ACB', 'MULN', 'LIDR',
    'XBP', 'SONN', 'FTFT', 'HOLO', 'WINT', 'BNGO', 'OCGN', 'INO', 'VXRT', 'MRNA',
    'BNTX', 'NVAX', 'SAVA', 'CTXR', 'ATOS', 'ZOM', 'CIDM', 'SENS', 'GNUS', 'MARK',
    'SHIP', 'TOPS', 'NAKD', 'CTRM', 'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CLSK',
    'ARBK', 'CIFR', 'BTBT', 'WULF', 'HIVE', 'CAN', 'GME', 'AMC', 'BBBY', 'BB',
    'NOK', 'KOSS', 'EXPR', 'UWMC', 'RKT', 'COIN', 'HOOD', 'SOFI', 'LC', 'UPST',
    'AFRM', 'SQ', 'PYPL',
    
    # More Comprehensive List
    'SNAP', 'PINS', 'TWTR', 'UBER', 'LYFT', 'DASH', 'ABNB', 'RBLX', 'PLTR', 'HOOD',
    'COIN', 'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL', 'MSTR', 'RIOT', 'MARA',
    'HUT', 'BITF', 'CLSK', 'ARBK', 'CIFR', 'BTBT', 'WULF', 'HIVE', 'CAN', 'GME',
    'AMC', 'BBBY', 'BB', 'NOK', 'KOSS', 'EXPR', 'UWMC', 'RKT', 'COIN', 'HOOD',
    'SOFI', 'LC', 'UPST', 'AFRM', 'SQ', 'PYPL', 'SNAP', 'PINS', 'TWTR', 'UBER',
    'LYFT', 'DASH', 'ABNB', 'RBLX', 'PLTR', 'HOOD', 'COIN', 'SOFI', 'LC', 'UPST',
    'AFRM', 'SQ', 'PYPL', 'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CLSK', 'ARBK',
    'CIFR', 'BTBT', 'WULF', 'HIVE', 'CAN', 'GME', 'AMC', 'BBBY', 'BB', 'NOK',
    'KOSS', 'EXPR', 'UWMC', 'RKT', 'COIN', 'HOOD', 'SOFI', 'LC', 'UPST', 'AFRM',
    'SQ', 'PYPL'
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

def filter_small_caps(stocks, max_market_cap=1_000_000_000):
    """Filter stocks to only include those with market cap < $1B."""
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
    """Main function to pre-populate all small cap stocks."""
    logger.info("🚀 Starting comprehensive small cap stock pre-population...")
    
    # Remove duplicates and get unique list
    unique_stocks = list(set(ALL_SMALL_CAPS))
    logger.info(f"📊 Processing {len(unique_stocks)} unique stocks...")
    
    # Filter for small caps (optional - can be skipped for speed)
    # small_caps = filter_small_caps(unique_stocks)
    small_caps = unique_stocks  # Skip filtering for now to process all
    
    if not small_caps:
        logger.error("❌ No small cap stocks found!")
        return
    
    logger.info(f"📊 Processing {len(small_caps)} stocks...")
    
    # Clear existing cache
    logger.info("🗑️ Clearing existing cache...")
    historical_cache.clear_cache()
    
    # Process stocks in parallel
    results = []
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:  # Increased workers
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
    
    logger.info("🎯 Comprehensive Pre-population Summary:")
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Total gap-up days cached: {total_gap_ups}")
    logger.info(f"⏱️ Total processing time: {total_duration:.2f}s")
    logger.info(f"📈 Average time per stock: {total_duration/len(small_caps):.2f}s")
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"comprehensive_small_caps_results_{timestamp}.json"
    
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
    logger.info("✅ Comprehensive small cap pre-population complete!")

if __name__ == "__main__":
    main() 