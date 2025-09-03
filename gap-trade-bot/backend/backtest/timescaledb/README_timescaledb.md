# TimescaleDB Setup Guide

## Prerequisites
- Docker Desktop installed and running
- DBeaver Community Edition installed

## Step 1: Start TimescaleDB

```bash
# Navigate to the timescaledb directory
cd timescaledb

# Start the TimescaleDB container
docker-compose up -d

# Verify it's running
docker-compose ps
```

## Step 2: Connect with DBeaver

1. **Open DBeaver**
2. **Create New Connection**:
   - Click "New Database Connection" (plug icon)
   - Select "PostgreSQL"
   - Click "Next"

3. **Connection Settings**:
   - **Host**: `localhost`
   - **Port**: `5432`
   - **Database**: `marketdata`
   - **Username**: `ts_user`
   - **Password**: `ts_pass`

4. **Test Connection**:
   - Click "Test Connection" to verify
   - Click "Finish" to save

## Step 3: Run the Setup Script

1. **Open SQL Editor**:
   - Right-click on your connection
   - Select "SQL Editor" → "New SQL Script"

2. **Load the Script**:
   - Open `setup_marketdata.sql` in DBeaver
   - Or copy-paste the SQL content

3. **Execute the Script**:
   - Click the "Execute SQL Script" button (▶️)
   - Or press `Ctrl+Enter`

## Step 4: Verify Setup

Run these queries to verify everything is working:

```sql
-- Check if TimescaleDB extension is enabled
SELECT * FROM pg_extension WHERE extname = 'timescaledb';

-- Check if hypertable was created
SELECT * FROM timescaledb_information.hypertables;

-- Check compression settings
SELECT * FROM timescaledb_information.compression_settings;

-- Check the materialized view
SELECT * FROM existing_ticker_day LIMIT 5;
```

## Step 5: Test Data Insertion

```sql
-- Insert some test data
INSERT INTO ohlcv_1m (ticker, ts, day, open, high, low, close, volume, vwap, source)
VALUES 
    ('AAPL', '2024-01-15 09:30:00+00', '2024-01-15', 150.00, 151.50, 149.80, 151.20, 1000000, 150.50, 'polygon'),
    ('AAPL', '2024-01-15 09:31:00+00', '2024-01-15', 151.20, 152.00, 151.10, 151.80, 1200000, 151.60, 'polygon'),
    ('TSLA', '2024-01-15 09:30:00+00', '2024-01-15', 250.00, 252.00, 249.50, 251.50, 800000, 250.80, 'polygon');

-- Query the data
SELECT * FROM ohlcv_1m ORDER BY ticker, ts;

-- Check the materialized view
SELECT * FROM existing_ticker_day;
```

## Troubleshooting

### Connection Issues
- **Port already in use**: Stop other PostgreSQL instances
- **Container not starting**: Check Docker logs with `docker-compose logs`

### Permission Issues
- Make sure you're connected as `ts_user`
- The user should have superuser privileges

### TimescaleDB Extension Issues
- Restart the container: `docker-compose restart`
- Check if the extension is loaded: `SELECT * FROM pg_extension;`

## Next Steps

Once setup is complete, you can:
1. **Import your gap data** from SQLite to TimescaleDB
2. **Store 1-minute intraday data** for ORB backtesting
3. **Use compression** to save storage space
4. **Scale horizontally** if needed

## Useful Commands

```bash
# Stop TimescaleDB
docker-compose down

# View logs
docker-compose logs timescaledb

# Backup database
docker exec timescaledb pg_dump -U ts_user marketdata > backup.sql

# Restore database
docker exec -i timescaledb psql -U ts_user marketdata < backup.sql
```
