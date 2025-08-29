-- TimescaleDB Market Data Setup Script
-- Run as marketdata superuser (ts_user)

-- 1) Enable extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2) Raw minute OHLCV table
CREATE TABLE IF NOT EXISTS ohlcv_1m (
    ticker TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,          -- exact minute timestamp, timezone-aware
    day DATE NOT NULL,                -- trading date (redundant but convenient)
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    vwap DOUBLE PRECISION,
    source TEXT,                      -- e.g., 'polygon'
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, ts)
);

-- 3) Convert to hypertable using (ticker, ts) as partition dimension
-- Use partition by ticker so each ticker chunk is independent
SELECT create_hypertable('ohlcv_1m', 'ts', 'ticker', 8, if_not_exists => TRUE);

-- 4) Indexes for common access patterns
CREATE INDEX IF NOT EXISTS idx_ohlcv_1m_ticker_day ON ohlcv_1m (ticker, day);
CREATE INDEX IF NOT EXISTS idx_ohlcv_1m_day ON ohlcv_1m (day);

-- 5) Compression policy (5 years)
-- First enable compression
ALTER TABLE ohlcv_1m 
  SET (timescaledb.compress, timescaledb.compress_segmentby = 'ticker');

-- Compress data older than 5 years automatically
SELECT add_compression_policy('ohlcv_1m', compress_after => INTERVAL '5 years'); 

-- Optional: retention (e.g., drop data older than 20 years if you don't want infinite growth)
-- SELECT add_retention_policy('ohlcv_1m', INTERVAL '20 years');

-- 6) Utility: check existing rows for a (ticker, date) quickly
CREATE MATERIALIZED VIEW IF NOT EXISTS existing_ticker_day AS
SELECT ticker, day, count(*) as cnt
FROM ohlcv_1m
GROUP BY ticker, day;

-- 7) Create a refresh function for the materialized view
CREATE OR REPLACE FUNCTION refresh_existing_ticker_day()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW existing_ticker_day;
END;
$$ LANGUAGE plpgsql;

-- 8) Show setup confirmation
SELECT 'TimescaleDB Market Data Setup Complete!' as status;
SELECT 'Table: ohlcv_1m' as table_name, 'Hypertable with compression' as description;
SELECT 'Materialized View: existing_ticker_day' as view_name, 'For quick ticker/day lookups' as description;
