import sys
import os
sys.path.append('.')

from get_gappers import get_gap_data_from_db, init_gap_table
from orb_tester import run_backtest, CFG
import pandas as pd
from pathlib import Path

def test_orb_with_gap_data():
    """Test the ORB backtester with gap data from the database"""
    
    # Initialize database table if needed
    print("🔧 Initializing gap_data table...")
    init_gap_table()
    print("✅ Database table ready!")
    
    # Get gap data from database for a specific date range
    print("📊 Fetching gap data from database...")
    
    # Use historical dates instead of future dates
    # Let's try to find some recent historical data
    gap_data = get_gap_data_from_db(start_date="2024-01-01", end_date="2024-12-31")
    
    if not gap_data:
        print("❌ No gap data found in database for 2024. Trying 2023...")
        gap_data = get_gap_data_from_db(start_date="2023-01-01", end_date="2023-12-31")
    
    if not gap_data:
        print("❌ No gap data found in database for 2023. Trying 2022...")
        gap_data = get_gap_data_from_db(start_date="2022-01-01", end_date="2022-12-31")
    
    if not gap_data:
        print("❌ No historical gap data found in database.")
        print("Please run test1.py with historical dates to populate the database.")
        print("Example: Modify test1.py to use dates like '2024-01-01' to '2024-01-31'")
        return
    
    # Convert to DataFrame and map column names to match ORB tester expectations
    df = pd.DataFrame(gap_data)
    
    # Map database columns to ORB tester expected columns
    column_mapping = {
        'date': 'date',
        'ticker': 'ticker', 
        'today_open': 'today_open',
        'today_close': 'today_close',
        'today_high': 'today_high',
        'today_low': 'today_low',
        'highest_dollar_volume_m': 'highest_dollar_volume_m'
    }
    
    # Select and rename columns
    gappers_df = df[list(column_mapping.keys())].rename(columns=column_mapping)
    
    print(f"📈 Found {len(gappers_df)} gap records for ORB testing")
    print(f"📅 Date range: {gappers_df['date'].min()} to {gappers_df['date'].max()}")
    print(f"🎯 Unique tickers: {gappers_df['ticker'].nunique()}")
    
    # Show sample of data
    print("\n📋 Sample gap data:")
    print(gappers_df.head())
    
    # Configure ORB tester for testing (use smaller sample first)
    test_config = CFG
    test_config.min_price = 1.0  # Minimum price filter
    test_config.min_dollar_volume_m = 1.0  # Minimum dollar volume filter
    
    # For testing, let's use a smaller sample to avoid API rate limits
    test_sample = gappers_df.head(3)  # Test with first 3 gaps
    print(f"\n🧪 Testing ORB strategy on {len(test_sample)} sample gaps...")
    print("Sample tickers and dates:")
    for _, row in test_sample.iterrows():
        print(f"  - {row['ticker']} on {row['date']}")
    
    try:
        # Run the ORB backtest
        trades_df, overall = run_backtest(test_sample, test_config)
        
        if trades_df.empty:
            print("❌ No trades were generated. This could be due to:")
            print("   - No breakouts occurred in the sample")
            print("   - API rate limits or data availability")
            print("   - Strategy filters being too restrictive")
            print("   - No intraday data available for these dates")
        else:
            print(f"✅ Generated {len(trades_df)} trades!")
            print("\n📊 Trade Summary:")
            print(trades_df[['date', 'ticker', 'entry', 'exit_price', 'pnl', 'R', 'reason']].head())
            
            print("\n📈 Overall Performance:")
            print(overall)
            
            # Save results
            out_dir = Path("./backtest_output")
            out_dir.mkdir(exist_ok=True)
            
            trades_path = out_dir / "orb_trades_test.csv"
            overall_path = out_dir / "orb_overall_test.csv"
            
            trades_df.to_csv(trades_path, index=False)
            overall.to_csv(overall_path, index=False)
            
            print(f"\n💾 Saved results to:")
            print(f"   Trades: {trades_path}")
            print(f"   Summary: {overall_path}")
    
    except Exception as e:
        print(f"❌ Error running ORB backtest: {e}")
        print("This could be due to:")
        print("   - API key issues")
        print("   - Network connectivity")
        print("   - Missing dependencies")
        print("   - Data format issues")

if __name__ == "__main__":
    test_orb_with_gap_data()
