import sys
import os
sys.path.append('.')

from get_gappers import get_grouped_bars, build_gap_dataset
from datetime import datetime, timedelta

df = build_gap_dataset("2025-08-22", "2025-08-28", gap_threshold=0.10)
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
