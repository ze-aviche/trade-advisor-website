#!/usr/bin/env python3
"""
SQLite Table Checker for Windows
Helps you inspect SQLite databases and their tables
"""
import sqlite3
import os
import sys
from pathlib import Path

def list_tables(db_path):
    """List all tables in a SQLite database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n📊 Database: {os.path.basename(db_path)}")
        print(f"📍 Path: {db_path}")
        print(f"📋 Tables found: {len(tables)}")
        print("-" * 50)
        
        if not tables:
            print("No tables found in this database.")
            return
        
        for i, (table_name,) in enumerate(tables, 1):
            print(f"{i}. {table_name}")
            
            # Get row count for each table
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"   └─ Rows: {count:,}")
            except Exception as e:
                print(f"   └─ Error getting row count: {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error accessing database {db_path}: {e}")

def show_table_schema(db_path, table_name):
    """Show the schema for a specific table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        print(f"\n🔍 Schema for table '{table_name}' in {os.path.basename(db_path)}:")
        print("-" * 60)
        print(f"{'Column':<20} {'Type':<15} {'Not Null':<10} {'Primary Key':<12}")
        print("-" * 60)
        
        for col in columns:
            cid, name, type_, notnull, dflt_value, pk = col
            print(f"{name:<20} {type_:<15} {'Yes' if notnull else 'No':<10} {'Yes' if pk else 'No':<12}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting schema for {table_name}: {e}")

def show_sample_data(db_path, table_name, limit=5):
    """Show sample data from a table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Get sample data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        
        print(f"\n📄 Sample data from '{table_name}' (showing {len(rows)} rows):")
        print("-" * 80)
        
        if rows:
            # Print column headers
            print(" | ".join(f"{col:<15}" for col in columns))
            print("-" * 80)
            
            # Print data rows
            for row in rows:
                print(" | ".join(f"{str(val):<15}" for val in row))
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting data from {table_name}: {e}")

def main():
    """Main function to check databases"""
    # Common database paths in your project
    project_root = Path("C:/Users/avina/OneDrive/Documents/Projects/trade-advisor-website/gap-trade-bot/backend")
    
    databases = [
        project_root / "trading_advisor.db",
        project_root / "bot" / "trading_positions.db",
        project_root / "bot" / "strategies" / "gap_up_history.db",
        project_root / "bot" / "data" / "gap_up_cache.db",
        project_root / "db" / "ticker_details.db"
    ]
    
    print("🔍 SQLite Database Table Checker")
    print("=" * 50)
    
    # Check each database
    for db_path in databases:
        if db_path.exists():
            list_tables(str(db_path))
        else:
            print(f"\n❌ Database not found: {db_path}")
    
    # Interactive mode
    print("\n" + "=" * 50)
    print("🔧 Interactive Mode")
    print("Enter database path and table name to inspect:")
    
    while True:
        try:
            db_input = input("\nEnter database path (or 'quit' to exit): ").strip()
            if db_input.lower() == 'quit':
                break
            
            if not os.path.exists(db_input):
                print("❌ Database file not found!")
                continue
            
            list_tables(db_input)
            
            table_name = input("Enter table name to inspect (or press Enter to skip): ").strip()
            if table_name:
                show_table_schema(db_input, table_name)
                show_sample_data(db_input, table_name)
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
