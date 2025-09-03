# Gap Data to TimescaleDB Complete Workflow

## Overview

This guide explains how to fetch gap trading data and ingest it into TimescaleDB for backtesting and analysis. The workflow consists of two main steps:

1. **Fetch Gap Data**: Run `test1.py` to populate the `gap_data` table in SQLite
2. **Ingest Market Data**: Run `ingest_min_bars_for_gappers_fixed.py` to fetch 1-minute bars and store in TimescaleDB

## Prerequisites

### Required Software
- Python 3.7+
- PostgreSQL with TimescaleDB extension
- Access to Polygon.io API
- SQLite database (`trading_advisor.db`)

### Required Python Packages
```bash
cd gap-trade-bot/backend/backtest/timescaledb
pip install -r requirements.txt
```

### Environment Variables
Set these environment variables or they will use defaults:

```bash
export POLYGON_API_KEY="your_polygon_api_key"
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="marketdata"
export DB_USER="ts_user"
export DB_PASS="ts_pass"
```

## Complete Workflow

### Step 1: Fetch Gap Data (Populate gap_data table)

Navigate to the backtest directory and run the gap detection script:

```bash
cd gap-trade-bot/backend/backtest

# Initialize database and fetch gap data for a date range
python test1.py
```

**What this does:**
- Creates/initializes the `gap_data` table in SQLite
- Fetches daily market data from Polygon.io for the specified date range
- Calculates gap percentages (default: 10% threshold)
- Saves gap data to the `gap_data` table
- Exports results to `gappers.csv`

**Customizing the date range:**
Edit `test1.py` line 13 to change the date range:
```python
# Change these dates to your desired range
df = build_gap_dataset("2024-01-01", "2024-01-31", gap_threshold=0.10)
```

**Example date ranges:**
```python
# Last week
df = build_gap_dataset("2024-01-22", "2024-01-26", gap_threshold=0.10)

# Last month
df = build_gap_dataset("2023-12-01", "2023-12-31", gap_threshold=0.10)

# Specific period
df = build_gap_dataset("2024-01-15", "2024-01-19", gap_threshold=0.10)
```

### Step 2: Ingest Market Data (Populate ohlcv_1m table)

Navigate to the TimescaleDB directory and run the ingestion script:

```bash
cd gap-trade-bot/backend/backtest/timescaledb

# Ingest all available gap data
python ingest_min_bars_for_gappers_fixed.py

# Or specify a date range
python ingest_min_bars_for_gappers_fixed.py --from-date 2024-01-01 --to-date 2024-01-31

# Limit the number of ticker-date combinations
python ingest_min_bars_for_gappers_fixed.py --limit 1000

# Clean up cache files after processing
python ingest_min_bars_for_gappers_fixed.py --cleanup-cache
```

**What this does:**
- Queries the `gap_data` table for ticker-date combinations
- Fetches 1-minute OHLCV bars from Polygon.io for each combination
- Stores the data in TimescaleDB `ohlcv_1m` table
- Implements caching to avoid redundant API calls
- Handles rate limits and retries automatically

## Daily/Periodic Workflow

### When You Login Every Few Days

Run this sequence to catch up on missed data:

```bash
# 1. Navigate to backtest directory
cd gap-trade-bot/backend/backtest

# 2. Check what dates you have data for
python -c "
import sqlite3
import os
script_dir = os.path.dirname(os.path.dirname(os.path.abspath('.')))
db_path = os.path.join(script_dir, 'trading_advisor.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT DISTINCT date FROM gap_data ORDER BY date DESC LIMIT 10')
dates = cursor.fetchall()
print('Available dates in gap_data:')
for date in dates:
    print(f'  {date[0]}')
conn.close()
"

# 3. Determine your date range (e.g., last 7 days)
# Edit test1.py with your desired date range

# 4. Fetch gap data
python test1.py

# 5. Ingest market data into TimescaleDB
cd timescaledb
python ingest_min_bars_for_gappers_fixed.py --from-date 2025-08-28 --to-date 2025-09-02
```

## Data Verification Queries

### Verify Gap Data in SQLite

```bash
cd gap-trade-bot/backend/backtest

# Check total records
python -c "
import sqlite3
import os
script_dir = os.path.dirname(os.path.dirname(os.path.abspath('.')))
db_path = os.path.join(script_dir, 'trading_advisor.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM gap_data')
total = cursor.fetchone()[0]
print(f'Total gap records: {total}')
conn.close()
"

# Check data by date
python -c "
import sqlite3
import os
script_dir = os.path.dirname(os.path.dirname(os.path.abspath('.')))
db_path = os.path.join(script_dir, 'trading_advisor.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('''
    SELECT date, COUNT(*) as count, 
           AVG(gap_percentage) as avg_gap,
           COUNT(CASE WHEN gap_percentage >= 25 THEN 1 END) as major_gaps
    FROM gap_data 
    GROUP BY date 
    ORDER BY date DESC 
    LIMIT 10
''')
results = cursor.fetchall()
print('Gap data summary by date:')
for row in results:
    print(f'  {row[0]}: {row[1]} gaps, avg: {row[2]:.1f}%, major: {row[3]}')
conn.close()
"

# Check specific ticker
python -c "
import sqlite3
import os
script_dir = os.path.dirname(os.path.dirname(os.path.abspath('.')))
db_path = os.path.join(script_dir, 'trading_advisor.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('''
    SELECT date, ticker, gap_percentage, volume_m, today_high, today_low
    FROM gap_data 
    WHERE ticker = 'AAPL'
    ORDER BY date DESC 
    LIMIT 5
''')
results = cursor.fetchall()
print('AAPL gap data:')
for row in results:
    print(f'  {row[0]}: Gap {row[2]:.1f}%, Vol {row[3]}M, H:{row[4]} L:{row[5]}')
conn.close()
"
```

### Verify Market Data in TimescaleDB

```sql
-- Connect to your TimescaleDB
psql -h localhost -U ts_user -d marketdata

-- Check total records
SELECT COUNT(*) as total_bars FROM ohlcv_1m;

-- Check data by date
SELECT 
    day,
    COUNT(*) as bars,
    COUNT(DISTINCT ticker) as tickers,
    MIN(ts) as earliest_time,
    MAX(ts) as latest_time
FROM ohlcv_1m 
GROUP BY day 
ORDER BY day DESC 
LIMIT 10;

-- Check specific ticker
SELECT 
    day,
    COUNT(*) as bars,
    MIN(ts) as first_bar,
    MAX(ts) as last_bar,
    AVG(volume) as avg_volume
FROM ohlcv_1m 
WHERE ticker = 'AAPL'
GROUP BY day 
ORDER BY day DESC 
LIMIT 5;

-- Check data completeness for a specific date
SELECT 
    ticker,
    COUNT(*) as bars,
    CASE 
        WHEN COUNT(*) >= 390 THEN 'Complete'
        WHEN COUNT(*) >= 300 THEN 'Partial'
        ELSE 'Incomplete'
    END as status
FROM ohlcv_1m 
WHERE day = '2024-01-26'
GROUP BY ticker 
ORDER BY bars DESC 
LIMIT 10;

-- Check for missing data
SELECT 
    g.ticker,
    g.date,
    COUNT(o.ts) as bars_found,
    CASE 
        WHEN COUNT(o.ts) = 0 THEN 'Missing'
        WHEN COUNT(o.ts) < 390 THEN 'Partial'
        ELSE 'Complete'
    END as status
FROM gap_data g
LEFT JOIN ohlcv_1m o ON g.ticker = o.ticker AND g.date = o.day::text
WHERE g.date = '2024-01-26'
GROUP BY g.ticker, g.date
ORDER BY bars_found ASC;
```

## Troubleshooting

### Common Issues and Solutions

#### 1. No Gap Data Found
```bash
# Check if gap_data table exists and has data
python -c "
import sqlite3
import os
script_dir = os.path.dirname(os.path.dirname(os.path.abspath('.')))
db_path = os.path.join(script_dir, 'trading_advisor.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')
tables = cursor.fetchall()
print('Available tables:', [t[0] for t in tables])
if 'gap_data' in [t[0] for t in tables]:
    cursor.execute('SELECT COUNT(*) FROM gap_data')
    count = cursor.fetchone()[0]
    print(f'gap_data table has {count} records')
conn.close()
"
```

#### 2. TimescaleDB Connection Issues
```bash
# Test database connection
python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        dbname='marketdata',
        user='ts_user',
        password='ts_pass'
    )
    print('✅ TimescaleDB connection successful')
    conn.close()
except Exception as e:
    print(f'❌ TimescaleDB connection failed: {e}')
"
```

#### 3. API Rate Limiting
```bash
# Check Polygon API key
python -c "
import os
key = os.getenv('POLYGON_API_KEY', '5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT')
print(f'Using API key: {key[:10]}...')
"
```

## Performance Optimization

### For Large Date Ranges

```bash
# Process in smaller chunks to avoid memory issues
python ingest_min_bars_for_gappers_fixed.py --from-date 2024-01-01 --to-date 2024-01-07 --limit 5000
python ingest_min_bars_for_gappers_fixed.py --from-date 2024-01-08 --to-date 2024-01-14 --limit 5000
python ingest_min_bars_for_gappers_fixed.py --from-date 2024-01-15 --to-date 2024-01-21 --limit 5000
```

### Monitor Progress

```bash
# Check progress during ingestion
watch -n 5 'psql -h localhost -U ts_user -d marketdata -c "SELECT COUNT(*) FROM ohlcv_1m;"'
```

## Summary

**Complete workflow every few days:**

1. **Fetch gap data**: `cd backtest && python test1.py`
2. **Ingest market data**: `cd timescaledb && python ingest_min_bars_for_gappers_fixed.py`
3. **Verify data**: Use the SQL queries above to check both databases
4. **Clean up**: `python ingest_min_bars_for_gappers_fixed.py --cleanup-cache`

**Expected results:**
- `gap_data` table: Daily gap trading opportunities
- `ohlcv_1m` table: 1-minute bars for all gap tickers
- Data ready for backtesting with `orb_tester.py`

This workflow ensures you have complete gap trading data for analysis and backtesting, even when running the system intermittently.
