from polygon import RESTClient
from polygon_api_get_historical_data import analyze, get_gap_up_day_stats

# Replace with your actual Polygon API key
API_KEY = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"

def main():
    polygon_client = RESTClient(API_KEY)
    tickers = ["LIDR", "ARX", "MFH"]  # You can use any tickers you want to test

    # Test the analyze function
    print("Testing analyze() for multiple tickers:")
    results = analyze(tickers, polygon_client)
    for ticker, gap_up_days in results.items():
        print(f"\nResults for {ticker}:")
        for day in gap_up_days:
            print(day)

    # Test get_gap_up_day_stats for a single ticker
    print("\nTesting get_gap_up_day_stats for LIDR:")
    stats = get_gap_up_day_stats("LIDR", polygon_client)
    for day in stats:
        print(day)

if __name__ == "__main__":
    main() 