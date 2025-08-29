import requests
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta

API_KEY = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"

# Database setup
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_FILE = os.path.join(script_dir, 'trading_advisor.db')

def init_gap_table():
    """Initialize the gap_data table in the database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gap_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            yesterday_close REAL NOT NULL,
            today_open REAL NOT NULL,
            gap_percentage REAL NOT NULL,
            today_close REAL NOT NULL,
            today_high REAL NOT NULL,
            today_low REAL NOT NULL,
            volume_m REAL NOT NULL,
            highest_dollar_volume_m REAL NOT NULL,
            vwap REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, ticker)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_gap_data_to_db(gap_data_list):
    """Save gap data to the database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    for gap in gap_data_list:
        cursor.execute('''
            INSERT OR REPLACE INTO gap_data 
            (date, ticker, yesterday_close, today_open, gap_percentage, 
             today_close, today_high, today_low, volume_m, highest_dollar_volume_m, vwap)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            gap['date'],
            gap['ticker'],
            gap['yesterday_close'],
            gap['today_open'],
            gap['gap%'],
            gap['today_close'],
            gap['today_high'],
            gap['today_low'],
            gap['volume (M)'],
            gap['highest_dollar_volume (M)'],
            gap['vwap']
        ))
    
    conn.commit()
    conn.close()

def get_gap_data_from_db(start_date=None, end_date=None, ticker=None):
    """Retrieve gap data from the database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    query = "SELECT * FROM gap_data WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    
    if ticker:
        query += " AND ticker = ?"
        params.append(ticker)
    
    query += " ORDER BY date DESC, gap_percentage DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Convert to list of dictionaries
    columns = [description[0] for description in cursor.description]
    gap_data = []
    for row in rows:
        gap_data.append(dict(zip(columns, row)))
    
    conn.close()
    return gap_data

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
            vwap = stock.get("vw", None)  # Use .get() to safely handle missing VWAP data
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
                                "volume (M)": round(volume / 1000000, 2),
                                "highest_dollar_volume (M)": highest_dollar_volume,
                                "vwap": vwap
                            })

            # update prev_closes for tomorrow
            prev_closes[ticker] = close_price

        all_gappers.extend(gappers_today)
        
        # Save today's gap data to database
        if gappers_today:
            save_gap_data_to_db(gappers_today)
            print(f"💾 Saved {len(gappers_today)} gap records to database for {date_str}")
        
        cur += timedelta(days=1)

    return pd.DataFrame(all_gappers)
