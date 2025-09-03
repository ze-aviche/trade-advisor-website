# Gap Data Market Data Ingestion Tool

## Overview

`ingest_min_bars_for_gappers_fixed.py` is a Python script designed to fetch and ingest 1-minute OHLCV (Open, High, Low, Close, Volume) market data for gap trading tickers into a TimescaleDB database. The script queries a SQLite database containing gap trading data, fetches historical minute bars from Polygon.io API, and efficiently stores them in TimescaleDB for backtesting and analysis.

## Purpose

This tool serves as a bridge between:
- **Source**: SQLite database containing gap trading opportunities (`gap_data` table)
- **API**: Polygon.io for historical market data
- **Destination**: TimescaleDB for time-series market data storage

## Features

- **Efficient Data Fetching**: Uses Polygon.io API to retrieve 1-minute bars for gap tickers
- **Smart Caching**: Implements parquet file caching to avoid redundant API calls
- **Concurrent Processing**: Multi-threaded execution for faster data ingestion
- **Rate Limit Handling**: Built-in retry logic and rate limit compliance
- **Conflict Resolution**: Handles duplicate data gracefully with ON CONFLICT DO NOTHING
- **Flexible Filtering**: Date range and limit options for targeted data ingestion

## Prerequisites

### Required Software
- Python 3.7+
- PostgreSQL with TimescaleDB extension
- Access to Polygon.io API

### Required Python Packages
```bash
pip install -r requirements.txt
```

Key dependencies:
- `psycopg2` - PostgreSQL adapter
- `pandas` - Data manipulation
- `requests` - HTTP requests
- `tqdm` - Progress bars

### Database Setup
1. **TimescaleDB**: Must have the `ohlcv_1m` table with proper schema
2. **SQLite**: Must contain the `gap_data` table with ticker and date information

## Configuration

### Environment Variables
Set these environment variables or they will use defaults:

```bash
export POLYGON_API_KEY="your_polygon_api_key"
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="marketdata"
export DB_USER="ts_user"
export DB_PASS="ts_pass"
```

### Script Configuration
Key parameters in the script:
- `MAX_WORKERS`: Number of concurrent threads (default: 4)
- `SLEEP_BETWEEN_CALLS`: Delay between API calls in seconds (default: 1.0)
- `MAX_RETRIES`: Maximum retry attempts for failed API calls (default: 5)
- `PARQUET_CACHE_DIR`: Directory for caching fetched data (default: "./parquet_cache")

## Usage

### Basic Usage
```bash
python ingest_min_bars_for_gappers_fixed.py
```

### Advanced Usage with Filters
```bash
# Process specific date range
python ingest_min_bars_for_gappers_fixed.py --from-date 2024-01-01 --to-date 2024-01-31

# Limit number of ticker-date combinations
python ingest_min_bars_for_gappers_fixed.py --limit 1000

# Clean up cache files after processing
python ingest_min_bars_for_gappers_fixed.py --cleanup-cache

# Combine options
python ingest_min_bars_for_gappers_fixed.py --from-date 2024-01-01 --to-date 2024-01-31 --limit 5000 --cleanup-cache
```

### Command Line Arguments
- `--from-date`: Start date in YYYY-MM-DD format
- `--to-date`: End date in YYYY-MM-DD format  
- `--limit`: Maximum number of ticker-date combinations to process
- `--cleanup-cache`: Remove all parquet cache files after processing

## How It Works

### 1. Data Source Query
The script queries the SQLite `gap_data` table to get ticker-date combinations that need market data.

### 2. Duplicate Detection
Checks TimescaleDB for existing data to avoid redundant API calls and database insertions.

### 3. Data Fetching
- Uses Polygon.io API to fetch 1-minute bars for each ticker-date combination
- Implements intelligent caching with parquet files
- Handles API rate limits and retries

### 4. Data Processing
- Normalizes data format (timestamp conversion, column renaming)
- Ensures data types match database schema
- Handles missing VWAP data gracefully

### 5. Database Insertion
- Uses fast COPY operations for bulk insertion
- Falls back to individual INSERT statements with conflict resolution
- Commits data in batches for efficiency

### 6. Progress Tracking
- Real-time progress bars for monitoring
- Detailed logging of successes, failures, and warnings
- Summary statistics upon completion

## Output Schema

The script inserts data into the `ohlcv_1m` table with the following structure:

| Column | Type | Description |
|--------|------|-------------|
| ticker | text | Stock ticker symbol |
| ts | timestamp | Timestamp (UTC) |
| day | date | Date partition |
| open | numeric | Opening price |
| high | numeric | High price |
| low | numeric | Low price |
| close | numeric | Closing price |
| volume | integer | Trading volume |
| vwap | numeric | Volume-weighted average price |
| source | text | Data source identifier |

## Performance Considerations

- **Concurrency**: Limited to 4 workers to comply with API rate limits
- **Caching**: Parquet files reduce redundant API calls
- **Batch Operations**: Uses COPY for fast bulk insertion
- **Memory Management**: Processes data in chunks to avoid memory issues

## Error Handling

- **API Failures**: Automatic retry with exponential backoff
- **Rate Limiting**: Respects Retry-After headers
- **Database Conflicts**: Graceful handling of duplicate data
- **Network Issues**: Timeout handling and connection retries

## Monitoring and Logging

The script provides comprehensive feedback:
- Progress bars for overall completion
- Individual ticker processing status
- Error details with stack traces
- Summary statistics at completion
- Cache file management information

## Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure `POLYGON_API_KEY` is set and valid
2. **Database Connection**: Verify TimescaleDB credentials and connectivity
3. **Rate Limiting**: Script automatically handles this, but may slow down processing
4. **Memory Issues**: Reduce `MAX_WORKERS` if experiencing memory problems

### Debug Mode
For detailed debugging, the script includes extensive logging and error reporting.

## Integration

This script is part of a larger gap trading system:
- **Input**: Gap data from `test1.py` or similar gap detection tools
- **Output**: Market data in TimescaleDB for backtesting (`orb_tester.py`, etc.)
- **Workflow**: Run after gap detection, before backtesting

## Future Enhancements

Potential improvements:
- Support for additional data sources
- Real-time data streaming capabilities
- Enhanced error recovery mechanisms
- Performance optimization for larger datasets
- Integration with other market data providers

## Support

For issues or questions:
1. Check the logs for detailed error information
2. Verify all prerequisites are met
3. Ensure API keys and database credentials are correct
4. Review the configuration parameters for your use case
