from polygon import RESTClient
from api_helper.polygon_api_get_historical_data import (
    analyze, get_gap_up_day_stats, get_daily_high_low_data,
    get_premarket_high_low_data, get_premarket_volume, count_vwap_crosses,
    get_intraday_volume_analysis, get_price_action_patterns, get_historical_pattern_analysis
)

API_KEY = "5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT"

def analyze_tool(tickers: str):
    """
    Enhanced analyze tool that provides comprehensive pattern recognition data.
    Accepts a comma-separated string of tickers, e.g. "AAPL,MSFT"
    """
    tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
    polygon_client = RESTClient(API_KEY)
    return analyze(tickers_list, polygon_client)

def get_gap_up_day_stats_tool(ticker: str):
    """
    Accepts a ticker symbol, e.g. "AAPL"
    """
    polygon_client = RESTClient(API_KEY)
    return get_gap_up_day_stats(ticker, polygon_client)

def get_daily_high_low_data_tool(ticker: str, date_str: str):
    """
    Accepts a ticker symbol and a date string in YYYY-MM-DD format, e.g. "2024-01-01"
    """
    polygon_client = RESTClient(API_KEY)
    return get_daily_high_low_data(ticker, polygon_client, date_str)

def get_premarket_high_low_data_tool(ticker: str, date_str: str):
    """
    Accepts a ticker symbol and a date string in YYYY-MM-DD format, e.g. "2024-01-01"
    """
    polygon_client = RESTClient(API_KEY)
    return get_premarket_high_low_data(ticker, polygon_client, date_str)

def get_premarket_volume_tool(ticker: str, date_str: str):
    """
    Accepts a ticker symbol and a date string in YYYY-MM-DD format, e.g. "2024-01-01"
    """
    polygon_client = RESTClient(API_KEY)
    return get_premarket_volume(polygon_client, ticker, date_str)

def count_vwap_crosses_tool(ticker: str, date_str: str):
    """
    Accepts a ticker symbol and a date string in YYYY-MM-DD format, e.g. "2024-01-01"
    """
    polygon_client = RESTClient(API_KEY)
    return count_vwap_crosses(polygon_client, ticker, date_str)

def get_intraday_volume_analysis_tool(ticker: str, date_str: str):
    """
    Analyzes volume patterns throughout the trading day for pattern recognition.
    Accepts a ticker symbol and a date string in YYYY-MM-DD format.
    """
    polygon_client = RESTClient(API_KEY)
    return get_intraday_volume_analysis(ticker, polygon_client, date_str)

def get_price_action_patterns_tool(ticker: str, date_str: str):
    """
    Analyzes price action patterns for pattern recognition.
    Accepts a ticker symbol and a date string in YYYY-MM-DD format.
    """
    polygon_client = RESTClient(API_KEY)
    return get_price_action_patterns(ticker, polygon_client, date_str)

def get_historical_pattern_analysis_tool(ticker: str, days_back: int = 30):
    """
    Analyzes historical patterns to determine stock behavior tendencies.
    Accepts a ticker symbol and number of days to analyze.
    """
    polygon_client = RESTClient(API_KEY)
    return get_historical_pattern_analysis(ticker, polygon_client, days_back)
