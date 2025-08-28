#!/usr/bin/env python3
"""
Check what days of the week the dates fall on
"""

from datetime import datetime

dates = ["2025-08-25", "2025-08-26", "2025-08-27", "2025-08-28"]

for date_str in dates:
    dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt_obj.strftime("%A")
    is_weekend = dt_obj.weekday() >= 5
    
    print(f"📅 {date_str}: {day_name} {'(Weekend)' if is_weekend else '(Weekday)'}")
