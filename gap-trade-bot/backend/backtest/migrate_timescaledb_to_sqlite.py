"""
Migrate ohlcv_1m from TimescaleDB → SQLite (ohlcv_1m.db, separate file).

Uses a single streaming server-side cursor so Postgres sends all 11M rows in
one pass — no per-day round-trips. Writes to a dedicated ohlcv_1m.db to avoid
locking conflicts with the running Flask app.

Run from the backtest/ directory (venv active, Docker running):
    python migrate_timescaledb_to_sqlite.py
"""
import os
import sqlite3
import argparse
from datetime import datetime

try:
    import psycopg2
except Exception as _e:
    raise SystemExit(f"Cannot import psycopg2: {_e}\nRun: pip install psycopg2-binary")

# ── Config ─────────────────────────────────────────────────────────────────────
PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = int(os.getenv("DB_PORT", "5432"))
PG_NAME = os.getenv("DB_NAME", "marketdata")
PG_USER = os.getenv("DB_USER", "ts_user")
PG_PASS = os.getenv("DB_PASS", "ts_pass")

# Separate file — avoids locking the main trading_advisor.db while Flask runs.
# The backtest engine reads from this file directly.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_PATH = os.path.join(BACKEND_DIR, "ohlcv_1m.db")

FETCH_SIZE  = 100_000   # rows fetched from Postgres per round-trip
COMMIT_EVERY = 500_000  # rows per SQLite commit


def get_pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_NAME,
        user=PG_USER, password=PG_PASS,
        connect_timeout=10,
    )


def open_sqlite(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-262144")   # 256 MB
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def ensure_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1m (
            ticker  TEXT    NOT NULL,
            ts      TEXT    NOT NULL,
            day     TEXT    NOT NULL,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  INTEGER,
            vwap    REAL,
            source  TEXT,
            PRIMARY KEY (ticker, ts)
        )
    """)
    # Drop secondary indexes before bulk insert — rebuilt at the end
    conn.execute("DROP INDEX IF EXISTS idx_ohlcv_ticker_day")
    conn.execute("DROP INDEX IF EXISTS idx_ohlcv_day")
    conn.commit()


def rebuild_indexes(conn: sqlite3.Connection):
    print("Building indexes…", flush=True)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_day ON ohlcv_1m (ticker, day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_day        ON ohlcv_1m (day)")
    conn.commit()
    print("Indexes ready.")


def count_rows(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM ohlcv_1m").fetchone()[0]


def count_pg_rows(pg_conn) -> int:
    with pg_conn.cursor() as cur:
        cur.execute("SET max_parallel_workers_per_gather = 0")
        cur.execute("SELECT COUNT(*) FROM ohlcv_1m")
        return cur.fetchone()[0]


def get_done_days(conn: sqlite3.Connection) -> set:
    return {r[0] for r in conn.execute("SELECT DISTINCT day FROM ohlcv_1m").fetchall()}


def migrate(pg_conn, sqlite_conn: sqlite3.Connection, total_pg: int):
    done_days = get_done_days(sqlite_conn)
    already   = count_rows(sqlite_conn)
    print(f"Rows already in SQLite : {already:,}")
    print(f"Days already done      : {len(done_days)}")

    # Build WHERE clause to skip days already migrated
    if done_days:
        placeholders = ",".join(f"'{d}'" for d in sorted(done_days))
        where = f"WHERE day NOT IN ({placeholders})"
    else:
        where = ""

    inserted = 0
    batch    = []
    start    = datetime.now()

    # Disable parallel workers before opening the named cursor
    with pg_conn.cursor() as setup:
        setup.execute("SET max_parallel_workers_per_gather = 0")

    # One server-side cursor streams the whole table — no per-day round-trips
    with pg_conn.cursor(name="stream_cur", withhold=False) as cur:
        cur.itersize = FETCH_SIZE
        cur.execute(
            f"SELECT ticker, ts, day, open, high, low, close, volume, vwap, source "
            f"FROM ohlcv_1m {where} ORDER BY day, ticker, ts"
        )

        while True:
            rows = cur.fetchmany(FETCH_SIZE)
            if not rows:
                break

            for ticker, ts, day_, open_, high, low, close, volume, vwap, source in rows:
                ts_str  = ts.isoformat()   if ts  is not None else None
                day_str = day_.isoformat() if hasattr(day_, "isoformat") else str(day_)
                batch.append((ticker, ts_str, day_str, open_, high, low, close,
                               volume, vwap, source))

            inserted += len(rows)

            if len(batch) >= COMMIT_EVERY:
                sqlite_conn.executemany(
                    "INSERT OR IGNORE INTO ohlcv_1m "
                    "(ticker,ts,day,open,high,low,close,volume,vwap,source) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )
                sqlite_conn.commit()
                batch = []
                elapsed = (datetime.now() - start).total_seconds()
                rate    = inserted / elapsed if elapsed else 1
                eta_m   = ((total_pg - already - inserted) / rate) / 60
                print(f"  {inserted + already:,} / {total_pg:,} rows "
                      f"({(inserted+already)/total_pg*100:.1f}%)  "
                      f"{rate:,.0f} rows/s  ETA {eta_m:.1f} min", flush=True)

    # flush remainder
    if batch:
        sqlite_conn.executemany(
            "INSERT OR IGNORE INTO ohlcv_1m "
            "(ticker,ts,day,open,high,low,close,volume,vwap,source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        sqlite_conn.commit()

    elapsed = (datetime.now() - start).total_seconds()
    rate    = inserted / elapsed if elapsed else 1
    print(f"\nStreamed {inserted:,} rows in {elapsed:.0f}s  ({rate:,.0f} rows/s)")
    rebuild_indexes(sqlite_conn)
    print(f"Final row count: {count_rows(sqlite_conn):,}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default=SQLITE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"SQLite target : {args.sqlite}")
    print(f"PostgreSQL    : {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_NAME}")
    print()

    try:
        pg_conn = get_pg_conn()
        print("Connected to TimescaleDB ✓")
    except Exception as e:
        raise SystemExit(f"Cannot connect: {e}")

    if args.dry_run:
        print(f"TimescaleDB rows : {count_pg_rows(pg_conn):,}")
        pg_conn.close()
        return

    sqlite_conn = open_sqlite(args.sqlite)
    ensure_table(sqlite_conn)

    total_pg = count_pg_rows(pg_conn)
    print(f"Rows in TimescaleDB   : {total_pg:,}")

    migrate(pg_conn, sqlite_conn, total_pg)

    pg_conn.close()
    sqlite_conn.close()


if __name__ == "__main__":
    main()
