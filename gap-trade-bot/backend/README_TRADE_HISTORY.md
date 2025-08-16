# Trade History System

This document describes the trade history functionality that integrates with DAS Trader to record and display trading activity.

## Overview

The trade history system consists of:

1. **Database Table**: `trades` table in `trading_advisor.db`
2. **DAS Integration**: Connection to DAS Trader for real-time trade data
3. **API Endpoints**: REST API for managing trade data
4. **Frontend Interface**: Trade history tab in the web dashboard

## Database Schema

The `trades` table stores the following information:

```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,           -- DAS trade ID
    symbol TEXT NOT NULL,                -- Stock symbol (e.g., AAPL)
    side TEXT NOT NULL,                  -- B (Buy), S (Sell), SS (Short Sell)
    quantity INTEGER NOT NULL,           -- Number of shares
    price REAL NOT NULL,                 -- Trade price
    route TEXT NOT NULL,                 -- Trading route (e.g., SMAT)
    trade_time TEXT NOT NULL,            -- Time of trade (HH:MM:SS)
    order_id INTEGER,                    -- Order ID
    liquidity TEXT,                      -- Liquidity indicator
    ecn_fee REAL DEFAULT 0.0,           -- ECN fees
    pnl REAL DEFAULT 0.0,               -- Profit/Loss
    trade_date DATE NOT NULL,           -- Date of trade (YYYY-MM-DD)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## DAS Integration

### DAS Connection

The system connects to DAS Trader using the CMD API on port 9800. The connection parameters are:

- **Host**: 127.0.0.1
- **Port**: 9800
- **User ID**: IDAS12181
- **Password**: Dastrader@2
- **Account**: TRIDAS12181

### DAS Trade Data Format

DAS Trader sends trade data in the following format:

```
#Trade id symb B/S qty price 
route time orderid Liq EcnFee PL 
%TRADE 1 MSFT B 100 28.3 
SMAT 18:00:31 3 
%TRADE 2 MSFT B 100 28.31 
SMAT 18:01:19 4 
%TRADE 3 DELL SS 100 14.75 
SMAT 18:02:17 5 
#TradeEnd
```

### Parsing Logic

The system parses each `%TRADE` line to extract:
- Trade ID
- Symbol
- Side (B/S/SS)
- Quantity
- Price

## API Endpoints

### Get Trade History
```
GET /api/trades
```

**Query Parameters:**
- `symbol` (optional): Filter by stock symbol
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `limit` (optional): Maximum number of trades to return (default: 100)

**Response:**
```json
{
    "success": true,
    "data": {
        "trades": [...],
        "summary": {...}
    },
    "timestamp": "2024-01-15T10:30:00",
    "count": 5
}
```

### Add Trade
```
POST /api/trades
```

**Request Body:**
```json
{
    "trade_id": 1,
    "symbol": "AAPL",
    "side": "B",
    "quantity": 100,
    "price": 150.25,
    "route": "SMAT",
    "trade_time": "14:30:00",
    "order_id": 12345,
    "liquidity": "M",
    "ecn_fee": 0.50,
    "pnl": 0.0,
    "trade_date": "2024-01-15"
}
```

### Import DAS Trades
```
POST /api/trades/import-das
```

**Request Body:**
```json
{
    "das_trades_text": "#Trade id symb B/S qty price\n%TRADE 1 MSFT B 100 28.3\n#TradeEnd"
}
```

### Sync from DAS
```
POST /api/trades/sync-das
```

Connects to DAS Trader and imports current trades.

### Get Trade Summary
```
GET /api/trades/summary
```

**Query Parameters:**
- `symbol` (optional): Filter by stock symbol
- `start_date` (optional): Start date
- `end_date` (optional): End date

**Response:**
```json
{
    "success": true,
    "data": {
        "total_trades": 10,
        "total_buy_quantity": 500,
        "total_sell_quantity": 300,
        "net_quantity": 200,
        "total_buy_value": 75000.00,
        "total_sell_value": 45000.00,
        "net_value": 30000.00,
        "total_pnl": 5000.00,
        "total_fees": 25.50,
        "avg_buy_price": 150.00,
        "avg_sell_price": 150.00
    }
}
```

## Frontend Features

### Trade History Tab

The trade history tab provides:

1. **Period Selection**: Filter trades by time period (1 day to 1 year)
2. **Ticker Search**: Filter trades by specific stock symbol
3. **Sync Buttons**: 
   - Sync from DAS Trader (green button)
   - Sync from Alpaca (purple button)
4. **Import Feature**: Manual import of DAS trades data
5. **Export Options**: Download as CSV or Excel
6. **Trade Table**: Displays trade details with sorting and filtering

### Trade Table Columns

- **Ticker**: Stock symbol
- **Type**: Long/Short (Buy/Sell)
- **Quantity**: Number of shares
- **Price**: Trade price
- **Status**: Trade status (filled)
- **P&L**: Profit/Loss
- **Date**: Trade date and time

## Usage Examples

### 1. Import Sample Data

```python
from das_integration import das_trade_manager

# Sample DAS data
das_data = """%TRADE 1 AAPL B 100 150.25
%TRADE 2 MSFT S 50 300.00
#TradeEnd"""

success, message, count = das_trade_manager.import_das_trades_text(das_data)
print(f"Imported {count} trades")
```

### 2. Sync from DAS Trader

```python
from das_integration import das_trade_manager

# Make sure DAS Trader is running
success, message, count = das_trade_manager.sync_trades_from_das()
print(f"Synced {count} trades from DAS")
```

### 3. Get Trade History

```python
from database import db_manager

# Get all trades
trades = db_manager.get_trades()

# Get trades for specific symbol
trades = db_manager.get_trades(symbol="AAPL")

# Get trades for date range
trades = db_manager.get_trades(
    start_date="2024-01-01",
    end_date="2024-01-31"
)
```

### 4. Get Trade Summary

```python
from database import db_manager

summary = db_manager.get_trade_summary()
print(f"Total trades: {summary['total_trades']}")
print(f"Total P&L: ${summary['total_pnl']:.2f}")
```

## Command Line Tools

### Import Script

Run the import script to interactively manage trade data:

```bash
cd gap-trade-bot/backend/scripts
python import_das_trades.py
```

This script provides options to:
- Import sample DAS data
- Sync from DAS Trader
- View trade history
- View trade summary

### Test Script

Run the test script to verify functionality:

```bash
python test_trade_history.py
```

## Configuration

### DAS Connection Settings

Edit `das_integration.py` to modify DAS connection parameters:

```python
class DASConnection:
    def __init__(self, host="127.0.0.1", port=9800, 
                 userid="IDAS12181", password="Dastrader@2", 
                 account="TRIDAS12181"):
```

### Database Location

The database file is located at:
```
gap-trade-bot/backend/trading_advisor.db
```

## Troubleshooting

### DAS Connection Issues

1. **DAS Trader not running**: Make sure DAS Trader is open and logged in
2. **Wrong port**: Verify DAS is listening on port 9800
3. **Authentication**: Check user ID, password, and account settings
4. **Firewall**: Ensure firewall allows connection to localhost:9800

### Database Issues

1. **Permission errors**: Check file permissions on the database file
2. **Corrupted database**: Delete the database file to recreate it
3. **SQLite version**: Ensure SQLite 3.x is installed

### Frontend Issues

1. **API errors**: Check backend server is running on port 5000
2. **CORS issues**: Verify CORS settings in app.py
3. **Data not loading**: Check browser console for JavaScript errors

## Future Enhancements

1. **Real-time updates**: WebSocket integration for live trade updates
2. **Advanced filtering**: More sophisticated search and filter options
3. **Trade analysis**: Built-in P&L analysis and reporting
4. **Multi-account support**: Support for multiple DAS accounts
5. **Backup and restore**: Database backup and restore functionality
6. **Trade alerts**: Notifications for specific trade events
