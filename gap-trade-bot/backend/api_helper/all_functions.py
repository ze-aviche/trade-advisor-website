# app.py (Full content with download route)
from flask import Flask, request, render_template, send_file
import pandas as pd
import pytz
from datetime import datetime, time, timedelta, timezone
import os
from polygon import RESTClient
import io

from database.dbmodel import db, GapUpResult

# Initialize the Flask application
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///gap_up_analysis.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    print("Creating tables...")
    db.create_all()


# Initialize the Polygon client (assuming POLYGON_API_KEY is already in userdata)
try:
    polygon_client = RESTClient(os.environ.get("POLYGON_API_KEY"))
except Exception as e:
    print(f"Error initializing Polygon client: {e}")
    polygon_client = None  # Handle the case where the client cannot be initialized

# Dictionary to store results for potential download
all_tickers_gap_up_results = {}


# Include the necessary functions directly
def count_vwap_crosses(polygon_client, ticker, date):
    """
    Fetches 2-minute bar data for a given ticker and date and counts VWAP crosses.

    Args:
        polygon_client: The initialized Polygon.io RESTClient.
        ticker (str): The stock ticker symbol.
        date (str): The date in 'YYYY-MM-DD' format.

    Returns:
        int: The number of times the price crossed the VWAP.
    """
    try:
        # Fetch 2-minute bar data
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=2,
            timespan='minute',
            from_=date,
            to=date,
            # adjusted='true',
            limit=50000  # Increased limit for potentially more bars
        )
        aggs_list = list(aggs_data)
    except Exception as e:
        print(f"Error fetching 2-minute bar data for {ticker} on {date}: {e}")
        return None  # Return None on error

    if not aggs_list:
        return 0  # No data means no crosses

    cross_count = 0
    # Initialize previous close and vwap with the first bar's data
    previous_close = aggs_list[0].close
    previous_vwap = aggs_list[0].vwap

    for i in range(1, len(aggs_list)):
        current_bar = aggs_list[i]
        current_close = current_bar.close
        current_vwap = current_bar.vwap

        # Check for a cross: price goes from below VWAP to above, or vice versa
        if previous_close is not None and current_close is not None and previous_vwap is not None and current_vwap is not None:
            if (previous_close < previous_vwap and current_close > current_vwap) or \
                    (previous_close > previous_vwap and current_close < current_vwap):
                cross_count += 1

        previous_close = current_close
        previous_vwap = current_vwap

    return cross_count


def get_premarket_high_low_data(ticker, polygon_client, date_str):
    """
    Fetches the daily high price, low price, and their timestamps for a given ticker and date
    within the standard trading hours (9:30 AM to 4:00 PM EST).

    Args:
        ticker (str): The stock ticker symbol.
        polygon_client: The initialized Polygon.io RESTClient.
        date_str (str): The date in 'YYYY-MM-DD' format.

    Returns:
        tuple: A tuple containing:
            - max_high (float or None): The maximum high price for the day within trading hours.
            - high_timestamp_est (str or None): The timestamp (HH:MM EST) of the daily high within trading hours.
            - min_low (float or None): The minimum low price for the day within trading hours.
            - low_timestamp_est (str or None): The timestamp (HH:MM EST) of the daily low within trading hours.
            or (None, None, None, None) if data is not available or an error occurs.
    """
    try:
        est_timezone = pytz.timezone('America/New_York')

        # Define the start and end times in EST for the trading day
        start_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 04:00", '%Y-%m-%d %H:%M'))
        end_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 9:30", '%Y-%m-%d %H:%M'))

        # Convert EST datetimes to UTC timestamps (in milliseconds) for the API call
        start_timestamp_utc_ms = int(start_datetime_est.timestamp() * 1000)
        end_timestamp_utc_ms = int(end_datetime_est.timestamp() * 1000)

        # Fetch 1-minute bar data for the specified time range
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='minute',
            from_=start_timestamp_utc_ms,
            to=end_timestamp_utc_ms,
            limit=50000  # Increased limit to get all bars for the specified range
        )
        aggs_list = list(aggs_data)

        if not aggs_list:
            print(f"No data available for {ticker} between 4:00 AM and 9:30 AM EST on {date_str}")
            return None, None, None, None

        # Find the maximum high price and its corresponding timestamp
        max_high = -1
        high_timestamp = None
        min_low = float('inf')
        low_timestamp = None

        for bar in aggs_list:
            if bar.high > max_high:
                max_high = bar.high
                high_timestamp = bar.timestamp

            if bar.low < min_low:
                min_low = bar.low
                low_timestamp = bar.timestamp

        high_timestamp_est = None
        if high_timestamp:
            high_datetime_utc = datetime.fromtimestamp(high_timestamp / 1000, tz=pytz.utc)
            high_datetime_est = high_datetime_utc.astimezone(est_timezone)
            high_timestamp_est = high_datetime_est.strftime('%H:%M')

        low_timestamp_est = None
        if low_timestamp:
            low_datetime_utc = datetime.fromtimestamp(low_timestamp / 1000, tz=pytz.utc)
            low_datetime_est = low_datetime_utc.astimezone(est_timezone)
            low_timestamp_est = low_datetime_est.strftime('%H:%M')

        return max_high, high_timestamp_est, min_low, low_timestamp_est

    except Exception as e:
        print(f"Error fetching data for {ticker} on {date_str} between 4:00 AM and 9:30 AM EST: {e}")
        return None, None, None, None


def get_daily_high_low_data(ticker, polygon_client, date_str):
    """
    Fetches the daily high price, low price, and their timestamps for a given ticker and date
    within the standard trading hours (9:30 AM to 4:00 PM EST).

    Args:
        ticker (str): The stock ticker symbol.
        polygon_client: The initialized Polygon.io RESTClient.
        date_str (str): The date in 'YYYY-MM-DD' format.

    Returns:
        tuple: A tuple containing:
            - max_high (float or None): The maximum high price for the day within trading hours.
            - high_timestamp_est (str or None): The timestamp (HH:MM EST) of the daily high within trading hours.
            - min_low (float or None): The minimum low price for the day within trading hours.
            - low_timestamp_est (str or None): The timestamp (HH:MM EST) of the daily low within trading hours.
            or (None, None, None, None) if data is not available or an error occurs.
    """
    try:
        est_timezone = pytz.timezone('America/New_York')

        # Define the start and end times in EST for the trading day
        start_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 09:30", '%Y-%m-%d %H:%M'))
        end_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 16:00", '%Y-%m-%d %H:%M'))

        # Convert EST datetimes to UTC timestamps (in milliseconds) for the API call
        start_timestamp_utc_ms = int(start_datetime_est.timestamp() * 1000)
        end_timestamp_utc_ms = int(end_datetime_est.timestamp() * 1000)

        # Fetch 1-minute bar data for the specified time range
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='minute',
            from_=start_timestamp_utc_ms,
            to=end_timestamp_utc_ms,
            limit=50000  # Increased limit to get all bars for the specified range
        )
        aggs_list = list(aggs_data)

        if not aggs_list:
            print(f"No data available for {ticker} between 9:30 AM and 4:00 PM EST on {date_str}")
            return None, None, None, None

        # Find the maximum high price and its corresponding timestamp
        max_high = -1
        high_timestamp = None
        min_low = float('inf')
        low_timestamp = None

        for bar in aggs_list:
            if bar.high > max_high:
                max_high = bar.high
                high_timestamp = bar.timestamp

            if bar.low < min_low:
                min_low = bar.low
                low_timestamp = bar.timestamp

        high_timestamp_est = None
        if high_timestamp:
            high_datetime_utc = datetime.fromtimestamp(high_timestamp / 1000, tz=pytz.utc)
            high_datetime_est = high_datetime_utc.astimezone(est_timezone)
            high_timestamp_est = high_datetime_est.strftime('%H:%M')

        low_timestamp_est = None
        if low_timestamp:
            low_datetime_utc = datetime.fromtimestamp(low_timestamp / 1000, tz=pytz.utc)
            low_datetime_est = low_datetime_utc.astimezone(est_timezone)
            low_timestamp_est = low_datetime_est.strftime('%H:%M')

        return max_high, high_timestamp_est, min_low, low_timestamp_est

    except Exception as e:
        print(f"Error fetching data for {ticker} on {date_str} between 9:30 AM and 4:00 PM EST: {e}")
        return None, None, None, None


def get_premarket_volume(polygon_client, ticker, date_str):
    """
    Fetches the total volume for a given ticker and date during the pre-market hours (4:00 AM to 9:30 AM EST).

    Args:
        polygon_client: The initialized Polygon.io RESTClient.
        ticker (str): The stock ticker symbol.
        date_str (str): The date in 'YYYY-MM-DD' format.

    Returns:
        float: The total pre-market volume, or 0.0 if no data is available or an error occurs.
    """
    try:
        est_timezone = pytz.timezone('America/New_York')

        # Define the start and end times in EST for the pre-market session
        start_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 04:00", '%Y-%m-%d %H:%M'))
        end_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 09:30", '%Y-%m-%d %H:%M'))

        # Convert EST datetimes to UTC timestamps (in milliseconds) for the API call
        start_timestamp_utc_ms = int(start_datetime_est.timestamp() * 1000)
        end_timestamp_utc_ms = int(end_datetime_est.timestamp() * 1000)

        # Fetch 1-minute bar data for the specified pre-market range
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='minute',
            from_=start_timestamp_utc_ms,
            to=end_timestamp_utc_ms,
            limit=50000  # Increased limit to get all bars for the specified range
        )
        aggs_list = list(aggs_data)

        if not aggs_list:
            # print(f"No pre-market data available for {ticker} on {date_str}")
            return 0.0

        # Calculate the total volume in the pre-market period
        premarket_total_volume = sum(bar.volume for bar in aggs_list)

        return premarket_total_volume

    except Exception as e:
        print(f"Error fetching pre-market data for {ticker} on {date_str}: {e}")
        return 0.0  # Return 0.0 on error


def get_gap_up_day_stats(ticker, polygon_client):
    """
    Analyzes historical data for a given ticker to identify significant gap-ups.

    Args:
        ticker (str): The stock ticker symbol.
        polygon_client: The initialized Polygon.io RESTClient.
    Returns:
        list: A list of dictionaries, each representing a gap-up day with relevant data.
    """
    user_input_gap_up = 25
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=1095)  # Fetch data for the last 3 years

    try:
        aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='day',
            from_=start_date.strftime('%Y-%m-%d'),
            to=end_date.strftime('%Y-%m-%d'),
            adjusted='true',
            limit=10000
        )
        aggs_list = list(aggs_data)
    except Exception as e:
        print(f"Error fetching daily data for {ticker}: {e}")
        return []  # Return empty list on error

    gap_up_days = []

    for i in range(1, len(aggs_list)):
        previous_day_agg = aggs_list[i - 1]
        current_day_agg = aggs_list[i]

        previous_day_close = previous_day_agg.close
        current_day_open = current_day_agg.open
        current_day_volume = current_day_agg.volume  # Get total volume for the day

        if previous_day_close is not None and current_day_open is not None:
            gap_up_percent = ((current_day_open - previous_day_close) / previous_day_close) * 100

            if gap_up_percent >= user_input_gap_up:

                current_day_high = current_day_agg.high

                date_str = datetime.fromtimestamp(current_day_agg.timestamp / 1000).strftime('%Y-%m-%d')
                current_day_high_time = get_daily_high_low_data(ticker, polygon_client, date_str)[1]
                # print('current_day_high_time:', current_day_high_time)
                current_day_close = current_day_agg.close
                current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                percent_gap_high = ((
                                            current_day_high - previous_day_close) / previous_day_close) * 100 if previous_day_close is not None else None
                closing_percent = ((
                                           current_day_close - previous_day_close) / previous_day_close) * 100 if previous_day_close is not None else None

                # Fetch pre-market volume using the new function
                premarket_volume = get_premarket_volume(polygon_client, ticker, date_str)

                # Fetch Daily Ticker Summary for pre-market open, high, and after-hours close
                try:
                    daily_summary = polygon_client.get_daily_open_close_agg(
                        ticker=ticker,
                        date=date_str,
                        adjusted="true",
                    )
                    premarket_open = daily_summary.pre_market if daily_summary.pre_market else None
                    # Re-fetch premarket high and time using the specific premarket range to ensure accuracy
                    premarket_high, premarket_high_time, _, _ = get_premarket_high_low_data(ticker, polygon_client,
                                                                                            date_str)
                    afterhours_close = daily_summary.after_hours if daily_summary.after_hours else None
                except Exception as e:
                    print(f"Error fetching daily summary for {ticker} on {date_str}: {e}")
                    premarket_open = None
                    premarket_high = None
                    premarket_high_time = None
                    afterhours_close = None

                # Determine if the day was a Runner or Fader
                runner_fader = "Runner" if current_day_close > current_day_open else (
                    "Fader" if current_day_close < current_day_open else "Neutral")

                # Count VWAP crosses
                vwap_crosses = count_vwap_crosses(polygon_client, ticker, date_str)

                gap_up_days.append({
                    'date': date_str,
                    'pd close': previous_day_close,
                    'premarket open': premarket_open,
                    'premarket high': premarket_high,
                    'premarket high time': premarket_high_time,
                    'premarket volume': premarket_volume,  # Add pre-market volume
                    # 'premarket low' : premarket_low,
                    # 'premarket low time': premarket_low_time,
                    'open': current_day_open,
                    'gap up % at open': gap_up_percent,
                    'day high': current_day_high,
                    'day high time': current_day_high_time,
                    'day high %': percent_gap_high,
                    # 'day low' : current_day_low,
                    # 'day low time': current_day_low_time,
                    # 'day low %': percent_gap_low,
                    'close price': current_day_close,
                    'closing percent': closing_percent,
                    'afterhours close': afterhours_close,
                    'total volume': current_day_volume,  # Add total volume
                    'VWAP Crosses': vwap_crosses,
                    'Runner/Fader': runner_fader,

                })
    # print (gap_up_days)
    return gap_up_days


def fetch_intraday_1_min(polygon_client, ticker, date_str):
    """
    Fetches intraday 1-minute bar data for a given ticker and date for the first 30 minutes.

    Args:
        polygon_client: The initialized Polygon.io RESTClient.
        ticker (str): The stock ticker symbol.
        date_str (str): The date in 'YYYY-MM-DD' format.

    Returns:
        list: A list of intraday 1-minute bar aggregates for the first 30 minutes, or an empty list on error.
    """
    try:
        est_timezone = pytz.timezone('America/New_York')
        # Define the start and end times in EST for the first 30 minutes of trading
        start_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 09:30", '%Y-%m-%d %H:%M'))
        end_datetime_est = est_timezone.localize(datetime.strptime(f"{date_str} 10:00", '%Y-%m-%d %H:%M'))

        # Convert EST datetimes to UTC timestamps (in milliseconds) for the API call
        start_timestamp_utc_ms = int(start_datetime_est.timestamp() * 1000)
        end_timestamp_utc_ms = int(end_datetime_est.timestamp() * 1000)

        intraday_aggs_data = polygon_client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan='minute',
            from_=start_timestamp_utc_ms,
            to=end_timestamp_utc_ms,
            limit=50000  # Increased limit to ensure all bars in the 30 mins are fetched
        )
        return list(intraday_aggs_data)
    except Exception as e:
        print(f"Error fetching intraday data for {ticker} on {date_str}: {e}")
        return []


# Function from cell IwB-XnhKIW6f
import pdb  # Keep import here for now, will remove if not needed


def analyze_intraday_first_30_mins(intraday_aggs_list, daily_high):
    """
    Analyzes intraday 1-minute bar data for the first 30 minutes of trading.

    Args:
        intraday_aggs_list (list): A list of intraday 1-minute bar aggregates.
        daily_high (float): The high price for the entire trading day.

    Returns:
        tuple: A tuple containing:
            - max_price_30min (float or None): The maximum price within the first 30 minutes.
            - max_price_30min_timestamp (str or None): The timestamp (HH:MM) of the 30-min high.
            - high_within_30min (bool): True if the daily high occurred within the first 30 minutes.
            - volume_30min (float): The total volume within the first 30 minutes.
    """
    max_price_30min = None
    max_price_30min_timestamp = None
    interval_start_time = time(9, 30)
    interval_end_time_30min = time(10, 0)
    high_within_30min = False
    bars_in_30min = []
    volume_30min = 0  # Initialize volume for the first 30 minutes

    est_timezone = pytz.timezone('America/New_York')  # Define est_timezone here

    for bar in intraday_aggs_list:

        bar_datetime_utc = datetime.fromtimestamp(bar.timestamp / 1000, tz=pytz.utc)  # Assume timestamp is in UTC
        bar_datetime_est = bar_datetime_utc.astimezone(est_timezone)  # Convert to EST
        bar_time = bar_datetime_est.time()

        # pdb.set_trace() # Removed pdb trace

        if interval_start_time <= bar_time < interval_end_time_30min:
            # print('inside the intraday-aggs-list on ' + str(bar_datetime_est.strftime('%Y-%m-%d')) ) # Use EST datetime for printing
            bars_in_30min.append(bar)
            volume_30min += bar.volume  # Add volume of the bar

    if not bars_in_30min:
        return None, None, False, 0  # Return 0 for volume if no bars in 30 mins

    # Initialize max_price_30min with the high of the first bar
    max_price_30min = bars_in_30min[0].high
    # print('max_price_30min for RELI on: ' + str(datetime.fromtimestamp(bars_in_30min[0].timestamp / 1000).strftime('%Y-%m-%d')) + ' = ' + str( max_price_30min)) #datetime.strptime(date_str, '%Y-%m-%d').date()
    max_price_30min_timestamp = datetime.fromtimestamp(bars_in_30min[0].timestamp / 1000, tz=pytz.utc).astimezone(
        est_timezone).strftime('%H:%M')  # Convert and format timestamp

    for bar in bars_in_30min:
        if bar.high > max_price_30min:  # Corrected comparison to find max high
            # print('bar.high:', bar.high)
            max_price_30min = bar.high
            max_price_30min_timestamp = datetime.fromtimestamp(bar.timestamp / 1000, tz=pytz.utc).astimezone(
                est_timezone).strftime('%H:%M')  # Store as HH:MM string and convert timezone

        if bar.high == daily_high:
            high_within_30min = True

    return max_price_30min, max_price_30min_timestamp, high_within_30min, volume_30min  # Return volume_30min


def categorize_fade(runner_fader, high_within_30min, percent_high_from_open_30min):
    """
    Categorizes a 'Fader' day based on intraday price action.

    Args:
        runner_fader (str): The 'Runner' or 'Fader' label for the day.
        high_within_30min (bool): True if the daily high occurred within the first 30 minutes.
        percent_high_from_open_30min (float or None): The percentage difference between the
                                                    30-min high and the open price.

    Returns:
        str or None: The fade category ('Straight Down Fade', 'Quick Swipe and Fade',
                     'Steady gap up and Fade'), or None if not a Fader or category cannot be determined.
    """
    fade_category = None
    if runner_fader == "Fader":
        if high_within_30min and percent_high_from_open_30min is not None:
            if percent_high_from_open_30min < 10:
                fade_category = "Straight Down Fade"
            elif 10 <= percent_high_from_open_30min < 40:
                fade_category = "Quick Swipe and Fade"
            elif 40 <= percent_high_from_open_30min < 100:
                fade_category = "Steady gap up and Fade"
        elif not high_within_30min:
            fade_category = "Straight Down Fade"
    return fade_category


@app.route('/')
def index():
    """Renders the home page with the stock ticker input form."""
    return render_template('index.html', all_tickers_gap_up_results={})


@app.route('/analyze', methods=['POST'])
def analyze():
    """Handles the ticker input, fetches data, and displays the results."""
    tickers_input = request.form['ticker'].strip().upper()
    if not tickers_input:
        return render_template('index.html', error="Please enter a ticker symbol.", all_tickers_gap_up_results={})

    tickers = [t.strip() for t in tickers_input.split(',') if t.strip()]
    if not tickers:
        return render_template('index.html', error="Please enter at least one valid ticker.",
                               all_tickers_gap_up_results={})

    if polygon_client is None:
        return render_template('index.html', error="Polygon API client not initialized. Check API key.",
                               all_tickers_gap_up_results={})

    global all_tickers_gap_up_results
    all_tickers_gap_up_results = {}

    for ticker in tickers:
        print(f"Analyzing gap ups for {ticker}...")
        gap_up_days_list = get_gap_up_day_stats(ticker, polygon_client)
        if not gap_up_days_list:
            all_tickers_gap_up_results[ticker] = pd.DataFrame()  # Empty DataFrame for no results
            continue

        gap_up_results_df = pd.DataFrame(gap_up_days_list)

        # Store the results in SQLite database

        result_json = gap_up_results_df.to_json(orient='records')
        gapup = GapUpResult(ticker=ticker, result_json=result_json)
        db.session.add(gapup)
        db.session.commit()

        # Format the percentage columns
        for col in ['gap up % at open', 'day high %', 'closing percent']:
            if col in gap_up_results_df.columns:
                gap_up_results_df[col] = gap_up_results_df[col].apply(lambda x: f'{x:.2f}%' if pd.notna(x) else '')

        # Format volume columns in millions
        for col in ['total volume', '30min volume', 'premarket volume']:
            if col in gap_up_results_df.columns:
                gap_up_results_df[col] = gap_up_results_df[col].apply(
                    lambda x: f'{x / 1_000_000:.2f}M' if pd.notna(x) and x > 0 else (
                        '0M' if pd.notna(x) and x == 0 else ''))

        all_tickers_gap_up_results[ticker] = gap_up_results_df

    return render_template('index.html', all_tickers_gap_up_results=all_tickers_gap_up_results)


@app.route('/download/<ticker>')
def download_excel(ticker):
    """Provides the analysis results as an Excel file for download."""
    gapup = GapUpResult.query.filter_by(ticker=ticker).order_by(GapUpResult.created_at.desc()).first()
    if gapup:
        df = pd.read_json(gapup.result_json)
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name=f'{ticker}_GapUps')
        writer.close()
        output.seek(0)
        return send_file(output, download_name=f'{ticker}_gap_up_analysis.xlsx', as_attachment=True)
    else:
        return "Data not found for this ticker.", 404


@app.route('/download/all')
def download_all_excel():
    gapups = GapUpResult.query.order_by(GapUpResult.ticker, GapUpResult.created_at.desc()).all()
    if not gapups:
        return "No data available to download.", 404

    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    tickers_added = set()
    for gapup in gapups:
        if gapup.ticker not in tickers_added:
            # df = pd.read_json(gapup.result_json)
            df = pd.read_json(io.StringIO(gapup.result_json))
            if not df.empty:
                # writer.sheets = {}  # Fix for xlsxwriter bug
                df.to_excel(writer, index=False, sheet_name=gapup.ticker[:31])
            tickers_added.add(gapup.ticker)
    writer.close()
    output.seek(0)
    return send_file(output, download_name="all_gap_up_analysis.xlsx", as_attachment=True)


# Note: In a production environment, you would not run app.run() directly.
# You would use a production-ready WSGI server like Gunicorn.
# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#     app.run(debug=True)