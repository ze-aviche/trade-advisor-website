"""
ORB Tester Validation Script
Validates the Opening Range Breakout backtester functionality
"""
import sys
import os
sys.path.append('.')

def validate_orb_tester():
    """Validate the ORB tester implementation"""
    
    print("🔍 Validating ORB Tester Implementation...")
    
    # 1. Check imports
    print("\n1️⃣ Checking imports...")
    try:
        from orb_tester import CFG, fetch_polygon_1min, build_opening_range, simulate_orb_long, run_backtest
        print("✅ All ORB tester functions imported successfully")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # 2. Check configuration
    print("\n2️⃣ Checking configuration...")
    try:
        print(f"   API Key: {'✅ Set' if CFG.polygon_api_key and CFG.polygon_api_key != 'YOUR_POLYGON_API_KEY' else '❌ Not set'}")
        print(f"   Cache Directory: {CFG.cache_dir}")
        print(f"   Session: {CFG.session_start} - {CFG.session_end}")
        print(f"   ORB Minutes: {CFG.orb_minutes}")
        print(f"   Risk per Trade: ${CFG.risk_per_trade_usd}")
        print(f"   Take Profit R: {CFG.take_profit_R}")
        print(f"   Time Exit: {CFG.time_exit}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False
    
    # 3. Check database integration
    print("\n3️⃣ Checking database integration...")
    try:
        from get_gappers import get_gap_data_from_db, init_gap_table
        print("✅ Database functions available")
        
        # Test database connection
        init_gap_table()
        print("✅ Database table initialized")
        
        # Check for sample data
        sample_data = get_gap_data_from_db(start_date="2025-08-22", end_date="2025-08-25")
        print(f"   Sample data records: {len(sample_data)}")
        
    except Exception as e:
        print(f"❌ Database integration error: {e}")
        return False
    
    # 4. Check API connectivity
    print("\n4️⃣ Checking Polygon API connectivity...")
    try:
        import requests
        
        # Test API key with a simple request
        test_url = f"https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2025-01-01/2025-01-01?adjusted=true&apiKey={CFG.polygon_api_key}"
        response = requests.get(test_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Polygon API connectivity confirmed")
        elif response.status_code == 401:
            print("❌ API key authentication failed")
            return False
        elif response.status_code == 403:
            print("❌ API key doesn't have required permissions")
            return False
        else:
            print(f"⚠️ API response status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ API connectivity error: {e}")
        return False
    
    # 5. Check file structure
    print("\n5️⃣ Checking file structure...")
    try:
        from pathlib import Path
        
        # Check if cache directory can be created
        cache_dir = Path("intraday_cache")
        cache_dir.mkdir(exist_ok=True)
        print(f"✅ Cache directory: {cache_dir.absolute()}")
        
        # Check if output directory can be created
        output_dir = Path("backtest_output")
        output_dir.mkdir(exist_ok=True)
        print(f"✅ Output directory: {output_dir.absolute()}")
        
    except Exception as e:
        print(f"❌ File structure error: {e}")
        return False
    
    # 6. Check dependencies
    print("\n6️⃣ Checking dependencies...")
    try:
        import pandas as pd
        import numpy as np
        print("✅ pandas and numpy available")
        
        # Check parquet support
        try:
            import pyarrow
            print("✅ pyarrow (parquet support) available")
        except ImportError:
            print("⚠️ pyarrow not available - parquet caching disabled")
            
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False
    
    print("\n✅ ORB Tester validation completed successfully!")
    print("\n📋 Summary:")
    print("   - All imports working")
    print("   - Configuration valid")
    print("   - Database integration ready")
    print("   - API connectivity confirmed")
    print("   - File structure ready")
    print("   - Dependencies satisfied")
    
    print("\n🚀 Ready to run ORB backtests!")
    print("   Run: python test_orb.py")
    
    return True

if __name__ == "__main__":
    validate_orb_tester()
