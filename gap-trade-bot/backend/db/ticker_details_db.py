import sqlite3
import os

def get_db_path():
    db_dir = os.path.dirname(__file__)
    return os.path.join(db_dir, 'ticker_details.db')

def init_ticker_details_db():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS ticker_details (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            market_cap INTEGER,
            sic_description TEXT,
            list_date TEXT,
            share_class_shares_outstanding INTEGER,
            date TEXT
        )
    ''')
    
    # Add date column to existing table if it doesn't exist
    try:
        c.execute('ALTER TABLE ticker_details ADD COLUMN date TEXT')
        print("Added date column to existing table")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    conn.commit()
    conn.close()

def insert_or_update_ticker(details):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO ticker_details VALUES (?,?,?,?,?,?,?)
    ''', (
        details.get('ticker'),
        details.get('name'),
        details.get('market_cap'),
        details.get('sic_description'),
        details.get('list_date'),
        details.get('shares_outstanding'),
        details.get('date')
    ))
    conn.commit()
    conn.close()

def get_ticker_details_from_db(ticker):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('SELECT * FROM ticker_details WHERE ticker = ?', (ticker,))
    row = c.fetchone()
    conn.close()
    if row:
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))
    return None 