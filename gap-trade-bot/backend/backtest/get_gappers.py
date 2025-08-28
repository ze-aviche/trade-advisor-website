import requests
import pandas as pd
from datetime import datetime, timedelta

API_KEY = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"

def get_grouped_bars(date: str):
    """Fetch grouped OHLCV for all tickers on a given date"""
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true&apiKey=5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"
    
    res = requests.get(url).json()
    return res.get("results", [])

def build_gap_dataset(start_date: str, end_date: str, gap_threshold=0.10):
    """Build daily gapper dataset between start_date and end_date"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Data store: {ticker: last_close}
    prev_closes = {}
    all_gappers = []

    cur = start
    while cur <= end:
        date_str = cur.strftime("%Y-%m-%d")
        print(f"Processing {date_str} ...")

        daily_data = get_grouped_bars(date_str)
        gappers_today = []

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
                    if gap_pct >= gap_threshold:
                        if volume > 5000000:
                            gappers_today.append({
                                "date": date_str,
                                "ticker": ticker,
                                "yesterday_close": y_close,
                                "today_open": open_price,
                                "gap%": round(gap_pct*100, 2),
                                "today_close": close_price,
                                "today_high": high_price,
                                "today_low": low_price,
                                "volume (M)": volume / 1000000,
                                "highest_dollar_volume (M)": highest_dollar_volume
                            })

            # update prev_closes for tomorrow
            prev_closes[ticker] = close_price

        all_gappers.extend(gappers_today)
        cur += timedelta(days=1)

    return pd.DataFrame(all_gappers)
