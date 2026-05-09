#!/usr/bin/env python3
"""
Mock DAS Trader server for local testing without a real DAS subscription.

Listens on 127.0.0.1:9800 and responds to every DAS command the bot sends.
Simulates slow price drift so exit conditions can be triggered.
Run this BEFORE starting the Flask app and bot.

Usage:
    python mock_das_server.py                    # normal mode
    python mock_das_server.py --scenario eod     # day positions exit at 15:45
    python mock_das_server.py --scenario swing   # only swing positions (never EOD)
    python mock_das_server.py --scenario mixed   # one day + one swing position
    python mock_das_server.py --drift target     # prices drift toward profit targets
    python mock_das_server.py --drift stop       # prices drift toward stop losses
"""

import socket
import threading
import time
import sys
import re
import math
from datetime import datetime, timedelta
import pytz

HOST = '127.0.0.1'
PORT = 9800

# ──────────────────────────────────────────────────────────────────────────────
# TEST SCENARIOS
# Each position: (symbol, type_num, qty, avg_cost, realized, create_time, position_type)
# type_num: 2 = LONG, 3 = SHORT
# position_type: only used for logging/notes; DAS itself doesn't know about it
# ──────────────────────────────────────────────────────────────────────────────

SCENARIOS = {
    'mixed': [
        # Symbol     type  qty   avg_cost  realized  create_time   label
        ('NVDA',      2,   100,  480.00,   0.00,     '09:31:00',  'day'),
        ('AAPL',      2,    50,  175.00,   0.00,     '09:35:00',  'swing'),
    ],
    'day': [
        ('TSLA',      2,    75,  250.00,   0.00,     '09:30:00',  'day'),
        ('AMD',       3,   200,   95.00,   0.00,     '10:00:00',  'day'),
    ],
    'swing': [
        ('MSFT',      2,    30,  410.00,   0.00,     '09:30:00',  'swing'),
        ('META',      2,    20,  520.00,   0.00,     '09:30:00',  'swing'),
    ],
    'eod': [
        ('SPY',       2,   100,  510.00,   0.00,     '09:30:00',  'day'),
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# LIVE PRICE STATE  (mutated by drift thread)
# ──────────────────────────────────────────────────────────────────────────────
# Prices start at avg_cost; drift thread moves them ± slowly

prices = {}   # symbol -> {'bid': float, 'ask': float, 'last': float}
positions = []  # list of position dicts (mutable - removed when order closed)
closed_symbols = set()

drift_direction = 'neutral'  # 'target' | 'stop' | 'neutral'

ET = pytz.timezone('US/Eastern')


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def build_positions_response():
    lines = []
    for p in positions:
        if p['symbol'] in closed_symbols:
            continue
        # %POS symbol type qty avgcost initqty initprice realized createtime unrealized
        unrealized = (prices.get(p['symbol'], {}).get('bid', p['avg_cost']) - p['avg_cost']) * p['qty']
        line = (
            f"%POS {p['symbol']} {p['type_num']} {p['qty']} {p['avg_cost']:.2f} "
            f"{p['qty']} {p['avg_cost']:.2f} {p['realized']:.2f} "
            f"{p['create_time']} {unrealized:.2f}"
        )
        lines.append(line)
    return '\r\n'.join(lines) + '\r\n' if lines else '\r\n'


def build_level1_response(symbol):
    sym = symbol.upper()
    p = prices.get(sym)
    if not p:
        return f'$Quote {sym} A:0 Asz:0 B:0 Bsz:0 L:0\r\n'
    return (
        f'$Quote {sym} '
        f'A:{p["ask"]:.2f} Asz:100 '
        f'B:{p["bid"]:.2f} Bsz:200 '
        f'L:{p["last"]:.2f} '
        f'V:1500000 Vt:2500000\r\n'
    )


def handle_command(cmd: str) -> str:
    cmd = cmd.strip()
    if not cmd:
        return '\r\n'

    print(f'  [DAS←bot] {cmd}')

    upper = cmd.upper()

    if upper.startswith('LOGIN'):
        return 'Login id=IDAS12181 Accepted\r\n'

    if upper.startswith('GET ACCOUNT'):
        return '%ACCT TRIDAS12181 1000000.00 900000.00 50000.00\r\n'

    if upper.startswith('GET POSITIONS'):
        resp = build_positions_response()
        print(f'  [DAS→bot] (positions response, {len(positions)} positions)')
        return resp

    if upper.startswith('RETURNFULLLV1'):
        return 'OK\r\n'

    if upper.startswith('SB ') and 'LV1' in upper:
        symbol = cmd.split()[1].upper()
        resp = build_level1_response(symbol)
        print(f'  [DAS→bot] {resp.strip()}')
        return resp

    if upper.startswith('UNSB'):
        return 'OK\r\n'

    if upper.startswith('NEWORDER'):
        # NEWORDER {id} [S|B] {symbol} SMAT {qty} MKT
        parts = cmd.split()
        if len(parts) >= 6:
            order_id = parts[1]
            side = parts[2].upper()
            symbol = parts[3].upper()
            qty = parts[5] if len(parts) > 5 else '?'
            print(f'  [DAS→bot] ORDER ACCEPTED: {side} {qty} {symbol} (id={order_id})')
            closed_symbols.add(symbol)
            return f'Order Submitted SUCCESS orderId={order_id}\r\n'
        return 'Order Submitted SUCCESS\r\n'

    if upper.startswith('QUIT'):
        return ''

    if upper.startswith('GET QUOTE'):
        parts = cmd.split()
        symbol = parts[2].upper() if len(parts) >= 3 else ''
        p = prices.get(symbol, {})
        bid = p.get('bid', 0)
        ask = p.get('ask', 0)
        last = p.get('last', 0)
        return f'%QUOTE {symbol} {bid:.2f} {ask:.2f} {last:.2f}\r\n'

    # Unknown command — return empty OK
    return 'OK\r\n'


# ──────────────────────────────────────────────────────────────────────────────
# PRICE DRIFT THREAD
# ──────────────────────────────────────────────────────────────────────────────

def drift_thread(scenario_positions):
    """
    Slowly moves prices every 5 seconds.
    'target'  → toward profit target   (+5% for LONG, -5% for SHORT)
    'stop'    → toward stop loss       (-2.5% for LONG, +2.5% for SHORT)
    'neutral' → small random oscillation
    """
    import random
    tick = 0
    while True:
        time.sleep(5)
        tick += 1
        for p in scenario_positions:
            sym = p['symbol']
            if sym in closed_symbols:
                continue
            cur = prices[sym]
            entry = p['avg_cost']
            is_long = p['type_num'] == 2

            if drift_direction == 'target':
                # Slowly move 0.3% per tick toward target
                factor = 1.003 if is_long else 0.997
            elif drift_direction == 'stop':
                # Slowly move 0.2% per tick toward stop
                factor = 0.998 if is_long else 1.002
            else:
                # Small oscillation ±0.1%
                factor = 1 + random.uniform(-0.001, 0.001)

            new_last = round(cur['last'] * factor, 2)
            new_bid  = round(new_last - 0.05, 2)
            new_ask  = round(new_last + 0.05, 2)
            prices[sym] = {'bid': new_bid, 'ask': new_ask, 'last': new_last}

            pct = (new_last - entry) / entry * 100
            direction_arrow = '▲' if new_last > cur['last'] else '▼'
            print(f'  [PRICE] {sym}: ${new_last:.2f} ({pct:+.2f}% vs entry) {direction_arrow}')


# ──────────────────────────────────────────────────────────────────────────────
# CLIENT HANDLER
# ──────────────────────────────────────────────────────────────────────────────

class ClientHandler(threading.Thread):
    def __init__(self, conn, addr):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr

    def run(self):
        print(f'\n[SERVER] Client connected: {self.addr}')
        buf = b''
        try:
            while True:
                chunk = self.conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b'\r\n' in buf:
                    line_bytes, buf = buf.split(b'\r\n', 1)
                    cmd = line_bytes.decode('ascii', errors='replace')
                    response = handle_command(cmd)
                    if response:
                        self.conn.sendall(response.encode('ascii'))
                    if cmd.strip().upper() == 'QUIT':
                        return
        except Exception as e:
            print(f'[SERVER] Client error: {e}')
        finally:
            self.conn.close()
            print(f'[SERVER] Client disconnected: {self.addr}')


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    scenario_name = 'mixed'
    global drift_direction

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--scenario' and i + 1 < len(args):
            scenario_name = args[i + 1]
            i += 2
        elif args[i] == '--drift' and i + 1 < len(args):
            drift_direction = args[i + 1]
            i += 2
        else:
            i += 1

    if scenario_name not in SCENARIOS:
        print(f'Unknown scenario "{scenario_name}". Available: {list(SCENARIOS.keys())}')
        sys.exit(1)

    scenario_positions = SCENARIOS[scenario_name]

    # Build mutable positions list and initial prices
    for sym, type_num, qty, avg_cost, realized, create_time, label in scenario_positions:
        positions.append({
            'symbol': sym,
            'type_num': type_num,
            'qty': qty,
            'avg_cost': avg_cost,
            'realized': realized,
            'create_time': create_time,
            'label': label,
        })
        prices[sym] = {
            'bid':  round(avg_cost - 0.05, 2),
            'ask':  round(avg_cost + 0.05, 2),
            'last': avg_cost,
        }

    print('=' * 60)
    print('  MOCK DAS SERVER')
    print('=' * 60)
    print(f'  Scenario  : {scenario_name}')
    print(f'  Drift     : {drift_direction}')
    print(f'  Listening : {HOST}:{PORT}')
    print()
    print('  Positions:')
    for p in positions:
        side = 'LONG' if p['type_num'] == 2 else 'SHORT'
        print(f'    {p["symbol"]:6s} {side:5s} {p["qty"]:4d} @ ${p["avg_cost"]:.2f}  [{p["label"]}]')
    print()
    print('  Price drift commands (type in terminal):')
    print('    t → drift toward targets')
    print('    s → drift toward stops')
    print('    n → neutral oscillation')
    print('    q → quit server')
    print('=' * 60)

    # Start price drift thread
    t = threading.Thread(target=drift_thread, args=(positions,), daemon=True)
    t.start()

    # Start TCP server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    server.settimeout(1.0)

    print(f'\n[SERVER] Listening on {HOST}:{PORT}  (Ctrl+C or "q" to stop)\n')

    def accept_loop():
        while True:
            try:
                conn, addr = server.accept()
                ClientHandler(conn, addr).start()
            except socket.timeout:
                continue
            except Exception:
                break

    accept_thread = threading.Thread(target=accept_loop, daemon=True)
    accept_thread.start()

    # Interactive keyboard control
    try:
        while True:
            try:
                key = input().strip().lower()
            except EOFError:
                time.sleep(1)
                continue
            if key == 't':
                drift_direction = 'target'
                print('[SERVER] Drift → toward profit targets')
            elif key == 's':
                drift_direction = 'stop'
                print('[SERVER] Drift → toward stop losses')
            elif key == 'n':
                drift_direction = 'neutral'
                print('[SERVER] Drift → neutral')
            elif key == 'q':
                break
            elif key == 'p':
                print('\n[SERVER] Current prices:')
                for sym, p in prices.items():
                    if sym not in closed_symbols:
                        print(f'  {sym}: bid=${p["bid"]:.2f} ask=${p["ask"]:.2f} last=${p["last"]:.2f}')
            elif key == 'c':
                print(f'[SERVER] Closed positions: {closed_symbols or "(none)"}')
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        print('\n[SERVER] Stopped.')


if __name__ == '__main__':
    main()
