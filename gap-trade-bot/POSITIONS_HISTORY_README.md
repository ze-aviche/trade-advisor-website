# Positions History Feature

## Overview

The Positions History feature provides comprehensive tracking and management of trading positions. It automatically syncs position data from DAS Trader every 10 seconds when the bot is running, stores the data in a SQLite database, and displays it in a user-friendly interface.

## Features

### 1. Automatic Position Syncing
- **10-Second Intervals**: When the bot is running, positions are automatically synced from DAS Trader every 10 seconds
- **Real-time Updates**: Position data including realized/unrealized P&L, current prices, and market values are updated in real-time
- **Upsert Operations**: Positions are automatically inserted or updated in the database based on symbol and position type

### 2. Database Storage
- **Positions Table**: New SQLite table to store position history
- **Comprehensive Data**: Stores symbol, quantity, average price, position type, P&L data, market values, and timestamps
- **Efficient Queries**: Indexed for fast retrieval and filtering

### 3. Frontend Interface
- **Dedicated Tab**: New "Positions History" tab in the main navigation
- **Real-time Status**: Shows sync status, bot status, and update intervals
- **Advanced Filtering**: Filter by ticker symbol and position type (Long/Short)
- **Export Options**: Download positions data as CSV or Excel files

## Database Schema

### Positions Table
```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL DEFAULT 0.0,
    position_type TEXT NOT NULL CHECK (position_type IN ('LONG', 'SHORT')),
    realized_pnl REAL DEFAULT 0.0,
    unrealized_pnl REAL DEFAULT 0.0,
    unrealized_pnl_pct REAL DEFAULT 0.0,
    market_value REAL DEFAULT 0.0,
    cost_basis REAL DEFAULT 0.0,
    profit_target REAL DEFAULT 0.0,
    stop_loss REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, position_type)
);
```

## API Endpoints

### GET /api/positions
Retrieve positions with optional filtering
- **Query Parameters**:
  - `symbol`: Filter by ticker symbol
  - `position_type`: Filter by position type (LONG/SHORT)
  - `limit`: Maximum number of positions to return (default: 100, max: 1000)

### POST /api/positions/sync-das
Manually sync positions from DAS Trader
- **Response**: Success status and number of positions synced

### POST /api/positions/upsert
Insert or update a position in the database
- **Body**: Position data object with required fields

## DAS Integration

### Position Parsing
The system parses DAS position responses in the format:
```
%POSITION symbol quantity avg_price realized_pnl unrealized_pnl
```

### Example DAS Response
```
%POSITION AAPL 100 150.50 50.00 250.00
%POSITION MSFT -50 300.25 25.00 -125.00
%POSITION TSLA 200 250.75 0.00 500.00
```

### Position Type Detection
- **LONG**: Quantity > 0
- **SHORT**: Quantity < 0

## Frontend Features

### Status Display
- **Position Sync Status**: Shows if automatic syncing is running
- **Bot Status**: Shows if the bot is running (required for auto-sync)
- **Update Interval**: Displays the 10-second sync interval

### Filtering Options
- **Ticker Symbol**: Search for specific stocks
- **Position Type**: Filter by Long or Short positions
- **Real-time Updates**: Filters apply immediately

### Export Functionality
- **CSV Export**: Download positions as comma-separated values
- **Excel Export**: Download positions as Excel spreadsheet
- **Timestamped Files**: Files include current date in filename

## Usage Instructions

### 1. Starting Position Tracking
1. Ensure DAS Trader is connected
2. Start the trading bot
3. Position syncing will automatically begin every 10 seconds

### 2. Manual Sync
1. Navigate to the "Positions History" tab
2. Click "Sync from DAS" to manually sync positions
3. View the updated position data

### 3. Filtering Positions
1. Enter a ticker symbol in the search field
2. Select position type (Long/Short) from dropdown
3. Results update automatically

### 4. Exporting Data
1. Click "Export CSV" or "Export Excel"
2. Files download automatically with timestamped names
3. Data includes all position fields and calculations

## Technical Implementation

### Backend Components
- **DatabaseManager**: Handles position CRUD operations
- **DASTradeManager**: Manages DAS connection and position parsing
- **ScheduledDASSync**: Handles automatic 10-second syncing
- **API Endpoints**: RESTful endpoints for position management

### Frontend Components
- **Vue.js Data**: Reactive position data and filtering
- **API Integration**: Axios calls to backend endpoints
- **Export Functions**: CSV and Excel generation
- **Real-time Updates**: Automatic data refresh

### Scheduled Sync Service
- **10-Second Intervals**: Runs every 10 seconds when bot is active
- **Bot Status Check**: Only syncs when bot is running
- **Error Handling**: Graceful handling of connection issues
- **Logging**: Comprehensive logging for debugging

## Testing

Run the test script to verify functionality:
```bash
cd backend
python test_positions.py
```

The test script validates:
- Database operations
- DAS integration
- API endpoints
- Position parsing

## Configuration

### Sync Interval
The 10-second sync interval is configured in `scheduled_das_sync.py`:
```python
schedule.every(10).seconds.do(self.sync_positions_if_bot_running)
```

### Database Location
Positions are stored in the same SQLite database as trades:
- **File**: `trading_advisor.db`
- **Table**: `positions`

## Troubleshooting

### Common Issues
1. **No Positions Displayed**: Check DAS connection and bot status
2. **Sync Not Working**: Verify bot is running and DAS is connected
3. **Database Errors**: Check database file permissions and integrity

### Debug Information
- Check backend logs for sync status
- Verify DAS connection in bot status
- Test API endpoints manually
- Run test script for validation

## Future Enhancements

### Planned Features
- **Position Charts**: Visual representation of position performance
- **Historical Analysis**: Position performance over time
- **Risk Metrics**: Position sizing and risk calculations
- **Alerts**: Notifications for position changes
- **Backup/Restore**: Position data backup functionality

### Performance Optimizations
- **Caching**: Implement position data caching
- **Batch Operations**: Optimize database operations
- **Real-time Streaming**: WebSocket updates for live data
