import sys
import os
sys.path.append('.')

from get_gappers import get_grouped_bars, build_gap_dataset, init_gap_table, get_gap_data_from_db
from datetime import datetime, timedelta

# Initialize the database table
print("🔧 Initializing gap_data table...")
init_gap_table()
print("✅ Database table ready!")

df = build_gap_dataset("2024-01-01", "2024-01-31", gap_threshold=0.10)
df.to_csv("gappers.csv", index=False)

print("📊 Total gaps found:", len(df))
print("\n📅 Gaps by date:")
print(df['date'].value_counts().sort_index())

print("\n📋 First 10 gaps (all dates):")
print(df.head(10))

print("\n📋 Gaps for 2025-08-26:")
print(df[df['date'] == '2025-08-26'][['ticker', 'gap%', 'volume (M)']].head())

print("\n📋 Gaps for 2025-08-27:")
print(df[df['date'] == '2025-08-27'][['ticker', 'gap%', 'volume (M)']].head())

# Show all column names for reference
print("\n📋 Available columns:")
print(df.columns.tolist())

# Demonstrate querying from database
print("\n🗄️ Querying gap data from database:")
db_data = get_gap_data_from_db(start_date="2024-01-01", end_date="2024-01-31")
print(f"📊 Found {len(db_data)} gap records in database")

if db_data:
    print("\n📋 First 5 records from database:")
    for i, record in enumerate(db_data[:5]):
        print(f"{i+1}. {record['ticker']} - {record['date']} - Gap: {record['gap_percentage']}%")
