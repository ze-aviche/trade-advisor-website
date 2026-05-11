#!/usr/bin/env python3
"""
Mock DAS Trader server for local testing without a real DAS subscription.

Listens on 127.0.0.1:9800 and responds to every DAS command the bot sends.
Simulates slow price drift so exit conditions can be triggered.

Run this BEFORE starting the Flask app and bot.

Usage:
    python mock_das_server.py                        # mixed scenario, neutral drift
    python mock_das_server.py --scenario entry       # empty positions; entry bot creates them
    python mock_das_server.py --scenario mixed       # 1 day + 1 swing (pre-existing)
    python mock_das_server.py --scenario day         # 2 day positions
    python mock_das_server.py --scenario swing       # 2 swing positions
    python mock_das_server.py --scenario eod         # 1 SPY day position
    python mock_das_server.py --drift target         # prices drift toward profit targets
    python mock_das_server.py --drift stop           # prices drift toward stop losses
    python mock_das_server.py --ramp 15              # volume ramps up after 15 s (default)
"""

import socket
import threading
import time
import sys
import math
from datetime import datetime
import pytz

HOST = '127.0.0.1'
PORT = 9800

# ──────────────────────────────────────────────────────────────────────────────
# TEST SCENARIOS
# Each position: (symbol, type_num, qty, avg_cost, realized, create_time, label)
# type_num: 2 = LONG, 3 = SHORT
# ──────────────────────────────────────────────────────────────────────────────

SCENARIOS = {
    # No pre-existing positions.  Entry bot will open them via NEWORDER.
    'entry': [],
    'mixed': [
        ('NVDA',  2,  100,  480.00,  0.00,  '09:31:00',  'day'),
        ('AAPL',  2,   50,  175.00,  0.00,  '09:35:00',  'swing'),
    ],
    'day': [
        ('TSLA',  2,   75,  250.00,  0.00,  '09:30:00',  'day'),
        ('AMD',   3,  200,   95.00,  0.00,  '10:00:00',  'day'),
    ],
    'swing': [
        ('MSFT',  2,   30,  410.00,  0.00,  '09:30:00',  'swing'),
        ('META',  2,   20,  520.00,  0.00,  '09:30:00',  'swing'),
    ],
    'eod': [
        ('SPY',   2,  100,  510.00,  0.00,  '09:30:00',  'day'),
    ],
}

# Default prices for symbols not in the scenario (used by entry scenario so
# the entry bot can get Level 1 data before a position exists).
SYMBOL_DEFAULTS = {
    'NVDA': 480.00,
    'AAPL': 175.00,
    'MSFT': 415.00,
    'META': 520.00,
    'TSLA': 250.00,
    'AMD':   95.00,
    'SPY':  510.00,
    'AMZN': 185.00,
    'GOOG': 170.00,
    'NFLX': 620.00,
}

# ──────────────────────────────────────────────────────────────────────────────
# LIVE STATE  (mutated by drift thread / NEWORDER handler)
# ──────────────────────────────────────────────────────────────────────────────

prices = {}          # symbol -> {'bid', 'ask', 'last'}
positions = []       # list of position dicts (removed when closed)
closed_symbols = set()

drift_direction = 'neutral'   # 'target' | 'stop' | 'neutral'

# Volume ramp: starts low, jumps to high after `volume_ramp_seconds` seconds.
server_start_time = None
volume_ramp_seconds = 15   # overridden by --ramp flag
_volume_ramped = False      # internal flag so we only print the banner once

ET = pytz.timezone('US/Eastern')


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _current_volume_shares(symbol: str) -> int:
    """Return the simulated share volume for the symbol.
    Low (100 K) until the ramp window passes; then high (3 M).
    """
    global _volume_ramped
    elapsed = time.time() - server_start_time
    if elapsed >= volume_ramp_seconds:
        if not _volume_ramped:
            _volume_ramped = True
            print(
                f'\n[SERVER] Volume ramped up after {volume_ramp_seconds}s '
                '— day-trade entry conditions should trigger now\n'
            )
        return 3_000_000
    return 100_000


def build_positions_response():
    lines = []
    for p in positions:
        if p['symbol'] in closed_symbols:
            continue
        bid = prices.get(p['symbol'], {}).get('bid', p['avg_cost'])
        unrealized = (bid - p['avg_cost']) * p['qty']
        line = (
            f"%POS {p['symbol']} {p['type_num']} {p['qty']} {p['avg_cost']:.2f} "
            f"{p['qty']} {p['avg_cost']:.2f} {p['realized']:.2f} "
            f"{p['create_time']} {unrealized:.2f}"
        )
        lines.append(line)
    return '\r\n'.join(lines) + '\r\n' if lines else '\r\n'


def build_level1_response(symbol: str) -> str:
    sym = symbol.upper()
    p = prices.get(sym)
    if not p:
        # Auto-create a price for any known symbol (supports entry scenario)
        default = SYMBOL_DEFAULTS.get(sym)
        if default:
            prices[sym] = {
                'bid':  round(default - 0.05, 2),
                'ask':  round(default + 0.05, 2),
                'last': default,
            }
            p = prices[sym]
        else:
            return f'$Quote {sym} A:0 Asz:0 B:0 Bsz:0 L:0 V:0\r\n'

    volume = _current_volume_shares(sym)
    return (
        f'$Quote {sym} '
        f'A:{p["ask"]:.2f} Asz:100 '
        f'B:{p["bid"]:.2f} Bsz:200 '
        f'L:{p["last"]:.2f} '
        f'V:{volume} Vt:{int(volume * 1.5)}\r\n'
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
        open_count = sum(1 for p in positions if p['symbol'] not in closed_symbols)
        print(f'  [DAS→bot] (positions response, {open_count} open)')
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
        # NEWORDER {id} {B|S} {symbol} {route} {qty} {MKT|price} ...
        parts = cmd.split()
        if len(parts) >= 4:
            order_id = parts[1]
            side     = parts[2].upper()
            symbol   = parts[3].upper()
            qty      = int(parts[5]) if len(parts) > 5 else 100

            is_open = any(
                p['symbol'] == symbol and symbol not in closed_symbols
                for p in positions
            )

            if side == 'B' and not is_open:
                # Opening a new long position (entry bot buy)
                last = prices.get(symbol, {}).get('last', SYMBOL_DEFAULTS.get(symbol, 100.0))
                # Ensure price state exists
                if symbol not in prices:
                    prices[symbol] = {
                        'bid':  round(last - 0.05, 2),
                        'ask':  round(last + 0.05, 2),
                        'last': last,
                    }
                positions.append({
                    'symbol':      symbol,
                    'type_num':    2,
                    'qty':         qty,
                    'avg_cost':    last,
                    'realized':    0.0,
                    'create_time': datetime.now(ET).strftime('%H:%M:%S'),
                    'label':       'entry-bot',
                })
                print(f'  [DAS→bot] POSITION OPENED: LONG {qty} {symbol} @ ${last:.2f} (id={order_id})')
            else:
                # Closing an existing position (exit bot sell / short sell)
                closed_symbols.add(symbol)
                pnl = 0.0
                for p in positions:
                    if p['symbol'] == symbol:
                        bid = prices.get(symbol, {}).get('bid', p['avg_cost'])
                        pnl = (bid - p['avg_cost']) * p['qty'] if p['type_num'] == 2 else (p['avg_cost'] - bid) * p['qty']
                        break
                print(f'  [DAS→bot] POSITION CLOSED: {side} {qty} {symbol}  PnL≈${pnl:.2f} (id={order_id})')

            return f'Order Submitted SUCCESS orderId={order_id}\r\n'
        return 'Order Submitted SUCCESS\r\n'

    if upper.startswith('QUIT'):
        return ''

    if upper.startswith('GET QUOTE'):
        parts = cmd.split()
        symbol = parts[2].upper() if len(parts) >= 3 else ''
        p = prices.get(symbol, {})
        bid  = p.get('bid',  0)
        ask  = p.get('ask',  0)
        last = p.get('last', 0)
        return f'%QUOTE {symbol} {bid:.2f} {ask:.2f} {last:.2f}\r\n'

    return 'OK\r\n'


# ──────────────────────────────────────────────────────────────────────────────
# PRICE DRIFT THREAD
# ──────────────────────────────────────────────────────────────────────────────

def drift_thread(scenario_positions):
    """
    Moves prices every 5 seconds.
    'target'  → toward profit target  (+0.3%/tick for LONG)
    'stop'    → toward stop loss      (-0.2%/tick for LONG)
    'neutral' → ±0.1% random oscillation
    """
    import random
    tick = 0
    while True:
        time.sleep(5)
        tick += 1
        for sym, p_info in list(prices.items()):
            if sym in closed_symbols:
                continue
            # Determine if this is a long or short position
            is_long = True
            for pos in positions:
                if pos['symbol'] == sym:
                    is_long = pos['type_num'] == 2
                    break

            cur = p_info
            if drift_direction == 'target':
                factor = 1.003 if is_long else 0.997
            elif drift_direction == 'stop':
                factor = 0.998 if is_long else 1.002
            else:
                factor = 1 + random.uniform(-0.001, 0.001)

            new_last = round(cur['last'] * factor, 2)
            new_bid  = round(new_last - 0.05, 2)
            new_ask  = round(new_last + 0.05, 2)
            prices[sym] = {'bid': new_bid, 'ask': new_ask, 'last': new_last}

            # Find entry price for pct display
            entry = new_last
            for pos in positions:
                if pos['symbol'] == sym:
                    entry = pos['avg_cost']
                    break
            pct = (new_last - entry) / entry * 100
            arrow = '▲' if new_last > cur['last'] else '▼'
            print(f'  [PRICE] {sym}: ${new_last:.2f} ({pct:+.2f}% vs entry) {arrow}')


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
    global drift_direction, volume_ramp_seconds, server_start_time, _volume_ramped

    scenario_name = 'mixed'

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--scenario' and i + 1 < len(args):
            scenario_name = args[i + 1]
            i += 2
        elif args[i] == '--drift' and i + 1 < len(args):
            drift_direction = args[i + 1]
            i += 2
        elif args[i] == '--ramp' and i + 1 < len(args):
            volume_ramp_seconds = int(args[i + 1])
            i += 2
        else:
            i += 1

    if scenario_name not in SCENARIOS:
        print(f'Unknown scenario "{scenario_name}". Available: {list(SCENARIOS.keys())}')
        sys.exit(1)

    scenario_positions = SCENARIOS[scenario_name]

    for sym, type_num, qty, avg_cost, realized, create_time, label in scenario_positions:
        positions.append({
            'symbol':      sym,
            'type_num':    type_num,
            'qty':         qty,
            'avg_cost':    avg_cost,
            'realized':    realized,
            'create_time': create_time,
            'label':       label,
        })
        prices[sym] = {
            'bid':  round(avg_cost - 0.05, 2),
            'ask':  round(avg_cost + 0.05, 2),
            'last': avg_cost,
        }

    server_start_time = time.time()

    print('=' * 62)
    print('  MOCK DAS SERVER')
    print('=' * 62)
    print(f'  Scenario  : {scenario_name}')
    print(f'  Drift     : {drift_direction}')
    print(f'  Listening : {HOST}:{PORT}')
    print(f'  Vol ramp  : {volume_ramp_seconds}s  (low=100K → high=3M shares)')
    print()
    if positions:
        print('  Pre-seeded positions:')
        for p in positions:
            side = 'LONG' if p['type_num'] == 2 else 'SHORT'
            print(f'    {p["symbol"]:6s} {side:5s} {p["qty"]:4d} @ ${p["avg_cost"]:.2f}  [{p["label"]}]')
    else:
        print('  No pre-seeded positions (entry bot will open them via NEWORDER)')
    print()
    print('  Keyboard commands:')
    print('    t → drift toward profit targets')
    print('    s → drift toward stop losses')
    print('    n → neutral oscillation')
    print('    v → manually trigger volume ramp now')
    print('    p → print current prices')
    print('    c → show closed positions')
    print('    q → quit server')
    print('=' * 62)

    # Start price drift thread
    threading.Thread(target=drift_thread, args=(positions,), daemon=True).start()

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
            except OSError as e:
                # Server socket was closed — exit the loop
                if server.fileno() == -1:
                    break
                print(f'[SERVER] Accept error (continuing): {e}')
            except Exception as e:
                print(f'[SERVER] Accept error (continuing): {e}')

    threading.Thread(target=accept_loop, daemon=True).start()

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
            elif key == 'v':
                # Manually trigger volume ramp immediately
                server_start_time = time.time() - volume_ramp_seconds - 1
                _volume_ramped = False  # let the banner print on the next SB call
                print('[SERVER] Volume ramped to 3 M shares — next SB response will meet day-trade thresholds')
            elif key == 'p':
                print('\n[SERVER] Current prices:')
                for sym, p in prices.items():
                    status = ' [CLOSED]' if sym in closed_symbols else ''
                    print(f'  {sym}: bid=${p["bid"]:.2f} ask=${p["ask"]:.2f} last=${p["last"]:.2f}{status}')
            elif key == 'c':
                print(f'[SERVER] Closed positions: {closed_symbols or "(none)"}')
                open_syms = [p['symbol'] for p in positions if p['symbol'] not in closed_symbols]
                print(f'[SERVER] Open positions:   {open_syms or "(none)"}')
            elif key == 'q':
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        print('\n[SERVER] Stopped.')


if __name__ == '__main__':
    main()
