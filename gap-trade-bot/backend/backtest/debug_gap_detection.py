#!/usr/bin/env python3
"""
Debug script to see what gaps are being detected for each date
"""

import sys
import os
sys.path.append('.')

from get_gappers import get_grouped_bars
from datetime import datetime, timedelta

def debug_gap_detection():
    """Debug the gap detection process"""
    
    start_date = "2025-08-25"
    end_date = "2025-08-28"
    gap_threshold = 0.10
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Data store: {ticker: last_close}
    prev_closes = {}
    all_gappers = []

    cur = start
    while cur <= end:
        date_str = cur.strftime("%Y-%m-%d")
        print(f"\n🔍 Processing {date_str} ...")
        print(f"📊 Previous closes available: {len(prev_closes)} tickers")

        daily_data = get_grouped_bars(date_str)
        print(f"📊 Daily data retrieved: {len(daily_data)} stocks")
        
        gappers_today = []
        gap_candidates = 0
        volume_filtered = 0
        threshold_filtered = 0

        for stock in daily_data:
            ticker = stock["T"]
            open_price = stock["o"]
            close_price = stock["c"]
            high_price = stock["h"]
            low_price = stock["l"]
            volume = stock["v"]
            highest_dollar_volume = round((volume * high_price) / 1000000, 2)

            # if we saw this ticker yesterday, compute gap
            if ticker in prev_closes:
                y_close = prev_closes[ticker]
                if y_close > 0:
                    gap_pct = (open_price - y_close) / y_close
                    gap_candidates += 1
                    
                    if gap_pct >= gap_threshold:
                        if volume > 5000000:
                            gappers_today.append({
                                "date": date_str,
                                "ticker": ticker,
                                "yesterday_close": y_close,
                                "today_open": open_price,
                                "gap_pct": gap_pct,
                                "today_close": close_price,
                                "today_high": high_price,
                                "today_low": low_price,
                                "volume": volume,
                                "highest_dollar_volume (M)": highest_dollar_volume
                            })
                        else:
                            volume_filtered += 1
                    else:
                        threshold_filtered += 1

            # update prev_closes for tomorrow
            prev_closes[ticker] = close_price

        print(f"📊 Gap candidates: {gap_candidates}")
        print(f"📊 Below threshold: {threshold_filtered}")
        print(f"📊 Below volume: {volume_filtered}")
        print(f"📊 Final gaps found: {len(gappers_today)}")
        
        if len(gappers_today) > 0:
            print(f"📋 Gaps for {date_str}:")
            for gap in gappers_today:
                print(f"   {gap['ticker']}: {gap['gap_pct']:.2%} gap, Volume: {gap['volume']:,}, Dollar Vol: ${gap['highest_dollar_volume (M)']}M")
        else:
            print(f"❌ No gaps found for {date_str}")

        all_gappers.extend(gappers_today)
        cur += timedelta(days=1)

    print(f"\n📊 TOTAL GAPS FOUND: {len(all_gappers)}")
    
    # Group by date
    from collections import defaultdict
    gaps_by_date = defaultdict(list)
    for gap in all_gappers:
        gaps_by_date[gap['date']].append(gap)
    
    for date, gaps in gaps_by_date.items():
        print(f"📅 {date}: {len(gaps)} gaps")
        for gap in gaps:
            print(f"   {gap['ticker']}: {gap['gap_pct']:.2%} gap")

if __name__ == "__main__":
    debug_gap_detection()
