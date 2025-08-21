#!/usr/bin/env python3
"""
Script to fix existing trades with null PnL values
This script will recalculate PnL for trades that have null price or PnL values
UPDATED: Now handles complete roundtrip trades (buy all shares, then sell all shares)
"""
import sqlite3
import os
from datetime import datetime
from collections import defaultdict

# Database file path
script_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(script_dir, 'trading_advisor.db')

def fix_existing_pnl():
    """Fix existing trades with null PnL values using roundtrip logic"""
    print("=== Fixing Existing Trades with Null PnL Values (Roundtrip Logic) ===")
    
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Database file not found: {DATABASE_FILE}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get all trades with null price or PnL values
        cursor.execute('''
            SELECT id, symbol, side, quantity, price, pnl, trade_date, trade_time
            FROM trades 
            WHERE price IS NULL OR pnl IS NULL OR price = 0 OR pnl = 0
            ORDER BY symbol, trade_date, trade_time
        ''')
        
        null_trades = cursor.fetchall()
        
        if not null_trades:
            print("✅ No trades found with null price or PnL values")
            return
        
        print(f"Found {len(null_trades)} trades with null/zero price or PnL values")
        print("-" * 80)
        
        # Group trades by symbol to match buy/sell pairs
        trades_by_symbol = defaultdict(list)
        for trade in null_trades:
            trade_id, symbol, side, quantity, price, pnl, trade_date, trade_time = trade
            trades_by_symbol[symbol].append({
                'id': trade_id,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'pnl': pnl,
                'trade_date': trade_date,
                'trade_time': trade_time
            })
        
        fixed_count = 0
        
        for symbol, trades in trades_by_symbol.items():
            print(f"\nProcessing {symbol}: {len(trades)} trades")
            
            # Sort trades by date and time
            trades.sort(key=lambda x: (x['trade_date'], x['trade_time']))
            
            # Find buy/sell trades
            buy_trades = []
            sell_trades = []
            
            for trade in trades:
                if trade['side'] == 'B':
                    buy_trades.append(trade)
                elif trade['side'] in ['S', 'SS']:
                    sell_trades.append(trade)
            
            print(f"  Buy trades: {len(buy_trades)}, Sell trades: {len(sell_trades)}")
            
            # Calculate total quantities
            total_buy_qty = sum(trade['quantity'] for trade in buy_trades)
            total_sell_qty = sum(trade['quantity'] for trade in sell_trades)
            
            print(f"  Total buy quantity: {total_buy_qty}, Total sell quantity: {total_sell_qty}")
            
            # Only calculate PnL if we have complete roundtrips
            if total_buy_qty > 0 and total_sell_qty > 0:
                # Calculate weighted average buy price
                total_buy_value = sum(trade['quantity'] * (trade['price'] or 0) for trade in buy_trades)
                avg_buy_price = total_buy_value / total_buy_qty if total_buy_qty > 0 else 0
                
                # Calculate weighted average sell price
                total_sell_value = sum(trade['quantity'] * (trade['price'] or 0) for trade in sell_trades)
                avg_sell_price = total_sell_value / total_sell_qty if total_sell_qty > 0 else 0
                
                print(f"  Average buy price: ${avg_buy_price:.2f}, Average sell price: ${avg_sell_price:.2f}")
                
                # Calculate PnL for the roundtrip
                if avg_buy_price > 0 and avg_sell_price > 0:
                    # Use the minimum of buy and sell quantities for PnL calculation
                    roundtrip_qty = min(total_buy_qty, total_sell_qty)
                    pnl = (avg_sell_price - avg_buy_price) * roundtrip_qty
                    pnl = round(pnl, 2)  # Round to 2 decimal places
                    
                    print(f"  Roundtrip PnL: ${pnl:.2f} for {roundtrip_qty} shares")
                    
                    # Update all sell trades with the calculated PnL
                    for sell_trade in sell_trades:
                        if sell_trade['price'] is None or sell_trade['price'] == 0:
                            # Use average sell price if individual price is missing
                            cursor.execute('UPDATE trades SET price = ?, pnl = ? WHERE id = ?', 
                                         (avg_sell_price, pnl, sell_trade['id']))
                        else:
                            # Keep individual price, update PnL
                            cursor.execute('UPDATE trades SET pnl = ? WHERE id = ?', (pnl, sell_trade['id']))
                        fixed_count += 1
                    
                    # Update buy trades with missing prices
                    for buy_trade in buy_trades:
                        if buy_trade['price'] is None or buy_trade['price'] == 0:
                            cursor.execute('UPDATE trades SET price = ? WHERE id = ?', (avg_buy_price, buy_trade['id']))
                            fixed_count += 1
                else:
                    print(f"  Cannot calculate PnL - missing prices")
                    # Set PnL to 0 for sell trades with missing prices
                    for sell_trade in sell_trades:
                        cursor.execute('UPDATE trades SET pnl = 0.0 WHERE id = ?', (sell_trade['id'],))
                        fixed_count += 1
            else:
                print(f"  No complete roundtrip - setting PnL to 0")
                # Set PnL to 0 for sell trades when no complete roundtrip
                for sell_trade in sell_trades:
                    cursor.execute('UPDATE trades SET pnl = 0.0 WHERE id = ?', (sell_trade['id'],))
                    fixed_count += 1
        
        # Commit changes
        conn.commit()
        print(f"\n✅ Fixed {fixed_count} trades with null/zero PnL values")
        
        # Show updated results
        print("\n=== Updated Trades ===")
        cursor.execute('''
            SELECT symbol, side, quantity, price, pnl, trade_date, trade_time
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        
        rows = cursor.fetchall()
        for row in rows:
            symbol, side, quantity, price, pnl, trade_date, trade_time = row
            print(f"Symbol: {symbol:6} | Side: {side} | Qty: {quantity:4} | Price: ${price:8.2f} | PnL: ${pnl:8.2f} | Date: {trade_date} | Time: {trade_time}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error fixing existing PnL: {e}")

def add_test_trades():
    """Add some test trades with proper PnL values for testing roundtrip logic"""
    print("\n=== Adding Test Trades with Roundtrip PnL ===")
    
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Database file not found: {DATABASE_FILE}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Test roundtrip trades - PPCBin example
        test_trades = [
            # Buy 1000 shares of PPCBin
            {
                'trade_id': int(datetime.now().timestamp() * 1000) % 1000000 + 1,
                'symbol': 'PPCBIN',
                'side': 'B',
                'quantity': 1000,
                'price': 10.00,
                'route': 'SMAT',
                'trade_time': datetime.now().strftime('%H:%M:%S'),
                'order_id': 1001,
                'liquidity': '',
                'ecn_fee': 0.0,
                'pnl': 0.0,  # Buy trades have no PnL
                'trade_date': datetime.now().date().isoformat()
            },
            # Sell 1000 shares of PPCBin (complete roundtrip)
            {
                'trade_id': int(datetime.now().timestamp() * 1000) % 1000000 + 2,
                'symbol': 'PPCBIN',
                'side': 'S',
                'quantity': 1000,
                'price': 12.00,
                'route': 'SMAT',
                'trade_time': datetime.now().strftime('%H:%M:%S'),
                'order_id': 1002,
                'liquidity': '',
                'ecn_fee': 0.0,
                'pnl': 2000.0,  # (12.00 - 10.00) * 1000 = $2000 profit
                'trade_date': datetime.now().date().isoformat()
            },
            # Buy 500 shares of TEST2
            {
                'trade_id': int(datetime.now().timestamp() * 1000) % 1000000 + 3,
                'symbol': 'TEST2',
                'side': 'B',
                'quantity': 500,
                'price': 15.00,
                'route': 'SMAT',
                'trade_time': datetime.now().strftime('%H:%M:%S'),
                'order_id': 1003,
                'liquidity': '',
                'ecn_fee': 0.0,
                'pnl': 0.0,  # Buy trades have no PnL
                'trade_date': datetime.now().date().isoformat()
            },
            # Sell 500 shares of TEST2 (complete roundtrip)
            {
                'trade_id': int(datetime.now().timestamp() * 1000) % 1000000 + 4,
                'symbol': 'TEST2',
                'side': 'S',
                'quantity': 500,
                'price': 14.00,
                'route': 'SMAT',
                'trade_time': datetime.now().strftime('%H:%M:%S'),
                'order_id': 1004,
                'liquidity': '',
                'ecn_fee': 0.0,
                'pnl': -500.0,  # (14.00 - 15.00) * 500 = -$500 loss
                'trade_date': datetime.now().date().isoformat()
            }
        ]
        
        for trade in test_trades:
            cursor.execute('''
                INSERT INTO trades (
                    trade_id, symbol, side, quantity, price, route, 
                    trade_time, order_id, liquidity, ecn_fee, pnl, trade_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade['trade_id'],
                trade['symbol'],
                trade['side'],
                trade['quantity'],
                trade['price'],
                trade['route'],
                trade['trade_time'],
                trade['order_id'],
                trade['liquidity'],
                trade['ecn_fee'],
                trade['pnl'],
                trade['trade_date']
            ))
        
        conn.commit()
        print(f"✅ Added {len(test_trades)} test trades with roundtrip PnL values")
        print("  - PPCBin: Buy 1000 @ $10.00, Sell 1000 @ $12.00 = $2000 profit")
        print("  - TEST2: Buy 500 @ $15.00, Sell 500 @ $14.00 = -$500 loss")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error adding test trades: {e}")

if __name__ == "__main__":
    fix_existing_pnl()
    add_test_trades()
