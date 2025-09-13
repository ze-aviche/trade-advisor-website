#!/usr/bin/env python3
"""
Script to help diagnose and fix PostgreSQL shared memory issues
"""
import os
import subprocess
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_postgresql_config():
    """Check PostgreSQL configuration for memory settings"""
    print("🔍 Checking PostgreSQL configuration...")
    
    # Common PostgreSQL config file locations
    config_locations = [
        "/etc/postgresql/*/main/postgresql.conf",
        "/usr/local/var/postgres/postgresql.conf",
        "/opt/homebrew/var/postgres/postgresql.conf",
        "C:\\Program Files\\PostgreSQL\\*\\data\\postgresql.conf",
        "C:\\Program Files (x86)\\PostgreSQL\\*\\data\\postgresql.conf"
    ]
    
    print("📁 Common PostgreSQL config file locations:")
    for location in config_locations:
        print(f"   {location}")
    
    print("\n💡 To fix the shared memory issue, you need to:")
    print("1. Find your postgresql.conf file")
    print("2. Edit the following settings:")
    print("   max_locks_per_transaction = 256")
    print("   shared_buffers = 256MB")
    print("   max_connections = 100")
    print("3. Restart PostgreSQL/TimescaleDB")

def check_docker_compose():
    """Check if using Docker and provide Docker-specific fixes"""
    print("\n🐳 Checking for Docker setup...")
    
    docker_compose_file = "gap-trade-bot/backend/backtest/timescaledb/docker-compose.yml"
    if os.path.exists(docker_compose_file):
        print(f"✅ Found Docker Compose file: {docker_compose_file}")
        print("\n💡 For Docker setup, you can:")
        print("1. Restart the TimescaleDB container:")
        print("   cd gap-trade-bot/backend/backtest/timescaledb")
        print("   docker-compose restart")
        print("2. Or increase memory limits in docker-compose.yml:")
        print("   services:")
        print("     timescaledb:")
        print("       shm_size: 1gb")
        print("       environment:")
        print("         - POSTGRES_SHARED_BUFFERS=256MB")
        print("         - POSTGRES_MAX_LOCKS_PER_TRANSACTION=256")
    else:
        print("❌ No Docker Compose file found")

def check_environment_variables():
    """Check environment variables for database connection"""
    print("\n🔧 Checking environment variables...")
    
    required_vars = [
        "TIMESCALEDB_HOST",
        "TIMESCALEDB_PORT", 
        "TIMESCALEDB_NAME",
        "TIMESCALEDB_USER",
        "TIMESCALEDB_PASSWORD"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if "PASSWORD" in var:
                print(f"   {var}: {'*' * len(value)}")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: ❌ Not set")

def provide_quick_fixes():
    """Provide quick fixes for the shared memory issue"""
    print("\n🚀 Quick fixes to try:")
    print("=" * 40)
    
    print("1. Restart PostgreSQL/TimescaleDB:")
    print("   - If using Docker: docker-compose restart")
    print("   - If using system service: sudo systemctl restart postgresql")
    print("   - If using Homebrew: brew services restart postgresql")
    
    print("\n2. Reduce concurrent connections:")
    print("   - Close any other database connections")
    print("   - Use the lightweight test script instead")
    
    print("\n3. Check for long-running queries:")
    print("   - Connect to database and run: SELECT * FROM pg_stat_activity;")
    print("   - Kill any long-running queries if found")
    
    print("\n4. Increase system limits (Linux/Mac):")
    print("   - Check: ulimit -a")
    print("   - Increase if needed: ulimit -n 65536")

def test_lightweight_connection():
    """Test a lightweight database connection"""
    print("\n🧪 Testing lightweight connection...")
    
    try:
        import psycopg2
        from historical_ts_data import get_timescaledb_connection
        
        conn = get_timescaledb_connection()
        if conn:
            print("✅ Lightweight connection successful")
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result:
                    print("✅ Basic query successful")
            conn.close()
            return True
        else:
            print("❌ Lightweight connection failed")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    """Main function"""
    print("🔧 PostgreSQL Shared Memory Issue Diagnostic Tool")
    print("=" * 50)
    
    check_environment_variables()
    check_postgresql_config()
    check_docker_compose()
    provide_quick_fixes()
    
    print("\n" + "=" * 50)
    print("🧪 Testing lightweight connection...")
    if test_lightweight_connection():
        print("✅ Lightweight connection works! Use lightweight_test_ts_data.py")
    else:
        print("❌ Even lightweight connection fails. Check your database setup.")
    
    print("\n💡 Recommended next steps:")
    print("1. Try running: python lightweight_test_ts_data.py")
    print("2. If that fails, restart your database")
    print("3. If still failing, check your environment variables")

if __name__ == "__main__":
    main()
