import os
import time
import csv
import math
import io
import traceback
import sqlite3
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Tuple

import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm

# ---------- CONFIG ----------
POLYGON_KEY = os.getenv("POLYGON_API_KEY", "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "marketdata")
DB_USER = os.getenv("DB_USER", "ts_user")
DB_PASS = os.getenv("DB_PASS", "ts_pass")

# concurrency & rate limits
MAX_WORKERS = 2                 # reduced for better memory management
SLEEP_BETWEEN_CALLS = 1.0       # increased to 1 second to avoid rate limits
MAX_RETRIES = 5                 # increased retries

# caching
PARQUET_CACHE_DIR = "./parquet_cache"
os.makedirs(PARQUET_CACHE_DIR, exist_ok=True)

# polygon endpoint template
AGGS_RANGE_URL = ("https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/"
                  "{from_iso}/{to_iso}?adjusted=true&sort=asc&limit=50000&apiKey={key}")

# ---------- DB UTIL ----------
def get_db_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS)

def check_existing_data_safe(ticker: str, date_str: str) -> bool:
    """Check if data exists for a specific ticker/date without memory issues"""
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM ohlcv_1m 
                    WHERE ticker = %s AND day = %s
                """, (ticker, date_str))
                count = cur.fetchone()[0]
                return count > 0
    except Exception as e:
        print(f"⚠️ Error checking existing data for {ticker} {date_str}: {e}")
        return False

# ---------- POLYGON FETCH ----------
def fetch_minute_bars_polygon(ticker: str, date_str: str) -> pd.DataFrame:
    """Fetch 1-min bars for one ticker/date. Returns empty DataFrame if no data or error."""
    # date_str expected 'YYYY-MM-DD'
    url = AGGS_RANGE_URL.format(ticker=ticker, from_iso=date_str, to_iso=date_str, key=POLYGON_KEY)
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                j = r.json()
                results = j.get("results", [])
                if not results:
                    return pd.DataFrame()  # no bars
                df = pd.DataFrame(results)
                # convert and normalize
                df = df.rename(columns={'t': 'ts_ms', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 'vw': 'vwap'})
                df['ts'] = pd.to_datetime(df['ts_ms'], unit='ms', utc=True)
                df['day'] = pd.to_datetime(date_str).date()
                # keep expected cols and add ticker
                df = df[['ts', 'open', 'high', 'low', 'close', 'volume']].copy()
                df['ticker'] = ticker
                df['vwap'] = None  # polygon returns vw in results only for some endpoints; keep null if missing
                df['day'] = pd.to_datetime(date_str).date()
                # Convert volume to integer to match database schema
                df['volume'] = df['volume'].astype(int)
                # reorder
                df = df[['ticker', 'ts', 'day', 'open', 'high', 'low', 'close', 'volume', 'vwap']]
                # optional: save parquet cache
                pq_path = f"{PARQUET_CACHE_DIR}/{ticker}_{date_str}.parquet"
                df.to_parquet(pq_path, index=False)
                time.sleep(SLEEP_BETWEEN_CALLS)
                return df
            else:
                # handle 429 rate limit etc
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", "60"))  # default to 60 seconds
                    print(f"⚠️ Rate limited for {ticker}, waiting {retry_after}s")
                    time.sleep(retry_after + 1.0)
                elif r.status_code == 403:
                    print(f"❌ API key doesn't have permissions for {ticker}")
                    return pd.DataFrame()
                else:
                    print(f"⚠️ API error {r.status_code} for {ticker}: {r.text[:100]}")
                    time.sleep(2.0 + attempt)
        except Exception as e:
            print(f"⚠️ Exception for {ticker}: {e}")
            time.sleep(2.0 + attempt)
    # after retries, return empty DataFrame
    return pd.DataFrame()

# ---------- INSERT BATCH ----------
def copy_dataframe_to_db(df: pd.DataFrame):
    """Insert DataFrame into ohlcv_1m using COPY from CSV in-memory for speed."""
    if df.empty:
        return 0
    # prepare CSV buffer
    buf = io.StringIO()
    # use CSV order matching table columns
    # (ticker, ts, day, open, high, low, close, volume, vwap, source)
    df_out = df.copy()
    df_out['source'] = 'polygon'
    # ensure ts in ISO and timezone-aware
    df_out['ts'] = df_out['ts'].dt.strftime('%Y-%m-%d %H:%M:%S%z')
    # vwap may be None -> cast to empty string
    df_out['vwap'] = df_out['vwap'].fillna('')
    # Ensure volume is integer for CSV output
    df_out['volume'] = df_out['volume'].astype(int)
    df_out.to_csv(buf, header=False, index=False, columns=['ticker','ts','day','open','high','low','close','volume','vwap','source'])
    buf.seek(0)

    sql = "COPY ohlcv_1m (ticker, ts, day, open, high, low, close, volume, vwap, source) FROM STDIN WITH (FORMAT CSV)"
    rows_inserted = 0
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.copy_expert(sql, buf)
                conn.commit()
                # ON CONFLICT DO NOTHING is not available with COPY; we rely on PRIMARY KEY uniqueness to error out.
            except Exception as e:
                # fallback: insert rows one-by-one with ON CONFLICT DO NOTHING in small batch
                conn.rollback()
                buf.seek(0)
                reader = csv.reader(buf)
                rows = [r for r in reader]
                with conn.cursor() as c2:
                    execute_values(
                        c2,
                        """
                        INSERT INTO ohlcv_1m (ticker, ts, day, open, high, low, close, volume, vwap, source)
                        VALUES %s
                        ON CONFLICT (ticker, ts) DO NOTHING
                        """,
                        rows,
                        page_size=1000
                    )
                    conn.commit()
    return rows_inserted

# ---------- WORKER ----------
def process_one(ticker: str, date_str: str):
    try:
        # Check if data already exists (safe way)
        if check_existing_data_safe(ticker, date_str):
            print(f"✅ Data already exists for {ticker} on {date_str}")
            return (ticker, date_str, "already_exists")
        
        # check parquet cache first
        pq_path = f"{PARQUET_CACHE_DIR}/{ticker}_{date_str}.parquet"
        if os.path.exists(pq_path):
            print(f"📁 Using cached data for {ticker}")
            df = pd.read_parquet(pq_path)
        else:
            print(f"🌐 Fetching data for {ticker}...")
            df = fetch_minute_bars_polygon(ticker, date_str)
        
        if df.empty:
            print(f"⚠️ No data for {ticker}")
            return (ticker, date_str, "no_data")
        
        print(f"💾 Inserting {len(df)} bars for {ticker}")
        # do DB insert
        copy_dataframe_to_db(df)
        return (ticker, date_str, "ok")
    except Exception as e:
        print(f"❌ Error processing {ticker}: {e}")
        traceback.print_exc()
        return (ticker, date_str, "error")

# ---------- ORCHESTRATOR ----------
def run_orchestrator(ticker_dates: List[Tuple[str, str]]):
    # dedupe list
    uniq = sorted(set(ticker_dates))
    print(f"Total tasks: {len(uniq)}")
    
    # Process in smaller batches to avoid memory issues
    batch_size = 100
    all_results = []
    
    for i in range(0, len(uniq), batch_size):
        batch = uniq[i:i + batch_size]
        print(f"\n🔄 Processing batch {i//batch_size + 1}/{(len(uniq) + batch_size - 1)//batch_size}")
        print(f"📦 Batch size: {len(batch)}")
        
        results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(process_one, t, d): (t,d) for t,d in batch}
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"Batch {i//batch_size + 1}"):
                t,d = futures[fut]
                try:
                    res = fut.result()
                    results.append(res)
                except Exception:
                    results.append((t,d,"error"))
        
        all_results.extend(results)
        
        # Small delay between batches to prevent memory buildup
        if i + batch_size < len(uniq):
            print("⏳ Waiting 2 seconds before next batch...")
            time.sleep(2)
    
    return all_results

# ---------- USAGE ----------
def get_ticker_dates_from_sqlite(from_date=None, to_date=None, limit=None):
    """Get ticker-date combinations directly from SQLite gap_data table"""
    # Path to your SQLite database
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sqlite_db = os.path.join(script_dir, 'trading_advisor.db')
    
    if not os.path.exists(sqlite_db):
        print(f"❌ SQLite database not found: {sqlite_db}")
        return []
    
    conn = sqlite3.connect(sqlite_db)
    cursor = conn.cursor()
    
    try:
        # Build the query with optional date filters
        query = """
        SELECT DISTINCT ticker, date 
        FROM gap_data 
        WHERE 1=1
        """
        
        params = []
        
        if from_date:
            query += " AND date >= ?"
            params.append(from_date)
        
        if to_date:
            query += " AND date <= ?"
            params.append(to_date)
        
        query += " ORDER BY date, ticker"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        ticker_dates = [(row[0], row[1]) for row in rows]
        
        print(f"📊 Found {len(ticker_dates)} ticker-date combinations from SQLite")
        if ticker_dates:
            print(f"📅 Date range: {min(row[1] for row in rows)} to {max(row[1] for row in rows)}")
            print(f"🎯 Unique tickers: {len(set(row[0] for row in rows))}")
        
        return ticker_dates
        
    except Exception as e:
        print(f"❌ Error reading from SQLite: {e}")
        return []
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ingest minute bars for gap tickers from SQLite to TimescaleDB (Memory-Optimized)')
    parser.add_argument('--from-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=25000, help='Limit number of ticker-date combinations')
    parser.add_argument('--cleanup-cache', action='store_true', help='Delete all parquet cache files after processing')
    parser.add_argument('--batch-size', type=int, default=100, help='Process data in batches of this size')
    
    args = parser.parse_args()
    
    print("🔍 GAP DATA INGESTION (MEMORY OPTIMIZED)")
    print("=" * 50)
    
    if args.from_date:
        print(f"📅 From date: {args.from_date}")
    if args.to_date:
        print(f"📅 To date: {args.to_date}")
    print(f"📦 Limit: {args.limit}")
    print(f"🔄 Batch size: {args.batch_size}")
    
    # Get ticker-dates directly from SQLite with date range filtering
    ticker_dates = get_ticker_dates_from_sqlite(
        from_date=args.from_date, 
        to_date=args.to_date, 
        limit=args.limit
    )
    
    if not ticker_dates:
        print("❌ No ticker-dates found. Please run test1.py first to populate gap_data table.")
        exit(1)
    
    print(f"\n🧪 Processing {len(ticker_dates)} ticker-date combinations:")
    for i, (ticker, date) in enumerate(ticker_dates[:10], 1):  # Show first 10
        print(f"  {i}. {ticker} on {date}")
    if len(ticker_dates) > 10:
        print(f"  ... and {len(ticker_dates) - 10} more")
    
    # Run orchestrator
    print(f"\n🚀 Starting ingestion...")
    res = run_orchestrator(ticker_dates)
    
    # Summary
    summary = {r[2]: sum(1 for x in res if x[2]==r[2]) for r in res}
    print(f"\n📊 Summary: {summary}")
    
    if summary.get('ok', 0) > 0:
        print(f"✅ Successfully ingested {summary['ok']} ticker-date combinations!")
    if summary.get('already_exists', 0) > 0:
        print(f"ℹ️ Data already existed for {summary['already_exists']} combinations")
    if summary.get('no_data', 0) > 0:
        print(f"⚠️ No data available for {summary['no_data']} combinations")
    if summary.get('error', 0) > 0:
        print(f"❌ Errors occurred for {summary['error']} combinations")
    
    # Cleanup cache if requested
    if args.cleanup_cache:
        import glob
        cache_files = glob.glob(f"{PARQUET_CACHE_DIR}/*.parquet")
        if cache_files:
            for file in cache_files:
                os.remove(file)
            print(f"🧹 Cleaned up {len(cache_files)} parquet cache files")
        else:
            print("🧹 No parquet cache files to clean up")
