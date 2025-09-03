# ORB Tester with TimescaleDB

This is an updated version of the Opening-Range Breakout (ORB) backtester that uses your TimescaleDB `ohlcv_1m` data instead of fetching from Polygon API.

## Key Changes

- **Replaced Polygon API calls** with direct TimescaleDB queries
- **No external API rate limits** or API key requirements
- **Faster data access** using your local TimescaleDB instance
- **Uses your historical data** from 2005 onwards

## Prerequisites

1. **TimescaleDB running** with your `ohlcv_m` table populated
2. **Python dependencies** installed (see `requirements_backtest.txt`)
3. **Database connection** configured

## Setup

### 1. Install Dependencies

```bash
cd gap-trade-bot/backend/backtest
pip install -r requirements_backtest.txt
```

### 2. Configure Database Connection

Copy the environment template and configure your TimescaleDB settings:

```bash
cp timescaledb_env_template.txt .env
# Edit .env with your actual database credentials
```

Or set environment variables directly:

```bash
export TIMESCALEDB_HOST=localhost
export TIMESCALEDB_PORT=5432
export TIMESCALEDB_NAME=marketdata
export TIMESCALEDB_USER=ts_user
export TIMESCALEDB_PASSWORD=ts_password
```

### 3. Test Connection

Run the connection test to verify everything works:

```bash
python test_timescaledb_connection.py
```

## Usage

### Basic Usage

```python
from orb_tester import run_backtest, CFG

# Your gappers DataFrame
gappers_df = pd.DataFrame([
    {"date": "2025-01-15", "ticker": "AAPL", "today_open": 150.0},
    {"date": "2025-01-15", "ticker": "MSFT", "today_open": 300.0},
])

# Run backtest
trades_df, overall = run_backtest(gappers_df, CFG)
```

### Configuration

The `Config` class allows you to customize:

- **Database connection** settings
- **Trading session** times (default: 09:30-16:00)
- **Opening range** window (default: 5 minutes)
- **Risk management** parameters
- **Exit rules** and timing

```python
from orb_tester import Config

# Custom configuration
cfg = Config(
    orb_minutes=10,           # 10-minute opening range
    risk_per_trade_usd=200,   # $200 risk per trade
    take_profit_R=3.0,        # 3R take profit
    time_exit="12:00:00"      # Exit by noon
)
```

## Data Requirements

Your `ohlcv_1m` table should have this structure:

```sql
CREATE TABLE ohlcv_1m (
    ticker TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    day DATE NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    vwap DOUBLE PRECISION,
    source TEXT,
    created_at TIMESTAMPTZ
);
```

## How It Works

1. **Data Fetching**: Queries TimescaleDB for 1-minute bars directly from the `ohlcv_1m` table
2. **Opening Range**: Calculates ORH/ORL from first 5 minutes of trading
3. **Breakout Detection**: Looks for first close above opening range high
4. **Position Management**: Simulates entry, stop-loss, take-profit, and time-based exits
5. **Results**: Returns detailed trade data and summary statistics

## Performance Benefits

- **No API rate limiting** - process as many tickers/dates as needed
- **Local data access** - faster than external API calls
- **Batch processing** - efficient for large backtests
- **Historical depth** - access to your full 2005+ dataset

## Troubleshooting

### Connection Issues

- Verify TimescaleDB is running: `docker ps` (if using Docker)
- Check credentials in `.env` file
- Ensure database `marketdata` exists

### Data Issues

- Verify `ohlcv_1m` table exists and has data
- Check date format in your gappers DataFrame
- Ensure ticker symbols match between gappers and TimescaleDB

### Performance Issues

- Consider adding indexes on `(ticker, ts)` in TimescaleDB
- Use smaller date ranges for initial testing
- Monitor database query performance

## Example Output

The backtester generates:

1. **Trades DataFrame**: Individual trade details with entry/exit times, P&L, R-multiples
2. **Overall Summary**: Aggregate statistics across all trades
3. **Daily Breakdown**: Performance metrics by trading date

## Next Steps

- **Validate strategy** with historical data before live trading
- **Optimize parameters** using walk-forward analysis
- **Add filters** for volume, volatility, or other criteria
- **Extend functionality** with additional exit rules or position sizing
