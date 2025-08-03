from polygon import RESTClient
import os
import datetime
#from api_helper.config.api_keys import POLYGON_API_KEY
#from db.ticker_details_db import init_ticker_details_db, insert_or_update_ticker

def get_previous_close_price(ticker, polygon_client):
    """
    Fetches the last trading day's close price for the given ticker using Polygon aggregates endpoint.
    Returns the close price as a float, or None if not available.
    """
    # Get last trading day (skip weekends/holidays)
    today = datetime.datetime.now().date()
    last_trading_day = today - datetime.timedelta(days=1)
    
    # Skip weekends (Saturday = 5, Sunday = 6)
    while last_trading_day.weekday() >= 5:
        last_trading_day -= datetime.timedelta(days=1)
    
    date_str = last_trading_day.strftime("%Y-%m-%d")
    print(f"Using last trading day: {date_str} for {ticker}")
    
    try:
        aggs = polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=date_str,
            to=date_str
        )
        print("aggs: ", aggs)
        if aggs and len(aggs) > 0:
            print("aggs[0].close: ", aggs[0].close)
            return aggs[0].close
        else:
            print(f"No previous close found for {ticker}")
            return None
    except Exception as e:
        print(f"Error fetching previous close for {ticker}: {e}")
        return None


def get_gap_up_list():
    polygon_client = RESTClient("5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT")
    tickers = polygon_client.get_snapshot_direction(
        "stocks",
        direction="gainers",
        # include_otc=True,  # Uncomment if you want OTC
    )
    all_tickers = []
    total_tickers = 0
    below_1_count = 0
    cs_type_count = 0
    if tickers and isinstance(tickers, list):
        print("First item structure:", tickers[0], "type:", type(tickers[0]))
    for item in tickers:
        ticker = None
        if isinstance(item, dict):
            ticker = item.get("ticker") or item.get("symbol")
        elif hasattr(item, "ticker"):
            ticker = getattr(item, "ticker", None)
        elif hasattr(item, "symbol"):
            ticker = getattr(item, "symbol", None)
        if ticker:
            total_tickers += 1
            try:
                details = polygon_client.get_ticker_details(ticker)
                issue_type = details.type
                if issue_type == "CS":
                    cs_type_count += 1
                    price = get_previous_close_price(ticker, polygon_client)
                    if price is not None and price >= 1:
                        print(f"ticker: {ticker}, previous close: {price}")
                        all_tickers.append(ticker)
                    else:
                        below_1_count += 1
            except Exception as e:
                print(f"Error fetching details for {ticker}: {e}")
                continue
    print(f"Total tickers processed: {total_tickers}")
    print(f"Tickers with type == 'CS': {cs_type_count}")
    print(f"Tickers with price < $1: {below_1_count} / {total_tickers} processed.")
    print(f"Final output tickers count: {len(all_tickers)}")
    joined_list_str = ", ".join(str(item) for item in all_tickers)
    print("joined_list_str: ", joined_list_str)
    return joined_list_str

def get_ticker_details(tickers: str):
    polygon_client = RESTClient("5TcX1iTW6Fu2vysfbRbw60oW3PLWsdPT")
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    #rint("ticker_list: ", ticker_list)
    details_list = []
    #init_ticker_details_db() 
    #print("init_ticker_details_db called, and ticker_details.db is initialized....")
    for ticker in ticker_list:
        try:
            # Fetch ticker details from Polygon
            details = polygon_client.get_ticker_details(ticker)
            name = details.name
            sic_description = details.sic_description
            market_cap = details.market_cap
            shares_outstanding = details.share_class_shares_outstanding
            list_date = details.list_date
            
            details_dict = {
                "ticker": ticker,
                "name": name,
                "market_cap": market_cap,
                "sic_description": sic_description,
                "list_date": list_date,
                "shares_outstanding": shares_outstanding,
            }
            details_list.append(details_dict)
            #insert_or_update_ticker(details_dict)

        except Exception as e:
            print(f"Error fetching details for {ticker}: {e}")
    #print("Ticker details:", details_list)
    return details_list

if __name__ == "__main__":
    #get_gap_up_list()
    gainers = get_gap_up_list()
    get_ticker_details(gainers)

