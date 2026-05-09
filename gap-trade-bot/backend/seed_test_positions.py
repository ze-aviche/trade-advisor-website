#!/usr/bin/env python3
"""
Seed the local SQLite DB with test positions for UI testing.

Run AFTER the Flask app has started at least once (so the DB and tables exist),
then reload the browser.

Usage:
    python seed_test_positions.py           # seed mixed day + swing positions
    python seed_test_positions.py --clear   # wipe positions table first
"""

import sys
import sqlite3
import os
from datetime import datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.environ.get('DATABASE_PATH', os.path.join(script_dir, 'trading_advisor.db'))

CLEAR = '--clear' in sys.argv

def seed():
    if not os.path.exists(DB_FILE):
        print(f'DB not found at {DB_FILE}')
        print('Start the Flask app once first so it creates the database.')
        sys.exit(1)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if CLEAR:
        c.execute('DELETE FROM positions')
        print('Cleared existing positions.')

    today = datetime.now().date()
    five_days_ago = (today - timedelta(days=5)).isoformat()
    today_str = today.isoformat()

    # ── Test positions ────────────────────────────────────────────────────────
    # symbol, type(1=LONG via DAS type 2, tracked as 2), qty, avg_cost,
    # realized, create_time, date, position_type, entry_date, swing_stop_loss,
    # swing_target, swing_entry_reason, max_hold_days
    test_positions = [
        {
            'symbol':             'NVDA',
            'type':               2,           # DAS type 2 = LONG
            'quantity':           100,
            'avg_cost':           480.00,
            'init_quantity':      100,
            'init_price':         480.00,
            'realized':           0.0,
            'create_time':        '09:31:00',
            'date':               today_str,
            'unrealized':         -50.0,        # slightly down
            'position_type':      'day',
            'entry_date':         today_str,
            'swing_stop_loss':    None,
            'swing_target':       None,
            'swing_entry_reason': None,
            'max_hold_days':      None,
        },
        {
            'symbol':             'AAPL',
            'type':               2,
            'quantity':           50,
            'avg_cost':           175.00,
            'init_quantity':      50,
            'init_price':         175.00,
            'realized':           0.0,
            'create_time':        '09:35:00',
            'date':               five_days_ago,  # entered 5 days ago (swing)
            'unrealized':         250.0,           # up $5/share
            'position_type':      'swing',
            'entry_date':         five_days_ago,
            'swing_stop_loss':    round(175.00 * 0.93, 2),   # 7% stop
            'swing_target':       round(175.00 * 1.15, 2),   # 15% target
            'swing_entry_reason': 'bull_flag_breakout',
            'max_hold_days':      20,
        },
        {
            'symbol':             'MSFT',
            'type':               3,           # SHORT
            'quantity':           30,
            'avg_cost':           415.00,
            'init_quantity':      30,
            'init_price':         415.00,
            'realized':           0.0,
            'create_time':        '09:45:00',
            'date':               (today - timedelta(days=2)).isoformat(),
            'unrealized':         90.0,
            'position_type':      'swing',
            'entry_date':         (today - timedelta(days=2)).isoformat(),
            'swing_stop_loss':    round(415.00 * 1.07, 2),
            'swing_target':       round(415.00 * 0.85, 2),
            'swing_entry_reason': 'resistance_rejection',
            'max_hold_days':      15,
        },
    ]

    inserted = 0
    skipped = 0
    for p in test_positions:
        c.execute('SELECT id FROM positions WHERE symbol=? AND type=?', (p['symbol'], p['type']))
        if c.fetchone():
            skipped += 1
            print(f'  Skip  {p["symbol"]} (already exists)')
            continue

        c.execute('''
            INSERT INTO positions (
                symbol, type, quantity, avg_cost, init_quantity, init_price,
                realized, create_time, date, unrealized,
                position_type, entry_date, swing_stop_loss, swing_target,
                swing_entry_reason, max_hold_days
            ) VALUES (
                :symbol, :type, :quantity, :avg_cost, :init_quantity, :init_price,
                :realized, :create_time, :date, :unrealized,
                :position_type, :entry_date, :swing_stop_loss, :swing_target,
                :swing_entry_reason, :max_hold_days
            )
        ''', p)
        inserted += 1
        side = 'LONG' if p['type'] == 2 else 'SHORT'
        days = (today - datetime.strptime(p['entry_date'], '%Y-%m-%d').date()).days
        label = f"[{p['position_type'].upper()}]"
        days_str = f' | {days}d held' if p['position_type'] == 'swing' else ''
        print(f'  Seeded {p["symbol"]:5s} {side:5s} {p["quantity"]:4d} @ ${p["avg_cost"]:.2f} {label}{days_str}')

    conn.commit()
    conn.close()

    print(f'\nDone. Inserted {inserted}, skipped {skipped}.')
    print('Reload the dashboard → Positions tab to see the seeded data.')

if __name__ == '__main__':
    seed()
