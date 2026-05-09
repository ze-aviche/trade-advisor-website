#!/usr/bin/env python3
import sqlite3, json, os, sys
backend = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend)
os.chdir(backend)

db = os.path.join(backend, 'trading_advisor.db')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT data_json FROM historical_data_cache WHERE ticker='HWH' AND date='2025-12-19'")
row = cur.fetchone()
if row:
    d = json.loads(row['data_json'])
    print("Stored data for HWH 2025-12-19:")
    for k, v in d.items():
        print(f"  {k}: {repr(v)}")
else:
    print("No record found for HWH 2025-12-19")

# Also check what all HWH records look like for premarket open
print()
print("All HWH records - premarket open values:")
cur.execute("SELECT date, data_json FROM historical_data_cache WHERE ticker='HWH' ORDER BY date")
for r in cur.fetchall():
    d = json.loads(r['data_json'])
    print(f"  {r['date']}: premarket open={repr(d.get('premarket open'))}, gap={d.get('gap up % at open')}%")
conn.close()
